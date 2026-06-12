"""Transparent / partial blocks: per-block voxelize, hollow, and face-attach to structure."""

from block_model_aliases import is_sparse_shape_block
from block_voxels import block_appearance, voxelize_block_local
from config import VOXEL_SCALE
from blueprint_writer import GLASS_SHAPE_ID, get_shape_id_for_block, rgba_to_hex

TRANSPARENT_KEYWORDS = (
    "glass",
    "pane",
    "bars",
    "chain",
    "cobweb",
    "ice",
    "leaves",
    "trapdoor",
    "door",
    "fence",
    "fence_gate",
    "wall_torch",
    "torch",
    "ladder",
    "scaffolding",
    "slab",
    "stairs",
    "bed",
    "campfire",
    "chest",
    "anvil",
    "sign",
    "banner",
    "carpet",
    "pressure_plate",
    "button",
    "lever",
    "rail",
    "lantern",
    "candle",
    "flower_pot",
    "rod",
    "hanging",
    "wall",
)

# Solid blocks that look wrong when welded as full 16³ cells
TRANSPARENT_EXACT = frozenset({
    "glass",
    "stained_glass",
    "glass_pane",
    "stained_glass_pane",
    "iron_bars",
    "chain",
    "cobweb",
    "ice",
    "frosted_ice",
    "packed_ice",
    "blue_ice",
})

def _is_double_slab(block_name: str) -> bool:
    name = block_name.lower()
    return "double" in name and "slab" in name


def _keyword_matches(name: str, keyword: str) -> bool:
    if keyword == "wall":
        # cobblestone_wall etc. — NOT wall_torch / oak_wall_sign (own keywords)
        return name.endswith("_wall")
    if keyword == "bed":
        return name.endswith("_bed") or name == "bed"
    if keyword == "chest":
        return "chest" in name and not name.endswith("_chestplate")
    if keyword == "rod":
        return name.endswith("_rod") or "lightning_rod" in name
    if keyword == "slab":
        return "slab" in name
    if keyword == "stairs":
        return "stairs" in name
    return keyword in name


def is_transparent_block(block_name: str) -> bool:
    """
    Blocks that must use their MC model geometry and weld after structure hollow/merge.

    Includes glass, partial blocks (slabs, stairs), and sparse shapes (doors, fences, etc.).
    """
    name = block_name.lower()
    if name == "bedrock":
        return False
    if _is_double_slab(name):
        return False
    if name in TRANSPARENT_EXACT:
        return True
    if is_sparse_shape_block(block_name):
        return True
    if any(_keyword_matches(name, kw) for kw in TRANSPARENT_KEYWORDS):
        return True
    return False


def is_solid_neighbor_for_connections(block_name: str) -> bool:
    """Whether fences/walls should connect to this block like a solid face."""
    name = block_name.lower()
    if not is_transparent_block(name):
        return True
    if "slab" in name or "stairs" in name:
        return True
    if name.endswith("_wall") and "wall_torch" not in name:
        return True
    return False


def _needs_opaque_face_attach(block_name: str) -> bool:
    """Only thin see-through blocks need a weld sheet on adjacent opaque faces."""
    name = block_name.lower()
    if "glass" in name or "pane" in name:
        return True
    return name in ("iron_bars", "cobweb", "chain")


def get_shape_id_for_transparent(block_name: str) -> str:
    name = block_name.lower()
    if "glass" in name or "ice" in name:
        return GLASS_SHAPE_ID
    return get_shape_id_for_block(block_name)


def rotate_local_position(pos, xaxis, zaxis):
    x, y, z = pos["x"], pos["y"], pos["z"]
    if xaxis == 1 and zaxis == 3:
        return {"x": x, "y": y, "z": z}
    if xaxis == -1 and zaxis == 3:
        return {"x": VOXEL_SCALE - 1 - x, "y": y, "z": VOXEL_SCALE - 1 - z}
    if xaxis == 3 and zaxis == 1:
        return {"x": z, "y": y, "z": VOXEL_SCALE - 1 - x}
    if xaxis == -3 and zaxis == 1:
        return {"x": VOXEL_SCALE - 1 - z, "y": y, "z": x}
    return {"x": x, "y": y, "z": z}


