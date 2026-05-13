"""Video downloader dialog.

Supports TikTok (single + profile), Facebook, Dailymotion, and any yt-dlp URL.
Features:
  • Per-platform tabs with paste-and-preview
  • TikTok tab has "Single Video / User Profile" mode toggle
  • Batch tab — paste multiple URLs at once
  • Folder picker — choose destination folder per session
  • Persistent download queue (survives dialog close)
  • Up to 3 concurrent background downloads via VideoDownloadManager
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.logger import get_logger
from services.video_download_manager import DownloadJob, JobStatus, VideoDownloadManager
from services.video_download_service import (
    DEFAULT_DOWNLOAD_DIR,
    VideoDownloadService,
    VideoInfo,
    detect_platform,
)
from ui.components.app_button import AppButton
from ui.components.app_select import AppSelect
from ui.components.icons import app_icon

logger = get_logger(__name__)

# ── quality map ───────────────────────────────────────────────────────────────

_QUALITY_LABELS = [
    "Best available",
    "1080p",
    "720p",
    "480p",
    "360p",
    "Audio only",
]
_QUALITY_VALUES = {
    "Best available": "best",
    "1080p":          "1080",
    "720p":           "720",
    "480p":           "480",
    "360p":           "360",
    "Audio only":     "audio",
}

# ── platform config ───────────────────────────────────────────────────────────

_PLATFORMS = [
    {
        "name":        "TikTok",
        "placeholder": "https://www.tiktok.com/@user/video/123456...",
        "hint":        "Paste a TikTok video link.",
        "profile":     True,   # this tab gets Single / Profile toggle
    },
    {
        "name":        "Facebook",
        "placeholder": "https://www.facebook.com/watch?v=123456...",
        "hint":        "Paste a Facebook video or reel link.",
        "profile":     False,
    },
    {
        "name":        "Dailymotion",
        "placeholder": "https://www.dailymotion.com/video/x8abc12",
        "hint":        "Paste a Dailymotion video link.",
        "profile":     False,
    },
    {
        "name":        "Other",
        "placeholder": "https://…  (YouTube, Instagram, Twitter / X, …)",
        "hint":        "Any yt-dlp compatible URL works here.",
        "profile":     False,
    },
]

# ── platform badge colours ────────────────────────────────────────────────────

_BADGE_COLOUR: dict[str, str] = {
    "TikTok":      "#fe2c55",
    "Facebook":    "#1877f2",
    "Dailymotion": "#0066dc",
    "YouTube":     "#ff0000",
    "Instagram":   "#e1306c",
    "Twitter / X": "#1da1f2",
}

# ── QSS ───────────────────────────────────────────────────────────────────────

_QSS = """
QDialog { background-color: #111827; color: #e2e8f0; }

/* tabs */
QTabWidget::pane {
    background-color: #161d2e;
    border: 1px solid #1e293b;
    border-bottom-left-radius: 10px;
    border-bottom-right-radius: 10px;
    border-top-right-radius: 10px;
}
QTabBar { alignment: left; }
QTabBar::tab {
    background-color: #1e293b;
    color: #64748b;
    border: none;
    padding: 9px 0;
    min-width: 96px;
    font-size: 12px;
    font-weight: 600;
}
QTabBar::tab:first { border-top-left-radius: 8px; }
QTabBar::tab:last  { border-top-right-radius: 8px; }
QTabBar::tab:selected { background-color: #3b82f6; color: #ffffff; }
QTabBar::tab:hover:!selected { background-color: #273449; color: #cbd5e1; }

/* inputs */
QLineEdit, QPlainTextEdit {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: #3b82f6;
}
QLineEdit:focus, QPlainTextEdit:focus {
    border-color: #3b82f6;
    background-color: #172033;
}

/* buttons */
QPushButton {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 9px 20px;
    font-size: 13px;
    font-weight: 600;
    min-width: 90px;
}
QPushButton:hover   { background-color: #2563eb; }
QPushButton:pressed { background-color: #1d4ed8; }
QPushButton:disabled { background-color: #1e3a5f; color: #4b6fa0; }

QPushButton#ghostBtn {
    background-color: transparent;
    color: #94a3b8;
    border: 1px solid #334155;
    min-width: 0;
}
QPushButton#ghostBtn:hover  { background-color: #1e293b; color: #e2e8f0; border-color: #475569; }
QPushButton#ghostBtn:pressed{ background-color: #273449; }

QPushButton#dangerBtn {
    background-color: #7f1d1d;
    color: #fca5a5;
    border: 1px solid #991b1b;
    min-width: 0;
}
QPushButton#dangerBtn:hover { background-color: #991b1b; }

/* segmented toggle (profile/single mode) */
QPushButton#segActive {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 11px;
    font-weight: 700;
    min-width: 0;
}
QPushButton#segInactive {
    background-color: transparent;
    color: #64748b;
    border: none;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 11px;
    font-weight: 600;
    min-width: 0;
}
QPushButton#segInactive:hover { color: #cbd5e1; background-color: #273449; }

/* folder chooser row */
QPushButton#folderBtn {
    background-color: #1e293b;
    color: #94a3b8;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 500;
    text-align: left;
    min-width: 0;
}
QPushButton#folderBtn:hover  { border-color: #3b82f6; color: #e2e8f0; background-color: #172033; }
QPushButton#folderBtn:pressed{ background-color: #1e293b; }

/* progress */
QProgressBar {
    background-color: #1e293b;
    border: none;
    border-radius: 3px;
    height: 5px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk                  { background-color: #3b82f6; border-radius: 3px; }
QProgressBar[status="done"]::chunk   { background-color: #16a34a; }
QProgressBar[status="failed"]::chunk { background-color: #dc2626; }
QProgressBar[status="queued"]::chunk { background-color: #475569; }

/* queue list */
QListWidget {
    background-color: transparent;
    border: none;
    outline: none;
    padding: 0;
}
QListWidget::item { border-radius: 8px; margin: 2px 0; padding: 0; background: transparent; }
QListWidget::item:selected { background-color: transparent; }

/* labels */
QLabel                { color: #cbd5e1; font-size: 13px; }
QLabel#sectionTitle   { color: #f1f5f9; font-size: 13px; font-weight: 700; }
QLabel#hintLabel      { color: #475569; font-size: 11px; font-style: italic; }
QLabel#platformBadge  {
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 700;
}

/* group box */
QGroupBox {
    background-color: #161d2e;
    border: 1px solid #1e293b;
    border-radius: 8px;
    margin-top: 10px;
    padding: 12px 10px 10px 10px;
    color: #475569;
    font-size: 11px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
}

/* AppSelect inside dialog */
#appSelect {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 0 12px;
    font-size: 12px;
    font-weight: 500;
    text-align: left;
    min-height: 34px;
}
#appSelect:hover { border-color: #3b82f6; background-color: #172033; }
"""

_SELECT_MENU_QSS = """
QMenu {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 4px 0;
    font-size: 12px;
    font-weight: 500;
}
QMenu::item {
    color: #e2e8f0;
    background-color: transparent;
    padding: 9px 16px;
    border-radius: 5px;
    margin: 1px 4px;
}
QMenu::item:selected  { background-color: #3b82f6; color: #ffffff; }
QMenu::item:checked   { background-color: #172033; color: #93c5fd; font-weight: 700; }
QMenu::item:disabled  { color: #475569; }
"""


def _make_quality_select() -> AppSelect:
    sel = AppSelect(items=_QUALITY_LABELS, width=160, height=34)
    _patch_menu(sel)
    return sel


def _patch_menu(sel: AppSelect) -> None:
    """Apply dark menu QSS every time AppSelect rebuilds its menu."""
    original = sel.rebuild_menu
    def _patched():
        original()
        sel.menu.setStyleSheet(_SELECT_MENU_QSS)
    sel.rebuild_menu = _patched
    sel.menu.setStyleSheet(_SELECT_MENU_QSS)


# ─────────────────────────────────────────────────────────────────────────────
# Job row widget
# ─────────────────────────────────────────────────────────────────────────────

class _JobRow(QWidget):
    def __init__(self, job: DownloadJob, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.job_id = job.id
        self._build(job)

    def _build(self, job: DownloadJob) -> None:
        self.setStyleSheet(
            "background-color: #1a2236; border-radius: 8px;"
            "border: 1px solid #1e293b;"
        )
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 10, 10, 10)
        root.setSpacing(10)

        # Left column ─────────────────────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(3)

        platform = detect_platform(job.url)
        colour   = _BADGE_COLOUR.get(platform, "#6366f1")

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        badge = QLabel(platform)
        badge.setObjectName("platformBadge")
        badge.setStyleSheet(
            f"color: {colour}; background-color: {colour}22;"
            "border-radius: 4px; padding: 2px 8px;"
            "font-size: 10px; font-weight: 700;"
        )
        top_row.addWidget(badge)

        if job.playlist:
            pl_badge = QLabel("Profile")
            pl_badge.setStyleSheet(
                "color: #a78bfa; background-color: #2e1065; border-radius: 4px;"
                "padding: 2px 6px; font-size: 10px; font-weight: 700;"
            )
            top_row.addWidget(pl_badge)

        top_row.addStretch()
        left.addLayout(top_row)

        self._title_lbl = QLabel(job.title or job.url)
        self._title_lbl.setStyleSheet("color: #f1f5f9; font-size: 12px; font-weight: 600;")
        self._title_lbl.setWordWrap(False)
        left.addWidget(self._title_lbl)

        self._url_lbl = QLabel(job.url)
        self._url_lbl.setStyleSheet("color: #475569; font-size: 10px;")
        left.addWidget(self._url_lbl)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(job.progress)
        self._progress.setFixedHeight(5)
        self._progress.setTextVisible(False)
        self._progress.setProperty("status", "queued")
        left.addWidget(self._progress)

        self._msg_lbl = QLabel(job.message)
        self._msg_lbl.setStyleSheet("color: #64748b; font-size: 10px;")
        left.addWidget(self._msg_lbl)

        root.addLayout(left, 1)

        # Right column ────────────────────────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(4)
        right.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._open_btn = QPushButton("Open")
        self._open_btn.setObjectName("ghostBtn")
        self._open_btn.setFixedWidth(64)
        self._open_btn.setFixedHeight(26)
        self._open_btn.setStyleSheet("font-size: 11px; padding: 3px 8px;")
        self._open_btn.hide()

        self._action_btn = QPushButton("Cancel")
        self._action_btn.setObjectName("dangerBtn")
        self._action_btn.setFixedWidth(64)
        self._action_btn.setFixedHeight(26)
        self._action_btn.setStyleSheet("font-size: 11px; padding: 3px 8px;")

        right.addWidget(self._open_btn)
        right.addWidget(self._action_btn)
        root.addLayout(right)

        self._sync_status(job)

    # ── live updates ──────────────────────────────────────────────────────────

    def update_progress(self, pct: int, msg: str) -> None:
        self._progress.setValue(pct)
        self._msg_lbl.setText(msg)

    def update_finished(self, success: bool, output_path: str) -> None:
        self._progress.setValue(100)
        if success:
            self._progress.setProperty("status", "done")
            self._msg_lbl.setText("✓ Done")
            self._msg_lbl.setStyleSheet("color: #86efac; font-size: 10px;")
            if output_path:
                self._open_btn.setProperty("_path", output_path)
                self._open_btn.show()
        else:
            self._progress.setProperty("status", "failed")
            self._msg_lbl.setText("✕ Failed")
            self._msg_lbl.setStyleSheet("color: #fca5a5; font-size: 10px;")
        self._action_btn.setText("Remove")
        self._action_btn.setObjectName("ghostBtn")
        self._action_btn.setStyleSheet("font-size: 11px; padding: 3px 8px;")
        self._progress.style().unpolish(self._progress)
        self._progress.style().polish(self._progress)

    def _sync_status(self, job: DownloadJob) -> None:
        if job.status in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED):
            self.update_finished(
                job.status == JobStatus.DONE, job.output_path
            )
        elif job.status == JobStatus.DOWNLOADING:
            self._progress.setProperty("status", "active")
            self._progress.style().unpolish(self._progress)
            self._progress.style().polish(self._progress)


# ─────────────────────────────────────────────────────────────────────────────
# Single-URL tab
# ─────────────────────────────────────────────────────────────────────────────

class _SingleTab(QWidget):
    def __init__(self, platform: dict, parent=None) -> None:
        super().__init__(parent)
        self._platform      = platform
        self._info: Optional[VideoInfo] = None
        self._profile_mode  = False   # only used when platform["profile"] is True
        self._fetch_thread: Optional[QThread] = None
        self._build()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        # Profile/Single toggle (TikTok only)
        if self._platform.get("profile"):
            # Pill-style segmented control — fixed width, not full-width
            toggle_outer = QHBoxLayout()
            toggle_outer.setContentsMargins(0, 0, 0, 0)

            self._toggle_row = QWidget()
            self._toggle_row.setFixedHeight(38)
            self._toggle_row.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
            )
            self._toggle_row.setStyleSheet(
                "background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;"
            )
            tr = QHBoxLayout(self._toggle_row)
            tr.setContentsMargins(4, 4, 4, 4)
            tr.setSpacing(2)

            mode_lbl = QLabel("Mode:")
            mode_lbl.setStyleSheet(
                "color: #475569; font-size: 11px; padding: 0 6px;"
            )
            tr.addWidget(mode_lbl)

            self._single_btn = QPushButton("Single Video")
            self._single_btn.setObjectName("segActive")
            self._single_btn.setFixedHeight(28)
            self._single_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._single_btn.clicked.connect(lambda: self._set_profile_mode(False))

            self._profile_btn = QPushButton("User Profile")
            self._profile_btn.setObjectName("segInactive")
            self._profile_btn.setFixedHeight(28)
            self._profile_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._profile_btn.clicked.connect(lambda: self._set_profile_mode(True))

            tr.addWidget(self._single_btn)
            tr.addWidget(self._profile_btn)

            toggle_outer.addWidget(self._toggle_row)
            toggle_outer.addStretch()
            root.addLayout(toggle_outer)
        else:
            self._single_btn  = None  # type: ignore[assignment]
            self._profile_btn = None  # type: ignore[assignment]

        # URL input row
        url_row = QHBoxLayout()
        url_row.setSpacing(8)

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText(self._platform["placeholder"])
        self._url_input.setMinimumHeight(38)
        self._url_input.returnPressed.connect(self._fetch_info)

        self._fetch_btn = QPushButton("Preview")
        self._fetch_btn.setFixedWidth(84)
        self._fetch_btn.setFixedHeight(38)
        self._fetch_btn.clicked.connect(self._fetch_info)

        url_row.addWidget(self._url_input, 1)
        url_row.addWidget(self._fetch_btn)
        root.addLayout(url_row)

        # Profile-mode extra options (limit)
        self._profile_opts = QWidget()
        self._profile_opts.setStyleSheet("background: transparent;")
        opts_row = QHBoxLayout(self._profile_opts)
        opts_row.setContentsMargins(0, 0, 0, 0)
        opts_row.setSpacing(8)

        max_lbl = QLabel("Max videos:")
        max_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        opts_row.addWidget(max_lbl)

        self._max_spin = QSpinBox()
        self._max_spin.setRange(0, 9999)
        self._max_spin.setValue(0)
        self._max_spin.setSpecialValueText("All")
        self._max_spin.setFixedWidth(72)
        self._max_spin.setFixedHeight(26)
        self._max_spin.setStyleSheet("""
            QSpinBox {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 2px 6px;
                font-size: 12px;
                min-height: 0;
            }
            QSpinBox:focus { border-color: #3b82f6; }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 14px;
                border: none;
                background: transparent;
            }
        """)
        opts_row.addWidget(self._max_spin)

        zero_hint = QLabel("(0 = all)")
        zero_hint.setStyleSheet("color: #334155; font-size: 11px; font-style: italic;")
        opts_row.addWidget(zero_hint)
        opts_row.addStretch()

        self._profile_opts.hide()
        root.addWidget(self._profile_opts)

        hint = QLabel(self._platform["hint"])
        hint.setObjectName("hintLabel")
        root.addWidget(hint)

        # Info card
        self._info_card = QGroupBox("Video Info")
        ic_layout = QVBoxLayout(self._info_card)
        ic_layout.setSpacing(4)
        ic_layout.setContentsMargins(10, 14, 10, 10)

        self._info_title = QLabel("—")
        self._info_title.setStyleSheet("color: #f1f5f9; font-weight: 600; font-size: 13px;")
        self._info_title.setWordWrap(True)
        self._info_dur  = QLabel("")
        self._info_dur.setStyleSheet("color: #64748b; font-size: 11px;")
        self._info_size = QLabel("")
        self._info_size.setStyleSheet("color: #64748b; font-size: 11px;")
        self._info_qual = QLabel("")
        self._info_qual.setStyleSheet("color: #64748b; font-size: 11px;")

        ic_layout.addWidget(self._info_title)
        ic_layout.addWidget(self._info_dur)
        ic_layout.addWidget(self._info_size)
        ic_layout.addWidget(self._info_qual)

        self._info_card.hide()
        root.addWidget(self._info_card)
        root.addStretch()

    # ── toggle mode ───────────────────────────────────────────────────────────

    def _set_profile_mode(self, on: bool) -> None:
        self._profile_mode = on
        if self._single_btn:
            self._single_btn.setObjectName("segInactive" if on else "segActive")
            self._single_btn.style().unpolish(self._single_btn)
            self._single_btn.style().polish(self._single_btn)
        if self._profile_btn:
            self._profile_btn.setObjectName("segActive" if on else "segInactive")
            self._profile_btn.style().unpolish(self._profile_btn)
            self._profile_btn.style().polish(self._profile_btn)

        if on:
            self._url_input.setPlaceholderText(
                "https://www.tiktok.com/@username"
            )
            self._fetch_btn.hide()
            self._info_card.hide()
            self._profile_opts.show()
        else:
            self._url_input.setPlaceholderText(self._platform["placeholder"])
            self._fetch_btn.show()
            self._profile_opts.hide()

    # ── preview fetch ─────────────────────────────────────────────────────────

    def _fetch_info(self) -> None:
        url = self._url_input.text().strip()
        if not url:
            return
        self._fetch_btn.setEnabled(False)
        self._fetch_btn.setText("…")
        self._info_card.hide()
        self._info = None

        from PySide6.QtCore import QObject as _QO, Signal as _S, Slot as _Sl

        class _FW(_QO):
            done   = _S(object)
            failed = _S(str)
            def __init__(self, u): super().__init__(); self._url = u
            @_Sl()
            def run(self):
                try:
                    from services.video_download_service import VideoDownloadService as _V
                    self.done.emit(_V().fetch_info(self._url))
                except Exception as e:
                    self.failed.emit(str(e))

        self._fetch_thread = QThread()
        self._fw = _FW(url)
        self._fw.moveToThread(self._fetch_thread)
        self._fetch_thread.started.connect(self._fw.run)
        self._fw.done.connect(self._on_info_ready)
        self._fw.failed.connect(self._on_info_failed)
        self._fw.done.connect(self._fetch_thread.quit)
        self._fw.failed.connect(self._fetch_thread.quit)
        self._fw.done.connect(self._fw.deleteLater)
        self._fw.failed.connect(self._fw.deleteLater)
        self._fetch_thread.finished.connect(self._fetch_thread.deleteLater)
        self._fetch_thread.start()

    @Slot(object)
    def _on_info_ready(self, info: VideoInfo) -> None:
        self._info = info
        self._fetch_btn.setEnabled(True)
        self._fetch_btn.setText("Preview")

        def _dur(s):
            m, sec = divmod(s, 60); h, m = divmod(m, 60)
            return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"

        def _sz(b):
            if not b: return "unknown size"
            for u in ("B", "KB", "MB", "GB"):
                if b < 1024: return f"{b:.0f} {u}"
                b /= 1024
            return f"{b:.1f} TB"

        self._info_title.setText(info.title)
        self._info_dur.setText(f"Duration: {_dur(info.duration_s)}")
        self._info_size.setText(f"Approx. size: {_sz(info.filesize_approx)}")
        self._info_qual.setText(f"Best quality: {info.best_height}p")
        self._info_card.show()

    @Slot(str)
    def _on_info_failed(self, error: str) -> None:
        self._fetch_btn.setEnabled(True)
        self._fetch_btn.setText("Preview")
        self._info_title.setText(f"Could not fetch info: {error[:80]}")
        self._info_dur.setText("")
        self._info_size.setText("")
        self._info_qual.setText("")
        self._info_card.show()

    # ── public ────────────────────────────────────────────────────────────────

    def get_url(self) -> str:
        return self._url_input.text().strip()

    def is_profile_mode(self) -> bool:
        return self._profile_mode

    def max_downloads(self) -> int:
        return self._max_spin.value() if hasattr(self, "_max_spin") else 0

    def get_title(self) -> str:
        return self._info.title if self._info else ""

    def clear(self) -> None:
        self._url_input.clear()
        self._info_card.hide()
        self._info = None


# ─────────────────────────────────────────────────────────────────────────────
# Batch tab
# ─────────────────────────────────────────────────────────────────────────────

class _BatchTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        lbl = QLabel("Paste one URL per line — any supported platform:")
        lbl.setObjectName("sectionTitle")
        root.addWidget(lbl)

        self._text = QPlainTextEdit()
        self._text.setPlaceholderText(
            "https://www.tiktok.com/@user/video/...\n"
            "https://www.facebook.com/watch?v=...\n"
            "https://www.dailymotion.com/video/..."
        )
        root.addWidget(self._text, 1)

        hint = QLabel("Each line is queued as a separate background download job.")
        hint.setObjectName("hintLabel")
        root.addWidget(hint)

    def get_urls(self) -> list[str]:
        return [u.strip() for u in self._text.toPlainText().splitlines() if u.strip()]

    def clear(self) -> None:
        self._text.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Main dialog
# ─────────────────────────────────────────────────────────────────────────────

class DownloadVideoDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._mgr         = VideoDownloadManager.instance()
        self._output_dir  = DEFAULT_DOWNLOAD_DIR
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self.setWindowTitle("Download Video")
        self.setMinimumSize(860, 580)
        self.resize(960, 660)
        self.setStyleSheet(_QSS)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )

        self._build_ui()
        self._attach_manager_signals()
        self._populate_queue()

    # ── layout ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── header ────────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(54)
        header.setStyleSheet(
            "background-color: #0c1526; border-bottom: 1px solid #1e293b;"
        )
        hrow = QHBoxLayout(header)
        hrow.setContentsMargins(20, 0, 16, 0)
        hrow.setSpacing(12)

        title_lbl = QLabel("Download Video")
        title_lbl.setStyleSheet(
            "color: #f1f5f9; font-size: 16px; font-weight: 700;"
        )
        hrow.addWidget(title_lbl)
        hrow.addStretch()

        qual_lbl = QLabel("Quality")
        qual_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        hrow.addWidget(qual_lbl)

        self._quality_select = _make_quality_select()
        hrow.addWidget(self._quality_select)

        root.addWidget(header)

        # ── body splitter ─────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # LEFT — input panel ───────────────────────────────────────────────────
        left_w = QWidget()
        left_w.setStyleSheet("background-color: #111827;")
        left_l = QVBoxLayout(left_w)
        left_l.setContentsMargins(16, 14, 12, 14)
        left_l.setSpacing(10)

        self._tabs = QTabWidget()
        self._single_tabs: list[_SingleTab] = []

        for p in _PLATFORMS:
            tab = _SingleTab(p)
            self._single_tabs.append(tab)
            self._tabs.addTab(tab, p["name"])

        self._batch_tab = _BatchTab()
        self._tabs.addTab(self._batch_tab, "Batch")
        left_l.addWidget(self._tabs, 1)

        # Folder picker row
        folder_box = QWidget()
        folder_box.setStyleSheet(
            "background-color: #161d2e; border-radius: 8px;"
            "border: 1px solid #1e293b;"
        )
        fbl = QHBoxLayout(folder_box)
        fbl.setContentsMargins(10, 8, 10, 8)
        fbl.setSpacing(8)

        folder_icon_lbl = QLabel()
        folder_icon_lbl.setPixmap(
            app_icon("folder", fallback="fa6s.folder", color="#64748b", size=16)
            .pixmap(16, 16)
        )
        fbl.addWidget(folder_icon_lbl)

        folder_title = QLabel("Save to:")
        folder_title.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 600;")
        fbl.addWidget(folder_title)

        self._folder_path_lbl = QLabel(self._fmt_path(self._output_dir))
        self._folder_path_lbl.setStyleSheet(
            "color: #94a3b8; font-size: 11px;"
        )
        self._folder_path_lbl.setWordWrap(False)
        fbl.addWidget(self._folder_path_lbl, 1)

        self._browse_btn = QPushButton("Browse…")
        self._browse_btn.setObjectName("ghostBtn")
        self._browse_btn.setFixedHeight(28)
        self._browse_btn.setStyleSheet("font-size: 11px; padding: 4px 12px;")
        self._browse_btn.clicked.connect(self._pick_dir)
        fbl.addWidget(self._browse_btn)

        left_l.addWidget(folder_box)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setObjectName("ghostBtn")
        self._clear_btn.setFixedHeight(38)
        self._clear_btn.setFixedWidth(80)
        self._clear_btn.clicked.connect(self._clear_current)

        self._add_btn = QPushButton("Add to Queue")
        self._add_btn.setFixedHeight(38)
        self._add_btn.clicked.connect(self._enqueue_current)

        btn_row.addStretch()
        btn_row.addWidget(self._clear_btn)
        btn_row.addWidget(self._add_btn)
        left_l.addLayout(btn_row)

        splitter.addWidget(left_w)

        # RIGHT — queue panel ──────────────────────────────────────────────────
        right_w = QWidget()
        right_w.setStyleSheet("background-color: #0c1526;")
        right_l = QVBoxLayout(right_w)
        right_l.setContentsMargins(12, 14, 16, 14)
        right_l.setSpacing(8)

        q_hdr = QHBoxLayout()
        q_title = QLabel("Download Queue")
        q_title.setObjectName("sectionTitle")
        q_hdr.addWidget(q_title)
        q_hdr.addStretch()

        clear_done = QPushButton("Clear finished")
        clear_done.setObjectName("ghostBtn")
        clear_done.setFixedHeight(26)
        clear_done.setStyleSheet("font-size: 11px; padding: 3px 10px; min-width: 0;")
        clear_done.clicked.connect(self._clear_finished)
        q_hdr.addWidget(clear_done)
        right_l.addLayout(q_hdr)

        self._queue_list = QListWidget()
        self._queue_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._queue_list.setSpacing(2)
        self._queue_list.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        right_l.addWidget(self._queue_list, 1)

        self._empty_lbl = QLabel("No downloads yet.\nAdd a URL on the left to get started.")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet("color: #1e293b; font-size: 12px;")
        right_l.addWidget(self._empty_lbl)

        splitter.addWidget(right_w)
        splitter.setSizes([480, 380])

        root.addWidget(splitter, 1)

        # ── footer ────────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(38)
        footer.setStyleSheet(
            "background-color: #0c1526; border-top: 1px solid #1e293b;"
        )
        frow = QHBoxLayout(footer)
        frow.setContentsMargins(16, 0, 16, 0)
        frow.setSpacing(8)

        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet("color: #475569; font-size: 11px;")
        frow.addWidget(self._status_lbl)
        frow.addStretch()

        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.setObjectName("ghostBtn")
        open_folder_btn.setFixedHeight(26)
        open_folder_btn.setStyleSheet("font-size: 11px; padding: 3px 12px; min-width: 0;")
        open_folder_btn.clicked.connect(self._open_dir)
        frow.addWidget(open_folder_btn)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("ghostBtn")
        close_btn.setFixedHeight(26)
        close_btn.setStyleSheet("font-size: 11px; padding: 3px 12px; min-width: 0;")
        close_btn.clicked.connect(self.close)
        frow.addWidget(close_btn)

        root.addWidget(footer)

    # ── enqueue ───────────────────────────────────────────────────────────────

    def _current_quality(self) -> str:
        return _QUALITY_VALUES.get(self._quality_select.value, "best")

    def _enqueue_current(self) -> None:
        idx     = self._tabs.currentIndex()
        quality = self._current_quality()

        if idx == len(self._single_tabs):   # Batch tab
            urls = self._batch_tab.get_urls()
            if not urls:
                self._status_lbl.setText("No URLs entered.")
                return
            for url in urls:
                self._mgr.enqueue(url, quality=quality, output_dir=self._output_dir)
            self._batch_tab.clear()
            self._status_lbl.setText(f"{len(urls)} URL(s) added to queue.")
        else:
            tab = self._single_tabs[idx]
            url = tab.get_url()
            if not url:
                self._status_lbl.setText("Please enter a URL first.")
                return
            self._mgr.enqueue(
                url,
                quality       = quality,
                output_dir    = self._output_dir,
                title         = tab.get_title(),
                playlist      = tab.is_profile_mode(),
                max_downloads = tab.max_downloads(),
            )
            tab.clear()
            self._status_lbl.setText("Added to queue.")

    def _clear_current(self) -> None:
        idx = self._tabs.currentIndex()
        if idx == len(self._single_tabs):
            self._batch_tab.clear()
        else:
            self._single_tabs[idx].clear()
        self._status_lbl.setText("Cleared.")

    # ── folder ────────────────────────────────────────────────────────────────

    def _pick_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "Choose Download Folder", str(self._output_dir)
        )
        if d:
            self._output_dir = Path(d)
            self._output_dir.mkdir(parents=True, exist_ok=True)
            self._folder_path_lbl.setText(self._fmt_path(self._output_dir))
            self._status_lbl.setText(f"Saving to: {self._fmt_path(self._output_dir)}")

    def _open_dir(self) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(self._output_dir)])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", str(self._output_dir)])
        else:
            subprocess.Popen(["xdg-open", str(self._output_dir)])

    @staticmethod
    def _fmt_path(p: Path) -> str:
        try:
            rel = p.relative_to(Path.home())
            return f"~/{rel}"
        except ValueError:
            return str(p)

    # ── queue ─────────────────────────────────────────────────────────────────

    def _populate_queue(self) -> None:
        for job in self._mgr.jobs():
            self._add_row(job)
        self._sync_empty()

    def _add_row(self, job: DownloadJob) -> None:
        row = _JobRow(job)
        row.setMinimumHeight(96)
        row._action_btn.clicked.connect(
            lambda checked=False, jid=job.id, r=row: self._on_action(jid, r)
        )
        row._open_btn.clicked.connect(
            lambda checked=False, r=row: self._open_file(r._open_btn.property("_path"))
        )
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, job.id)
        item.setSizeHint(row.sizeHint())
        self._queue_list.addItem(item)
        self._queue_list.setItemWidget(item, row)
        self._sync_empty()

    def _find_row(self, job_id: str) -> Optional[_JobRow]:
        for i in range(self._queue_list.count()):
            item = self._queue_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == job_id:
                return self._queue_list.itemWidget(item)  # type: ignore
        return None

    def _remove_item(self, job_id: str) -> None:
        for i in range(self._queue_list.count()):
            item = self._queue_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == job_id:
                self._queue_list.takeItem(i)
                break
        self._sync_empty()

    def _on_action(self, job_id: str, row: _JobRow) -> None:
        job = self._mgr.get_job(job_id)
        # If already done/failed/cancelled → just remove from view
        if job and job.status in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED):
            self._mgr.remove(job_id)
        else:
            self._mgr.cancel(job_id)
            self._mgr.remove(job_id)

    def _clear_finished(self) -> None:
        to_rm = [
            j.id for j in self._mgr.jobs()
            if j.status in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED)
        ]
        for jid in to_rm:
            self._mgr.remove(jid)

    def _sync_empty(self) -> None:
        empty = self._queue_list.count() == 0
        self._empty_lbl.setVisible(empty)
        self._queue_list.setVisible(not empty)

    # ── manager signals ───────────────────────────────────────────────────────

    def _attach_manager_signals(self) -> None:
        self._mgr.job_added.connect(self._on_job_added)
        self._mgr.job_progress.connect(self._on_job_progress)
        self._mgr.job_finished.connect(self._on_job_finished)
        self._mgr.job_removed.connect(self._on_job_removed)

    def _detach_manager_signals(self) -> None:
        try:
            self._mgr.job_added.disconnect(self._on_job_added)
            self._mgr.job_progress.disconnect(self._on_job_progress)
            self._mgr.job_finished.disconnect(self._on_job_finished)
            self._mgr.job_removed.disconnect(self._on_job_removed)
        except RuntimeError:
            pass

    @Slot(str, str, str)
    def _on_job_added(self, job_id: str, url: str, title: str) -> None:
        job = self._mgr.get_job(job_id)
        if job:
            self._add_row(job)
        self._update_status()

    @Slot(str, int, str)
    def _on_job_progress(self, job_id: str, pct: int, msg: str) -> None:
        row = self._find_row(job_id)
        if row:
            row.update_progress(pct, msg)

    @Slot(str, bool, str)
    def _on_job_finished(self, job_id: str, success: bool, path: str) -> None:
        row = self._find_row(job_id)
        if row:
            row.update_finished(success, path)
        self._update_status()

    @Slot(str)
    def _on_job_removed(self, job_id: str) -> None:
        self._remove_item(job_id)

    def _update_status(self) -> None:
        running = sum(1 for j in self._mgr.jobs() if j.status == JobStatus.DOWNLOADING)
        done    = sum(1 for j in self._mgr.jobs() if j.status == JobStatus.DONE)
        queued  = sum(1 for j in self._mgr.jobs() if j.status == JobStatus.QUEUED)
        parts   = []
        if running: parts.append(f"{running} downloading")
        if queued:  parts.append(f"{queued} queued")
        if done:    parts.append(f"{done} done")
        self._status_lbl.setText("  •  ".join(parts) if parts else "Ready")

    # ── file open ─────────────────────────────────────────────────────────────

    def _open_file(self, path: str) -> None:
        if not path:
            return
        p = Path(path)
        if not p.exists():
            QMessageBox.warning(self, "File Not Found", f"File no longer exists:\n{path}")
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(p)])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p.parent)])

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._detach_manager_signals()
        super().closeEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._detach_manager_signals()
        self._attach_manager_signals()
