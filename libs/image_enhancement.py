# -*- coding: utf-8 -*-
"""Standalone batch image contrast enhancement window."""

import os

import cv2
import numpy as np
from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from libs.canvas import hist_equalize
from libs.stringBundle import get_str


IMAGE_EXTENSIONS = {
    ".bmp",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
class ImageEnhancementWorker(QThread):
    scanStarted = pyqtSignal(int)
    progressChanged = pyqtSignal(int, int, str)
    processingFinished = pyqtSignal(int, int, int, bool, object)

    def __init__(self, source_dir, output_dir, clahe, parent=None):
        super().__init__(parent)
        self.source_dir = os.path.abspath(source_dir)
        self.output_dir = os.path.abspath(output_dir) if output_dir else None
        self.clahe = clahe

    def _image_paths(self):
        paths = []
        output_dir = os.path.normcase(self.output_dir) if self.output_dir else None
        for current_dir, child_dirs, filenames in os.walk(self.source_dir):
            if output_dir:
                child_dirs[:] = [
                    folder for folder in child_dirs
                    if os.path.normcase(os.path.abspath(os.path.join(current_dir, folder))) != output_dir
                ]
            for filename in filenames:
                if os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS:
                    paths.append(os.path.join(current_dir, filename))
        paths.sort(key=lambda path: os.path.normcase(path))
        return paths

    @staticmethod
    def _equalize(image, clahe):
        if image.ndim == 2:
            bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            enhanced = hist_equalize(bgr, clahe=clahe, bgr=True)
            return cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)

        if image.ndim != 3:
            raise ValueError(get_str("imageEnhancementUnsupportedChannels"))

        if image.shape[2] == 4:
            bgr = image[:, :, :3]
            alpha = image[:, :, 3]
            enhanced = hist_equalize(bgr, clahe=clahe, bgr=True)
            return cv2.merge((enhanced[:, :, 0], enhanced[:, :, 1], enhanced[:, :, 2], alpha))

        if image.shape[2] == 3:
            return hist_equalize(image, clahe=clahe, bgr=True)

        if image.shape[2] == 1:
            bgr = cv2.cvtColor(image[:, :, 0], cv2.COLOR_GRAY2BGR)
            enhanced = hist_equalize(bgr, clahe=clahe, bgr=True)
            return cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)

        raise ValueError(get_str("imageEnhancementUnsupportedChannels"))

    @staticmethod
    def _write_image(destination, extension, image):
        success, encoded = cv2.imencode(extension, image)
        if not success:
            raise OSError(get_str("imageEnhancementEncodeFailed"))

        os.makedirs(os.path.dirname(destination), exist_ok=True)
        temporary_path = destination + ".labelimg-tmp"
        try:
            with open(temporary_path, "wb") as output_file:
                output_file.write(encoded.tobytes())
            os.replace(temporary_path, destination)
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)

    def run(self):
        errors = []
        paths = self._image_paths()
        self.scanStarted.emit(len(paths))

        completed = 0
        failed = 0
        cancelled = False
        total = len(paths)

        for index, source_path in enumerate(paths, start=1):
            if self.isInterruptionRequested():
                cancelled = True
                break

            self.progressChanged.emit(index - 1, total, os.path.basename(source_path))
            try:
                image_bytes = np.fromfile(source_path, dtype=np.uint8)
                image = cv2.imdecode(image_bytes, cv2.IMREAD_UNCHANGED)
                if image is None:
                    raise ValueError(get_str("imageEnhancementReadFailed"))

                enhanced = self._equalize(image, self.clahe)
                if self.output_dir:
                    relative_path = os.path.relpath(source_path, self.source_dir)
                    destination = os.path.join(self.output_dir, relative_path)
                else:
                    destination = source_path
                extension = os.path.splitext(source_path)[1].lower()
                self._write_image(destination, extension, enhanced)
                completed += 1
            except Exception as error:  # Keep processing other images in the batch.
                failed += 1
                if len(errors) < 10:
                    errors.append(get_str("imageEnhancementErrorLine").format(
                        os.path.relpath(source_path, self.source_dir), error
                    ))

            self.progressChanged.emit(index, total, os.path.basename(source_path))

        self.processingFinished.emit(completed, failed, total, cancelled, errors)


