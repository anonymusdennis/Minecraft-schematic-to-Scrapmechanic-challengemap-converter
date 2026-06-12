@echo off
REM Build a standalone Windows .exe of the converter GUI with PyInstaller.
REM
REM Requirements: Python 3.10+ from python.org (tkinter is included)
REM Run this script ON WINDOWS (PyInstaller cannot cross-compile from Linux).
REM Output: dist\mc2sm.exe
cd /d "%~dp0"

python -m pip install --upgrade pyinstaller Pillow
if errorlevel 1 exit /b 1

if not exist resourcepacks (
    echo ERROR: resourcepacks folder missing - the bundled 3D packs are a required dependency.
    exit /b 1
)

python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name mc2sm ^
    --hidden-import PIL._tkinter_finder ^
    --add-data "resourcepacks;resourcepacks" ^
    gui.py
if errorlevel 1 exit /b 1

echo.
echo Build complete: dist\mc2sm.exe
echo The required 3D resource packs are embedded in the .exe and unpack into
echo a "resourcepacks" folder next to it on first run. Vanilla assets are
echo downloaded next to the .exe on first run as well.
pause
