"""Tests for welded schematic map building."""

import unittest

from component_connector import count_connected_components
from hollow import worldedit_hollow
from map_builder import build_voxel_map
from transparent_blocks import is_transparent_block


class TestMapBuilder(unittest.TestCase):
    def test_adjacent_mc_blocks_share_faces(self):
        schematic = {
            "width": 2,
            "height": 1,
            "length": 1,
            "blocks": [
                {"x": 0, "y": 0, "z": 0, "name": "stone", "data": 0},
                {"x": 1, "y": 0, "z": 0, "name": "stone", "data": 0},
            ],
        }
        blueprint, stats = build_voxel_map(schematic, "/nonexistent", progress=False)
        positions = {
            (int(p["pos"]["x"]), int(p["pos"]["y"]), int(p["pos"]["z"]))
            for p in blueprint["bodies"][0]["childs"]
            if not p.get("is_transparent")
        }
        self.assertIn((15, 0, 0), positions)
        self.assertIn((16, 0, 0), positions)
        self.assertEqual(count_connected_components(positions), 1)

    def test_welded_cube_hollows_as_one_structure(self):
        schematic = {
            "width": 3,
            "height": 3,
            "length": 3,
            "blocks": [
                {"x": x, "y": y, "z": z, "name": "stone", "data": 0}
                for x in range(3) for y in range(3) for z in range(3)
            ],
        }
        blueprint, stats = build_voxel_map(schematic, "/nonexistent", progress=False)
        structure = [
            p for p in blueprint["bodies"][0]["childs"] if not p.get("is_transparent")
        ]
        positions = {
            (int(p["pos"]["x"]), int(p["pos"]["y"]), int(p["pos"]["z"]))
            for p in structure
        }
        self.assertEqual(count_connected_components(positions), 1)
        struct_bp = {"bodies": [{"childs": structure}]}
        before = len(structure)
        struct_bp = worldedit_hollow(struct_bp)
        after = len(struct_bp["bodies"][0]["childs"])
        self.assertLess(after, before * 0.5)

    def test_stone_is_not_transparent(self):
        self.assertFalse(is_transparent_block("stone"))


if __name__ == "__main__":
    unittest.main()