def _local_face_coords(face: str, scale: int = VOXEL_SCALE):
    if face == "x_min":
        return [(0, y, z) for y in range(scale) for z in range(scale)]
    if face == "x_max":
        return [(scale - 1, y, z) for y in range(scale) for z in range(scale)]
    if face == "y_min":
        return [(x, 0, z) for x in range(scale) for z in range(scale)]
    if face == "y_max":
        return [(x, scale - 1, z) for x in range(scale) for z in range(scale)]
    if face == "z_min":
        return [(x, y, 0) for x in range(scale) for y in range(scale)]
    if face == "z_max":
        return [(x, y, scale - 1) for x in range(scale) for y in range(scale)]
    return []


# Local model coordinates are (x, y up, z) — same axes as MC block coordinates.
MC_FACE_NEIGHBORS = (
    ((1, 0, 0), "x_max"),
    ((-1, 0, 0), "x_min"),
    ((0, 1, 0), "y_max"),
    ((0, -1, 0), "y_min"),
    ((0, 0, 1), "z_max"),
    ((0, 0, -1), "z_min"),
)


def _local_to_parts(local_voxels, color_hex, shape_id, xaxis, zaxis):
    from config import CHALLENGE_GLASS_SHAPE_ID
    from dynamic_model_loader import CLEAR_GLASS_COLOR

    parts = []
    for (lx, ly, lz), color in local_voxels.items():
        voxel_shape = shape_id
        if isinstance(color, tuple):
            # Clear-glass filler voxels use a distinct glass part type so the
            # uncolored interior of glass blocks reads as clear, not painted.
            if color == CLEAR_GLASS_COLOR:
                voxel_shape = CHALLENGE_GLASS_SHAPE_ID
            hex_color = rgba_to_hex(color)
        elif isinstance(color, str):
            hex_color = color.upper()
        else:
            hex_color = color_hex
        parts.append({
            "bounds": {"x": 1, "y": 1, "z": 1},
            "shapeId": voxel_shape,
            "color": hex_color,
            "pos": {"x": float(lx), "y": float(ly), "z": float(lz)},
            "xaxis": xaxis,
            "zaxis": zaxis,
            "is_transparent": True,
        })
    return parts


