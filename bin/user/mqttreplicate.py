#
#    Copyright (c) 2025-2026 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
''' Replicate WeeWX dstabases using MQTT request/response functionality.'''
import argparse
import dataclasses
import json
import logging
import queue
import random
import threading
import time
import traceback

import paho
import paho.mqtt
import paho.mqtt.client

import weecfg
import weeutil
import weeutil.logger
import weewx
import weewx.drivers
import weewx.engine

from weeutil.weeutil import to_bool, to_int

from user import mqttcommon

# All the weewx-mqtt extensions ship their own copy of mqttcommon. Fail loudly when the
# loaded copy is older than this extension needs, instead of with a mysterious error later.
if getattr(mqttcommon, 'MQTTCOMMON_API', (0, 0)) < (1, 0):
    raise ImportError("user.mqttcommon is too old. An older weewx-mqtt extension likely overwrote it during"
                      " install; reinstall or upgrade all the weewx-mqtt extensions.")

VERSION = "1.0.0-rc03c"
DRIVER_NAME = 'MQTTRequester'
DRIVER_VERSION = VERSION
REQUEST_TOPIC = 'replicate/request'
RESPONSE_TOPIC = 'replicate/response'
ARCHIVE_TOPIC = 'replicate/archive'

class ThreadError(Exception):
    ''' Exception raised when a critical error occurs in a child thread. '''

class Logger:
    ''' Manage the logging.
        Messages are queued and written by a LoggerThread, so logging never blocks the caller. '''
    # The default time shutdown waits for the LoggerThread to flush queued messages.
    SHUTDOWN_TIMEOUT = 10

    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.log_queue = queue.Queue()
        self.log_functions = {
            'DEBUG': self._log_debug,
            'INFO': self._log_info,
            'ERROR': self._log_error,
        }
        self.log_thread = LoggerThread(self.log_queue, self)
        self.log_thread.start()

    def logdbg(self, msg):
        """ queue debug messages """
        self.log_queue.put({'log_type': 'DEBUG', 'thread_id': threading.get_native_id(), 'msg_text': msg})

    def loginf(self, msg):
        """ queue informational messages """
        self.log_queue.put({'log_type': 'INFO', 'thread_id': threading.get_native_id(), 'msg_text': msg})

    def logerr(self, msg):
        """ queue error messages """
        self.log_queue.put({'log_type': 'ERROR', 'thread_id': threading.get_native_id(), 'msg_text': msg})

    def log_entry(self, entry):
        """ Log a queued entry. This is called by the LoggerThread. """
        self.log_functions[entry['log_type']](entry)

    def shutdown(self, timeout=SHUTDOWN_TIMEOUT):
        """ Stop the logger thread, flushing queued messages. """
        if not self.log_thread.is_alive():
            return

        self.log_queue.put(None)
        self.log_thread.join(timeout)
        if self.log_thread.is_alive():
            self._log_error({'thread_id': threading.get_native_id(),
                             'msg_text': f"Unable to shut down {self.log_thread.name} thread"})

    def _log_debug(self, entry):
        """ write a debug message """
        self.log.debug("(%s) %s", entry['thread_id'], entry['msg_text'])

    def _log_info(self, entry):
        """ write an informational message """
        self.log.info("(%s) %s", entry['thread_id'], entry['msg_text'])

    def _log_error(self, entry):
        """ write an error message """
        self.log.error("(%s) %s", entry['thread_id'], entry['msg_text'])

class LoggerThread(mqttcommon.QueueLoggerThread):
    ''' Thread to drain the Logger's queue and write the messages.
        The queue loop is inherited from mqttcommon.QueueLoggerThread. '''
    def start_entry(self):
        """ Return the entry logged when the thread starts. """
        return {'log_type': 'INFO', 'thread_id': threading.get_native_id(), 'msg_text': "Starting logger thread"}

    def exit_entry(self):
        """ Return the entry logged when the thread exits. """
        return {'log_type': 'INFO', 'thread_id': threading.get_native_id(),
                'msg_text': f"Exited logger thread, {self.name}."}

    def invalid_entry(self, entry):
        """ Return the error entry logged for an entry that could not be logged. """
        return {'log_type': 'ERROR', 'thread_id': threading.get_native_id(), 'msg_text': entry}

