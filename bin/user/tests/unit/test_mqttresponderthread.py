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

    def test_run(self):
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
                with mock.patch('user.mqttreplicate.MQTTClient'):
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

                    SUT = user.mqttreplicate.MQTTResponderThread(mock_logger,
                                                                 None,
                                                                 mock_data_queue,
                                                                 None,
                                                                 config,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None)

                    SUT.run()
                    print("done 1")

        print("done 2")

    def test_template(self):
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
                with mock.patch('user.mqttreplicate.MQTTClient'):

                    user.mqttreplicate.MQTTResponderThread(mock_logger,
                                                           None,
                                                           None,
                                                           None,
                                                           config,
                                                           None,
                                                           None,
                                                           None,
                                                           None,
                                                           None)

            print("done 1")

        print("done 2")

if __name__ == '__main__':
    helpers.run_tests()
