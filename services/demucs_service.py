import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.paths import STEMS_CACHE_DIR
from app.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DemucsResult:
    """Paths produced by a Demucs separation run."""
    vocals_path: Path
    background_path: Path  # no_vocals stem – instruments + ambient
    raw_audio_path: Path   # full stereo WAV extracted from the source video
    model_used: str


ProgressCallback = Callable[[int, str], None]


class DemucsService:
    """Wraps Demucs CLI to separate a video's audio into vocal and background stems."""

    DEFAULT_MODEL = "htdemucs"

    def separate(
        self,
        video_path: Path,
        output_dir: Path | None = None,
        model: str = DEFAULT_MODEL,
        progress_callback: ProgressCallback | None = None,
    ) -> DemucsResult:
        def emit(pct: int, msg: str) -> None:
            if progress_callback:
                progress_callback(pct, msg)

        self.validate_runtime()

        if output_dir is None:
            output_dir = STEMS_CACHE_DIR / video_path.stem
        output_dir.mkdir(parents=True, exist_ok=True)

        # ── Step 1: extract stereo WAV from video ──────────────────────────
        emit(5, "Extracting audio from video…")
        raw_audio_path = self._extract_audio(video_path, output_dir)

        # ── Step 2: run Demucs with --two-stems vocals ─────────────────────
        # Outputs: {demucs_out}/{model}/{track_stem}/vocals.wav
        #          {demucs_out}/{model}/{track_stem}/no_vocals.wav
        demucs_out = output_dir / "demucs_out"
        demucs_out.mkdir(parents=True, exist_ok=True)

        emit(15, f"Starting Demucs separation ({model})…")
        self._run_demucs(
            audio_path=raw_audio_path,
            output_dir=demucs_out,
            model=model,
            progress_callback=lambda pct, msg: emit(15 + int(pct * 0.78), msg),
        )

        # ── Step 3: resolve output paths ───────────────────────────────────
        emit(94, "Locating output files…")
        stem_dir = demucs_out / model / raw_audio_path.stem
        vocals_path = stem_dir / "vocals.wav"
        background_path = stem_dir / "no_vocals.wav"

        if not vocals_path.exists():
            raise FileNotFoundError(
                f"Demucs did not produce a vocals stem at: {vocals_path}"
            )
        if not background_path.exists():
            raise FileNotFoundError(
                f"Demucs did not produce a no_vocals stem at: {background_path}"
            )

        emit(100, "Audio separation complete")
        return DemucsResult(
            vocals_path=vocals_path,
            background_path=background_path,
            raw_audio_path=raw_audio_path,
            model_used=model,
        )

    # ── private helpers ──────────────────────────────────────────────────────

    def _extract_audio(self, video_path: Path, output_dir: Path) -> Path:
        """Extract a stereo 44.1 kHz WAV from *video_path*."""
        audio_path = output_dir / f"{video_path.stem}_raw.wav"

        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(video_path),
                "-vn", "-ar", "44100", "-ac", "2",
                str(audio_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=self._clean_env(),
            check=True,
        )

        return audio_path
        
    def _run_demucs(
        self,
        audio_path: Path,
        output_dir: Path,
        model: str,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> None:
        """Invoke ``python -m demucs`` in a subprocess and forward progress."""
        cmd = [
            sys.executable, "-m", "demucs",
            "--two-stems", "vocals",
            "-n", model,
            "-o", str(output_dir),
        ]

        # On Windows (and Linux), add an explicit --device flag so users with a
        # CUDA GPU get a significant speed-up.  Skip on macOS because Demucs
        # already handles MPS detection gracefully without the flag.
        if sys.platform != "darwin":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
                cmd += ["--device", device]
                logger.info("Demucs device: %s", device)
            except Exception:
                pass  # torch not available; let Demucs pick its own default

        cmd.append(str(audio_path))

        logger.info("Demucs command: %s", " ".join(cmd))
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=self._clean_env(),
        )

        if progress_callback:
            progress_callback(0.0, f"Running Demucs ({model})…")

        # Read stdout for progress lines; stderr is read after the process exits.
        stdout_lines: list[str] = []
        for raw_line in iter(process.stdout.readline, ""):
            line = raw_line.strip()
            if not line:
                continue
            stdout_lines.append(line)
            logger.debug("demucs stdout: %s", line)

            if progress_callback:
                lower = line.lower()
                if "loading" in lower or "downloading" in lower:
                    progress_callback(5.0, "Loading model weights…")
                elif "device" in lower or "using" in lower:
                    progress_callback(8.0, "Model loaded, starting separation…")
                elif "separated" in lower:
                    progress_callback(95.0, "Stems separated, writing files…")
                else:
                    pct = self._parse_tqdm_pct(line)
                    if pct is not None:
                        progress_callback(
                            10.0 + pct * 0.85,
                            f"Separating audio… {int(pct)}%",
                        )

        stderr_output = process.stderr.read()
        process.wait()

        if stderr_output:
            for line in stderr_output.splitlines():
                logger.debug("demucs stderr: %s", line)

        if process.returncode != 0:
            combined = "\n".join(
                filter(None, [
                    "\n".join(stdout_lines[-30:]),  # last 30 stdout lines
                    stderr_output.strip(),
                ])
            )
            raise RuntimeError(
                f"Demucs exited with code {process.returncode}.\n\n{combined}"
            )

    @staticmethod
    def _parse_tqdm_pct(line: str) -> float | None:
        """Return the percentage value from a tqdm progress line, or None."""
        try:
            # tqdm format: "  45%|████      | 9/20 …"
            pct_str = line.split("%")[0].split()[-1]
            val = float(pct_str)
            if 0.0 <= val <= 100.0:
                return val
        except (ValueError, IndexError):
            pass
        return None

    @staticmethod
    def _clean_env() -> dict:
        """Return an env dict that is safe for Demucs on Windows/macOS."""
        import os

        env = os.environ.copy()

        # Force child Python process to use UTF-8 instead of Windows cp1252.
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        # Disable tqdm coloring / special chars.
        env["TQDM_DISABLE"] = "0"
        env["FORCE_COLOR"] = "0"
        env["NO_COLOR"] = "1"

        return env

    def validate_runtime(self) -> None:
        """
        Check Demucs runtime dependencies before running separation.
        This gives a clean app error instead of a long Demucs traceback.
        """
        checks = [
            (
                "demucs",
                "Demucs is missing. Install it with: uv add demucs",
            ),
            (
                "torch",
                "PyTorch is missing. Install it with: uv add torch",
            ),
            (
                "torchaudio",
                "Torchaudio is missing. Install it with: uv add torchaudio",
            ),
        ]

        for module_name, error_message in checks:
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    f"import {module_name}",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            
            if result.returncode != 0:
                    raise RuntimeError(
                        f"{error_message}\n\nOriginal error:\n{result.stderr.strip()}"
                    )