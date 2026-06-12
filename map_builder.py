"""Build a welded solid voxel map from a parsed Minecraft schematic."""

from block_placement import placement_rotation
from block_model_aliases import is_sparse_shape_block
from blockstate_resolver import has_blockstate_definition
from block_voxels import block_appearance, opaque_cell_voxels, solid_cube_local
from blueprint_writer import rgba_to_hex
from component_connector import (
    connect_floating_component_parts,
    connect_floating_components,
    count_connected_component_parts,
    count_connected_components,
)
from config import VOXEL_SCALE
from hollow import is_surface_voxel, worldedit_hollow
from mesh_optimizer import greedy_mesh_merge
from transparent_blocks import build_all_transparent_blocks, is_transparent_block


def _build_block_index(mc_blocks):
    return {(b["x"], b["y"], b["z"]): b for b in mc_blocks}


def _make_block_lookup(block_index):
    def block_at(x, y, z):
        block = block_index.get((x, y, z))
        return block if block else None

    def block_name_at(x, y, z):
        block = block_at(x, y, z)
        return block["name"] if block else None

    return block_at, block_name_at


def _placement_rotation(mc_block, assets_dir, block_at=None):
    return placement_rotation(mc_block, assets_dir, block_at)


def determine_rotation(block_name, data_value):
    """Backwards-compatible wrapper; prefer placement_rotation(mc_block, ...)."""
    from block_placement import determine_rotation as _legacy_determine_rotation
    return _legacy_determine_rotation(block_name, data_value)


def _sm_position(mc_x, mc_y, mc_z, local_x, local_y, local_z):
    return (
        mc_x * VOXEL_SCALE + local_x,
        mc_y * VOXEL_SCALE + local_y,
        mc_z * VOXEL_SCALE + local_z,
    )


def _solid_cell_positions(mc_block):
    """All SM voxel positions for a welded opaque MC cell (connectivity topology)."""
    positions = []
    for local_x in range(VOXEL_SCALE):
        for local_y in range(VOXEL_SCALE):
            for local_z in range(VOXEL_SCALE):
                positions.append(
                    _sm_position(
                        mc_block["x"], mc_block["y"], mc_block["z"],
                        local_x, local_y, local_z,
                    )
                )
    return positions


def _seal_through_holes(local_voxels):
    """
    Opaque blocks with carved 3D models (lattices, recessed faces) can have
    columns with no voxels at all; after hollowing, those read as windows into
    the empty interior. Cap both boundary cells of every fully-empty column
    with the block's dominant color. Sparse/decoration shapes are left alone.
    """
    if not local_voxels or len(local_voxels) >= 4096 or len(local_voxels) < 2048:
        return local_voxels

    from collections import Counter

    dominant = Counter(local_voxels.values()).most_common(1)[0][0]
    sealed = dict(local_voxels)
    S = VOXEL_SCALE
    for axis in range(3):
        for u in range(S):
            for v in range(S):
                line = [
                    (w, u, v) if axis == 0 else (u, w, v) if axis == 1 else (u, v, w)
                    for w in range(S)
                ]
                if any(p in local_voxels for p in line):
                    continue
                sealed.setdefault(line[0], dominant)
                sealed.setdefault(line[-1], dominant)
    return sealed


def _fill_opaque_cell(voxel_grid, mc_block, appearance, xaxis, zaxis, local_voxels=None):
    if local_voxels is None:
        local_voxels = appearance["local_voxels"]
    local_voxels = _seal_through_holes(local_voxels)
    for (local_x, local_y, local_z), color in local_voxels.items():
        color_value = color
        if isinstance(color_value, tuple):
            color_hex = rgba_to_hex(color_value)
        else:
            color_hex = str(color_value).upper()
        sm_pos = _sm_position(
            mc_block["x"], mc_block["y"], mc_block["z"],
            local_x, local_y, local_z,
        )
        voxel_grid[sm_pos] = {
            "bounds": {"x": 1, "y": 1, "z": 1},
            "shapeId": appearance["shapeId"],
            "color": color_hex,
            "pos": {"x": float(sm_pos[0]), "y": float(sm_pos[1]), "z": float(sm_pos[2])},
            "xaxis": xaxis,
            "zaxis": zaxis,
            "is_transparent": False,
        }


