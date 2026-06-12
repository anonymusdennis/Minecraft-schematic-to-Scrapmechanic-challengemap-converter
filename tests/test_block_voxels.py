"""Tests for block texture voxelization."""

import unittest
from pathlib import Path

from block_voxels import opaque_cell_voxels, voxelize_block_local
from blueprint_writer import rgba_to_hex

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS = PROJECT_ROOT / "MyResourcePack/assets"


class TestBlockVoxels(unittest.TestCase):
    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_spruce_planks_are_not_flat_gray(self):
        local = opaque_cell_voxels("spruce_planks", ASSETS)
        colors = {rgba_to_hex(c) if isinstance(c, tuple) else c for c in local.values()}
        self.assertGreater(len(colors), 1)
        self.assertNotEqual(colors, {"808080"})

    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_bare_texture_variable_resolves(self):
        local = voxelize_block_local("spruce_planks", ASSETS)
        self.assertGreater(len(local), 0)


if __name__ == "__main__":
    unittest.main()
