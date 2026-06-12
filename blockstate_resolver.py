"""Resolve Minecraft blockstate JSON into one or more block models."""

from __future__ import annotations

import json
import re
from pathlib import Path

from assets_paths import normalize_assets_dir

# Legacy schematic data -> blockstate properties (1.12-style)
_FACING_FROM_2BIT = ("south", "west", "north", "east")
_STAIRS_FACING = ("east", "west", "south", "north")
_DOOR_FACING = ("east", "south", "west", "north")


def normalize_block_name(block_name: str) -> str:
    name = block_name.lower()
    if name == "fence":
        return "oak_fence"
    if name == "wooden_door":
        return "oak_door"
    if name == "iron_door":
        return "iron_door"
    if name == "bed":
        return "red_bed"
    if name == "chest":
        return "chest"
    if name == "trapped_chest":
        return "trapped_chest"
    if name == "ender_chest":
        return "ender_chest"
    return name


def legacy_data_to_properties(block_name: str, data: int) -> dict:
    """Best-effort properties from pre-flattening schematic data values."""
    name = normalize_block_name(block_name)
    data = int(data or 0)
    props: dict = {}

    if name.endswith("_door"):
        props["facing"] = _DOOR_FACING[data & 0x3]
        props["half"] = "upper" if data & 0x8 else "lower"
        props["hinge"] = "right" if data & 0x1 else "left"
        props["open"] = "true" if data & 0x4 else "false"
        return props

    if name.endswith("_trapdoor"):
        props["facing"] = _FACING_FROM_2BIT[data & 0x3]
        props["open"] = "true" if data & 0x4 else "false"
        props["half"] = "top" if data & 0x8 else "bottom"
        return props

    if name.endswith("_bed") or name == "bed":
        props["facing"] = _FACING_FROM_2BIT[data & 0x3]
        props["part"] = "head" if data & 0x8 else "foot"
        if name.endswith("_bed"):
            props["color"] = name.replace("_bed", "")
        return props

    if "anvil" in name:
        damage = ("intact", "chipped", "damaged", "damaged")[min(data & 0x3, 3)]
        if damage != "intact":
            name_map = {
                "chipped": "chipped_anvil",
                "damaged": "damaged_anvil",
            }
            props["_model_override"] = name_map.get(damage, "anvil")
        props["facing"] = _FACING_FROM_2BIT[(data >> 2) & 0x3]
        return props

    if name in ("chest", "trapped_chest", "ender_chest") or name.endswith("_chest"):
        facing_map = {2: "north", 3: "south", 4: "west", 5: "east"}
        if data in facing_map:
            props["facing"] = facing_map[data]
        elif data & 0x3 in range(4):
            props["facing"] = _FACING_FROM_2BIT[data & 0x3]
        props["type"] = "single"
        return props

    if name.endswith("_fence_gate"):
        props["facing"] = _FACING_FROM_2BIT[data & 0x3]
        props["open"] = "true" if data & 0x4 else "false"
        props["in_wall"] = "true" if data & 0x8 else "false"
        return props

    if "stairs" in name:
        props["facing"] = _STAIRS_FACING[data & 0x3]
        props["half"] = "top" if data & 0x4 else "bottom"
        props.setdefault("shape", "straight")
        return props

    if "slab" in name and "double" not in name:
        props["type"] = "top" if data & 0x8 else "bottom"
        return props

    return props


def block_properties(mc_block: dict) -> dict:
    """Merge explicit blockstate properties with legacy data decoding."""
    name = normalize_block_name(mc_block["name"])
    props = dict(mc_block.get("properties") or {})
    if not props:
        props.update(legacy_data_to_properties(name, mc_block.get("data", 0)))
    if name.endswith("_bed") and "color" not in props:
        props["color"] = name.replace("_bed", "")
    return props


_json_cache: dict = {}


def _load_json(path: Path | None) -> dict | None:
    if path is None:
        return None
    key = str(path)
    if key in _json_cache:
        return _json_cache[key]
    if not path.is_file():
        _json_cache[key] = None
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    _json_cache[key] = data
    return data


