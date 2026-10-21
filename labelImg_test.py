"""Tests for applying remote detections to the labelImg canvas."""

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QComboBox, QMainWindow, QMenu

from labelImg import MainWindow
from libs.shape import Shape


class _FakeCanvas:
    def __init__(self, shapes=None):
        self.shapes = list(shapes or [])

    @staticmethod
    def snap_point_to_canvas(x, y):
        return x, y, False

    def load_shapes(self, shapes):
        self.shapes = list(shapes)


class _FakeStatusBar:
    def __init__(self):
        self.message = None

    def showMessage(self, message, _delay):
        self.message = message


class _FakeMainWindow:
    def __init__(self, file_path, shapes=None):
        self.file_path = file_path
        self.image = object()
        self.canvas = _FakeCanvas(shapes)
        self.shapes_to_items = {shape: object() for shape in self.canvas.shapes}
        self._remote_prompt_shapes = []
        self.label_hist = []
        self.default_label = "target"
        self.display_label_option = type(
            "DisplayOption", (), {"isChecked": lambda _self: True}
        )()
        self.status_bar = _FakeStatusBar()
        self.dirty = False

    def add_label(self, shape):
        self.shapes_to_items[shape] = object()

    def remove_label(self, shape):
        self.shapes_to_items.pop(shape, None)

    def update_combo_box(self):
        pass

    def set_dirty(self):
        self.dirty = True

    def statusBar(self):
        return self.status_bar


class ApplyRemotePredictionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        self.image_path = os.path.abspath(handle.name)

    def tearDown(self):
        os.unlink(self.image_path)

    @staticmethod
    def _detection(label="car"):
        return {
            "label": label,
            "points": [(10, 20), (30, 20), (30, 40), (10, 40)],
        }

    def test_remote_rectangle_is_added_as_a_closed_labelimg_shape(self):
        window = _FakeMainWindow(self.image_path)

        MainWindow.apply_remote_predictions(
            window, self.image_path, [self._detection()], False, 0
        )

        self.assertEqual(len(window.canvas.shapes), 1)
        shape = window.canvas.shapes[0]
        self.assertIsInstance(shape, Shape)
        self.assertEqual(shape.label, "car")
        self.assertEqual(len(shape.points), 4)
        self.assertTrue(shape.is_closed())
        self.assertEqual(window.label_hist, ["car"])
        self.assertTrue(window.dirty)

    def test_generic_remote_object_label_uses_current_default_class(self):
        window = _FakeMainWindow(self.image_path)
        detection = self._detection("AUTOLABEL_OBJECT")

        MainWindow.apply_remote_predictions(
            window, self.image_path, [detection], False, 0
        )

        self.assertEqual(window.canvas.shapes[0].label, "target")
        self.assertEqual(window.label_hist, ["target"])

    def test_replace_option_clears_existing_shapes_before_adding_results(self):
        old_shape = Shape(label="old")
        window = _FakeMainWindow(self.image_path, [old_shape])

        MainWindow.apply_remote_predictions(
            window, self.image_path, [self._detection()], True, 0
        )

        self.assertEqual([shape.label for shape in window.canvas.shapes], ["car"])
        self.assertNotIn(old_shape, window.shapes_to_items)

    def test_stale_result_for_previous_image_is_ignored(self):
        window = _FakeMainWindow(self.image_path)
        another_image = self.image_path + ".previous"

        MainWindow.apply_remote_predictions(
            window, another_image, [self._detection()], False, 0
        )

        self.assertEqual(window.canvas.shapes, [])
        self.assertFalse(window.dirty)

    def test_invalid_clipped_result_does_not_delete_existing_shapes(self):
        old_shape = Shape(label="old")
        window = _FakeMainWindow(self.image_path, [old_shape])
        invalid_detection = {
            "label": "car",
            "points": [(5, 5), (5, 5), (5, 5), (5, 5)],
        }

        MainWindow.apply_remote_predictions(
            window, self.image_path, [invalid_detection], True, 0
        )

        self.assertEqual(window.canvas.shapes, [old_shape])
        self.assertFalse(window.dirty)

    def test_new_prompt_result_replaces_only_the_previous_prompt_result(self):
        user_shape = Shape(label="existing")
        window = _FakeMainWindow(self.image_path, [user_shape])

        MainWindow.apply_remote_predictions(
            window, self.image_path, [self._detection("first")], False, 0, True
        )
        first_prompt_shape = window._remote_prompt_shapes[0]
        MainWindow.apply_remote_predictions(
            window, self.image_path, [self._detection("second")], False, 0, True
        )

        self.assertEqual(
            [shape.label for shape in window.canvas.shapes], ["existing", "second"]
        )
        self.assertNotIn(first_prompt_shape, window.shapes_to_items)
        self.assertEqual(
            [shape.label for shape in window._remote_prompt_shapes], ["second"]
        )

    def test_empty_prompt_result_removes_previous_prompt_shapes_only(self):
        user_shape = Shape(label="existing")
        window = _FakeMainWindow(self.image_path, [user_shape])
        MainWindow.apply_remote_predictions(
            window, self.image_path, [self._detection()], False, 0, True
        )

        MainWindow.apply_remote_predictions(
            window, self.image_path, [], False, 0, True
        )

        self.assertEqual(window.canvas.shapes, [user_shape])
        self.assertEqual(window._remote_prompt_shapes, [])
        self.assertIn(user_shape, window.shapes_to_items)

    def test_discard_prompt_round_removes_its_boxes_and_keeps_manual_shapes(self):
        manual_shape = Shape(label="manual")
        prompt_shape = Shape(label="remote")
        window = _FakeMainWindow(self.image_path, [manual_shape, prompt_shape])
        window._remote_prompt_shapes = [prompt_shape]

        MainWindow._discard_remote_prompt_session(window)

        self.assertEqual(window.canvas.shapes, [manual_shape])
        self.assertNotIn(prompt_shape, window.shapes_to_items)
        self.assertIn(manual_shape, window.shapes_to_items)
        self.assertEqual(window._remote_prompt_shapes, [])
        self.assertTrue(window.dirty)


