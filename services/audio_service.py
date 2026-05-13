import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


class AudioService:
    def extract_audio_for_transcription(self, video_path: Path) -> Path:
        temp_dir = Path(tempfile.gettempdir()) / "freecut_ai"
        temp_dir.mkdir(parents=True, exist_ok=True)

        output_path = temp_dir / f"{video_path.stem}_transcribe.wav"

        command = [
            "ffmpeg",
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
            "ffmpeg",
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
        valid = [s for s in segments if s.audio_path and Path(s.audio_path).exists()]
        if not valid:
            raise ValueError("No segments with audio to mix.")

        total_s = total_duration_ms / 1000.0

        # Input 0: silent stereo 44 100 Hz base of the full video duration.
        # Inputs 1..N: each TTS clip.
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r=44100:cl=stereo:d={total_s}",
        ]
        for seg in valid:
            cmd += ["-i", str(seg.audio_path)]

        # For each clip: resample → stereo → delay to its start position.
        filter_parts: list[str] = []
        mix_inputs = ["[0]"]

        for i, seg in enumerate(valid, start=1):
            delay_ms = self._srt_time_to_ms(seg.start_time)
            filter_parts.append(
                f"[{i}]aresample=44100,"
                f"aformat=channel_layouts=stereo,"
                f"adelay={delay_ms}|{delay_ms}[d{i}]"
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
            "-ac", "2",
            str(output_path),
        ]

        self._run_ffmpeg(cmd)
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

        total_ms = int(self.get_duration_seconds(video_path) * 1000)

        temp_dir = Path(tempfile.gettempdir()) / "freecut_ai"
        temp_dir.mkdir(parents=True, exist_ok=True)
        dubbed_wav = temp_dir / f"{video_path.stem}_dubbed_mix.wav"

        self.mix_dubbed_track(segments, total_ms, dubbed_wav)

        if progress_callback:
            progress_callback(50, "Encoding final video…")

        # Build FFmpeg command
        cmd = ["ffmpeg", "-y", "-i", str(video_path)]
        has_bg = background_path and background_path.exists()

        if has_bg:
            cmd += ["-i", str(background_path)]
        cmd += ["-i", str(dubbed_wav)]

        dubbed_idx = 2 if has_bg else 1

        if has_bg:
            # Normalise both audio tracks to the same format before mixing.
            filter_complex = (
                f"[1]aresample=44100,aformat=channel_layouts=stereo,"
                f"volume={background_volume}[bg];"
                f"[{dubbed_idx}]aresample=44100,aformat=channel_layouts=stereo,"
                f"volume={dubbed_volume}[dub];"
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
                "-map", f"{dubbed_idx}:a",
            ]

        cmd += [
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path),
        ]

        self._run_ffmpeg(cmd)

        if progress_callback:
            progress_callback(100, "Export complete!")

        return output_path

    def get_duration_seconds(self, media_path: Path) -> float:
        command = [
            "ffprobe",
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
        )
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])

    @staticmethod
    def _run_ffmpeg(cmd: list) -> None:
        """Run an FFmpeg command and raise with the full stderr on failure."""
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg exited with code {result.returncode}.\n\n"
                f"{result.stderr[-3000:]}"   # last 3 000 chars is usually enough
            )