def _blockstate_path(assets_dir, block_name: str) -> Path | None:
    from asset_resolution import find_blockstate_file

    found = find_blockstate_file(block_name, assets_dir)
    if found is not None:
        return found
    base = normalize_assets_dir(assets_dir)
    return base / "minecraft" / "blockstates" / f"{block_name}.json"


def _variant_key(props: dict) -> str:
    if not props:
        return ""
    return ",".join(f"{k}={v}" for k, v in sorted(props.items()))


def _value_matches(expected, actual) -> bool:
    """Compare a blockstate condition value against a property value.

    Handles JSON booleans ("true" vs True) and pipe-alternatives ("low|tall").
    """
    actual_str = str(actual).lower()
    expected_str = str(expected).lower()
    if "|" in expected_str:
        return actual_str in {part.strip() for part in expected_str.split("|")}
    return actual_str == expected_str


def _props_match(when: dict, props: dict) -> bool:
    for key, expected in when.items():
        actual = props.get(key)
        if actual is None:
            return False
        if not _value_matches(expected, actual):
            return False
    return True


def _when_matches(when, props: dict) -> bool:
    """Multipart 'when' condition: plain dict, OR list, or AND list."""
    if not when:
        return True
    if "OR" in when:
        return any(_when_matches(cond, props) for cond in when["OR"])
    if "AND" in when:
        return all(_when_matches(cond, props) for cond in when["AND"])
    return _props_match(when, props)


def _model_ref_to_path(model_ref: str) -> str:
    if model_ref.startswith("minecraft:"):
        model_ref = model_ref.split(":", 1)[1]
    if model_ref.startswith("block/"):
        model_ref = model_ref[len("block/") :]
    return model_ref


def _apply_entry(entry: dict) -> list[dict]:
    if "model" in entry:
        return [{
            "model": _model_ref_to_path(entry["model"]),
            "x": int(entry.get("x", 0) or 0),
            "y": int(entry.get("y", 0) or 0),
            "z": int(entry.get("z", 0) or 0),
        }]
    if "apply" in entry:
        applied = entry["apply"]
        if isinstance(applied, list):
            out = []
            for item in applied:
                out.extend(_apply_entry(item))
            return out
        return _apply_entry(applied)
    return []


# Properties ignored when matching blockstate variant keys
_VARIANT_IGNORE_PROPS = frozenset({
    "waterlogged", "powered", "occupied", "lit", "enabled", "triggered",
    "signal_fire", "inverted", "locked", "extended", "eye", "short",
})

# Chest left/right/single is resolved via chest_type_properties, not blockstate variants.
_CHEST_TYPE_IGNORE = frozenset({"type"})


def _relevant_props(props: dict, block_name: str | None = None) -> dict:
    ignored = set(_VARIANT_IGNORE_PROPS)
    name = (block_name or "").lower()
    if "chest" in name and not name.endswith("_chestplate"):
        ignored |= _CHEST_TYPE_IGNORE
    return {k: v for k, v in props.items() if not k.startswith("_") and k not in ignored}


def _parse_variant_key(variant_key: str) -> dict:
    req = {}
    for part in variant_key.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            req[k.strip()] = v.strip()
    return req


def _conflicts(req: dict, props: dict) -> bool:
    """True when a provided property contradicts the variant requirement."""
    for key, expected in req.items():
        actual = props.get(key)
        if actual is not None and not _value_matches(expected, actual):
            return True
    return False


def _pick_variant_entry(variants: dict, props: dict):
    """
    Select a variant entry:
    1. exact key match with all provided properties
    2. variant whose requirements are all satisfied by the provided properties
    3. variant that at least does not contradict the provided properties
       (handles legacy schematics with missing properties, e.g. lit/snowy)
    4. the catch-all "" variant, else the first variant
    """
    key = _variant_key({k: v for k, v in sorted(props.items())})
    if key in variants:
        return variants[key]

    for variant_key, candidate in variants.items():
        req = _parse_variant_key(variant_key)
        if req and _props_match(req, props):
            return candidate

    for variant_key, candidate in variants.items():
        req = _parse_variant_key(variant_key)
        if not _conflicts(req, props):
            return candidate

    if "" in variants:
        return variants[""]
    return next(iter(variants.values())) if variants else None


