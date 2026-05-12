from pathlib import Path
from typing import Any

import httpx

from app.config import AppConfig
from app.logger import get_logger
from models.subtitle_segment import SubtitleSegment


logger = get_logger(__name__)


class DeepInfraTranscriptionService:
    def __init__(self, config: AppConfig):
        self.config = config
        self.base_url = "https://api.deepinfra.com/v1/openai"
        self.timeout = 300

    def transcribe_audio(
        self,
        audio_path: Path,
        model: str,
        language: str | None = "zh",
    ) -> list[SubtitleSegment]:
        if not self.config.deepinfra_api_key:
            raise ValueError(
                "DeepInfra API key is missing. Set DEEPINFRA_API_KEY or config deepinfra_api_key."
            )

        url = f"{self.base_url}/audio/transcriptions"

        data: dict[str, Any] = {
            "model": model,
            "response_format": "verbose_json",
            "temperature": "0",
        }

        if language:
            data["language"] = language

        headers = {
            "Authorization": f"Bearer {self.config.deepinfra_api_key}",
        }

        with audio_path.open("rb") as audio_file:
            files = {
                "file": (
                    audio_path.name,
                    audio_file,
                    "audio/wav",
                )
            }

            response = httpx.post(
                url,
                headers=headers,
                data=data,
                files=files,
                timeout=self.timeout,
            )

        if response.status_code >= 400:
            logger.error("DeepInfra transcription failed: %s", response.text)
            response.raise_for_status()

        return self.parse_response(response.json())

    def parse_response(self, payload: dict[str, Any]) -> list[SubtitleSegment]:
        segments_data = payload.get("segments", [])

        if not segments_data:
            text = payload.get("text", "").strip()

            if not text:
                return []

            return [
                SubtitleSegment(
                    index=1,
                    start_time="00:00:00,000",
                    end_time="00:00:00,000",
                    original_text=text,
                    khmer_text="",
                )
            ]

        segments: list[SubtitleSegment] = []

        for index, item in enumerate(segments_data, start=1):
            segments.append(
                SubtitleSegment(
                    index=index,
                    start_time=self.seconds_to_srt_time(float(item.get("start", 0))),
                    end_time=self.seconds_to_srt_time(float(item.get("end", 0))),
                    original_text=str(item.get("text", "")).strip(),
                    khmer_text="",
                )
            )

        return segments

    def seconds_to_srt_time(self, seconds: float) -> str:
        milliseconds_total = int(seconds * 1000)

        hours = milliseconds_total // 3_600_000
        milliseconds_total %= 3_600_000

        minutes = milliseconds_total // 60_000
        milliseconds_total %= 60_000

        secs = milliseconds_total // 1000
        millis = milliseconds_total % 1000

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"