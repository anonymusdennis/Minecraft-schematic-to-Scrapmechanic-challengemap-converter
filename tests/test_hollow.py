"""Tests for WorldEdit //hollow implementation."""

import unittest

from hollow import is_surface_voxel, worldedit_hollow


def _make_blueprint(positions):
    parts = [
        {
            "pos": {"x": float(x), "y": float(y), "z": float(z)},
            "bounds": {"x": 1, "y": 1, "z": 1},
            "color": "808080",
            "shapeId": "628b2d61-5ceb-43e9-8334-a4135566df7a",
            "xaxis": 1,
            "zaxis": 3,
        }
        for x, y, z in positions
    ]
    return {"bodies": [{"childs": parts}], "version": 4}


def _positions(blueprint):
    return {
        (
            int(p["pos"]["x"]),
            int(p["pos"]["y"]),
            int(p["pos"]["z"]),
        )
        for p in blueprint["bodies"][0]["childs"]
    }


class TestWorldEditHollow(unittest.TestCase):
    def test_solid_5x5x5_cube_has_98_surface_voxels(self):
        positions = [(x, y, z) for x in range(5) for y in range(5) for z in range(5)]
        bp = worldedit_hollow(_make_blueprint(positions))
        self.assertEqual(len(bp["bodies"][0]["childs"]), 98)

    def test_hollow_cube_shell_only(self):
        positions = []
        for x in range(5):
            for y in range(5):
                for z in range(5):
                    if x in (0, 4) or y in (0, 4) or z in (0, 4):
                        positions.append((x, y, z))
        bp = worldedit_hollow(_make_blueprint(positions))
        self.assertEqual(len(bp["bodies"][0]["childs"]), len(positions))

    def test_two_rooms_separated_by_wall(self):
        positions = []
        for x in range(9):
            for y in range(5):
                for z in range(5):
                    in_left = 1 <= x <= 3 and 1 <= y <= 3 and 1 <= z <= 3
                    in_right = 5 <= x <= 7 and 1 <= y <= 3 and 1 <= z <= 3
                    is_wall = x == 4
                    if in_left or in_right or is_wall:
                        positions.append((x, y, z))
        bp = worldedit_hollow(_make_blueprint(positions))
        kept = _positions(bp)
        self.assertIn((1, 2, 2), kept)
        self.assertIn((7, 2, 2), kept)
        self.assertNotIn((2, 2, 2), kept)
        self.assertNotIn((6, 2, 2), kept)

    def test_u_shape_keeps_all_exposed_faces(self):
        positions = []
        for x in range(5):
            for z in range(3):
                if x == 0 or x == 4 or z == 0:
                    positions.append((x, 0, z))
        bp = worldedit_hollow(_make_blueprint(positions))
        self.assertEqual(len(bp["bodies"][0]["childs"]), len(positions))

    def test_is_surface_voxel(self):
        occupied = {(0, 0, 0), (1, 0, 0)}
        self.assertTrue(is_surface_voxel((0, 0, 0), occupied))
        self.assertTrue(is_surface_voxel((1, 0, 0), occupied))


if __name__ == "__main__":
    unittest.main()
