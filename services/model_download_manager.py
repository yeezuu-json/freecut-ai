"""Global singleton that owns and tracks background AI model downloads.

Keeping the QThread objects here means downloads survive dialog close/reopen
without crashing or being cancelled accidentally.

Usage
-----
    mgr = ModelDownloadManager.instance()

    # Start a download (no-op if already running)
    mgr.start("local", "small")

    # Check state
    mgr.is_downloading("local", "small")
    mgr.is_ready("local", "small")
    mgr.progress("local", "small")   # (pct, message) or None

    # Cancel
    mgr.cancel("local", "small")

Signals
-------
    download_progress(provider, model, pct, message)
    download_finished(provider, model, success)
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from app.logger import get_logger
from services.model_manager import ModelManager

logger = get_logger(__name__)


class ModelDownloadManager(QObject):
    """Application-wide singleton for background model downloads."""

    download_progress = Signal(str, str, int, str)   # provider, model, pct, msg
    download_finished = Signal(str, str, bool)        # provider, model, success

    _instance: Optional["ModelDownloadManager"] = None

    @classmethod
    def instance(cls) -> "ModelDownloadManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        # key -> {"thread": QThread, "worker": ..., "pct": int, "msg": str}
        self._active: dict[str, dict] = {}
        self._manager = ModelManager()

    # ── public API ────────────────────────────────────────────────────────────

    @staticmethod
    def _key(provider: str, model: str) -> str:
        return f"{provider}:{model}"

    def is_downloading(self, provider: str, model: str) -> bool:
        return self._key(provider, model) in self._active

    def is_ready(self, provider: str, model: str) -> bool:
        if provider == "local":
            return self._manager.check_local_whisper_model(model).is_ready
        if provider == "local_nllb":
            return self._manager.check_nllb_model(model).is_ready
        if provider == "local_voxcpm":
            return self._manager.check_voxcpm_model(model).is_ready
        return False

    def progress(self, provider: str, model: str) -> tuple[int, str] | None:
        """Return (pct, message) for a running download, or None."""
        entry = self._active.get(self._key(provider, model))
        if entry is None:
            return None
        return entry["pct"], entry["msg"]

    def start(self, provider: str, model: str) -> None:
        """Start a download; silently skips if one is already running."""
        key = self._key(provider, model)
        if key in self._active:
            logger.debug("Download already running for %s", key)
            return
        if self.is_ready(provider, model):
            logger.debug("Model %s already cached, skipping download.", key)
            return

        from workers.model_download_worker import ModelDownloadWorker

        worker = ModelDownloadWorker(provider, model)
        thread = QThread()
        worker.moveToThread(thread)

        thread.started.connect(worker.run)

        worker.progress_changed.connect(
            lambda pct, msg, p=provider, m=model: self._on_progress(p, m, pct, msg)
        )
        worker.finished.connect(
            lambda result, p=provider, m=model: self._on_finished(p, m, result)
        )
        worker.failed.connect(
            lambda err, p=provider, m=model: self._on_failed(p, m, err)
        )
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(lambda k=key: self._active.pop(k, None))
        thread.finished.connect(thread.deleteLater)

        self._active[key] = {"thread": thread, "worker": worker, "pct": 0, "msg": "Starting…"}
        logger.info("Starting background download: %s", key)
        thread.start()

    def cancel(self, provider: str, model: str) -> None:
        key = self._key(provider, model)
        entry = self._active.get(key)
        if entry:
            entry["worker"].cancel()

    # ── internal slots ────────────────────────────────────────────────────────

    def _on_progress(self, provider: str, model: str, pct: int, msg: str) -> None:
        key = self._key(provider, model)
        if key in self._active:
            self._active[key]["pct"] = pct
            self._active[key]["msg"] = msg
        self.download_progress.emit(provider, model, pct, msg)

    def _on_finished(self, provider: str, model: str, result) -> None:
        success = result.is_ready
        logger.info("Download finished: %s/%s  ready=%s", provider, model, success)
        self.download_finished.emit(provider, model, success)

    def _on_failed(self, provider: str, model: str, error: str) -> None:
        logger.error("Download failed: %s/%s  error=%s", provider, model, error)
        self.download_finished.emit(provider, model, False)
