"""Tests for temporary interactive prompts on the labelImg canvas."""

import os
import unittest

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from libs.canvas import CURSOR_DEFAULT, CURSOR_DRAW, CURSOR_POINT, Canvas


class CanvasPromptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.canvas = Canvas()
        self.canvas.resize(100, 100)
        self.canvas.load_pixmap(QPixmap(100, 100))
        self.canvas.show()
        self.app.processEvents()

    def tearDown(self):
        self.canvas.close()
        self.canvas.deleteLater()
        self.app.processEvents()

    def test_point_tool_adds_positive_or_negative_point_on_click(self):
        self.canvas.set_prompt_mode("positive-point")
        QTest.mouseClick(
            self.canvas,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(20, 30),
        )
        self.canvas.set_prompt_mode("negative-point")
        QTest.mouseClick(
            self.canvas,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(60, 70),
        )

        self.assertEqual(
            self.canvas.prompt_marks,
            [
                {"type": "point", "data": [20.0, 30.0], "label": 1},
                {"type": "point", "data": [60.0, 70.0], "label": 0},
            ],
        )
        self.assertEqual(self.canvas.shapes, [])

    def test_rectangle_tool_adds_normalized_prompt_on_drag(self):
        self.canvas.set_prompt_mode("positive-rectangle")
        QTest.mousePress(
            self.canvas,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(10, 10),
        )
        QTest.mouseRelease(
            self.canvas,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(40, 45),
        )
        self.canvas.set_prompt_mode("negative-rectangle")
        QTest.mousePress(
            self.canvas,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(70, 80),
        )
        QTest.mouseMove(self.canvas, QPoint(20, 30))
        QTest.mouseRelease(
            self.canvas,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(20, 30),
        )

        self.assertEqual(
            self.canvas.prompt_marks,
            [
                {
                    "type": "rectangle",
                    "data": [10.0, 10.0, 40.0, 45.0],
                    "label": 1,
                },
                {
                    "type": "rectangle",
                    "data": [20.0, 30.0, 70.0, 80.0],
                    "label": 0,
                }
            ],
        )
        self.assertEqual(self.canvas.shapes, [])

    def test_right_mouse_release_requests_prompt_round_finish(self):
        self.canvas.set_prompt_mode("positive-point")
        finish_requests = []
        self.canvas.promptFinishRequested.connect(
            lambda: finish_requests.append(True)
        )

        QTest.mousePress(
            self.canvas,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(20, 30),
        )
        self.assertEqual(finish_requests, [])
        QTest.mouseRelease(
            self.canvas,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(20, 30),
        )

        self.assertEqual(finish_requests, [True])
        self.assertEqual(self.canvas.prompt_marks, [])

    def test_clear_prompts_keeps_saved_shapes_and_image_change_resets_mode(self):
        saved_shape = object()
        self.canvas.shapes = [saved_shape]
        self.canvas.add_prompt_point(QPointF(10, 10), 1)

        self.canvas.clear_prompt_marks()

        self.assertEqual(self.canvas.prompt_marks, [])
        self.assertEqual(self.canvas.shapes, [saved_shape])
        self.canvas.set_prompt_mode("positive-point")
        self.canvas.load_pixmap(QPixmap(100, 100))
        self.assertIsNone(self.canvas.prompt_mode)
        self.assertEqual(self.canvas.prompt_marks, [])

    def test_entering_prompt_mode_uses_prompt_cursor_not_manual_crosshair(self):
        self.canvas.set_editing(False)
        self.canvas._cursor = CURSOR_DRAW
        self.assertEqual(self.canvas._cursor, CURSOR_DRAW)

        self.canvas.set_prompt_mode("positive-point")

        self.assertEqual(self.canvas._cursor, CURSOR_POINT)
        self.assertEqual(self.canvas.cursor().shape(), CURSOR_POINT)

    def test_returning_to_edit_mode_resets_manual_cursor(self):
        self.canvas.set_editing(False)
        self.canvas._cursor = CURSOR_DRAW
        self.canvas.set_editing(True)

        self.assertFalse(self.canvas.drawing())
        self.assertEqual(self.canvas._cursor, CURSOR_DEFAULT)

    def test_cancel_current_shape_discards_only_the_unfinished_shape(self):
        self.canvas.set_editing(False)
        self.canvas.new_shape(QPointF(12, 18))

        self.assertTrue(self.canvas.cancel_current_shape())
        self.assertIsNone(self.canvas.current)
        self.assertEqual(self.canvas.line.points, [])
        self.assertFalse(self.canvas.cancel_current_shape())


if __name__ == "__main__":
    unittest.main()
