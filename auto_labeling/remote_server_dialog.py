"""Settings and lifecycle controls for the remote annotation services."""

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from auto_labeling.qt import new_icon
from auto_labeling.remote_client import RemoteInferenceClient
from auto_labeling.remote_control_client import RemoteControlClient
from auto_labeling.style import (
    get_highlight_button_style,
    get_lineedit_style,
    get_normal_button_style,
)
from libs.stringBundle import get_str


_ACTIVE_DIALOG_THREADS = set()


def _text(key, *values):
    value = get_str(key)
    return value.format(*values) if values else value


class _DialogRequestThread(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, request):
        super().__init__()
        self.request = request

    def run(self):
        try:
            self.succeeded.emit(self.request())
        except Exception as exc:  # show connection errors in the dialog
            self.failed.emit(str(exc))


class RemoteServerDialog(QDialog):
    """Edit inference settings and remotely control the Uvicorn process."""

    def __init__(
        self,
        parent=None,
        default_url="http://192.168.31.5:8000",
        default_api_key="",
        default_control_url="http://192.168.31.5:8001",
        default_control_api_key="",
    ):
        super().__init__(parent)
        self.setWindowTitle(get_str("remoteServerDialogTitle"))
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setMinimumWidth(570)
        self._request_running = False

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        inference_group = QGroupBox(get_str("remoteServerDialogInferenceGroup"))
        inference_layout = QVBoxLayout(inference_group)
        inference_layout.setSpacing(7)
        inference_layout.addWidget(QLabel(get_str("remoteServerDialogUrlLabel")))

        self.url_input = QLineEdit(default_url)
        self.url_input.setStyleSheet(get_lineedit_style())
        self.url_input.setPlaceholderText(
            get_str("remoteServerDialogUrlPlaceholder")
        )
        self.url_input.setToolTip(get_str("remoteServerDialogUrlTooltip"))
        inference_layout.addWidget(self.url_input)

        inference_layout.addWidget(
            QLabel(get_str("remoteServerDialogApiKeyLabel"))
        )
        api_key_container = QHBoxLayout()
        self.api_key_input = QLineEdit(default_api_key)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText(
            get_str("remoteServerDialogApiKeyPlaceholder")
        )
        self.api_key_input.setStyleSheet(get_lineedit_style())
        self.api_key_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        button_size = self.api_key_input.sizeHint().height()
        self.toggle_visibility_btn = QPushButton()
        self.toggle_visibility_btn.setCheckable(True)
        self.toggle_visibility_btn.setFixedSize(button_size, button_size)
        self.toggle_visibility_btn.setStyleSheet(get_normal_button_style())
        self.toggle_visibility_btn.clicked.connect(
            self.toggle_api_key_visibility
        )
        self._update_visibility_button(False)
        api_key_container.addWidget(self.api_key_input)
        api_key_container.addWidget(self.toggle_visibility_btn)
        inference_layout.addLayout(api_key_container)
        layout.addWidget(inference_group)

        control_group = QGroupBox(get_str("remoteServerDialogControlGroup"))
        control_layout = QVBoxLayout(control_group)
        control_layout.setSpacing(7)
        control_layout.addWidget(
            QLabel(get_str("remoteServerDialogControlUrlLabel"))
        )
        self.control_url_input = QLineEdit(default_control_url)
        self.control_url_input.setStyleSheet(get_lineedit_style())
        self.control_url_input.setPlaceholderText(
            get_str("remoteServerDialogControlUrlPlaceholder")
        )
        self.control_url_input.setToolTip(
            get_str("remoteServerDialogControlUrlTooltip")
        )
        control_layout.addWidget(self.control_url_input)
        control_layout.addWidget(
            QLabel(get_str("remoteServerDialogControlTokenLabel"))
        )
        self.control_api_key_input = QLineEdit(default_control_api_key)
        self.control_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.control_api_key_input.setPlaceholderText(
            get_str("remoteServerDialogControlTokenPlaceholder")
        )
        self.control_api_key_input.setStyleSheet(get_lineedit_style())
        control_layout.addWidget(self.control_api_key_input)

        action_grid = QGridLayout()
        action_grid.setHorizontalSpacing(8)
        action_grid.setVerticalSpacing(7)
        self.test_connection_button = QPushButton(
            get_str("remoteServerDialogTestConnection")
        )
        self.test_connection_button.setStyleSheet(get_normal_button_style())
        self.test_connection_button.clicked.connect(self.test_connection)
        self.start_server_button = QPushButton(
            get_str("remoteServerDialogStartServer")
        )
        self.start_server_button.setStyleSheet(get_highlight_button_style())
        self.start_server_button.clicked.connect(
            lambda: self._run_control_action("start")
        )
        self.stop_server_button = QPushButton(
            get_str("remoteServerDialogStopServer")
        )
        self.stop_server_button.setStyleSheet(get_normal_button_style())
        self.stop_server_button.clicked.connect(
            lambda: self._run_control_action("stop")
        )
        self.status_server_button = QPushButton(
            get_str("remoteServerDialogRefreshStatus")
        )
        self.status_server_button.setStyleSheet(get_normal_button_style())
        self.status_server_button.clicked.connect(
            lambda: self._run_control_action("status")
        )
        for button in (
            self.test_connection_button,
            self.start_server_button,
            self.stop_server_button,
            self.status_server_button,
        ):
            button.setMinimumHeight(30)
        action_grid.addWidget(self.test_connection_button, 0, 0)
        action_grid.addWidget(self.status_server_button, 0, 1)
        action_grid.addWidget(self.start_server_button, 1, 0)
        action_grid.addWidget(self.stop_server_button, 1, 1)
        action_grid.setColumnStretch(0, 1)
        action_grid.setColumnStretch(1, 1)
        control_layout.addLayout(action_grid)

        self.status_label = QLabel(
            get_str("remoteServerDialogIdleStatus"), control_group
        )
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #66758a; padding: 2px;")
        control_layout.addWidget(self.status_label)
        layout.addWidget(control_group)

        button_container = QHBoxLayout()
        button_container.addStretch()
        cancel_button = QPushButton(get_str("remoteServerDialogCancel"))
        cancel_button.setStyleSheet(get_normal_button_style())
        cancel_button.clicked.connect(self.reject)
        button_container.addWidget(cancel_button)
        ok_button = QPushButton(get_str("remoteServerDialogOK"))
        ok_button.setStyleSheet(get_highlight_button_style())
        ok_button.clicked.connect(self.accept)
        button_container.addWidget(ok_button)
        layout.addLayout(button_container)

    def _update_visibility_button(self, checked):
        """Updates the icon or text of the inference API key button."""
        show_text = get_str("remoteServerDialogShow")
        hide_text = get_str("remoteServerDialogHide")
        if checked:
            try:
                self.toggle_visibility_btn.setIcon(QIcon(new_icon("eye", "svg")))
                self.toggle_visibility_btn.setText("")
                self.toggle_visibility_btn.setToolTip(hide_text)
            except Exception:  # icon packs may omit the optional eye artwork
                self.toggle_visibility_btn.setIcon(QIcon())
                self.toggle_visibility_btn.setText(hide_text)
                self.toggle_visibility_btn.setToolTip("")
        else:
            try:
                self.toggle_visibility_btn.setIcon(
                    QIcon(new_icon("eye-off", "svg"))
                )
                self.toggle_visibility_btn.setText("")
                self.toggle_visibility_btn.setToolTip(show_text)
            except Exception:  # icon packs may omit the optional eye artwork
                self.toggle_visibility_btn.setIcon(QIcon())
                self.toggle_visibility_btn.setText(show_text)
                self.toggle_visibility_btn.setToolTip("")

    def toggle_api_key_visibility(self, checked):
        if checked:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._update_visibility_button(checked)

    def get_server_url(self):
        return self.url_input.text().strip()

    def get_api_key(self):
        return self.api_key_input.text().strip()

    def get_control_server_url(self):
        return self.control_url_input.text().strip()

    def get_control_api_key(self):
        return self.control_api_key_input.text().strip()

    def _set_operation_buttons_enabled(self, enabled):
        for button in (
            self.test_connection_button,
            self.start_server_button,
            self.stop_server_button,
            self.status_server_button,
        ):
            button.setEnabled(enabled)

    def _start_request(self, request, success_callback):
        if self._request_running:
            return
        self._request_running = True
        self._set_operation_buttons_enabled(False)
        self.status_label.setText(get_str("remoteServerDialogWorking"))
        self.status_label.setStyleSheet("color: #66758a; padding: 2px;")
        thread = _DialogRequestThread(request)
        _ACTIVE_DIALOG_THREADS.add(thread)
        thread.succeeded.connect(success_callback)
        thread.failed.connect(self._on_request_failed)
        thread.finished.connect(self._on_request_finished)
        thread.finished.connect(lambda: _ACTIVE_DIALOG_THREADS.discard(thread))
        thread.start()

    def _on_request_finished(self):
        self._request_running = False
        self._set_operation_buttons_enabled(True)

    def _on_request_failed(self, message):
        self.status_label.setText(
            _text("remoteServerDialogOperationFailed", message)
        )
        self.status_label.setStyleSheet("color: #b42318; padding: 2px;")

    def _run_control_action(self, action):
        url = self.get_control_server_url()
        token = self.get_control_api_key()

        def request():
            client = RemoteControlClient(url, api_key=token)
            if action == "start":
                result = client.start()
            elif action == "stop":
                result = client.stop()
            else:
                result = client.status()
            return action, result

        self._start_request(request, self._on_control_action_succeeded)

    def _on_control_action_succeeded(self, result):
        action, data = result
        status = data.get("status", "unknown")
        message_keys = {
            "start": "remoteServerDialogStartAccepted",
            "stop": "remoteServerDialogStopCompleted",
            "status": "remoteServerDialogStatusResult",
        }
        self.status_label.setText(
            _text(message_keys[action], status)
        )
        self.status_label.setStyleSheet("color: #237a48; padding: 2px;")

    def test_connection(self):
        inference_url = self.get_server_url()
        inference_key = self.get_api_key()
        control_url = self.get_control_server_url()
        control_key = self.get_control_api_key()

        def request():
            result = {"inference": None, "control": None, "control_status": None}
            try:
                models = RemoteInferenceClient(
                    inference_url, api_key=inference_key, timeout=10
                ).list_models()
                result["inference"] = {"ok": True, "count": len(models)}
            except Exception as exc:
                result["inference"] = {"ok": False, "error": str(exc)}
            try:
                control = RemoteControlClient(
                    control_url, api_key=control_key, timeout=5
                )
                control.health()
                result["control"] = {"ok": True}
                if control_key:
                    try:
                        result["control_status"] = {
                            "ok": True,
                            "status": control.status().get("status", "unknown"),
                        }
                    except Exception as exc:
                        result["control_status"] = {
                            "ok": False,
                            "error": str(exc),
                        }
                else:
                    result["control_status"] = {"ok": False, "missing_token": True}
            except Exception as exc:
                result["control"] = {"ok": False, "error": str(exc)}
            return result

        self._start_request(request, self._on_connection_test_succeeded)

    def _on_connection_test_succeeded(self, result):
        messages = []
        inference = result.get("inference") or {"ok": False, "error": ""}
        if inference.get("ok"):
            messages.append(
                _text("remoteServerDialogInferenceReachable", inference["count"])
            )
        else:
            messages.append(
                _text(
                    "remoteServerDialogInferenceUnreachable",
                    inference.get("error", ""),
                )
            )

        control = result.get("control") or {"ok": False, "error": ""}
        if control.get("ok"):
            messages.append(get_str("remoteServerDialogControlReachable"))
        else:
            messages.append(
                _text(
                    "remoteServerDialogControlUnreachable",
                    control.get("error", ""),
                )
            )

        control_status = result.get("control_status") or {}
        if control_status.get("ok"):
            messages.append(
                _text(
                    "remoteServerDialogStatusResult",
                    control_status.get("status", "unknown"),
                )
            )
        elif control_status.get("missing_token"):
            messages.append(get_str("remoteServerDialogTokenRequiredForControl"))
        elif control_status:
            messages.append(
                _text(
                    "remoteServerDialogControlAuthFailed",
                    control_status.get("error", ""),
                )
            )

        self.status_label.setText("\n".join(messages))
        self.status_label.setStyleSheet(
            "color: {}; padding: 2px;".format(
                "#237a48"
                if inference.get("ok") and control.get("ok")
                else "#b54708"
            )
        )
