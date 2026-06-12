#!/usr/bin/env bash
# Build a standalone Linux binary of the converter GUI with PyInstaller.
#
# Requirements: python3, python3-tk (sudo apt install python3-tk), pip
# Output: dist/mc2sm  (single self-contained executable)
set -euo pipefail
cd "$(dirname "$0")"

python3 -c "import tkinter" 2>/dev/null || {
    echo "ERROR: tkinter missing. Install it first:  sudo apt install python3-tk"
    exit 1
}

python3 -m pip install --user --upgrade pyinstaller Pillow

python3 -m PyInstaller \
    --noconfirm \
    --onefile \
    --windowed \
    --name mc2sm \
    --hidden-import PIL._tkinter_finder \
    gui.py

echo
echo "Build complete: dist/mc2sm"
echo "Note: the app downloads vanilla Minecraft assets next to the binary on"
echo "first run, and reads resource packs from a 'resourcepacks' folder there."
