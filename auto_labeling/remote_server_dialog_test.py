"""Tests for the localized remote server settings dialog."""

import unittest

from PyQt6.QtWidgets import QApplication

from auto_labeling.remote_server_dialog import RemoteServerDialog
from libs.stringBundle import get_str


class RemoteServerDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_values_are_trimmed_and_api_key_is_masked(self):
        dialog = RemoteServerDialog(
            default_url=" http://example.test:8000 ",
            default_api_key="secret",
            default_control_url=" http://example.test:8001 ",
            default_control_api_key="control-secret",
        )
        self.assertEqual(dialog.get_server_url(), "http://example.test:8000")
        self.assertEqual(dialog.get_api_key(), "secret")
        self.assertEqual(
            dialog.get_control_server_url(), "http://example.test:8001"
        )
        self.assertEqual(dialog.get_control_api_key(), "control-secret")
        self.assertEqual(
            dialog.api_key_input.echoMode(),
            dialog.api_key_input.EchoMode.Password,
        )
        self.assertEqual(
            dialog.control_api_key_input.echoMode(),
            dialog.control_api_key_input.EchoMode.Password,
        )
        dialog.close()

    def test_dialog_uses_project_translation_bundle(self):
        dialog = RemoteServerDialog()
        self.assertEqual(
            dialog.windowTitle(), get_str("remoteServerDialogTitle")
        )
        self.assertEqual(
            dialog.url_input.placeholderText(),
            get_str("remoteServerDialogUrlPlaceholder"),
        )
        self.assertEqual(
            dialog.control_url_input.placeholderText(),
            get_str("remoteServerDialogControlUrlPlaceholder"),
        )
        self.assertEqual(
            dialog.test_connection_button.text(),
            get_str("remoteServerDialogTestConnection"),
        )
        dialog.close()

    def test_control_server_defaults_to_separate_management_port(self):
        dialog = RemoteServerDialog()
        self.assertEqual(
            dialog.get_server_url(), "http://192.168.31.5:8000"
        )
        self.assertEqual(
            dialog.get_control_server_url(), "http://192.168.31.5:8001"
        )
        self.assertEqual(dialog.get_control_api_key(), "")
        dialog.close()


if __name__ == "__main__":
    unittest.main()
