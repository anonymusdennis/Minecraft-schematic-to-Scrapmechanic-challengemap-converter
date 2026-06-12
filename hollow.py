"""WorldEdit //hollow implementation for assembled voxel blueprints."""

NEIGHBOR_OFFSETS = (
    (1, 0, 0), (-1, 0, 0),
    (0, 1, 0), (0, -1, 0),
    (0, 0, 1), (0, 0, -1),
)

# Geometry thinner than this (in voxels) is kept intact — hollowing would destroy it.
MIN_SAFE_HOLLOW_THICKNESS = 4


def bbox_min_extent(occupied) -> int:
    """Minimum axis extent of an occupied voxel set (0 when empty)."""
    if not occupied:
        return 0
    xs = [p[0] for p in occupied]
    ys = [p[1] for p in occupied]
    zs = [p[2] for p in occupied]
    return min(
        max(xs) - min(xs) + 1,
        max(ys) - min(ys) + 1,
        max(zs) - min(zs) + 1,
    )


def should_hollow_geometry(occupied, min_thickness=MIN_SAFE_HOLLOW_THICKNESS) -> bool:
    """
    Return False when the occupied shape is too thin to hollow safely
    (e.g. a 4-voxel-thick glass panel should stay solid).
    """
    if not occupied:
        return False
    return bbox_min_extent(occupied) > min_thickness


def _part_position(part):
    pos = part["pos"]
    return int(pos["x"]), int(pos["y"]), int(pos["z"])


def iter_part_voxels(part):
    """Yield every integer cell covered by a part (unit or dynamic mesh bounds)."""
    cell = part.get("occupied_cell")
    if cell is not None:
        # Rotated interactive parts (lamps): pos is rotation-offset, the
        # actually occupied world cell is stored explicitly.
        yield (int(cell[0]), int(cell[1]), int(cell[2]))
        return
    pos = part["pos"]
    bounds = part.get("bounds", {"x": 1, "y": 1, "z": 1})
    sx, sy, sz = int(pos["x"]), int(pos["y"]), int(pos["z"])
    bx, by, bz = int(bounds.get("x", 1)), int(bounds.get("y", 1)), int(bounds.get("z", 1))
    for x in range(sx, sx + bx):
        for y in range(sy, sy + by):
            for z in range(sz, sz + bz):
                yield (x, y, z)


def part_intersects_positions(part, positions):
    """True when any voxel in *part*'s bounds lies in *positions*."""
    for pos in iter_part_voxels(part):
        if pos in positions:
            return True
    return False


def _occupied_from_unit_parts(parts):
    return {_part_position(part) for part in parts}


def occupied_from_parts(parts, include_bounds=True):
    """
    Occupied voxel positions for hollow / connectivity.

    When *include_bounds* is True, expanded parts (post mesh-merge) occupy every
    cell inside their bounds box — required for dynamic meshes.
    """
    occupied = set()
    for part in parts:
        cell = part.get("occupied_cell")
        if cell is not None:
            occupied.add((int(cell[0]), int(cell[1]), int(cell[2])))
            continue
        pos = part["pos"]
        bounds = part.get("bounds", {"x": 1, "y": 1, "z": 1})
        bx = int(bounds.get("x", 1))
        by = int(bounds.get("y", 1))
        bz = int(bounds.get("z", 1))
        sx, sy, sz = int(pos["x"]), int(pos["y"]), int(pos["z"])
        if include_bounds and (bx > 1 or by > 1 or bz > 1):
            for x in range(sx, sx + bx):
                for y in range(sy, sy + by):
                    for z in range(sz, sz + bz):
                        occupied.add((x, y, z))
        else:
            occupied.add((sx, sy, sz))
    return occupied


def is_surface_voxel(position, occupied):
    """True when any 6-connected neighbor is not occupied (WorldEdit thickness 0)."""
    x, y, z = position
    for dx, dy, dz in NEIGHBOR_OFFSETS:
        if (x + dx, y + dy, z + dz) not in occupied:
            return True
    return False


def surface_positions(occupied, thickness=0):
    """Return positions to keep for the given solid topology."""
    if thickness <= 0:
        return {pos for pos in occupied if is_surface_voxel(pos, occupied)}

    from collections import deque

    distance = {}
    queue = deque()
    for pos in occupied:
        if is_surface_voxel(pos, occupied):
            distance[pos] = 0
            queue.append(pos)

    while queue:
        current = queue.popleft()
        cx, cy, cz = current
        current_dist = distance[current]
        if current_dist >= thickness:
            continue
        for dx, dy, dz in NEIGHBOR_OFFSETS:
            neighbor = (cx + dx, cy + dy, cz + dz)
            if neighbor in occupied and neighbor not in distance:
                distance[neighbor] = current_dist + 1
                queue.append(neighbor)

    return {pos for pos, dist in distance.items() if dist <= thickness}


def worldedit_hollow(blueprint, thickness=0, topology_occupied=None):
    """
    Remove interior voxels using WorldEdit //hollow logic.

    When *topology_occupied* is set, surface tests use that solid weld volume while
    parts are taken from the blueprint (supports sparse 3D-texture shells and merged
    dynamic meshes via bounds expansion on the topology set).
    """
    if not blueprint.get("bodies") or not blueprint["bodies"][0].get("childs"):
        return blueprint

    parts = blueprint["bodies"][0]["childs"]
    if not parts:
        return blueprint

    if topology_occupied is not None:
        occupied = topology_occupied
    else:
        occupied = occupied_from_parts(parts, include_bounds=True)

    kept_positions = surface_positions(occupied, thickness)
    kept = [p for p in parts if part_intersects_positions(p, kept_positions)]

    blueprint["bodies"][0]["childs"] = kept
    return blueprint


def safe_worldedit_hollow(parts, min_thickness=MIN_SAFE_HOLLOW_THICKNESS, **kwargs):
    """
    Apply //hollow only when geometry is thicker than *min_thickness* voxels.
    Thin shells (glass panes, bars, etc.) are returned unchanged.
    """
    if not parts:
        return parts
    occupied = occupied_from_parts(parts, include_bounds=True)
    if not should_hollow_geometry(occupied, min_thickness):
        return parts
    bp = worldedit_hollow({"bodies": [{"childs": parts}]}, **kwargs)
    return bp["bodies"][0]["childs"]
