"""Bridge disconnected voxel islands with highlighted connector lines."""

from collections import deque

from config import CONNECTOR_COLOR
from hollow import NEIGHBOR_OFFSETS, is_surface_voxel, iter_part_voxels, occupied_from_parts


def find_connected_components(occupied):
    """Return a list of 6-connected component position sets."""
    remaining = set(occupied)
    components = []
    while remaining:
        start = next(iter(remaining))
        component = set()
        queue = deque([start])
        remaining.discard(start)
        component.add(start)
        while queue:
            x, y, z = queue.popleft()
            for dx, dy, dz in NEIGHBOR_OFFSETS:
                neighbor = (x + dx, y + dy, z + dz)
                if neighbor in remaining:
                    remaining.discard(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        components.append(component)
    return components


def count_connected_components(occupied):
    return len(find_connected_components(occupied))


def count_connected_component_parts(parts, include_bounds=True):
    """Count 6-connected components using merged part bounds (dynamic meshes)."""
    return count_connected_components(occupied_from_parts(parts, include_bounds))


_iter_part_voxels = iter_part_voxels


def connect_floating_component_parts(parts, color=None, shape_id=None, match_island_color=False):
    """Bridge disconnected merged meshes; returns parts plus any connector voxels."""
    voxel_grid = {}
    for part in parts:
        for pos in _iter_part_voxels(part):
            voxel_grid[pos] = part

    if count_connected_components(set(voxel_grid.keys())) <= 1:
        return parts

    occupied_before = set(voxel_grid.keys())
    connect_floating_components(
        voxel_grid, color=color, shape_id=shape_id,
        match_island_color=match_island_color,
    )

    new_parts = list(parts)
    for pos, part in voxel_grid.items():
        if part.get("is_connector") and pos not in occupied_before:
            new_parts.append(part)
    return new_parts


def enforce_single_structure_parts(parts, progress=True, max_iters=10):
    """
    Guarantee ALL parts (structure, transparent, lamps, entities) form one
    6-connected component so the game loads them as a single welded body.
    Bridges are colored like the island they attach, to stay unobtrusive.
    """
    components = count_connected_component_parts(parts)
    if components <= 1:
        return parts

    before_parts = len(parts)
    before_components = components
    for _ in range(max_iters):
        parts = connect_floating_component_parts(parts, match_island_color=True)
        components = count_connected_component_parts(parts)
        if components <= 1:
            break

    if progress:
        print(
            f"  Final weld enforcement: +{len(parts) - before_parts} bridge voxels "
            f"({before_components} -> {components} component(s))"
        )
    if components > 1:
        print(f"  WARNING: {components} components remain after weld enforcement")
    return parts


def _boundary_voxels(component):
    """Exterior-facing voxels on a component (good bridge endpoints)."""
    occupied = set(component)
    return {pos for pos in component if is_surface_voxel(pos, occupied)}


def _nearest_pair(comp_a, comp_b, max_samples=5000):
    """Closest boundary voxel pair between two components."""
    surf_a = _boundary_voxels(comp_a) or comp_a
    surf_b = _boundary_voxels(comp_b) or comp_b
    return _nearest_pair_surfaces(surf_a, surf_b, max_samples)


def _nearest_pair_surfaces(surf_a, surf_b, max_samples=5000):
    """Closest voxel pair between two precomputed surface sets."""
    if len(surf_a) * len(surf_b) > max_samples * max_samples:
        surf_a = _sample_positions(surf_a, max_samples)
        surf_b = _sample_positions(surf_b, max_samples)

    # Search outward from the smaller surface against a sampled larger one
    if len(surf_a) * len(surf_b) > 2_000_000:
        bigger, smaller = (surf_a, surf_b) if len(surf_a) > len(surf_b) else (surf_b, surf_a)
        bigger = _sample_positions(bigger, max(1, 2_000_000 // max(len(smaller), 1)))
        surf_a, surf_b = (bigger, smaller) if len(surf_a) > len(surf_b) else (smaller, bigger)

    best = None
    best_dist = None
    for pa in surf_a:
        for pb in surf_b:
            dist = (
                (pa[0] - pb[0]) ** 2
                + (pa[1] - pb[1]) ** 2
                + (pa[2] - pb[2]) ** 2
            )
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best = (pa, pb)
    return best


def _sample_positions(positions, max_count):
    items = sorted(positions)
    if len(items) <= max_count:
        return items
    step = max(1, len(items) // max_count)
    return items[::step][:max_count]


def _manhattan_line(p0, p1):
    """6-connected voxel path from p0 to p1 (one axis at a time)."""
    x, y, z = p0
    x1, y1, z1 = p1
    path = [(x, y, z)]
    while (x, y, z) != (x1, y1, z1):
        if x != x1:
            x += 1 if x1 > x else -1
        elif y != y1:
            y += 1 if y1 > y else -1
        elif z != z1:
            z += 1 if z1 > z else -1
        path.append((x, y, z))
    return path


def _make_connector_part(pos, color, shape_id):
    return {
        "bounds": {"x": 1, "y": 1, "z": 1},
        "shapeId": shape_id,
        "color": color,
        "pos": {"x": float(pos[0]), "y": float(pos[1]), "z": float(pos[2])},
        "xaxis": 1,
        "zaxis": 3,
        "is_connector": True,
    }


def _island_color(voxel_grid, island, fallback):
    """Representative color of an island's parts (for unobtrusive bridges)."""
    for pos in island:
        part = voxel_grid.get(pos)
        if part is not None:
            part_color = part.get("color")
            if part_color:
                return part_color
    return fallback


def _shortest_escape_path(island, occupied, max_expansions=150000):
    """
    BFS from *island* through empty space to the nearest occupied voxel that
    is NOT part of the island. Returns the list of empty bridge positions, or
    None when nothing is reachable within the expansion budget.
    """
    others = occupied - island
    if not others:
        return None

    parents = {}
    queue = deque()
    for pos in _boundary_voxels(island) or island:
        parents[pos] = None
        queue.append(pos)

    expansions = 0
    while queue and expansions < max_expansions:
        current = queue.popleft()
        expansions += 1
        x, y, z = current
        for dx, dy, dz in NEIGHBOR_OFFSETS:
            neighbor = (x + dx, y + dy, z + dz)
            if neighbor in parents:
                continue
            if neighbor in others:
                # Reconstruct the empty-space path back to the island
                path = []
                node = current
                while node is not None and node not in island:
                    path.append(node)
                    node = parents[node]
                path.reverse()
                return path
            if neighbor in island:
                continue
            parents[neighbor] = current
            queue.append(neighbor)
    return None


def connect_floating_components(voxel_grid, color=None, shape_id=None, match_island_color=False):
    """
    Bridge each disconnected island to its nearest occupied neighbor with a
    1-voxel-thick connector line (shortest empty-space path via BFS, falling
    back to a Manhattan line toward the main component for far islands).
    With *match_island_color* bridges take the island's color instead of the
    highlight color.
    """
    from conversion_settings import CURRENT as _settings

    color = color or CONNECTOR_COLOR
    shape_id = shape_id or _settings.connector_shape_id()

    components = find_connected_components(set(voxel_grid.keys()))
    if len(components) <= 1:
        return 0

    components.sort(key=len, reverse=True)
    occupied = set(voxel_grid.keys())
    main_surface = None
    added = 0

    for island in components[1:]:
        bridge_color = (
            _island_color(voxel_grid, island, color) if match_island_color else color
        )
        path = _shortest_escape_path(island, occupied)
        if path is None:
            # Far island: straight Manhattan line to the main component
            if main_surface is None:
                main_surface = _boundary_voxels(components[0]) or set(components[0])
            island_surface = _boundary_voxels(island) or set(island)
            start, end = _nearest_pair_surfaces(main_surface, island_surface)
            path = [p for p in _manhattan_line(end, start) if p not in occupied]
        for pos in path:
            if pos in voxel_grid:
                continue
            voxel_grid[pos] = _make_connector_part(pos, bridge_color, shape_id)
            occupied.add(pos)
            added += 1

    return added
