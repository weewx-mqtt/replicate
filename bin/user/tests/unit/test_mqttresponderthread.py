#    Copyright (c) 2026 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

# pylint: disable=wrong-import-order
# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring
# pylint: disable=invalid-name

import unittest
import mock

import configobj
from collections import namedtuple
import random
import time

import helpers

import user.mqttreplicate

class TestMQTTResponderThread(unittest.TestCase):
    def test_init(self):
        mock_logger = mock.Mock()
        random_int = random.randint(1, 9999)
        instance_name = helpers.random_string()
        data_binding_name = helpers.random_string()

        config_dict = {
            'MQTTReplicate': {
                'Responder': {
                    instance_name: {
                        data_binding_name: {
                        }
                    }
                }
            }
        }

        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.weewx.manager') as mock_manager:
                with mock.patch('user.mqttreplicate.MQTTClient') as mock_client:
                    with mock.patch('user.mqttreplicate.random.randint', return_value=random_int):
                        manager_dict = helpers.random_string()
                        mock_manager.get_manager_dict_from_config.return_value = manager_dict

                        mock_mqtt_client = mock.Mock()
                        mock_client.get_client.return_value = mock_mqtt_client

                        SUT = user.mqttreplicate.MQTTResponderThread(mock_logger,
                                                                     None,
                                                                     None,
                                                                     None,
                                                                     None,
                                                                     None,
                                                                     None,
                                                                     config,
                                                                     True,
                                                                     None,
                                                                     None,
                                                                     None,
                                                                     None)

            client_id = f'MQTTReplicateRespondThread-{random_int}'
            mock_client.get_client.assert_called_once_with(SUT.logger, client_id, None)

            self.assertEqual(mock_mqtt_client.on_connect, SUT._on_connect)
            self.assertEqual(mock_mqtt_client.on_publish, SUT._on_publish)
            self.assertEqual(mock_mqtt_client.on_log, SUT._on_log)

            expected_results = {
                f"{instance_name}/{data_binding_name}": {
                    'delta': None,
                    'type': 'secondary',
                    'manager_dict': manager_dict,
                }
            }
            self.assertDictEqual(SUT.data_bindings, expected_results)

    def test_mqtt_logger_levels(self):
        mock_logger = mock.Mock()
        instance_name = helpers.random_string()
        data_binding_name = helpers.random_string()

        config_dict = {
            'MQTTReplicate': {
                'Responder': {
                    instance_name: {
                        data_binding_name: {
                        }
                    }
                }
            }
        }

        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.weewx.manager') as mock_manager:
                with mock.patch('user.mqttreplicate.MQTTClient') as mock_client:
                    mock_manager.get_manager_dict_from_config.return_value = helpers.random_string()
                    mock_client.get_client.return_value = mock.Mock()

                    SUT = user.mqttreplicate.MQTTResponderThread(mock_logger,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 config,
                                                                 True,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None)

                self.assertEqual(SUT.mqtt_logger[user.mqttreplicate.paho.mqtt.client.MQTT_LOG_INFO],
                                 mock_logger.loginf)
                self.assertEqual(SUT.mqtt_logger[user.mqttreplicate.paho.mqtt.client.MQTT_LOG_NOTICE],
                                 mock_logger.loginf)
                self.assertEqual(SUT.mqtt_logger[user.mqttreplicate.paho.mqtt.client.MQTT_LOG_WARNING],
                                 mock_logger.logerr)
                self.assertEqual(SUT.mqtt_logger[user.mqttreplicate.paho.mqtt.client.MQTT_LOG_ERR],
                                 mock_logger.logerr)
                self.assertEqual(SUT.mqtt_logger[user.mqttreplicate.paho.mqtt.client.MQTT_LOG_DEBUG],
                                 mock_logger.logdbg)

    def test_on_log(self):
        mock_logger = mock.Mock()
        random_int = random.randint(1, 9999)
        instance_name = helpers.random_string()
        data_binding_name = helpers.random_string()
        msg = helpers.random_string()

        config_dict = {
            'MQTTReplicate': {
                'Responder': {
                    instance_name: {
                        data_binding_name: {
                        }
                    }
                }
            }
        }

        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.weewx.manager') as mock_manager:
                with mock.patch('user.mqttreplicate.MQTTClient') as mock_client:
                    with mock.patch('user.mqttreplicate.random.randint', return_value=random_int):
                        mock_manager.get_manager_dict_from_config.return_value = helpers.random_string()
                        mock_client.get_client.return_value = mock.Mock()

                        SUT = user.mqttreplicate.MQTTResponderThread(mock_logger,
                                                                     None,
                                                                     None,
                                                                     None,
                                                                     None,
                                                                     None,
                                                                     None,
                                                                     config,
                                                                     True,
                                                                     None,
                                                                     None,
                                                                     None,
                                                                     None)

                        client_id = f'MQTTReplicateRespondThread-{random_int}'

                        # A mapped level dispatches to the mapped logger method.
                        SUT._on_log(None, None, user.mqttreplicate.paho.mqtt.client.MQTT_LOG_ERR, msg)
                        mock_logger.logerr.assert_called_once_with(f'Client {client_id} MQTT log: {msg}')

                        # An unmapped level falls back to loginf instead of raising KeyError.
                        SUT._on_log(None, None, helpers.random_string(), msg)
                        mock_logger.loginf.assert_called_once_with(f'Client {client_id} MQTT log: {msg}')

    def test_run(self):
        mock_logger = mock.Mock()
        now = time.time()
        host = helpers.random_string()
        port = helpers.random_string()
        keepalive = helpers.random_string()
        publish_qos = helpers.random_string()
        instance_name = helpers.random_string()
        binding_name = helpers.random_string()
        config_dict = {
            'MQTTReplicate': {
                'Responder': {
                    instance_name: {
                        binding_name: {
                        }
                    }
                }
            }
        }

        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.weewx.manager') as mock_manager:
                with mock.patch('user.mqttreplicate.MQTTClient') as mock_client:
                    with mock.patch('user.mqttreplicate.time') as mock_time:
                        mock_time.time.return_value = now
                        mock_db_manager = mock.Mock()
                        mock_manager.open_manager.return_value = mock_db_manager
                        mock_db_manager.genBatchRecords.return_value = [{}]

                        data = {
                            'topic': helpers.random_string(),
                            'data_binding': f'{instance_name}/{binding_name}',
                            'properties': helpers.random_string(),
                            'start_timestamp': helpers.random_string()
                        }
                        mock_data_queue = mock.Mock()
                        mock_data_queue.get.side_effect = [data, None]

                        mock_mqtt_client = mock.Mock()
                        mock_client.get_client.return_value = mock_mqtt_client

                        mock_thread_error = mock.Mock()

                        SUT = user.mqttreplicate.MQTTResponderThread(mock_logger,
                                                                     mock_thread_error,
                                                                     mock_data_queue,
                                                                     random.randint(2, 100),
                                                                     1000,
                                                                     1,
                                                                     None,
                                                                     config,
                                                                     None,
                                                                     host,
                                                                     port,
                                                                     keepalive,
                                                                     publish_qos)

                        msg_dict = {
                            'rc': 0,
                            'mid': random.randint(1, 9999)
                        }
                        msg = namedtuple('msg', msg_dict.keys())(**msg_dict)
                        mock_mqtt_client.publish.return_value = msg

                        SUT.mids = {
                            msg.mid: {}
                        }

                        SUT.run()

                        mock_manager.open_manager.assert_called_once()
                        mock_mqtt_client.connect.assert_called_once_with(host, port, keepalive)
                        mock_mqtt_client.publish.assert_called_once_with(data['topic'],
                                                                         '{}',
                                                                         publish_qos,
                                                                         False,
                                                                         properties=data['properties'])

                        mock_mqtt_client.loop.assert_called_once_with(.1)
                        mock_db_manager.close.assert_called_once()
                        self.assertFalse(SUT.mids)
                        # The happy path must not signal a thread error.
                        mock_thread_error.set.assert_not_called()

    def test_run_publish_wait_timeout(self):
        mock_logger = mock.Mock()
        instance_name = helpers.random_string()
        binding_name = helpers.random_string()
        config_dict = {
            'MQTTReplicate': {
                'Responder': {
                    instance_name: {
                        binding_name: {
                        }
                    }
                }
            }
        }

        config = configobj.ConfigObj(config_dict)

        host = helpers.random_string()
        port = helpers.random_string()
        keepalive = 10
        publish_qos = helpers.random_string()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.weewx.manager') as mock_manager:
                with mock.patch('user.mqttreplicate.MQTTClient') as mock_client:
                    with mock.patch('user.mqttreplicate.time') as mock_time:
                        # time.time() is called for the mid time_stamp, the wait start,
                        # and then the wait check. The last one puts the wait past the keepalive.
                        mock_time.time.side_effect = [100, 200, 200 + keepalive + 1]

                        mock_db_manager = mock.Mock()
                        mock_manager.open_manager.return_value = mock_db_manager
                        mock_db_manager.genBatchRecords.return_value = [{}]

                        mock_mqtt_client = mock.Mock()
                        mock_client.get_client.return_value = mock_mqtt_client

                        mock_thread_error = mock.Mock()

                        data = {
                            'topic': helpers.random_string(),
                            'data_binding': f'{instance_name}/{binding_name}',
                            'properties': helpers.random_string(),
                            'start_timestamp': helpers.random_string()
                        }
                        mock_data_queue = mock.Mock()
                        mock_data_queue.get.side_effect = [data, None]

                        SUT = user.mqttreplicate.MQTTResponderThread(mock_logger,
                                                                     mock_thread_error,
                                                                     mock_data_queue,
                                                                     random.randint(2, 100),
                                                                     1000,
                                                                     1,
                                                                     None,
                                                                     config,
                                                                     None,
                                                                     host,
                                                                     port,
                                                                     keepalive,
                                                                     publish_qos)

                        msg_dict = {
                            'rc': 0,
                            'mid': random.randint(1, 9999)
                        }
                        msg = namedtuple('msg', msg_dict.keys())(**msg_dict)
                        mock_mqtt_client.publish.return_value = msg

                        # The publish callback never fires, so the mid stays in flight.
                        SUT.run()

                        # The wait must give up after the keepalive, log, and disconnect.
                        self.assertEqual(mock_logger.logerr.call_count, 1)
                        self.assertIn(f'Timed out after {keepalive} seconds',
                                      mock_logger.logerr.call_args[0][0])
                        mock_mqtt_client.disconnect.assert_called_once_with()
                        # A publish timeout is logged, but must not take the responder down.
                        mock_thread_error.set.assert_not_called()
                        mock_db_manager.close.assert_called_once()

    def test_run_has_exception(self):
        mock_logger = mock.Mock()
        instance_name = helpers.random_string()
        binding_name = helpers.random_string()
        config_dict = {
            'MQTTReplicate': {
                'Responder': {
                    instance_name: {
                        binding_name: {
                        }
                    }
                }
            }
        }

        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.weewx.manager') as mock_manager:
                with mock.patch('user.mqttreplicate.MQTTClient') as mock_client:
                    mock_db_manager = mock.Mock()
                    mock_manager.open_manager.return_value = mock_db_manager
                    mock_db_manager.genBatchRecords.return_value = [{}]

                    mock_mqtt_client = mock.Mock()
                    mock_client.get_client.return_value = mock_mqtt_client

                    mock_thread_error = mock.Mock()

                    data = {
                        'topic': helpers.random_string(),
                        'data_binding': f'{instance_name}/{binding_name}',
                        'properties': helpers.random_string(),
                        'start_timestamp': helpers.random_string()
                    }
                    mock_data_queue = mock.Mock()

                    SUT = user.mqttreplicate.MQTTResponderThread(mock_logger,
                                                                 mock_thread_error,
                                                                 mock_data_queue,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 config,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None)

                    data = {
                        'topic': helpers.random_string(),
                        'data_binding': f'{instance_name}/{binding_name}',
                        'properties': helpers.random_string(),
                        'start_timestamp': helpers.random_string()
                    }
                    mock_data_queue.get.side_effect = [data]
                    mock_mqtt_client.connect = mock.Mock(side_effect=Exception())
                    SUT.run()

                    mock_manager.open_manager.assert_called_once()
                    self.assertEqual(mock_logger.logerr.call_count, 2)
                    # The failure must be signaled through the shared thread_error event.
                    mock_thread_error.set.assert_called_once_with()
                    mock_db_manager.close.assert_called_once()

    def test_on_publish_all_responses_published(self):
        mock_logger = mock.Mock()
        config_dict = {
            'MQTTReplicate': {
                'Responder': {
                    helpers.random_string(): {
                        helpers.random_string(): {
                        }
                    }
                }
            }
        }

        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.weewx.manager'):
                with mock.patch('user.mqttreplicate.MQTTClient') as mock_client:

                    mock_mqtt_client = mock.Mock()
                    mock_client.get_client.return_value = mock_mqtt_client

                    SUT = user.mqttreplicate.MQTTResponderThread(mock_logger,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 config,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None)

            mid = random.randint(1, 99)
            SUT.mids[mid] = {
                'time_stamp': helpers.random_string(),
                'qos': helpers.random_string()
            }

            SUT._on_publish(None, mid)

            self.assertDictEqual(SUT.mids, {})

    def test_on_publish_still_publishing(self):
        mock_logger = mock.Mock()
        config_dict = {
            'MQTTReplicate': {
                'Responder': {
                    helpers.random_string(): {
                        helpers.random_string(): {
                        }
                    }
                }
            }
        }

        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.weewx.manager'):
                with mock.patch('user.mqttreplicate.MQTTClient') as mock_client:

                    mock_mqtt_client = mock.Mock()
                    mock_client.get_client.return_value = mock_mqtt_client

                    SUT = user.mqttreplicate.MQTTResponderThread(mock_logger,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 config,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None)

            mid = random.randint(1, 99)
            SUT.mids[mid] = {
                'time_stamp': helpers.random_string(),
                'qos': helpers.random_string()
            }
            mid2 = helpers.random_string()
            SUT.mids[mid2] = {}

            SUT._on_publish(None, mid)

            self.assertDictEqual(SUT.mids, {mid2: {}})

if __name__ == '__main__':
    helpers.run_tests()
