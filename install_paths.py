"""Auto-detect Scrap Mechanic Challenges folders on Linux (Steam/Proton) and Windows."""

from __future__ import annotations

import os
import re
from pathlib import Path

_SM_APP_ID = "387990"
_SM_USERDATA_REL = (
    f"steamapps/compatdata/{_SM_APP_ID}/pfx/drive_c/users/steamuser"
    "/AppData/Roaming/Axolot Games/Scrap Mechanic/User"
)


def _steam_roots() -> list[Path]:
    home = Path.home()
    roots = [
        home / ".local/share/Steam",
        home / ".steam/steam",
        home / ".steam/root",
        home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",  # Flatpak
    ]
    seen = set()
    result = []
    for root in roots:
        if root.is_dir():
            resolved = root.resolve()
            if resolved not in seen:
                seen.add(resolved)
                result.append(resolved)
    return result


def _library_folders(steam_root: Path) -> list[Path]:
    """Steam library roots from libraryfolders.vdf (plus the root itself)."""
    libraries = [steam_root]
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    if vdf.is_file():
        try:
            text = vdf.read_text(encoding="utf-8", errors="ignore")
            for match in re.finditer(r'"path"\s+"([^"]+)"', text):
                path = Path(match.group(1))
                if path.is_dir():
                    libraries.append(path)
        except OSError:
            pass
    return libraries


def detect_challenge_dirs() -> list[Path]:
    """All Scrap Mechanic Challenges folders found on this machine."""
    found: list[Path] = []
    seen = set()

    def _add(path: Path):
        if path.is_dir():
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                found.append(resolved)

    # Windows native
    appdata = os.environ.get("APPDATA")
    if appdata:
        user_root = Path(appdata) / "Axolot Games/Scrap Mechanic/User"
        if user_root.is_dir():
            for user_dir in sorted(user_root.glob("User_*")):
                _add(user_dir / "Challenges")

    # Linux: Steam/Proton prefixes in every library
    for steam_root in _steam_roots():
        for library in _library_folders(steam_root):
            user_root = library / _SM_USERDATA_REL
            if user_root.is_dir():
                for user_dir in sorted(user_root.glob("User_*")):
                    _add(user_dir / "Challenges")

    return found


def default_challenge_dir() -> Path | None:
    from config import SM_CHALLENGES_DIR

    if SM_CHALLENGES_DIR.is_dir():
        return SM_CHALLENGES_DIR
    detected = detect_challenge_dirs()
    return detected[0] if detected else None


def find_existing_challenges(output_dir: Path, name: str) -> list[tuple[Path, str]]:
    """Challenge folders whose display name matches *name* (or numbered variants)."""
    matches = []
    if not output_dir.is_dir():
        return matches
    import json

    pattern = re.compile(rf"^{re.escape(name)}(?:\s+\d+)?$", re.IGNORECASE)
    for desc in output_dir.glob("*/description.json"):
        try:
            with open(desc, encoding="utf-8") as f:
                data = json.load(f)
            existing = str(data.get("name", ""))
            if pattern.match(existing.strip()):
                matches.append((desc.parent, existing))
        except (OSError, json.JSONDecodeError):
            continue
    return matches