def _resolve_variants(blockstate: dict, props: dict, block_name: str | None = None) -> list[dict]:
    variants = blockstate.get("variants", {})
    if not variants:
        return []

    # Match with the full property set (minus internal keys) — stripping
    # properties like "lit" breaks variant keys that include them.
    matching_props = {k: v for k, v in props.items() if not k.startswith("_")}
    entry = _pick_variant_entry(variants, matching_props)
    if entry is None:
        return []

    # A list means Minecraft picks ONE weighted-random variant — use the first
    # (deterministic), never merge all rotations together.
    if isinstance(entry, list):
        entry = entry[0] if entry else None
        if entry is None:
            return []
    return _apply_entry(entry)


def _resolve_multipart(blockstate: dict, props: dict) -> list[dict]:
    models = []
    for part in blockstate.get("multipart", []):
        when = part.get("when", {})
        if not _when_matches(when, props):
            continue
        applied = part.get("apply")
        if applied is None:
            continue
        # A list means ONE weighted-random choice — use the first deterministically
        if isinstance(applied, list):
            applied = applied[0] if applied else None
        if applied:
            models.extend(_apply_entry(applied))
    return models


def _neighbor_block(block_at, x, y, z) -> dict | None:
    """Normalize block_at lookup to a block dict (or None)."""
    if block_at is None:
        return None
    result = block_at(x, y, z)
    if result is None:
        return None
    if isinstance(result, dict):
        return result
    return {"name": str(result), "data": 0, "properties": {}}


def _neighbor_name(block_at, x, y, z) -> str | None:
    block = _neighbor_block(block_at, x, y, z)
    return block["name"] if block else None


def _is_fence(name: str) -> bool:
    return name.endswith("_fence") or name == "nether_brick_fence"


def _is_pane_or_bars(name: str) -> bool:
    return name.endswith("_pane") or name in ("glass_pane", "iron_bars") or name.endswith("_bars")


def _is_wall(name: str) -> bool:
    return name.endswith("_wall") and "torch" not in name and "sign" not in name and not name.endswith("_banner")


def fence_connection_properties(
    block_name: str,
    mc_block: dict,
    block_at,
) -> dict:
    """
    Fill in missing north/east/south/west connection flags from neighbors for
    fences, glass panes, iron bars, and walls. Properties already present in
    the schematic (modern .schem) are kept untouched.
    """
    name = normalize_block_name(block_name)
    props = block_properties(mc_block)

    fence = _is_fence(name)
    pane = _is_pane_or_bars(name)
    wall = _is_wall(name)
    if not (fence or pane or wall):
        return props

    connected_value = "low" if wall else "true"
    open_value = "none" if wall else "false"
    if wall and "up" not in props:
        props["up"] = "true"

    missing_sides = [s for s in ("north", "south", "west", "east") if s not in props]
    if not missing_sides:
        return props

    x = mc_block.get("x")
    y = mc_block.get("y")
    z = mc_block.get("z")
    if x is None or y is None or z is None:
        for side in missing_sides:
            props[side] = open_value
        return props

    def connects_to(neighbor_name: str | None) -> bool:
        if not neighbor_name:
            return False
        neighbor = normalize_block_name(neighbor_name)
        if neighbor == name:
            return True
        if fence:
            if neighbor.endswith("_fence") or "fence_gate" in neighbor:
                return True
        if pane:
            if _is_pane_or_bars(neighbor) or _is_wall(neighbor):
                return True
            if neighbor in ("glass",) or neighbor.endswith("_stained_glass"):
                return True
        if wall:
            if _is_wall(neighbor) or _is_pane_or_bars(neighbor):
                return True
            if neighbor.endswith("_fence_gate"):
                return True
        # Solid opaque blocks connect all of these
        from transparent_blocks import is_solid_neighbor_for_connections

        return is_solid_neighbor_for_connections(neighbor)

    side_offsets = {
        "north": (x, y, z - 1),
        "south": (x, y, z + 1),
        "west": (x - 1, y, z),
        "east": (x + 1, y, z),
    }
    for side in missing_sides:
        nx, ny, nz = side_offsets[side]
        props[side] = (
            connected_value if connects_to(_neighbor_name(block_at, nx, ny, nz)) else open_value
        )
    return props


