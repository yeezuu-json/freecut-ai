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