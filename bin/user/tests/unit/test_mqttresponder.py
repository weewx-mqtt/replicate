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

import helpers

import user.mqttreplicate
from user.tests.unit.replicate_helpers import (create_responder_service_config,
                                               patched_responder_service)

class Event:
    def __init__(self, record):
        self.record = record

class TestMQTTResponder(unittest.TestCase):
    def test_init(self):
        mock_engine = mock.Mock()
        random_int = random.randint(1, 9999)
        instance_name = helpers.random_string()
        primary_name = helpers.random_string()

        config, instance_name, primary_name = create_responder_service_config(section_overrides={'log_mqtt': True})

        with patched_responder_service(queue=True, random_int=random_int) as mocks:
            SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)

            client_id = f'MQTTReplicateRespond-{random_int}'

            data_bindings = {
                f"{instance_name}/{primary_name}": {
                    'delta': 60,
                    'type': 'main',
                    'dbmanager': mocks.db_manager,
                }
            }

            mocks.mqtt_client.assert_called_once_with(mocks.logger(), client_id, None)
            # The thread_error event must be shared with the threads,
            # so a thread failure is seen by the service.
            self.assertEqual(SUT.thread_error, mocks.threading.Event())
            mocks.responder_thread.assert_called_once_with(mocks.logger(),
                                                           SUT.thread_error,
                                                           mocks.queue(),
                                                           SUT.config,
                                                           config)
            # The parsed options reach the thread through the config object.
            self.assertEqual(SUT.config.instance_name, instance_name)
            self.assertEqual(SUT.config.log_msg_count, 1000)
            self.assertEqual(SUT.config.throttle_count, 1000)
            self.assertEqual(SUT.config.throttle_sleep, 1)
            self.assertEqual(SUT.config.delta, 60)
            self.assertTrue(SUT.config.log_mqtt)
            self.assertEqual(SUT.config.host, 'localhost')
            self.assertEqual(SUT.config.port, 1883)
            self.assertEqual(SUT.config.keepalive, 60)
            self.assertEqual(SUT.config.publish_qos, 1)
            self.assertEqual(SUT.config.wait_for_thread_shutdown, 20)
            mocks.responder_thread().start.assert_called_once_with()

            mocks.loop_thread.assert_called_once_with(mocks.logger(),
                                                      mocks.client,
                                                      SUT.config,
                                                      mocks.queue(),
                                                      data_bindings)
            self.assertEqual(SUT.config.client_id, client_id)
            self.assertEqual(SUT.config.request_topic, f'replicate/request/{instance_name}')
            mocks.loop_thread().start.assert_called_once_with()

            self.assertDictEqual(SUT.data_bindings, data_bindings)

    def test_init_no_instance(self):
        mock_engine = mock.Mock()
        config, _, _ = create_responder_service_config(include_instance=False)

        with patched_responder_service():

            # A Responder section with no instance must raise,
            # not blow up with an IndexError.
            with self.assertRaises(AttributeError):
                user.mqttreplicate.MQTTResponder(mock_engine, config)

    def test_shutDown_disabled(self):
        mock_engine = mock.Mock()
        config, _, _ = create_responder_service_config(
            include_instance=False,
            section_overrides={'enable': False, 'wait_for_thread_shutdown': 3})

        with patched_responder_service(log_direct=True) as mocks:

            SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)
            self.assertFalse(SUT.enabled)

            # A disabled responder must shut down without error,
            # even though it was never fully initialized.
            SUT.shutDown()

            mocks.logger().info.assert_any_call(None, 'Responder not enabled, exiting.')
            # A component that never ran does not announce that it is shutting down.
            self.assertNotIn(mock.call(None, 'Shutting down.'),
                             mocks.logger().info.call_args_list)
            # The logger thread is still stopped, with the configured wait.
            mocks.logger().shutdown.assert_called_once_with(3)
            mocks.log_direct.assert_not_called()

    def test_shutDown(self):
        mock_engine = mock.Mock()
        config, _, _ = create_responder_service_config(section_overrides={'wait_for_thread_shutdown': 3})

        with patched_responder_service(queue=True, log_direct=True) as mocks:

            SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)
            SUT.loop_thread.is_alive.return_value = False
            for thread in SUT.threads:
                thread.is_alive.return_value = False

            SUT.shutDown()

            mocks.db_manager.close.assert_called_once_with()
            mocks.client.disconnect.assert_called_once_with()
            mocks.queue().put.assert_called_once_with(None)
            SUT.loop_thread.join.assert_called_once_with(3)
            for thread in SUT.threads:
                thread.join.assert_called_once_with(3)
            mocks.logger.return_value.info.assert_any_call(None, 'Shutting down.')
            mocks.logger.return_value.info.assert_any_call(None, 'Shutting down the loop thread.')
            mocks.logger.return_value.info.assert_any_call(None, 'Shutting down the responder threads.')
            mocks.logger.return_value.info.assert_any_call(None, 'Shutting down the logger thread.')
            mocks.logger.return_value.shutdown.assert_called_once_with(3)
            # The completion is logged directly, because the logger thread has stopped by then.
            mocks.log_direct.assert_called_once_with('MQTTResponder', 'INFO',
                                                     "MQTTResponder is shut down.")

    def test_new_archive_record(self):
        mock_engine = mock.Mock()
        config, _, _ = create_responder_service_config(secondary_bindings=(helpers.random_string() + '-secondary',))

        with patched_responder_service(paho=True, use_json=True) as mocks:

            SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)

            event = Event({'dateTime': random.randint(9999, 99999)})

            SUT.thread_error.is_set.return_value = False
            SUT.new_archive_record(event)

            mocks.db_manager.getRecord.assert_called_once_with(event.record['dateTime'], max_delta=60)
            self.assertEqual(mocks.client.publish.call_count, 2)

    def test_new_archive_record_thread_error(self):
        mock_engine = mock.Mock()
        config, _, _ = create_responder_service_config()

        with patched_responder_service(paho=True, use_json=True):

            SUT = user.mqttreplicate.MQTTResponder(mock_engine, config)

            event = Event({'dateTime': random.randint(9999, 99999)})

            # A set thread_error event must raise a ThreadError.
            SUT.thread_error.is_set.return_value = True
            with self.assertRaises(user.mqttreplicate.ThreadError):
                SUT.new_archive_record(event)

if __name__ == '__main__':
    helpers.run_tests()
