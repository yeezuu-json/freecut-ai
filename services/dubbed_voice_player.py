from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from app.logger import get_logger


logger = get_logger(__name__)


def _srt_to_ms(time_str: str) -> int:
    """Convert '00:00:04,590' → 4590 ms."""
    try:
        h, m, rest = time_str.split(":")
        s, ms = rest.replace(".", ",").split(",")
        return int(h) * 3_600_000 + int(m) * 60_000 + int(s) * 1_000 + int(ms)
    except Exception:
        return 0


class DubbedVoicePlayer(QObject):
    """Plays per-segment TTS clips in sync with the main video player.

    Uses a single QMediaPlayer that switches source at segment boundaries.
    Driven entirely by ``on_position_changed(pos_ms)`` calls from the main player.
    """

    def __init__(self, segments: list, parent: QObject | None = None) -> None:
        super().__init__(parent)

        # Keep only segments that have an audio file.
        self._segments = sorted(
            [s for s in segments if s.audio_path],
            key=lambda s: _srt_to_ms(s.start_time),
        )

        self._output = QAudioOutput(self)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._output)

        self._current_idx: int = -1
        self._muted: bool = False
        self._playing: bool = False   # tracks whether the main player is playing

    # ── public API ────────────────────────────────────────────────────────────

    def set_muted(self, muted: bool) -> None:
        self._muted = muted
        self._output.setMuted(muted)
        if muted:
            self._player.pause()

    def is_muted(self) -> bool:
        return self._muted

    def play(self) -> None:
        """Call when the main player starts playing."""
        self._playing = True

    def pause(self) -> None:
        """Call when the main player pauses."""
        self._playing = False
        self._player.pause()

    def stop(self) -> None:
        """Call when the main player stops."""
        self._playing = False
        self._player.stop()
        self._current_idx = -1

    def seek(self, pos_ms: int) -> None:
        """Call when the user seeks to a new position."""
        self._current_idx = -1          # force a source reload
        self.on_position_changed(pos_ms)

    def on_position_changed(self, pos_ms: int) -> None:
        """Drive playback; call this from main player's positionChanged signal."""
        if self._muted:
            return

        idx = self._find_segment(pos_ms)

        if idx == -1:
            # No segment covers this position — pause if needed.
            if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._player.pause()
            self._current_idx = -1
            return

        if idx != self._current_idx:
            # Switched to a new segment — load its audio and seek to offset.
            seg = self._segments[idx]
            offset_ms = max(0, pos_ms - _srt_to_ms(seg.start_time))
            self._current_idx = idx

            self._player.setSource(QUrl.fromLocalFile(seg.audio_path))
            self._player.setPosition(offset_ms)
            if self._playing:
                self._player.play()
        else:
            # Same segment — just ensure it's playing if the main player is.
            if (
                self._playing
                and self._player.playbackState()
                != QMediaPlayer.PlaybackState.PlayingState
            ):
                self._player.play()

    # ── private ───────────────────────────────────────────────────────────────

    def _find_segment(self, pos_ms: int) -> int:
        for i, seg in enumerate(self._segments):
            start = _srt_to_ms(seg.start_time)
            end   = _srt_to_ms(seg.end_time)
            if start <= pos_ms < end:
                return i
        return -1
