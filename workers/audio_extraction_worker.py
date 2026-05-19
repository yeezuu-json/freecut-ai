from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.logger import get_logger
from services.demucs_service import DemucsResult, DemucsService


logger = get_logger(__name__)


class AudioExtractionWorker(QObject):
    """Runs Demucs stem separation on a background QThread.

    Signals:
        progress_changed(int, str)  – percentage 0-100 and a status message.
        finished(DemucsResult)      – emitted on success with the output paths.
        failed(str)                 – emitted on error with the exception message.
    """

    progress_changed = Signal(int, str)
    finished = Signal(object)  # DemucsResult
    failed = Signal(str)

    def __init__(
        self,
        video_path: Path,
        model: str = DemucsService.DEFAULT_MODEL,
        output_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self.video_path = video_path
        self.model = model
        self.output_dir = output_dir
        self._service = DemucsService()

    @Slot()
    def run(self) -> None:
        try:
            self.progress_changed.emit(0, "Initialising audio extraction…")

            result: DemucsResult = self._service.separate(
                video_path=self.video_path,
                output_dir=self.output_dir,
                model=self.model,
                progress_callback=self._on_progress,
            )

            logger.info(
                "Audio extraction finished. vocals=%s background=%s",
                result.vocals_path,
                result.background_path,
            )
            self.finished.emit(result)

        except Exception as exc:
            logger.exception("Audio extraction failed.")

            message = str(exc)
            if "torchcodec" in message.lower() or "libtorchcodec" in message.lower():
                message = (
                    "Demucs failed because TorchCodec/PyTorch DLLs are broken on Windows.\n\n"
                    "Run:\n"
                    "uv pip uninstall torchcodec\n"
                    "uv remove torch torchaudio torchvision demucs\n"
                    "uv pip install demucs==4.0.1\n"
                    "uv pip install torch==2.5.1 torchaudio==2.5.1 torchvision==0.20.1 "
                    "--index-url https://download.pytorch.org/whl/cpu"
                )

            self.failed.emit(message)

    def _on_progress(self, pct: int, msg: str) -> None:
        self.progress_changed.emit(int(pct), msg)
