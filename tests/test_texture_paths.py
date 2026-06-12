"""Tests for texture path resolution and quiet candidate loading."""

import io
import sys
import unittest
from pathlib import Path
from unittest import mock

from assets_paths import normalize_assets_dir, texture_file_path
from block_voxels import _sample_block_texture_color
from texture_loader import _texture_cache, load_texture

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS = PROJECT_ROOT / "MyResourcePack/assets"
ASSETS_MINECRAFT = ASSETS / "minecraft"


class TestTexturePaths(unittest.TestCase):
    def test_normalize_accepts_assets_root(self):
        self.assertEqual(normalize_assets_dir(ASSETS), ASSETS)

    def test_normalize_accepts_minecraft_subdir(self):
        self.assertEqual(normalize_assets_dir(ASSETS_MINECRAFT), ASSETS)

    def test_texture_file_path_no_double_minecraft(self):
        path = texture_file_path(ASSETS_MINECRAFT, "block/snow.png")
        self.assertEqual(path, ASSETS / "minecraft/textures/block/snow.png")

    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_sample_color_with_minecraft_subdir_assets_path(self):
        _texture_cache.clear()
        captured = io.StringIO()
        with mock.patch("sys.stdout", captured):
            color = _sample_block_texture_color("snow", ASSETS_MINECRAFT)
        self.assertIsNotNone(color)
        self.assertNotIn("texture file not found", captured.getvalue())

    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_load_texture_finds_break_folder_fallback(self):
        _texture_cache.clear()
        chest = ASSETS / "minecraft/textures/block/break/chest.png"
        self.assertTrue(chest.is_file())
        img = load_texture(
            str(ASSETS / "minecraft/textures/block/chest.png"),
            warn=False,
        )
        self.assertIsNotNone(img)


if __name__ == "__main__":
    unittest.main()
