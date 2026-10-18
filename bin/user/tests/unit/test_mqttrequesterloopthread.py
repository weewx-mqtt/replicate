#    Copyright (c) 2026 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

# pylint: disable=wrong-import-order
# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring
# pylint: disable=invalid-name

import unittest
import mock

import random
from collections import namedtuple

import helpers

import user.mqttreplicate

class TestMQTTRequesterLoopThread(unittest.TestCase):
    # pylint: disable=protected-access
    def test_init(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()
        host = helpers.random_string()
        port = helpers.random_string()
        keepalive = helpers.random_string()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):

                config = user.mqttreplicate.MQTTRequesterConfig(log_mqtt=True,
                                                                host=host,
                                                                port=port,
                                                                keepalive=keepalive)

                SUT = user.mqttreplicate.MQTTRequesterLoopThread(mock_logger,
                                                                 mock_client,
                                                                 config,
                                                                 None,
                                                                 None)

                self.assertEqual(mock_client.on_connect, SUT._on_connect)
                self.assertEqual(mock_client.on_message, SUT._on_message)
                self.assertEqual(mock_client.on_subscribe, SUT._on_subscribe)
                self.assertEqual(mock_client.on_log, SUT._on_log)
                mock_client.connect.assert_called_once_with(host, port, keepalive)

                # 'running' must be readable before the thread has started.
                self.assertFalse(SUT.running)

    def test_mqtt_logger_levels(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt') as mock_mqtt:

                SUT = user.mqttreplicate.MQTTRequesterLoopThread(mock_logger,
                                                                 mock_client,
                                                                 user.mqttreplicate.MQTTRequesterConfig(),
                                                                 None,
                                                                 None)

                self.assertEqual(SUT.mqtt_logger[mock_mqtt.client.MQTT_LOG_INFO], mock_logger.loginf)
                self.assertEqual(SUT.mqtt_logger[mock_mqtt.client.MQTT_LOG_NOTICE], mock_logger.loginf)
                self.assertEqual(SUT.mqtt_logger[mock_mqtt.client.MQTT_LOG_WARNING], mock_logger.logerr)
                self.assertEqual(SUT.mqtt_logger[mock_mqtt.client.MQTT_LOG_ERR], mock_logger.logerr)
                self.assertEqual(SUT.mqtt_logger[mock_mqtt.client.MQTT_LOG_DEBUG], mock_logger.logdbg)

    def test_on_log(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()
        client_id = helpers.random_string()
        msg = helpers.random_string()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt') as mock_mqtt:

                config = user.mqttreplicate.MQTTRequesterConfig(client_id=client_id)

                SUT = user.mqttreplicate.MQTTRequesterLoopThread(mock_logger,
                                                                 mock_client,
                                                                 config,
                                                                 None,
                                                                 None)

                # A mapped level dispatches to the mapped logger method.
                SUT._on_log(None, None, mock_mqtt.client.MQTT_LOG_ERR, msg)
                mock_logger.logerr.assert_called_once_with(f'({client_id}) MQTT log: {msg}')

                # An unmapped level falls back to loginf instead of raising KeyError.
                SUT._on_log(None, None, helpers.random_string(), msg)
                mock_logger.loginf.assert_called_once_with(f'({client_id}) MQTT log: {msg}')

    def test_run(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()
        mock_db_manager = mock.Mock()
        instance_name = helpers.random_string()
        data_bindings = {
            instance_name: {
                'dbmanager': None,
                'manager_dict': helpers.random_string(),
            }
        }
        with mock.patch('user.mqttreplicate.threading') as mock_threading:
            with mock.patch('user.mqttreplicate.paho.mqtt'):
                with mock.patch('user.mqttreplicate.weewx.manager') as mock_manager:
                    mock_manager.open_manager.return_value = mock_db_manager

                    SUT = user.mqttreplicate.MQTTRequesterLoopThread(mock_logger,
                                                                     mock_client,
                                                                     user.mqttreplicate.MQTTRequesterConfig(),
                                                                     None,
                                                                     data_bindings)

                    SUT.run()

                    mock_threading.get_native_id.assert_called_once_with()
                    self.assertTrue(data_bindings[instance_name]['dbmanager'])
                    mock_manager.open_manager.assert_called_once()
                    mock_client.loop_forever.assert_called_once_with()
                    mock_db_manager.close.assert_called_once()

    def test_on_connect(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()
        instance_name = helpers.random_string()
        data_bindings = {
            instance_name: {
                'manager_dict': {},
                'dbmanager': None,
            }
        }

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):
                SUT = user.mqttreplicate.MQTTRequesterLoopThread(mock_logger,
                                                                 mock_client,
                                                                 user.mqttreplicate.MQTTRequesterConfig(),
                                                                 None,
                                                                 data_bindings)

                mock_client.subscribe.return_value = (random.randint(11, 20), random.randint(1, 10))

                SUT._on_connect(None)

                self.assertEqual(mock_client.subscribe.call_count, 2)

    def test_on_subscribe(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()
        instance_name = helpers.random_string()
        data_bindings = {
            instance_name: {
                'dbmanager': None,
            }
        }

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):
                SUT = user.mqttreplicate.MQTTRequesterLoopThread(mock_logger,
                                                                 mock_client,
                                                                 user.mqttreplicate.MQTTRequesterConfig(),
                                                                 None,
                                                                 data_bindings)

                SUT.response_topic_mid = random.randint(1, 10)
                SUT._on_subscribe(None, SUT.response_topic_mid)

                self.assertTrue(SUT.subscribed)

    def test_on_message(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()
        mock_db_manager = mock.Mock()
        instance_name = helpers.random_string()
        data_bindings = {
            instance_name: {
                'dbmanager': mock_db_manager,
                'type': None,
            }
        }

        data = helpers.random_string()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):
                with mock.patch('user.mqttreplicate.json') as mock_json:
                    mock_json.loads.return_value = data

                    SUT = user.mqttreplicate.MQTTRequesterLoopThread(mock_logger,
                                                                     mock_client,
                                                                     user.mqttreplicate.MQTTRequesterConfig(),
                                                                     None,
                                                                     data_bindings)

                    properties_dict = {
                        'UserProperty': [('data_binding', instance_name)]
                    }

                    msg_dict = {
                        'topic': helpers.random_string(),
                        'properties': namedtuple('properties', properties_dict.keys())(**properties_dict),
                        'qos': random.randint(1, 10),
                        'retain': helpers.random_string(),
                        'payload': helpers.random_string().encode('utf-8'),
                    }
                    msg = namedtuple('msg', msg_dict.keys())(**msg_dict)

                    SUT._on_message(None, msg)

                    mock_db_manager.addRecord.assert_called_once_with(data)

    def test_on_message_with_main_database(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()
        mock_db_manager = mock.Mock()
        mock_data_queue = mock.Mock()
        instance_name = helpers.random_string()
        data_bindings = {
            instance_name: {
                'dbmanager': mock_db_manager,
                'type': 'main',
            }
        }

        data = {'dateTime': helpers.random_string()}

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):
                with mock.patch('user.mqttreplicate.json') as mock_json:
                    mock_json.loads.return_value = data

                    SUT = user.mqttreplicate.MQTTRequesterLoopThread(mock_logger,
                                                                     mock_client,
                                                                     user.mqttreplicate.MQTTRequesterConfig(),
                                                                     mock_data_queue,
                                                                     data_bindings)

                    properties_dict = {
                        'UserProperty': [('data_binding', instance_name)]
                    }

                    msg_dict = {
                        'topic': helpers.random_string(),
                        'properties': namedtuple('properties', properties_dict.keys())(**properties_dict),
                        'qos': random.randint(1, 10),
                        'retain': helpers.random_string(),
                        'payload': helpers.random_string().encode('utf-8'),
                    }
                    msg = namedtuple('msg', msg_dict.keys())(**msg_dict)

                    SUT._on_message(None, msg)

                    mock_data_queue.put.assert_called_once_with((data['dateTime'], data))

if __name__ == '__main__':
    helpers.run_tests()
