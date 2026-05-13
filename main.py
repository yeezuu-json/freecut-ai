import os

from dotenv import load_dotenv

from app.application import run_app


def _suppress_av_warnings() -> None:
    """
    Redirect C-level stderr (fd 2) to /dev/null so that libav/FFmpeg
    warnings like '[aac @ 0x...] illegal icc' are silenced.

    Python's logging module is unaffected — it writes through its own
    handlers (file, stdout) and does not use fd 2 directly.

    Set FREECUT_DEBUG=1 in the environment to keep stderr visible when
    debugging low-level media issues.
    """
    if os.environ.get("FREECUT_DEBUG"):
        return
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 2)   # replace fd 2 with /dev/null
        os.close(devnull)
    except OSError:
        pass


if __name__ == "__main__":
    load_dotenv()
    _suppress_av_warnings()
    run_app()