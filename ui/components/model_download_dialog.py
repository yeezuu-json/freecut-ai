"""Lazy model-download dialog.

Shown whenever the user attempts an action that requires a local AI model
that has not yet been downloaded.  The dialog:

  1. Explains what the model is and roughly how large it is.
  2. Asks the user to confirm the download.
  3. Shows a progress bar while downloading.
  4. Returns ``True`` (model ready) or ``False`` (cancelled / failed).

Static helper
-------------
    ok = ModelDownloadDialog.ensure(provider, model_name, parent=self)
    if not ok:
        return   # user declined
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.logger import get_logger
from services.model_manager import ModelManager
from workers.model_download_worker import ModelDownloadWorker

logger = get_logger(__name__)

# Rough size hints displayed to the user (update as needed)
_SIZE_HINTS: dict[str, str] = {
    "tiny":                                "~75 MB",
    "base":                                "~145 MB",
    "small":                               "~465 MB",
    "medium":                              "~1.5 GB",
    "large-v3":                            "~3.1 GB",
    "facebook/nllb-200-distilled-600M":    "~2.4 GB",
    "facebook/nllb-200-distilled-1.3B":    "~5.3 GB",
}

_PROVIDER_LABEL: dict[str, str] = {
    "local":      "Whisper speech-recognition",
    "local_nllb": "NLLB translation",
}

_QSS = """
QDialog {
    background-color: #1a1f2e;
    color: #e2e8f0;
}
QLabel {
    color: #cbd5e1;
    font-size: 13px;
}
QLabel#title {
    color: #f1f5f9;
    font-size: 15px;
    font-weight: 700;
}
QLabel#hint {
    color: #64748b;
    font-size: 11px;
    font-style: italic;
}
QProgressBar {
    background-color: #374151;
    border-radius: 5px;
    height: 12px;
    text-align: center;
    color: #ffffff;
    font-size: 9px;
    font-weight: 700;
}
QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 5px;
}
QPushButton {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 600;
    min-width: 80px;
}
QPushButton:hover { background-color: #2563eb; }
QPushButton#cancelBtn {
    background-color: #374151;
}
QPushButton#cancelBtn:hover { background-color: #4b5563; }
"""


class ModelDownloadDialog(QDialog):
    """Modal dialog for downloading a local AI model.

    Use the static :meth:`ensure` method instead of instantiating directly.
    """

    def __init__(
        self,
        provider: str,
        model_name: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.provider   = provider
        self.model_name = model_name
        self._success   = False
        self._thread: Optional[QThread] = None
        self._worker: Optional[ModelDownloadWorker] = None

        self.setWindowTitle("Download AI Model")
        self.setMinimumWidth(460)
        self.setStyleSheet(_QSS)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint
        )
        self._build_ui()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        size_hint = _SIZE_HINTS.get(self.model_name, "size unknown")
        provider_label = _PROVIDER_LABEL.get(self.provider, self.provider)

        title = QLabel("Local AI Model Required")
        title.setObjectName("title")
        root.addWidget(title)

        info = QLabel(
            f"The <b>{provider_label}</b> model <b>{self.model_name}</b> "
            f"({size_hint}) is not downloaded yet.\n\n"
            "FreeCut AI will download it from Hugging Face and cache it "
            "on your computer for future use."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        hint = QLabel(
            "You can also download or manage models later via Settings → Local AI Models."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.hide()
        root.addWidget(self._progress)

        self._status_label = QLabel("")
        self._status_label.setObjectName("hint")
        self._status_label.hide()
        root.addWidget(self._status_label)

        # Buttons
        self._download_btn = QPushButton("Download Now")
        self._download_btn.clicked.connect(self._start_download)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("cancelBtn")
        self._cancel_btn.clicked.connect(self._on_cancel)

        btn_row = QVBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addWidget(self._download_btn)
        btn_row.addWidget(self._cancel_btn)
        root.addLayout(btn_row)

    # ── download flow ─────────────────────────────────────────────────────────

    def _start_download(self) -> None:
        self._download_btn.setEnabled(False)
        self._cancel_btn.setText("Cancel Download")
        self._progress.show()
        self._status_label.show()
        self._status_label.setText("Starting…")

        self._worker = ModelDownloadWorker(self.provider, self.model_name)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress_changed.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.failed.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _on_progress(self, pct: int, msg: str) -> None:
        self._progress.setValue(pct)
        self._status_label.setText(msg)

    def _on_finished(self, result) -> None:
        if result.is_ready:
            self._success = True
            self._status_label.setText("Download complete!")
            self.accept()
        else:
            self._status_label.setText(f"Failed: {result.message}")
            self._download_btn.setEnabled(True)
            self._cancel_btn.setText("Close")

    def _on_failed(self, message: str) -> None:
        self._status_label.setText(f"Error: {message}")
        self._download_btn.setEnabled(True)
        self._cancel_btn.setText("Close")

    def _on_cancel(self) -> None:
        if self._worker:
            self._worker.cancel()
        self.reject()

    def closeEvent(self, event):
        if self._worker:
            self._worker.cancel()
        super().closeEvent(event)

    # ── public API ────────────────────────────────────────────────────────────

    @staticmethod
    def ensure(
        provider: str,
        model_name: str,
        parent: Optional[QWidget] = None,
    ) -> bool:
        """Return True if the model is ready (already cached or just downloaded).

        Calling code pattern::

            if not ModelDownloadDialog.ensure("local", "small", parent=self):
                return   # user declined or download failed
            # proceed to use the model
        """
        manager = ModelManager()

        if provider == "local" and manager.check_local_whisper_model(model_name).is_ready:
            return True
        if provider == "local_nllb" and manager.check_nllb_model(model_name).is_ready:
            return True

        dlg = ModelDownloadDialog(provider, model_name, parent)
        dlg.exec()
        return dlg._success