class MQTTClient():  # (paho callback adapter) pylint: disable=too-many-instance-attributes
    ''' Wrap paho mqtt to protect from breaking changes. '''
    def __init__(self, logger, client_id, userdata):
        if not mqttcommon.has_v2_api():
            raise ValueError("paho mqtt v2 is required.")

        self.logger = logger
        self.client_id = client_id
        self.client = mqttcommon.create_client(mqttcommon.API_V2_MQTT5,
                                               client_id=client_id,
                                               protocol=paho.mqtt.client.MQTTv5,
                                               userdata=userdata)

        # The reconnect delays are not configurable; use the paho defaults.
        mqttcommon.configure_reconnect_delay(self.client, min_delay=1, max_delay=128)

        self._on_connect = None
        self._on_connect_fail = None
        self._on_disconnect = None
        self._on_log = None
        self._on_message = None
        self._on_publish = None
        self._on_subscribe = None

    # Properties for each supported callback

    @property
    def on_connect(self):
        ''' The on_connect call back function. '''
        return self._on_connect

    @on_connect.setter
    def on_connect(self, value):
        self._on_connect = value
        if value:
            self.client.on_connect = self._client_on_connect
        else:
            self.client.on_connect = None

    @property
    def on_connect_fail(self):
        ''' The on_connect_fail call back function. '''
        return self._on_connect_fail

    @on_connect_fail.setter
    def on_connect_fail(self, value):
        self._on_connect_fail = value
        if value:
            self.client.on_connect_fail = self._client_on_connect_fail
        else:
            self.client.on_connect_fail = None

    @property
    def on_disconnect(self):
        ''' The on_disconnect call back function. '''
        return self._on_disconnect

    @on_disconnect.setter
    def on_disconnect(self, value):
        self._on_disconnect = value
        if value:
            self.client.on_disconnect = self._client_on_disconnect
        else:
            self.client.on_disconnect = None

    @property
    def on_log(self):
        ''' The on_log call back function. '''
        return self._on_log

    @on_log.setter
    def on_log(self, value):
        self._on_log = value
        if value:
            self.client.on_log = self._client_on_log
        else:
            self.client.on_log = None

    @property
    def on_message(self):
        ''' The on_message call back function. '''
        return self._on_message

    @on_message.setter
    def on_message(self, value):
        self._on_message = value
        if value:
            self.client.on_message = self._client_on_message
        else:
            self.client.on_message = None

    @property
    def on_publish(self):
        ''' The on_publish call back function. '''
        return self._on_publish

    @on_publish.setter
    def on_publish(self, value):
        self._on_publish = value
        if value:
            self.client.on_publish = self._client_on_publish
        else:
            self.client.on_publish = None

    @property
    def on_subscribe(self):
        ''' The on_subscribe call back function. '''
        return self._on_subscribe

    @on_subscribe.setter
    def on_subscribe(self, value):
        self._on_subscribe = value
        if value:
            self.client.on_subscribe = self._client_on_subscribe
        else:
            self.client.on_subscribe = None

    # The  wrappers of the callbacks are next

    def _client_on_connect(self, _client, userdata, flags, reason_code, _properties):
        self.logger.logdbg(f"Connected with result code {int(reason_code.value)}-{reason_code}")
        self.logger.logdbg(f"(Connected flags {str(flags)}")
        self._on_connect(userdata)

    def _client_on_connect_fail(self, _client, userdata):
        self._on_connect_fail(userdata)

    def _client_on_disconnect(self, _client, userdata, _flags, reason_code, _properties):
        self.logger.logdbg(f"Disconnected with result code {int(reason_code.value)}-{reason_code}")
        self._on_disconnect(userdata, reason_code.value)

    def _client_on_log(self, _client, userdata, level, msg):
        """ The on_log callback. """
        self._on_log(userdata, level, msg)

    def _client_on_message(self, _client, userdata, msg):
        self._on_message(userdata, msg)

    def _client_on_publish(self, _client, userdata, mid, _reason_codes, _properties):
        """ The on_publish callback. """
        self._on_publish(userdata, mid)

    def _client_on_subscribe(self, _client, userdata, mid, _reason_code_list, _properties):
        self._on_subscribe(userdata, mid)

    # The wrappers of the  client methods are next

    def connect(self, host, port, keepalive):
        ''' Connect to the MQTT server. '''
        mqttcommon.connect(self.client, mqttcommon.API_V2_MQTT5, host=host, port=port, keepalive=keepalive)

    def disconnect(self):
        ''' Disconnect from the MQTT server. '''
        self.client.disconnect()

    def loop_forever(self):
        ''' Run the network loop forever. '''
        self.client.loop_forever()

    def loop(self, blocking_time):
        ''' Run the network loop, checking for new messages every blocking_time. '''
        self.client.loop(blocking_time)

    def publish(self, topic, data, qos, retain, properties=None):
        ''' Publish a MQTT message. '''
        return self.client.publish(topic, data, qos, retain, properties)

    def subscribe(self, topic, qos):
        ''' Subscribe to a MQTT topic. '''
        return self.client.subscribe(topic, qos)

def paho_log_methods(logger):
    ''' Map the paho mqtt log levels to the logger methods. '''
    logger_methods = {'DEBUG': 'logdbg', 'INFO': 'loginf', 'ERROR': 'logerr'}
    return {level: getattr(logger, logger_methods[level_name])
            for level, level_name in mqttcommon.PAHO_LOG_LEVELS.items()}

@dataclasses.dataclass
# (configuration object) pylint: disable=too-many-instance-attributes
class MQTTResponderConfig:
    ''' The configuration options for the responder. '''
    client_id: str = None
    enabled: bool = None
    instance_name: str = None
    request_topic: str = None
    archive_topic: str = None
    delta: int = None
    throttle_count: int = None
    throttle_sleep: int = None
    log_msg_count: int = None
    host: str = None
    port: int = None
    keepalive: int = None
    subscribe_qos: int = None
    publish_qos: int = None
    max_responder_threads: int = None
    log_mqtt: bool = None

