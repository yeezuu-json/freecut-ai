import os
import shutil
import subprocess
import sys
from pathlib import Path

from app.logger import get_logger


logger = get_logger(__name__)


class CapCutAppService:
    """
    Finds and opens CapCut after export.

    Supports common Windows/macOS CapCut install locations.
    Later, this can read user custom CapCut path from config/settings.
    """

    def __init__(self, custom_capcut_path: str | None = None):
        self.custom_capcut_path = Path(custom_capcut_path) if custom_capcut_path else None

    def find_capcut(self) -> Path | None:
        if self.custom_capcut_path and self.custom_capcut_path.exists():
            return self.custom_capcut_path

        if sys.platform == "darwin":
            return self._find_capcut_macos()

        if sys.platform.startswith("win"):
            return self._find_capcut_windows()

        return None

    def _find_capcut_macos(self) -> Path | None:
        candidates = [
            Path("/Applications/CapCut.app"),
            Path.home() / "Applications" / "CapCut.app",
        ]

        for path in candidates:
            if path.exists():
                return path

        return None

    def _find_capcut_windows(self) -> Path | None:
        local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        app_data = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))

        candidates = [
            # Common current CapCut installs
            local_app_data / "CapCut" / "Apps" / "CapCut.exe",
            local_app_data / "CapCut" / "CapCut.exe",
            local_app_data / "Programs" / "CapCut" / "CapCut.exe",

            # Sometimes CapCut installs under versions
            local_app_data / "CapCut" / "Apps",

            # Roaming fallback
            app_data / "CapCut" / "CapCut.exe",

            # Machine-wide installs
            program_files / "CapCut" / "CapCut.exe",
            program_files_x86 / "CapCut" / "CapCut.exe",
        ]

        for path in candidates:
            if path.is_file():
                return path

            # If path is a folder, search inside it.
            if path.is_dir():
                found = self._search_capcut_exe(path)
                if found:
                    return found

        # Search PATH as fallback.
        path_from_env = shutil.which("CapCut.exe") or shutil.which("CapCut")
        if path_from_env:
            return Path(path_from_env)

        # Last fallback: limited search in LOCALAPPDATA/CapCut
        capcut_root = local_app_data / "CapCut"
        if capcut_root.exists():
            found = self._search_capcut_exe(capcut_root)
            if found:
                return found

        return None

    def _search_capcut_exe(self, root: Path) -> Path | None:
        try:
            matches = list(root.rglob("CapCut.exe"))
        except Exception:
            return None

        if not matches:
            return None

        # Prefer shortest path / most direct executable.
        matches.sort(key=lambda p: (len(str(p)), str(p).lower()))
        return matches[0]

    def open_capcut(self) -> bool:
        capcut_path = self.find_capcut()

        if capcut_path is None:
            logger.warning("CapCut app not found.")
            return False

        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(capcut_path)], check=False)

            elif sys.platform.startswith("win"):
                subprocess.Popen(
                    [str(capcut_path)],
                    cwd=str(capcut_path.parent),
                    shell=False,
                )

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