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

# Install build deps only when missing (Debian 13+ blocks global pip installs)
python3 -m PyInstaller --version >/dev/null 2>&1 || \
    python3 -m pip install --user --upgrade pyinstaller Pillow || \
    python3 -m pip install --user --break-system-packages --upgrade pyinstaller Pillow

[ -d resourcepacks ] || {
    echo "ERROR: resourcepacks/ missing — the bundled 3D packs are a required dependency."
    exit 1
}

python3 -m PyInstaller \
    --noconfirm \
    --onefile \
    --windowed \
    --name mc2sm \
    --hidden-import PIL._tkinter_finder \
    --add-data "resourcepacks:resourcepacks" \
    gui.py

echo
echo "Build complete: dist/mc2sm"
echo "The required 3D resource packs are embedded in the binary and unpack"
echo "into a 'resourcepacks' folder next to it on first run. Vanilla assets"
echo "are downloaded next to the binary on first run as well."
