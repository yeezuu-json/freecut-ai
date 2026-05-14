from __future__ import annotations

import importlib.util
import shutil
import time
from pathlib import Path
from typing import Callable

import soundfile as sf
import torch

from app.logger import get_logger
from app.paths import MODEL_CACHE_DIR, TTS_CACHE_DIR
from services.voice_library_service import VoiceLibraryService

logger = get_logger(__name__)


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

    @staticmethod
    def _select_device() -> str:
        """Return the best available torch device string.

        Priority: CUDA (Windows/Linux NVIDIA) → MPS (macOS Apple Silicon) → CPU.
        Logs a warning when a CUDA GPU exists but the torch build lacks CUDA.
        """
        import sys
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            logger.info("CUDA available — using GPU: %s", name)
            return "cuda"

        # Warn when an NVIDIA driver exists but torch has no CUDA support.
        if sys.platform != "darwin":
            try:
                import subprocess
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                    capture_output=True, text=True, timeout=5,
                    encoding="utf-8", errors="replace",
                )
                if result.returncode == 0 and result.stdout.strip():
                    gpu_name = result.stdout.strip().splitlines()[0]
                    logger.warning(
                        "NVIDIA GPU detected (%s) but torch.cuda.is_available() is False. "
                        "Your PyTorch was likely installed without CUDA support. "
                        "Reinstall with: pip install torch --index-url "
                        "https://download.pytorch.org/whl/cu121",
                        gpu_name,
                    )
            except Exception:
                pass

        if sys.platform == "darwin":
            mps = getattr(torch.backends, "mps", None)
            if mps and mps.is_available():
                logger.info("Using Apple MPS device")
                return "mps"

        logger.warning("Falling back to CPU for VoxCPM2 inference")
        return "cpu"

    @classmethod
    def get_device_info(cls) -> dict:
        """Return device diagnostics for the Hardware Check UI panel."""
        import sys
        device = cls._select_device()
        info: dict = {
            "device": device,
            "gpu_name": "N/A",
            "vram_gb": 0.0,
            "cuda_version": "N/A",
            "torch_cuda_built": torch.cuda.is_available(),
            "nvidia_smi_gpu": "N/A",
            "warning": "",
        }

        if device == "cuda":
            idx = torch.cuda.current_device()
            info["gpu_name"] = torch.cuda.get_device_name(idx)
            info["vram_gb"] = round(
                torch.cuda.get_device_properties(idx).total_memory / 1e9, 1
            )
            info["cuda_version"] = torch.version.cuda or "unknown"
        else:
            # Try nvidia-smi to detect the physical GPU even when torch can't use it
            if sys.platform != "darwin":
                try:
                    import subprocess
                    r = subprocess.run(
                        ["nvidia-smi", "--query-gpu=name,memory.total",
                         "--format=csv,noheader"],
                        capture_output=True, text=True, timeout=5,
                        encoding="utf-8", errors="replace",
                    )
                    if r.returncode == 0 and r.stdout.strip():
                        parts = r.stdout.strip().splitlines()[0].split(",")
                        info["nvidia_smi_gpu"] = parts[0].strip()
                        if len(parts) > 1:
                            info["vram_gb"] = parts[1].strip()
                        info["warning"] = (
                            "GPU detected via nvidia-smi but PyTorch cannot use it.\n"
                            "Fix: reinstall PyTorch with CUDA support —\n"
                            "  pip install torch --index-url "
                            "https://download.pytorch.org/whl/cu121"
                        )
                except Exception:
                    pass

        return info

    @classmethod
    def load_model(cls, cache_dir: Path | None = None):
        if cls._model is not None:
            return cls._model

        if importlib.util.find_spec("voxcpm") is None:
            raise RuntimeError(
                "VoxCPM package is not installed. Install it first."
            )

        from voxcpm import VoxCPM

        device = cls._select_device()
        logger.info("Loading VoxCPM2 model on device: %s", device)

        kwargs: dict = {"load_denoiser": False}
        if cache_dir is not None:
            kwargs["cache_dir"] = str(cache_dir)

        # Pass device directly so VoxCPM loads weights onto the correct device
        # from the start rather than loading to CPU then moving.
        try:
            cls._model = VoxCPM.from_pretrained(cls.MODEL_NAME, device=device, **kwargs)
        except TypeError:
            # Older voxcpm versions may not accept device= — fall back gracefully.
            cls._model = VoxCPM.from_pretrained(cls.MODEL_NAME, **kwargs)
            try:
                cls._model = cls._model.to(device)
            except Exception as exc:
                logger.warning("Could not move VoxCPM model to %s: %s", device, exc)

        logger.info("VoxCPM2 model loaded successfully on %s", device)
        return cls._model

    def synthesize(
        self,
        text: str,
        output_path: str | Path | None = None,
        # ── Ultimate Cloning params ──────────────────────────────────────────
        prompt_wav: str | Path | None = None,
        prompt_text: str | None = None,
        # ── Voice Design param ───────────────────────────────────────────────
        # Natural-language voice description, e.g. "A young man, calm and deep".
        # When provided it is wrapped in parentheses and prepended to text so
        # VoxCPM2's Voice Design feature creates that voice without needing a
        # reference audio clip.
        voice_design: str | None = None,
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

        # Apply Voice Design prefix if provided and no reference audio supplied.
        # VoxCPM2 format: "(description)text to say"
        effective_text = text
        if voice_design and voice_design.strip() and not prompt_wav:
            effective_text = f"({voice_design.strip()}){text}"

        generate_kwargs: dict = {
            "text": effective_text,
            "cfg_value": 2.0,
            "inference_timesteps": 10,
        }

        if prompt_wav and prompt_text:
            # Ultimate Cloning — pass the reference clip to both fields for
            # maximum timbre / rhythm similarity (per VoxCPM2 README).
            generate_kwargs["prompt_wav_path"]    = str(prompt_wav)
            generate_kwargs["prompt_text"]        = prompt_text.strip()
            generate_kwargs["reference_wav_path"] = str(prompt_wav)

        elif prompt_wav and not prompt_text:
            # Controllable Cloning — reference only, no transcript needed.
            generate_kwargs["reference_wav_path"] = str(prompt_wav)

        elif prompt_text and not prompt_wav:
            raise ValueError("Sample audio is required when a transcript is provided.")

        audio = model.generate(**generate_kwargs)

        if on_progress:
            on_progress(80, "Saving audio file...")

        # VoxCPM2 outputs at 48 kHz; use the model's own sample_rate so this
        # stays correct across model versions.
        sample_rate = getattr(
            getattr(model, "tts_model", None), "sample_rate", 48000
        )
        sf.write(str(output_path), audio, sample_rate)

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