def build_voxel_map(schematic_data, assets_dir, progress=True, connect_islands=True):
    """
    Build opaque welded structure only. Transparent MC blocks are deferred until
    after structure hollow/merge in process_voxel_map.
    """
    mc_blocks = schematic_data["blocks"]
    block_index = _build_block_index(mc_blocks)
    block_at, block_name_at = _make_block_lookup(block_index)
    opaque_mc_positions = {
        (b["x"], b["y"], b["z"])
        for b in mc_blocks
        if not is_transparent_block(b["name"]) and b["name"] not in ("water", "lava")
    }

    from conversion_settings import CURRENT as settings
    from light_emission import extract_lamps, is_light_block, reset_controller_ids

    reset_controller_ids()

    appearance_cache = {}
    structure_grid = {}
    solid_occupancy = set()
    transparent_mc_blocks = []
    lamp_parts = []
    lamp_positions = set()
    stats = {
        "opaque_cells": 0,
        "transparent_cells": 0,
        "transparent_voxels": 0,
        "missing": set(),
        "appearance_cache": appearance_cache,
        "opaque_mc_blocks": [],
        "transparent_mc_blocks": transparent_mc_blocks,
        "solid_occupancy": solid_occupancy,
        "opaque_mc_positions": opaque_mc_positions,
        "block_at": block_at,
        "lamp_parts": lamp_parts,
        "lamp_positions": lamp_positions,
    }

    if progress:
        print(f"Building welded map from {len(mc_blocks)} MC blocks...")
        print(
            f"  Dimensions: {schematic_data['width']}x{schematic_data['height']}"
            f"x{schematic_data['length']} | cell size: {VOXEL_SCALE}³"
        )

    import progress as progress_reporter

    for idx, mc_block in enumerate(mc_blocks):
        if progress and idx % 100 == 0:
            pct = 100 * idx // max(len(mc_blocks), 1)
            print(f"  Placing block {idx + 1}/{len(mc_blocks)} ({pct}%)...")
        if idx % 50 == 0:
            progress_reporter.report(
                "build",
                idx / max(len(mc_blocks), 1),
                f"Placing blocks {idx + 1}/{len(mc_blocks)}",
            )

        block_name = mc_block["name"]

        if block_name in ("water", "lava"):
            if settings.water_mode == "skip":
                continue
            transparent_mc_blocks.append(mc_block)
            stats["transparent_cells"] += 1
            continue

        if is_transparent_block(block_name):
            transparent_mc_blocks.append(mc_block)
            stats["transparent_cells"] += 1
            continue

        xaxis, zaxis = placement_rotation(mc_block, assets_dir, block_at=block_at)

        variant_block = (
            is_sparse_shape_block(block_name)
            or has_blockstate_definition(block_name, assets_dir)
        )
        if variant_block:
            from blockstate_resolver import resolved_block_properties

            props = resolved_block_properties(block_name, mc_block, block_at)
            cache_key = (block_name, tuple(sorted(props.items())))
            if cache_key not in appearance_cache:
                local_voxels = opaque_cell_voxels(
                    block_name, assets_dir, mc_block=mc_block, block_at=block_at
                )
                if not local_voxels and not is_sparse_shape_block(block_name):
                    local_voxels = solid_cube_local(block_name, assets_dir)
                appearance_cache[cache_key] = block_appearance(
                    block_name,
                    assets_dir,
                    local_voxels=local_voxels,
                    mc_block=mc_block,
                    block_at=block_at,
                )
            appearance = appearance_cache[cache_key]
        elif block_name not in appearance_cache:
            local_voxels = opaque_cell_voxels(block_name, assets_dir)
            if not local_voxels and not is_sparse_shape_block(block_name):
                local_voxels = solid_cube_local(block_name, assets_dir)
            appearance_cache[block_name] = block_appearance(
                block_name, assets_dir, local_voxels=local_voxels
            )
            appearance = appearance_cache[block_name]
        else:
            appearance = appearance_cache[block_name]
        if not appearance.get("found", True):
            stats["missing"].add(block_name)

        cell_voxels = None
        if settings.lights_enabled and is_light_block(block_name):
            cell_voxels = dict(appearance["local_voxels"])
            lamps = extract_lamps(mc_block, cell_voxels, opaque_mc_positions, settings)
            if lamps:
                lamp_parts.extend(lamps)
                if settings.light_mode == "replace":
                    for lamp in lamps:
                        lamp_positions.add(tuple(lamp["occupied_cell"]))

        solid_occupancy.update(_solid_cell_positions(mc_block))
        _fill_opaque_cell(
            structure_grid, mc_block, appearance, xaxis, zaxis, local_voxels=cell_voxels
        )
        stats["opaque_cells"] += 1
        stats["opaque_mc_blocks"].append(mc_block)

    components_before = count_connected_components(set(structure_grid.keys()))
    stats["connectors_added"] = 0

    if connect_islands and components_before > 1:
        stats["connectors_added"] = connect_floating_components(structure_grid)

    structure_parts = [structure_grid[pos] for pos in sorted(structure_grid)]
    blueprint = {"bodies": [{"childs": structure_parts}], "version": 4}
    stats["unique_voxels"] = len(structure_parts)
    stats["structure_voxels"] = len(structure_parts)
    stats["components"] = count_connected_components(set(structure_grid.keys()))
    stats["components_before_connect"] = components_before

    if progress:
        print(
            f"  Opaque welded: {stats['structure_voxels']} voxels "
            f"({stats['opaque_cells']} cells)"
        )
        print(
            f"  Transparent deferred: {stats['transparent_cells']} cells "
            f"(welded after structure hollow/merge)"
        )
        print(f"  Structure components: {components_before} before bridges")
        if stats["connectors_added"]:
            print(
                f"  Connector bridges: {stats['connectors_added']} highlighted voxels "
                f"({components_before} -> {count_connected_components(set(structure_grid))} structure)"
            )
        if stats["missing"]:
            print(
                f"  Blocks using fallback color ({len(stats['missing'])}): "
                f"{', '.join(sorted(stats['missing'])[:8])}"
                f"{'...' if len(stats['missing']) > 8 else ''}"
            )

    return blueprint, stats


