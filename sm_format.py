"""Normalize blueprint JSON to match Scrap Mechanic's native export format."""

import json

from config import BEARING_JOINT_SHAPE_ID, PARTS_PER_BODY, WELD_BODIES


def _to_float(value):
    if isinstance(value, dict):
        return {k: _to_float(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_float(v) for v in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return float(value)
    return value


def normalize_part(part: dict) -> dict:
    normalized = _to_float(part)
    if "bounds" not in normalized and "controller" not in normalized:
        # Scalable blocks need bounds; interactive parts (lamps) must not have them.
        normalized["bounds"] = {"x": 1.0, "y": 1.0, "z": 1.0}
    normalized.pop("is_connector", None)
    normalized.pop("is_transparent", None)
    normalized.pop("is_lamp", None)
    normalized.pop("occupied_cell", None)
    normalized.pop("joints", None)
    return normalized


def _identity_transform():
    return {
        "pos": {"x": 0.0, "y": 0.0, "z": 0.0},
        "rot": {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0},
    }


def _add_body_bearing_joints(bodies: list, joint_shape_id: str) -> list:
    """
    Chain bearing joints between bodies when a chunk must be split into multiple bodies.
    Use only when PARTS_PER_BODY is below the chunk part count — static builds should
    prefer one weld-welded body instead (PARTS_PER_BODY = MAX_PARTS_PER_CHUNK).
    """
    if len(bodies) <= 1:
        return []

    joints = []
    global_index = 0
    prev_global = 0
    prev_part = bodies[0]["childs"][0]
    prev_pos = prev_part["pos"]
    joint_id = 1
    global_index += len(bodies[0]["childs"])

    for body in bodies[1:]:
        if not body.get("childs"):
            global_index += len(body.get("childs", []))
            continue
        child_b = global_index
        part_b = body["childs"][0]
        weld_pos = part_b["pos"]
        joints.append({
            "childA": float(prev_global),
            "childB": float(child_b),
            "color": "577d07",
            "id": float(joint_id),
            "posA": prev_pos,
            "posB": weld_pos,
            "shapeId": joint_shape_id,
            "xaxisA": 1.0,
            "xaxisB": 1.0,
            "zaxisA": 3.0,
            "zaxisB": 3.0,
        })
        prev_part.setdefault("joints", []).append({"id": float(joint_id)})
        part_b.setdefault("joints", []).append({"id": float(joint_id)})
        joint_id += 1
        prev_global = child_b
        prev_part = part_b
        prev_pos = weld_pos
        global_index += len(body["childs"])

    return joints


def normalize_level_creation_blueprint(
    parts: list,
    parts_per_body: int = None,
    weld_bodies: bool = None,
) -> dict:
    """
    Build a LevelCreation blueprint matching in-game export layout:
    - version 3.0, joints array, float numeric types
    - one body per chunk by default (implicit weld-welds between all parts)
    - optional bearing joints only when forced to split into multiple bodies
    """
    parts_per_body = parts_per_body if parts_per_body is not None else PARTS_PER_BODY
    normalized_parts = [normalize_part(p) for p in parts]
    body_size = len(normalized_parts) or 1
    if parts_per_body and parts_per_body < body_size:
        body_size = parts_per_body
    bodies = []

    for i in range(0, max(len(normalized_parts), 1), body_size):
        chunk = normalized_parts[i : i + body_size]
        if not chunk and bodies:
            continue
        bodies.append({
            "childs": chunk,
            "transform": _identity_transform(),
            "type": 0.0,
        })

    if not bodies:
        bodies.append({"childs": [], "transform": _identity_transform(), "type": 0.0})

    if weld_bodies is None:
        weld_bodies = WELD_BODIES
    joints = _add_body_bearing_joints(bodies, BEARING_JOINT_SHAPE_ID) if weld_bodies else []

    return {
        "bodies": bodies,
        "joints": joints,
        "version": 3.0,
    }


def write_sm_json(data: dict, path) -> None:
    """Write JSON using tab indentation like Scrap Mechanic exports."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent="\t", ensure_ascii=False)
        f.write("\n")
