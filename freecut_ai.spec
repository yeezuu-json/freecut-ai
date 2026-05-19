# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for FreeCut AI.

Build:
    Windows: uv run pyinstaller --clean --noconfirm freecut_ai.spec
    macOS:   uv run pyinstaller --clean --noconfirm freecut_ai.spec
"""

import os
import sys
import shutil
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

block_cipher = None
ROOT = Path(SPECPATH)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_binary(name: str) -> str | None:
    exe_name = name + (".exe" if sys.platform == "win32" else "")
    local = ROOT / "bin" / exe_name

    if local.exists():
        return str(local)

    found = shutil.which(exe_name) or shutil.which(name)
    return found


def _safe_collect_data(package: str):
    try:
        return collect_data_files(package)
    except Exception:
        return []


def _safe_collect_dynamic_libs(package: str):
    try:
        return collect_dynamic_libs(package)
    except Exception:
        return []


def _safe_collect_submodules(package: str):
    try:
        return collect_submodules(package)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# FFmpeg / FFprobe
# ---------------------------------------------------------------------------

ffmpeg_src = _find_binary("ffmpeg")
ffprobe_src = _find_binary("ffprobe")

extra_binaries = []

if ffmpeg_src:
    extra_binaries.append((ffmpeg_src, "bin"))

if ffprobe_src:
    extra_binaries.append((ffprobe_src, "bin"))


# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------

extra_datas = [
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "config"), "config"),
]

voice_library_dir = ROOT / "voice_library"
if voice_library_dir.exists():
    extra_datas.append((str(voice_library_dir), "voice_library"))


# ---------------------------------------------------------------------------
# ML / Torch / Demucs collection
# ---------------------------------------------------------------------------

ml_binaries = []
ml_datas = []
ml_hiddenimports = []

# Torch needs DLLs on Windows.
ml_binaries += _safe_collect_dynamic_libs("torch")
ml_binaries += _safe_collect_dynamic_libs("torchaudio")
ml_binaries += _safe_collect_dynamic_libs("ctranslate2")

ml_datas += _safe_collect_data("torch")
ml_datas += _safe_collect_data("torchaudio")
ml_datas += _safe_collect_data("demucs")
ml_datas += _safe_collect_data("faster_whisper")
ml_datas += _safe_collect_data("ctranslate2")
ml_datas += _safe_collect_data("transformers")
ml_datas += _safe_collect_data("sentencepiece")

# Demucs imports several modules dynamically.
ml_hiddenimports += _safe_collect_submodules("demucs")
ml_hiddenimports += _safe_collect_submodules("torchaudio")
ml_hiddenimports += _safe_collect_submodules("faster_whisper")
ml_hiddenimports += _safe_collect_submodules("ctranslate2")

# Keep this small for torch. collect_submodules("torch") can become huge.
ml_hiddenimports += [
    "torch",
    "torch.nn",
    "torch.nn.functional",
    "torch.jit",
    "torch.fft",
    "torch.linalg",
    "torch._C",

    # Required by torch internal imports
    "torch.distributed",
    "torch.distributed.rpc",
    "torch.distributed.autograd",
    "torch.distributed.optim",
    "torch.distributions",

    "torchaudio",
    "torchaudio.functional",
    "torchaudio.transforms",
]


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=extra_binaries + ml_binaries,
    datas=extra_datas + ml_datas,
    hiddenimports=[
        # PySide6
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
        "PySide6.QtOpenGL",

        # UI libs
        "qfluentwidgets",
        "qfluentwidgets._rc",
        "qtawesome",

        # App runtime
        "dotenv",
        "httpx",
        "httpx._transports.default",
        "anyio",
        "anyio._backends._asyncio",
        "pkg_resources",

        # Audio / video / AI
        "soundfile",
        "edge_tts",
        "edge_tts.communicate",
        "edge_tts.submaker",
        "yt_dlp",

        # Whisper / translation / Gemini
        "faster_whisper",
        "ctranslate2",
        "transformers",
        "accelerate",
        "sentencepiece",
        "google.genai",

        # Optional voice clone package, only if installed
        "voxcpm",
    ] + ml_hiddenimports,

    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],

    excludes=[
        # Dev tools
        "pytest",
        "IPython",
        "jupyter",
        "notebook",

        # Do NOT include torchcodec. It caused Windows DLL errors.
        "torchcodec",

        # Do NOT include diffq because we use htdemucs, not mdx_extra_q.
        "diffq",

        # Heavy optional packages
        "matplotlib",
        "sklearn",
        "pandas",
        "numpy.testing",
    ],

    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)


pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FreeCut AI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # safer for torch/Qt DLLs
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=(
        str(ROOT / "assets" / "app.icns")
        if sys.platform == "darwin" and (ROOT / "assets" / "app.icns").exists()
        else str(ROOT / "assets" / "app.ico")
        if (ROOT / "assets" / "app.ico").exists()
        else None
    ),
)


coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FreeCut AI",
)


if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="FreeCut AI.app",
        icon=str(ROOT / "assets" / "app.icns")
        if (ROOT / "assets" / "app.icns").exists()
        else None,
        bundle_identifier="com.freecut.ai",
        info_plist={
            "CFBundleDisplayName": "FreeCut AI",
            "CFBundleVersion": "1.0.0",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "NSMicrophoneUsageDescription": "FreeCut AI needs microphone access for audio processing.",
            "com.apple.security.cs.allow-jit": True,
            "com.apple.security.cs.disable-library-validation": True,
        },
    )