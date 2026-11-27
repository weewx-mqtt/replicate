#    Copyright (c) 2026 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

# pylint: disable=wrong-import-order
# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring
# pylint: disable=invalid-name

import unittest
import mock

from collections import namedtuple
import random

import paho.mqtt.client as paho_mqtt

import helpers

import user.mqttreplicate
from user.tests.unit.replicate_helpers import (create_responder_service_config,
                                               patched_responder_service)

class Event:
    def __init__(self, record):
        self.record = record

class Properties:
    pass

def create_request_message(data_binding, timestamp, *, user_property=True):
    """ Build an MQTT message carrying a replication request. """
    properties_dict = {'ResponseTopic': helpers.random_string()}
    if user_property:
        properties_dict['UserProperty'] = [('data_binding', data_binding)]
    properties = namedtuple('properties', properties_dict.keys())(**properties_dict)

    msg_dict = {
        'topic': helpers.random_string(),
        'properties': properties,
        'qos': random.randint(1, 10),
        'retain': helpers.random_string(),
        'payload': str(timestamp).encode('utf-8'),
    }
    return namedtuple('msg', msg_dict.keys())(**msg_dict)

class TestMQTTResponder(unittest.TestCase):
    def test_init(self):
        mock_engine = mock.Mock()
        random_int = random.randint(1, 9999)
        instance_name = helpers.random_string()
        primary_name = helpers.random_string()

        config, instance_name, primary_name = create_responder_service_config(section_overrides={'log_mqtt': True})

        with patched_responder_service(queue=True, random_int=random_int) as mocks:
            SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)

            client_id = f'MQTTReplicateRespond-{random_int}'

            data_bindings = {
                f"{instance_name}/{primary_name}": {
                    'delta': 60,
                    'type': 'main',
                    'dbmanager': mocks.db_manager,
                }
            }

            mocks.mqtt_client.assert_called_once_with(mocks.logger(), client_id, None)
            # The thread_error event must be shared with the threads,
            # so a thread failure is seen by the service.
            self.assertEqual(SUT.thread_error, mocks.threading.Event())
            mocks.responder_thread.assert_called_once_with(mocks.logger(),
                                                           SUT.thread_error,
                                                           mocks.queue(),
                                                           SUT.config,
                                                           config,
                                                           mocks.client)
            # The parsed options reach the thread through the config object.
            self.assertEqual(SUT.config.instance_name, instance_name)
            self.assertEqual(SUT.config.log_msg_count, 1000)
            self.assertEqual(SUT.config.batch_size, 200)
            self.assertEqual(SUT.config.batch_sleep, 0.1)
            self.assertEqual(SUT.config.wait_for_inflight, 2)
            self.assertEqual(SUT.config.delta, 60)
            self.assertTrue(SUT.config.log_mqtt)
            self.assertEqual(SUT.config.host, 'localhost')
            self.assertEqual(SUT.config.port, 1883)
            self.assertEqual(SUT.config.keepalive, 60)
            self.assertEqual(SUT.config.publish_qos, 1)
            self.assertEqual(SUT.config.wait_for_thread_shutdown, 20)
            mocks.responder_thread().start.assert_called_once_with()

            # paho's network loop owns the connection and the reconnect.
            mocks.client.connect_async.assert_called_once_with('localhost', 1883, 60)
            mocks.client.loop_start.assert_called_once_with()
            self.assertEqual(SUT.config.client_id, client_id)
            self.assertEqual(SUT.config.request_topic, f'replicate/request/{instance_name}')

            self.assertDictEqual(SUT.data_bindings, data_bindings)

    def test_init_no_instance(self):
        mock_engine = mock.Mock()
        config, _, _ = create_responder_service_config(include_instance=False)

        with patched_responder_service():

            # A Responder section with no instance must raise,
            # not blow up with an IndexError.
            with self.assertRaises(AttributeError):
                user.mqttreplicate.MQTTResponder(mock_engine, config)

    def test_shutDown_disabled(self):
        mock_engine = mock.Mock()
        config, _, _ = create_responder_service_config(
            include_instance=False,
            section_overrides={'enable': False, 'wait_for_thread_shutdown': 3})

        with patched_responder_service(log_direct=True) as mocks:

            SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)
            self.assertFalse(SUT.enabled)

            # A disabled responder must shut down without error,
            # even though it was never fully initialized.
            SUT.shutDown()

            mocks.logger().info.assert_any_call(None, 'Responder not enabled, exiting.')
            # A component that never ran does not announce that it is shutting down.
            self.assertNotIn(mock.call(None, 'Shutting down.'),
                             mocks.logger().info.call_args_list)
            # The logger thread is still stopped, with the configured wait.
            mocks.logger().shutdown.assert_called_once_with(3)
            mocks.log_direct.assert_not_called()

    def test_shutDown(self):
        mock_engine = mock.Mock()
        config, _, _ = create_responder_service_config(section_overrides={'wait_for_thread_shutdown': 3})

        with patched_responder_service(queue=True, log_direct=True) as mocks:

            SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)
            for thread in SUT.threads:
                thread.is_alive.return_value = False

            SUT.shutDown()

            mocks.db_manager.close.assert_called_once_with()
            mocks.queue().put.assert_called_once_with(None)
            # The pool threads stop before the client goes away.
            for thread in SUT.threads:
                thread.join.assert_called_once_with(3)
            mocks.client.disconnect.assert_called_once_with()
            mocks.client.loop_stop.assert_called_once_with()
            mocks.logger.return_value.info.assert_any_call(None, 'Shutting down.')
            mocks.logger.return_value.info.assert_any_call(None, 'Shutting down the responder threads.')
            mocks.logger.return_value.info.assert_any_call(None, 'Shutting down the loop.')
            mocks.logger.return_value.info.assert_any_call(None, 'Shutting down the logger thread.')
            mocks.logger.return_value.shutdown.assert_called_once_with(3)
            # The completion is logged directly, because the logger thread has stopped by then.
            mocks.log_direct.assert_called_once_with('MQTTResponder', 'INFO',
                                                     "MQTTResponder is shut down.")

    def test_new_archive_record(self):
        mock_engine = mock.Mock()
        config, _, _ = create_responder_service_config(secondary_bindings=(helpers.random_string() + '-secondary',))

        with patched_responder_service(paho=True, use_json=True) as mocks:

            SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)

            event = Event({'dateTime': random.randint(9999, 99999)})

            SUT.thread_error.is_set.return_value = False
            SUT.new_archive_record(event)

            mocks.db_manager.getRecord.assert_called_once_with(event.record['dateTime'], max_delta=60)
            self.assertEqual(mocks.client.publish.call_count, 2)

    def test_new_archive_record_thread_error(self):
        mock_engine = mock.Mock()
        config, _, _ = create_responder_service_config()

        with patched_responder_service(paho=True, use_json=True):

            SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)

            event = Event({'dateTime': random.randint(9999, 99999)})

            # A set thread_error event must raise a ThreadError.
            SUT.thread_error.is_set.return_value = True
            with self.assertRaises(user.mqttreplicate.ThreadError):
                SUT.new_archive_record(event)

    def test_on_connect(self):
        mock_engine = mock.Mock()
        config, _, _ = create_responder_service_config()

        with patched_responder_service() as mocks:
            SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)
            mocks.client.subscribe.return_value = (0, random.randint(1, 10))

            SUT._on_connect(None)

            mocks.client.subscribe.assert_called_once_with(SUT.config.request_topic,
                                                           SUT.config.subscribe_qos)

    def test_on_connect_subscribe_failure_is_logged(self):
        mock_engine = mock.Mock()
        config, _, _ = create_responder_service_config()

        with patched_responder_service() as mocks:
            SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)
            mocks.client.subscribe.side_effect = Exception()

            # The network thread must not die on a callback exception.
            SUT._on_connect(None)

            self.assertIn('Subscribing failed', mocks.logger.return_value.error.call_args[0][1])

    def test_mqtt_logger_levels(self):
        mock_engine = mock.Mock()
        config, _, _ = create_responder_service_config()

        with patched_responder_service() as mocks:
            SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)

            self.assertEqual(SUT.mqtt_logger[paho_mqtt.MQTT_LOG_INFO], mocks.logger.return_value.info)
            self.assertEqual(SUT.mqtt_logger[paho_mqtt.MQTT_LOG_NOTICE], mocks.logger.return_value.info)
            self.assertEqual(SUT.mqtt_logger[paho_mqtt.MQTT_LOG_WARNING], mocks.logger.return_value.info)
            self.assertEqual(SUT.mqtt_logger[paho_mqtt.MQTT_LOG_ERR], mocks.logger.return_value.error)
            self.assertEqual(SUT.mqtt_logger[paho_mqtt.MQTT_LOG_DEBUG], mocks.logger.return_value.debug)

    def test_on_log(self):
        mock_engine = mock.Mock()
        config, _, _ = create_responder_service_config()
        msg = helpers.random_string()

        with patched_responder_service() as mocks:
            SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)
            mocks.logger.return_value.info.reset_mock()
            mocks.logger.return_value.error.reset_mock()

            # A mapped level dispatches to the mapped logger method.
            SUT._on_log(None, None, paho_mqtt.MQTT_LOG_ERR, msg)
            mocks.logger.return_value.error.assert_called_once_with(
                None, f'({SUT.config.client_id}) MQTT log: {msg}')

            # An unmapped level falls back to info instead of raising KeyError.
            SUT._on_log(None, None, helpers.random_string(), msg)
            mocks.logger.return_value.info.assert_called_once_with(
                None, f'({SUT.config.client_id}) MQTT log: {msg}')

    def test_on_message(self):
        mock_engine = mock.Mock()
        config, _, _ = create_responder_service_config()

        with patched_responder_service(queue=True, paho=True) as mocks:
            SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)
            mocks.paho.client.Properties.return_value = Properties()

            data_binding = next(iter(SUT.data_bindings))
            timestamp = random.randint(1, 9999)
            SUT._on_message(None, create_request_message(data_binding, timestamp))

            data = mocks.queue().put.call_args[0][0]
            self.assertEqual(data['start_timestamp'], timestamp)
            self.assertEqual(data['data_binding'], data_binding)

    def test_on_message_no_user_property(self):
        mock_engine = mock.Mock()
        config, instance_name, _ = create_responder_service_config()

        with patched_responder_service(queue=True, paho=True) as mocks:
            SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)
            mocks.paho.client.Properties.return_value = Properties()

            SUT._on_message(None, create_request_message(instance_name, 1, user_property=False))

            mocks.queue().put.assert_not_called()
            self.assertIn('has no UserProperty', mocks.logger.return_value.error.call_args[0][1])

    def test_on_message_unknown_data_binding(self):
        mock_engine = mock.Mock()
        config, _, _ = create_responder_service_config()
        unknown_data_binding = helpers.random_string()

        with patched_responder_service(queue=True, paho=True) as mocks:
            SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)
            mocks.paho.client.Properties.return_value = Properties()

            SUT._on_message(None, create_request_message(unknown_data_binding, 1))

            # The request must not be queued and the error message must
            # contain the actual unknown data_binding name.
            mocks.queue().put.assert_not_called()
            self.assertIn(f"has unknown 'data_binding' {unknown_data_binding}.",
                          mocks.logger.return_value.error.call_args[0][1])

if __name__ == '__main__':
    helpers.run_tests()
