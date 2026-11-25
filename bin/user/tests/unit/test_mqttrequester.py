#    Copyright (c) 2026 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

# pylint: disable=wrong-import-order
# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring
# pylint: disable=invalid-name

import json
import unittest
import mock

from collections import namedtuple
import queue
import random

import paho.mqtt.client as paho_mqtt

import helpers

import user.mqttreplicate
from user.tests.unit.replicate_helpers import create_requester_config, patched_requester

class PriorityQueueStub:
    def __init__(self):
        # Some variables that are only used for testing
        self.get_call_count = 0

    def get(self, _block, _timeout):
        self.get_call_count += 1
        if self.get_call_count == 2:
            return ({'dateTime': random.randint(0, 9999)}, {'dateTime': random.randint(10000, 19999)})

        raise queue.Empty

import contextlib
@contextlib.contextmanager
def patch(module, old, new):
    original = getattr(module, old)
    setattr(module, old, new)
    try:
        yield
    finally:
        setattr(module, old, original)

def create_message(data_binding, record):
    """ Build an MQTT message carrying a replication response. """
    properties_dict = {
        'UserProperty': [('data_binding', data_binding)],
    }
    properties = namedtuple('properties', properties_dict.keys())(**properties_dict)

    msg_dict = {
        'topic': helpers.random_string(),
        'properties': properties,
        'qos': random.randint(1, 10),
        'retain': helpers.random_string(),
        'payload': json.dumps(record).encode('utf-8'),
    }
    return namedtuple('msg', msg_dict.keys())(**msg_dict)

