"""Block placement rotation: legacy data axes and blockstate-aware identity."""

from __future__ import annotations

from blockstate_resolver import (
    block_properties,
    has_blockstate_definition,
    normalize_block_name,
    resolve_block_models,
)


def determine_rotation(block_name: str, data_value: int) -> tuple[int, int]:
    """Legacy schematic data -> Scrap Mechanic xaxis/zaxis."""
    xaxis = 1
    zaxis = 3
    name = block_name.lower()
    data_value = int(data_value or 0)

    if "stairs" in name:
        direction = data_value & 0x3
        upside_down = (data_value & 0x4) != 0
        if direction == 0:
            xaxis, zaxis = 1, 3
        elif direction == 1:
            xaxis, zaxis = -1, 3
        elif direction == 2:
            xaxis, zaxis = 3, 1
        elif direction == 3:
            xaxis, zaxis = -3, 1
        if upside_down:
            zaxis = -zaxis
    elif "log" in name or "wood" in name:
        orientation = data_value & 0xC
        if orientation == 0x0:
            xaxis, zaxis = 1, 2
        elif orientation == 0x4:
            xaxis, zaxis = 2, 1
        elif orientation == 0x8:
            xaxis, zaxis = 1, 3
    elif "slab" in name:
        top_half = (data_value & 0x8) != 0
        zaxis = 2 if top_half else -2
    elif "torch" in name:
        rotations = {
            5: (1, 2), 1: (1, 3), 2: (-1, 3), 3: (3, 1), 4: (-3, 1),
        }
        xaxis, zaxis = rotations.get(data_value, (1, 3))
    elif "button" in name or "lever" in name:
        direction = data_value & 0x7
        rotations = {
            0: (1, -2), 5: (1, 2), 1: (1, 3), 2: (-1, 3), 3: (3, 1), 4: (-3, 1),
        }
        xaxis, zaxis = rotations.get(direction, (1, 3))
    elif "fence_gate" in name or "door" in name:
        direction = data_value & 0x3
        rotations = {0: (3, 1), 1: (-1, 3), 2: (-3, 1), 3: (1, 3)}
        xaxis, zaxis = rotations.get(direction, (1, 3))

    return xaxis, zaxis


_ORIENTATION_PROPS = frozenset({
    "facing", "half", "open", "hinge", "part", "face", "axis", "type", "shape",
    "north", "south", "east", "west", "attachment", "vertical_direction",
    "lever", "inverted", "mode",
})


def _props_affect_orientation(props: dict) -> bool:
    from blockstate_resolver import _relevant_props

    return bool(_ORIENTATION_PROPS & set(_relevant_props(props).keys()))


def _model_bakes_orientation(models: list[dict]) -> bool:
    if not models:
        return False
    if any(m.get("x") or m.get("y") or m.get("z") for m in models):
        return True
    for model in models:
        path = model.get("model", "")
        if "/" in path or path.startswith("_"):
            return True
    return False


def placement_rotation(
    mc_block: dict,
    assets_dir,
    block_at=None,
) -> tuple[int, int]:
    """
    Return SM xaxis/zaxis for a placed block.

    When blockstate properties or model JSON encode facing/rotation, return
    identity (1, 3) so voxels are not double-rotated. Legacy schematics without
    properties still use determine_rotation().
    """
    block_name = mc_block["name"]
    name = normalize_block_name(block_name)

    if has_blockstate_definition(name, assets_dir):
        models = resolve_block_models(name, assets_dir, mc_block, block_at)
        if _model_bakes_orientation(models):
            return 1, 3
        props = block_properties(mc_block)
        if _props_affect_orientation(props):
            return 1, 3

    return determine_rotation(name, mc_block.get("data", 0))


def facing_y_rotation(facing: str) -> int:
    return {"north": 0, "east": 90, "south": 180, "west": 270}.get(facing, 0)