def parse_responder_config(config_dict, logger):
    ''' Parse the responder's configuration options. '''
    client_id = 'MQTTReplicateRespond-' + str(random.randint(1000, 9999))

    enabled = to_bool(config_dict.get('MQTTReplicate', {})
                      .get('Responder', {})
                      .get('enable', True))
    if not enabled:
        return MQTTResponderConfig(client_id=client_id, enabled=False)

    service_dict = config_dict.get('MQTTReplicate', {}).get('Responder', {})
    exclude_keys = ['password']
    sanitized_service_dict = {k: service_dict[k] for k in set(list(service_dict.keys())) - set(exclude_keys)}
    logger.logdbg(f"sanitized configuration removed {exclude_keys}")
    logger.logdbg(f"sanitized_service_dict is {sanitized_service_dict}")

    if len(service_dict.sections) > 1:
        raise AttributeError("Only one instance is allowed.")

    if not service_dict.sections:
        raise AttributeError("At least one instance is required.")

    instance_name = service_dict.sections[0]
    throttle_count = to_int(service_dict.get('throttle_count', 1000))

    return MQTTResponderConfig(
        client_id=client_id,
        enabled=True,
        instance_name=instance_name,
        request_topic=service_dict.get('request_topic', f'{REQUEST_TOPIC}/{instance_name}'),
        archive_topic=service_dict.get('archive_topic', ARCHIVE_TOPIC),
        delta=to_int(service_dict.get('delta', 60)),
        throttle_count=throttle_count,
        throttle_sleep=to_int(service_dict.get('throttle_sleep', 1)),
        log_msg_count=to_int(service_dict.get('log_msg_count', throttle_count)),
        host=service_dict.get('host', 'localhost'),
        port=to_int(service_dict.get('port', 1883)),
        keepalive=to_int(service_dict.get('keepalive', 60)),
        subscribe_qos=to_int(service_dict.get('subscribe_qos', 1)),
        publish_qos=to_int(service_dict.get('publish_qos', 1)),
        max_responder_threads=to_int(service_dict.get('max_responder_threads', 1)),
        log_mqtt=to_bool(service_dict.get('log_mqtt', False)),
    )

class MQTTResponder(weewx.engine.StdService):
    # (service state) pylint: disable=too-many-instance-attributes
    ''' The "server" that sends the replication data to the requester/client. '''
    def __init__(self, engine, config_dict):
        super().__init__(engine, config_dict)
        self.logger = Logger()
        self.logger.loginf(f"version: {VERSION}")

        self.config = parse_responder_config(config_dict, self.logger)
        self.client_id = self.config.client_id
        self.logger.logdbg(f"Responder main MQTT client is: {self.client_id}")

        self.enabled = self.config.enabled
        if not self.enabled:
            self.logger.loginf("Responder not enabled, exiting.")
            return

        self.main_data_binding = None
        self.data_bindings = {}
        service_dict = config_dict.get('MQTTReplicate', {}).get('Responder', {})
        for data_binding_name, data_binding in service_dict[self.config.instance_name].items():
            data_binding_key = f"{self.config.instance_name}/{data_binding_name}"
            self.data_bindings[data_binding_key] = {}
            self.data_bindings[data_binding_key]['delta'] = data_binding.get('delta', self.config.delta)
            self.data_bindings[data_binding_key]['type'] = data_binding.get('type', 'secondary')
            manager_dict = weewx.manager.get_manager_dict_from_config(config_dict,
                                                                      data_binding_name)
            self.data_bindings[data_binding_key]['dbmanager'] = \
                weewx.manager.open_manager(manager_dict)
            if self.data_bindings[data_binding_key]['type'] == 'main':
                if self.main_data_binding is not None:
                    raise ValueError(f"Multiple 'main' data bindings found: {self.main_data_binding}, {data_binding_key}")
                self.main_data_binding = data_binding_key

        self.logger.logdbg(f"data bindings are: {self.data_bindings}")

        if self.main_data_binding is None:
            raise ValueError("No 'main' data bindings found")

        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

        self.data_queue = queue.Queue()
        self.threads = []
        # A shared event, so a thread pool thread can signal that it has failed.
        self.thread_error = threading.Event()
        for _i in range(self.config.max_responder_threads):
            thread = MQTTResponderThread(self.logger,
                                         self.thread_error,
                                         self.data_queue,
                                         self.config,
                                         config_dict)
            thread.start()
            self.threads.append(thread)

        self.mqtt_client = MQTTClient(self.logger, self.client_id, None)

        self.loop_thread = MQTTResponderLoopThread(self.logger,
                                                   self.mqtt_client,
                                                   self.config,
                                                   self.data_queue,
                                                   self.data_bindings)
        self.loop_thread.start()

    def shutDown(self):
        self.logger.loginf('Shutting down.')
        try:
            if not self.enabled:
                return

            for _, data_binding in self.data_bindings.items():
                data_binding['dbmanager'].close()

            self.mqtt_client.disconnect()
            self.loop_thread.join(20.0)
            if self.loop_thread.is_alive():
                self.logger.logerr(f"Unable to shut down {self.loop_thread.native_id} thread")
            else:
                self.logger.loginf(f"Shut down {self.loop_thread.native_id} thread")

            for _ in range(self.config.max_responder_threads):
                self.data_queue.put(None)

            for thread in self.threads:
                thread.join(20)
                if thread.is_alive():
                    self.logger.logerr(f"Unable to shut down {thread.native_id} thread")
                else:
                    self.logger.loginf(f"Shut down {thread.native_id} thread")
        finally:
            # Flush the queued messages after the threads that produced them have stopped.
            self.logger.shutdown()

    def new_archive_record(self, event):
        ''' Handle the new_archive_record event.'''
        if not self.loop_thread.is_alive():
            raise ThreadError('Loop thread abnormally ended')
        if self.thread_error.is_set():
            raise ThreadError('A thread pool thread abnormally ended.')
        for data_binding_name, data_binding in self.data_bindings.items():
            if data_binding['type'] == 'main':
                continue

            timestamp = event.record['dateTime']
            # some extensions do not force the timestamp to be on an interval
            record = data_binding['dbmanager'].getRecord(timestamp, max_delta=data_binding['delta'])
            if record:
                payload = json.dumps(record)
                self.publish_payload(data_binding_name, self.config.publish_qos, payload)
            else:
                self.logger.loginf(f'No record found for binding {data_binding_name} '
                                   f'and timestamp {timestamp}.')

        payload = json.dumps(event.record)
        self.publish_payload(self.main_data_binding, self.config.publish_qos, payload)

    def publish_payload(self, data_binding_name, qos, payload):
        ''' Publish the record. '''
        properties = paho.mqtt.client.Properties(paho.mqtt.client.PacketTypes.PUBLISH)
        properties.UserProperty = [
            ('data_binding', data_binding_name)
        ]
        self.logger.logdbg(f'Publishing on topic {self.config.archive_topic}, properties {properties}, payload: {payload}.')
        self.mqtt_client.publish(self.config.archive_topic,
                                 payload,
                                 qos,
                                 False,
                                 properties=properties)
