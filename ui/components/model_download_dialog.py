"""Lazy model-download dialog.

Shown whenever the user attempts an action that requires a local AI model
that has not yet been downloaded.

Behaviour
---------
* Before download starts  — Cancel/X closes without downloading.
* After download starts   — Cancel/X *hides* the dialog; the download
  continues in the background via ModelDownloadManager.
  The next call to ``ensure()`` reattaches to the running download
  and the user can monitor it again.

Static helper
-------------
    ok = ModelDownloadDialog.ensure(provider, model_name, parent=self)
    if not ok:
        return   # user declined or closed dialog (download may still run)
    # model is ready — proceed
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpacerItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.logger import get_logger
from services.model_download_manager import ModelDownloadManager
from services.model_manager import ModelManager

logger = get_logger(__name__)

# ── constants ─────────────────────────────────────────────────────────────────

_SIZE_HINTS: dict[str, str] = {
    "tiny":                              "~75 MB",
    "base":                              "~145 MB",
    "small":                             "~465 MB",
    "medium":                            "~1.5 GB",
    "large-v3":                          "~3.1 GB",
    "facebook/nllb-200-distilled-600M":  "~2.4 GB",
    "facebook/nllb-200-distilled-1.3B":  "~5.3 GB",
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
QLabel#statusLabel {
    color: #93c5fd;
    font-size: 11px;
}
QProgressBar {
    background-color: #2d3748;
    border: 1px solid #374151;
    border-radius: 5px;
    height: 10px;
    text-align: center;
    color: #ffffff;
    font-size: 9px;
    font-weight: 700;
}
QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 4px;
}
QPushButton#primaryBtn {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 7px;
    padding: 9px 24px;
    font-size: 13px;
    font-weight: 600;
    min-width: 140px;
}
QPushButton#primaryBtn:hover  { background-color: #2563eb; }
QPushButton#primaryBtn:pressed{ background-color: #1d4ed8; }
QPushButton#primaryBtn:disabled {
    background-color: #1e3a5f;
    color: #4b6fa0;
}
QPushButton#secondaryBtn {
    background-color: transparent;
    color: #94a3b8;
    border: 1px solid #374151;
    border-radius: 7px;
    padding: 9px 24px;
    font-size: 13px;
    font-weight: 500;
    min-width: 100px;
}
QPushButton#secondaryBtn:hover  { background-color: #1f2937; color: #e2e8f0; }
QPushButton#secondaryBtn:pressed{ background-color: #374151; }
"""


