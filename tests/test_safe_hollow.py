"""Tests for thickness-aware safe hollow on transparent geometry."""

import unittest

from hollow import (
    MIN_SAFE_HOLLOW_THICKNESS,
    bbox_min_extent,
    safe_worldedit_hollow,
    should_hollow_geometry,
)


def _parts(positions):
    return [
        {
            "pos": {"x": float(x), "y": float(y), "z": float(z)},
            "bounds": {"x": 1, "y": 1, "z": 1},
            "color": "AARRGG",
            "shapeId": "628b2d61-5ceb-43e9-8334-a4135566df7a",
            "xaxis": 1,
            "zaxis": 3,
            "is_transparent": True,
        }
        for x, y, z in positions
    ]


class TestSafeHollow(unittest.TestCase):
    def test_four_voxel_slab_not_hollowed(self):
        positions = [(x, 0, 0) for x in range(4)]
        self.assertEqual(bbox_min_extent(set(positions)), 1)
        self.assertFalse(should_hollow_geometry(set(positions)))
        kept = safe_worldedit_hollow(_parts(positions))
        self.assertEqual(len(kept), 4)

    def test_thick_glass_block_is_hollowed(self):
        positions = [(x, y, z) for x in range(6) for y in range(6) for z in range(6)]
        self.assertGreater(bbox_min_extent(set(positions)), MIN_SAFE_HOLLOW_THICKNESS)
        kept = safe_worldedit_hollow(_parts(positions))
        self.assertLess(len(kept), len(positions))

    def test_four_cube_not_hollowed(self):
        positions = [(x, y, z) for x in range(4) for y in range(4) for z in range(4)]
        self.assertEqual(bbox_min_extent(set(positions)), 4)
        self.assertFalse(should_hollow_geometry(set(positions)))
        kept = safe_worldedit_hollow(_parts(positions))
        self.assertEqual(len(kept), len(positions))


if __name__ == "__main__":
    unittest.main()