class TestMQTTRequester(unittest.TestCase):
    def test_init(self):
        mock_engine = mock.Mock()
        random_int = random.randint(1, 9999)
        config, instance_name, primary_name = create_requester_config()

        with patched_requester(random_int=random_int) as mocks:
            last_good_timestamp = helpers.random_string()
            manager_dict = helpers.random_string()
            mock_db_manager = mock.Mock()
            mocks.manager.get_manager_dict_from_config.return_value = manager_dict
            mocks.manager.open_manager.return_value = mock_db_manager
            mock_db_manager.lastGoodStamp.return_value = last_good_timestamp

            SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)

            client_id = f'MQTTReplicateRequest-{random_int}'
            self.assertEqual(SUT.config.wait_for_thread_shutdown, 20)
            mocks.mqtt_client.assert_called_once_with(SUT.logger, client_id, None)
            # paho's network loop owns the connection and the reconnect.
            SUT.mqtt_client.connect_async.assert_called_once_with('localhost', 1883, 60)
            SUT.mqtt_client.loop_start.assert_called_once_with()
            SUT.subscribed.wait.assert_called_once_with(user.mqttreplicate.CONNECT_TIMEOUT)
            SUT.mqtt_client.publish.assert_called_once()

            # The default response_topic is RESPONSE_TOPIC.
            self.assertEqual(SUT.response_topic, f'replicate/response/{client_id}')

            expected_results = {
                f"{instance_name}/{primary_name}": {
                    'request_topic': f"replicate/request/{instance_name}",
                    'type': 'main',
                    'manager_dict': manager_dict,
                    'last_good_timestamp': last_good_timestamp,
                    'dbmanager': mock_db_manager,
                }
            }
            self.assertDictEqual(SUT.data_bindings, expected_results)

    def test_init_log_mqtt_string(self):
        mock_engine = mock.Mock()
        config, _, _ = create_requester_config(requester_overrides={'log_mqtt': 'False'})

        with patched_requester() as mocks:
            mocks.manager.open_manager.return_value = mock.Mock()

            SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)

            self.assertFalse(SUT.config.log_mqtt)

    def test_close_port(self):
        mock_engine = mock.Mock()
        config, _, _ = create_requester_config(requester_overrides={'wait_for_thread_shutdown': 3})

        with patched_requester(log_direct=True) as mocks:
            mock_db_manager = mock.Mock()
            mocks.manager.open_manager.return_value = mock_db_manager

            SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)
            SUT.closePort()

            SUT.mqtt_client.disconnect.assert_called_once_with()
            SUT.mqtt_client.loop_stop.assert_called_once_with()
            mock_db_manager.close.assert_called_once_with()
            mocks.logger.return_value.info.assert_any_call(None, "Shutting down.")
            mocks.logger.return_value.info.assert_any_call(None, "Shutting down the loop.")
            mocks.logger.return_value.info.assert_any_call(None, "Shutting down the logger thread.")
            mocks.logger.return_value.shutdown.assert_called_once_with(3)
            # The completion is logged directly, because the logger thread has stopped by then.
            mocks.log_direct.assert_called_once_with('MQTTRequester', 'INFO',
                                                     "MQTTRequester is shut down.")

    def test_gen_startup_records(self):
        mock_engine = mock.Mock()
        config, _, _ = create_requester_config()

        with patched_requester() as mocks:
            with patch(user.mqttreplicate.queue, 'PriorityQueue', PriorityQueueStub):
                with mock.patch.object(user.mqttreplicate.queue.PriorityQueue,
                                       'get',
                                       side_effect=PriorityQueueStub.get,
                                       autospec=True) as mock_get:

                    SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)

                    for _record in SUT.genStartupRecords(random.randint(1, 9999)):
                        pass

                    self.assertEqual(mock_get.call_count, 4)
                    self.assertEqual(mocks.logger().info.call_count, 2)

    def test_gen_archive_records(self):
        mock_engine = mock.Mock()
        config, _, _ = create_requester_config()

        with patched_requester() as mocks:
            with patch(user.mqttreplicate.queue, 'PriorityQueue', PriorityQueueStub):
                with mock.patch.object(user.mqttreplicate.queue.PriorityQueue,
                                       'get',
                                       side_effect=PriorityQueueStub.get,
                                       autospec=True) as mock_get:

                    SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)

                    for _record in SUT.genArchiveRecords(random.randint(1, 9999)):
                        pass

                    self.assertEqual(mock_get.call_count, 4)
                    self.assertEqual(mocks.logger().info.call_count, 1)

    def test_on_connect(self):
        mock_engine = mock.Mock()
        config, _, _ = create_requester_config()

        with patched_requester():
            SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)
            SUT.mqtt_client.subscribe.reset_mock()
            SUT.mqtt_client.subscribe.side_effect = [(0, 11), (0, 22)]

            SUT._on_connect(None)

            self.assertEqual(SUT.mqtt_client.subscribe.call_count, 2)
            self.assertEqual(SUT.response_topic_mid, 11)

    def test_on_connect_subscribe_failure_is_logged(self):
        mock_engine = mock.Mock()
        config, _, _ = create_requester_config()

        with patched_requester() as mocks:
            SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)
            SUT.mqtt_client.subscribe.side_effect = Exception()

            # The network thread must not die on a callback exception.
            SUT._on_connect(None)

            self.assertIn('Subscribing failed', mocks.logger.return_value.error.call_args[0][1])

    def test_on_subscribe(self):
        mock_engine = mock.Mock()
        config, _, _ = create_requester_config()

        with patched_requester():
            SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)
            SUT.response_topic_mid = random.randint(1, 10)

            SUT._on_subscribe(None, SUT.response_topic_mid)
            SUT.subscribed.set.assert_called_once_with()

            # A different mid is not the subscription the requester waits for.
            SUT._on_subscribe(None, SUT.response_topic_mid + 1)
            SUT.subscribed.set.assert_called_once_with()

    def test_mqtt_logger_levels(self):
        mock_engine = mock.Mock()
        config, _, _ = create_requester_config()

        with patched_requester() as mocks:
            SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)

            self.assertEqual(SUT.mqtt_logger[paho_mqtt.MQTT_LOG_INFO], mocks.logger.return_value.info)
            self.assertEqual(SUT.mqtt_logger[paho_mqtt.MQTT_LOG_NOTICE], mocks.logger.return_value.info)
            self.assertEqual(SUT.mqtt_logger[paho_mqtt.MQTT_LOG_WARNING], mocks.logger.return_value.info)
            self.assertEqual(SUT.mqtt_logger[paho_mqtt.MQTT_LOG_ERR], mocks.logger.return_value.error)
            self.assertEqual(SUT.mqtt_logger[paho_mqtt.MQTT_LOG_DEBUG], mocks.logger.return_value.debug)

    def test_on_log(self):
        mock_engine = mock.Mock()
        config, _, _ = create_requester_config()
        msg = helpers.random_string()

        with patched_requester() as mocks:
            SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)
            mocks.logger.return_value.info.reset_mock()
            mocks.logger.return_value.error.reset_mock()

            # A mapped level dispatches to the mapped logger method.
            SUT._on_log(None, None, paho_mqtt.MQTT_LOG_ERR, msg)
            mocks.logger.return_value.error.assert_called_once_with(None, f'({SUT.client_id}) MQTT log: {msg}')

            # An unmapped level falls back to info instead of raising KeyError.
            SUT._on_log(None, None, helpers.random_string(), msg)
            mocks.logger.return_value.info.assert_called_once_with(None, f'({SUT.client_id}) MQTT log: {msg}')

    def test_on_message(self):
        mock_engine = mock.Mock()
        config, instance_name, _ = create_requester_config()
        mock_db_manager = mock.Mock()
        data = {'dateTime': random.randint(1, 9999)}

        with patched_requester():
            SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)
            SUT.data_bindings = {instance_name: {'dbmanager': mock_db_manager, 'type': None}}

            SUT._on_message(None, create_message(instance_name, data))

            mock_db_manager.addRecord.assert_called_once_with(data)

    def test_on_message_with_main_database(self):
        mock_engine = mock.Mock()
        config, instance_name, _ = create_requester_config()
        data = {'dateTime': random.randint(1, 9999)}

        with patched_requester():
            SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)
            SUT.data_bindings = {instance_name: {'dbmanager': mock.Mock(), 'type': 'main'}}
            SUT.data_queue = mock.Mock()

            SUT._on_message(None, create_message(instance_name, data))

            SUT.data_queue.put.assert_called_once_with((data['dateTime'], data))

    def test_on_message_unknown_data_binding(self):
        mock_engine = mock.Mock()
        config, instance_name, _ = create_requester_config()

        with patched_requester() as mocks:
            SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)
            SUT.data_bindings = {instance_name: {'dbmanager': mock.Mock(), 'type': None}}
            SUT.data_queue = mock.Mock()

            SUT._on_message(None, create_message(helpers.random_string(), {'dateTime': 1}))

            SUT.data_queue.put.assert_not_called()
            self.assertIn('has unknown', mocks.logger.return_value.error.call_args[0][1])

if __name__ == '__main__':
    helpers.run_tests()
