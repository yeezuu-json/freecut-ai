"""yt-dlp based video download service.

Supports TikTok, Facebook, Dailymotion and any other yt-dlp compatible URL.
Downloads run synchronously so they work cleanly inside a QThread.

Usage
-----
    svc = VideoDownloadService(output_dir=Path("~/Downloads"))
    info = svc.fetch_info(url)          # fast metadata fetch (no download)
    result = svc.download(url, on_progress=cb)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from app.logger import get_logger
from app.paths import BASE_DIR

logger = get_logger(__name__)

ProgressCallback = Callable[[int, str], None]   # percent 0-100, message

DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads" / "FreeCutAI"


@dataclass
class VideoInfo:
    url: str
    title: str
    platform: str
    duration_s: int           # seconds
    thumbnail: str            # URL
    formats: list[dict]       # raw yt-dlp format list
    best_height: int          # e.g. 1080
    filesize_approx: int      # bytes, 0 if unknown


@dataclass
class DownloadResult:
    url: str
    title: str
    output_path: Path
    success: bool
    error: str = ""


# ── platform detection ────────────────────────────────────────────────────────

_PLATFORM_RE: list[tuple[str, str]] = [
    (r"tiktok\.com",        "TikTok"),
    (r"vm\.tiktok\.com",    "TikTok"),
    (r"facebook\.com",      "Facebook"),
    (r"fb\.watch",          "Facebook"),
    (r"dailymotion\.com",   "Dailymotion"),
    (r"dai\.ly",            "Dailymotion"),
    (r"youtube\.com",       "YouTube"),
    (r"youtu\.be",          "YouTube"),
    (r"instagram\.com",     "Instagram"),
    (r"twitter\.com",       "Twitter / X"),
    (r"x\.com",             "Twitter / X"),
]


def detect_platform(url: str) -> str:
    for pattern, name in _PLATFORM_RE:
        if re.search(pattern, url, re.IGNORECASE):
            return name
    return "Unknown"


# ── service ───────────────────────────────────────────────────────────────────

class VideoDownloadService:
    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.output_dir = output_dir or DEFAULT_DOWNLOAD_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    # ── metadata ──────────────────────────────────────────────────────────────

    def fetch_info(self, url: str) -> VideoInfo:
        """Fetch video metadata without downloading."""
        import yt_dlp  # type: ignore[import]

        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(url, download=False)

        formats = data.get("formats") or []
        best_height = max(
            (f.get("height") or 0 for f in formats), default=0
        )
        approx = data.get("filesize_approx") or data.get("filesize") or 0

        return VideoInfo(
            url=url,
            title=data.get("title") or "Unknown",
            platform=detect_platform(url),
            duration_s=int(data.get("duration") or 0),
            thumbnail=data.get("thumbnail") or "",
            formats=formats,
            best_height=best_height,
            filesize_approx=approx,
        )

    # ── download ──────────────────────────────────────────────────────────────

    def download(
        self,
        url: str,
        quality: str = "best",           # "best" | "1080" | "720" | "480" | "360" | "audio"
        on_progress: Optional[ProgressCallback] = None,
        custom_filename: Optional[str] = None,
        playlist: bool = False,          # True = download all videos from profile/playlist
        max_downloads: int = 0,          # 0 = unlimited (only used when playlist=True)
    ) -> DownloadResult:
        """Download video to output_dir with progress reporting."""
        import yt_dlp  # type: ignore[import]

        self._cancelled = False
        _p = on_progress or (lambda *_: None)
        _p(0, "Preparing download…")

        # Build format selector
        if quality == "audio":
            fmt = "bestaudio/best"
        elif quality == "best":
            fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        else:
            h = quality.rstrip("p")
            fmt = (
                f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]"
                f"/best[height<={h}][ext=mp4]/best[height<={h}]/best"
            )

        # Output template
        tmpl_name = custom_filename or "%(title)s [%(id)s].%(ext)s"
        out_tmpl = str(self.output_dir / tmpl_name)

        collected: dict = {}

        def _hook(d: dict) -> None:
            if self._cancelled:
                raise yt_dlp.utils.DownloadCancelled()

            status = d.get("status")
            if status == "downloading":
                total   = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                current = d.get("downloaded_bytes") or 0
                pct     = int(current / total * 90) if total else 0
                speed   = d.get("speed") or 0
                speed_s = f"{speed / 1024 / 1024:.1f} MB/s" if speed else ""
                eta     = d.get("eta") or 0
                eta_s   = f"  ETA {eta}s" if eta else ""
                _p(pct, f"Downloading… {speed_s}{eta_s}".strip())
            elif status == "finished":
                collected["filename"] = d.get("filename") or d.get("info_dict", {}).get("_filename")
                _p(92, "Processing…")

        opts: dict = {
            "format": fmt,
            "outtmpl": out_tmpl,
            "progress_hooks": [_hook],
            "quiet": True,
            "no_warnings": True,
            "noplaylist": not playlist,
            "merge_output_format": "mp4",
            **({"max_downloads": max_downloads} if playlist and max_downloads > 0 else {}),
            "postprocessors": [{
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }] if quality != "audio" else [],
        }

        info: dict | None = None
        try:
            _p(5, "Fetching video info…")
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)

        except yt_dlp.utils.MaxDownloadsReached:
            # Raised when user-set --max-downloads limit is hit — this is
            # expected and counts as a successful playlist download.
            logger.info("Max downloads limit reached for %s — treating as success.", url)
            _p(100, "Done!")
            return DownloadResult(
                url=url,
                title=info.get("title") if info else "Playlist",
                output_path=self.output_dir,
                success=True,
            )

        except Exception as exc:
            logger.exception("Download failed for %s", url)
            return DownloadResult(
                url=url,
                title="",
                output_path=self.output_dir,
                success=False,
                error=str(exc),
            )

        # Resolve final filename (single-video path)
        filename = collected.get("filename")
        if not filename and info:
            with yt_dlp.YoutubeDL({"quiet": True}) as _ydl:
                filename = _ydl.prepare_filename(info)

        out_path = Path(filename) if filename else self.output_dir

        # yt-dlp may rename after merge (e.g. .webm → .mp4)
        if not out_path.exists():
            mp4 = out_path.with_suffix(".mp4")
            if mp4.exists():
                out_path = mp4

        _p(100, "Done!")
        logger.info("Download complete: %s", out_path)

        return DownloadResult(
            url=url,
            title=info.get("title") or "Unknown" if info else "Unknown",
            output_path=out_path,
            success=True,
        )
