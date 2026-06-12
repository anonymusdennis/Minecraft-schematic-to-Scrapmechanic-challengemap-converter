"""Render schematic entities (paintings, item frames) as SM parts.

Paintings map 1:1 — each texture pixel becomes one voxel of a 1-voxel-thick
sheet hanging on the wall the painting faces away from.
"""

from __future__ import annotations

from blueprint_writer import rgba_to_hex
from config import DEFAULT_SHAPE_ID, VOXEL_SCALE

# Painting/item-frame facing: 0=south, 1=west, 2=north, 3=east
_FACING_BYTE = {0: "south", 1: "west", 2: "north", 3: "east"}

# MC direction vectors (x, y, z) the entity FACES (away from the wall)
_FACING_DIR = {
    "south": (0, 0, 1),
    "west": (-1, 0, 0),
    "north": (0, 0, -1),
    "east": (1, 0, 0),
}


def _entity_facing(data: dict) -> str:
    for key in ("facing", "Facing", "Dir", "direction"):
        if key in data:
            value = data[key]
            if isinstance(value, str):
                return value if value in _FACING_DIR else "south"
            return _FACING_BYTE.get(int(value) % 4, "south")
    return "south"


def _entity_variant(data: dict) -> str:
    for key in ("variant", "Variant", "Motive", "motive"):
        if key in data:
            value = str(data[key])
            if ":" in value:
                value = value.split(":", 1)[1]
            return value
    return "kebab"


def _entity_block_pos(entity: dict) -> tuple[int, int, int]:
    data = entity.get("data", {})
    if all(k in data for k in ("TileX", "TileY", "TileZ")):
        return int(data["TileX"]), int(data["TileY"]), int(data["TileZ"])
    pos = entity.get("pos", [0, 0, 0])
    import math

    return (
        int(math.floor(float(pos[0]))),
        int(math.floor(float(pos[1]))),
        int(math.floor(float(pos[2]))),
    )


def _painting_texture(variant: str, assets_dir):
    from asset_resolution import find_texture_file
    from texture_loader import load_texture

    path = find_texture_file(f"painting/{variant}.png", assets_dir)
    if path is None:
        return None
    return load_texture(str(path), warn=False)


def _sheet_part(world_pos, color_hex) -> dict:
    return {
        "bounds": {"x": 1, "y": 1, "z": 1},
        "shapeId": DEFAULT_SHAPE_ID,
        "color": color_hex,
        "pos": {"x": float(world_pos[0]), "y": float(world_pos[1]), "z": float(world_pos[2])},
        "xaxis": 1,
        "zaxis": 3,
        "is_transparent": True,
    }


def build_painting_parts(entity: dict, assets_dir) -> list[dict]:
    """
    One voxel per texture pixel, hung flat against the wall behind the
    painting. The anchor block is the painting's bottom-left tile.
    """
    data = entity.get("data", {})
    facing = _entity_facing(data)
    variant = _entity_variant(data)
    img = _painting_texture(variant, assets_dir)
    if img is None:
        print(f"Warning: painting texture not found: {variant}")
        return []

    width_px, height_px = img.size  # 16 px per MC block — matches 16 voxels/cell
    bx, by, bz = _entity_block_pos(entity)

    # The sheet sits on the back face of the anchor cell (against the wall)
    base_x = bx * VOXEL_SCALE
    base_y = by * VOXEL_SCALE
    base_z = bz * VOXEL_SCALE
    parts = []
    pixels = img.load()

    for px in range(width_px):
        for py in range(height_px):
            color = pixels[px, height_px - 1 - py]  # py = up
            if len(color) > 3 and color[3] < 128:
                continue
            color_hex = rgba_to_hex(color[:3])
            if facing == "south":
                pos = (base_x + px, base_y + py, base_z)
            elif facing == "north":
                pos = (base_x + (width_px - 1 - px), base_y + py, base_z + VOXEL_SCALE - 1)
            elif facing == "east":
                pos = (base_x, base_y + py, base_z + (width_px - 1 - px))
            else:  # west
                pos = (base_x + VOXEL_SCALE - 1, base_y + py, base_z + px)
            parts.append(_sheet_part(pos, color_hex))
    return parts


_FRAME_COLOR = "8A6A47"  # birch-ish wood


def build_item_frame_parts(entity: dict) -> list[dict]:
    """Simple 12x12 wooden frame outline on the wall face."""
    data = entity.get("data", {})
    facing = _entity_facing(data)
    bx, by, bz = _entity_block_pos(entity)
    base_x, base_y, base_z = bx * VOXEL_SCALE, by * VOXEL_SCALE, bz * VOXEL_SCALE

    parts = []
    for u in range(2, 14):
        for v in range(2, 14):
            if u not in (2, 13) and v not in (2, 13):
                continue
            if facing == "south":
                pos = (base_x + u, base_y + v, base_z)
            elif facing == "north":
                pos = (base_x + u, base_y + v, base_z + VOXEL_SCALE - 1)
            elif facing == "east":
                pos = (base_x, base_y + v, base_z + u)
            else:
                pos = (base_x + VOXEL_SCALE - 1, base_y + v, base_z + u)
            parts.append(_sheet_part(pos, _FRAME_COLOR))
    return parts


def build_entity_parts(entities: list, assets_dir) -> list[dict]:
    """Render all supported entities; unsupported types are skipped."""
    parts = []
    skipped = {}
    for entity in entities or []:
        eid = entity.get("id", "")
        if eid == "painting":
            parts.extend(build_painting_parts(entity, assets_dir))
        elif eid in ("item_frame", "glow_item_frame"):
            parts.extend(build_item_frame_parts(entity))
        else:
            skipped[eid] = skipped.get(eid, 0) + 1
    if skipped:
        names = ", ".join(f"{k} x{v}" for k, v in sorted(skipped.items()))
        print(f"  Skipped unsupported entities: {names}")
    if parts:
        print(f"  Entities rendered: {len(parts)} voxels")
    return parts
