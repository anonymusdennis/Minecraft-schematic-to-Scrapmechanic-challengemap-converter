"""Allocate unique numbered challenge map names."""

import json
import re
from pathlib import Path


def _normalize_base_name(name: str) -> str:
    """Strip an existing version suffix so --name groups with prior exports."""
    stripped = name.strip()
    stripped = re.sub(r"\s+#\d+$", "", stripped)
    stripped = re.sub(r"\s+\(\d+\)$", "", stripped)
    stripped = re.sub(r"\s+\d+$", "", stripped)
    return stripped or name.strip()


def _parse_version_number(base_name: str, existing_name: str) -> int | None:
    """Return the version number if *existing_name* matches *base_name*."""
    if existing_name == base_name:
        return 1

    for pattern in (
        rf"^{re.escape(base_name)}\s+#(\d+)$",
        rf"^{re.escape(base_name)}\s+\((\d+)\)$",
        rf"^{re.escape(base_name)}\s+(\d+)$",
    ):
        match = re.match(pattern, existing_name)
        if match:
            return int(match.group(1))

    return None


def _existing_numbers(base_name: str, output_dir: Path) -> list:
    """Read challenge folders and collect used numbers for this base name."""
    numbers = []
    if not output_dir.is_dir():
        return numbers

    for child in output_dir.iterdir():
        if not child.is_dir():
            continue
        desc_path = child / "description.json"
        if not desc_path.is_file():
            continue
        try:
            with open(desc_path, encoding="utf-8") as f:
                existing_name = json.load(f).get("name", "")
        except (json.JSONDecodeError, OSError):
            continue

        version = _parse_version_number(base_name, existing_name)
        if version is not None:
            numbers.append(version)

    return numbers


def allocate_map_name(base_name: str, output_dir: Path) -> str:
    """
    Return the next available name: ``{base} 1``, ``{base} 2``, ...

    Uses a plain space + number (no ``#``) because Scrap Mechanic treats ``#``
    as a localization tag and hides everything from ``#`` onward in the UI.
    """
    base = _normalize_base_name(base_name)
    used = _existing_numbers(base, Path(output_dir))
    next_num = max(used, default=0) + 1
    return f"{base} {next_num}"
