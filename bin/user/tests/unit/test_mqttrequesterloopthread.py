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

                SUT = user.mqttreplicate.MQTTRequesterLoopThread(mock_logger,
                                                                 mock_client,
                                                                 None,
                                                                 True,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 host,
                                                                 port,
                                                                 keepalive)

                self.assertEqual(mock_client.on_connect, SUT._on_connect)
                self.assertEqual(mock_client.on_disconnect, SUT._on_disconnect)
                self.assertEqual(mock_client.on_message, SUT._on_message)
                self.assertEqual(mock_client.on_subscribe, SUT._on_subscribe)
                self.assertEqual(mock_client.on_log, SUT._on_log)
                mock_client.connect.assert_called_once_with(host, port, keepalive)

    def test_run(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()

        with mock.patch('user.mqttreplicate.threading') as mock_threading:
            with mock.patch('user.mqttreplicate.paho.mqtt'):

                SUT = user.mqttreplicate.MQTTRequesterLoopThread(mock_logger,
                                                                 mock_client,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None)

                SUT.run()

                mock_threading.get_native_id.assert_called_once_with()
                mock_client.loop_forever.assert_called_once_with()

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
                with mock.patch('user.mqttreplicate.weewx.manager') as mock_manager:
                    SUT = user.mqttreplicate.MQTTRequesterLoopThread(mock_logger,
                                                                     mock_client,
                                                                     None,
                                                                     None,
                                                                     None,
                                                                     data_bindings,
                                                                     None,
                                                                     None,
                                                                     None,
                                                                     None,
                                                                     None,
                                                                     None)

                    mock_client.subscribe.return_value = (random.randint(11, 20), random.randint(1, 10))

                    SUT._on_connect(None)

                    self.assertEqual(mock_client.subscribe.call_count, 2)
                    self.assertTrue(data_bindings[instance_name]['dbmanager'])
                    mock_manager.open_manager.assert_called_once()

    def test_on_disconnect(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()
        instance_name = helpers.random_string()
        mock_db_manager = mock.Mock()
        data_bindings = {
            instance_name: {
                'dbmanager': mock_db_manager,
            }
        }

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):
                with mock.patch('user.mqttreplicate.weewx.manager'):
                    SUT = user.mqttreplicate.MQTTRequesterLoopThread(mock_logger,
                                                                     mock_client,
                                                                     None,
                                                                     None,
                                                                     None,
                                                                     data_bindings,
                                                                     None,
                                                                     None,
                                                                     None,
                                                                     None,
                                                                     None,
                                                                     None)

                    SUT._on_disconnect(None, 0)

                    mock_db_manager.close.assert_called_once()

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
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 data_bindings,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None)

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

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):
                with mock.patch('user.mqttreplicate.json'):
                    SUT = user.mqttreplicate.MQTTRequesterLoopThread(mock_logger,
                                                                    mock_client,
                                                                    None,
                                                                    None,
                                                                    None,
                                                                    data_bindings,
                                                                    None,
                                                                    None,
                                                                    None,
                                                                    None,
                                                                    None,
                                                                    None)

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

                    print("done")

if __name__ == '__main__':
    helpers.run_tests()
