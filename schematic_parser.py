"""Parse Minecraft schematic files (.schematic NBT or JSON) into block lists."""

import json
from pathlib import Path

from block_ids import get_block_name
from schematic_to_json import read_nbt_from_gzipped_file


def parse_block_state(block_state):
    if ":" in block_state:
        block_state = block_state.split(":", 1)[1]

    if "[" in block_state:
        block_name = block_state.split("[")[0]
        props_str = block_state.split("[")[1].rstrip("]")
        properties = {}
        if props_str:
            for prop in props_str.split(","):
                if "=" in prop:
                    key, value = prop.split("=", 1)
                    properties[key] = value
        return block_name, properties
    return block_state, {}


def parse_schematic_data(data: dict) -> dict:
    """Parse schematic JSON/NBT dict into width, height, length, blocks."""
    if "Schematic" in data:
        schematic = data["Schematic"]
    elif "" in data and "Schematic" in data[""]:
        schematic = data[""]["Schematic"]
    else:
        raise ValueError("Invalid schematic format: 'Schematic' key not found")

    width = schematic["Width"]
    height = schematic["Height"]
    length = schematic["Length"]
    blocks_data = schematic["Blocks"]
    is_new_format = (
        isinstance(blocks_data, dict) and "Palette" in blocks_data and "Data" in blocks_data
    )

    block_list = []

    if is_new_format:
        palette = blocks_data["Palette"]
        data_array = blocks_data["Data"]
        id_to_block_state = {v: k for k, v in palette.items()}

        for y in range(height):
            for z in range(length):
                for x in range(width):
                    index = (y * length + z) * width + x
                    palette_id = data_array[index]
                    block_state = id_to_block_state.get(palette_id, "minecraft:air")
                    block_name, properties = parse_block_state(block_state)
                    if block_name == "air":
                        continue
                    block_list.append({
                        "x": x,
                        "y": y,
                        "z": z,
                        "block_id": None,
                        "data": 0,
                        "name": block_name,
                        "properties": properties,
                        "block_state": block_state,
                    })
    else:
        blocks = blocks_data
        block_data = schematic["Data"]
        for y in range(height):
            for z in range(length):
                for x in range(width):
                    index = (y * length + z) * width + x
                    block_id = blocks[index]
                    data_value = block_data[index]
                    if block_id == 0:
                        continue
                    block_list.append({
                        "x": x,
                        "y": y,
                        "z": z,
                        "block_id": block_id,
                        "data": data_value,
                        "name": get_block_name(block_id, data_value),
                    })

    return {
        "width": width,
        "height": height,
        "length": length,
        "blocks": block_list,
        "entities": _parse_entities(schematic),
    }


def _parse_entities(schematic: dict) -> list:
    """
    Normalize schematic entities (paintings, item frames, ...) to
    {"id": str, "pos": [x, y, z], "data": dict}.
    Supports Sponge v2 (flattened) and v3 ("Data" sub-compound) layouts.
    """
    entities = []
    for raw in schematic.get("Entities") or []:
        if not isinstance(raw, dict):
            continue
        entity_id = raw.get("Id") or raw.get("id") or ""
        if ":" in entity_id:
            entity_id = entity_id.split(":", 1)[1]
        pos = raw.get("Pos") or raw.get("pos") or [0, 0, 0]
        data = dict(raw.get("Data") or {})
        for key, value in raw.items():
            if key not in ("Id", "id", "Pos", "pos", "Data"):
                data.setdefault(key, value)
        entities.append({"id": entity_id, "pos": list(pos), "data": data})
    return entities


def parse_schematic_file(path) -> dict:
    """Load a .schematic, .schem, or .json file and return parsed schematic data (in-memory)."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Schematic file not found: {path}")

    suffix = path.suffix.lower()
    if suffix in (".schematic", ".schem"):
        root_name, root_payload = read_nbt_from_gzipped_file(path)
        data = {root_name: root_payload}
    elif suffix == ".json":
        with open(path) as f:
            data = json.load(f)
    else:
        raise ValueError(f"Unsupported schematic format: {suffix} (use .schematic, .schem, or .json)")

    return parse_schematic_data(data)


def schematic_voxel_bounds(schematic_data: dict, voxel_scale: int = 16) -> dict:
    """Compute SM voxel AABB for validation."""
    if not schematic_data["blocks"]:
        return {"min_x": 0, "min_y": 0, "min_z": 0, "max_x": 0, "max_y": 0, "max_z": 0}

    max_mc_x = max(b["x"] for b in schematic_data["blocks"])
    max_mc_y = max(b["y"] for b in schematic_data["blocks"])
    max_mc_z = max(b["z"] for b in schematic_data["blocks"])

    return {
        "min_x": 0,
        "min_y": 0,
        "min_z": 0,
        "max_x": (max_mc_x + 1) * voxel_scale,
        "max_y": (max_mc_y + 1) * voxel_scale,
        "max_z": (max_mc_z + 1) * voxel_scale,
    }
