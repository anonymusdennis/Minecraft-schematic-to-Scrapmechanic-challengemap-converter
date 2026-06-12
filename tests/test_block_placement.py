"""Tests for blockstate rotation and variant placement."""

import unittest
from pathlib import Path

from block_placement import placement_rotation
from block_voxels import voxelize_block_local
from schematic_parser import parse_schematic_file

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS = PROJECT_ROOT / "MyResourcePack/assets"


class TestBlockPlacement(unittest.TestCase):
    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_trapdoor_variants_differ_by_facing(self):
        data = parse_schematic_file("MYHOUSE.json")
        blocks = data["blocks"]
        block_index = {(b["x"], b["y"], b["z"]): b for b in blocks}

        north = next(b for b in blocks if b["name"] == "jungle_trapdoor" and b["properties"]["facing"] == "north")
        south_blocks = [b for b in blocks if b["name"] == "jungle_trapdoor" and b["properties"]["facing"] == "south"]
        if not south_blocks:
            self.skipTest("no south-facing jungle trapdoor in schematic")
        south = south_blocks[0]

        def block_at(x, y, z):
            return block_index.get((x, y, z))

        north_vox = set(voxelize_block_local("jungle_trapdoor", ASSETS, mc_block=north, block_at=block_at))
        south_vox = set(voxelize_block_local("jungle_trapdoor", ASSETS, mc_block=south, block_at=block_at))
        self.assertNotEqual(north_vox, south_vox)

    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_connected_glass_pane_keeps_post_and_sides(self):
        from blockstate_resolver import resolve_block_models

        mc = {
            "name": "white_stained_glass_pane",
            "properties": {
                "east": "true",
                "west": "true",
                "north": "false",
                "south": "false",
            },
        }
        models = resolve_block_models("white_stained_glass_pane", ASSETS, mc)
        # Minecraft always renders the pane center post; dropping it leaves a
        # hole where the arms never connect.
        self.assertTrue(any("_post" in m["model"] for m in models))
        self.assertTrue(any("_side" in m["model"] for m in models))

    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_bottom_slab_is_half_height(self):
        from block_voxels import voxelize_block_local

        mc = {"name": "oak_slab", "properties": {"type": "bottom"}}
        local = voxelize_block_local("oak_slab", ASSETS, mc_block=mc)
        self.assertGreater(len(local), 0)
        ys = [y for _, y, _ in local]
        self.assertLessEqual(max(ys), 7)
        self.assertLess(len(local), 16 ** 3)

    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_top_slab_resolves_top_model(self):
        from blockstate_resolver import resolve_block_models

        mc = {"name": "oak_slab", "properties": {"type": "top"}}
        models = resolve_block_models("oak_slab", ASSETS, mc)
        self.assertTrue(any("top" in m["model"] for m in models))

    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_tnt_top_faces_up(self):
        local = voxelize_block_local("tnt", ASSETS, mc_block={"name": "tnt", "properties": {}})
        self.assertGreater(len(local), 0)
        max_y = max(y for _, y, _ in local)
        self.assertGreater(len([1 for _, y, _ in local if y == max_y]), 10)

    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_modern_blocks_use_identity_placement_axes(self):
        mc = {
            "name": "spruce_door",
            "data": 0,
            "properties": {"facing": "south", "half": "lower", "hinge": "left", "open": "true"},
        }
        self.assertEqual(placement_rotation(mc, ASSETS), (1, 3))

    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_chest_facing_changes_geometry(self):
        east = {
            "name": "chest",
            "x": 0, "y": 0, "z": 0,
            "data": 0,
            "properties": {"facing": "east", "type": "single"},
        }
        south = {
            "name": "chest",
            "x": 0, "y": 0, "z": 0,
            "data": 0,
            "properties": {"facing": "south", "type": "single"},
        }
        east_vox = voxelize_block_local("chest", ASSETS, mc_block=east)
        south_vox = voxelize_block_local("chest", ASSETS, mc_block=south)
        self.assertGreater(len(east_vox), 100)
        # The latch knob is intentionally removed, so occupancy is identical
        # across facings — but the painted faces (front vs side textures)
        # must still rotate with the block.
        self.assertNotEqual(east_vox, south_vox)
        # No protruding latch: the chest body must stay within 1..14 on x/z.
        for (x, y, z) in east_vox:
            self.assertTrue(1 <= x <= 14 and 1 <= z <= 14)


if __name__ == "__main__":
    unittest.main()
