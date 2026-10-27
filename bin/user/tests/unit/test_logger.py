#    Copyright (c) 2026 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring
# pylint: disable=invalid-name

import queue
import threading
import unittest

import mock

import helpers

import user.mqttreplicate

class TestInitialization(unittest.TestCase):
    def test_init_starts_a_daemon_logger_thread(self):
        with mock.patch('user.mqttcommon.logging') as mock_logging:
            mock_log = mock_logging.getLogger.return_value

            SUT = user.mqttcommon.Logger('test-logger', queue.Queue(), log_keys=('thread_id',))

            self.assertTrue(SUT.log_thread.daemon)
            self.assertTrue(SUT.log_thread.is_alive())

            SUT.shutdown(timeout=5)

            self.assertFalse(SUT.log_thread.is_alive())
            # The thread logs its start and its exit, and nothing else.
            messages = [call[0][2] for call in mock_log.info.call_args_list]
            self.assertEqual(messages, ["Starting logger thread", f"Exited logger thread, {SUT.log_thread.name}."])

class TestCreateEntry(unittest.TestCase):
    def test_create_entry_returns_the_expected_entry(self):
        name = helpers.random_string()
        log_type = helpers.random_string()
        msg_text = helpers.random_string()

        entry = user.mqttcommon.Logger.create_entry(name, log_type, None, msg_text)

        self.assertEqual(entry, {'name': name, 'log_type': log_type, 'msg_id': None, 'msg_text': msg_text,
                                 'thread_id': threading.get_native_id(), 'archive_timestamp': None})

class TestLogMethods(unittest.TestCase):
    def test_log_methods_queue_the_message_with_the_calling_thread_id(self):
        with mock.patch('user.mqttcommon.logging') as mock_logging:
            mock_log = mock_logging.getLogger.return_value
            SUT = user.mqttcommon.Logger('test-logger', queue.Queue(), log_keys=('thread_id',))

            debug_message = helpers.random_string()
            info_message = helpers.random_string()
            error_message = helpers.random_string()
            thread_ids = []

            def log_messages():
                thread_ids.append(threading.get_native_id())
                SUT.debug(None, debug_message)
                SUT.info(None, info_message)
                SUT.error(None, error_message)

            thread = threading.Thread(target=log_messages)
            thread.start()
            thread.join()

            SUT.shutdown(timeout=5)

            # The message is logged with the id of the thread that queued it,
            # not the id of the logger thread.
            mock_log.debug.assert_called_once_with("(%s) %s", str(thread_ids[0]), debug_message)
            mock_log.info.assert_any_call("(%s) %s", str(thread_ids[0]), info_message)
            mock_log.error.assert_called_once_with("(%s) %s", str(thread_ids[0]), error_message)

class TestLogEntry(unittest.TestCase):
    @staticmethod
    def _stopped_logger():
        """ Construct a Logger and drain its thread, so log_entry calls are synchronous. """
        logger = user.mqttcommon.Logger('test-logger', queue.Queue(), log_keys=('thread_id',))
        logger.shutdown(timeout=5)
        return logger

    def test_log_entry_dispatches_the_log_types(self):
        with mock.patch('user.mqttcommon.logging') as mock_logging:
            mock_log = mock_logging.getLogger.return_value
            SUT = self._stopped_logger()
            mock_log.reset_mock()

            debug_name = helpers.random_string()
            debug_message = helpers.random_string()
            info_name = helpers.random_string()
            info_message = helpers.random_string()
            error_name = helpers.random_string()
            error_message = helpers.random_string()

            SUT.log_entry({'log_type': 'DEBUG', 'thread_id': debug_name, 'msg_text': debug_message})
            SUT.log_entry({'log_type': 'INFO', 'thread_id': info_name, 'msg_text': info_message})
            SUT.log_entry({'log_type': 'ERROR', 'thread_id': error_name, 'msg_text': error_message})

            mock_log.debug.assert_called_once_with("(%s) %s", debug_name, debug_message)
            mock_log.info.assert_called_once_with("(%s) %s", info_name, info_message)
            mock_log.error.assert_called_once_with("(%s) %s", error_name, error_message)

    def test_log_entry_with_an_invalid_entry_raises(self):
        with mock.patch('user.mqttcommon.logging'):
            SUT = self._stopped_logger()

            with self.assertRaises(KeyError):  # unknown log type
                SUT.log_entry({'log_type': helpers.random_string(), 'thread_id': 0,
                               'msg_text': helpers.random_string()})
            with self.assertRaises(KeyError):  # missing log type
                SUT.log_entry({})
            with self.assertRaises(TypeError):  # not a dict
                SUT.log_entry(helpers.random_string())

    def test_log_entry_skips_entries_with_a_none_log_type(self):
        with mock.patch('user.mqttcommon.logging') as mock_logging:
            mock_log = mock_logging.getLogger.return_value
            SUT = self._stopped_logger()
            mock_log.reset_mock()

            SUT.log_entry(user.mqttcommon.Logger.create_entry('test-logger', None, None,
                                                              helpers.random_string()))

            mock_log.debug.assert_not_called()
            mock_log.info.assert_not_called()
            mock_log.error.assert_not_called()

