@echo off
REM Build a standalone Windows .exe of the converter GUI with PyInstaller.
REM
REM Requirements: Python 3.10+ from python.org (tkinter is included)
REM Run this script ON WINDOWS (PyInstaller cannot cross-compile from Linux).
REM Output: dist\mc2sm.exe
cd /d "%~dp0"

python -m pip install --upgrade pyinstaller Pillow
if errorlevel 1 exit /b 1

python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name mc2sm ^
    --hidden-import PIL._tkinter_finder ^
    gui.py
if errorlevel 1 exit /b 1

echo.
echo Build complete: dist\mc2sm.exe
echo Note: the app downloads vanilla Minecraft assets next to the .exe on
echo first run, and reads resource packs from a "resourcepacks" folder there.
pause
