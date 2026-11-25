#    Copyright (c) 2026 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

# pylint: disable=wrong-import-order
# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring
# pylint: disable=invalid-name

import unittest
import mock

import queue
import random

import helpers

import user.mqttreplicate
from user.tests.unit.replicate_helpers import create_requester_config, patched_requester

class PriorityQueueStub:
    def __init__(self):
        # Some variables that are only used for testing
        self.get_call_count = 0

    def get(self, _block, _timeout):
        self.get_call_count += 1
        if self.get_call_count == 2:
            return ({'dateTime': random.randint(0, 9999)}, {'dateTime': random.randint(10000, 19999)})

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
        config, instance_name, primary_name = create_requester_config()

        with patched_requester(random_int=random_int) as mocks:
            last_good_timestamp = helpers.random_string()
            manager_dict = helpers.random_string()
            mock_db_manager = mock.Mock()
            mocks.manager.get_manager_dict_from_config.return_value = manager_dict
            mocks.manager.open_manager.return_value = mock_db_manager
            mock_db_manager.lastGoodStamp.return_value = last_good_timestamp

            SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)

            client_id = f'MQTTReplicateRequest-{random_int}'
            self.assertEqual(SUT.config.wait_for_thread_shutdown, 20)
            mocks.mqtt_client.assert_called_once_with(SUT.logger, client_id, None)
            mocks.loop_thread.assert_called_once()
            SUT.loop_thread.start.assert_called_once_with()
            SUT.mqtt_client.publish.assert_called_once()

            # The default response_topic is RESPONSE_TOPIC.
            self.assertEqual(SUT.response_topic, f'replicate/response/{client_id}')
            # The config passed to MQTTRequesterLoopThread carries the response_topic.
            self.assertEqual(mocks.loop_thread.call_args[0][2].response_topic,
                             f'replicate/response/{client_id}')

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

    def test_init_log_mqtt_string(self):
        mock_engine = mock.Mock()
        config, _, _ = create_requester_config(requester_overrides={'log_mqtt': 'False'})

        with patched_requester() as mocks:
            mocks.manager.open_manager.return_value = mock.Mock()

            SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)

            self.assertFalse(SUT.config.log_mqtt)
            # The parsed value reaches the loop thread's config.
            self.assertFalse(mocks.loop_thread.call_args[0][2].log_mqtt)

    def test_close_port(self):
        mock_engine = mock.Mock()
        config, _, _ = create_requester_config(requester_overrides={'wait_for_thread_shutdown': 3})

        with patched_requester(log_direct=True) as mocks:
            mocks.loop_thread.return_value.is_alive.return_value = False

            SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)
            SUT.closePort()

            SUT.mqtt_client.disconnect.assert_called_once_with()
            SUT.loop_thread.join.assert_called_once_with(3)
            mocks.logger.return_value.info.assert_any_call(None, "Shutting down.")
            mocks.logger.return_value.info.assert_any_call(None, "Shutting down the loop thread.")
            mocks.logger.return_value.info.assert_any_call(None, "Shutting down the logger thread.")
            mocks.logger.return_value.shutdown.assert_called_once_with(3)
            # The completion is logged directly, because the logger thread has stopped by then.
            mocks.log_direct.assert_called_once_with('MQTTRequester', 'INFO',
                                                     "MQTTRequester is shut down.")

    def test_gen_startup_records(self):
        mock_engine = mock.Mock()
        config, _, _ = create_requester_config()

        with patched_requester() as mocks:
            with patch(user.mqttreplicate.queue, 'PriorityQueue', PriorityQueueStub):
                with mock.patch.object(user.mqttreplicate.queue.PriorityQueue,
                                       'get',
                                       side_effect=PriorityQueueStub.get,
                                       autospec=True) as mock_get:

                    SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)

                    for _record in SUT.genStartupRecords(random.randint(1, 9999)):
                        pass

                    self.assertEqual(mock_get.call_count, 4)
                    self.assertEqual(mocks.logger().info.call_count, 2)

    def test_gen_archive_records(self):
        mock_engine = mock.Mock()
        config, _, _ = create_requester_config()

        with patched_requester() as mocks:
            with patch(user.mqttreplicate.queue, 'PriorityQueue', PriorityQueueStub):
                with mock.patch.object(user.mqttreplicate.queue.PriorityQueue,
                                       'get',
                                       side_effect=PriorityQueueStub.get,
                                       autospec=True) as mock_get:

                    SUT = user.mqttreplicate.MQTTRequester(config, mock_engine)

                    for _record in SUT.genArchiveRecords(random.randint(1, 9999)):
                        pass

                    self.assertEqual(mock_get.call_count, 4)
                    self.assertEqual(mocks.logger().info.call_count, 1)

if __name__ == '__main__':
    helpers.run_tests()