class MQTTResponderLoopThread(threading.Thread):
    ''' The MQTT 'loop' thread. '''
    def __init__(self,
                 logger,
                 mqtt_client,
                 config,
                 data_queue,
                 data_bindings):
        threading.Thread.__init__(self)
        self.thread_id = 0
        self.logger = logger
        self.mqtt_client = mqtt_client
        self.config = config
        self.data_queue = data_queue
        self.data_bindings = data_bindings

        self.mqtt_client.on_connect = self._on_connect
        if config.log_mqtt:
            self.mqtt_client.on_log = self._on_log
        self.mqtt_client.on_message = self._on_message

        self.mqtt_logger = paho_log_methods(self.logger)
        mqtt_client.connect(config.host, config.port, config.keepalive)

    def run(self):
        self.thread_id = threading.get_native_id()
        threading.current_thread().name = f"MQTTReplicate-{self.thread_id}"
        self.logger.loginf(f"MQTTResponderLoopThread, {threading.current_thread().name}, is running.")
        self.mqtt_client.loop_forever()

    def _on_connect(self, _userdata):
        (result, mid) = self.mqtt_client.subscribe(self.config.request_topic, self.config.subscribe_qos)
        self.logger.loginf(f"Subscribing to topic {self.config.request_topic} "
                           f"returned mid {int(mid)} "
                           f"and result {int(result)}.")

    def _on_log(self, _client, _userdata, level, msg):
        self.mqtt_logger.get(level, self.logger.loginf)(f"({self.config.client_id}) MQTT log: {msg}")

    def _on_message(self, _userdata, msg):
        try:
            self.logger.logdbg(f"Request has, topic: {msg.topic}, "
                               f"properties: {msg.properties} "
                               f"QOS: {int(msg.qos)}, "
                               f"retain: {msg.retain}, "
                               f"payload: {msg.payload} ")

            if not hasattr(msg.properties, 'UserProperty'):
                self.logger.logerr(f'Request with topic skipped: {msg.topic} '
                                   f'payload: {msg.payload} '
                                   'has no UserProperty')

                return

            user_property = msg.properties.UserProperty
            data_binding = None
            for keyword_value in user_property:
                if keyword_value[0] == 'data_binding':
                    data_binding = keyword_value[1]
                    break

            if not data_binding:
                self.logger.logerr(f'Request with topic skipped: {msg.topic} '
                                   f'UserProperty: {msg.properties.UserProperty} '
                                   f'payload: {msg.payload} '
                                   'has no data_binding')
                return

            if data_binding not in self.data_bindings:
                self.logger.logerr(f'Request with topic skipped: {msg.topic} '
                                   f'UserProperty: {msg.properties.UserProperty} '
                                   f'payload: {msg.payload} '
                                   f'has unknown data_binding {data_binding}')
                return

            response_topic = msg.properties.ResponseTopic

            properties = paho.mqtt.client.Properties(paho.mqtt.client.PacketTypes.PUBLISH)
            properties.UserProperty = [
                ('data_binding', data_binding)
            ]

            start_timestamp = int(msg.payload.decode('utf-8'))

            data = {'topic': response_topic,
                    'start_timestamp': start_timestamp,
                    'data_binding': data_binding,
                    'properties': properties}
            self.data_queue.put(data)
            self.logger.logdbg(f'Request with data binding {data_binding}, '
                               f'response topic {response_topic} has been queued for processing: {data}')
        except Exception as exception:  # (want to catch all ) pylint: disable=broad-exception-caught
            self.logger.logerr(f"Request message failed with {type(exception)} and reason {exception}.")
            self.logger.logerr(f"{traceback.format_exc()}")
            self.mqtt_client.disconnect()

