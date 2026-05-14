"""Download local AI models (Whisper / NLLB) with progress callbacks.

This service is intentionally *not* called at startup. It is invoked
lazily — either when the user first tries to use a local model and the
model file is missing, or explicitly from the Settings dialog.
"""
from __future__ import annotations

import threading
from typing import Callable

from app.logger import get_logger
from services.model_manager import ModelManager, ModelCheckResult
from services.voxcpm_service import VoxCpmService

logger = get_logger(__name__)

ProgressCallback = Callable[[int, str], None]   # percent (0-100), message


class ModelDownloadService:
    """Download AI models and report progress.

    All downloads are synchronous so they run cleanly inside a QThread.
    Use :class:`workers.model_download_worker.ModelDownloadWorker` to run
    them off the main thread.
    """

    def __init__(self) -> None:
        self._manager = ModelManager()
        self._cancelled = threading.Event()

    # ── public API ────────────────────────────────────────────────────────────

    def cancel(self) -> None:
        self._cancelled.set()

    def is_whisper_ready(self, model_name: str) -> bool:
        return self._manager.check_local_whisper_model(model_name).is_ready

    def is_nllb_ready(self, model_name: str) -> bool:
        return self._manager.check_nllb_model(model_name).is_ready

    def download_whisper(
        self,
        model_name: str,
        on_progress: ProgressCallback | None = None,
    ) -> ModelCheckResult:
        """Download a faster-whisper model from Hugging Face.

        faster-whisper automatically downloads the model to the HF cache
        directory when you construct ``WhisperModel`` — we just do that
        here in a controlled way so we can report progress.
        """
        self._cancelled.clear()
        _p = on_progress or (lambda *_: None)

        _p(0, f"Preparing Whisper {model_name}…")
        logger.info("Downloading Whisper model: %s", model_name)

        try:
            _p(5, "Connecting to Hugging Face…")
            # Import here so the startup path doesn't pay the import cost.
            from faster_whisper import WhisperModel  # type: ignore[import]

            # Download-only pass — we construct with cpu + int8 so no heavy
            # device setup is needed, then discard the object immediately.
            _p(10, f"Downloading {model_name} (this may take a while)…")
            _ = WhisperModel(model_name, device="cpu", compute_type="int8",
                             download_root=None)
            del _

        except Exception as exc:
            logger.exception("Whisper download failed for %s.", model_name)
            return ModelCheckResult(
                provider="local",
                model=model_name,
                is_ready=False,
                message=str(exc),
            )

        _p(100, "Whisper model ready.")
        logger.info("Whisper model downloaded: %s", model_name)
        return self._manager.check_local_whisper_model(model_name)

    def download_nllb(
        self,
        model_name: str,
        on_progress: ProgressCallback | None = None,
    ) -> ModelCheckResult:
        """Download an NLLB translation model from Hugging Face.

        Uses ``transformers.AutoModelForSeq2SeqLM`` and
        ``transformers.AutoTokenizer`` to trigger the HF cache download.
        """
        self._cancelled.clear()
        _p = on_progress or (lambda *_: None)

        _p(0, f"Preparing NLLB model {model_name}…")
        logger.info("Downloading NLLB model: %s", model_name)

        try:
            _p(5, "Connecting to Hugging Face…")
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM  # type: ignore[import]

            _p(10, "Downloading tokenizer…")
            _ = AutoTokenizer.from_pretrained(model_name)
            del _

            if self._cancelled.is_set():
                return ModelCheckResult(
                    provider="local_nllb",
                    model=model_name,
                    is_ready=False,
                    message="Download cancelled.",
                )

            _p(55, "Downloading model weights (this may take a few minutes)…")
            _ = AutoModelForSeq2SeqLM.from_pretrained(model_name)
            del _

        except Exception as exc:
            logger.exception("NLLB download failed for %s.", model_name)
            return ModelCheckResult(
                provider="local_nllb",
                model=model_name,
                is_ready=False,
                message=str(exc),
            )

        _p(100, "NLLB model ready.")
        logger.info("NLLB model downloaded: %s", model_name)
        return self._manager.check_nllb_model(model_name)

    # download voxcpm model
    def download_voxcpm(
        self,
        on_progress: ProgressCallback | None = None,
    ) -> ModelCheckResult:
        self._cancelled.clear()
        _p = on_progress or (lambda *_: None)

        from services.voxcpm_service import VoxCpmService

        service = VoxCpmService()

        try:
            _p(5, "Preparing VoxCPM2...")
            _p(20, "Connecting to Hugging Face...")
            _p(45, "Downloading/loading VoxCPM2 model...")

            service.load_model(service.cache_dir)

            _p(100, "VoxCPM2 model ready.")

            return ModelCheckResult(
                provider="local_voxcpm",
                model="openbmb/VoxCPM2",
                is_ready=True,
                message="VoxCPM2 model ready.",
            )

        except Exception as exc:
            logger.exception("VoxCPM2 download failed.")

            return ModelCheckResult(
                provider="local_voxcpm",
                model="openbmb/VoxCPM2",
                is_ready=False,
                message=str(exc),
            )
            
    # ── convenience: dispatch by provider ────────────────────────────────────

    def download(
        self,
        provider: str,
        model_name: str,
        on_progress: ProgressCallback | None = None,
    ) -> ModelCheckResult:
        if provider == "local":
            return self.download_whisper(model_name, on_progress)
        if provider == "local_nllb":
            return self.download_nllb(model_name, on_progress)
        if provider == "local_voxcpm":
            return self.download_voxcpm(on_progress)
        raise ValueError(f"Unknown local provider: {provider!r}")
