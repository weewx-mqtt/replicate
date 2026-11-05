#
#    Copyright (c) 2026 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

import unittest
import mock

import helpers

import user.mqttreplicate


class TestMQTTClient(unittest.TestCase):
    # pylint: disable=protected-access
    @staticmethod
    def _make_client(log_connection=True):
        mock_logger = mock.Mock()

        with mock.patch('user.mqttreplicate.mqttcommon.has_v2_api', return_value=True):
            with mock.patch('user.mqttreplicate.mqttcommon.create_client') as mock_create_client:
                with mock.patch('user.mqttreplicate.mqttcommon.configure_reconnect_delay'):
                    SUT = user.mqttreplicate.MQTTClient(mock_logger, helpers.random_string(), None,
                                                        log_connection=log_connection)

        return SUT, mock_logger, mock_create_client

    def test_the_disconnect_is_always_logged(self):
        SUT, _, mock_create_client = self._make_client()

        # The wrapper is wired even though no consumer registered a handler.
        self.assertEqual(mock_create_client.return_value.on_disconnect, SUT._client_on_disconnect)

    def test_a_connection_is_informational(self):
        SUT, mock_logger, _ = self._make_client()
        SUT.on_connect = mock.Mock()
        reason_code = mock.Mock(value=0)

        SUT._client_on_connect(None, 'userdata', {'session present': 0}, reason_code, None)

        mock_logger.info.assert_any_call(None, "Connected with result code 0, No error.")
        mock_logger.info.assert_any_call(None, "Connection flags: {'session present': 0}.")
        mock_logger.debug.assert_not_called()

    def test_a_per_request_connection_is_quiet(self):
        SUT, mock_logger, _ = self._make_client(log_connection=False)
        SUT.on_connect = mock.Mock()
        reason_code = mock.Mock(value=0)

        SUT._client_on_connect(None, 'userdata', {}, reason_code, None)
        SUT._client_on_disconnect(None, 'userdata', None, reason_code, None)

        mock_logger.info.assert_not_called()
        mock_logger.debug.assert_not_called()

    def test_a_per_request_disconnect_error_is_still_logged(self):
        SUT, mock_logger, _ = self._make_client(log_connection=False)
        reason_code = mock.Mock(value=7)

        SUT._client_on_disconnect(None, 'userdata', None, reason_code, None)

        mock_logger.error.assert_called_once_with(
            None, f"Disconnected with result code 7, {user.mqttreplicate.paho.mqtt.client.error_string(7)}")
        mock_logger.info.assert_not_called()

    def test_a_requested_disconnect_is_informational(self):
        SUT, mock_logger, _ = self._make_client()
        reason_code = mock.Mock(value=0)

        SUT._client_on_disconnect(None, None, None, reason_code, None)

        mock_logger.info.assert_called_once_with(None, "Disconnected with result code 0, No error.")
        mock_logger.error.assert_not_called()

    def test_an_unexpected_disconnect_is_an_error(self):
        SUT, mock_logger, _ = self._make_client()
        reason_code = mock.Mock(value=7)
        SUT.on_disconnect = mock.Mock()

        SUT._client_on_disconnect(None, 'userdata', None, reason_code, None)

        mock_logger.error.assert_called_once_with(
            None, f"Disconnected with result code 7, {user.mqttreplicate.paho.mqtt.client.error_string(7)}")
        mock_logger.info.assert_not_called()
        # A registered handler still receives the normalized result code.
        SUT.on_disconnect.assert_called_once_with('userdata', 7)


if __name__ == '__main__':
    helpers.run_tests()