class MQTTResponderThread(threading.Thread):
    # (thread state) pylint: disable=too-many-instance-attributes
    '''  Publish the requested data. '''
    def __init__(self,
                 logger,
                 thread_error,
                 data_queue,
                 config,
                 config_dict):
        threading.Thread.__init__(self)
        self.thread_id = threading.get_native_id()
        self.logger = logger
        self.thread_error = thread_error
        self.data_queue = data_queue
        self.config = config
        self.config_dict = config_dict
        self.client_id = 'MQTTReplicateRespondThread-' + str(random.randint(1000, 9999))

        self.logger.logdbg(f"Responder catchup MQTT client is: {self.client_id}")

        self.data_bindings = {}

        service_dict = config_dict.get('MQTTReplicate', {}).get('Responder', {})

        for data_binding_name, data_binding in service_dict[config.instance_name].items():
            data_binding_key = f"{config.instance_name}/{data_binding_name}"
            self.data_bindings[data_binding_key] = {}
            self.data_bindings[data_binding_key]['delta'] = data_binding.get('delta', config.delta)
            self.data_bindings[data_binding_key]['type'] = data_binding.get('type', 'secondary')
            self.data_bindings[data_binding_key]['manager_dict'] = \
                weewx.manager.get_manager_dict_from_config(config_dict, data_binding_name)

        self.mqtt_logger = paho_log_methods(self.logger)

        self.mids = {}
        self.mqtt_client = MQTTClient(self.logger, self.client_id, None)

        self.mqtt_client.on_connect = self._on_connect
        if config.log_mqtt:
            self.mqtt_client.on_log = self._on_log
        self.mqtt_client.on_publish = self._on_publish

    def run(self):
        ''' Publish the data. '''
        threading.current_thread().name = f"MQTTReplicate-{self.thread_id}"
        self.logger.loginf(f"MQTTResponderThread, {threading.current_thread().name}, is running.")
        for _data_binding_key, data_binding in self.data_bindings.items():
            data_binding['dbmanager'] = weewx.manager.open_manager(data_binding['manager_dict'])

        while True:
            try:
                data = self.data_queue.get()
                if not data:
                    break
                self._respond(data)
            except Exception as exception:  # (want to catch all ) pylint: disable=broad-exception-caught
                self.logger.logerr(f'Responding/publishing topic {data["topic"]} '
                                   f'data_binding {data["data_binding"]} '
                                   f'qos {self.config.publish_qos} '
                                   f'properties {data["properties"]} '
                                   f"failed with {type(exception)} and reason {exception}.")
                self.logger.logerr(f"{traceback.format_exc()}")
                self.thread_error.set()
                break

        for _data_binding_key, data_binding in self.data_bindings.items():
            data_binding['dbmanager'].close()

    def _respond(self, data):
        ''' Respond to one request by publishing its records. '''
        self.logger.logdbg(f"In MQTTResponderThread.run request: {data}")

        # ToDo: Wait for connection?
        self.mqtt_client.connect(self.config.host, self.config.port, self.config.keepalive)

        record_count = self._publish_records(data)

        self.logger.loginf(f'Responding/publishing topic {data["topic"]} '
                           f'data_binding {data["data_binding"]} '
                           f'qos {self.config.publish_qos} '
                           f'properties {data["properties"]} '
                           f'with records: {record_count}.')
        self._wait_for_publish(data)
        self.mqtt_client.disconnect()

    def _publish_records(self, data):
        ''' Publish the batch of records for one request; return the record count. '''
        record_count = 0
        self.logger.logdbg(f'Responding/publishing topic {data["topic"]} '
                           f'data_binding {data["data_binding"]} '
                           f'qos {self.config.publish_qos} '
                           f'properties {data["properties"]}')
        for record in self.data_bindings[data['data_binding']]['dbmanager']\
                .genBatchRecords(data['start_timestamp']):
            record_count += 1
            payload = json.dumps(record)
            self.logger.logdbg(f"Responding/publishing on topic {data['topic']}, properties {data['properties']}, payload: {payload}.")
            mqtt_message_info = self.mqtt_client.publish(data['topic'],
                                                         payload,
                                                         self.config.publish_qos,
                                                         False,
                                                         properties=data['properties'])
            if mqtt_message_info.rc > 0:
                self.logger.logerr(f"Error {int(mqtt_message_info.rc)}, "
                                   f"{paho.mqtt.client.error_string(mqtt_message_info.rc)} "
                                   f"responding/publishing on topic {data['topic']}, "
                                   f"properties {data['properties']}, payload: {payload}.")

            self.mqtt_client.loop(.1)

            self._track_mid(mqtt_message_info)

            if record_count % self.config.log_msg_count == 0:
                self.logger.loginf(f"{record_count} 'catchup' records {weeutil.weeutil.timestamp_to_string(record['dateTime'])} "
                                   "have been published.")

            if record_count % self.config.throttle_count == 0:
                time.sleep(self.config.throttle_sleep)

        return record_count

    def _track_mid(self, mqtt_message_info):
        ''' Record a published message 'mid' until _on_publish reports it done. '''
        # Add the message 'mid' to the 'mids collection', self.mids.
        # This collection will be monitored (in _on_publish) to know when it safe to disconnect.
        # Sometimes on_publish is called before the call returns
        # In that case, the 'inflight' mid was added in the on_publish callback.
        # So, we remove it here.
        if mqtt_message_info.mid in self.mids:
            del self.mids[mqtt_message_info.mid]
        else:
            self.mids[mqtt_message_info.mid] = {}
            self.mids[mqtt_message_info.mid]['time_stamp'] = time.time()
            self.mids[mqtt_message_info.mid]['qos'] = self.config.publish_qos

    def _wait_for_publish(self, data):
        ''' Wait for the outstanding messages to be published. '''
        # Bound the wait by the keepalive, so a lost connection
        # does not hang the thread forever.
        wait_start = time.time()
        while self.mids:
            if time.time() - wait_start > self.config.keepalive:
                self.logger.logerr(f'Timed out after {self.config.keepalive} seconds '
                                   f'waiting for {len(self.mids)} messages '
                                   f'to be published on topic {data["topic"]}.')
                break
            self.mqtt_client.loop(1)

    def _on_connect(self, _userdata):
        pass

    def _on_publish(self, _userdata, mid):
        if mid in self.mids:
            # time_stamp = self.mids[mid]['time_stamp']
            # qos = self.mids[mid]['qos']
            del self.mids[mid]
        # Sometimes on_publish is called before publish call returns.
        # So we will add the 'inflight' mid here instead.
        # I think this happens when qos=0
        else:
            self.mids[mid] = {}

    def _on_log(self, _client, _userdata, level, msg):
        self.mqtt_logger.get(level, self.logger.loginf)(f"Client {self.client_id} MQTT log: {msg}")

