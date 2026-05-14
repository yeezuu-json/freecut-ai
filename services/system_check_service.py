import subprocess

from app.logger import get_logger
from app.paths import find_ffmpeg, find_ffprobe

logger = get_logger(__name__)


class SystemCheckService:
    def check_ffmpeg(self) -> tuple[bool, str]:
        try:
            ffmpeg_path = find_ffmpeg()
        except FileNotFoundError:
            return False, "FFmpeg not found"

        try:
            result = subprocess.run(
                [ffmpeg_path, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )

            if result.returncode != 0:
                return False, "FFmpeg installed but not working"

            first_line = result.stdout.splitlines()[0] if result.stdout else "FFmpeg found"
            logger.info("FFmpeg check passed: %s", first_line)
            return True, "Installed"

        except Exception:
            logger.exception("FFmpeg check failed.")
            return False, "FFmpeg check failed"

    def check_ffprobe(self) -> tuple[bool, str]:
        try:
            find_ffprobe()
            return True, "Installed"
        except FileNotFoundError:
            return False, "FFprobe not found"