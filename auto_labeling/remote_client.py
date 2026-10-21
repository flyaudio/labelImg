"""Small HTTP client for X-AnyLabeling-Server image detection."""

import base64
import math
import mimetypes
import os

import requests

REMOTE_OBJECT_LABEL = "AUTOLABEL_OBJECT"


class RemoteInferenceError(RuntimeError):
    """An error returned by, or encountered while contacting, the server."""


class RemoteInferenceClient:
    """Client for the server's model-list and single-image prediction APIs."""

    def __init__(self, server_url, api_key="", timeout=180, session=None):
        self.server_url = (server_url or "").strip().rstrip("/")
        if not self.server_url:
            raise ValueError("Server URL is empty")
        self.api_key = (api_key or "").strip()
        self.timeout = timeout
        self.session = session or requests

    @property
    def headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Token"] = self.api_key
        return headers

    def list_models(self):
        """Return the server's model metadata keyed by model ID."""
        try:
            response = self.session.get(
                self.server_url + "/v1/models",
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise RemoteInferenceError("Unable to load remote models: {}".format(exc)) from exc

        data = self._success_data(payload)
        if not isinstance(data, dict):
            raise RemoteInferenceError("The server returned an invalid model list")
        return data

    def predict(
        self, image_path, model_id, confidence=0.25, iou=0.45, marks=None
    ):
        """Return bbox detections and the number of ignored invalid results."""
        if not model_id:
            raise ValueError("No remote model is selected")
        if not os.path.isfile(image_path):
            raise ValueError("Image file does not exist: {}".format(image_path))

        try:
            with open(image_path, "rb") as image_file:
                image_bytes = image_file.read()
            encoded = base64.b64encode(image_bytes).decode("ascii")
            mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
            payload = {
                "model": model_id,
                "image": "data:{};base64,{}".format(mime_type, encoded),
                "params": {
                    "conf_threshold": float(confidence),
                    "iou_threshold": float(iou),
                },
            }
            if marks:
                payload["params"]["marks"] = marks
            response = self.session.post(
                self.server_url + "/v1/predict",
                json=payload,
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            response_payload = response.json()
        except (requests.RequestException, OSError, ValueError) as exc:
            raise RemoteInferenceError("Remote prediction failed: {}".format(exc)) from exc

        data = self._success_data(response_payload)
        if not isinstance(data, dict) or not isinstance(data.get("shapes", []), list):
            raise RemoteInferenceError("The server returned invalid prediction data")

        detections = []
        skipped = 0
        for shape in data.get("shapes", []):
            if not isinstance(shape, dict):
                skipped += 1
                continue
            try:
                detections.append(self._shape_bbox_detection(shape))
            except RemoteInferenceError:
                skipped += 1
        return detections, skipped

    @staticmethod
    def _success_data(payload):
        if not isinstance(payload, dict):
            raise RemoteInferenceError("The server returned an invalid response")
        if payload.get("success") is False:
            error = payload.get("error", {})
            message = error.get("message", "Unknown server error") if isinstance(error, dict) else str(error)
            raise RemoteInferenceError(message)
        if "data" not in payload:
            raise RemoteInferenceError("The server response is missing data")
        return payload["data"]

    @staticmethod
    def _shape_bbox_detection(shape):
        label = shape.get("label")
        points = shape.get("points")
        if not isinstance(label, str) or not label.strip():
            raise RemoteInferenceError("A shape is missing its class label")
        if not isinstance(points, list) or len(points) < 2:
            raise RemoteInferenceError("A shape must contain at least two points")

        coordinates = []
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                raise RemoteInferenceError("A shape contains an invalid point")
            try:
                x, y = float(point[0]), float(point[1])
            except (TypeError, ValueError) as exc:
                raise RemoteInferenceError("A shape contains non-numeric coordinates") from exc
            if not math.isfinite(x) or not math.isfinite(y):
                raise RemoteInferenceError("A shape contains non-finite coordinates")
            coordinates.append((x, y))

        min_x = min(point[0] for point in coordinates)
        min_y = min(point[1] for point in coordinates)
        max_x = max(point[0] for point in coordinates)
        max_y = max(point[1] for point in coordinates)
        if min_x == max_x or min_y == max_y:
            raise RemoteInferenceError("A shape has zero width or height")

        return {
            "label": label.strip(),
            "points": [
                (min_x, min_y),
                (max_x, min_y),
                (max_x, max_y),
                (min_x, max_y),
            ],
            "score": shape.get("score"),
        }
