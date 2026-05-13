"""QThread worker that drives ModelDownloadService off the main thread."""
from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot

from services.model_download_service import ModelDownloadService
from services.model_manager import ModelCheckResult


class ModelDownloadWorker(QObject):
    """Run a model download in the background.

    Usage
    -----
    worker = ModelDownloadWorker("local", "small")
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.progress_changed.connect(...)
    worker.finished.connect(...)
    thread.start()
    """

    progress_changed = Signal(int, str)       # percent, message
    finished         = Signal(object)         # ModelCheckResult
    failed           = Signal(str)

    def __init__(self, provider: str, model_name: str) -> None:
        super().__init__()
        self.provider   = provider
        self.model_name = model_name
        self._service   = ModelDownloadService()

    @Slot()
    def run(self) -> None:
        try:
            result = self._service.download(
                provider    = self.provider,
                model_name  = self.model_name,
                on_progress = lambda pct, msg: self.progress_changed.emit(pct, msg),
            )
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))

    def cancel(self) -> None:
        self._service.cancel()
