# Minecraft Schematic → Scrap Mechanic Challenge Map Converter

[![itch.io](https://img.shields.io/badge/itch.io-Download-FA5C5C?logo=itchdotio&logoColor=white)](https://anonymusdennis.itch.io/mc-schematic-to-scrapmechanic)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-67%20passing-brightgreen)](#tests)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**Walk through your Minecraft builds in Scrap Mechanic.** This tool takes a
Minecraft schematic — your house, your castle, your entire WorldEdit export —
and turns it into a fully welded, textured, *glowing* Scrap Mechanic challenge
map. Every block becomes 16×16×16 voxels of painted Scrap Mechanic parts:
stairs are stairs, glass is glass you can see through, torches actually emit
light, and the whole thing arrives as **one single welded structure** that
won't collapse into a pile of physics debris when you load it.

---

## Why this exists

Minecraft and Scrap Mechanic both speak "blocks", but they don't speak the
same dialect. Minecraft blocks are data + JSON models + textures; Scrap
Mechanic wants thousands of individually placed, painted, welded parts in a
challenge blueprint. Translating between them means solving real problems:

- A Minecraft block is **one** block — but at Scrap Mechanic scale it's
  **4,096 voxels** that need textures sampled, tinted, hollowed, and merged
  so the game doesn't melt.
- Scrap Mechanic **only welds face-to-face**. One diagonal connection in
  your build and half your map falls out of the sky.
- Minecraft models are full of tricks — flat crossed quads for plants,
  faces floating *outside* the geometry, fire billboards, sub-voxel detail —
  that all break naive voxelization.

This converter handles all of it, automatically.

## Features

- **Point-and-click GUI** — pick a schematic, see a live size estimate, watch
  the progress bar, get an overwrite warning if the map name already exists.
  Your Scrap Mechanic install is auto-detected (native and Proton paths).
- **3D models for everything** — a curated stack of eight 3D resource packs
  ships with the tool, and the converter always prefers a model with real
  carved 3D geometry. Furnaces have recessed fronts, lamps have lattices,
  ladders have rungs.
- **Real light emission** — glowstone, lanterns, torches, campfires and
  friends get actual Scrap Mechanic lamps on all six faces, painted to match
  the block, hidden inside the voxels (or replacing them — your choice).
- **Single-structure guarantee** — every floating island, pane, painting and
  lamp is bridged with indestructible glass until exactly **one** welded
  component remains, then anchored to the platform with a glass pole.
- **Entities too** — paintings are rendered pixel-perfect (one voxel per
  texture pixel), item frames get wooden frames, signs get post + board.
- **Your resource packs, your look** — drop packs into `resourcepacks/`;
  alphabetical order = priority, exactly like Minecraft. Biome color presets
  tint grass, leaves and water.
- **Performance-aware** — greedy mesh merging slashes part counts, hollowing
  keeps only the walls (configurable thickness), and every export is
  validated against limits measured from real workshop maps.
- **Standalone builds** — package it as a single executable for Linux and
  Windows with PyInstaller. No Python required for end users.

## Quick start

### GUI

```bash
pip install -r requirements.txt
python3 download_vanilla_assets.py   # one-time: vanilla texture/model base
python3 gui.py                       # Linux: sudo apt install python3-tk once
```

### CLI

```bash
python3 convert.py my_build.schem --name "My Castle"
```

Exports straight into your Scrap Mechanic Challenges folder — open
**Challenge Builder** in game and play. Maps are auto-numbered
(`My Castle 1`, `My Castle 2`, …) so you never overwrite an old export by
accident.

### Try the gauntlet

```bash
python3 generate_test_map.py
python3 convert.py test_map.json --name "Feature Test"
```

`generate_test_map.py` creates a deliberately nasty schematic: floating
islands, every stair facing, connected glass-pane runs, fences ending at
blocks, torches on all four wall sides, hanging lanterns, water and lava
pools, tinted leaves, double chests, beds, ladders, signs and paintings.
If a converter change breaks something, this map shows it.

## How it works

1. **Parse** — `.schem`, `.schematic` and JSON exports are read (including
   NBT varints), along with block entities and entities.
2. **Resolve** — each block's state is matched against real Minecraft
   blockstate JSON (variants, multipart, OR/AND conditions), picking the
   correct model and rotation per block.
3. **Voxelize** — the model's elements are rasterized into a 16³ grid.
   Every voxel samples the texture of the element that created it, with
   UV mapping, biome tinting, and support for "negative inset" skin faces
   that float outside the geometry (a common 3D-pack trick).
4. **Hollow** — the welded opaque volume is hollowed WorldEdit-style down
   to a configurable wall thickness; carved model details are preserved,
   and through-holes are capped so you can never peek into the empty
   interior.
5. **Merge** — greedy meshing combines runs of same-colored voxels into
   larger parts (an optimized O(n log n) pass — large maps convert in
   about a minute, not fourteen).
6. **Weld** — a final pass BFS-bridges every disconnected island with
   indestructible glass, colored like the island it rescues, until the
   entire map is one component standing on a glass anchor pole.
7. **Light** — light-emitting blocks get headlight parts placed
   symmetrically on all six faces, rotation-corrected to face outward.
8. **Export** — everything is written as a challenge map (description,
   level, blueprints) directly into your Challenges folder, with a
   performance validation report.

## Resource packs and the "3D for everything" rule

Textures and models resolve through a priority stack:

1. `--assets` / `SM_ASSETS_DIR` (defaults to `MyResourcePack/assets`)
2. Every pack in `resourcepacks/` — **alphabetical order = priority**
   (folders and `.zip` both work)
3. `supplement_assets/` (generated chest/bed geometry)
4. `vanilla_assets/` (from `download_vanilla_assets.py`)

When resolving a model the converter scans the **whole stack** and picks the
first model with visible carved 3D geometry — so a 3D furnace from a
low-priority pack beats a flat furnace from a high-priority one, while
textures keep normal priority and each model loads textures from its own
pack first (no mismatched art).

The eight 3D packs below are a **required dependency** and ship with the
tool: they're committed in `resourcepacks/`, and the standalone executables
have them embedded — on first run they unpack into a `resourcepacks/` folder
next to the binary. Name your own packs anything before `y` to outrank them:

| Pack | Covers | License |
|------|--------|---------|
| `y1 3D Crops Revamped` | all crops | ARR (free download) |
| `y2 Better 3D Beds` | beds (OptiFine CEM) | ARR (free download) |
| `y3 Drigo 3D Lanterns` | lanterns | — |
| `y4 Simply 3D` | furnaces, crafting/utility blocks | MIT |
| `y5 Nautilus 3D` | broad vanilla-style coverage | AGPL-3.0 |
| `y6 Actually 3D Blocks and Items` | broad coverage | CC-BY-4.0 |
| `y7 3D Vanilla` | 1400+ block models (catch-all) | MIT |
| `zzz 3D Default (base)` | [GeForceLegend's 3D Default](https://github.com/GeForceLegend/Minecraft-3D-Default) | GPL-3.0 |

The voxelizer adds safety nets on top: flat planes (cross plants, vines) are
extruded to one voxel, flat ladders get generated rails and rungs, bar walls
become real rods, glass keeps its transparent interior as clear
challenge-glass, fire billboards are skipped (lamps provide the glow),
sub-voxel knobs are dropped, broken sparse remodels of full-cube blocks are
rejected, and block interiors take the dominant surface color.

## Standalone app (Linux + Windows)

```bash
./build_linux.sh        # on Linux   -> dist/mc2sm
build_windows.bat       # on Windows -> dist\mc2sm.exe
```

PyInstaller can't cross-compile, so run each script on its own OS. The
required 3D resource packs are **embedded in the executable** and unpack
next to it on first run; the vanilla asset base is downloaded there on first
run too. Drop extra packs into that same `resourcepacks/` folder.

## CLI reference

```bash
python3 convert.py my_build.schematic \
  --name "Hide and Seek Warehouse" \
  --description "Converted from Minecraft" \
  --biome Jungle --water glass --wall-thickness 2 \
  --light-mode embed --lamps-per-face 1 --luminance 50
```

| Flag | Description |
|------|-------------|
| `--name` | Challenge map display name (required) |
| `--description` | Optional description text |
| `--output-dir` | Custom output folder (default: SM Challenges folder) |
| `--assets` | Minecraft resource pack assets path |
| `--dry-run` | Validate without writing files |
| `--no-hollow` | Skip hollowing (not recommended) |
| `--no-merge` | Skip greedy mesh merging |
| `--no-connect` | Skip island bridging |
| `--biome` | Biome color preset (Plains, Jungle, Swamp, Snowy, ...) |
| `--water` | Water handling: `glass` (default), `solid`, `skip` |
| `--wall-thickness` | Voxel layers kept when hollowing (default: 2) |
| `--no-lights` | Disable lamp placement on light blocks |
| `--light-mode` | `embed` (hidden inside voxels, default) or `replace` (cutout) |
| `--lamps-per-face` | Lamps per face, 6 faces per light block (default: 1) |
| `--luminance` | Lamp light strength 1-100 (default: 50) |
| `--no-pole` | Skip the glass anchor pole |
| `--pole-height` | Anchor pole height in voxels (default: 32) |
| `--prefabs` | Builder palette (WARNING: spawns loose blocks at the platform) |
| `--no-entities` | Skip paintings / item frames |
| `--max-parts` | Hard part-count limit for validation |

## Configuration

Copy `.env.example` to `.env` or set environment variables:

- `SM_CHALLENGES_DIR` — Scrap Mechanic user Challenges folder
- `SM_REFERENCE_PRIVATE_DIR` / `SM_REFERENCE_WORKSHOP_DIR` — reference maps
  for performance benchmarking
- `SM_ASSETS_DIR` — Minecraft assets directory
- `MC_SCHEMATIC_PATH` — default schematic when none is given

## Output format

```
Challenges/<uuid>/
├── description.json
├── challengeLevel.json
├── Blueprints/            (builder palette, only with --prefabs)
└── LevelCreation_1.blueprint
```

Performance limits derived from real workshop maps: ≤ 12,000 parts per
blueprint chunk, ≤ 4 MB per chunk file, ≤ 15,000 total parts recommended
(big builds still export — you just get a warning).

## Tests

```bash
python3 -m unittest discover -s tests -v
```

67 tests cover parsing, blockstates, voxelization, hollowing, merging,
connectivity, transparent blocks, naming and the export format.

## Get it

The converter is published on these pages — grab a standalone build or the
source:

| Page | Link |
|------|------|
| **GitHub** (source + releases) | this repository |
| **itch.io** (standalone builds) | <https://anonymusdennis.itch.io/mc-schematic-to-scrapmechanic> |
| **ModDB** (Scrap Mechanic mods section) | <https://www.moddb.com/games/scrap-mechanic/mods> |
| **SourceForge** (downloads mirror) | <https://sourceforge.net/projects/mc-schematic-to-scrapmechanic/> |

## License & credits

The converter code is **MIT licensed** (see [LICENSE](LICENSE)). Bundled
resource packs keep their own licenses (see the table above) and remain the
property of their authors. Minecraft is a trademark of Mojang/Microsoft;
Scrap Mechanic is a trademark of Axolot Games. This project is affiliated
with neither.
