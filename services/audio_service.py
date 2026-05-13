import json
import subprocess
import tempfile
from pathlib import Path


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

        subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

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

        subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        if progress_callback:
            progress_callback(100, "MP3 export complete")

        return output_path

    def mix_dubbed_track(
        self,
        segments,           # list[SubtitleSegment] with audio_path + start_time set
        total_duration_ms: int,
        output_path: Path,
    ) -> Path:
        """Combine per-segment TTS clips into one full-length WAV using FFmpeg adelay."""
        valid = [s for s in segments if s.audio_path and Path(s.audio_path).exists()]
        if not valid:
            raise ValueError("No segments with audio to mix.")

        total_s = total_duration_ms / 1000.0

        # Build the FFmpeg command dynamically.
        # Input 0: silent base track of the full video duration.
        # Inputs 1..N: each TTS clip.
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r=44100:cl=stereo:d={total_s}",
        ]

        for seg in valid:
            cmd += ["-i", str(seg.audio_path)]

        # Build filter_complex: delay each clip to its start time, then amix all.
        filter_parts: list[str] = []
        mix_inputs = ["[0]"]

        for i, seg in enumerate(valid, start=1):
            delay_ms = self._srt_time_to_ms(seg.start_time)
            label = f"[d{i}]"
            filter_parts.append(f"[{i}]adelay={delay_ms}|{delay_ms}[d{i}]")
            mix_inputs.append(label)

        n_inputs = len(mix_inputs)
        mix_filter = (
            "".join(mix_inputs)
            + f"amix=inputs={n_inputs}:normalize=0:dropout_transition=0[out]"
        )
        filter_complex = ";".join(filter_parts) + (";" if filter_parts else "") + mix_filter

        cmd += [
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-t", str(total_s),
            "-ar", "44100",
            str(output_path),
        ]

        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
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

    def get_duration_seconds(self, media_path: Path) -> float:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
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