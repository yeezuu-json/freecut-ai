#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# FreeCut AI — macOS build script
#
# Produces:  dist/FreeCut AI.app
# Requires:  uv, ffmpeg, ffprobe (via Homebrew is fine)
# Optional:  Apple Developer ID for code-signing + notarisation
#
# Usage:
#   chmod +x build_macos.sh
#   ./build_macos.sh                    # unsigned build
#   SIGN_IDENTITY="Developer ID Application: …" ./build_macos.sh
# ---------------------------------------------------------------------------
set -euo pipefail

APP_NAME="FreeCut AI"
BUNDLE_ID="com.freecut.ai"

# ── 1. Verify prerequisites ────────────────────────────────────────────────
echo "▶ Checking prerequisites…"
command -v uv    >/dev/null || { echo "ERROR: uv not found. Install from https://docs.astral.sh/uv/"; exit 1; }
command -v ffmpeg  >/dev/null || { echo "ERROR: ffmpeg not found. Run: brew install ffmpeg"; exit 1; }
command -v ffprobe >/dev/null || { echo "ERROR: ffprobe not found. Run: brew install ffmpeg"; exit 1; }

# ── 2. Copy ffmpeg binaries into bin/ so the spec can pick them up ─────────
echo "▶ Copying ffmpeg binaries…"
mkdir -p bin
cp "$(which ffmpeg)"  bin/ffmpeg
cp "$(which ffprobe)" bin/ffprobe

# ── 3. Clean previous build ───────────────────────────────────────────────
echo "▶ Cleaning previous build…"
rm -rf build dist

# ── 4. Run PyInstaller ────────────────────────────────────────────────────
echo "▶ Running PyInstaller…"
uv run pyinstaller freecut_ai.spec --noconfirm

# ── 5. Code-sign (optional) ───────────────────────────────────────────────
if [ -n "${SIGN_IDENTITY:-}" ]; then
    echo "▶ Code-signing with: $SIGN_IDENTITY"
    codesign --deep --force --verify --verbose \
        --options runtime \
        --entitlements entitlements.plist \
        --sign "$SIGN_IDENTITY" \
        "dist/${APP_NAME}.app"
    echo "▶ Verifying signature…"
    codesign --verify --deep --strict "dist/${APP_NAME}.app"
    spctl --assess --type execute "dist/${APP_NAME}.app" && echo "Gatekeeper: OK"
else
    echo "ℹ  Skipping code-sign (set SIGN_IDENTITY to enable)."
fi

# ── 6. Package into a DMG ─────────────────────────────────────────────────
if command -v create-dmg >/dev/null; then
    echo "▶ Creating DMG…"
    create-dmg \
        --volname "${APP_NAME}" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "${APP_NAME}.app" 175 190 \
        --hide-extension "${APP_NAME}.app" \
        --app-drop-link 425 190 \
        "dist/${APP_NAME}.dmg" \
        "dist/${APP_NAME}.app"
    echo "✅  DMG: dist/${APP_NAME}.dmg"
else
    echo "ℹ  create-dmg not found — skipping DMG. Install with: brew install create-dmg"
    echo "✅  App bundle: dist/${APP_NAME}.app"
fi

echo ""
echo "✅  Build complete!"
