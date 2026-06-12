"""Tests for per-block builder palette prefabs."""

import unittest
from pathlib import Path

from block_prefab_library import (
    build_block_prefab_parts,
    catalog_used_blocks,
    prefab_filename,
)
from config import VOXEL_SCALE
from hollow import occupied_from_parts

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS = PROJECT_ROOT / "MyResourcePack/assets"


class TestBlockPrefabLibrary(unittest.TestCase):
    def test_catalog_dedupes_by_variant(self):
        blocks = [
            {"name": "oak_slab", "properties": {"type": "top"}},
            {"name": "oak_slab", "properties": {"type": "bottom"}},
            {"name": "stone", "properties": {}},
            {"name": "stone", "properties": {}},
        ]
        catalog = catalog_used_blocks(blocks)
        names = {b["name"] for b in catalog}
        self.assertEqual(names, {"oak_slab", "stone"})
        self.assertEqual(len(catalog), 3)

    def test_prefab_filename_includes_variant(self):
        mc = {"name": "oak_slab", "properties": {"type": "top"}}
        self.assertIn("type-top", prefab_filename(mc))

    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_cobblestone_prefab_is_hollow_shell(self):
        parts = build_block_prefab_parts({"name": "cobblestone", "properties": {}}, ASSETS)
        self.assertGreater(len(parts), 0)
        self.assertLess(len(parts), VOXEL_SCALE ** 3)
        occupied = occupied_from_parts(parts)
        cx = cy = cz = VOXEL_SCALE // 2
        self.assertNotIn((cx, cy, cz), occupied)

    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_stair_prefab_uses_model_not_full_cube(self):
        mc = {
            "name": "oak_stairs",
            "properties": {"facing": "south", "half": "bottom", "shape": "straight"},
        }
        parts = build_block_prefab_parts(mc, ASSETS)
        self.assertGreater(len(parts), 100)
        self.assertLess(len(parts), VOXEL_SCALE ** 3)

    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_slab_prefab_is_half_height(self):
        mc = {"name": "oak_slab", "properties": {"type": "bottom"}}
        parts = build_block_prefab_parts(mc, ASSETS)
        ys = [int(p["pos"]["y"]) for p in parts]
        self.assertLessEqual(max(ys), 7)


if __name__ == "__main__":
    unittest.main()
