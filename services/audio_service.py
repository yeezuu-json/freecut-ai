import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from app.logger import get_logger
from app.paths import find_ffmpeg, find_ffprobe

_log = get_logger(__name__)


class AudioService:
    def extract_audio_for_transcription(self, video_path: Path) -> Path:
        temp_dir = Path(tempfile.gettempdir()) / "freecut_ai"
        temp_dir.mkdir(parents=True, exist_ok=True)

        output_path = temp_dir / f"{video_path.stem}_transcribe.wav"

        command = [
            find_ffmpeg(),
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "wav",
            str(output_path),
        ]

        self._run_ffmpeg(command)
        return output_path

    def export_to_mp3(
        self,
        video_path: Path,
        output_path: Path,
        bitrate: str = "320k",
        progress_callback=None,
    ) -> Path:
        if progress_callback:
            progress_callback(10, "Converting to MP3…")

        command = [
            find_ffmpeg(),
            "-y",
            "-i", str(video_path),
            "-vn",
            "-ar", "44100",
            "-ac", "2",
            "-b:a", bitrate,
            "-f", "mp3",
            str(output_path),
        ]

        self._run_ffmpeg(command)

        if progress_callback:
            progress_callback(100, "MP3 export complete")

        return output_path

    def mix_dubbed_track(
        self,
        segments,           # list[SubtitleSegment] with audio_path + start_time set
        total_duration_ms: int,
        output_path: Path,
    ) -> Path:
        """Combine per-segment TTS clips into one full-length WAV using FFmpeg adelay.

        TTS clips from edge-tts are typically 24 000 Hz mono.  Each clip is
        resampled to 44 100 Hz stereo before the delay is applied so that
        amix receives uniform-format streams.
        """
        all_segs = list(segments)
        valid = [s for s in all_segs if s.audio_path and Path(s.audio_path).exists()]
        missing = [s for s in all_segs if s.audio_path and not Path(s.audio_path).exists()]

        if missing:
            _log.warning(
                "mix_dubbed_track: %d segment(s) have audio_path set but the file is missing "
                "(e.g. %s). They will be skipped.",
                len(missing),
                missing[0].audio_path,
            )
        if not valid:
            raise ValueError(
                f"No TTS audio files found on disk. "
                f"The {len(all_segs)} segment(s) reference paths that no longer exist "
                f"(e.g. {all_segs[0].audio_path if all_segs else 'N/A'}). "
                "Please re-run Generate Voice before exporting."
            )

        _log.info("mix_dubbed_track: mixing %d valid segments into %s", len(valid), output_path)

        total_s = total_duration_ms / 1000.0

        # Input 0: silent mono 44 100 Hz base (matches resampled TTS clips).
        # Inputs 1..N: each TTS clip.
        # We keep everything mono inside the filter graph; -ac 2 at the output
        # upmixes to stereo so the final WAV can be fed to the combine step.
        cmd = [
            find_ffmpeg(), "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r=44100:cl=mono:d={total_s}",
        ]
        for seg in valid:
            cmd += ["-i", str(seg.audio_path)]

        # Each clip: resample to 44 100 Hz (keeps mono), then delay to start.
        filter_parts: list[str] = []
        mix_inputs = ["[0]"]

        for i, seg in enumerate(valid, start=1):
            delay_ms = self._srt_time_to_ms(seg.start_time)
            filter_parts.append(
                f"[{i}]aresample=44100,adelay={delay_ms}:all=1[d{i}]"
            )
            mix_inputs.append(f"[d{i}]")

        n_inputs = len(mix_inputs)
        mix_filter = (
            "".join(mix_inputs)
            + f"amix=inputs={n_inputs}:normalize=0:dropout_transition=0[out]"
        )
        filter_complex = ";".join(filter_parts) + ";" + mix_filter

        cmd += [
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-t", str(total_s),
            "-ar", "44100",
            "-ac", "2",          # upmix mono → stereo at output
            str(output_path),
        ]

        self._run_ffmpeg(cmd)
        _log.info("mix_dubbed_track: done → %s", output_path)
        return output_path

    @staticmethod
    def _srt_time_to_ms(time_str: str) -> int:
        """Convert SRT timestamp '00:00:04,590' to milliseconds."""
        try:
            h, m, rest = time_str.split(":")
            s, ms = rest.replace(".", ",").split(",")
            return int(h) * 3_600_000 + int(m) * 60_000 + int(s) * 1_000 + int(ms)
        except Exception:
            return 0

    def export_dubbed_video(
        self,
        video_path: Path,
        segments,                           # list[SubtitleSegment] with audio_path set
        output_path: Path,
        background_path: Optional[Path] = None,
        background_volume: float = 0.8,
        dubbed_volume: float = 1.0,
        progress_callback=None,
    ) -> Path:
        """Export a final MP4 that replaces the video's original audio with the
        dubbed voice (and optional Demucs background stem).

        Steps:
          1. Mix all per-segment TTS clips into a single full-length WAV.
          2. Run FFmpeg to combine the video stream with that WAV (plus an
             optional background stem) into the output MP4.
        """
        if progress_callback:
            progress_callback(5, "Mixing dubbed voice segments…")

        _log.info("export_dubbed_video: starting — %s segments, bg=%s", len(list(segments)), background_path)
        total_ms = int(self.get_duration_seconds(video_path) * 1000)

        temp_dir = Path(tempfile.gettempdir()) / "freecut_ai"
        temp_dir.mkdir(parents=True, exist_ok=True)
        dubbed_wav = temp_dir / f"{video_path.stem}_dubbed_mix.wav"

        self.mix_dubbed_track(segments, total_ms, dubbed_wav)
        _log.info("export_dubbed_video: dubbed mix ready → %s", dubbed_wav)

        if progress_callback:
            progress_callback(50, "Encoding final video…")

        # Build FFmpeg command
        cmd = [find_ffmpeg(), "-y", "-i", str(video_path)]
        has_bg = background_path and background_path.exists()

        if has_bg:
            cmd += ["-i", str(background_path)]
        cmd += ["-i", str(dubbed_wav)]

        dubbed_idx = 2 if has_bg else 1

        # At this point dubbed_wav is already stereo 44 100 Hz (produced by
        # mix_dubbed_track with -ac 2 -ar 44100).  Demucs background is also
        # stereo 44 100 Hz.  No resampling or channel conversion needed here —
        # just apply volume and amix.
        if has_bg:
            filter_complex = (
                f"[1]volume={background_volume}[bg];"
                f"[{dubbed_idx}]volume={dubbed_volume}[dub];"
                "[bg][dub]amix=inputs=2:normalize=0:dropout_transition=0[audio]"
            )
            cmd += [
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[audio]",
            ]
        else:
            cmd += [
                "-map", "0:v",
                f"-map", f"{dubbed_idx}:a",
            ]

        cmd += [
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-ac", "2",
            str(output_path),
        ]

        self._run_ffmpeg(cmd)
        _log.info("export_dubbed_video: video encode done → %s", output_path)

        if progress_callback:
            progress_callback(100, "Export complete!")

        return output_path

    def get_duration_seconds(self, media_path: Path) -> float:
        command = [
            find_ffprobe(),
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(media_path),
        ]
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])

    @staticmethod
    def _run_ffmpeg(cmd: list, timeout: int = 600) -> None:
        """Run an FFmpeg command, raising with stderr details on failure.

        Uses Popen + communicate(timeout) instead of subprocess.run so that
        the pipe buffers are always drained, preventing hangs on macOS when
        called from a Qt worker thread with many inputs.

        ``-loglevel error`` is injected after the ``ffmpeg`` executable so
        only real errors reach stderr (suppresses the verbose stream-info
        dump that can fill pipe buffers with large numbers of inputs).
        """
        # Inject quiet log level right after the executable name so we only
        # capture actual errors, not per-input stream headers.
        full_cmd = [cmd[0], "-loglevel", "error"] + cmd[1:]
        _log.info("FFmpeg: %s", " ".join(str(c) for c in full_cmd))

        proc = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            stdout_data, stderr_data = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise RuntimeError(
                f"FFmpeg timed out after {timeout}s.\n"
                f"Command: {' '.join(str(c) for c in full_cmd)}"
            )

        stderr_text = stderr_data.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            _log.error("FFmpeg failed (code %d):\n%s", proc.returncode, stderr_text[-3000:])
            raise RuntimeError(
                f"FFmpeg exited with code {proc.returncode}.\n\n"
                f"{stderr_text[-3000:]}"
            )
        if stderr_text.strip():
            _log.debug("FFmpeg stderr: %s", stderr_text[-500:])