def loader(config_dict, engine):
    """ Load and return the driver. """
    return MQTTRequester(config_dict, engine)  # pragma: no cover

@dataclasses.dataclass
# (configuration object) pylint: disable=too-many-instance-attributes
class MQTTRequesterConfig:
    ''' The configuration options for the requester. '''
    client_id: str = None
    loop_interval: float = None
    archive_interval: int = None
    startup_max_tries: float = None
    startup_wait_before_retry: float = None
    archive_max_tries: float = None
    archive_wait_before_retry: float = None
    subscribe_qos: int = None
    publish_qos: int = None
    archive_topic: str = None
    response_topic: str = None
    request_topic: str = None
    host: str = None
    port: int = None
    keepalive: int = None
    log_mqtt: bool = None

def parse_requester_config(config_dict, logger):
    ''' Parse the requester's configuration options. '''
    client_id = 'MQTTReplicateRequest-' + str(random.randint(1000, 9999))

    stn_dict = config_dict['MQTTReplicate']['Requester']
    exclude_keys = ['password']
    sanitized_service_dict = {k: stn_dict[k] for k in set(list(stn_dict.keys())) - set(exclude_keys)}
    logger.logdbg(f"sanitized configuration removed {exclude_keys}")
    logger.logdbg(f"sanitized_service_dict is {sanitized_service_dict}")

    response_topic = stn_dict.get('response_topic', RESPONSE_TOPIC)
    request_topic = stn_dict.get('request_topic', REQUEST_TOPIC)

    return MQTTRequesterConfig(
        client_id=client_id,
        loop_interval=float(stn_dict.get('loop_interval', 2.5)),
        archive_interval=to_int(stn_dict.get('archive_interval', 300)),
        startup_max_tries=float(stn_dict.get('startup_max_tries', 2)),
        startup_wait_before_retry=float(stn_dict.get('startup_wait_before_retry', 10)),
        archive_max_tries=float(stn_dict.get('archive_max_tries', 2)),
        archive_wait_before_retry=float(stn_dict.get('archive_wait_before_retry', 10)),
        subscribe_qos=to_int(stn_dict.get('subscribe_qos', 1)),
        publish_qos=to_int(stn_dict.get('publish_qos', 1)),
        archive_topic=stn_dict.get('archive_topic', ARCHIVE_TOPIC),
        response_topic=f'{response_topic}/{client_id}',
        request_topic=request_topic,
        host=stn_dict.get('host', 'localhost'),
        port=to_int(stn_dict.get('port', 1883)),
        keepalive=to_int(stn_dict.get('keepalive', 60)),
        log_mqtt=to_bool(stn_dict.get('log_mqtt', False)),
    )

