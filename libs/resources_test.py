"""Tests that generated Qt resources expose the remote UI translations."""

import unittest

from libs.stringBundle import StringBundle


class ResourceTranslationTest(unittest.TestCase):
    def test_remote_panel_has_english_and_simplified_chinese_strings(self):
        english = StringBundle.get_bundle("en")
        chinese = StringBundle.get_bundle("zh-CN")

        self.assertEqual(
            english.get_string("remoteRunDetection"), "Run remote detection"
        )
        self.assertEqual(
            chinese.get_string("remoteRunDetection"), "运行远程检测"
        )
        self.assertEqual(
            chinese.get_string("remoteDetectionsFound").format(3, 1),
            "已将 3 个结果转换为矩形框；已跳过 1 个无效结果。",
        )
        self.assertIn("立即预测", chinese.get_string("remotePromptInstructions"))
        self.assertEqual(
            english.get_string("remotePromptFinished"),
            "Prompt round finished. Add prompts for the next object.",
        )
        self.assertEqual(
            chinese.get_string("remotePromptFinished"),
            "本轮提示已结束，可继续标注下一个物体。",
        )
        self.assertIn("Shift+R", chinese.get_string("remotePromptModeInactive"))
        self.assertEqual(
            chinese.get_string("remoteExitManualDrawing"), "退出手动画框 (B)"
        )


if __name__ == "__main__":
    unittest.main()
