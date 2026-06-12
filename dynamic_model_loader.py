"""Discover and load block geometry from blockstate, item, CEM, and supplement assets."""

from __future__ import annotations

import os
from pathlib import Path

from assets_paths import normalize_assets_dir
from cem_parser import cem_part_to_model
from config import VOXEL_SCALE

PROJECT_ROOT = Path(__file__).resolve().parent
SUPPLEMENT_DIR = PROJECT_ROOT / "supplement_assets" / "minecraft"

# Sentinel color (alpha 254) marking "clear glass" filler voxels — rendered
# with the clear/challenge glass shape instead of painted armored glass.
CLEAR_GLASS_COLOR = (255, 255, 255, 254)

# Blocks whose vanilla block JSON has no elements (block-entity rendered).
_ENTITY_BLOCKS = frozenset({
    "chest", "trapped_chest", "ender_chest", "bed",
    "copper_chest", "exposed_copper_chest", "weathered_copper_chest", "oxidized_copper_chest",
})

_CHEST_TEXTURE_MAP = {
    "chest": "custom_textures/chest/normal",
    "trapped_chest": "custom_textures/chest/trapped",
    "ender_chest": "custom_textures/chest/ender",
    "copper_chest": "custom_textures/chest/copper",
    "exposed_copper_chest": "custom_textures/chest/copper_exposed",
    "weathered_copper_chest": "custom_textures/chest/copper_weathered",
    "oxidized_copper_chest": "custom_textures/chest/copper_oxidized",
}

_CHEST_DOUBLE_TEXTURE_SUFFIX = {
    "left": "_left",
    "right": "_right",
    "single": "",
}


def _assets_base(assets_dir) -> Path:
    return normalize_assets_dir(assets_dir)


def _model_file(base: Path, model_type: str, model_path: str) -> Path:
    rel = model_path
    if rel.startswith("minecraft:"):
        rel = rel.split(":", 1)[1]
    for prefix in ("block/", "item/"):
        if rel.startswith(prefix):
            rel = rel[len(prefix):]
            break
    return base / "minecraft" / "models" / model_type / f"{rel}.json"


def load_model_any(model_ref: str, assets_dir, model_type: str = "block") -> dict:
    """
    Load a model for geometry. Searches the whole pack stack and prefers the
    first candidate with detailed 3D elements ("3D for everything"): flat or
    plain-cube models from higher-priority packs are skipped when a 3D pack
    lower in the stack provides real geometry for the same model name.
    """
    from model_parser import load_model_prefer_3d

    base = str(_assets_base(assets_dir))
    path = model_ref
    if not path.startswith("minecraft:"):
        path = f"minecraft:{model_type}/{model_ref}"
    return load_model_prefer_3d(path, base)


def model_has_geometry(model: dict) -> bool:
    return bool(model.get("elements"))


def _chest_item_name(block_name: str) -> str:
    name = block_name.lower()
    if name.startswith("waxed_"):
        name = name[len("waxed_"):]
    return name


def _chest_texture_ref(block_name: str, chest_type: str = "single") -> str:
    name = _chest_item_name(block_name)
    base = _CHEST_TEXTURE_MAP.get(name, _CHEST_TEXTURE_MAP["chest"])
    suffix = _CHEST_DOUBLE_TEXTURE_SUFFIX.get(chest_type, "")
    if suffix and not base.endswith(suffix):
        # entity/chest uses normal_left.png style names
        if "custom_textures/chest/" in base:
            variant = base.rsplit("/", 1)[-1]
            return f"entity/chest/{variant}{suffix}"
        return f"{base}{suffix}"
    return base


