from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.logger import get_logger
from models.timeline_cache import TimelineCache
from services.capcut_export_service import CapCutExportService


logger = get_logger(__name__)


class CapCutExportWorker(QObject):
    progress_changed = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, cache: TimelineCache):
        super().__init__()

        self.cache = cache
        self.export_service = CapCutExportService()

    @Slot()
    def run(self):
        try:
            project_name = (
                Path(self.cache.video_path).stem
                if self.cache.video_path
                else "FreeCut Export"
            )

            project_dir = self.export_service.export_capcut_project(
                cache=self.cache,
                project_name=project_name,
                on_progress=self.progress_changed.emit,
            )

            self.progress_changed.emit(100, "CapCut project ready")
            self.finished.emit(project_dir)

        except Exception as error:
            logger.exception("CapCut export failed.")
            self.failed.emit(str(error))