def _dedupe_parts_at_positions(parts):
    final_parts = []
    seen_positions = set()
    for part in reversed(parts):
        key = (int(part["pos"]["x"]), int(part["pos"]["y"]), int(part["pos"]["z"]))
        if key not in seen_positions:
            seen_positions.add(key)
            final_parts.append(part)
    final_parts.reverse()
    return final_parts


def deduplicate_voxels(blueprint):
    if not blueprint.get("bodies") or not blueprint["bodies"][0].get("childs"):
        return blueprint

    parts = blueprint["bodies"][0]["childs"]
    structure = [p for p in parts if not p.get("is_transparent")]
    transparent = [p for p in parts if p.get("is_transparent")]
    # Structure (and connector voxels) win over glass at the same anchor position.
    merged = _dedupe_parts_at_positions(structure + transparent)
    blueprint["bodies"][0]["childs"] = merged
    return blueprint


def _mc_cell_center_sm(mc_block):
    half = VOXEL_SCALE // 2
    return _sm_position(mc_block["x"], mc_block["y"], mc_block["z"], half, half, half)


def _cell_has_structure_voxel(mc_block, occupied):
    bx = mc_block["x"] * VOXEL_SCALE
    by = mc_block["y"] * VOXEL_SCALE
    bz = mc_block["z"] * VOXEL_SCALE
    for lx in range(VOXEL_SCALE):
        for ly in range(VOXEL_SCALE):
            for lz in range(VOXEL_SCALE):
                if (bx + lx, by + ly, bz + lz) in occupied:
                    return True
    return False


