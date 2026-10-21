"""Small standard-library HTTP control service for X-AnyLabeling-Server."""

import hmac
import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

try:  # direct execution under systemd and package-style test imports
    from .process_manager import (
        RemoteInferenceProcessError,
        RemoteInferenceProcessManager,
    )
except ImportError:  # pragma: no cover - used by direct script execution
    from process_manager import (
        RemoteInferenceProcessError,
        RemoteInferenceProcessManager,
    )


LOGGER = logging.getLogger("label_server")
MAX_REQUEST_BYTES = 16 * 1024


class LabelServerHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler_class, manager):
        super().__init__(address, handler_class)
        self.manager = manager


class LabelServerRequestHandler(BaseHTTPRequestHandler):
    server_version = "label_server/1.0"

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/health":
            self._send_json(200, True, {"status": "ok"})
            return
        if path == "/status":
            if not self._is_authorized():
                return
            try:
                status = self.server.manager.status()
            except RemoteInferenceProcessError as exc:
                self._send_error(503, str(exc))
                return
            self._send_json(200, True, {"status": status})
            return
        self._send_error(404, "Unknown endpoint")

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in {"/start", "/stop"}:
            self._send_error(404, "Unknown endpoint")
            return
        if not self._is_authorized():
            return
        if not self._read_json_body():
            return

        action = "start" if path == "/start" else "stop"
        LOGGER.info("Received %s request from %s", action, self.client_address[0])
        try:
            status = getattr(self.server.manager, action)()
        except RemoteInferenceProcessError as exc:
            LOGGER.exception("Unable to %s the inference service", action)
            self._send_error(503, str(exc))
            return
        LOGGER.info("Inference service state after %s request: %s", action, status)
        self._send_json(200, True, {"status": status})

    def _is_authorized(self):
        expected_token = os.environ.get("LABEL_SERVER_TOKEN", "").strip()
        if not expected_token:
            self._send_error(503, "Control API token is not configured")
            return False
        supplied_token = self.headers.get("Token", "").strip()
        if not hmac.compare_digest(
            supplied_token.encode("utf-8"), expected_token.encode("utf-8")
        ):
            self._send_error(401, "Invalid control API token")
            return False
        return True

    def _read_json_body(self):
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError:
            self._send_error(400, "Invalid Content-Length")
            return False
        if length < 0 or length > MAX_REQUEST_BYTES:
            self._send_error(413, "Request body is too large")
            return False
        if length == 0:
            return True
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_error(400, "Request body must be valid JSON")
            return False
        if not isinstance(payload, dict):
            self._send_error(400, "Request body must be a JSON object")
            return False
        return True

    def _send_error(self, status, message):
        self._send_json(status, False, error={"message": message})

    def _send_json(self, status, success, data=None, error=None):
        response = {"success": success}
        if success:
            response["data"] = data or {}
        else:
            response["error"] = error or {"message": "Request failed"}
        body = json.dumps(response).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def log_message(self, format_string, *args):
        LOGGER.info("%s - %s", self.client_address[0], format_string % args)


def create_server(host=None, port=None, manager=None):
    """Create a testable server; the control API uses no ML/GPU packages."""
    address = host or os.environ.get("LABEL_SERVER_HOST", "0.0.0.0")
    listen_port = int(
        port if port is not None else os.environ.get("LABEL_SERVER_PORT", "8001")
    )
    return LabelServerHTTPServer(
        (address, listen_port),
        LabelServerRequestHandler,
        manager or RemoteInferenceProcessManager(),
    )


def main():
    logging.basicConfig(
        level=os.environ.get("LABEL_SERVER_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    host = os.environ.get("LABEL_SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("LABEL_SERVER_PORT", "8001"))
    server = create_server(host=host, port=port)
    LOGGER.info("label_server listening on %s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("label_server shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
