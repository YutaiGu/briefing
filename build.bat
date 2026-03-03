@echo off
echo [1/3] Cleaning previous build...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo [2/3] Running PyInstaller...
D:\anaconda3\envs\ct\python.exe -m PyInstaller briefing.spec --noconfirm

echo [3/3] Done!
echo Output: dist\briefing\briefing.exe
pause
