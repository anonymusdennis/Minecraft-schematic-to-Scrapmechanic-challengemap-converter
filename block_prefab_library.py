"""Build per-block prefab blueprints for the challenge builder palette."""

from __future__ import annotations

import re

from block_model_aliases import is_sparse_shape_block
from block_placement import placement_rotation
from block_voxels import block_appearance, opaque_cell_voxels, solid_cube_local, voxelize_block_local
from blueprint_writer import rgba_to_hex
from config import VOXEL_SCALE
from hollow import worldedit_hollow
from transparent_blocks import get_shape_id_for_transparent, is_transparent_block


def _sanitize_filename(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())
    return safe.strip("._") or "block"


def catalog_used_blocks(schematic_blocks: list) -> list[dict]:
    """
    One representative MC block per distinct type + variant used in the schematic.
    """
    from blockstate_resolver import _relevant_props, block_properties

    seen: dict[tuple, dict] = {}
    for mc_block in schematic_blocks:
        name = mc_block["name"]
        props = block_properties(mc_block)
        relevant = _relevant_props(props, name)
        key = (name, tuple(sorted(relevant.items())))
        if key not in seen:
            seen[key] = mc_block
    return list(seen.values())


def prefab_label(mc_block: dict) -> str:
    """Human-readable label for a catalog entry."""
    from blockstate_resolver import _relevant_props, block_properties

    name = mc_block["name"]
    relevant = _relevant_props(block_properties(mc_block), name)
    if not relevant:
        return name
    props = ", ".join(f"{k}={v}" for k, v in sorted(relevant.items()))
    return f"{name} ({props})"


def prefab_filename(mc_block: dict) -> str:
    from blockstate_resolver import _relevant_props, block_properties

    name = mc_block["name"]
    relevant = _relevant_props(block_properties(mc_block), name)
    if not relevant:
        return _sanitize_filename(name)
    suffix = "_".join(f"{k}-{v}" for k, v in sorted(relevant.items()))
    return _sanitize_filename(f"{name}__{suffix}")


def _local_to_parts(local_voxels, color_hex, shape_id, xaxis, zaxis):
    parts = []
    for (lx, ly, lz), color in local_voxels.items():
        if isinstance(color, tuple):
            hex_color = rgba_to_hex(color)
        elif isinstance(color, str):
            hex_color = color.upper()
        else:
            hex_color = color_hex
        parts.append({
            "bounds": {"x": 1, "y": 1, "z": 1},
            "shapeId": shape_id,
            "color": hex_color,
            "pos": {"x": float(lx), "y": float(ly), "z": float(lz)},
            "xaxis": xaxis,
            "zaxis": zaxis,
        })
    return parts


def _is_full_cell_volume(local_voxels: dict) -> bool:
    return len(local_voxels) >= int(VOXEL_SCALE ** 3 * 0.75)


def _shell_hollow_parts(parts: list) -> list:
    if not parts:
        return parts
    bp = worldedit_hollow({"bodies": [{"childs": parts}]})
    return bp["bodies"][0]["childs"]


def build_block_prefab_parts(mc_block: dict, assets_dir, block_at=None) -> list:
    """
    One MC cell prefab at local 0..15: model geometry for partial blocks,
    hollow 16³ shell for solid full cubes (e.g. cobblestone).
    """
    block_name = mc_block["name"]
    xaxis, zaxis = placement_rotation(mc_block, assets_dir, block_at=block_at)

    partial = is_transparent_block(block_name) or is_sparse_shape_block(block_name)

    if partial:
        local = dict(
            voxelize_block_local(
                block_name, assets_dir, mc_block=mc_block, block_at=block_at
            )
        )
        appearance = block_appearance(
            block_name,
            assets_dir,
            local_voxels=local or None,
            mc_block=mc_block,
            block_at=block_at,
        )
        shape_id = get_shape_id_for_transparent(block_name)
        if not local:
            half = VOXEL_SCALE // 2
            local = {(half, half, half): appearance["color"]}
        parts = _local_to_parts(local, appearance["color"], shape_id, xaxis, zaxis)
        if _is_full_cell_volume(local):
            parts = _shell_hollow_parts(parts)
        return parts

    local = opaque_cell_voxels(
        block_name, assets_dir, mc_block=mc_block, block_at=block_at
    )
    if not local:
        local = solid_cube_local(block_name, assets_dir)
    appearance = block_appearance(
        block_name,
        assets_dir,
        local_voxels=local,
        mc_block=mc_block,
        block_at=block_at,
    )
    parts = _local_to_parts(
        local, appearance["color"], appearance["shapeId"], xaxis, zaxis
    )
    return _shell_hollow_parts(parts)


def build_all_block_prefabs(schematic_blocks: list, assets_dir, block_at=None) -> list[dict]:
    """
    Return catalog entries: {mc_block, label, filename, parts}.
    """
    catalog = []
    for mc_block in catalog_used_blocks(schematic_blocks):
        parts = build_block_prefab_parts(mc_block, assets_dir, block_at=block_at)
        if not parts:
            continue
        catalog.append({
            "mc_block": mc_block,
            "label": prefab_label(mc_block),
            "filename": prefab_filename(mc_block),
            "parts": parts,
        })
    return sorted(catalog, key=lambda entry: entry["label"].lower())
