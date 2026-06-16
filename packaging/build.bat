@echo off
REM Run from the repo root so the spec's relative paths (src\, launcher.py) resolve.
cd /d "%~dp0.."

echo [1/3] Cleaning previous build...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo [2/3] Running PyInstaller...
python -m PyInstaller packaging\briefing.spec --noconfirm

echo [3/3] Done!
echo Output: dist\briefing\briefing.exe
pause
