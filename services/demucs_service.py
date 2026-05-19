import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.logger import get_logger
from app.paths import STEMS_CACHE_DIR, find_ffmpeg

logger = get_logger(__name__)


@dataclass
class DemucsResult:
    """Paths produced by a Demucs separation run."""
    vocals_path: Path
    background_path: Path
    raw_audio_path: Path
    model_used: str


ProgressCallback = Callable[[int, str], None]


class DemucsService:
    """Wraps Demucs CLI to separate a video's audio into vocal and background stems."""

    # htdemucs = better quality, slower on CPU
    # mdx_extra_q = faster/lighter, better for Windows CPU
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
                progress_callback(int(pct), msg)

        self.validate_runtime()

        if output_dir is None:
            output_dir = STEMS_CACHE_DIR / video_path.stem

        output_dir.mkdir(parents=True, exist_ok=True)

        emit(5, "Extracting audio from video…")
        raw_audio_path = self._extract_audio(video_path, output_dir)

        demucs_out = output_dir / "demucs_out"
        demucs_out.mkdir(parents=True, exist_ok=True)

        emit(15, f"Starting Demucs separation ({model})…")

        self._run_demucs(
            audio_path=raw_audio_path,
            output_dir=demucs_out,
            model=model,
            progress_callback=lambda pct, msg: emit(15 + int(pct * 0.78), msg),
        )

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

    def _extract_audio(self, video_path: Path, output_dir: Path) -> Path:
        """Extract a stereo 44.1 kHz WAV from video_path."""
        audio_path = output_dir / f"{video_path.stem}_raw.wav"

        command = [
            find_ffmpeg(),
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ar",
            "44100",
            "-ac",
            "2",
            str(audio_path),
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=self._clean_env(),
        )

        if result.returncode != 0:
            raise RuntimeError(
                "FFmpeg failed while extracting audio.\n\n"
                f"{result.stderr[-3000:]}"
            )

        return audio_path

    def _run_demucs(
        self,
        audio_path: Path,
        output_dir: Path,
        model: str,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> None:
        """Invoke python -m demucs in a subprocess and forward progress."""

        cmd = [
            sys.executable,
            "-m",
            "demucs",
            "--two-stems",
            "vocals",
            "-n",
            model,
            "-o",
            str(output_dir),

            # Windows/CPU stability options
            "--segment",
            "7",
            "--overlap",
            "0.1",
            "--shifts",
            "0",
            "-j",
            "1",
        ]
        
        if sys.platform != "darwin":
            device = self._detect_torch_device()
            cmd += ["--device", device]
            logger.info("Demucs device: %s", device)

        cmd.append(str(audio_path))

        logger.info("Demucs command: %s", " ".join(str(c) for c in cmd))

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=self._clean_env(),
        )

        if progress_callback:
            progress_callback(0.0, f"Running Demucs ({model})…")

        all_lines: list[str] = []

        try:
            if process.stdout is not None:
                for raw_line in iter(process.stdout.readline, ""):
                    line = raw_line.strip()

                    if not line:
                        continue

                    all_lines.append(line)
                    logger.debug("demucs: %s", line)

                    if progress_callback:
                        self._handle_demucs_progress_line(
                            line=line,
                            progress_callback=progress_callback,
                        )

            process.wait()

        except KeyboardInterrupt:
            process.kill()
            process.wait()
            raise RuntimeError(
                "Demucs was interrupted before finishing. "
                "On CPU, separation can take several minutes. "
                "Please let it finish or use CUDA GPU."
            )

        if process.returncode != 0:
            tail = "\n".join(all_lines[-80:])

            if "keyboardinterrupt" in tail.lower():
                raise RuntimeError(
                    "Demucs was interrupted before finishing.\n\n"
                    "This is not a TorchCodec error anymore. Demucs started correctly, "
                    "but it was stopped while processing the audio.\n\n"
                    "On CPU, this can take several minutes. Try using CUDA GPU, "
                    "or keep using the lighter model mdx_extra_q."
                )

            raise RuntimeError(
                f"Demucs exited with code {process.returncode}.\n\n{tail}"
            )

    def _handle_demucs_progress_line(
        self,
        line: str,
        progress_callback: Callable[[float, str], None],
    ) -> None:
        lower = line.lower()

        if "loading" in lower or "downloading" in lower:
            progress_callback(5.0, "Loading model weights…")
            return

        if "selected model" in lower:
            progress_callback(8.0, "Model loaded, preparing separation…")
            return

        if "separated tracks will be stored" in lower:
            progress_callback(9.0, "Output folder prepared…")
            return

        if "separating track" in lower:
            progress_callback(10.0, "Separating audio…")
            return

        pct = self._parse_tqdm_pct(line)
        if pct is not None:
            progress_callback(
                10.0 + pct * 0.85,
                f"Separating audio… {int(pct)}%",
            )

    @staticmethod
    def _parse_tqdm_pct(line: str) -> float | None:
        """Return the percentage value from a tqdm progress line, or None."""
        try:
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

        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        env["TQDM_DISABLE"] = "0"
        env["FORCE_COLOR"] = "0"
        env["NO_COLOR"] = "1"

        # Helps CPU stability on Windows
        env.setdefault("OMP_NUM_THREADS", "1")
        env.setdefault("MKL_NUM_THREADS", "1")

        return env

    def validate_runtime(self) -> None:
        """
        Check Demucs runtime dependencies before running separation.
        Gives a clean Windows-friendly error instead of a long traceback.
        """
        checks = [
            (
                "demucs",
                "Demucs is missing. Install it with: uv add demucs==4.0.1",
            ),
            (
                "torch",
                "PyTorch is missing or broken. Reinstall torch/torchaudio.",
            ),
            (
                "torchaudio",
                "Torchaudio is missing or broken. Reinstall torch/torchaudio.",
            ),
        ]

        for module_name, error_message in checks:
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        f"import {module_name}; print('ok')",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                    env=self._clean_env(),
                )
            except subprocess.TimeoutExpired:
                raise RuntimeError(
                    f"{module_name} import timed out on Windows.\n\n"
                    "Your PyTorch installation may be broken or loading bad DLLs."
                )

            stderr = result.stderr.strip()

            if result.returncode != 0:
                if "torchcodec" in stderr.lower() or "libtorchcodec" in stderr.lower():
                    raise RuntimeError(
                        "TorchCodec DLL error detected on Windows.\n\n"
                        "Fix:\n"
                        "  uv pip uninstall torchcodec\n"
                        "  uv add torch==2.5.1 torchaudio==2.5.1 torchvision==0.20.1\n"
                        "  uv add demucs==4.0.1\n\n"
                        f"Original error:\n{stderr[-3000:]}"
                    )

                raise RuntimeError(
                    f"{error_message}\n\nOriginal error:\n{stderr[-3000:]}"
                )

    @staticmethod
    def _detect_torch_device() -> str:
        """
        Detect torch device using a subprocess so the Qt app does not hang
        if torch DLL loading freezes on Windows.
        """
        import os

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import torch; "
                        "print('cuda' if torch.cuda.is_available() else 'cpu')"
                    ),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                env=os.environ.copy(),
            )

            if result.returncode == 0:
                device = result.stdout.strip().lower()
                if device in {"cuda", "cpu"}:
                    return device

        except Exception:
            pass

        return "cpu"