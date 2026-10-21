"""Unit tests for the X-AnyLabeling-Server HTTP client."""

import os
import tempfile
import unittest
from unittest.mock import Mock

import requests

from auto_labeling.remote_client import (
    RemoteInferenceClient,
    RemoteInferenceError,
)


class RemoteInferenceClientTest(unittest.TestCase):
    def test_model_list_uses_server_envelope_and_token(self):
        session = Mock()
        response = Mock()
        response.json.return_value = {
            "success": True,
            "data": {"model-a": {"display_name": "Model A"}},
        }
        session.get.return_value = response
        client = RemoteInferenceClient(
            "http://server:8000/", api_key="secret", session=session
        )

        self.assertEqual(
            client.list_models(), {"model-a": {"display_name": "Model A"}}
        )
        session.get.assert_called_once_with(
            "http://server:8000/v1/models",
            headers={"Content-Type": "application/json", "Token": "secret"},
            timeout=180,
        )
        response.raise_for_status.assert_called_once_with()

    def test_predict_encodes_image_and_converts_rectangle_to_corners(self):
        session = Mock()
        response = Mock()
        response.json.return_value = {
            "success": True,
            "data": {
                "shapes": [
                    {
                        "label": "car",
                        "shape_type": "rectangle",
                        "points": [[20, 30], [10, 30], [10, 5], [20, 5]],
                        "score": 0.92,
                    }
                ]
            },
        }
        session.post.return_value = response
        client = RemoteInferenceClient("http://server:8000", session=session)
        handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        try:
            handle.write(b"image-bytes")
            handle.close()

            detections, skipped = client.predict(
                handle.name,
                "detector",
                confidence=0.3,
                iou=0.5,
                marks=[
                    {"type": "point", "data": [8, 9], "label": 1},
                    {"type": "point", "data": [11, 12], "label": 0},
                    {"type": "rectangle", "data": [1, 2, 3, 4], "label": 1},
                ],
            )
        finally:
            os.unlink(handle.name)

        self.assertEqual(skipped, 0)
        self.assertEqual(detections[0]["label"], "car")
        self.assertEqual(
            detections[0]["points"],
            [(10.0, 5.0), (20.0, 5.0), (20.0, 30.0), (10.0, 30.0)],
        )
        self.assertEqual(detections[0]["score"], 0.92)
        payload = session.post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "detector")
        self.assertTrue(payload["image"].startswith("data:image/png;base64,"))
        self.assertEqual(
            payload["params"],
            {
                "conf_threshold": 0.3,
                "iou_threshold": 0.5,
                "marks": [
                    {"type": "point", "data": [8, 9], "label": 1},
                    {"type": "point", "data": [11, 12], "label": 0},
                    {"type": "rectangle", "data": [1, 2, 3, 4], "label": 1},
                ],
            },
        )

    def test_predict_converts_polygon_results_to_bbox(self):
        session = Mock()
        response = Mock()
        response.json.return_value = {
            "success": True,
            "data": {
                "shapes": [
                    {
                        "shape_type": "polygon",
                        "label": "mask",
                        "points": [[5, 7], [15, 8], [12, 20], [3, 18]],
                    }
                ]
            },
        }
        session.post.return_value = response
        client = RemoteInferenceClient("http://server", session=session)
        image = tempfile.NamedTemporaryFile(delete=False)
        try:
            image.close()
            detections, skipped = client.predict(image.name, "detector")
        finally:
            os.unlink(image.name)

        self.assertEqual(skipped, 0)
        self.assertEqual(detections[0]["label"], "mask")
        self.assertEqual(
            detections[0]["points"],
            [(3.0, 7.0), (15.0, 7.0), (15.0, 20.0), (3.0, 20.0)],
        )

    def test_server_error_envelope_raises_readable_error(self):
        session = Mock()
        response = Mock()
        response.json.return_value = {
            "success": False,
            "error": {"code": "MODEL_NOT_FOUND", "message": "Missing model"},
        }
        session.post.return_value = response
        client = RemoteInferenceClient("http://server", session=session)
        image = tempfile.NamedTemporaryFile(delete=False)
        try:
            image.close()
            with self.assertRaisesRegex(RemoteInferenceError, "Missing model"):
                client.predict(image.name, "missing")
        finally:
            os.unlink(image.name)

    def test_bad_shape_coordinates_raise_error(self):
        with self.assertRaises(RemoteInferenceError):
            RemoteInferenceClient._shape_bbox_detection(
                {"label": "car", "points": [[1, 1], [1, 10]]}
            )

    def test_predict_skips_only_invalid_shapes(self):
        session = Mock()
        response = Mock()
        response.json.return_value = {
            "success": True,
            "data": {
                "shapes": [
                    {"shape_type": "point", "label": "good", "points": [[2, 3], [8, 9]]},
                    {"shape_type": "polygon", "label": "bad", "points": [[1, 1]]},
                    None,
                ]
            },
        }
        session.post.return_value = response
        client = RemoteInferenceClient("http://server", session=session)
        image = tempfile.NamedTemporaryFile(delete=False)
        try:
            image.close()
            detections, skipped = client.predict(image.name, "detector")
        finally:
            os.unlink(image.name)

        self.assertEqual(skipped, 2)
        self.assertEqual(len(detections), 1)
        self.assertEqual(
            detections[0]["points"],
            [(2.0, 3.0), (8.0, 3.0), (8.0, 9.0), (2.0, 9.0)],
        )

    def test_http_failure_is_wrapped(self):
        session = Mock()
        session.get.side_effect = requests.Timeout("timed out")
        client = RemoteInferenceClient("http://server", session=session)

        with self.assertRaisesRegex(RemoteInferenceError, "timed out"):
            client.list_models()


if __name__ == "__main__":
    unittest.main()
