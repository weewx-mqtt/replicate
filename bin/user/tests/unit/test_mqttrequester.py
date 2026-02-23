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
import queue
import random

import helpers

import user.mqttreplicate

class PriorityQueueStub:
    def __init__(self):
        # Some variables that are only used for testing
        self.get_call_count = 0

    def get(self, _block, _timeout):
        self.get_call_count += 1
        if self.get_call_count == 2:
            return (helpers.random_string(), helpers.random_string())

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

class TestMQTTRequester(unittest.TestCase):
    def test_init(self):
        mock_engine = mock.Mock()
        random_int = random.randint(1, 9999)
        instance_name = helpers.random_string()
        primary_name = helpers.random_string()
        config_dict = {
            'MQTTReplicate': {
                'Requester': {
                    instance_name: {
                        primary_name: {
                            'type': 'main',
                            'secondary_data_binding': helpers.random_string()
                        }
                    }
                }
            }
        }

        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):
                with mock.patch('user.mqttreplicate.Logger'):
                    with mock.patch('user.mqttreplicate.weewx.manager') as mock_manager:
                        with mock.patch('user.mqttreplicate.MQTTClient') as mock_mqtt_client:
                            with mock.patch('user.mqttreplicate.MQTTRequesterLoopThread') as mock_requester_thread:
                                with mock.patch('user.mqttreplicate.random.randint', return_value=random_int):
                                    last_good_timestamp = helpers.random_string()
                                    manager_dict = helpers.random_string()
                                    mock_db_manager = mock.Mock()
                                    mock_manager.get_manager_dict_from_config.return_value = manager_dict
                                    mock_manager.open_manager.return_value = mock_db_manager
                                    mock_db_manager.lastGoodStamp.return_value = last_good_timestamp

                                    SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)

                                    client_id = f'MQTTReplicateRequest-{random_int}'
                                    mock_mqtt_client.get_client.assert_called_once_with(SUT.logger, client_id, None)
                                    mock_requester_thread.assert_called_once()
                                    SUT.loop_thread.start.assert_called_once_with()
                                    SUT.mqtt_client.publish.assert_called_once()

                                    expected_results = {
                                        f"{instance_name}/{primary_name}": {
                                            'request_topic': f"replicate/request/{instance_name}",
                                            'type': 'main',
                                            'manager_dict': manager_dict,
                                            'last_good_timestamp': last_good_timestamp,
                                            'dbmanager': None,
                                        }
                                    }
                                    self.assertDictEqual(SUT.data_bindings, expected_results)

    def test_gen_startup_records(self):
        mock_engine = mock.Mock()
        config_dict = {
            'MQTTReplicate': {
                'Requester': {
                    helpers.random_string(): {
                        helpers.random_string(): {
                            'type': 'main',
                            'secondary_data_binding': helpers.random_string()
                        }
                    }
                }
            }
        }

        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):
                with mock.patch('user.mqttreplicate.Logger') as mock_logger:
                    with mock.patch('user.mqttreplicate.weewx.manager'):
                        with mock.patch('user.mqttreplicate.MQTTClient'):
                            with mock.patch('user.mqttreplicate.MQTTRequesterLoopThread'):
                                with patch(user.mqttreplicate.queue, 'PriorityQueue', PriorityQueueStub):
                                    with mock.patch.object(user.mqttreplicate.queue.PriorityQueue,
                                                           'get',
                                                           side_effect=PriorityQueueStub.get,
                                                           autospec=True) as mock_get:

                                        SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)

                                        for _record in SUT.genStartupRecords(random.randint(1, 9999)):
                                            pass

                                        self.assertEqual(mock_get.call_count, 4)
                                        self.assertEqual(mock_logger().loginf.call_count, 4)

    def test_gen_archive_records(self):
        mock_engine = mock.Mock()
        config_dict = {
            'MQTTReplicate': {
                'Requester': {
                    helpers.random_string(): {
                        helpers.random_string(): {
                            'type': 'main',
                            'secondary_data_binding': helpers.random_string()
                        }
                    }
                }
            }
        }

        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):
                with mock.patch('user.mqttreplicate.Logger') as mock_logger:
                    with mock.patch('user.mqttreplicate.weewx.manager'):
                        with mock.patch('user.mqttreplicate.MQTTClient'):
                            with mock.patch('user.mqttreplicate.MQTTRequesterLoopThread'):
                                with patch(user.mqttreplicate.queue, 'PriorityQueue', PriorityQueueStub):
                                    with mock.patch.object(user.mqttreplicate.queue.PriorityQueue,
                                                           'get',
                                                           side_effect=PriorityQueueStub.get,
                                                           autospec=True) as mock_get:

                                        SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)

                                        for _record in SUT.genArchiveRecords(random.randint(1, 9999)):
                                            pass

                                        self.assertEqual(mock_get.call_count, 4)
                                        self.assertEqual(mock_logger().loginf.call_count, 4)

if __name__ == '__main__':
    helpers.run_tests()
