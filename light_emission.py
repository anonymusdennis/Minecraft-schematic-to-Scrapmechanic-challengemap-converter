"""Place real SM lamps (headlight parts) on light-emitting Minecraft blocks.

Two placement modes:
- "embed" (default): lamps are glitchwelded INSIDE existing surface voxels —
  no cutout, the lamp is hidden inside the block and shines through.
- "replace": the surface voxel is removed and the lamp takes its place.

Lamps are placed on all 6 faces of a light block, ``lamps_per_face`` each, in
a symmetrical pattern spreading from the face center. Each lamp faces outward
and is painted the color of the voxel it sits in/replaces. Luminance scales
with the block's Minecraft light level.
"""

from __future__ import annotations

from blueprint_writer import rgba_to_hex
from config import VOXEL_SCALE

HEADLIGHT_SHAPE_ID = "ed27f5e2-cac5-4a32-a5d9-49f116acc6af"

# Minecraft light levels (0-15) for emitting blocks
LIGHT_BLOCKS = {
    "glowstone": 15,
    "sea_lantern": 15,
    "shroomlight": 15,
    "ochre_froglight": 15,
    "verdant_froglight": 15,
    "pearlescent_froglight": 15,
    "jack_o_lantern": 15,
    "lantern": 15,
    "soul_lantern": 10,
    "copper_lantern": 15,
    "beacon": 15,
    "conduit": 15,
    "campfire": 15,
    "soul_campfire": 10,
    "lava": 15,
    "fire": 15,
    "soul_fire": 10,
    "torch": 14,
    "wall_torch": 14,
    "soul_torch": 10,
    "soul_wall_torch": 10,
    "end_rod": 14,
    "redstone_lamp": 15,  # only when lit
    "glow_lichen": 7,
    "crying_obsidian": 10,
    "magma_block": 3,
    "amethyst_cluster": 5,
    "sculk_catalyst": 6,
    "redstone_torch": 7,
    "redstone_wall_torch": 7,
}

_LIT_REQUIRED = frozenset({"redstone_lamp", "furnace", "blast_furnace", "smoker", "campfire", "soul_campfire"})

# Flame-orange reference for picking the brightest-looking pixel on sparse models
_FLAME_RGB = (255, 165, 0)

_AXIS_VECTORS = {
    1: (1, 0, 0), -1: (-1, 0, 0),
    2: (0, 1, 0), -2: (0, -1, 0),
    3: (0, 0, 1), -3: (0, 0, -1),
}
_DIR_AXIS_CODE = {v: k for k, v in _AXIS_VECTORS.items()}

# All 6 outward directions (up first so single-lamp sparse blocks light their flame)
_DIRECTIONS = ((0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1), (1, 0, 0), (-1, 0, 0))

_next_controller_id = 1


def reset_controller_ids(start: int = 1):
    global _next_controller_id
    _next_controller_id = start


def _take_controller_id() -> int:
    global _next_controller_id
    cid = _next_controller_id
    _next_controller_id += 1
    return cid


def light_level(block_name: str, props: dict | None = None) -> int:
    name = block_name.lower()
    if ":" in name:
        name = name.split(":", 1)[1]
    level = LIGHT_BLOCKS.get(name, 0)
    if not level:
        return 0
    if name in _LIT_REQUIRED:
        lit = str((props or {}).get("lit", "true")).lower()
        if lit != "true":
            return 0
    return level


def is_light_block(block_name: str, props: dict | None = None) -> bool:
    return light_level(block_name, props) > 0


def _color_to_rgb(color) -> tuple[int, int, int]:
    if isinstance(color, tuple):
        return color[0], color[1], color[2]
    s = str(color).lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def _orange_distance(color) -> int:
    r, g, b = _color_to_rgb(color)
    return (
        (r - _FLAME_RGB[0]) ** 2
        + (g - _FLAME_RGB[1]) ** 2
        + (b - _FLAME_RGB[2]) ** 2
    )


def _rotation_columns(xaxis: int, zaxis: int):
    """Local X/Y/Z axes in world space (y = z cross x, right-handed)."""
    x = _AXIS_VECTORS[xaxis]
    z = _AXIS_VECTORS[zaxis]
    y = (
        z[1] * x[2] - z[2] * x[1],
        z[2] * x[0] - z[0] * x[2],
        z[0] * x[1] - z[1] * x[0],
    )
    return x, y, z


def _pos_for_cell(cell, xaxis: int, zaxis: int):
    """
    Blueprint 'pos' so a rotated 1x1x1 part occupies world cell *cell*.

    SM part positions are the part's local origin; rotation can swing the
    unit box into negative world directions, so compensate with the negative
    row sums of the rotation matrix. (This was the cause of lamps appearing
    offset from their cutout.)
    """
    cols = _rotation_columns(xaxis, zaxis)
    offset = [0, 0, 0]
    for world_axis in range(3):
        for col in cols:
            if col[world_axis] < 0:
                offset[world_axis] += col[world_axis]
    return (
        cell[0] - offset[0],
        cell[1] - offset[1],
        cell[2] - offset[2],
    )


