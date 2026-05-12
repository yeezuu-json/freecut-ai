import sys

from PySide6.QtCore import QObject, QThread, Slot
from PySide6.QtWidgets import QApplication, QMessageBox

from app.bootstrap import BootstrapWorker
from app.logger import get_logger
from ui.windows.main_window import MainWindow
from ui.windows.splash_screen import SplashScreen
from utils.font_manager import get_google_sans


class Application(QObject):
    def __init__(self):
        super().__init__()

        self.app = QApplication(sys.argv)

        self.splash = SplashScreen()
        self.main_window = None

        self.thread = QThread()
        self.worker = BootstrapWorker()

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)

        self.worker.progress_changed.connect(self.splash.update_progress)
        self.worker.status_changed.connect(self.splash.set_status)
        self.worker.finished.connect(self.on_bootstrap_finished)
        self.worker.failed.connect(self.on_bootstrap_failed)

        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)

        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.failed.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

    def run(self):
        self.splash.show()
        self.thread.start()

        sys.exit(self.app.exec())
    
    def load_theme(self, theme_path):
        logger = get_logger(__name__)

        if not theme_path.exists():
            logger.warning("Theme file not found: %s", theme_path)
            return

        with open(theme_path, "r", encoding="utf-8") as file:
            self.app.setStyleSheet(file.read())

        logger.info("Theme loaded: %s", theme_path)

    @Slot(object)
    def on_bootstrap_finished(self, config):
        logger = get_logger(__name__)
        logger.info("Opening main window.")

        self.splash.set_version(config.app_version)

        self.app.setFont(get_google_sans(size=10, weight="Regular"))
        self.load_theme(config.theme_path)

        self.main_window = MainWindow(config)

        self.splash.close()
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    @Slot(str)
    def on_bootstrap_failed(self, message: str):
        try:
            logger = get_logger(__name__)
            logger.error("Application failed to start: %s", message)
        except Exception:
            pass

        self.splash.close()

        QMessageBox.critical(
            None,
            "Application Error",
            f"Failed to start application:\n\n{message}",
        )

        self.app.quit()


def run_app():
    application = Application()
    application.run()