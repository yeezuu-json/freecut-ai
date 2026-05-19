from PySide6.QtWidgets import QMainWindow, QMessageBox

from app.logger import get_logger
from ui.layouts.editor_layout import EditorLayout


logger = get_logger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()

        self.config = config

        logger.info("MainWindow initialized.")

        self.setWindowTitle(f"{config.app_name} - AI Dubbing Studio")
        self.resize(1280, 760)

        self.editor_layout = EditorLayout(config)
        self.setCentralWidget(self.editor_layout)

    def closeEvent(self, event):
        if hasattr(self.editor_layout, "running_threads") and self.editor_layout.running_threads:
            result = QMessageBox.question(
                self,
                "Process Running",
                "A background process is still running (TTS, Demucs, etc.).\n\n"
                "Close anyway? Running jobs will be cancelled. "
                "This may take a few seconds.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if result == QMessageBox.StandardButton.No:
                event.ignore()
                return

        self.editor_layout.cleanup()
        event.accept()