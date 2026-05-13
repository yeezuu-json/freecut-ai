import subprocess
import sys
from pathlib import Path

from app.logger import get_logger


logger = get_logger(__name__)


class CapCutAppService:
    """
    Finds and opens CapCut after export.

    Later, this can read user custom CapCut path from config/settings.
    """

    def __init__(self, custom_capcut_path: str | None = None):
        self.custom_capcut_path = Path(custom_capcut_path) if custom_capcut_path else None

    def find_capcut(self) -> Path | None:
        if self.custom_capcut_path and self.custom_capcut_path.exists():
            return self.custom_capcut_path

        if sys.platform == "darwin":
            candidates = [
                Path("/Applications/CapCut.app"),
                Path.home() / "Applications" / "CapCut.app",
            ]

            for path in candidates:
                if path.exists():
                    return path

        elif sys.platform.startswith("win"):
            candidates = [
                Path.home() / "AppData/Local/CapCut/CapCut.exe",
                Path.home() / "AppData/Local/Programs/CapCut/CapCut.exe",
                Path("C:/Program Files/CapCut/CapCut.exe"),
                Path("C:/Program Files (x86)/CapCut/CapCut.exe"),
            ]

            for path in candidates:
                if path.exists():
                    return path

        return None

    def open_capcut(self) -> bool:
        capcut_path = self.find_capcut()

        if capcut_path is None:
            logger.warning("CapCut app not found.")
            return False

        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(capcut_path)], check=False)
            elif sys.platform.startswith("win"):
                subprocess.Popen([str(capcut_path)])
            else:
                logger.warning("Opening CapCut is not supported on this platform yet.")
                return False

            logger.info("Opened CapCut: %s", capcut_path)
            return True

        except Exception:
            logger.exception("Failed to open CapCut.")
            return False

    def open_folder(self, folder_path: Path) -> bool:
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(folder_path)], check=False)
            elif sys.platform.startswith("win"):
                subprocess.run(["explorer", str(folder_path)], check=False)
            else:
                subprocess.run(["xdg-open", str(folder_path)], check=False)

            logger.info("Opened folder: %s", folder_path)
            return True

        except Exception:
            logger.exception("Failed to open folder: %s", folder_path)
            return False