class MQTTRequester(weewx.drivers.AbstractDevice):
    # (methods not used) pylint: disable=abstract-method
    # (driver state) pylint: disable=too-many-instance-attributes
    ''' The "client" class that data ts replicated to. '''
    def __init__(self, config_dict, _engine):
        self.logger = Logger()
        self.logger.loginf(f"version: {VERSION}")

        self.config = parse_requester_config(config_dict, self.logger)
        self.client_id = self.config.client_id
        self.logger.logdbg(f"Requester main MQTT client is: {self.client_id}")

        self.the_time = time.time()
        self.response_topic = self.config.response_topic

        self.main_data_binding = None
        self.data_bindings = {}
        self._build_data_bindings(config_dict)

        self.mqtt_client = MQTTClient(self.logger, self.client_id, None)

        self.data_queue = queue.PriorityQueue()

        self.loop_thread = MQTTRequesterLoopThread(self.logger,
                                                   self.mqtt_client,
                                                   self.config,
                                                   self.data_queue,
                                                   self.data_bindings)
        self.loop_thread.start()

        self.logger.logdbg("Waiting for subscriptions to be set.")
        while not self.loop_thread.subscribed:
            time.sleep(1)

        # Request any possible missing records
        # Do it now, so hopefully queue is primed when genStartupRecords is called
        self._request_missing_records()

    def _build_data_bindings(self, config_dict):
        ''' Build the data bindings and validate the 'main' binding. '''
        stn_dict = config_dict['MQTTReplicate']['Requester']
        for instance_name in stn_dict.sections:
            for primary_name, binding in stn_dict[instance_name].items():
                self._add_data_binding(config_dict, instance_name, primary_name, binding)

        self.logger.logdbg(f"data bindings are: {self.data_bindings}")

        if self.main_data_binding is None:
            raise ValueError("No 'main' data bindings found")
        self.logger.logdbg(f"main data bindings is: {self.main_data_binding}")

    def _add_data_binding(self, config_dict, instance_name, primary_name, binding):
        ''' Add one data binding, tracking the 'main' binding. '''
        secondary_name = binding['secondary_data_binding']
        data_binding_key = f'{instance_name}/{primary_name}'
        self.data_bindings[data_binding_key] = {}
        self.data_bindings[data_binding_key]['request_topic'] = (f'{self.config.request_topic}/'
                                                                 f'{instance_name}')
        self.data_bindings[data_binding_key]['type'] = binding.get('type', 'secondary')
        self.data_bindings[data_binding_key]['manager_dict'] = \
            weewx.manager.get_manager_dict_from_config(config_dict, secondary_name)
        # 5/1/2024 - The DBBinder is instantiated after the driver
        # db_manager = engine.db_binder.get_manager(data_binding=secondary_name,
        #                                          initialize=False)
        db_manager = \
            weewx.manager.open_manager(self.data_bindings[data_binding_key]['manager_dict'],
                                       initialize=binding.get('initialize', True))

        self.data_bindings[data_binding_key]['last_good_timestamp'] = \
            db_manager.lastGoodStamp()
        if self.data_bindings[data_binding_key]['last_good_timestamp'] is None:
            self.data_bindings[data_binding_key]['last_good_timestamp'] = 0

        self.data_bindings[data_binding_key]['dbmanager'] = None
        if self.data_bindings[data_binding_key]['type'] == 'main':
            if self.main_data_binding is not None:
                raise ValueError(f"Multiple 'main' data bindings found: {self.main_data_binding}, {data_binding_key}")
            self.main_data_binding = data_binding_key

    def _request_missing_records(self):
        ''' Request any records missing from the secondary bindings. '''
        for data_binding_name, data_binding in self.data_bindings.items():
            if data_binding['type'] == 'main':
                continue
            self.request_records(data_binding_name,
                                 self.config.publish_qos,
                                 data_binding['request_topic'],
                                 data_binding['last_good_timestamp'])

        if self.main_data_binding:
            # Request 'main' last, so new_archive_record event fired after other DBs are updated
            self.request_records(self.main_data_binding,
                                 self.config.publish_qos,
                                 self.data_bindings[self.main_data_binding]['request_topic'],
                                 self.data_bindings[self.main_data_binding]['last_good_timestamp'])

    @property
    def hardware_name(self):
        """ The name of the hardware driver. """
        return DRIVER_NAME

    @property
    def archive_interval(self):
        """ The archive interval. """
        return self.config.archive_interval

    def genStartupRecords(self, _lastgood_ts):
        record_count = 0
        record = {'dateTime': 0}
        for record in self.gen_replica_record(self.config.startup_max_tries,
                                              self.config.startup_wait_before_retry):
            record_count += 1
            # ToDo: Make configurable
            if record_count % 1000 == 0:
                self.logger.loginf(f"Received {record_count} 'catchup' records, {weeutil.weeutil.timestamp_to_string(record['dateTime'])}")
            yield record

        # ToDo: decided what to do when record_count is 0
        self.logger.loginf(f"Received {record_count} 'catchup' records, {weeutil.weeutil.timestamp_to_string(record['dateTime'])}")

    def genArchiveRecords(self, _lastgood_ts):
        yield from self.gen_replica_record(self.config.archive_max_tries,
                                           self.config.archive_wait_before_retry)

    def gen_replica_record(self, max_tries, wait_before_retry):
        ''' Generator to return the records that are in the queue. '''
        tries = 0
        while True:
            try:
                record = self.data_queue.get(True, wait_before_retry)[1]
                tries = 0
                yield record
            except queue.Empty:
                tries += 1
                self.logger.logdbg(f"No replica record available after a wait of {wait_before_retry} seconds, "
                                   f"try {tries} of {max_tries}.")
                if tries >= max_tries:
                    break

    def genLoopPackets(self):
        while True:
            if not self.loop_thread.is_alive():
                raise ThreadError(' Loop thread abnormally ended')
            sleep_time = self.the_time + self.config.loop_interval - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)

            self.the_time += self.config.loop_interval
            yield {'dateTime': int(self.the_time + 0.5),
                   'usUnits': weewx.US}

    def closePort(self):
        """Run when an engine shutdown is requested."""
        self.mqtt_client.disconnect()
        # ToDo: add ability to exit loop after X time
        while self.loop_thread.running:
            time.sleep(1)
        self.logger.loginf("Exiting MQTTRequester")
        self.logger.shutdown()

    def request_records(self, data_binding_name, qos, topic, last_ts):
        ''' Request the missing data. '''
        properties = paho.mqtt.client.Properties(paho.mqtt.client.PacketTypes.PUBLISH)
        properties.ResponseTopic = self.response_topic
        properties.UserProperty = [
            ('data_binding', data_binding_name)
        ]

        self.logger.loginf(f"Request 'catchup' on topic {topic}, properties {properties}, payload/timestamp: {last_ts}.")

        self.mqtt_client.publish(topic,
                                 last_ts,
                                 qos,
                                 False,
                                 properties=properties)

