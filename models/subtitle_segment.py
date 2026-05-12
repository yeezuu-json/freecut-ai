from dataclasses import dataclass
from typing import Literal


SpeakerGender = Literal["male", "female", "unknown"]


@dataclass
class SubtitleSegment:
    index: int
    start_time: str
    end_time: str

    original_text: str = ""
    khmer_text: str = ""

    gender: SpeakerGender = "unknown"
    voice: str = "Default"

    pitch: str = "0"
    speed: str = "1.25"
    volume: str = "0"

    audio_path: str | None = None

    @property
    def display_text(self) -> str:
        if self.khmer_text.strip():
            return self.khmer_text.strip()

        return self.original_text.strip()