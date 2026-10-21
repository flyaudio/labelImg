"""Tests for the remote label_server control client."""

import unittest
from unittest.mock import Mock

import requests

from auto_labeling.remote_control_client import (
    RemoteControlClient,
    RemoteControlError,
)


class RemoteControlClientTest(unittest.TestCase):
    def _response(self, data):
        response = Mock()
        response.json.return_value = {"success": True, "data": data}
        return response

    def test_health_does_not_require_token(self):
        session = Mock()
        session.request.return_value = self._response({"status": "ok"})
        client = RemoteControlClient(
            "http://server:8001/", session=session
        )

        self.assertEqual(client.health(), {"status": "ok"})
        session.request.assert_called_once_with(
            "GET",
            "http://server:8001/health",
            json=None,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

    def test_start_sends_token_and_empty_json_body(self):
        session = Mock()
        session.request.return_value = self._response({"status": "starting"})
        client = RemoteControlClient(
            "http://server:8001", api_key="secret", session=session
        )

        self.assertEqual(client.start(), {"status": "starting"})
        session.request.assert_called_once_with(
            "POST",
            "http://server:8001/start",
            json={},
            headers={"Content-Type": "application/json", "Token": "secret"},
            timeout=10,
        )

    def test_admin_action_requires_token(self):
        client = RemoteControlClient("http://server:8001")
        with self.assertRaisesRegex(RemoteControlError, "token is required"):
            client.stop()

    def test_error_envelope_is_reported(self):
        session = Mock()
        response = Mock()
        response.json.return_value = {
            "success": False,
            "error": {"message": "not authorized"},
        }
        session.request.return_value = response
        client = RemoteControlClient(
            "http://server:8001", api_key="bad", session=session
        )

        with self.assertRaisesRegex(RemoteControlError, "not authorized"):
            client.status()

    def test_http_error_uses_server_error_message(self):
        session = Mock()
        response = Mock()
        response.json.return_value = {
            "success": False,
            "error": {"message": "Invalid control API token"},
        }
        response.raise_for_status.side_effect = requests.HTTPError("401", response=response)
        session.request.return_value = response
        client = RemoteControlClient(
            "http://server:8001", api_key="bad", session=session
        )

        with self.assertRaisesRegex(RemoteControlError, "Invalid control API token"):
            client.status()

    def test_network_error_is_wrapped(self):
        session = Mock()
        session.request.side_effect = requests.ConnectionError("offline")
        client = RemoteControlClient(
            "http://server:8001", api_key="secret", session=session
        )

        with self.assertRaisesRegex(RemoteControlError, "offline"):
            client.status()


if __name__ == "__main__":
    unittest.main()
