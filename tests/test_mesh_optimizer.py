"""Tests for greedy mesh merging."""

import unittest

from mesh_optimizer import greedy_mesh_merge


def _unit_part(x, y, z):
    return {
        "pos": {"x": float(x), "y": float(y), "z": float(z)},
        "bounds": {"x": 1, "y": 1, "z": 1},
        "color": "FF0000",
        "shapeId": "628b2d61-5ceb-43e9-8334-a4135566df7a",
        "xaxis": 1,
        "zaxis": 3,
    }


class TestMeshOptimizer(unittest.TestCase):
    def test_merge_2x2_plane_into_one_part(self):
        parts = [_unit_part(x, 0, 0) for x in range(2)]
        bp = {"bodies": [{"childs": parts}], "version": 4}
        result = greedy_mesh_merge(bp)
        self.assertEqual(len(result["bodies"][0]["childs"]), 1)
        merged = result["bodies"][0]["childs"][0]
        self.assertEqual(merged["bounds"]["x"], 2)

    def test_merge_preserves_transparent_flag(self):
        parts = [_unit_part(0, 0, 0)]
        parts[0]["is_transparent"] = True
        bp = {"bodies": [{"childs": parts}], "version": 4}
        result = greedy_mesh_merge(bp)
        self.assertTrue(result["bodies"][0]["childs"][0].get("is_transparent"))

    def test_merge_2x2x2_cube_into_one_part(self):
        parts = [
            _unit_part(x, y, z)
            for x in range(2) for y in range(2) for z in range(2)
        ]
        bp = {"bodies": [{"childs": parts}], "version": 4}
        result = greedy_mesh_merge(bp)
        self.assertEqual(len(result["bodies"][0]["childs"]), 1)
        merged = result["bodies"][0]["childs"][0]
        self.assertEqual(merged["bounds"]["x"], 2)
        self.assertEqual(merged["bounds"]["y"], 2)
        self.assertEqual(merged["bounds"]["z"], 2)


if __name__ == "__main__":
    unittest.main()