def _load_chest_item_model(block_name: str, assets_dir, chest_type: str = "single") -> dict:
    """Load template_chest_item geometry via the block's item model."""
    item_name = _chest_item_name(block_name)
    tex_ref = _chest_texture_ref(block_name, chest_type)

    try:
        model = load_model_any(item_name, assets_dir, model_type="item")
    except FileNotFoundError:
        model = load_model_any("template_chest_item", assets_dir, model_type="item")

    model = dict(model)
    textures = dict(model.get("textures", {}))
    textures["chest"] = f"minecraft:{tex_ref}"
    model["textures"] = textures

    # Drop the tiny lock/latch element — it voxelizes into an odd knob.
    elements = model.get("elements")
    if elements:
        kept = []
        for elem in elements:
            f, t = elem.get("from", (0, 0, 0)), elem.get("to", (0, 0, 0))
            volume = abs((t[0] - f[0]) * (t[1] - f[1]) * (t[2] - f[2]))
            if volume >= 64:  # latch is 2x4x1 = 8; chest body is ~2744
                kept.append(elem)
        if kept:
            model = dict(model)
            model["elements"] = kept
    return model


def _load_bed_cem_model(block_name: str, assets_dir, part: str = "foot") -> dict:
    from blockstate_resolver import block_properties

    color = block_name.replace("_bed", "") if block_name.endswith("_bed") else "red"
    props = {"part": part, "color": color}
    if block_name.endswith("_bed"):
        props["color"] = block_name.replace("_bed", "")
    return cem_part_to_model(assets_dir, part, props.get("color", "red"))


def _sign_wood(block_name: str) -> str:
    name = block_name.lower()
    for suffix in ("_wall_hanging_sign", "_hanging_sign", "_wall_sign", "_sign"):
        if name.endswith(suffix):
            wood = name[: -len(suffix)]
            return wood or "oak"
    return "oak"


def _sign_model(block_name: str, props: dict) -> dict | None:
    """Generated board/post geometry for signs (vanilla renders them as entities)."""
    name = block_name.lower()
    wood = _sign_wood(name)
    tex = f"minecraft:block/{wood}_planks"
    textures = {"board": tex, "particle": tex}

    def _faces(texture="#board"):
        return {f: {"texture": texture} for f in ("north", "south", "east", "west", "up", "down")}

    if name.endswith("_wall_sign"):
        elements = [
            {"from": [0, 4.5, 0], "to": [16, 12.5, 2], "faces": _faces()},
        ]
    elif name.endswith("_hanging_sign") or name.endswith("_wall_hanging_sign"):
        elements = [
            {"from": [1, 0, 7], "to": [15, 10, 9], "faces": _faces()},
            {"from": [3, 10, 7.5], "to": [4.5, 16, 8.5], "faces": _faces()},
            {"from": [11.5, 10, 7.5], "to": [13, 16, 8.5], "faces": _faces()},
        ]
    elif name.endswith("_sign"):
        elements = [
            {"from": [7, 0, 7], "to": [9, 9, 9], "faces": _faces()},
            {"from": [0, 9, 7], "to": [16, 17, 9], "faces": _faces()},
        ]
    else:
        return None
    return {"textures": textures, "elements": elements}


def _is_sign(block_name: str) -> bool:
    name = block_name.lower()
    return name.endswith(("_sign", "_wall_sign", "_hanging_sign", "_wall_hanging_sign"))


def _sign_y_rotation(block_name: str, props: dict) -> int:
    """Standing signs use rotation 0-15; wall signs use facing."""
    name = block_name.lower()
    if name.endswith("_wall_sign") or name.endswith("_wall_hanging_sign"):
        facing = props.get("facing", "north")
        # Board faces away from the wall; the base board faces north/south.
        return {"north": 0, "east": 90, "south": 180, "west": 270}.get(facing, 0)
    rotation = int(props.get("rotation", 0) or 0)
    return (round(rotation * 22.5 / 90.0) * 90) % 360


def _all_elements_flat(elements, threshold=1.0) -> bool:
    """True when every element is a thin plane (min extent below threshold)."""
    for elem in elements:
        f, t = elem.get("from", (0, 0, 0)), elem.get("to", (0, 0, 0))
        if min(abs(t[i] - f[i]) for i in range(3)) >= threshold:
            return False
    return True


def _all_faces(texture="#texture"):
    return {f: {"texture": texture} for f in ("north", "south", "east", "west", "up", "down")}


def _ladder_3d_elements() -> list:
    """Real 3D ladder: two side rails + four rungs (replaces the flat quad)."""
    elements = [
        {"from": [2, 0, 14], "to": [4, 16, 16], "faces": _all_faces()},
        {"from": [12, 0, 14], "to": [14, 16, 16], "faces": _all_faces()},
    ]
    for y in (1, 5, 9, 13):
        elements.append({"from": [4, y, 14], "to": [12, y + 2, 15], "faces": _all_faces()})
    return elements