def _reconnect_structure(structure_grid, connect_islands=True):
    """Return structure parts list; bridge islands when needed."""
    if connect_islands and count_connected_components(set(structure_grid.keys())) > 1:
        connect_floating_components(structure_grid)
    return [structure_grid[pos] for pos in sorted(structure_grid)]


def _ensure_block_anchors(structure_parts, opaque_mc_blocks, appearance_cache, assets_dir):
    """
    After hollow, interior MC cells can lose every voxel. Place one anchor voxel
    per empty cell so blocks are not visually missing.
    """
    occupied = {
        (int(p["pos"]["x"]), int(p["pos"]["y"]), int(p["pos"]["z"]))
        for p in structure_parts
    }
    anchors = []
    for mc_block in opaque_mc_blocks:
        if _cell_has_structure_voxel(mc_block, occupied):
            continue
        block_name = mc_block["name"]
        if block_name not in appearance_cache:
            local_voxels = opaque_cell_voxels(block_name, assets_dir)
            appearance_cache[block_name] = block_appearance(
                block_name, assets_dir, local_voxels=local_voxels
            )
        appearance = appearance_cache[block_name]
        xaxis, zaxis = placement_rotation(mc_block, assets_dir)
        sm_pos = _mc_cell_center_sm(mc_block)
        part = {
            "bounds": {"x": 1, "y": 1, "z": 1},
            "shapeId": appearance["shapeId"],
            "color": appearance["color"],
            "pos": {"x": float(sm_pos[0]), "y": float(sm_pos[1]), "z": float(sm_pos[2])},
            "xaxis": xaxis,
            "zaxis": zaxis,
            "is_transparent": False,
        }
        anchors.append(part)
        occupied.add((int(sm_pos[0]), int(sm_pos[1]), int(sm_pos[2])))
    return structure_parts + anchors