class ImageEnhancementDialog(QDialog):
    """A self-contained interface for enhancing all images in a directory."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(get_str("imageEnhancementTitle"))
        self.setMinimumSize(640, 535)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setModal(False)
        self._worker = None
        self._running = False

        self.setStyleSheet("""
            QDialog {
                background: #f4f7fb;
                color: #182230;
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
                font-size: 13px;
            }
            QLabel { background: transparent; }
            QFrame#hero {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #e9f1ff, stop:1 #f2f7ff);
                border: 1px solid #dce8fa;
                border-radius: 16px;
            }
            QLabel#eyebrow { color: #4774bb; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
            QLabel#title { color: #162d4b; font-size: 22px; font-weight: 700; }
            QLabel#subtitle { color: #5f7188; font-size: 12px; }
            QFrame#card {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
            QLabel#sectionTitle { color: #26384d; font-size: 13px; font-weight: 700; }
            QLabel#hint, QLabel#status { color: #748398; font-size: 11px; }
            QLineEdit {
                background: #f8fafc;
                border: 1px solid #d9e2ee;
                border-radius: 8px;
                padding: 9px 11px;
                color: #394b60;
                selection-background-color: #2f75d6;
            }
            QLineEdit:focus { border: 1px solid #6da0e8; }
            QCheckBox { color: #26384d; font-weight: 600; spacing: 9px; }
            QCheckBox::indicator { width: 17px; height: 17px; }
            QPushButton {
                min-height: 36px;
                padding: 0 16px;
                border: 1px solid #d6dfeb;
                border-radius: 8px;
                background: #ffffff;
                color: #33465d;
                font-weight: 600;
            }
            QPushButton:hover { background: #f3f7fc; border-color: #b9cbe1; }
            QPushButton:disabled { color: #a5b0bf; background: #f3f5f8; }
            QPushButton#primaryButton {
                border: none;
                color: #ffffff;
                background: #3478d4;
                min-width: 132px;
            }
            QPushButton#primaryButton:hover { background: #2868bf; }
            QPushButton#stopButton { color: #6a7788; min-width: 90px; }
            QProgressBar {
                border: none;
                border-radius: 5px;
                height: 9px;
                background: #e9eef5;
                text-align: center;
            }
            QProgressBar::chunk { border-radius: 5px; background: #4b8fe5; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(13)

        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 17, 20, 17)
        hero_layout.setSpacing(5)
        eyebrow = QLabel(get_str("imageEnhancementEyebrow"))
        eyebrow.setObjectName("eyebrow")
        title = QLabel(get_str("imageEnhancementHeading"))
        title.setObjectName("title")
        subtitle = QLabel(get_str("imageEnhancementSubtitle"))
        subtitle.setObjectName("subtitle")
        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        root.addWidget(hero)

        folder_card = self._make_card(root, get_str("imageEnhancementScope"))
        folder_row = QHBoxLayout()
        folder_row.setSpacing(9)
        self.folder_input = QLineEdit()
        self.folder_input.setReadOnly(True)
        self.folder_input.setPlaceholderText(get_str("imageEnhancementFolderPlaceholder"))
        self.folder_input.setToolTip(get_str("imageEnhancementFolderTooltip"))
        self.folder_input.textChanged.connect(self._update_start_button)
        self.browse_button = QPushButton(get_str("imageEnhancementSelectFolder"))
        self.browse_button.clicked.connect(self._choose_source_folder)
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(self.browse_button)
        folder_card.layout().addLayout(folder_row)
        folder_hint = QLabel(get_str("imageEnhancementFormats"))
        folder_hint.setObjectName("hint")
        folder_card.layout().addWidget(folder_hint)

        options_card = self._make_card(root, get_str("imageEnhancementMethod"))
        self.clahe_checkbox = QCheckBox(get_str("imageEnhancementClahe"))
        self.clahe_checkbox.setChecked(True)
        self.clahe_checkbox.setToolTip(get_str("imageEnhancementClaheTooltip"))
        options_card.layout().addWidget(self.clahe_checkbox)
        options_hint = QLabel(get_str("imageEnhancementMethodHint"))
        options_hint.setObjectName("hint")
        options_card.layout().addWidget(options_hint)

        progress_card = self._make_card(root, get_str("imageEnhancementProgress"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_label = QLabel(get_str("imageEnhancementInitialStatus"))
        self.progress_label.setObjectName("status")
        self.progress_label.setWordWrap(True)
        progress_card.layout().addWidget(self.progress_bar)
        progress_card.layout().addWidget(self.progress_label)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.stop_button = QPushButton(get_str("imageEnhancementClose"))
        self.stop_button.setObjectName("stopButton")
        self.stop_button.clicked.connect(self._stop_or_close)
        self.start_button = QPushButton(get_str("imageEnhancementStart"))
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self._start_enhancement)
        footer.addWidget(self.stop_button)
        footer.addWidget(self.start_button)
        root.addLayout(footer)

        self._update_start_button()

    @staticmethod
    def _make_card(parent_layout, title):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(8)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        parent_layout.addWidget(card)
        return card

    def _choose_source_folder(self):
        initial_dir = self.folder_input.text() or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self,
            get_str("imageEnhancementChooseDialog"),
            initial_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if folder:
            self.folder_input.setText(os.path.normpath(folder))
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(0)
            self.progress_label.setText(get_str("imageEnhancementFolderStatus"))

    def _update_start_button(self, *_):
        self.start_button.setEnabled(not self._running and os.path.isdir(self.folder_input.text()))

    def _start_enhancement(self):
        source_dir = self.folder_input.text()
        if not os.path.isdir(source_dir):
            self._choose_source_folder()
            source_dir = self.folder_input.text()
            if not os.path.isdir(source_dir):
                return

        prompt = QMessageBox(self)
        prompt.setIcon(QMessageBox.Icon.Warning)
        prompt.setWindowTitle(get_str("imageEnhancementConfirmTitle"))
        prompt.setText(get_str("imageEnhancementOverwriteQuestion"))
        output_folder_name = get_str("imageEnhancementOutputFolder")
        prompt.setInformativeText(
            get_str("imageEnhancementOverwriteInfo").format(output_folder_name)
        )
        overwrite_button = prompt.addButton(
            get_str("imageEnhancementOverwriteButton"), QMessageBox.ButtonRole.YesRole
        )
        keep_original_button = prompt.addButton(
            get_str("imageEnhancementKeepButton"), QMessageBox.ButtonRole.NoRole
        )
        prompt.addButton(
            get_str("imageEnhancementCancel"), QMessageBox.ButtonRole.RejectRole
        )
        prompt.setDefaultButton(keep_original_button)
        prompt.exec()

        clicked_button = prompt.clickedButton()
        if clicked_button not in (overwrite_button, keep_original_button):
            return

        output_dir = None
        if clicked_button is keep_original_button:
            output_dir = os.path.join(source_dir, output_folder_name)
            if os.path.isdir(output_dir) and os.listdir(output_dir):
                replace_prompt = QMessageBox(self)
                replace_prompt.setIcon(QMessageBox.Icon.Warning)
                replace_prompt.setWindowTitle(get_str("imageEnhancementExistingTitle"))
                replace_prompt.setText(
                    get_str("imageEnhancementExistingText").format(output_folder_name)
                )
                replace_prompt.setInformativeText(get_str("imageEnhancementExistingInfo"))
                replace_prompt.setStandardButtons(
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
                )
                replace_prompt.setDefaultButton(QMessageBox.StandardButton.Cancel)
                replace_prompt.button(QMessageBox.StandardButton.Yes).setText(
                    get_str("imageEnhancementContinue")
                )
                replace_prompt.button(QMessageBox.StandardButton.Cancel).setText(
                    get_str("imageEnhancementCancel")
                )
                if replace_prompt.exec() != QMessageBox.StandardButton.Yes:
                    return

        self._set_running(True)
        self.progress_bar.setRange(0, 0)
        self.progress_label.setText(get_str("imageEnhancementScanning"))
        self._worker = ImageEnhancementWorker(
            source_dir,
            output_dir,
            self.clahe_checkbox.isChecked(),
            self,
        )
        self._worker.scanStarted.connect(self._on_scan_started)
        self._worker.progressChanged.connect(self._on_progress)
        self._worker.processingFinished.connect(self._on_finished)
        self._worker.start()

    def _set_running(self, running):
        self._running = running
        self.folder_input.setEnabled(not running)
        self.browse_button.setEnabled(not running)
        self.clahe_checkbox.setEnabled(not running)
        self.start_button.setEnabled(not running and os.path.isdir(self.folder_input.text()))
        self.start_button.setText(
            get_str("imageEnhancementProcessing") if running
            else get_str("imageEnhancementStart")
        )
        self.stop_button.setText(
            get_str("imageEnhancementStop") if running
            else get_str("imageEnhancementClose")
        )
        self.stop_button.setEnabled(True)

    def _on_scan_started(self, total):
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(0)
        if total:
            self.progress_label.setText(get_str("imageEnhancementFound").format(total))
        else:
            self.progress_label.setText(get_str("imageEnhancementNoneFound"))

    def _on_progress(self, current, total, filename):
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(current)
        self.progress_label.setText(
            get_str("imageEnhancementRunning").format(current, total, filename)
        )

    def _on_finished(self, completed, failed, total, cancelled, errors):
        self._set_running(False)
        if total == 0:
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(0)
            self.progress_label.setText(get_str("imageEnhancementNoImagesProcess"))
            QMessageBox.information(
                self,
                get_str("imageEnhancementNoImagesTitle"),
                get_str("imageEnhancementNoImages"),
            )
            return

        message = get_str("imageEnhancementSummary").format(completed, failed)
        if cancelled:
            message += "\n" + get_str("imageEnhancementStopped")
        self.progress_label.setText(message.replace("\n", " "))
        if errors:
            message += "\n\n" + get_str("imageEnhancementFailedFiles") + "\n" + "\n".join(errors)
            if failed > len(errors):
                message += "\n" + get_str("imageEnhancementMoreFailed").format(
                    failed - len(errors)
                )
        if failed or cancelled:
            QMessageBox.warning(self, get_str("imageEnhancementCompleteTitle"), message)
        else:
            QMessageBox.information(self, get_str("imageEnhancementCompleteTitle"), message)

    def _stop_or_close(self):
        if self._running:
            self.progress_label.setText(get_str("imageEnhancementStopPending"))
            self.stop_button.setEnabled(False)
            self._worker.requestInterruption()
        else:
            self.accept()

    def stop_for_shutdown(self):
        if self._running and self._worker is not None:
            self._worker.requestInterruption()
            self._worker.wait()
            self._running = False

    def closeEvent(self, event):
        if self._running:
            self._worker.requestInterruption()
            self.progress_label.setText(get_str("imageEnhancementStopPending"))
            event.ignore()
            return
        super().closeEvent(event)
