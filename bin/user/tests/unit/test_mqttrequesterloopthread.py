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

class TestInit(unittest.TestCase):
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