def process_voxel_map(
    blueprint,
    hollow=True,
    merge=True,
    progress=True,
    opaque_mc_blocks=None,
    appearance_cache=None,
    assets_dir=None,
    solid_occupancy=None,
    connect_islands=True,
    transparent_mc_blocks=None,
    opaque_mc_positions=None,
    block_at=None,
    lamp_parts=None,
    lamp_positions=None,
):
    """Hollow and merge opaque structure first; weld transparent blocks at the end."""
    from conversion_settings import CURRENT as settings

    quantize = settings.quantize_step()
    hollow_thickness = max(0, int(settings.wall_thickness) - 1)
    lamp_parts = list(lamp_parts or [])
    lamp_positions = set(lamp_positions or set())

    parts = blueprint["bodies"][0]["childs"]
    structure_parts = [p for p in parts if not p.get("is_transparent") and not p.get("is_lamp")]
    transparent_parts = [p for p in parts if p.get("is_transparent")]

    if hollow and structure_parts and solid_occupancy:
        before = len(structure_parts)
        components_before = count_connected_components(solid_occupancy)
        struct_bp = {"bodies": [{"childs": structure_parts}], "version": 4}
        struct_bp = worldedit_hollow(
            struct_bp, topology_occupied=solid_occupancy, thickness=hollow_thickness
        )
        structure_parts = struct_bp["bodies"][0]["childs"]
        # NOTE: no blanket "shell fill" here — carved models (inset furnace
        # fronts, lamp lattices) intentionally leave surface voxels empty and
        # must NOT be plastered over with flat average-color filler. Interior
        # visibility is prevented per block by _seal_through_holes, and
        # connectivity by the final single-structure weld pass.
        after = len(structure_parts)
        if progress:
            pct = 100 * (1 - after / max(before, 1))
            print(
                f"  WorldEdit hollow (solid topology): {before} -> {after} "
                f"({pct:.1f}% reduction) [{components_before} component(s) topology]"
            )
        if progress and transparent_parts:
            print(f"  Legacy transparent parts in blueprint: {len(transparent_parts)}")

        structure_grid = {
            (int(p["pos"]["x"]), int(p["pos"]["y"]), int(p["pos"]["z"])): p
            for p in structure_parts
        }
        components_after_hollow = count_connected_components(set(structure_grid.keys()))
        if connect_islands and components_after_hollow > 1:
            bridges = connect_floating_components(structure_grid)
            structure_parts = [structure_grid[pos] for pos in sorted(structure_grid)]
            if progress:
                print(
                    f"  Post-hollow bridges: {bridges} voxels "
                    f"({components_after_hollow} -> "
                    f"{count_connected_components(set(structure_grid.keys()))} structure)"
                )
        elif progress:
            print(
                f"  Structure connectivity after hollow: "
                f"{components_after_hollow} component(s)"
            )

    elif hollow and structure_parts:
        struct_bp = {"bodies": [{"childs": structure_parts}], "version": 4}
        before = len(structure_parts)
        struct_bp = worldedit_hollow(struct_bp, thickness=hollow_thickness)
        structure_parts = struct_bp["bodies"][0]["childs"]
        if progress:
            print(
                f"  WorldEdit hollow (structure): {before} -> {len(structure_parts)}"
            )

    if merge and structure_parts:
        struct_bp = {"bodies": [{"childs": structure_parts}], "version": 4}
        before = len(structure_parts)
        struct_bp = greedy_mesh_merge(
            struct_bp, quantize_step=quantize, max_dimension=VOXEL_SCALE
        )
        struct_bp = greedy_mesh_merge(
            struct_bp, quantize_step=quantize, max_dimension=VOXEL_SCALE
        )
        struct_bp = deduplicate_voxels(struct_bp)
        structure_parts = struct_bp["bodies"][0]["childs"]
        after = len(structure_parts)
        if progress:
            pct = 100 * (1 - after / max(before, 1))
            print(f"  Mesh merge (structure): {before} -> {after} ({pct:.1f}% reduction)")

    if merge and transparent_parts:
        trans_bp = {"bodies": [{"childs": transparent_parts}], "version": 4}
        before = len(transparent_parts)
        trans_bp = greedy_mesh_merge(
            trans_bp, quantize_step=quantize, max_dimension=VOXEL_SCALE
        )
        transparent_parts = trans_bp["bodies"][0]["childs"]
        if progress and before != len(transparent_parts):
            print(
                f"  Mesh merge (transparent): {before} -> {len(transparent_parts)} "
                f"({100 * (1 - len(transparent_parts) / max(before, 1)):.1f}% reduction)"
            )

    # Weld deferred transparent blocks after structure is fully hollowed and merged.
    if transparent_mc_blocks and assets_dir is not None:
        if appearance_cache is None:
            appearance_cache = {}
        if opaque_mc_positions is None:
            opaque_mc_positions = set()
        welded, deferred_lamps = build_all_transparent_blocks(
            transparent_mc_blocks,
            assets_dir,
            opaque_mc_positions,
            appearance_cache,
            block_at=block_at,
        )
        lamp_parts.extend(deferred_lamps)
        transparent_parts.extend(welded)
        stats_trans = len(welded)
        if merge and welded:
            trans_bp = {"bodies": [{"childs": transparent_parts}], "version": 4}
            before = len(transparent_parts)
            trans_bp = greedy_mesh_merge(
                trans_bp, quantize_step=quantize, max_dimension=VOXEL_SCALE
            )
            transparent_parts = trans_bp["bodies"][0]["childs"]
            if progress:
                print(
                    f"  Transparent weld (end): +{stats_trans} voxels from "
                    f"{len(transparent_mc_blocks)} cells"
                )
                if before != len(transparent_parts):
                    print(
                        f"  Mesh merge (transparent): {before} -> {len(transparent_parts)} "
                        f"({100 * (1 - len(transparent_parts) / max(before, 1)):.1f}% reduction)"
                    )
        elif progress:
            print(
                f"  Transparent weld (end): +{stats_trans} voxels from "
                f"{len(transparent_mc_blocks)} cells"
            )

    if merge and structure_parts and connect_islands:
        components_merged = count_connected_component_parts(structure_parts)
        if components_merged > 1:
            before = len(structure_parts)
            for _ in range(20):
                structure_parts = connect_floating_component_parts(structure_parts)
                if count_connected_component_parts(structure_parts) <= 1:
                    break
            after_components = count_connected_component_parts(structure_parts)
            if progress:
                print(
                    f"  Post-merge bridges: +{len(structure_parts) - before} parts "
                    f"({components_merged} -> {after_components} structure)"
                )

    blueprint["bodies"][0]["childs"] = structure_parts + transparent_parts
    blueprint = deduplicate_voxels(blueprint)
    if lamp_parts:
        # Lamps go in last so they win position conflicts and skip merging.
        blueprint["bodies"][0]["childs"] = blueprint["bodies"][0]["childs"] + lamp_parts
        if progress:
            print(f"  Light emission: {len(lamp_parts)} lamp(s) placed")

    if connect_islands:
        final_structure = [
            p for p in blueprint["bodies"][0]["childs"] if not p.get("is_transparent")
        ]
        components_final = count_connected_component_parts(final_structure)
        if components_final > 1:
            before = len(final_structure)
            for _ in range(50):
                final_structure = connect_floating_component_parts(final_structure)
                if count_connected_component_parts(final_structure) <= 1:
                    break
            after_components = count_connected_component_parts(final_structure)
            transparent_final = [
                p for p in blueprint["bodies"][0]["childs"] if p.get("is_transparent")
            ]
            blueprint["bodies"][0]["childs"] = final_structure + transparent_final
            if progress:
                print(
                    f"  Post-dedupe bridges: +{len(final_structure) - before} parts "
                    f"({components_final} -> {after_components} structure)"
                )

    if progress:
        final_structure = [p for p in blueprint["bodies"][0]["childs"] if not p.get("is_transparent")]
        final_components = count_connected_component_parts(final_structure)
        print(f"  Final structure components: {final_components}")

    if connect_islands:
        # Hard guarantee: EVERYTHING (structure, transparent, lamps) must be
        # one welded component or the game splits it into falling bodies.
        from component_connector import enforce_single_structure_parts

        blueprint["bodies"][0]["childs"] = enforce_single_structure_parts(
            blueprint["bodies"][0]["childs"], progress=progress
        )

    if settings.anchor_pole:
        blueprint["bodies"][0]["childs"] = _add_anchor_pole(
            blueprint["bodies"][0]["childs"], settings, progress=progress
        )

    return blueprint


def _add_anchor_pole(parts, settings, progress=True):
    """
    Add a 2x2 indestructible-glass pole below the structure's footprint
    center so it stands welded on a fixed anchor down at platform level.
    """
    from config import CONNECTOR_COLOR
    from hollow import occupied_from_parts

    if not parts:
        return parts
    occupied = occupied_from_parts(parts)
    min_y = min(p[1] for p in occupied)
    bottom = [p for p in occupied if p[1] == min_y]
    cx = sum(p[0] for p in bottom) / len(bottom)
    cz = sum(p[2] for p in bottom) / len(bottom)
    base = min(bottom, key=lambda p: (p[0] - cx) ** 2 + (p[2] - cz) ** 2)

    height = max(1, int(settings.anchor_pole_height))
    pole = {
        "bounds": {"x": 2, "y": height, "z": 2},
        "shapeId": settings.connector_shape_id(),
        "color": CONNECTOR_COLOR,
        "pos": {"x": base[0], "y": min_y - height, "z": base[2]},
        "xaxis": 1,
        "zaxis": 3,
        "is_connector": True,
    }
    if progress:
        print(
            f"  Anchor pole: 2x2x{height} glass pole at ({base[0]}, {min_y - height}, {base[2]})"
        )
    return parts + [pole]
