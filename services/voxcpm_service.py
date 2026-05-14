from __future__ import annotations

import importlib.util
import shutil
import time
from pathlib import Path
from typing import Callable

import soundfile as sf
import torch

from app.paths import MODEL_CACHE_DIR, TTS_CACHE_DIR
from services.voice_library_service import VoiceLibraryService


class VoxCpmService:
    _model = None

    MODEL_NAME = "openbmb/VoxCPM2"

    def __init__(self):
        self.cache_dir = MODEL_CACHE_DIR / "voxcpm2"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.output_dir = TTS_CACHE_DIR / "voxcpm2"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def is_package_installed(self) -> bool:
        return importlib.util.find_spec("voxcpm") is not None

    def is_model_downloaded(self) -> bool:
        return self.cache_dir.exists() and any(self.cache_dir.rglob("*"))

    def build_output_path(self, prefix: str = "voxcpm2") -> Path:
        timestamp = int(time.time())
        return self.output_dir / f"{prefix}_{timestamp}.wav"

    @classmethod
    def load_model(cls, cache_dir: Path | None = None):
        if cls._model is not None:
            return cls._model

        if importlib.util.find_spec("voxcpm") is None:
            raise RuntimeError(
                "VoxCPM package is not installed. Install it first."
            )

        from voxcpm import VoxCPM

        kwargs = {}

        if cache_dir is not None:
            kwargs["cache_dir"] = str(cache_dir)

        cls._model = VoxCPM.from_pretrained(cls.MODEL_NAME, **kwargs)

        if torch.cuda.is_available():
            cls._model = cls._model.cuda()

        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            try:
                cls._model = cls._model.to("mps")
            except Exception:
                pass

        return cls._model

    def synthesize(
        self,
        text: str,
        output_path: str | Path | None = None,
        prompt_wav: str | Path | None = None,
        prompt_text: str | None = None,
        speed_percent: int = 10,
        on_progress: Callable[[int, str], None] | None = None,
    ) -> Path:
        text = text.strip()

        if not text:
            raise ValueError("Text is empty.")

        if output_path is None:
            output_path = self.build_output_path()

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if on_progress:
            on_progress(5, "Loading VoxCPM2 model...")

        model = self.load_model(self.cache_dir)

        if on_progress:
            on_progress(35, "Generating voice...")

        generate_kwargs = {
            "text": text,
        }

        if prompt_wav and prompt_text:
            generate_kwargs["prompt_wav_path"] = str(prompt_wav)
            generate_kwargs["prompt_text"] = prompt_text.strip()

        elif prompt_wav and not prompt_text:
            raise ValueError(
                "Sample transcript is required when sample audio is provided."
            )

        elif prompt_text and not prompt_wav:
            raise ValueError(
                "Sample audio is required when sample transcript is provided."
            )

        # VoxCPM does not support speed in your installed package.
        # Keep speed_percent for future post-processing only.
        audio = model.generate(**generate_kwargs)

        if on_progress:
            on_progress(80, "Saving audio file...")

        sf.write(str(output_path), audio, 24000)

        if on_progress:
            on_progress(100, "Voice generated successfully.")

        return output_path

    def synthesize_with_voice_id(
        self,
        text: str,
        voice_id: str,
        output_path: str | Path | None = None,
        speed_percent: int = 10,
        on_progress: Callable[[int, str], None] | None = None,
    ) -> Path:
        voice_library = VoiceLibraryService()
        entry = voice_library.get_entry(voice_id)

        if entry is None:
            raise ValueError(f"Voice not found: {voice_id}")

        if not entry.sample_text.strip():
            raise ValueError(
                "This voice sample has no transcript."
            )

        return self.synthesize(
            text=text,
            output_path=output_path,
            prompt_wav=entry.wav_path,
            prompt_text=entry.sample_text,
            speed_percent=speed_percent,
            on_progress=on_progress,
        )

    def copy_to(self, source: str | Path, target: str | Path) -> Path:
        source = Path(source)
        target = Path(target)

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

        return target