"""Export processed blueprints as Scrap Mechanic challenge levels."""

import json
import math
from pathlib import Path
from uuid import uuid4

from config import MAX_CHUNK_FILE_MB, MAX_PARTS_PER_CHUNK, SINGLE_LEVEL_CREATION
from sm_format import normalize_level_creation_blueprint, write_sm_json


def _count_parts(blueprint: dict) -> int:
    return sum(len(body.get("childs", [])) for body in blueprint.get("bodies", []))


def _estimate_json_mb(blueprint: dict) -> float:
    return len(json.dumps(blueprint, indent="\t")) / (1024 * 1024)


def _make_level_creation_blueprint(parts: list) -> dict:
    return normalize_level_creation_blueprint(parts)


def _split_spatially(parts: list) -> list:
    """Split parts into multiple LevelCreation blueprints (legacy / --split mode)."""
    if not parts:
        return [_make_level_creation_blueprint([])]

    single = _make_level_creation_blueprint(parts)
    if _count_parts(single) <= MAX_PARTS_PER_CHUNK and _estimate_json_mb(single) <= MAX_CHUNK_FILE_MB:
        return [single]

    min_x = min(p["pos"]["x"] for p in parts)
    max_x = max(p["pos"]["x"] for p in parts)
    min_y = min(p["pos"]["y"] for p in parts)
    max_y = max(p["pos"]["y"] for p in parts)
    min_z = min(p["pos"]["z"] for p in parts)
    max_z = max(p["pos"]["z"] for p in parts)

    total_x = max_x - min_x + 1
    total_y = max_y - min_y + 1
    total_z = max_z - min_z + 1
    num_chunks_needed = max(2, math.ceil(len(parts) / MAX_PARTS_PER_CHUNK))
    chunk_dim = max(1, int((total_x * total_y * total_z / num_chunks_needed) ** (1 / 3)))

    chunk_x = max(1, min(int(total_x), chunk_dim))
    chunk_y = max(1, min(int(total_y), chunk_dim))
    chunk_z = max(1, min(int(total_z), chunk_dim))

    spatial_chunks = {}
    for part in parts:
        pos = part["pos"]
        x, y, z = pos["x"], pos["y"], pos["z"]
        key = (
            int((x - min_x) // chunk_x),
            int((y - min_y) // chunk_y),
            int((z - min_z) // chunk_z),
        )
        spatial_chunks.setdefault(key, []).append(part)

    final_chunks = []
    for part_list in spatial_chunks.values():
        if len(part_list) <= MAX_PARTS_PER_CHUNK:
            candidate = _make_level_creation_blueprint(part_list)
            if _estimate_json_mb(candidate) <= MAX_CHUNK_FILE_MB:
                final_chunks.append(candidate)
                continue
        for i in range(0, len(part_list), MAX_PARTS_PER_CHUNK):
            final_chunks.append(
                _make_level_creation_blueprint(part_list[i : i + MAX_PARTS_PER_CHUNK])
            )

    return final_chunks or [_make_level_creation_blueprint(parts)]


def split_into_level_creations(blueprint: dict, split: bool = None) -> list:
    """
    Build LevelCreation blueprint(s) for challenge export.

    Default: one file, one weld-welded body (entire map is a single structure).
    Pass split=True for legacy spatial chunking into multiple LevelCreation files.
    """
    parts = blueprint.get("bodies", [{}])[0].get("childs", [])
    use_split = (not SINGLE_LEVEL_CREATION) if split is None else split
    if not use_split:
        return [_make_level_creation_blueprint(parts)]
    return _split_spatially(parts)


def _write_challenge_level_json(
    path: Path,
    level_creation_paths: list,
    start_creation_paths: list | None = None,
) -> None:
    """Write challengeLevel.json matching the game's native export layout."""
    data = {
        "data": {
            "levelCreations": level_creation_paths,
            "startCreations": start_creation_paths or [],
            "tiles": ["$CHALLENGE_DATA/Terrain/Tiles/ChallengeBuilderDefault.tile"],
            "settings": None,
        }
    }
    write_sm_json(data, path)


def export_block_prefabs(
    schematic_blocks: list,
    challenge_dir: Path,
    assets_dir,
    block_at=None,
) -> list[str]:
    """
    Write one builder-palette blueprint per block type used in the schematic.
    Returns startCreations paths ($CONTENT_DATA/Blueprints/...).
    """
    from block_prefab_library import build_all_block_prefabs

    catalog = build_all_block_prefabs(schematic_blocks, assets_dir, block_at=block_at)
    if not catalog:
        return []

    blueprints_dir = challenge_dir / "Blueprints"
    blueprints_dir.mkdir(parents=True, exist_ok=True)
    start_paths = []

    for entry in catalog:
        filename = f"Block_{entry['filename']}.blueprint"
        filepath = blueprints_dir / filename
        bp = _make_level_creation_blueprint(entry["parts"])
        write_sm_json(bp, filepath)
        start_paths.append(f"$CONTENT_DATA/Blueprints/{filename}")

    return start_paths


def _write_description_json(path: Path, level_id: str, name: str, description: str) -> None:
    data = {
        "description": description or f"Converted from Minecraft schematic: {name}",
        "localId": level_id,
        "name": name,
        "type": "Challenge Level",
        "version": 1,
    }
    write_sm_json(data, path)


def export_challenge(
    blueprint: dict,
    name: str,
    output_dir: Path,
    description: str = "",
    split: bool = None,
    schematic_blocks: list | None = None,
    assets_dir=None,
    block_at=None,
    include_block_prefabs: bool = True,
) -> Path:
    """
    Write a Challenge Level folder with description.json, challengeLevel.json,
    and LevelCreation_N.blueprint files.
    """
    level_id = str(uuid4())
    challenge_dir = Path(output_dir) / level_id
    challenge_dir.mkdir(parents=True, exist_ok=True)

    chunks = split_into_level_creations(blueprint, split=split)
    level_creation_paths = []

    for i, chunk in enumerate(chunks, start=1):
        filename = f"LevelCreation_{i}.blueprint"
        filepath = challenge_dir / filename
        write_sm_json(chunk, filepath)
        level_creation_paths.append(f"$CONTENT_DATA/{filename}")

    start_creation_paths = []
    if include_block_prefabs and schematic_blocks and assets_dir is not None:
        start_creation_paths = export_block_prefabs(
            schematic_blocks,
            challenge_dir,
            assets_dir,
            block_at=block_at,
        )

    _write_description_json(challenge_dir / "description.json", level_id, name, description)
    _write_challenge_level_json(
        challenge_dir / "challengeLevel.json",
        level_creation_paths,
        start_creation_paths=start_creation_paths,
    )

    return challenge_dir