def _force_3d_model(block_name: str, model: dict) -> dict:
    """
    Substitute generated 3D geometry for blocks whose models are flat quads
    (they would voxelize into paper-thin or empty shapes).
    """
    name = block_name.lower()
    elements = model.get("elements")
    if not elements:
        return model

    if (name == "ladder" or name.endswith("_ladder")) and _all_elements_flat(elements):
        model = dict(model)
        model["elements"] = _ladder_3d_elements()
    return model


def _bars_are_flat(name, assets_dir, mc_block, block_at) -> bool:
    """Only rodify flat vanilla-style bars; 3D pack models stay as-is."""
    from blockstate_resolver import resolve_block_models

    try:
        entries = resolve_block_models(name, assets_dir, mc_block, block_at)
    except Exception:
        return True
    for entry in entries:
        try:
            entry_model = load_model_any(entry["model"], assets_dir)
        except FileNotFoundError:
            continue
        if entry_model.get("elements") and not _all_elements_flat(
            entry_model["elements"], threshold=2.5
        ):
            return False
    return True


def _rodify_bars(local: dict) -> dict:
    """
    Turn solid bar walls into actual bars: top/bottom rails, the center post,
    and 2-voxel-wide vertical rods every 5 voxels along each arm.
    """
    if not local:
        return local
    kept = {}
    for (x, y, z), color in local.items():
        if y <= 1 or y >= VOXEL_SCALE - 2:
            kept[(x, y, z)] = color  # top/bottom rails
            continue
        if 6 <= x <= 9 and 6 <= z <= 9:
            kept[(x, y, z)] = color  # center post
            continue
        run = x if 6 <= z <= 9 else z
        if run % 5 in (0, 1):
            kept[(x, y, z)] = color  # vertical rod
    return kept


def discover_geometry_sources(
    block_name: str,
    assets_dir,
    properties: dict | None = None,
) -> list[tuple[str, str]]:
    """
    Return ordered (model_type, model_name) candidates that may contain elements.
    model_type is 'block', 'item', or 'cem'.
    """
    name = block_name.lower()
    props = properties or {}
    sources: list[tuple[str, str]] = []

    if "chest" in name and not name.endswith("_chestplate"):
        sources.append(("item", _chest_item_name(name)))
        sources.append(("item", "template_chest_item"))
        return sources

    if name.endswith("_bed") or name == "bed":
        part = props.get("part", "foot")
        sources.append(("cem", part))
        color = props.get("color") or name.replace("_bed", "") or "red"
        sources.append(("item", f"{color}_bed"))
        sources.append(("item", "template_bed"))
        return sources

    # Generic fallbacks: block name, suffix variants, item counterpart
    sources.append(("block", name))
    for suffix in ("_post", "_bottom", "_top", "_side", "_inventory"):
        sources.append(("block", f"{name}{suffix}"))
    sources.append(("item", name))
    return sources


def _clip_chest_voxels(local: dict, chest_type: str) -> dict:
    if chest_type == "left":
        return {k: v for k, v in local.items() if k[0] >= 1}
    if chest_type == "right":
        return {k: v for k, v in local.items() if k[0] <= 14}
    return local


def _apply_facing_rotation(local: dict, props: dict) -> dict:
    facing = props.get("facing")
    if not facing or not local:
        return local
    from block_placement import facing_y_rotation
    from block_voxels import merge_local_voxels_rotated

    rotated = {}
    merge_local_voxels_rotated(rotated, local, y_rotation=facing_y_rotation(facing))
    return rotated


def _needs_facing_rotation(block_name: str) -> bool:
    name = block_name.lower()
    if "chest" in name and not name.endswith("_chestplate"):
        return True
    return name.endswith("_bed") or name == "bed"


