"""Tests for the lightweight label_server request handler."""

import io
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call

try:
    from .label_server import LabelServerRequestHandler
    from .process_manager import RemoteInferenceProcessError
except ImportError:  # direct execution from this directory
    from label_server import LabelServerRequestHandler
    from process_manager import RemoteInferenceProcessError


class LabelServerTest(unittest.TestCase):
    def setUp(self):
        self._old_token = os.environ.get("LABEL_SERVER_TOKEN")
        os.environ["LABEL_SERVER_TOKEN"] = "test-secret"
        self.manager = Mock()
        self.manager.status.return_value = "running"
        self.manager.start.return_value = "starting"
        self.manager.stop.return_value = "stopped"

    def tearDown(self):
        if self._old_token is None:
            os.environ.pop("LABEL_SERVER_TOKEN", None)
        else:
            os.environ["LABEL_SERVER_TOKEN"] = self._old_token

    def _handler(self, path, token=None, method="GET", body=b""):
        handler = object.__new__(LabelServerRequestHandler)
        handler.path = path
        handler.command = method
        handler.headers = {"Content-Length": str(len(body))}
        if token is not None:
            handler.headers["Token"] = token
        handler.rfile = io.BytesIO(body)
        handler.server = SimpleNamespace(manager=self.manager)
        handler.client_address = ("127.0.0.1", 43210)
        handler._send_json = Mock()
        return handler

    def test_health_is_public_and_reports_control_service(self):
        handler = self._handler("/health")
        handler.do_GET()
        handler._send_json.assert_called_once_with(200, True, {"status": "ok"})

    def test_status_requires_token(self):
        handler = self._handler("/status")
        handler.do_GET()
        handler._send_json.assert_called_once_with(
            401, False, error={"message": "Invalid control API token"}
        )
        self.manager.status.assert_not_called()

    def test_admin_api_fails_closed_without_configured_token(self):
        os.environ.pop("LABEL_SERVER_TOKEN", None)
        handler = self._handler("/status", token="test-secret")
        handler.do_GET()
        handler._send_json.assert_called_once_with(
            503, False, error={"message": "Control API token is not configured"}
        )

    def test_status_returns_manager_state_with_token(self):
        handler = self._handler("/status", token="test-secret")
        handler.do_GET()
        handler._send_json.assert_called_once_with(
            200, True, {"status": "running"}
        )
        self.manager.status.assert_called_once_with()

    def test_start_and_stop_call_only_fixed_manager_actions(self):
        start_handler = self._handler(
            "/start", token="test-secret", method="POST", body=b"{}"
        )
        stop_handler = self._handler(
            "/stop", token="test-secret", method="POST", body=b"{}"
        )
        start_handler.do_POST()
        stop_handler.do_POST()
        start_handler._send_json.assert_called_once_with(
            200, True, {"status": "starting"}
        )
        stop_handler._send_json.assert_called_once_with(
            200, True, {"status": "stopped"}
        )
        self.manager.start.assert_called_once_with()
        self.manager.stop.assert_called_once_with()

    def test_unknown_endpoint_is_rejected(self):
        handler = self._handler("/arbitrary-command")
        handler.do_GET()
        handler._send_json.assert_called_once_with(
            404, False, error={"message": "Unknown endpoint"}
        )

    def test_invalid_command_body_is_rejected(self):
        handler = self._handler(
            "/start", token="test-secret", method="POST", body=b"not-json"
        )
        handler.do_POST()
        self.assertEqual(handler._send_json.call_args, call(
            400, False, error={"message": "Request body must be valid JSON"}
        ))
        self.manager.start.assert_not_called()

    def test_process_manager_failure_is_reported_as_unavailable(self):
        self.manager.stop.side_effect = RemoteInferenceProcessError("docker failed")
        handler = self._handler(
            "/stop", token="test-secret", method="POST", body=json.dumps({}).encode()
        )
        with self.assertLogs("label_server", level="ERROR"):
            handler.do_POST()
        handler._send_json.assert_called_once_with(
            503, False, error={"message": "docker failed"}
        )


if __name__ == "__main__":
    unittest.main()
