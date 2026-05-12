import shutil
import subprocess

from app.logger import get_logger


logger = get_logger(__name__)


class SystemCheckService:
    def check_ffmpeg(self) -> tuple[bool, str]:
        ffmpeg_path = shutil.which("ffmpeg")

        if ffmpeg_path is None:
            return False, "FFmpeg not found"

        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
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
        ffprobe_path = shutil.which("ffprobe")

        if ffprobe_path is None:
            return False, "FFprobe not found"

        return True, "Installed"