def voxelize_resolved_model(resolved_elements, assets_dir, block_name: str | None = None) -> dict:
    from block_tints import tint_for_block
    from voxelizer import voxelize_model

    tint = tint_for_block(block_name) if block_name else None
    # Glass/ice: fully transparent texels are still glass material — keep them
    # as CLEAR_GLASS sentinel voxels (alpha 254) so glass blocks/panes get all
    # their walls, rendered with a different (clear) glass part type.
    name = (block_name or "").lower()
    glassy = "glass" in name or "ice" in name
    raw = voxelize_model(resolved_elements, {}, tint=tint)
    local = {}
    for (x, y, z), color in raw.items():
        if len(color) > 3 and color[3] == 0:
            if not glassy:
                continue
            color = CLEAR_GLASS_COLOR
        lx, ly, lz = int(x), int(y), int(z)
        if 0 <= lx < VOXEL_SCALE and 0 <= ly < VOXEL_SCALE and 0 <= lz < VOXEL_SCALE:
            local[(lx, ly, lz)] = color
    return local


def voxelize_from_source(
    source_type: str,
    source_name: str,
    block_name: str,
    assets_dir,
    properties: dict | None = None,
) -> dict:
    from model_parser import resolve_model

    props = properties or {}

    if source_type == "cem":
        model = _load_bed_cem_model(block_name, assets_dir, part=source_name)
    elif source_type == "item" and "chest" in block_name.lower():
        model = _load_chest_item_model(
            block_name, assets_dir, props.get("type", "single")
        )
    else:
        try:
            model = load_model_any(source_name, assets_dir, model_type=source_type)
        except FileNotFoundError:
            return {}

    if not model_has_geometry(model):
        return {}

    model = _force_3d_model(block_name, model)

    base = str(_assets_base(assets_dir))
    resolved = resolve_model(model, base)
    local = voxelize_resolved_model(resolved, assets_dir, block_name=block_name)

    if "chest" in block_name.lower():
        local = _clip_chest_voxels(local, props.get("type", "single"))
    return local


def load_block_geometry(
    block_name: str,
    assets_dir,
    mc_block: dict | None = None,
    block_at=None,
) -> dict:
    """Resolve blockstate models, then fall back to item/CEM/supplement sources."""
    from blockstate_resolver import block_properties, normalize_block_name, resolve_block_models
    from config import VOXEL_SCALE

    name = normalize_block_name(block_name)
    if mc_block:
        from blockstate_resolver import resolved_block_properties

        props = resolved_block_properties(name, mc_block, block_at)
    else:
        props = block_properties({"name": name, "data": 0})

    if _is_sign(name):
        from block_voxels import merge_local_voxels_rotated
        from model_parser import resolve_model

        model = _sign_model(name, props)
        if model:
            base = str(_assets_base(assets_dir))
            resolved = resolve_model(model, base)
            part = voxelize_resolved_model(resolved, assets_dir, block_name=name)
            rotated: dict = {}
            merge_local_voxels_rotated(
                rotated, part, y_rotation=_sign_y_rotation(name, props)
            )
            return rotated

    local = {}
    models_baked_rotation = False
    if mc_block is not None:
        from block_voxels import merge_local_voxels_rotated

        for entry in resolve_block_models(name, assets_dir, mc_block, block_at):
            if entry.get("x") or entry.get("y") or entry.get("z"):
                models_baked_rotation = True
            part = voxelize_from_source("block", entry["model"], name, assets_dir, props)
            if part:
                merge_local_voxels_rotated(
                    local,
                    part,
                    x_rotation=entry.get("x", 0),
                    y_rotation=entry.get("y", 0),
                    z_rotation=entry.get("z", 0),
                )

    if local:
        if name.endswith("_bars") and _bars_are_flat(name, assets_dir, mc_block, block_at):
            local = _rodify_bars(local)
        if not models_baked_rotation and props.get("facing") and _needs_facing_rotation(name):
            local = _apply_facing_rotation(local, props)
        return local

    for source_type, source_name in discover_geometry_sources(name, assets_dir, props):
        part = voxelize_from_source(source_type, source_name, name, assets_dir, props)
        if part:
            local.update(part)
            break

    if local and name.endswith("_bars"):
        local = _rodify_bars(local)

    if local and props.get("facing") and _needs_facing_rotation(name):
        local = _apply_facing_rotation(local, props)

    return local
