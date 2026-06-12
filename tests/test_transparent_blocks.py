"""Tests for transparent block handling."""

import unittest
from pathlib import Path

from hollow import worldedit_hollow
from map_builder import build_voxel_map, process_voxel_map
from transparent_blocks import is_transparent_block

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS = PROJECT_ROOT / "MyResourcePack/assets"


class TestTransparentBlocks(unittest.TestCase):
    def test_glass_is_transparent(self):
        self.assertTrue(is_transparent_block("glass"))
        self.assertTrue(is_transparent_block("white_stained_glass_pane"))
        self.assertFalse(is_transparent_block("stone"))

    def test_slabs_and_stairs_are_deferred(self):
        self.assertTrue(is_transparent_block("oak_slab"))
        self.assertTrue(is_transparent_block("oak_stairs"))
        self.assertTrue(is_transparent_block("spruce_fence_gate"))
        self.assertTrue(is_transparent_block("campfire"))
        self.assertFalse(is_transparent_block("double_stone_slab"))

    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_top_slab_uses_upper_half(self):
        from block_voxels import voxelize_block_local

        mc = {"name": "oak_slab", "properties": {"type": "top"}}
        local = voxelize_block_local("oak_slab", ASSETS, mc_block=mc)
        self.assertGreater(len(local), 0)
        ys = [y for _, y, _ in local]
        self.assertGreaterEqual(max(ys), 14)
        self.assertGreater(sum(ys) / len(ys), 8)

    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_stairs_survive_structure_hollow(self):
        schematic = {
            "width": 3,
            "height": 1,
            "length": 1,
            "blocks": [
                {"x": 0, "y": 0, "z": 0, "name": "stone", "data": 0},
                {"x": 1, "y": 0, "z": 0, "name": "oak_stairs", "data": 0,
                 "properties": {"facing": "south", "half": "bottom", "shape": "straight"}},
                {"x": 2, "y": 0, "z": 0, "name": "stone", "data": 0},
            ],
        }
        blueprint, stats = build_voxel_map(schematic, ASSETS, progress=False)
        self.assertEqual(stats["transparent_cells"], 1)
        blueprint = process_voxel_map(
            blueprint,
            merge=False,
            progress=False,
            transparent_mc_blocks=stats["transparent_mc_blocks"],
            opaque_mc_positions=stats["opaque_mc_positions"],
            assets_dir=ASSETS,
            block_at=stats["block_at"],
        )
        stair_parts = [
            p for p in blueprint["bodies"][0]["childs"] if p.get("is_transparent")
        ]
        self.assertGreater(len(stair_parts), 100)

    def test_transparent_not_in_opaque_weld(self):
        schematic = {
            "width": 2,
            "height": 1,
            "length": 1,
            "blocks": [
                {"x": 0, "y": 0, "z": 0, "name": "stone", "data": 0},
                {"x": 1, "y": 0, "z": 0, "name": "glass", "data": 0},
            ],
        }
        blueprint, stats = build_voxel_map(schematic, "/nonexistent", progress=False)
        self.assertEqual(stats["transparent_cells"], 1)
        self.assertEqual(stats["opaque_cells"], 1)
        transparent = [p for p in blueprint["bodies"][0]["childs"] if p.get("is_transparent")]
        opaque = [p for p in blueprint["bodies"][0]["childs"] if not p.get("is_transparent")]
        self.assertEqual(len(transparent), 0)
        self.assertEqual(len(opaque), 16 ** 3)

    def test_glass_attaches_to_stone_face(self):
        schematic = {
            "width": 2,
            "height": 1,
            "length": 1,
            "blocks": [
                {"x": 0, "y": 0, "z": 0, "name": "stone", "data": 0},
                {"x": 1, "y": 0, "z": 0, "name": "glass", "data": 0},
            ],
        }
        blueprint, stats = build_voxel_map(schematic, "/nonexistent", progress=False)
        blueprint = process_voxel_map(
            blueprint,
            merge=False,
            progress=False,
            transparent_mc_blocks=stats["transparent_mc_blocks"],
            opaque_mc_positions=stats["opaque_mc_positions"],
            assets_dir="/nonexistent",
            block_at=stats["block_at"],
        )
        positions = {
            (int(p["pos"]["x"]), int(p["pos"]["y"]), int(p["pos"]["z"]))
            for p in blueprint["bodies"][0]["childs"]
        }
        self.assertIn((15, 0, 0), positions)
        self.assertIn((16, 0, 0), positions)

    def test_structure_hollow_skips_transparent(self):
        schematic = {
            "width": 3,
            "height": 1,
            "length": 1,
            "blocks": [
                {"x": 0, "y": 0, "z": 0, "name": "stone", "data": 0},
                {"x": 1, "y": 0, "z": 0, "name": "glass", "data": 0},
                {"x": 2, "y": 0, "z": 0, "name": "stone", "data": 0},
            ],
        }
        blueprint, stats = build_voxel_map(schematic, "/nonexistent", progress=False)
        self.assertEqual(
            sum(1 for p in blueprint["bodies"][0]["childs"] if p.get("is_transparent")),
            0,
        )
        blueprint = process_voxel_map(
            blueprint,
            merge=False,
            progress=False,
            transparent_mc_blocks=stats["transparent_mc_blocks"],
            opaque_mc_positions=stats["opaque_mc_positions"],
            assets_dir="/nonexistent",
            block_at=stats["block_at"],
        )
        after_trans = sum(1 for p in blueprint["bodies"][0]["childs"] if p.get("is_transparent"))
        self.assertGreater(after_trans, 0)

if __name__ == "__main__":
    unittest.main()
