"""Convert OptiFine CEM (.jpm) box models into Minecraft block model elements."""

from __future__ import annotations

import json
from pathlib import Path

from assets_paths import normalize_assets_dir

_FACE_KEYS = ("north", "south", "east", "west", "up", "down")
_UV_KEYS = ("uvNorth", "uvSouth", "uvEast", "uvWest", "uvUp", "uvDown")


def _cem_box_to_element(box: dict, texture_var: str = "#bed") -> dict:
    x1, y1, z1, x2, y2, z2 = box["coordinates"]
    # CEM bed parts use 32 units per block axis; shift into 0–16 block space.
    scale = 0.5
    ox, oy, oz = 16.0, 16.0, 16.0
    from_coords = [
        (x1 + ox) * scale,
        (y1 + oy) * scale,
        (z1 + oz) * scale,
    ]
    to_coords = [
        (x2 + ox) * scale,
        (y2 + oy) * scale,
        (z2 + oz) * scale,
    ]
    for i in range(3):
        if from_coords[i] > to_coords[i]:
            from_coords[i], to_coords[i] = to_coords[i], from_coords[i]

    faces = {}
    for face, uv_key in zip(_FACE_KEYS, _UV_KEYS):
        if uv_key not in box:
            continue
        u1, v1, u2, v2 = box[uv_key]
        faces[face] = {
            "uv": [u1, v1, u2, v2],
            "texture": texture_var,
        }
    return {"from": from_coords, "to": to_coords, "faces": faces}


def load_cem_part(assets_dir, part: str) -> dict | None:
    """Load bed_head.jpm or bed_foot.jpm from any pack in the stack."""
    from asset_resolution import find_asset

    path = find_asset(f"minecraft/optifine/cem/bed_{part}.jpm", assets_dir)
    if path is None:
        base = normalize_assets_dir(assets_dir)
        path = base / "minecraft" / "optifine" / "cem" / f"bed_{part}.jpm"
        if not path.is_file():
            return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cem_part_to_model(assets_dir, part: str, color: str = "red") -> dict:
    """Build a resolved-style model dict from an OptiFine CEM bed part."""
    data = load_cem_part(assets_dir, part)
    if not data:
        return {"elements": [], "textures": {}}

    tex_path = f"minecraft:entity/bed/{color}"
    return {
        "textures": {"bed": tex_path, "particle": tex_path},
        "elements": [_cem_box_to_element(box, "#bed") for box in data.get("boxes", [])],
    }
