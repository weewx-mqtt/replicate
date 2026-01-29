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

import random

import user.mqttreplicate

class TestMQTTResponderLoopThread(unittest.TestCase):
    def test_init(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()
        host = helpers.random_string()
        port = helpers.random_string()
        keepalive = helpers.random_string()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):

                SUT = user.mqttreplicate.MQTTResponderLoopThread(mock_logger,
                                                                 mock_client,
                                                                 None,
                                                                 True,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 host,
                                                                 port,
                                                                 keepalive)

                self.assertEqual(mock_client.on_connect, SUT._on_connect)
                self.assertEqual(mock_client.on_message, SUT._on_message)
                self.assertEqual(mock_client.on_log, SUT._on_log)
                mock_client.connect.assert_called_once_with(host, port, keepalive)

    def test_run(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):

                SUT = user.mqttreplicate.MQTTResponderLoopThread(mock_logger,
                                                                 mock_client,
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

                mock_client.loop_forever.assert_called_once_with()

    def test_on_connect(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()
        topic = helpers.random_string()
        qos = helpers.random_string()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):

                SUT = user.mqttreplicate.MQTTResponderLoopThread(mock_logger,
                                                                 mock_client,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 topic,
                                                                 qos,
                                                                 None,
                                                                 None,
                                                                 None)

                mock_client.subscribe.return_value = (random.randint(1, 5), random.randint(6, 10))

                SUT._on_connect(None)

                mock_client.subscribe.assert_called_once_with(topic, qos)

    def test_on_message(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):

                SUT = user.mqttreplicate.MQTTResponderLoopThread(mock_logger,
                                                                 mock_client,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None)

                print(SUT.client_id)
                print("done 1")

        print("done 2")

    def test_template(self):
        mock_logger = mock.Mock()
        mock_client = mock.Mock()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.paho.mqtt'):

                SUT = user.mqttreplicate.MQTTResponderLoopThread(mock_logger,
                                                                 mock_client,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None,
                                                                 None)

                print(SUT.client_id)
                print("done 1")

        print("done 2")

if __name__ == '__main__':
    helpers.run_tests()
