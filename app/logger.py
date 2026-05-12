import logging
from logging.handlers import RotatingFileHandler

from app.paths import LOGS_DIR, LOG_FILE


def setup_logger(level: str = "INFO") -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("my_app")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    base_logger = logging.getLogger("my_app")

    if name:
        return base_logger.getChild(name)

    return base_logger