"""UI-focused tests for the remote annotation panel."""

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QApplication

from auto_labeling.remote_annotation_widget import RemoteAnnotationWidget


class RemoteAnnotationWidgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.settings_patcher = patch(
            "auto_labeling.remote_annotation_widget.get_config",
            return_value={
                "remote_server_settings": {
                    "server_url": "http://127.0.0.1:8000",
                    "api_key": "",
                    "timeout": 10,
                }
            },
        )
        self.settings_patcher.start()
        self.timer_patcher = patch(
            "PyQt6.QtCore.QTimer.singleShot", return_value=None
        )
        self.timer_patcher.start()
        self.widget = RemoteAnnotationWidget(parent=None)

    def tearDown(self):
        self.widget.close()
        self.widget.deleteLater()
        self.settings_patcher.stop()
        self.timer_patcher.stop()
        self.app.processEvents()

    def test_defaults_keep_existing_shapes_and_disable_run_until_model_load(self):
        self.assertTrue(self.widget.keep_existing_checkbox.isChecked())
        self.assertFalse(self.widget.run_button.isEnabled())
        self.assertEqual(self.widget.conf_spin.value(), 0.25)
        self.assertEqual(self.widget.iou_spin.value(), 0.45)
        self.assertEqual(
            self.widget._settings["control_server_url"],
            "http://192.168.31.5:8001",
        )
        self.assertEqual(self.widget._settings["control_api_key"], "")

    def test_model_list_populates_model_ids_as_combo_data(self):
        self.widget._on_models_loaded(
            {"model-1": {"display_name": "Detector One"}}
        )

        self.assertEqual(self.widget.model_combo.count(), 1)
        self.assertEqual(self.widget.model_combo.currentText(), "Detector One")
        self.assertEqual(self.widget.model_combo.currentData(), "model-1")
        self.assertTrue(self.widget.run_button.isEnabled())

    def test_visual_prompt_model_uses_server_confidence_default(self):
        self.widget._on_models_loaded(
            {
                "geco2": {
                    "display_name": "GECO2",
                    "widgets": [
                        {"name": "button_add_point"},
                        {"name": "edit_conf", "value": 0.33},
                    ],
                }
            }
        )

        self.assertTrue(self.widget._selected_model_requires_prompt())
        self.assertEqual(self.widget.conf_spin.value(), 0.33)

    def test_model_list_keeps_visual_prompt_models_and_hides_text_models(self):
        self.widget._on_models_loaded(
            {
                "geco2": {
                    "display_name": "GECO2",
                    "widgets": [{"name": "add_pos_rect"}],
                },
                "caption": {
                    "display_name": "Caption",
                    "params": {"task": "caption"},
                },
                "sam": {
                    "display_name": "SAM",
                    "widgets": [{"name": "button_add_point"}],
                },
                "visual": {
                    "display_name": "Visual Model",
                    "batch_processing_mode": "visual_prompting",
                },
                "prompt_model": {
                    "display_name": "Prompt model",
                    "batch_processing_mode": "text_prompt",
                },
                "detector": {"display_name": "Detector"},
            }
        )

        self.assertEqual(
            [
                self.widget.model_combo.itemData(index)
                for index in range(self.widget.model_combo.count())
            ],
            ["geco2", "sam", "visual", "detector"],
        )

    def test_prompt_model_requires_prompt_marks(self):
        self.widget.main_window = SimpleNamespace(
            canvas=SimpleNamespace(prompt_marks=[])
        )

        self.widget._models = {
            "prompt": {"widgets": [{"name": "button_add_point"}]}
        }
        self.widget.model_combo.addItem("Prompt", userData="prompt")

        self.assertTrue(self.widget._selected_model_requires_prompt())
        self.assertEqual(self.widget.main_window.canvas.prompt_marks, [])

    def test_prompt_buttons_expose_screenshot_shortcuts(self):
        self.assertEqual(self.widget.positive_point_button.shortcut().toString(), "Q")
        self.assertEqual(self.widget.negative_point_button.shortcut().toString(), "E")
        self.assertEqual(self.widget.positive_rectangle_button.shortcut().toString(), "R")
        self.assertEqual(
            self.widget.negative_rectangle_button.shortcut().toString(), "Shift+R"
        )
        # B is registered as a MainWindow shortcut so it works while the
        # canvas or another child widget has focus.
        self.assertEqual(self.widget.clear_prompts_button.shortcut().toString(), "")
        self.assertEqual(self.widget.run_button.shortcut().toString(), "F")

    def test_point_and_rectangle_prompts_are_sent_with_selected_model(self):
        image = tempfile.NamedTemporaryFile(delete=False)
        image.close()
        marks = [
            {"type": "point", "data": [12.0, 18.0], "label": 1},
            {"type": "point", "data": [20.0, 25.0], "label": 0},
            {"type": "rectangle", "data": [5.0, 6.0, 30.0, 40.0], "label": 1},
        ]
        canvas = SimpleNamespace(
            prompt_marks=marks,
            set_prompt_mode=Mock(),
            clear_prompt_marks=Mock(),
        )
        self.widget.main_window = SimpleNamespace(
            canvas=canvas, file_path=image.name
        )
        self.widget._models = {
            "prompt-model": {"batch_processing_mode": "visual_prompting"}
        }
        self.widget.model_combo.addItem("Prompt model", userData="prompt-model")
        client = Mock()
        client.predict.return_value = ([], 0)

        def run_request_immediately(request, callback, **_kwargs):
            callback(request())

        try:
            with patch.object(self.widget, "_client", return_value=client), patch.object(
                self.widget,
                "_start_request",
                side_effect=run_request_immediately,
            ):
                self.widget.run_prediction()
        finally:
            os.unlink(image.name)

        client.predict.assert_called_once_with(
            image.name,
            "prompt-model",
            confidence=0.25,
            iou=0.45,
            marks=marks,
        )

    def test_each_prompt_change_sends_the_accumulated_marks(self):
        image = tempfile.NamedTemporaryFile(delete=False)
        image.close()
        first_mark = {"type": "point", "data": [12.0, 18.0], "label": 1}
        second_mark = {"type": "point", "data": [20.0, 25.0], "label": 0}
        marks = []
        canvas = SimpleNamespace(
            prompt_marks=marks,
            set_prompt_mode=Mock(),
            clear_prompt_marks=Mock(),
        )
        self.widget.main_window = SimpleNamespace(
            canvas=canvas, file_path=image.name
        )
        self.widget._models = {
            "prompt-model": {"batch_processing_mode": "visual_prompting"}
        }
        self.widget.model_combo.addItem("Prompt model", userData="prompt-model")
        client = Mock()
        client.predict.return_value = ([], 0)

        def run_request_immediately(request, callback, **_kwargs):
            callback(request())

        try:
            with patch.object(self.widget, "_client", return_value=client), patch.object(
                self.widget,
                "_start_request",
                side_effect=run_request_immediately,
            ):
                marks.append(first_mark)
                self.widget._on_prompt_marks_changed(list(marks))
                marks.append(second_mark)
                self.widget._on_prompt_marks_changed(list(marks))
        finally:
            os.unlink(image.name)

        sent_marks = [call.kwargs["marks"] for call in client.predict.call_args_list]
        self.assertEqual(sent_marks, [[first_mark], [first_mark, second_mark]])
        self.assertEqual(canvas.prompt_marks, [first_mark, second_mark])

    def test_each_prompt_change_is_queued_with_accumulated_marks(self):
        image = tempfile.NamedTemporaryFile(delete=False)
        image.close()
        first_mark = {"type": "point", "data": [12.0, 18.0], "label": 1}
        second_mark = {"type": "rectangle", "data": [1.0, 2.0, 8.0, 9.0], "label": 1}
        third_mark = {"type": "point", "data": [22.0, 25.0], "label": 0}
        marks = []
        canvas = SimpleNamespace(
            prompt_marks=marks,
            set_prompt_mode=Mock(),
            clear_prompt_marks=Mock(),
        )
        self.widget.main_window = SimpleNamespace(
            canvas=canvas, file_path=image.name
        )
        self.widget._models = {
            "prompt-model": {"batch_processing_mode": "visual_prompting"}
        }
        self.widget.model_combo.addItem("Prompt model", userData="prompt-model")
        client = Mock()
        detections = [{"label": "object", "points": [(1, 1)] * 4}]
        client.predict.return_value = (detections, 0)
        started_requests = []
        applied_results = []
        self.widget.detections_ready.connect(
            lambda *values: applied_results.append(values)
        )

        def hold_request(request, callback, **kwargs):
            self.widget._prediction_running = True
            started_requests.append((request, callback, kwargs))

        try:
            with patch.object(self.widget, "_client", return_value=client), patch.object(
                self.widget, "_start_request", side_effect=hold_request
            ):
                marks.append(first_mark)
                self.widget._on_prompt_marks_changed(list(marks))
                marks.append(second_mark)
                self.widget._on_prompt_marks_changed(list(marks))

                self.assertEqual(len(started_requests), 1)
                marks.append(third_mark)
                self.widget._on_prompt_marks_changed(list(marks))

                completed_thread = Mock()
                completed_thread.property.return_value = True
                for index in range(2):
                    started_requests[index][1](started_requests[index][0]())
                    with patch.object(
                        self.widget, "sender", return_value=completed_thread
                    ):
                        self.widget._on_request_finished()

                self.assertEqual(len(started_requests), 3)
                started_requests[2][1](started_requests[2][0]())
        finally:
            os.unlink(image.name)

        sent_marks = [call.kwargs["marks"] for call in client.predict.call_args_list]
        self.assertEqual(
            sent_marks,
            [
                [first_mark],
                [first_mark, second_mark],
                [first_mark, second_mark, third_mark],
            ],
        )
        self.assertEqual(
            applied_results,
            [(image.name, detections, False, 0, True)],
        )

    def test_finish_prompt_round_clears_marks_and_preserves_prompt_mode(self):
        prompt_mode = "positive-point"
        canvas = SimpleNamespace(
            prompt_marks=[{"type": "point", "data": [12.0, 18.0], "label": 1}],
            prompt_mode=prompt_mode,
            clear_prompt_marks=Mock(),
            set_prompt_mode=Mock(),
        )
        self.widget.main_window = SimpleNamespace(canvas=canvas)
        self.widget._models = {
            "prompt-model": {"batch_processing_mode": "visual_prompting"}
        }
        self.widget.model_combo.addItem("Prompt model", userData="prompt-model")
        cleared_sessions = []
        self.widget.prompt_session_cleared.connect(
            lambda: cleared_sessions.append(True)
        )

        self.widget._finish_or_run_prediction()

        canvas.clear_prompt_marks.assert_called_once_with()
        canvas.set_prompt_mode.assert_called_once_with(prompt_mode)
        self.assertEqual(cleared_sessions, [True])
        self.assertFalse(self.widget._finish_prompt_session_pending)
        self.assertTrue(self.widget.run_button.isEnabled())

    def test_finish_waits_for_queued_prompt_requests_before_clearing_marks(self):
        prompt_mode = "positive-rectangle"
        canvas = SimpleNamespace(
            prompt_marks=[
                {"type": "rectangle", "data": [1.0, 2.0, 8.0, 9.0], "label": 1}
            ],
            prompt_mode=prompt_mode,
            clear_prompt_marks=Mock(),
            set_prompt_mode=Mock(),
        )
        self.widget.main_window = SimpleNamespace(canvas=canvas)
        self.widget.model_combo.addItem("Prompt model", userData="prompt-model")
        queued_request = {"marks": list(canvas.prompt_marks)}
        self.widget._pending_prompt_predictions = [queued_request]
        self.widget._prediction_running = True
        launched = []
        cleared_sessions = []
        self.widget.prompt_session_cleared.connect(
            lambda: cleared_sessions.append(True)
        )
        completed_thread = Mock()
        completed_thread.property.return_value = True

        self.widget.finish_prompt_session()
        canvas.clear_prompt_marks.assert_not_called()
        canvas.set_prompt_mode.assert_called_once_with(None)
        self.assertFalse(self.widget.run_button.isEnabled())

        with patch.object(self.widget, "_launch_prediction", side_effect=launched.append), patch.object(
            self.widget, "sender", return_value=completed_thread
        ):
            self.widget._on_request_finished()
            self.assertEqual(launched, [queued_request])
            canvas.clear_prompt_marks.assert_not_called()

            self.widget._prediction_running = True
            self.widget._on_request_finished()

        canvas.clear_prompt_marks.assert_called_once_with()
        self.assertEqual(cleared_sessions, [True])
        self.assertEqual(canvas.set_prompt_mode.call_args_list[-1].args, (prompt_mode,))
        self.assertFalse(self.widget._finish_prompt_session_pending)
        self.assertTrue(self.widget.run_button.isEnabled())

    def test_clear_prompts_discards_round_and_cancels_queued_requests(self):
        canvas = SimpleNamespace(
            prompt_marks=[{"type": "point", "data": [12.0, 18.0], "label": 1}],
            clear_prompt_marks=Mock(),
        )
        self.widget.main_window = SimpleNamespace(canvas=canvas)
        queued_request = {"marks": list(canvas.prompt_marks)}
        self.widget._pending_prompt_predictions = [queued_request]
        self.widget._latest_prompt_revision = 4
        cleared_sessions = []
        discarded_sessions = []
        self.widget.prompt_session_cleared.connect(
            lambda: cleared_sessions.append(True)
        )
        self.widget.prompt_session_discarded.connect(
            lambda: discarded_sessions.append(True)
        )

        self.widget.clear_prompts()

        canvas.clear_prompt_marks.assert_called_once_with()
        self.assertEqual(self.widget._pending_prompt_predictions, [])
        self.assertGreaterEqual(self.widget._latest_prompt_revision, 5)
        self.assertEqual(cleared_sessions, [])
        self.assertEqual(discarded_sessions, [True])

    def test_deactivate_prompt_mode_restores_manual_canvas_and_invalidates_pending(self):
        prompt_marks = [{"type": "point", "data": [12.0, 18.0], "label": 1}]
        canvas = SimpleNamespace(
            prompt_marks=prompt_marks,
            set_prompt_mode=Mock(),
        )
        self.widget.main_window = SimpleNamespace(canvas=canvas)
        self.widget._models = {
            "prompt-model": {"batch_processing_mode": "visual_prompting"}
        }
        self.widget.model_combo.addItem("Prompt model", userData="prompt-model")
        self.widget.positive_point_button.setChecked(True)
        self.widget._pending_prompt_predictions = [{"marks": prompt_marks}]
        self.widget._latest_prompt_revision = 2

        self.widget.deactivate_prompt_mode()

        canvas.set_prompt_mode.assert_called_once_with(None)
        self.assertFalse(self.widget.positive_point_button.isChecked())
        self.assertEqual(self.widget._pending_prompt_predictions, [])
        self.assertEqual(self.widget._latest_prompt_revision, 3)
        self.assertEqual(canvas.prompt_marks, prompt_marks)

    def test_prompt_shortcut_exits_manual_mode_before_activating_prompt(self):
        canvas = SimpleNamespace(
            prompt_mode=None,
            drawing=Mock(return_value=True),
            current=object(),
            cancel_current_shape=Mock(),
            set_editing=Mock(),
            restore_cursor=Mock(),
            set_prompt_mode=Mock(),
        )
        main_window = SimpleNamespace(canvas=canvas)

        def exit_manual_drawing_mode():
            canvas.cancel_current_shape()
            canvas.set_editing(True)
            canvas.restore_cursor()

        main_window.exit_manual_drawing_mode = Mock(
            side_effect=exit_manual_drawing_mode
        )
        self.widget.main_window = main_window

        self.widget.set_prompt_mode("positive-point")

        main_window.exit_manual_drawing_mode.assert_called_once_with()
        canvas.set_prompt_mode.assert_called_once_with("positive-point")
        self.assertFalse(self.widget._manual_drawing_active)

    def test_b_exits_manual_mode_instead_of_clearing_prompt_round(self):
        canvas = SimpleNamespace(
            prompt_mode=None,
            drawing=Mock(return_value=False),
            clear_prompt_marks=Mock(),
        )
        main_window = SimpleNamespace(
            canvas=canvas,
            exit_manual_drawing_mode=Mock(),
        )
        self.widget.main_window = main_window
        self.widget.set_manual_drawing_mode(True)
        self.assertTrue(self.widget.clear_prompts_button.text().endswith("(B)"))

        self.widget.handle_b_shortcut()

        main_window.exit_manual_drawing_mode.assert_called_once_with()
        canvas.clear_prompt_marks.assert_not_called()
        self.assertFalse(self.widget._manual_drawing_active)

    def test_b_in_prompt_mode_clears_prompts_and_discards_generated_boxes(self):
        canvas = SimpleNamespace(
            prompt_mode="positive-point",
            # Canvas can remain in CREATE mode while a prompt tool is active.
            drawing=Mock(return_value=True),
            clear_prompt_marks=Mock(),
        )
        main_window = SimpleNamespace(
            canvas=canvas,
            exit_manual_drawing_mode=Mock(),
        )
        self.widget.main_window = main_window
        discarded_sessions = []
        self.widget.prompt_session_discarded.connect(
            lambda: discarded_sessions.append(True)
        )

        self.widget.handle_b_shortcut()

        canvas.clear_prompt_marks.assert_called_once_with()
        main_window.exit_manual_drawing_mode.assert_not_called()
        self.assertEqual(discarded_sessions, [True])

    def test_prediction_result_emits_source_path_and_replace_preference(self):
        received = []
        self.widget.detections_ready.connect(
            lambda *values: received.append(values)
        )
        detections = [{"label": "car", "points": [(0, 0)] * 4}]

        self.widget._on_prediction_loaded(
            ("image.jpg", detections, 2, None),
            replace_existing=True,
        )

        self.assertEqual(
            received, [("image.jpg", detections, True, 2, False)]
        )


if __name__ == "__main__":
    unittest.main()