class _PresetShortcutWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.label_hist = ["ok", "cq", "bd", "ng1", "ng2"]
        self.default_label = self.label_hist[0]
        self.default_label_combo_box = SimpleNamespace(cb=QComboBox(self))
        self.default_label_combo_box.cb.addItems(self.label_hist)
        self.default_label_combo_box.cb.currentIndexChanged.connect(
            self.default_label_combo_selection_changed
        )
        self.setCentralWidget(self.default_label_combo_box.cb)
        MainWindow._init_default_label_shortcuts(self)

    def set_default_label_by_index(self, index):
        MainWindow.set_default_label_by_index(self, index)

    def default_label_combo_selection_changed(self, index):
        MainWindow.default_label_combo_selection_changed(self, index)


class PresetLabelShortcutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_number_shortcut_selects_predefined_label_by_class_index(self):
        window = _PresetShortcutWindow()
        window.show()
        window.activateWindow()
        window.default_label_combo_box.cb.setFocus()
        self.app.processEvents()

        QTest.keyClick(window.default_label_combo_box.cb, Qt.Key.Key_3)
        self.app.processEvents()

        self.assertEqual(window.default_label_combo_box.cb.currentIndex(), 2)
        self.assertEqual(window.default_label, "bd")
        window.close()

    def test_existing_selected_shape_shortcuts_move_to_alt_numbers(self):
        window = QMainWindow()
        window.label_hist = ["class-{}".format(index) for index in range(1, 10)]
        window.fast_change_label = Mock()
        window.menus = SimpleNamespace(edit=QMenu(window))

        MainWindow._initCategory(window)

        self.assertEqual(
            [action.shortcut().toString() for action in window.changeCategoryActions],
            ["Alt+{}".format(index) for index in range(1, 10)],
        )
        window.close()


class FitScaleUsesCanvasViewportTest(unittest.TestCase):
    @staticmethod
    def _window(viewport_width, viewport_height, image_width, image_height):
        viewport = SimpleNamespace(
            width=lambda: viewport_width,
            height=lambda: viewport_height,
        )
        pixmap = SimpleNamespace(
            width=lambda: image_width,
            height=lambda: image_height,
        )
        return SimpleNamespace(
            scroll_area=SimpleNamespace(viewport=lambda: viewport),
            canvas=SimpleNamespace(pixmap=pixmap),
        )

    def test_fit_window_uses_viewport_below_remote_annotation_panel(self):
        window = self._window(1000, 500, 1600, 1200)

        scale = MainWindow.scale_fit_window(window)

        self.assertAlmostEqual(scale, 498 / 1200)

    def test_fit_width_uses_viewport_width(self):
        window = self._window(1000, 500, 1600, 1200)

        scale = MainWindow.scale_fit_width(window)

        self.assertAlmostEqual(scale, 998 / 1600)


