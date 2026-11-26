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
from user.tests.unit.replicate_helpers import create_responder_thread_config_dict


def create_thread(logger, thread_error, data_queue, config, config_dict, mqtt_client):
    """ Build a responder thread with the standard collaborator arguments. """
    return user.mqttreplicate.MQTTResponderThread(logger, thread_error, data_queue,
                                                  config, config_dict, mqtt_client)


class TestMQTTResponderThread(unittest.TestCase):
    def test_init(self):
        mock_logger = mock.Mock()
        mqtt_client = mock.Mock()

        config, instance_name, data_binding_name = create_responder_thread_config_dict()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.weewx.manager') as mock_manager:
                manager_dict = helpers.random_string()
                mock_manager.get_manager_dict_from_config.return_value = manager_dict

                thread_config = user.mqttreplicate.MQTTResponderConfig(
                    instance_name=instance_name,
                    log_mqtt=True)
                SUT = create_thread(mock_logger, None, None, thread_config, config, mqtt_client)

        expected_results = {
            f"{instance_name}/{data_binding_name}": {
                'delta': None,
                'type': 'secondary',
                'manager_dict': manager_dict,
            }
        }
        self.assertDictEqual(SUT.data_bindings, expected_results)
        # The thread publishes through the service's client, not its own.
        self.assertEqual(SUT.mqtt_client, mqtt_client)
        self.assertFalse(SUT.inflight.inflight)

    def test_run(self):
        mock_logger = mock.Mock()
        config, instance_name, binding_name = create_responder_thread_config_dict()
        publish_qos = helpers.random_string()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.weewx.manager') as mock_manager:
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

                mock_mqtt_client = mock.Mock()
                message_info = mock.Mock(rc=0)
                mock_mqtt_client.publish.return_value = message_info

                mock_thread_error = mock.Mock()

                thread_config = user.mqttreplicate.MQTTResponderConfig(
                    instance_name=instance_name,
                    log_msg_count=random.randint(2, 100),
                    throttle_count=1000,
                    throttle_sleep=1,
                    keepalive=60,
                    publish_qos=publish_qos)
                SUT = create_thread(mock_logger, mock_thread_error, mock_data_queue,
                                    thread_config, config, mock_mqtt_client)

                SUT.run()

                mock_manager.open_manager.assert_called_once()
                mock_mqtt_client.publish.assert_called_once_with(data['topic'],
                                                                 '{}',
                                                                 publish_qos,
                                                                 False,
                                                                 properties=data['properties'])
                # The flush waits for the last publish, so the batch is complete.
                message_info.wait_for_publish.assert_called_once()
                mock_db_manager.close.assert_called_once()
                mock_logger.info.assert_any_call(None, "Responder thread is shut down.")
                # The happy path must not signal a thread error.
                mock_thread_error.set.assert_not_called()

    def test_run_publish_error_is_logged(self):
        mock_logger = mock.Mock()
        config, instance_name, binding_name = create_responder_thread_config_dict()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.weewx.manager') as mock_manager:
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

                mock_mqtt_client = mock.Mock()
                mock_mqtt_client.publish.return_value = mock.Mock(rc=4)

                thread_config = user.mqttreplicate.MQTTResponderConfig(
                    instance_name=instance_name,
                    log_msg_count=1000,
                    throttle_count=1000,
                    throttle_sleep=1,
                    keepalive=60,
                    publish_qos=1)
                SUT = create_thread(mock_logger, mock.Mock(), mock_data_queue,
                                    thread_config, config, mock_mqtt_client)

                SUT.run()

                # A refused publish is logged and is not tracked as in flight.
                self.assertIn('Error 4', mock_logger.error.call_args[0][1])
                self.assertFalse(SUT.inflight.inflight)

    def test_run_publish_wait_timeout(self):
        mock_logger = mock.Mock()
        config, instance_name, binding_name = create_responder_thread_config_dict()

        keepalive = 10

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.weewx.manager') as mock_manager:
                with mock.patch('user.mqttreplicate.time') as mock_time:
                    # The flush sets its deadline from the first call, then finds
                    # the wait has already passed it on the second.
                    mock_time.time.side_effect = [100, 100 + keepalive + 1]

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

                    mock_mqtt_client = mock.Mock()
                    mock_mqtt_client.publish.return_value = mock.Mock(rc=0)

                    thread_config = user.mqttreplicate.MQTTResponderConfig(
                        instance_name=instance_name,
                        log_msg_count=1000,
                        throttle_count=1000,
                        throttle_sleep=1,
                        keepalive=keepalive,
                        publish_qos=1)
                    SUT = create_thread(mock_logger, mock.Mock(), mock_data_queue,
                                        thread_config, config, mock_mqtt_client)

                    SUT.run()

                    # The wait gives up after the keepalive, logs, and clears the window.
                    self.assertEqual(mock_logger.error.call_count, 1)
                    self.assertIn(f'Timed out after {keepalive} seconds',
                                  mock_logger.error.call_args[0][1])
                    self.assertFalse(SUT.inflight.inflight)
                    mock_db_manager.close.assert_called_once()

    def test_run_has_exception(self):
        mock_logger = mock.Mock()
        config, instance_name, binding_name = create_responder_thread_config_dict()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.weewx.manager') as mock_manager:
                mock_db_manager = mock.Mock()
                mock_manager.open_manager.return_value = mock_db_manager
                mock_db_manager.genBatchRecords.return_value = [{}]

                mock_mqtt_client = mock.Mock()
                mock_mqtt_client.publish.side_effect = Exception()

                mock_thread_error = mock.Mock()

                data = {
                    'topic': helpers.random_string(),
                    'data_binding': f'{instance_name}/{binding_name}',
                    'properties': helpers.random_string(),
                    'start_timestamp': helpers.random_string()
                }
                mock_data_queue = mock.Mock()
                mock_data_queue.get.side_effect = [data]

                thread_config = user.mqttreplicate.MQTTResponderConfig(instance_name=instance_name)
                SUT = create_thread(mock_logger, mock_thread_error, mock_data_queue,
                                    thread_config, config, mock_mqtt_client)

                SUT.run()

                mock_manager.open_manager.assert_called_once()
                self.assertEqual(mock_logger.error.call_count, 2)
                # The failure must be signaled through the shared thread_error event.
                mock_thread_error.set.assert_called_once_with()
                mock_db_manager.close.assert_called_once()

    def test_track_inflight_waits_for_the_oldest_when_full(self):
        mock_logger = mock.Mock()
        config, instance_name, _ = create_responder_thread_config_dict()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.weewx.manager'):
                thread_config = user.mqttreplicate.MQTTResponderConfig(
                    instance_name=instance_name,
                    throttle_count=1,
                    keepalive=random.randint(1, 99))
                SUT = create_thread(mock_logger, None, None, thread_config, config, mock.Mock())

        first = mock.Mock()
        first.mid = 1
        first.is_published.return_value = False
        second = mock.Mock()
        second.mid = 2
        second.is_published.return_value = False

        SUT._track_inflight(first)
        self.assertEqual(list(SUT.inflight.inflight.values()), [first])

        # The window is full, so the oldest publish is awaited before the next is added.
        SUT._track_inflight(second)
        first.wait_for_publish.assert_called_once_with(thread_config.keepalive)
        self.assertEqual(list(SUT.inflight.inflight.values()), [second])

    def test_prune_inflight_drops_published_messages(self):
        mock_logger = mock.Mock()
        config, instance_name, _ = create_responder_thread_config_dict()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.weewx.manager'):
                thread_config = user.mqttreplicate.MQTTResponderConfig(instance_name=instance_name)
                SUT = create_thread(mock_logger, None, None, thread_config, config, mock.Mock())

        published = mock.Mock()
        published.mid = 1
        published.is_published.return_value = True
        pending = mock.Mock()
        pending.mid = 2
        pending.is_published.return_value = False
        SUT.inflight.inflight = {1: published, 2: pending}

        SUT.inflight.prune()

        self.assertEqual(list(SUT.inflight.inflight.values()), [pending])

    def test_prune_inflight_drops_messages_that_cannot_be_checked(self):
        mock_logger = mock.Mock()
        config, instance_name, _ = create_responder_thread_config_dict()

        with mock.patch('user.mqttreplicate.threading'):
            with mock.patch('user.mqttreplicate.weewx.manager'):
                thread_config = user.mqttreplicate.MQTTResponderConfig(instance_name=instance_name)
                SUT = create_thread(mock_logger, None, None, thread_config, config, mock.Mock())

        failed = mock.Mock()
        failed.mid = 1
        failed.is_published.side_effect = ValueError()
        SUT.inflight.inflight = {1: failed}

        SUT.inflight.prune()

        self.assertFalse(SUT.inflight.inflight)


if __name__ == '__main__':
    helpers.run_tests()
