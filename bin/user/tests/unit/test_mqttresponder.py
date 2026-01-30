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
import random

import helpers

import user.mqttreplicate

class TestMQTTResponder(unittest.TestCase):
    def test_init(self):
        mock_engine = mock.Mock()
        random_int = random.randint(1, 9999)
        instance_name = helpers.random_string()
        primary_name = helpers.random_string()

        config_dict = {
            'MQTTReplicate': {
                'Responder': {
                    instance_name: {
                        primary_name: {
                        }
                    }
                }
            }
        }

        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.Logger') as mock_logger:
                with mock.patch('user.mqttreplicate.weewx.manager') as mock_manager:
                    with mock.patch('user.mqttreplicate.MQTTResponderThread') as mock_responder_thread:
                        with mock.patch('user.mqttreplicate.MQTTClient') as mock_mqtt_client:
                            with mock.patch('user.mqttreplicate.MQTTResponderLoopThread') as mock_responder_loop_thread:
                                with mock.patch('user.mqttreplicate.queue.Queue') as mock_queue:
                                    with mock.patch('user.mqttreplicate.random.randint', return_value=random_int):
                                        mock_db_manager = mock.Mock()
                                        mock_manager.open_manager.return_value = mock_db_manager

                                        mock_client = mock.Mock()
                                        mock_mqtt_client.get_client.return_value = mock_client
                                        SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)

                                        client_id = f'MQTTReplicateRespond-{random_int}'

                                        data_bindings = {
                                            f"{instance_name}/{primary_name}": {
                                                'delta': 60,
                                                'type': 'secondary',
                                                'dbmanager': mock_db_manager,
                                            }
                                        }

                                        mock_mqtt_client.get_client.assert_called_once_with(mock_logger(), client_id, None)
                                        mock_responder_thread.assert_called_once_with(mock_logger(),
                                                                                      False,
                                                                                      mock_queue(),
                                                                                      60,
                                                                                      config,
                                                                                      False,
                                                                                      'localhost',
                                                                                      1883,
                                                                                      60,
                                                                                      1)
                                        mock_responder_thread().start.assert_called_once_with()

                                        mock_responder_loop_thread.assert_called_once_with(mock_logger(),
                                                                                           mock_client,
                                                                                           client_id,
                                                                                           False,
                                                                                           mock_queue(),
                                                                                           data_bindings,
                                                                                           f'replicate/request/{instance_name}',
                                                                                           1,
                                                                                           'localhost',
                                                                                           1883,
                                                                                           60)
                                        mock_responder_loop_thread().start.assert_called_once_with()

                                        self.assertDictEqual(SUT.data_bindings, data_bindings)

    def test_shutDown(self):
        mock_engine = mock.Mock()
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
            with mock.patch('user.mqttreplicate.Logger'):
                with mock.patch('user.mqttreplicate.weewx.manager') as mock_manager:
                    with mock.patch('user.mqttreplicate.MQTTResponderThread'):
                        with mock.patch('user.mqttreplicate.MQTTClient') as mock_mqtt_client:
                            with mock.patch('user.mqttreplicate.MQTTResponderLoopThread'):
                                with mock.patch('user.mqttreplicate.queue.Queue') as mock_queue:

                                    mock_db_manager = mock.Mock()
                                    mock_manager.open_manager.return_value = mock_db_manager

                                    mock_client = mock.Mock()
                                    mock_mqtt_client.get_client.return_value = mock_client

                                    SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)

                                    SUT.shutDown()

                                    mock_db_manager.close.assert_called_once_with()
                                    mock_client.disconnect.assert_called_once_with()
                                    mock_queue().put.assert_called_once_with(None)

    def test_template(self):
        mock_engine = mock.Mock()
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
            with mock.patch('user.mqttreplicate.Logger'):
                with mock.patch('user.mqttreplicate.weewx.manager'):
                    with mock.patch('user.mqttreplicate.MQTTResponderThread'):
                        with mock.patch('user.mqttreplicate.MQTTClient'):
                            with mock.patch('user.mqttreplicate.MQTTResponderLoopThread'):

                                SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)
                                print(SUT.client_id)

                                print("done 1")

        print("done 2")

if __name__ == '__main__':
    helpers.run_tests()
