from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.paths import VOICE_LIBRARY_DIR, VOICE_LIBRARY_INDEX


@dataclass
class VoiceEntry:
    id: str
    name: str
    gender: str
    wav_path: str
    sample_text: str
    created_at: datetime

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "gender": self.gender,
            "wav_path": self.wav_path,
            "sample_text": self.sample_text,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VoiceEntry":
        return cls(
            id=data["id"],
            name=data["name"],
            gender=data.get("gender", "unknown"),
            wav_path=data["wav_path"],
            sample_text=data.get("sample_text", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


class VoiceLibraryService:
    def __init__(self):
        VOICE_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        VOICE_LIBRARY_INDEX.parent.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> list[dict]:
        if not VOICE_LIBRARY_INDEX.exists():
            return []

        try:
            with open(VOICE_LIBRARY_INDEX, "r", encoding="utf-8") as f:
                data = json.load(f)

            return data if isinstance(data, list) else []

        except Exception:
            return []

    def _save_index(self, entries: list[dict]) -> None:
        VOICE_LIBRARY_INDEX.parent.mkdir(parents=True, exist_ok=True)

        with open(VOICE_LIBRARY_INDEX, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)

    def list_entries(self) -> list[VoiceEntry]:
        entries: list[VoiceEntry] = []

        for row in self._load_index():
            try:
                entry = VoiceEntry.from_dict(row)

                if Path(entry.wav_path).exists():
                    entries.append(entry)

            except Exception:
                continue

        return entries

    def add_sample(
        self,
        name: str,
        gender: str,
        src_wav: str | Path,
        sample_text: str,
    ) -> VoiceEntry:
        src_wav = Path(src_wav)

        if not src_wav.exists():
            raise FileNotFoundError(f"Voice sample not found: {src_wav}")

        if src_wav.suffix.lower() not in [".wav", ".mp3", ".m4a", ".flac"]:
            raise ValueError("Only audio files are supported.")

        sample_text = sample_text.strip()

        if not sample_text:
            raise ValueError(
                "Sample transcript is required. It must match the selected audio."
            )

        voice_id = uuid.uuid4().hex[:12]
        ext = src_wav.suffix.lower()
        dst = VOICE_LIBRARY_DIR / f"{voice_id}{ext}"

        shutil.copy2(src_wav, dst)

        entry = VoiceEntry(
            id=voice_id,
            name=name.strip() or "Untitled Voice",
            gender=gender,
            wav_path=str(dst),
            sample_text=sample_text,
            created_at=datetime.now(),
        )

        data = self._load_index()
        data.append(entry.to_dict())
        self._save_index(data)

        return entry

    def delete_entry(self, id: str) -> bool:
        data = self._load_index()
        remaining: list[dict] = []
        deleted = False

        for row in data:
            if row.get("id") == id:
                deleted = True

                try:
                    Path(row["wav_path"]).unlink(missing_ok=True)
                except Exception:
                    pass

                continue

            remaining.append(row)

        self._save_index(remaining)
        return deleted

    def get_entry(self, id: str) -> VoiceEntry | None:
        for row in self._load_index():
            if row.get("id") == id:
                try:
                    entry = VoiceEntry.from_dict(row)

                    if not Path(entry.wav_path).exists():
                        return None

                    return entry

                except Exception:
                    return None

        return None

    def get_wav_path(self, id: str) -> Path:
        entry = self.get_entry(id)

        if entry is None:
            raise ValueError(f"Voice not found: {id}")

        return Path(entry.wav_path)