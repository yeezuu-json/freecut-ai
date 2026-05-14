# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for FreeCut AI
Builds a single-folder app bundle on macOS (.app) and Windows (.exe folder).

Usage:
    macOS:   uv run pyinstaller freecut_ai.spec
    Windows: uv run pyinstaller freecut_ai.spec
"""

import os
import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH)

# ---------------------------------------------------------------------------
# ffmpeg / ffprobe binaries
# ---------------------------------------------------------------------------
# These are bundled inside the app so users don't need a separate installation.
# On macOS supply the static builds (see build scripts).
# On Windows supply the ffmpeg/ffprobe .exe files in a "bin/" folder next to
# this spec file.

def _find_binary(name: str) -> str | None:
    """Locate a binary on PATH or in a local bin/ directory."""
    local = ROOT / "bin" / (name + (".exe" if sys.platform == "win32" else ""))
    if local.exists():
        return str(local)
    import shutil
    return shutil.which(name)


ffmpeg_src  = _find_binary("ffmpeg")
ffprobe_src = _find_binary("ffprobe")

extra_binaries = []
if ffmpeg_src:
    extra_binaries.append((ffmpeg_src, "bin"))
if ffprobe_src:
    extra_binaries.append((ffprobe_src, "bin"))

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
extra_datas = [
    (str(ROOT / "assets"),       "assets"),
    (str(ROOT / "config"),       "config"),
    (str(ROOT / "voice_library"), "voice_library"),
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=extra_binaries,
    datas=extra_datas,
    hiddenimports=[
        # ── PySide6 ────────────────────────────────────────────────────────
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
        "PySide6.QtOpenGL",
        # ── PySide6-FluentWidgets ──────────────────────────────────────────
        "qfluentwidgets",
        "qfluentwidgets._rc",
        # ── qtawesome ─────────────────────────────────────────────────────
        "qtawesome",
        # ── ML / audio ────────────────────────────────────────────────────
        "torch",
        "torch.nn",
        "torch.nn.functional",
        "torchaudio",
        "torchvision",
        "faster_whisper",
        "ctranslate2",
        "demucs",
        "demucs.apply",
        "demucs.audio",
        "demucs.pretrained",
        "demucs.separate",
        "transformers",
        "accelerate",
        "sentencepiece",
        # ── VoxCPM2 ───────────────────────────────────────────────────────
        "voxcpm",
        "soundfile",
        # ── edge-tts ──────────────────────────────────────────────────────
        "edge_tts",
        "edge_tts.communicate",
        "edge_tts.submaker",
        # ── Google Gemini ──────────────────────────────────────────────────
        "google.genai",
        # ── misc ──────────────────────────────────────────────────────────
        "dotenv",
        "httpx",
        "httpx._transports.default",
        "anyio",
        "anyio._backends._asyncio",
        "pkg_resources",
        "yt_dlp",
    ],
    # Filter out None entries from datas list
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude test frameworks and dev tools to slim the bundle
        "pytest",
        "IPython",
        "jupyter",
        "notebook",
        "matplotlib",
        "scipy",
        "sklearn",
        "pandas",
        "numpy.testing",
        "torch.testing",
        "torch.distributed",
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
    upx=True,
    upx_exclude=[],
    console=False,      # no terminal window
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
    upx=True,
    upx_exclude=[],
    name="FreeCut AI",
)

# macOS — wrap the collected folder into a .app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="FreeCut AI.app",
        icon=str(ROOT / "assets" / "app.icns")
             if (ROOT / "assets" / "app.icns").exists() else None,
        bundle_identifier="com.freecut.ai",
        info_plist={
            "CFBundleDisplayName": "FreeCut AI",
            "CFBundleVersion": "1.0.0",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,   # allow dark mode
            "NSMicrophoneUsageDescription":
                "FreeCut AI needs microphone access for audio processing.",
            "com.apple.security.cs.allow-jit": True,
            "com.apple.security.cs.disable-library-validation": True,
        },
    )
