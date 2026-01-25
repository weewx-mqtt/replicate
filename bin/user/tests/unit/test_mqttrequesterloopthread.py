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

import user.mqttreplicate

class TestMQTTRequesterLoopThread(unittest.TestCase):
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

    def test_template(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):

                user.mqttreplicate.MQTTRequesterLoopThread(mock_logger,
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

        print("done 1")

        print("done 2")

if __name__ == '__main__':
    helpers.run_tests()