def _global_transparent_hollow(parts, opaque_mc_positions):
    """
    Remove interior voxels across the WHOLE transparent set (not per block) so
    adjacent slabs/stairs don't keep hidden walls between cells. A voxel is
    interior when all 6 neighbors are transparent voxels or opaque MC cells.
    """
    occupied = {
        (int(p["pos"]["x"]), int(p["pos"]["y"]), int(p["pos"]["z"])) for p in parts
    }

    def is_interior(pos):
        x, y, z = pos
        for dx, dy, dz in (
            (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
        ):
            n = (x + dx, y + dy, z + dz)
            if n in occupied:
                continue
            if (n[0] // VOXEL_SCALE, n[1] // VOXEL_SCALE, n[2] // VOXEL_SCALE) in opaque_mc_positions:
                continue
            return False
        return True

    return [
        p for p in parts
        if not is_interior((int(p["pos"]["x"]), int(p["pos"]["y"]), int(p["pos"]["z"])))
    ]


def build_all_transparent_blocks(
    transparent_mc_blocks,
    assets_dir,
    opaque_mc_positions,
    appearance_cache,
    block_at=None,
):
    """
    Voxelize and place all deferred transparent MC blocks, then hollow globally.
    Returns (parts, lamp_parts) — lamps from torches/lanterns/etc.
    """
    all_parts = []
    all_lamps = []
    for mc_block in transparent_mc_blocks:
        parts, lamps = build_transparent_block(
            mc_block,
            assets_dir,
            opaque_mc_positions,
            appearance_cache,
            block_at=block_at,
        )
        all_parts.extend(parts)
        all_lamps.extend(lamps)
    return _global_transparent_hollow(all_parts, opaque_mc_positions), all_lamps


def _attach_faces_to_opaque(local_voxels, mc_block, opaque_mc_positions, color_hex):
    """Add a 1-voxel face sheet on sides that touch opaque MC neighbors."""
    bx, by, bz = mc_block["x"], mc_block["y"], mc_block["z"]
    scale = VOXEL_SCALE

    for (dx, dy, dz), face in MC_FACE_NEIGHBORS:
        if (bx + dx, by + dy, bz + dz) not in opaque_mc_positions:
            continue
        face_coords = _local_face_coords(face, scale)
        if any(coord in local_voxels for coord in face_coords):
            continue
        for coord in face_coords:
            local_voxels[coord] = color_hex


def _place_in_world(local_parts, mc_block, xaxis, zaxis):
    bx, by, bz = mc_block["x"], mc_block["y"], mc_block["z"]
    world_parts = []
    for part in local_parts:
        lx = int(part["pos"]["x"])
        ly = int(part["pos"]["y"])
        lz = int(part["pos"]["z"])
        rotated = rotate_local_position({"x": lx, "y": ly, "z": lz}, xaxis, zaxis)
        sm_pos = {
            "x": bx * VOXEL_SCALE + rotated["x"],
            "y": by * VOXEL_SCALE + rotated["y"],
            "z": bz * VOXEL_SCALE + rotated["z"],
        }
        world_parts.append({
            **part,
            "pos": {"x": float(sm_pos["x"]), "y": float(sm_pos["y"]), "z": float(sm_pos["z"])},
            "xaxis": xaxis,
            "zaxis": zaxis,
            "is_transparent": True,
        })
    return world_parts


_LAVA_COLOR = (0xCF, 0x5C, 0x10, 255)


def _fluid_cube_voxels(block_name):
    from block_tints import WATER_TINT

    if block_name == "water":
        color = (WATER_TINT[0], WATER_TINT[1], WATER_TINT[2], 255)
    else:
        color = _LAVA_COLOR
    return {
        (x, y, z): color
        for x in range(VOXEL_SCALE)
        for y in range(VOXEL_SCALE)
        for z in range(VOXEL_SCALE)
    }


def build_transparent_block(mc_block, assets_dir, opaque_mc_positions, appearance_cache, block_at=None):
    """
    Voxelize a transparent MC block, attach to opaque neighbors.
    Returns (parts, lamp_parts).
    """
    block_name = mc_block["name"]

    from block_placement import placement_rotation
    from blockstate_resolver import resolved_block_properties
    from conversion_settings import CURRENT as settings
    from light_emission import extract_lamps, is_light_block

    xaxis, zaxis = placement_rotation(mc_block, assets_dir, block_at=block_at)

    if block_name in ("water", "lava"):
        local_voxels = _fluid_cube_voxels(block_name)
        shape_id = (
            GLASS_SHAPE_ID
            if block_name == "water" and settings.water_mode == "glass"
            else get_shape_id_for_block(block_name)
        )
        color_hex = rgba_to_hex(next(iter(local_voxels.values()))[:3])
        lamps = []
        if block_name == "lava":
            lamps = extract_lamps(mc_block, local_voxels, opaque_mc_positions, settings)
        parts = _local_to_parts(local_voxels, color_hex, shape_id, xaxis, zaxis)
        return _place_in_world(parts, mc_block, xaxis, zaxis), lamps

    props = resolved_block_properties(block_name, mc_block, block_at)
    geo_key = ("__geo__", block_name, tuple(sorted(props.items())))
    if geo_key in appearance_cache:
        local_voxels = dict(appearance_cache[geo_key])
    else:
        local_voxels = dict(
            voxelize_block_local(
                block_name, assets_dir, mc_block=mc_block, block_at=block_at
            )
        )
        appearance_cache[geo_key] = dict(local_voxels)
    if not local_voxels:
        if block_name not in appearance_cache:
            appearance_cache[block_name] = block_appearance(
                block_name,
                assets_dir,
                mc_block=mc_block,
                block_at=block_at,
            )
        appearance = appearance_cache[block_name]
        cx = cy = cz = VOXEL_SCALE // 2
        local_voxels = {(cx, cy, cz): appearance["color"]}
        color_hex = appearance["color"]
        shape_id = appearance.get("shapeId") or get_shape_id_for_transparent(block_name)
    else:
        appearance = block_appearance(
            block_name,
            assets_dir,
            local_voxels=local_voxels,
            mc_block=mc_block,
            block_at=block_at,
        )
        color_hex = appearance["color"]
        shape_id = get_shape_id_for_transparent(block_name)

    lamps = []
    if is_light_block(block_name, props):
        lamps = extract_lamps(mc_block, local_voxels, opaque_mc_positions, settings)

    if _needs_opaque_face_attach(block_name):
        _attach_faces_to_opaque(local_voxels, mc_block, opaque_mc_positions, color_hex)

    local_parts = _local_to_parts(local_voxels, color_hex, shape_id, xaxis, zaxis)

    # Hollowing happens globally in build_all_transparent_blocks — per-block
    # hollow would keep hidden walls between adjacent slabs/stairs.
    return _place_in_world(local_parts, mc_block, xaxis, zaxis), lamps