def _axes_for_direction(direction) -> tuple[int, int]:
    """xaxis/zaxis so the headlight beam (local +Z) points along *direction*."""
    zaxis = _DIR_AXIS_CODE[direction]
    xaxis = 2 if abs(zaxis) == 1 else 1
    return xaxis, zaxis


def make_lamp_part(cell, direction, color, luminance: int) -> dict:
    xaxis, zaxis = _axes_for_direction(direction)
    pos = _pos_for_cell(cell, xaxis, zaxis)
    color_hex = color if isinstance(color, str) else rgba_to_hex(color)
    return {
        "shapeId": HEADLIGHT_SHAPE_ID,
        "color": color_hex.upper(),
        "controller": {
            "color": color_hex.upper(),
            "coneAngle": 0,
            "id": _take_controller_id(),
            "luminance": int(max(1, min(100, luminance))),
        },
        "pos": {"x": float(pos[0]), "y": float(pos[1]), "z": float(pos[2])},
        "xaxis": xaxis,
        "zaxis": zaxis,
        "is_lamp": True,
        "is_transparent": False,
        # World cell the lamp occupies (pos alone is rotation-dependent)
        "occupied_cell": (int(cell[0]), int(cell[1]), int(cell[2])),
    }


def _face_pattern_offsets(count: int) -> list[tuple[int, int]]:
    """
    Symmetric (u, v) offsets on a 16x16 face, spreading from the center.
    1 lamp -> face center; 4 -> centered quad; n -> even grid.
    """
    if count <= 1:
        return [(8, 8)]
    import math

    k = max(1, math.ceil(math.sqrt(count)))
    grid = []
    for i in range(k):
        for j in range(k):
            u = round((i + 0.5) * VOXEL_SCALE / k)
            v = round((j + 0.5) * VOXEL_SCALE / k)
            grid.append((min(u, VOXEL_SCALE - 1), min(v, VOXEL_SCALE - 1)))
    grid.sort(key=lambda p: (p[0] - 7.5) ** 2 + (p[1] - 7.5) ** 2)
    return grid[:count]


def _face_cells_full_cube(direction, count: int) -> list[tuple]:
    """Lamp cells on one face of a full 16-cube, symmetric around the center."""
    dx, dy, dz = direction
    axis = 0 if dx else (1 if dy else 2)
    layer = VOXEL_SCALE - 1 if (dx + dy + dz) > 0 else 0

    cells = []
    for u, v in _face_pattern_offsets(count):
        cell = [0, 0, 0]
        cell[axis] = layer
        other = [a for a in range(3) if a != axis]
        cell[other[0]] = u
        cell[other[1]] = v
        cells.append(tuple(cell))
    return cells


def _face_cells_sparse(local_voxels, direction, count: int) -> list[tuple]:
    """Outermost voxels along *direction*, preferring flame-orange pixels."""
    dx, dy, dz = direction
    axis = 0 if dx else (1 if dy else 2)
    sign = dx + dy + dz

    extreme = None
    for pos in local_voxels:
        v = pos[axis]
        if extreme is None or (sign > 0 and v > extreme) or (sign < 0 and v < extreme):
            extreme = v
    if extreme is None:
        return []

    layer = [pos for pos in local_voxels if pos[axis] == extreme]
    layer.sort(key=lambda p: _orange_distance(local_voxels[p]))
    return layer[:count]


def extract_lamps(
    mc_block: dict,
    local_voxels: dict,
    opaque_mc_positions: set,
    settings,
) -> list[dict]:
    """
    Build lamp parts for a light-emitting block.

    embed mode: voxels stay; lamps are glitchwelded inside surface voxels.
    replace mode: chosen voxels are popped from *local_voxels* (mutated).
    """
    from blockstate_resolver import block_properties

    if not settings.lights_enabled or not local_voxels:
        return []

    name = mc_block["name"]
    props = block_properties(mc_block)
    level = light_level(name, props)
    if not level:
        return []

    bx, by, bz = mc_block["x"], mc_block["y"], mc_block["z"]
    luminance = max(1, round(settings.lamp_luminance * level / 15))
    per_face = max(1, settings.lamps_per_face)
    replace = settings.light_mode == "replace"
    is_full_cube = len(local_voxels) >= VOXEL_SCALE ** 3

    lamps = []
    for direction in _DIRECTIONS:
        if is_full_cube and not replace:
            cells = _face_cells_full_cube(direction, per_face)
        else:
            cells = _face_cells_sparse(local_voxels, direction, per_face)
        for cell in cells:
            if cell not in local_voxels:
                continue
            if replace:
                color = local_voxels.pop(cell)
            else:
                color = local_voxels[cell]
            world = (
                bx * VOXEL_SCALE + cell[0],
                by * VOXEL_SCALE + cell[1],
                bz * VOXEL_SCALE + cell[2],
            )
            lamps.append(make_lamp_part(world, direction, color, luminance))

    return lamps
