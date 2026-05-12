from PySide6.QtWidgets import QMainWindow

from app.logger import get_logger
from ui.layouts.editor_layout import EditorLayout


logger = get_logger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()

        self.config = config

        logger.info("MainWindow initialized.")

        self.setWindowTitle(config.app_name)
        self.resize(1200, 780)

        self.editor_layout = EditorLayout()
        self.setCentralWidget(self.editor_layout)