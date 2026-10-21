"""HTTP client for the lightweight remote inference service controller."""

import requests


class RemoteControlError(RuntimeError):
    """An error returned by, or encountered while contacting, label_server."""


class RemoteControlClient:
    """Client for label_server's health, status, start, and stop endpoints."""

    def __init__(self, server_url, api_key="", timeout=10, session=None):
        self.server_url = (server_url or "").strip().rstrip("/")
        if not self.server_url:
            raise ValueError("Control server URL is empty")
        self.api_key = (api_key or "").strip()
        self.timeout = timeout
        self.session = session or requests

    @property
    def headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Token"] = self.api_key
        return headers

    def health(self):
        """Check that the control service is reachable (no token required)."""
        return self._request("GET", "/health", authenticated=False)

    def status(self):
        """Return whether the inference service is running."""
        return self._request("GET", "/status")

    def start(self):
        """Ask the control service to start X-AnyLabeling-Server."""
        return self._request("POST", "/start")

    def stop(self):
        """Ask the control service to stop X-AnyLabeling-Server."""
        return self._request("POST", "/stop")

    def _request(self, method, path, authenticated=True):
        if authenticated and not self.api_key:
            raise RemoteControlError("Control API token is required")
        try:
            response = self.session.request(
                method,
                self.server_url + path,
                json={} if method == "POST" else None,
                headers=self.headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RemoteControlError(
                "Unable to contact the remote control service: {}".format(exc)
            ) from exc

        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            error_payload = None
            try:
                error_payload = response.json()
            except (AttributeError, ValueError):
                pass
            if isinstance(error_payload, dict):
                error = error_payload.get("error", {})
                if isinstance(error, dict) and error.get("message"):
                    raise RemoteControlError(error["message"]) from exc
            raise RemoteControlError(
                "Unable to contact the remote control service: {}".format(exc)
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise RemoteControlError(
                "The control service returned an invalid response"
            ) from exc

        if not isinstance(payload, dict):
            raise RemoteControlError("The control service returned an invalid response")
        if payload.get("success") is False:
            error = payload.get("error", {})
            message = (
                error.get("message", "Unknown control server error")
                if isinstance(error, dict)
                else str(error)
            )
            raise RemoteControlError(message)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise RemoteControlError("The control service response is missing data")
        return data
