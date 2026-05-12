import time

from PySide6.QtCore import QObject, Signal, Slot

from app.config import AppConfig, load_config
from app.logger import setup_logger, get_logger
from utils.font_manager import load_fonts


class BootstrapWorker(QObject):
    progress_changed = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str)

    @Slot()
    def run(self):
        try:
            self.progress_changed.emit(10, "Loading configuration...")
            config = load_config()
            time.sleep(0.2)

            self.progress_changed.emit(25, "Starting logger...")
            setup_logger(config.log_level)
            logger = get_logger(__name__)
            logger.info("Application bootstrap started.")
            time.sleep(0.2)

            self.progress_changed.emit(45, "Loading fonts...")
            load_fonts(config.fonts_path)
            time.sleep(0.2)

            self.progress_changed.emit(65, "Loading services...")
            self.load_services(config)
            time.sleep(0.2)

            self.progress_changed.emit(85, "Preparing window...")
            time.sleep(0.2)

            self.progress_changed.emit(100, "Ready")
            logger.info("Application bootstrap finished.")

            self.finished.emit(config)

        except Exception as error:
            try:
                logger = get_logger(__name__)
                logger.exception("Bootstrap failed.")
            except Exception:
                pass

            self.failed.emit(str(error))

    def load_services(self, config: AppConfig):
        logger = get_logger(__name__)
        logger.debug("Loading services with config: %s", config)

        # Later:
        # - init database
        # - init API client
        # - load user settings
        # - check local cache
        pass