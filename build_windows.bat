@echo off
REM ---------------------------------------------------------------------------
REM FreeCut AI - Windows build script
REM
REM Produces:  dist\FreeCut AI\FreeCut AI.exe
REM Requires:  uv, ffmpeg/ffprobe in PATH or in bin\
REM
REM Usage:
REM   build_windows.bat
REM ---------------------------------------------------------------------------

setlocal enabledelayedexpansion
set APP_NAME=FreeCut AI

echo ^> Checking prerequisites...
where uv >nul 2>&1 || (echo ERROR: uv not found. Install from https://docs.astral.sh/uv/ & exit /b 1)

REM ── Copy ffmpeg binaries into bin\ ─────────────────────────────────────
echo ^> Copying ffmpeg binaries...
if not exist bin mkdir bin

for /f "tokens=*" %%i in ('where ffmpeg 2^>nul') do (
    copy "%%i" bin\ffmpeg.exe >nul 2>&1
    goto :ffmpeg_done
)
echo WARNING: ffmpeg not found in PATH. Download from https://ffmpeg.org/download.html
echo          and place ffmpeg.exe + ffprobe.exe in the bin\ folder.
:ffmpeg_done

for /f "tokens=*" %%i in ('where ffprobe 2^>nul') do (
    copy "%%i" bin\ffprobe.exe >nul 2>&1
    goto :ffprobe_done
)
:ffprobe_done

REM ── Clean previous build ──────────────────────────────────────────────
echo ^> Cleaning previous build...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

REM ── Run PyInstaller ───────────────────────────────────────────────────
echo ^> Running PyInstaller...
uv run pyinstaller freecut_ai.spec --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller failed.
    exit /b 1
)

echo.
echo ✅  Build complete!
echo     Executable: dist\%APP_NAME%\%APP_NAME%.exe
echo.
echo To create an installer, install Inno Setup (https://jrsoftware.org/isinfo.php)
echo and run: iscc freecut_ai_installer.iss
