#!/usr/bin/env python3
"""
Generate test_map.json — a deliberately tricky schematic that exercises every
converter feature: floating blocks, all stair facings, slabs, connected glass
panes, iron bars, fences, walls, doors, trapdoors, torches (ground/wall/soul),
lanterns (standing/hanging), every light-emitting block, water/lava, snowy
grass, tinted leaves, double chests, beds, ladders, signs, paintings, and more.

Usage:
    python3 generate_test_map.py          # writes test_map.json
    python3 convert.py test_map.json --name "Feature Test"
"""

import json
from pathlib import Path

WIDTH, HEIGHT, LENGTH = 20, 12, 20

blocks: dict[tuple[int, int, int], str] = {}
entities: list[dict] = []


def put(x, y, z, state):
    assert 0 <= x < WIDTH and 0 <= y < HEIGHT and 0 <= z < LENGTH, (x, y, z)
    blocks[(x, y, z)] = state if ":" in state.split("[")[0] else f"minecraft:{state}"


# ---------------------------------------------------------------- platform
for x in range(WIDTH):
    for z in range(LENGTH):
        put(x, 0, z, "stone")

# ------------------------------------------------- z=1: stairs, slabs, lights
put(1, 1, 1, "oak_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]")
put(2, 1, 1, "oak_stairs[facing=west,half=bottom,shape=straight,waterlogged=false]")
put(3, 1, 1, "oak_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]")
put(4, 1, 1, "oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]")
put(5, 1, 1, "stone_brick_stairs[facing=east,half=top,shape=straight,waterlogged=false]")
put(7, 1, 1, "spruce_slab[type=bottom,waterlogged=false]")
put(8, 1, 1, "spruce_slab[type=top,waterlogged=false]")
put(10, 1, 1, "torch")
put(11, 1, 1, "soul_torch")
put(13, 1, 1, "lantern[hanging=false,waterlogged=false]")
put(15, 1, 1, "glowstone")
put(17, 1, 1, "sea_lantern")
put(18, 1, 1, "end_rod[facing=up]")

# --------------------------------- z=3: panes, bars, wall torches, hanging lantern
put(1, 1, 3, "white_stained_glass_pane[east=true,north=false,south=false,waterlogged=false,west=false]")
put(2, 1, 3, "white_stained_glass_pane[east=true,north=false,south=false,waterlogged=false,west=true]")
put(3, 1, 3, "white_stained_glass_pane[east=true,north=false,south=true,waterlogged=false,west=true]")
put(4, 1, 3, "white_stained_glass_pane[east=true,north=false,south=false,waterlogged=false,west=true]")
put(5, 1, 3, "white_stained_glass_pane[east=false,north=false,south=false,waterlogged=false,west=true]")
put(3, 1, 4, "white_stained_glass_pane[east=false,north=true,south=false,waterlogged=false,west=false]")
put(7, 1, 3, "iron_bars[east=true,north=false,south=false,waterlogged=false,west=false]")
put(8, 1, 3, "iron_bars[east=false,north=false,south=false,waterlogged=false,west=true]")
# stone pillar with wall torches on all four sides
put(12, 1, 3, "stone")
put(12, 2, 3, "stone")
put(13, 2, 3, "wall_torch[facing=east]")
put(11, 2, 3, "wall_torch[facing=west]")
put(12, 2, 4, "wall_torch[facing=south]")
put(12, 2, 2, "wall_torch[facing=north]")
# hanging lantern under a stone block
put(14, 2, 3, "stone")
put(14, 1, 3, "lantern[hanging=true,waterlogged=false]")

# --------------------------------------------- z=6: fences, gate, cobble walls
put(0, 1, 6, "oak_fence_gate[facing=south,in_wall=false,open=false,powered=false]")
for x in range(1, 5):
    put(x, 1, 6, "oak_fence")  # connections derived from neighbors
put(5, 1, 6, "oak_planks")
for x in range(8, 12):
    put(x, 1, 6, "cobblestone_wall")  # connections derived
put(12, 1, 6, "stone_bricks")

# ----------------------------------------- z=8: doors, trapdoors, furnace, lamp
put(2, 1, 8, "oak_door[facing=south,half=lower,hinge=left,open=false,powered=false]")
put(2, 2, 8, "oak_door[facing=south,half=upper,hinge=left,open=false,powered=false]")
put(4, 1, 8, "iron_door[facing=east,half=lower,hinge=left,open=false,powered=false]")
put(4, 2, 8, "iron_door[facing=east,half=upper,hinge=left,open=false,powered=false]")
put(6, 1, 8, "spruce_trapdoor[facing=north,half=bottom,open=false,powered=false,waterlogged=false]")
put(7, 1, 8, "spruce_trapdoor[facing=south,half=bottom,open=true,powered=false,waterlogged=false]")
put(15, 1, 8, "furnace[facing=west,lit=true]")
put(17, 1, 8, "redstone_lamp[lit=true]")