class RemoteAnnotationSignalConnectionTest(unittest.TestCase):
    def test_connecting_remote_widget_does_not_require_canvas_loading_api(self):
        connected_slots = []
        prediction_slot = lambda *_args: None
        finish_prompt_slot = lambda: None
        widget = SimpleNamespace(
            detections_ready=SimpleNamespace(connect=connected_slots.append),
            prompt_session_cleared=SimpleNamespace(connect=connected_slots.append),
            prompt_session_discarded=SimpleNamespace(connect=connected_slots.append),
            _finish_or_run_prediction=finish_prompt_slot,
        )
        canvas = SimpleNamespace(
            promptFinishRequested=SimpleNamespace(connect=connected_slots.append)
        )
        # The normal labelImg Canvas has no set_loading method.
        window = SimpleNamespace(
            canvas=canvas,
            apply_remote_predictions=prediction_slot,
            _reset_remote_prompt_session=lambda: None,
            _discard_remote_prompt_session=lambda: None,
        )

        MainWindow._initAiConnect(window, widget)

        self.assertEqual(
            connected_slots,
            [
                prediction_slot,
                window._reset_remote_prompt_session,
                window._discard_remote_prompt_session,
                finish_prompt_slot,
            ],
        )


class ManualDrawingDisablesRemotePromptTest(unittest.TestCase):
    def test_w_manual_draw_action_deactivates_prompt_mode(self):
        class _Action:
            def __init__(self):
                self.enabled = True

            def setEnabled(self, enabled):
                self.enabled = enabled

        canvas = SimpleNamespace(set_editing=Mock())
        ai_widget = SimpleNamespace(deactivate_prompt_mode=Mock())
        ai_widget.set_manual_drawing_mode = Mock()
        window = SimpleNamespace(
            beginner=lambda: True,
            canvas=canvas,
            actions=SimpleNamespace(create=_Action()),
            ai_widget=ai_widget,
        )

        MainWindow.create_shape(window)

        ai_widget.deactivate_prompt_mode.assert_called_once_with()
        ai_widget.set_manual_drawing_mode.assert_called_once_with(True)
        canvas.set_editing.assert_called_once_with(False)
        self.assertFalse(window.actions.create.enabled)

    def test_w_advanced_create_mode_deactivates_prompt_mode(self):
        ai_widget = SimpleNamespace(
            deactivate_prompt_mode=Mock(),
            set_manual_drawing_mode=Mock(),
        )
        window = SimpleNamespace(
            advanced=lambda: True,
            ai_widget=ai_widget,
            toggle_draw_mode=Mock(),
        )

        MainWindow.set_create_mode(window)

        ai_widget.deactivate_prompt_mode.assert_called_once_with()
        ai_widget.set_manual_drawing_mode.assert_called_once_with(True)
        window.toggle_draw_mode.assert_called_once_with(False)

    def test_b_exit_manual_mode_returns_beginner_canvas_to_selection(self):
        class _Action:
            def __init__(self):
                self.enabled = False

            def setEnabled(self, enabled):
                self.enabled = enabled

        canvas = SimpleNamespace(
            current=None,
            set_editing=Mock(),
            restore_cursor=Mock(),
        )
        ai_widget = SimpleNamespace(set_manual_drawing_mode=Mock())
        window = SimpleNamespace(
            beginner=lambda: True,
            canvas=canvas,
            actions=SimpleNamespace(create=_Action()),
            ai_widget=ai_widget,
        )

        MainWindow.exit_manual_drawing_mode(window)

        canvas.set_editing.assert_called_once_with(True)
        canvas.restore_cursor.assert_called_once_with()
        self.assertTrue(window.actions.create.enabled)
        ai_widget.set_manual_drawing_mode.assert_called_once_with(False)

    def test_prompt_switch_cancels_unfinished_manual_shape_in_advanced_mode(self):
        canvas = SimpleNamespace(
            current=object(),
            cancel_current_shape=Mock(),
        )
        ai_widget = SimpleNamespace(set_manual_drawing_mode=Mock())
        window = SimpleNamespace(
            canvas=canvas,
            beginner=lambda: False,
            set_edit_mode=Mock(),
            ai_widget=ai_widget,
        )

        MainWindow.exit_manual_drawing_mode(window)

        canvas.cancel_current_shape.assert_called_once_with()
        window.set_edit_mode.assert_called_once_with()
        ai_widget.set_manual_drawing_mode.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()