class MQTTRequesterLoopThread(threading.Thread):
    # (thread state) pylint: disable=too-many-instance-attributes
    ''' The MQTT 'loop' thread. '''
    def __init__(self,
                 logger,
                 mqtt_client,
                 config,
                 data_queue,
                 data_bindings):
        threading.Thread.__init__(self)
        self.thread_id = 0
        self.logger = logger
        self.mqtt_client = mqtt_client
        self.config = config
        self.data_queue = data_queue
        self.data_bindings = data_bindings

        self.response_topic_mid = None
        self.subscribed = False
        # Set in run(), but initialized here, so it is safe to read
        # before the thread has started.
        self.running = False

        self.mqtt_logger = paho_log_methods(self.logger)

        self.mqtt_client.on_connect = self._on_connect
        if config.log_mqtt:
            self.mqtt_client.on_log = self._on_log
        self.mqtt_client.on_message = self._on_message
        self.mqtt_client.on_subscribe = self._on_subscribe

        # ToDo: Wait for connection?
        self.mqtt_client.connect(config.host, config.port, config.keepalive)

    def run(self):
        self.thread_id = threading.get_native_id()
        threading.current_thread().name = f"MQTTReplicate-{self.thread_id}"
        self.logger.loginf(f"MQTTRequesterLoopThread, {threading.current_thread().name}, is running.")

        for data_binding_name, data_binding in self.data_bindings.items():
            if not data_binding['dbmanager']:
                data_binding['dbmanager'] = weewx.manager.open_manager(data_binding['manager_dict'])
                self.logger.logdbg(f"Opened db {data_binding_name}.")

        self.running = True
        self.mqtt_client.loop_forever()
        self.running = False

        for data_binding_name, data_binding in self.data_bindings.items():
            data_binding['dbmanager'].close()
            self.logger.logdbg(f"Closed db {data_binding_name}.")
        self.logger.loginf("Thread is shut down.")

    def _on_connect(self, _userdata):
        (result, mid) = self.mqtt_client.subscribe(self.config.response_topic, self.config.subscribe_qos)
        self.logger.loginf(f"Subscribing to {self.config.response_topic} "
                           f"has a mid {int(mid)} "
                           f"and result code {int(result)}")
        self.response_topic_mid = mid

        (result, mid) = self.mqtt_client.subscribe(self.config.archive_topic, self.config.subscribe_qos)
        self.logger.loginf(f"Subscribing for archive records on {self.config.archive_topic} "
                           f"has a mid {int(mid)} "
                           f"and result code {int(result)}")

    def _on_log(self, _client, _userdata, level, msg):
        self.mqtt_logger.get(level, self.logger.loginf)(f"({self.config.client_id}) MQTT log: {msg}")

    def _on_message(self, _userdata, msg):
        try:
            record = json.loads(msg.payload.decode('utf-8'))

            # self.logger.logdbg(f"Response has topic: {msg.topic}, "
            #                    f"properties: {msg.properties}"
            #                    f"QOS: {int(msg.qos)}, "
            #                    f"retain: {msg.retain}, "
            #                    f"payload: {record['dateTime']}, "
            #                    f"payload: {msg.payload}, ",
            #                    )

            if not hasattr(msg.properties, 'UserProperty'):
                self.logger.logerr(f'Response with topic {msg.topic}, payload: {msg.payload} skipped; has no "UserProperty"')
                return

            user_property = msg.properties.UserProperty
            data_binding = None
            for keyword_value in user_property:
                if keyword_value[0] == 'data_binding':
                    data_binding = keyword_value[1]
                    break

            if not data_binding:
                self.logger.logerr(f'Response with topic skipped: {msg.topic} payload: {msg.payload}, UserProperty: {user_property} '
                                   'has no "data_binding" UserProperty')
                return

            if data_binding not in self.data_bindings:
                self.logger.logerr(f'Response with topic skipped: {msg.topic} payload: {msg.payload}, UserProperty: {user_property} '
                                   f'has unknow data_binding {data_binding}')
                return

            if self.data_bindings[data_binding]['type'] == 'main':
                # For all records from the 'main' db, create an archive_record
                self.data_queue.put((record['dateTime'], record))
            else:
                self.data_bindings[data_binding]['dbmanager'].addRecord(record)
        except Exception as exception:  # (want to catch all ) pylint: disable=broad-exception-caught
            self.logger.logerr(f"Response Failed with {type(exception)} and reason {exception}.")
            self.logger.logerr(f"{traceback.format_exc()}")

    def _on_subscribe(self, _userdata, mid):
        if mid == self.response_topic_mid:
            self.subscribed = True

if __name__ == '__main__':  # pragma: no cover
    def add_request_parser(parser):
        ''' Add the requester parser, '''
        description = '''
'''
        subparser = parser.add_parser('request',
                                      description=description,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)

        subparser.add_argument("--conf",
                               required=True,
                               help="The WeeWX configuration file. Typically weewx.conf.")
        subparser.add_argument('--timestamp',
                               type=int,
                               help='The timestamp to replicate from.')

        return subparser

    def add_respond_parser(parser):
        ''' Add the requester parser, '''
        description = '''
'''
        subparser = parser.add_parser('respond',
                                      description=description,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)

        subparser.add_argument("--conf",
                               required=True,
                               help="The WeeWX configuration file. Typically weewx.conf.")

    def main():
        """ Run it."""

        arg_parser = argparse.ArgumentParser()
        arg_parser.add_argument('--version',
                                action='version',
                                version=f"mqttreplicate version is {VERSION}")

        subparsers = arg_parser.add_subparsers(dest='command')
        add_request_parser(subparsers)
        add_respond_parser(subparsers)
        options = arg_parser.parse_args()

        _config_path, config_dict = weecfg.read_config(options.conf)
        weewx.debug = 1
        weeutil.logger.setup('weewx', config_dict)

        del config_dict['Engine']
        config_dict['Engine'] = {}
        config_dict['Engine']['Services'] = {}

        if options.command == 'request':
            config_dict['MQTTReplicate']['Requester']['command_line'] = True
            engine = weewx.engine.DummyEngine(config_dict)
            mqtt_requester = MQTTRequester(config_dict, engine)
            try:
                for _packet in mqtt_requester.genLoopPackets():
                    pass
            except (KeyboardInterrupt, Exception):  # pylint: disable=broad-exception-caught
                mqtt_requester.closePort()
            print('done')
        elif options.command == 'respond':
            del config_dict['MQTTReplicate']['Responder']['enable']
            engine = weewx.engine.DummyEngine(config_dict)
            mqtt_responder = MQTTResponder(engine, config_dict)
            try:
                while True:
                    time.sleep(2)
            except KeyboardInterrupt:
                mqtt_responder.shutDown()
        else:
            arg_parser.print_help()

        print("done")

    main()
