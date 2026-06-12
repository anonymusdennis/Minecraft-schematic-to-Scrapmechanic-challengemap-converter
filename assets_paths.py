"""Resolve Minecraft asset and texture paths under a resource pack."""

import os
from pathlib import Path


def normalize_assets_dir(assets_dir) -> Path:
    """
    Return the pack ``assets`` root (the folder that contains ``minecraft/``).

    Accepts either ``.../MyResourcePack/assets`` or ``.../MyResourcePack/assets/minecraft``.
    """
    base = assets_dir if isinstance(assets_dir, Path) else Path(assets_dir)
    if (base / "minecraft" / "textures").is_dir():
        return base
    if base.name == "minecraft" and (base / "textures").is_dir():
        return base.parent
    return base


def texture_file_path(assets_dir, relative: str) -> Path:
    """Build ``<assets>/minecraft/textures/<relative>``."""
    rel = relative.replace("\\", "/").lstrip("/")
    if rel.startswith("minecraft/textures/"):
        rel = rel[len("minecraft/textures/") :]
    return normalize_assets_dir(assets_dir) / "minecraft" / "textures" / rel.replace("/", os.sep)
