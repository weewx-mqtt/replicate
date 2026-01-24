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

import helpers

import user.mqttreplicate

class TestInit(unittest.TestCase):
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

                                user.mqttreplicate.MQTTResponder(mock_engine, config)

                                print("done 1")

        print("done 2")

if __name__ == '__main__':
    helpers.run_tests()
