"""RestoreCacheDialog — shown when a cached project is detected on video load."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from models.timeline_cache import TimelineCache


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
    font-size: 16px;
    font-weight: 700;
}
QLabel#subtitle {
    color: #64748b;
    font-size: 12px;
}
QFrame#stepCard {
    background-color: #242b3d;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 10px;
}
QDialogButtonBox QPushButton {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 600;
    min-width: 100px;
}
QDialogButtonBox QPushButton:hover {
    background-color: #2563eb;
}
QPushButton#freshBtn {
    background-color: #374151;
    color: #e2e8f0;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 600;
    min-width: 100px;
}
QPushButton#freshBtn:hover {
    background-color: #4b5563;
}
"""


@dataclass
class CacheStatus:
    has_demucs: bool
    has_transcript: bool
    has_translation: bool
    has_tts: bool
    transcript_count: int
    translation_count: int
    tts_count: int
    tts_total: int


def inspect_cache(cache: TimelineCache) -> CacheStatus:
    """Check which steps have valid cached data (files still exist on disk)."""
    has_demucs = bool(
        cache.vocals_path and Path(cache.vocals_path).exists()
        and cache.background_path and Path(cache.background_path).exists()
    )

    segs = cache.segments or []
    transcript_count = sum(1 for s in segs if s.original_text.strip())
    translation_count = sum(1 for s in segs if s.khmer_text.strip())
    tts_total = translation_count or transcript_count
    tts_count = sum(
        1 for s in segs
        if s.audio_path and Path(s.audio_path).exists()
    )

    return CacheStatus(
        has_demucs=has_demucs,
        has_transcript=transcript_count > 0,
        has_translation=translation_count > 0,
        has_tts=tts_count > 0,
        transcript_count=transcript_count,
        translation_count=translation_count,
        tts_count=tts_count,
        tts_total=tts_total,
    )


class RestoreCacheDialog(QDialog):
    """Shown when a cached project is detected — lets the user choose to restore."""

    def __init__(
        self,
        cache: TimelineCache,
        status: CacheStatus,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.cache = cache
        self.status = status
        self._restore = False

        self.setWindowTitle("Restore Previous Session")
        self.setMinimumWidth(460)
        self.setStyleSheet(_QSS)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint
        )
        self._build_ui()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 20)
        root.setSpacing(16)

        # Header
        title = QLabel("Previous session found")
        title.setObjectName("title")
        root.addWidget(title)

        video_name = Path(self.cache.video_path).name
        sub = QLabel(f"Cached data exists for  {video_name}")
        sub.setObjectName("subtitle")
        root.addWidget(sub)

        # Step cards
        steps_col = QVBoxLayout()
        steps_col.setSpacing(8)

        steps_col.addWidget(self._step_row(
            "Demucs Audio Stems",
            "vocals + background extracted",
            self.status.has_demucs,
        ))
        steps_col.addWidget(self._step_row(
            "Transcription",
            f"{self.status.transcript_count} segments",
            self.status.has_transcript,
        ))
        steps_col.addWidget(self._step_row(
            "Khmer Translation",
            f"{self.status.translation_count} segments",
            self.status.has_translation,
        ))
        steps_col.addWidget(self._step_row(
            "Dubbed Voice (TTS)",
            f"{self.status.tts_count}/{self.status.tts_total} clips",
            self.status.has_tts,
        ))

        root.addLayout(steps_col)

        # Hint
        hint = QLabel(
            "Restoring skips re-running expensive AI steps and saves API tokens."
        )
        hint.setObjectName("subtitle")
        hint.setWordWrap(True)
        root.addWidget(hint)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        fresh_btn = QPushButton("Start Fresh")
        fresh_btn.setObjectName("freshBtn")
        fresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fresh_btn.clicked.connect(self._on_fresh)

        restore_btn = QPushButton("Restore Session")
        restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        restore_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
                min-width: 130px;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        restore_btn.clicked.connect(self._on_restore)

        btn_row.addWidget(fresh_btn)
        btn_row.addStretch()
        btn_row.addWidget(restore_btn)
        root.addLayout(btn_row)

    def _step_row(self, label: str, detail: str, available: bool) -> QWidget:
        card = QWidget()
        card.setObjectName("stepCard")
        card.setStyleSheet("""
            QWidget#stepCard {
                background-color: #242b3d;
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(12)

        # Status icon
        icon = QLabel("✓" if available else "–")
        icon.setFixedWidth(20)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"color: {'#22c55e' if available else '#4b5563'}; "
            "font-size: 16px; font-weight: 700;"
        )
        row.addWidget(icon)

        # Text
        text_col = QVBoxLayout()
        text_col.setSpacing(1)

        name_lbl = QLabel(label)
        name_lbl.setStyleSheet(
            f"color: {'#e2e8f0' if available else '#4b5563'}; "
            "font-size: 13px; font-weight: 600;"
        )
        detail_lbl = QLabel(detail)
        detail_lbl.setStyleSheet(
            f"color: {'#94a3b8' if available else '#374151'}; font-size: 11px;"
        )

        text_col.addWidget(name_lbl)
        text_col.addWidget(detail_lbl)
        row.addLayout(text_col)
        row.addStretch()

        badge = QLabel("cached" if available else "not cached")
        badge.setStyleSheet(
            f"color: {'#22c55e' if available else '#374151'}; "
            f"background: {'#14532d' if available else '#1f2937'}; "
            "border-radius: 4px; padding: 2px 8px; font-size: 11px;"
        )
        row.addWidget(badge)

        return card

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_restore(self) -> None:
        self._restore = True
        self.accept()

    def _on_fresh(self) -> None:
        self._restore = False
        self.accept()

    # ── public ────────────────────────────────────────────────────────────────

    def should_restore(self) -> bool:
        return self._restore
