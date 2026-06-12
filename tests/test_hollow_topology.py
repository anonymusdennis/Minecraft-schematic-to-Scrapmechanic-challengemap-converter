"""Tests for solid-topology hollow with sparse 3D shells."""

import unittest

from component_connector import count_connected_components
from hollow import worldedit_hollow


def _part(x, y, z, color="808080"):
    return {
        "pos": {"x": float(x), "y": float(y), "z": float(z)},
        "bounds": {"x": 1, "y": 1, "z": 1},
        "color": color,
        "shapeId": "628b2d61-5ceb-43e9-8334-a4135566df7a",
        "xaxis": 1,
        "zaxis": 3,
    }


class TestHollowTopology(unittest.TestCase):
    def test_sparse_shell_stays_one_component_with_solid_topology(self):
        solid = {(x, y, z) for x in range(5) for y in range(5) for z in range(5)}
        # Sparse interior detail only — would shatter without solid mask
        sparse_parts = [
            _part(x, 0, z, "FF0000")
            for x in range(5)
            for z in range(5)
            if x in (0, 4) or z in (0, 4)
        ]
        bp = worldedit_hollow(
            {"bodies": [{"childs": sparse_parts}]},
            topology_occupied=solid,
        )
        kept = {
            (int(p["pos"]["x"]), int(p["pos"]["y"]), int(p["pos"]["z"]))
            for p in bp["bodies"][0]["childs"]
        }
        self.assertEqual(count_connected_components(kept), 1)
        self.assertNotIn((2, 2, 2), kept)

    def test_dynamic_mesh_bounds_topology(self):
        solid = {(x, 0, z) for x in range(4) for z in range(4)}
        merged = [{
            "pos": {"x": 0.0, "y": 0.0, "z": 0.0},
            "bounds": {"x": 4, "y": 1, "z": 4},
            "color": "808080",
            "shapeId": "628b2d61-5ceb-43e9-8334-a4135566df7a",
            "xaxis": 1,
            "zaxis": 3,
        }]
        bp = worldedit_hollow(
            {"bodies": [{"childs": merged}]},
            topology_occupied=solid,
        )
        self.assertEqual(len(bp["bodies"][0]["childs"]), 1)

    def test_dynamic_mesh_kept_when_anchor_interior_but_bounds_touch_shell(self):
        solid = {(x, y, z) for x in range(5) for y in range(5) for z in range(5)}
        merged = [{
            "pos": {"x": 1.0, "y": 1.0, "z": 1.0},
            "bounds": {"x": 4, "y": 4, "z": 4},
            "color": "808080",
            "shapeId": "628b2d61-5ceb-43e9-8334-a4135566df7a",
            "xaxis": 1,
            "zaxis": 3,
        }]
        bp = worldedit_hollow(
            {"bodies": [{"childs": merged}]},
            topology_occupied=solid,
        )
        self.assertEqual(len(bp["bodies"][0]["childs"]), 1)

    def test_dynamic_mesh_removed_when_fully_interior(self):
        solid = {(x, y, z) for x in range(5) for y in range(5) for z in range(5)}
        merged = [{
            "pos": {"x": 2.0, "y": 2.0, "z": 2.0},
            "bounds": {"x": 1, "y": 1, "z": 1},
            "color": "808080",
            "shapeId": "628b2d61-5ceb-43e9-8334-a4135566df7a",
            "xaxis": 1,
            "zaxis": 3,
        }]
        bp = worldedit_hollow(
            {"bodies": [{"childs": merged}]},
            topology_occupied=solid,
        )
        self.assertEqual(len(bp["bodies"][0]["childs"]), 0)


if __name__ == "__main__":
    unittest.main()
