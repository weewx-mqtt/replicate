#    Copyright (c) 2026 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

# pylint: disable=wrong-import-order
# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring
# pylint: disable=invalid-name

import unittest
import mock

import helpers

from collections import namedtuple
import random

import user.mqttreplicate

class Properties:
    pass

class TestMQTTResponderLoopThread(unittest.TestCase):
    def test_init(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()
        host = helpers.random_string()
        port = helpers.random_string()
        keepalive = helpers.random_string()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):

                config = user.mqttreplicate.MQTTResponderConfig(log_mqtt=True,
                                                                host=host,
                                                                port=port,
                                                                keepalive=keepalive)
                SUT = user.mqttreplicate.MQTTResponderLoopThread(mock_logger,
                                                                 mock_client,
                                                                 config,
                                                                 None,
                                                                 None)

                self.assertEqual(mock_client.on_connect, SUT._on_connect)
                self.assertEqual(mock_client.on_message, SUT._on_message)
                self.assertEqual(mock_client.on_log, SUT._on_log)
                mock_client.connect.assert_called_once_with(host, port, keepalive)

    def test_mqtt_logger_levels(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()

        with mock.patch('user.mqttreplicate.threading'):

            SUT = user.mqttreplicate.MQTTResponderLoopThread(mock_logger,
                                                             mock_client,
                                                             user.mqttreplicate.MQTTResponderConfig(),
                                                             None,
                                                             None)

            self.assertEqual(SUT.mqtt_logger[user.mqttreplicate.paho.mqtt.client.MQTT_LOG_INFO], mock_logger.loginf)
            self.assertEqual(SUT.mqtt_logger[user.mqttreplicate.paho.mqtt.client.MQTT_LOG_NOTICE], mock_logger.loginf)
            self.assertEqual(SUT.mqtt_logger[user.mqttreplicate.paho.mqtt.client.MQTT_LOG_WARNING], mock_logger.loginf)
            self.assertEqual(SUT.mqtt_logger[user.mqttreplicate.paho.mqtt.client.MQTT_LOG_ERR], mock_logger.logerr)
            self.assertEqual(SUT.mqtt_logger[user.mqttreplicate.paho.mqtt.client.MQTT_LOG_DEBUG], mock_logger.logdbg)

    def test_on_log(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()
        client_id = helpers.random_string()
        msg = helpers.random_string()

        with mock.patch('user.mqttreplicate.threading'):

            SUT = user.mqttreplicate.MQTTResponderLoopThread(mock_logger,
                                                             mock_client,
                                                             user.mqttreplicate.MQTTResponderConfig(client_id=client_id),
                                                             None,
                                                             None)

            # A mapped level dispatches to the mapped logger method.
            SUT._on_log(None, None, user.mqttreplicate.paho.mqtt.client.MQTT_LOG_ERR, msg)
            mock_logger.logerr.assert_called_once_with(f'({client_id}) MQTT log: {msg}')

            # An unmapped level falls back to loginf instead of raising KeyError.
            SUT._on_log(None, None, helpers.random_string(), msg)
            mock_logger.loginf.assert_called_once_with(f'({client_id}) MQTT log: {msg}')

    def test_run(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):

                SUT = user.mqttreplicate.MQTTResponderLoopThread(mock_logger,
                                                                 mock_client,
                                                                 user.mqttreplicate.MQTTResponderConfig(),
                                                                 None,
                                                                 None)

                SUT.run()

                mock_client.loop_forever.assert_called_once_with()

    def test_on_connect(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()
        topic = helpers.random_string()
        qos = helpers.random_string()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):

                SUT = user.mqttreplicate.MQTTResponderLoopThread(
                    mock_logger,
                    mock_client,
                    user.mqttreplicate.MQTTResponderConfig(request_topic=topic, subscribe_qos=qos),
                    None,
                    None)

                mock_client.subscribe.return_value = (random.randint(1, 5), random.randint(6, 10))

                SUT._on_connect(None)

                mock_client.subscribe.assert_called_once_with(topic, qos)

    def test_on_message(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()
        mock_queue = mock.Mock()
        mock_db_manager = mock.Mock()
        instance_name = helpers.random_string()
        data_bindings = {
            instance_name: {
                'dbmanager': mock_db_manager,
                'type': None,
            }
        }

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt') as mock_mqtt:

                SUT = user.mqttreplicate.MQTTResponderLoopThread(mock_logger,
                                                                 mock_client,
                                                                 user.mqttreplicate.MQTTResponderConfig(),
                                                                 mock_queue,
                                                                 data_bindings)

                properties_dict = {
                    'UserProperty': [('data_binding', instance_name)],
                    'ResponseTopic': helpers.random_string(),
                }
                properties = namedtuple('properties', properties_dict.keys())(**properties_dict)

                mock_mqtt.client.Properties.return_value = Properties()

                timestamp = random.randint(1, 9999)
                msg_dict = {
                    'topic': helpers.random_string(),
                    'properties': properties,
                    'qos': random.randint(1, 10),
                    'retain': helpers.random_string(),
                    'payload': str(timestamp).encode('utf-8'),
                }
                msg = namedtuple('msg', msg_dict.keys())(**msg_dict)

                SUT._on_message(None, msg)

                mock_queue.put.assert_called_once()

    def test_on_message_unknown_data_binding(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()
        mock_queue = mock.Mock()
        instance_name = helpers.random_string()
        unknown_data_binding = helpers.random_string()
        data_bindings = {
            instance_name: {
                'dbmanager': mock.Mock(),
                'type': None,
            }
        }

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt') as mock_mqtt:

                SUT = user.mqttreplicate.MQTTResponderLoopThread(mock_logger,
                                                                 mock_client,
                                                                 user.mqttreplicate.MQTTResponderConfig(),
                                                                 mock_queue,
                                                                 data_bindings)

                properties_dict = {
                    'UserProperty': [('data_binding', unknown_data_binding)],
                    'ResponseTopic': helpers.random_string(),
                }
                properties = namedtuple('properties', properties_dict.keys())(**properties_dict)

                mock_mqtt.client.Properties.return_value = Properties()

                msg_dict = {
                    'topic': helpers.random_string(),
                    'properties': properties,
                    'qos': random.randint(1, 10),
                    'retain': helpers.random_string(),
                    'payload': str(random.randint(1, 9999)).encode('utf-8'),
                }
                msg = namedtuple('msg', msg_dict.keys())(**msg_dict)

                SUT._on_message(None, msg)

                # The request must not be queued and the error message must
                # contain the actual unknown data_binding name.
                mock_queue.put.assert_not_called()
                self.assertEqual(mock_logger.logerr.call_count, 1)
                self.assertIn(f'has unknown data_binding {unknown_data_binding}',
                              mock_logger.logerr.call_args[0][0])

if __name__ == '__main__':
    helpers.run_tests()