class ModelDownloadDialog(QDialog):
    """Modal download dialog backed by the global ModelDownloadManager.

    The QThread lives in the manager, not here — so closing the dialog
    never kills the download.
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
        self._downloading = False           # True once user clicked "Download"
        self._mgr = ModelDownloadManager.instance()

        self.setWindowTitle("Download AI Model")
        self.setMinimumWidth(440)
        self.setMaximumWidth(540)
        self.setStyleSheet(_QSS)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint
        )
        self._build_ui()
        self._attach_manager_signals()

        # If a download is already running (re-opened dialog), show progress immediately
        if self._mgr.is_downloading(provider, model_name):
            self._enter_downloading_state()
            prog = self._mgr.progress(provider, model_name)
            if prog:
                self._on_progress(*prog)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(0)

        size_hint      = _SIZE_HINTS.get(self.model_name, "size unknown")
        provider_label = _PROVIDER_LABEL.get(self.provider, self.provider)

        # ── header ────────────────────────────────────────────────────────────
        title = QLabel("Local AI Model Required")
        title.setObjectName("title")
        root.addWidget(title)
        root.addSpacing(10)

        self._info_label = QLabel(
            f"The <b>{provider_label}</b> model <b>{self.model_name}</b> "
            f"({size_hint}) is not downloaded yet. "
            "FreeCut AI will download it from Hugging Face and "
            "cache it on your computer for future use."
        )
        self._info_label.setWordWrap(True)
        root.addWidget(self._info_label)
        root.addSpacing(8)

        hint = QLabel(
            "Tip: you can also manage models via Settings → Local AI Models."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)
        root.addSpacing(16)

        # ── progress area (hidden until download starts) ───────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(8)
        self._progress.hide()
        root.addWidget(self._progress)

        self._status_label = QLabel("")
        self._status_label.setObjectName("statusLabel")
        self._status_label.hide()
        root.addWidget(self._status_label)

        root.addSpacing(4)

        # ── thin separator ────────────────────────────────────────────────
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #1f2937;")
        root.addWidget(sep)
        root.addSpacing(14)

        # ── buttons — right-aligned horizontal row ────────────────────────
        self._primary_btn = QPushButton("Download Now")
        self._primary_btn.setObjectName("primaryBtn")
        self._primary_btn.clicked.connect(self._on_primary)

        self._secondary_btn = QPushButton("Cancel")
        self._secondary_btn.setObjectName("secondaryBtn")
        self._secondary_btn.clicked.connect(self._on_secondary)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()
        btn_row.addWidget(self._secondary_btn)
        btn_row.addWidget(self._primary_btn)
        root.addLayout(btn_row)

    # ── state machine ─────────────────────────────────────────────────────────

    def _enter_downloading_state(self) -> None:
        """Switch UI to the in-progress view."""
        self._downloading = True
        self._primary_btn.setEnabled(False)
        self._primary_btn.setText("Downloading…")
        self._secondary_btn.setText("Continue in Background")
        self._info_label.setText(
            f"Downloading <b>{self.model_name}</b>…\n"
            "You can close this dialog — the download will keep running in the background."
        )
        self._progress.show()
        self._status_label.show()
        self._status_label.setText("Starting…")

    # ── button handlers ───────────────────────────────────────────────────────

    def _on_primary(self) -> None:
        """User clicked "Download Now"."""
        self._enter_downloading_state()
        self._mgr.start(self.provider, self.model_name)

    def _on_secondary(self) -> None:
        """Cancel (before download) or Continue in background (during download)."""
        if self._downloading:
            # Don't cancel — just hide.  Download keeps running.
            self.reject()
        else:
            self.reject()

    # ── manager signals ───────────────────────────────────────────────────────

    def _attach_manager_signals(self) -> None:
        self._mgr.download_progress.connect(self._on_manager_progress)
        self._mgr.download_finished.connect(self._on_manager_finished)

    def _detach_manager_signals(self) -> None:
        try:
            self._mgr.download_progress.disconnect(self._on_manager_progress)
            self._mgr.download_finished.disconnect(self._on_manager_finished)
        except RuntimeError:
            pass

    @Slot(str, str, int, str)
    def _on_manager_progress(self, provider: str, model: str, pct: int, msg: str) -> None:
        if provider != self.provider or model != self.model_name:
            return
        self._on_progress(pct, msg)

    @Slot(str, str, bool)
    def _on_manager_finished(self, provider: str, model: str, success: bool) -> None:
        if provider != self.provider or model != self.model_name:
            return
        self._detach_manager_signals()
        if success:
            self._success = True
            self._progress.setValue(100)
            self._status_label.setText("✓ Download complete!")
            self.accept()
        else:
            self._status_label.setText("Download failed — check your internet connection.")
            self._primary_btn.setEnabled(True)
            self._primary_btn.setText("Retry")
            self._secondary_btn.setText("Close")
            self._downloading = False

    def _on_progress(self, pct: int, msg: str) -> None:
        self._progress.setValue(pct)
        self._status_label.setText(msg)

    # ── close / destroy ───────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Close without cancelling any in-progress download."""
        self._detach_manager_signals()
        # Do NOT call cancel() — the manager keeps the download alive.
        super().closeEvent(event)

    def hideEvent(self, event) -> None:
        self._detach_manager_signals()
        super().hideEvent(event)

    # ── public static helper ──────────────────────────────────────────────────

    @staticmethod
    def ensure(
        provider: str,
        model_name: str,
        parent: Optional[QWidget] = None,
    ) -> bool:
        """Return True only if the model is cached and ready to use.

        * If already cached   → returns True immediately.
        * If download running → opens the dialog showing live progress;
          returns True if it finishes while open, False if user closes it.
        * Not started         → shows the confirm-then-download dialog;
          returns True on success, False on cancel / close.
        """
        manager = ModelManager()

        if provider == "local" and manager.check_local_whisper_model(model_name).is_ready:
            return True
        if provider == "local_nllb" and manager.check_nllb_model(model_name).is_ready:
            return True

        dlg = ModelDownloadDialog(provider, model_name, parent)
        dlg.exec()
        return dlg._success