class TestShutdown(unittest.TestCase):
    def test_shutdown_drains_the_queue(self):
        with mock.patch('user.mqttcommon.logging') as mock_logging:
            mock_log = mock_logging.getLogger.return_value
            SUT = user.mqttcommon.Logger('test-logger', queue.Queue(), log_keys=('thread_id',))

            info_message = helpers.random_string()
            error_message = helpers.random_string()
            SUT.log_queue.put(user.mqttcommon.Logger.create_entry('test-logger', 'INFO', None, info_message))
            SUT.log_queue.put(user.mqttcommon.Logger.create_entry('test-logger', 'ERROR', None, error_message))

            SUT.shutdown(timeout=5)

            # The start message, the queued messages, and the exit message are logged in queue order.
            self.assertFalse(SUT.log_thread.is_alive())
            logged = [(call[0], call[1][2]) for call in mock_log.method_calls if call[0] in ('info', 'error')]
            self.assertEqual(logged, [('info', "Starting logger thread"),
                                      ('info', info_message),
                                      ('error', error_message),
                                      ('info', f"Exited logger thread, {SUT.log_thread.name}.")])

    def test_shutdown_is_idempotent(self):
        with mock.patch('user.mqttcommon.logging') as mock_logging:
            mock_log = mock_logging.getLogger.return_value
            SUT = user.mqttcommon.Logger('test-logger', queue.Queue(), log_keys=('thread_id',))

            SUT.shutdown(timeout=5)
            leftover = user.mqttcommon.Logger.create_entry('test-logger', 'INFO', None, helpers.random_string())
            SUT.log_queue.put(leftover)

            SUT.shutdown(timeout=5)

            # The second shutdown neither joins again nor queues another sentinel.
            self.assertFalse(SUT.log_thread.is_alive())
            self.assertIs(SUT.log_queue.get_nowait(), leftover)
            with self.assertRaises(queue.Empty):
                SUT.log_queue.get_nowait()
            mock_log.error.assert_not_called()

    def test_shutdown_warns_when_the_logger_thread_does_not_shut_down(self):
        with mock.patch('user.mqttcommon.logging') as mock_logging:
            mock_log = mock_logging.getLogger.return_value
            SUT = user.mqttcommon.Logger('test-logger', queue.Queue(), log_keys=('thread_id',))

            # Replace log_entry to simulate a stuck WeeWX log handler.
            block_entered = threading.Event()
            blocked = threading.Event()

            def block_entry(_entry):
                block_entered.set()
                blocked.wait(5)

            SUT.log_entry = block_entry

            SUT.log_queue.put(user.mqttcommon.Logger.create_entry('test-logger', 'INFO', None,
                                                                  helpers.random_string()))
            self.assertTrue(block_entered.wait(5))

            SUT.shutdown(timeout=0.05)

            expected = SUT.log_messages[124004].format(name=SUT.log_thread.name)
            mock_log.error.assert_called_once_with("(%s) %s", str(threading.get_native_id()), expected)
            self.assertTrue(SUT.log_thread.is_alive())

            # Release the thread and wait for it to exit.
            blocked.set()
            SUT.log_thread.join(timeout=5)
            self.assertFalse(SUT.log_thread.is_alive())

if __name__ == '__main__':
    helpers.run_tests()
