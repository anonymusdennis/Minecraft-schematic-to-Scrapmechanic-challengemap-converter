"""Tests for Nautilus3D block model alias resolution."""

import unittest
from pathlib import Path

from block_model_aliases import resolve_block_model_name
from block_voxels import _sample_block_texture_color, voxelize_block_local
from blueprint_writer import rgba_to_hex

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS = PROJECT_ROOT / "MyResourcePack/assets"


class TestBlockModelAliases(unittest.TestCase):
    def test_snow_uses_snow_block_model(self):
        self.assertEqual(resolve_block_model_name("snow"), "snow_block")

    def test_waxed_copper_chest_alias(self):
        self.assertEqual(resolve_block_model_name("waxed_copper_chest"), "copper_chest")

    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_chest_texture_from_break_folder(self):
        color = _sample_block_texture_color("chest", ASSETS)
        self.assertIsNotNone(color)
        self.assertNotEqual(color, "808080")

    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_chest_voxelizes_from_item_model(self):
        mc = {"name": "chest", "x": 0, "y": 0, "z": 0, "data": 0}
        local = voxelize_block_local("chest", ASSETS, mc_block=mc)
        self.assertGreater(len(local), 100)
        colors = {rgba_to_hex(c) if isinstance(c, tuple) else c for c in local.values()}
        self.assertNotEqual(colors, {"808080"})

    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_red_bed_voxelizes_from_cem(self):
        mc = {
            "name": "red_bed",
            "x": 0,
            "y": 0,
            "z": 0,
            "data": 0,
            "properties": {"part": "foot"},
        }
        local = voxelize_block_local("red_bed", ASSETS, mc_block=mc)
        self.assertGreater(len(local), 50)

        local = voxelize_block_local("spruce_door", ASSETS)
        self.assertGreater(len(local), 0)
        colors = {rgba_to_hex(c) if isinstance(c, tuple) else c for c in local.values()}
        self.assertNotEqual(colors, {"808080"})


if __name__ == "__main__":
    unittest.main()
