from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.logger import get_logger
from services.voxcpm_service import VoxCpmService

logger = get_logger(__name__)


class VoxCpmWorker(QObject):
    progress_changed = Signal(int, str)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        text: str,
        speed_percent: int,
        output_path: str | Path | None = None,
        voice_id: str | None = None,
        prompt_wav: str | Path | None = None,
        prompt_text: str | None = None,
        voice_design: str | None = None,
    ):
        super().__init__()

        self.text = text
        self.speed_percent = speed_percent
        self.output_path = output_path
        self.voice_id = voice_id
        self.prompt_wav = prompt_wav
        self.prompt_text = prompt_text
        self.voice_design = voice_design
        self.service = VoxCpmService()

    @Slot()
    def run(self):
        try:
            if self.voice_id:
                output = self.service.synthesize_with_voice_id(
                    text=self.text,
                    voice_id=self.voice_id,
                    output_path=self.output_path,
                    speed_percent=self.speed_percent,
                    on_progress=self.progress_changed.emit,
                )
            else:
                output = self.service.synthesize(
                    text=self.text,
                    output_path=self.output_path,
                    prompt_wav=self.prompt_wav,
                    prompt_text=self.prompt_text,
                    voice_design=self.voice_design,
                    speed_percent=self.speed_percent,
                    on_progress=self.progress_changed.emit,
                )

            self.finished.emit(str(output))

        except Exception as error:
            logger.exception("VoxCPM generation failed.")
            self.failed.emit(str(error))