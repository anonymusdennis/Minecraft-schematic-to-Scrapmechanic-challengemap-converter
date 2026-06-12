#!/usr/bin/env python3
"""Convert a Minecraft schematic to a Scrap Mechanic challenge map."""

import argparse
import sys
from pathlib import Path

from challenge_exporter import export_challenge, split_into_level_creations
from assets_paths import normalize_assets_dir
from config import SM_ASSETS_DIR, SM_CHALLENGES_DIR, DEFAULT_SCHEMATIC_PATH
from map_builder import build_voxel_map, process_voxel_map
from map_naming import allocate_map_name
from performance_validator import print_validation_report, validate_chunks
from schematic_parser import parse_schematic_file, schematic_voxel_bounds


def convert_schematic(
    schematic_path,
    name,
    output_dir,
    assets_dir=None,
    description="",
    hollow=True,
    merge=True,
    connect_islands=True,
    split=False,
    dry_run=False,
    settings=None,
    exact_name=False,
):
    import conversion_settings
    import progress

    if settings is not None:
        conversion_settings.apply(settings)
    else:
        conversion_settings.apply(conversion_settings.CURRENT)
    settings = conversion_settings.CURRENT

    assets_dir = normalize_assets_dir(assets_dir or SM_ASSETS_DIR)

    from asset_resolution import asset_roots

    roots = asset_roots(assets_dir)
    if not roots:
        raise FileNotFoundError(
            "No assets found. Add resource packs to resourcepacks/ or run "
            "python3 download_vanilla_assets.py for the vanilla base."
        )
    print("Resource pack priority (high -> low):")
    for root in roots:
        print(f"  {root}")

    progress.report("parse", 0.0, "Parsing schematic...")
    print(f"Parsing schematic: {schematic_path}")
    schematic_data = parse_schematic_file(schematic_path)
    print(
        f"  {schematic_data['width']}x{schematic_data['height']}x{schematic_data['length']} | "
        f"{len(schematic_data['blocks'])} blocks"
    )
    progress.report("parse", 1.0, f"{len(schematic_data['blocks'])} blocks")

    blueprint, stats = build_voxel_map(
        schematic_data, assets_dir, connect_islands=connect_islands
    )
    progress.report("process", 0.0, "Hollowing and merging...")
    blueprint = process_voxel_map(
        blueprint,
        hollow=hollow,
        merge=merge,
        opaque_mc_blocks=stats.get("opaque_mc_blocks"),
        appearance_cache=stats.get("appearance_cache"),
        assets_dir=assets_dir,
        solid_occupancy=stats.get("solid_occupancy"),
        connect_islands=connect_islands,
        transparent_mc_blocks=stats.get("transparent_mc_blocks"),
        opaque_mc_positions=stats.get("opaque_mc_positions"),
        block_at=stats.get("block_at"),
        lamp_parts=stats.get("lamp_parts"),
        lamp_positions=stats.get("lamp_positions"),
    )

    if settings.include_entities and schematic_data.get("entities"):
        from entity_renderer import build_entity_parts

        entity_parts = build_entity_parts(schematic_data["entities"], assets_dir)
        if entity_parts:
            blueprint["bodies"][0]["childs"].extend(entity_parts)
            if connect_islands:
                from component_connector import enforce_single_structure_parts

                blueprint["bodies"][0]["childs"] = enforce_single_structure_parts(
                    blueprint["bodies"][0]["childs"]
                )

    progress.report("validate", 0.0, "Validating...")
    chunks = split_into_level_creations(blueprint, split=split)
    bounds = schematic_voxel_bounds(schematic_data)
    validation = validate_chunks(chunks, schematic_bounds=bounds)
    print_validation_report(validation)

    if not validation.passed:
        raise RuntimeError("Performance validation failed. Map not exported.")
    progress.report("validate", 1.0)

    output_path = Path(output_dir)
    numbered_name = name if exact_name else allocate_map_name(name, output_path)
    print(f"Map name: {numbered_name}")

    if dry_run:
        print("Dry run complete — validation passed, no files written.")
        progress.report("export", 1.0, "Dry run complete")
        return None

    progress.report("export", 0.2, "Writing challenge files...")
    challenge_dir = export_challenge(
        blueprint,
        name=numbered_name,
        output_dir=output_path,
        description=description,
        split=split,
        schematic_blocks=schematic_data["blocks"] if settings.include_prefabs else None,
        assets_dir=assets_dir,
        block_at=stats.get("block_at"),
        include_block_prefabs=settings.include_prefabs,
    )
    progress.report("export", 1.0, "Done")
    prefab_count = len(list((challenge_dir / "Blueprints").glob("Block_*.blueprint"))) if (challenge_dir / "Blueprints").is_dir() else 0
    print(f"Challenge map exported to: {challenge_dir}")
    if prefab_count:
        print(f"  Builder palette: {prefab_count} block prefab(s) in Blueprints/")
    return challenge_dir