def grass_snowy_properties(block_name: str, mc_block: dict, block_at) -> dict:
    """Derive snowy=true/false from the block above (legacy schematics)."""
    props = block_properties(mc_block)
    name = normalize_block_name(block_name)
    if name not in ("grass_block", "podzol", "mycelium"):
        return props
    if "snowy" not in props:
        x, y, z = mc_block["x"], mc_block["y"], mc_block["z"]
        above = _neighbor_name(block_at, x, y + 1, z) if block_at else None
        snowy = above in ("snow", "snow_block", "snow_layer", "powder_snow")
        props["snowy"] = "true" if snowy else "false"
    return props


def chest_type_properties(
    block_name: str,
    mc_block: dict,
    block_at,
) -> dict:
    """Detect single vs left/right double chest from adjacent chest blocks."""
    name = normalize_block_name(block_name)
    if "chest" not in name:
        return block_properties(mc_block)

    props = block_properties(mc_block)
    x, y, z = mc_block["x"], mc_block["y"], mc_block["z"]
    facing = props.get("facing", "north")

    def is_matching_chest(nx, ny, nz):
        other = _neighbor_block(block_at, nx, ny, nz)
        if not other:
            return False
        other_name = normalize_block_name(other["name"])
        if name in ("chest", "trapped_chest") and other_name in ("chest", "trapped_chest"):
            pass
        elif other_name != name:
            return False
        other_props = block_properties(other)
        return other_props.get("facing") == facing

    offset_map = {
        "north": ((0, 0, -1), (0, 0, 1)),
        "south": ((0, 0, 1), (0, 0, -1)),
        "west": ((-1, 0, 0), (1, 0, 0)),
        "east": ((1, 0, 0), (-1, 0, 0)),
    }
    left_off, right_off = offset_map.get(facing, ((0, 0, -1), (0, 0, 1)))
    lx, ly, lz = x + left_off[0], y + left_off[1], z + left_off[2]
    rx, ry, rz = x + right_off[0], y + right_off[1], z + right_off[2]

    if is_matching_chest(lx, ly, lz):
        props["type"] = "left"
    elif is_matching_chest(rx, ry, rz):
        props["type"] = "right"
    else:
        props["type"] = "single"
    return props


def has_blockstate_definition(block_name: str, assets_dir) -> bool:
    name = normalize_block_name(block_name)
    return _load_json(_blockstate_path(assets_dir, name)) is not None


def resolved_block_properties(
    block_name: str,
    mc_block: dict,
    block_at=None,
) -> dict:
    """Block properties with neighbor-derived connections / chest type / snowy."""
    name = normalize_block_name(block_name)
    if _is_fence(name) or _is_pane_or_bars(name) or _is_wall(name):
        return fence_connection_properties(name, mc_block, block_at)
    if "chest" in name and not name.endswith("_chestplate"):
        return chest_type_properties(name, mc_block, block_at)
    if name in ("grass_block", "podzol", "mycelium"):
        return grass_snowy_properties(name, mc_block, block_at)
    return block_properties(mc_block)


def resolve_block_models(
    block_name: str,
    assets_dir,
    mc_block: dict | None = None,
    block_at=None,
) -> list[dict]:
    """
    Return model descriptors: [{"model": "oak_fence_post", "y": 0}, ...]
    """
    name = normalize_block_name(block_name)
    if mc_block:
        props = resolved_block_properties(name, mc_block, block_at)
    else:
        props = block_properties({"name": name, "data": 0})

    model_override = props.pop("_model_override", None)
    if model_override:
        return [{"model": model_override, "y": 0}]

    blockstate = _load_json(_blockstate_path(assets_dir, name))
    if blockstate:
        if "multipart" in blockstate:
            models = _resolve_multipart(blockstate, props)
            if models:
                return models
        models = _resolve_variants(blockstate, props, block_name=name)
        if models:
            return models

    # Fallback single model from aliases
    from block_model_aliases import resolve_block_model_name

    return [{"model": resolve_block_model_name(name), "y": 0}]
