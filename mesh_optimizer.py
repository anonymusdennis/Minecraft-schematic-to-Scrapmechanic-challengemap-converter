"""Greedy 3D mesh merging to reduce Scrap Mechanic part counts."""

from collections import defaultdict

from config import VOXEL_SCALE


def _quantize_color(color_hex, step=8):
    """Bucket similar colors so adjacent textured voxels can merge."""
    if not color_hex or len(color_hex) < 6:
        return color_hex
    r = int(color_hex[0:2], 16)
    g = int(color_hex[2:4], 16)
    b = int(color_hex[4:6], 16)
    r = min(255, (r // step) * step)
    g = min(255, (g // step) * step)
    b = min(255, (b // step) * step)
    return f"{r:02x}{g:02x}{b:02x}".upper()


def _part_key(part, quantize_step=8):
    color = part.get("color", "")
    if part.get("is_connector"):
        qcolor = color
    else:
        qcolor = _quantize_color(color, quantize_step)
    return (
        part.get("shapeId"),
        qcolor,
        part.get("xaxis", 1),
        part.get("zaxis", 3),
        bool(part.get("is_connector")),
        bool(part.get("is_transparent")),
    )


def _voxel_positions(parts):
    voxels = {}
    for part in parts:
        pos = part["pos"]
        key = (int(pos["x"]), int(pos["y"]), int(pos["z"]))
        voxels[key] = part
    return voxels


def _greedy_merge_group(voxels, max_dimension=None):
    """Merge same-material unit voxels into axis-aligned boxes."""
    if not voxels:
        return []

    remaining = set(voxels.keys())
    merged = []
    max_dimension = max_dimension or VOXEL_SCALE

    # Presorted seed order: min(remaining) per iteration is O(n) and turns
    # the whole merge quadratic on large unmergeable groups.
    seed_order = sorted(remaining)
    seed_idx = 0

    while remaining:
        while seed_order[seed_idx] not in remaining:
            seed_idx += 1
        start = seed_order[seed_idx]
        sx, sy, sz = start
        template = voxels[start]

        ex = sx
        while (ex + 1, sy, sz) in remaining and (ex + 1 - sx + 1) <= max_dimension:
            ex += 1

        ey = sy
        can_extend_y = True
        while can_extend_y and (ey + 1 - sy + 1) <= max_dimension:
            for x in range(sx, ex + 1):
                if (x, ey + 1, sz) not in remaining:
                    can_extend_y = False
                    break
            if can_extend_y:
                ey += 1

        ez = sz
        can_extend_z = True
        while can_extend_z and (ez + 1 - sz + 1) <= max_dimension:
            for x in range(sx, ex + 1):
                for y in range(sy, ey + 1):
                    if (x, y, ez + 1) not in remaining:
                        can_extend_z = False
                        break
                if not can_extend_z:
                    break
            if can_extend_z:
                ez += 1

        for x in range(sx, ex + 1):
            for y in range(sy, ey + 1):
                for z in range(sz, ez + 1):
                    remaining.discard((x, y, z))

        merged_part = {
            "bounds": {"x": ex - sx + 1, "y": ey - sy + 1, "z": ez - sz + 1},
            "shapeId": template.get("shapeId"),
            "color": template.get("color"),
            "pos": {"x": float(sx), "y": float(sy), "z": float(sz)},
            "xaxis": template.get("xaxis", 1),
            "zaxis": template.get("zaxis", 3),
        }
        if template.get("is_transparent"):
            merged_part["is_transparent"] = True
        if template.get("is_connector"):
            merged_part["is_connector"] = True
        merged.append(merged_part)

    return merged


def greedy_mesh_merge(blueprint, quantize_step=8, max_dimension=None):
    """Combine adjacent unit voxels into larger bounded parts."""
    if not blueprint.get("bodies") or not blueprint["bodies"][0].get("childs"):
        return blueprint

    parts = blueprint["bodies"][0]["childs"]
    if not parts:
        return blueprint

    groups = defaultdict(dict)
    large_parts = []
    for part in parts:
        bounds = part.get("bounds", {"x": 1, "y": 1, "z": 1})
        if (
            bounds.get("x", 1) != 1 or bounds.get("y", 1) != 1 or bounds.get("z", 1) != 1
            or part.get("controller") or part.get("is_lamp")
        ):
            # Interactive parts (lamps) must never merge into boxes
            large_parts.append(part)
            continue
        key = _part_key(part, quantize_step)
        pos = part["pos"]
        groups[key][(int(pos["x"]), int(pos["y"]), int(pos["z"]))] = part

    merged_parts = list(large_parts)
    for key, voxels in groups.items():
        merged = _greedy_merge_group(voxels, max_dimension=max_dimension)
        for part in merged:
            part["color"] = key[1]
        merged_parts.extend(merged)

    blueprint["bodies"][0]["childs"] = merged_parts
    return blueprint