# ------------------------------------- z=10/11: fluids, ice, more light blocks
for x in (1, 2):
    for z in (10, 11):
        put(x, 1, z, "water")
put(4, 1, 10, "lava")
put(6, 1, 10, "ice")
put(8, 1, 10, "jack_o_lantern[facing=south]")
put(10, 1, 10, "shroomlight")
put(12, 1, 10, "campfire[facing=north,lit=true,signal_fire=false,waterlogged=false]")
put(14, 1, 10, "soul_lantern[hanging=false,waterlogged=false]")

# --------------------------- z=13: grass/snow, leaves, chests, bed, ladder
put(1, 1, 13, "grass_block[snowy=false]")
put(3, 1, 13, "grass_block[snowy=true]")
put(3, 2, 13, "snow[layers=1]")
put(5, 1, 13, "oak_leaves[distance=7,persistent=true,waterlogged=false]")
put(6, 1, 13, "birch_leaves[distance=7,persistent=true,waterlogged=false]")
put(8, 1, 13, "chest[facing=south,type=right,waterlogged=false]")
put(9, 1, 13, "chest[facing=south,type=left,waterlogged=false]")
put(11, 1, 13, "chest[facing=south,type=single,waterlogged=false]")
put(13, 1, 13, "red_bed[facing=east,occupied=false,part=foot]")
put(14, 1, 13, "red_bed[facing=east,occupied=false,part=head]")
put(17, 1, 13, "stone")
put(17, 2, 13, "stone")
put(16, 1, 13, "ladder[facing=west,waterlogged=false]")
put(16, 2, 13, "ladder[facing=west,waterlogged=false]")

# ------------------- z=15: signs, anvil, carpet, redstone bits, misc blocks
put(1, 1, 15, "oak_sign[rotation=4,waterlogged=false]")
put(3, 1, 15, "stone")
put(3, 1, 14, "oak_wall_sign[facing=north,waterlogged=false]")
put(5, 1, 15, "anvil[facing=south]")
put(7, 1, 15, "red_carpet")
put(8, 1, 15, "oak_button[face=floor,facing=north,powered=false]")
put(9, 1, 15, "lever[face=floor,facing=north,powered=false]")
put(10, 1, 15, "stone_pressure_plate[powered=false]")
put(12, 1, 15, "bookshelf")
put(13, 1, 15, "scaffolding[bottom=false,distance=0,waterlogged=false]")
put(15, 1, 15, "glass")
put(16, 1, 15, "white_stained_glass")

# ----------------------------- z=18: painting wall (paintings hang at z=17)
for x in range(1, 9):
    for y in range(1, 4):
        put(x, y, 18, "stone_bricks")
entities.append({
    "Id": "minecraft:painting",
    "Pos": [2.5, 2.5, 17.97],
    "Data": {"facing": 2, "variant": "minecraft:kebab", "TileX": 2, "TileY": 2, "TileZ": 17},
})
entities.append({
    "Id": "minecraft:painting",
    "Pos": [4.5, 2.5, 17.97],
    "Data": {"facing": 2, "variant": "minecraft:pool", "TileX": 4, "TileY": 2, "TileZ": 17},
})
entities.append({
    "Id": "minecraft:item_frame",
    "Pos": [7.5, 2.5, 17.97],
    "Data": {"Facing": 2, "TileX": 7, "TileY": 2, "TileZ": 17},
})

# -------------------------------------------------- floating geometry tests
for x in range(0, 3):
    for z in range(0, 3):
        put(x, 8, z, "oak_planks")
put(1, 9, 1, "torch")            # torch on the floating island
put(10, 8, 10, "glowstone")      # lone floating light block


def main():
    palette: dict[str, int] = {"minecraft:air": 0}
    data = [0] * (WIDTH * HEIGHT * LENGTH)
    for (x, y, z), state in blocks.items():
        if state not in palette:
            palette[state] = len(palette)
        data[(y * LENGTH + z) * WIDTH + x] = palette[state]

    schematic = {
        "Schematic": {
            "Version": 3,
            "Width": WIDTH,
            "Height": HEIGHT,
            "Length": LENGTH,
            "Blocks": {"Palette": palette, "Data": data},
            "Entities": entities,
        }
    }
    out = Path(__file__).resolve().parent / "test_map.json"
    out.write_text(json.dumps(schematic), encoding="utf-8")
    print(f"Wrote {out}")
    print(f"  {len(blocks)} blocks, {len(palette) - 1} block states, {len(entities)} entities")


if __name__ == "__main__":
    main()