def main():
    parser = argparse.ArgumentParser(
        description="Convert a Minecraft schematic to a Scrap Mechanic challenge map"
    )
    parser.add_argument(
        "schematic",
        nargs="?",
        default=None,
        help=f"Path to .schematic, .schem, or .json (default: {DEFAULT_SCHEMATIC_PATH})",
    )
    parser.add_argument("--name", "-n", required=True, help="Challenge map display name")
    parser.add_argument(
        "--description", "-d", default="", help="Challenge map description"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Output directory (default: SM Challenges folder)",
    )
    parser.add_argument(
        "--assets", "-a",
        default=None,
        help="Minecraft assets directory (default: MyResourcePack/assets)",
    )
    parser.add_argument(
        "--no-hollow",
        action="store_true",
        help="Disable WorldEdit hollow (not recommended)",
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Disable greedy mesh merging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate without writing challenge files",
    )
    parser.add_argument(
        "--split",
        action="store_true",
        help="Split into multiple LevelCreation files (default: one single weld-welded structure)",
    )
    parser.add_argument(
        "--no-connect",
        action="store_true",
        help="Do not bridge disconnected islands with highlighted connector voxels",
    )
    from conversion_settings import BIOME_PRESETS, WATER_MODES

    parser.add_argument(
        "--biome", default="Plains", choices=sorted(BIOME_PRESETS.keys()),
        help="Biome color preset for grass/foliage/water tints",
    )
    parser.add_argument(
        "--water", default="glass", choices=WATER_MODES,
        help="Water handling: glass cubes, solid cubes, or skip",
    )
    parser.add_argument(
        "--wall-thickness", type=int, default=2,
        help="Voxel layers kept when hollowing (default: 2)",
    )
    parser.add_argument(
        "--no-lights", action="store_true",
        help="Do not place real SM lamps on light-emitting blocks",
    )
    parser.add_argument(
        "--light-mode", default="embed", choices=("embed", "replace"),
        help="embed = lamps hidden inside voxels (glitchweld), replace = cutout",
    )
    parser.add_argument(
        "--lamps-per-face", type=int, default=1,
        help="Lamps per face of a light block, 6 faces total (default: 1)",
    )
    parser.add_argument(
        "--luminance", type=int, default=50,
        help="Lamp light strength 1-100 (default: 50)",
    )
    parser.add_argument(
        "--no-pole", action="store_true",
        help="Skip the glass anchor pole below the structure",
    )
    parser.add_argument(
        "--pole-height", type=int, default=32,
        help="Anchor pole height in voxels (default: 32)",
    )
    parser.add_argument(
        "--prefabs", action="store_true",
        help="Include builder-palette blueprints (WARNING: they spawn as loose "
        "creations at the platform and cause collision lag)",
    )
    parser.add_argument(
        "--no-entities", action="store_true",
        help="Skip paintings and other schematic entities",
    )
    parser.add_argument(
        "--max-parts", type=int, default=320000,
        help="Hard part-count limit for validation (default: 320000)",
    )

    args = parser.parse_args()
    schematic_path = Path(args.schematic) if args.schematic else DEFAULT_SCHEMATIC_PATH
    output_dir = Path(args.output_dir) if args.output_dir else SM_CHALLENGES_DIR

    from conversion_settings import ConversionSettings

    settings = ConversionSettings(
        biome=args.biome,
        water_mode=args.water,
        wall_thickness=max(1, args.wall_thickness),
        hollow=not args.no_hollow,
        merge=not args.no_merge,
        connect_islands=not args.no_connect,
        lights_enabled=not args.no_lights,
        light_mode=args.light_mode,
        lamps_per_face=max(1, args.lamps_per_face),
        lamp_luminance=args.luminance,
        anchor_pole=not args.no_pole,
        anchor_pole_height=max(1, args.pole_height),
        include_entities=not args.no_entities,
        include_prefabs=args.prefabs,
        max_parts=args.max_parts,
    )

    try:
        convert_schematic(
            schematic_path=schematic_path,
            name=args.name,
            output_dir=output_dir,
            assets_dir=args.assets,
            description=args.description,
            hollow=not args.no_hollow,
            merge=not args.no_merge,
            connect_islands=not args.no_connect,
            split=args.split,
            dry_run=args.dry_run,
            settings=settings,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
