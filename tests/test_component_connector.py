"""Tests for highlighted connector bridges between islands."""

import unittest

from component_connector import connect_floating_components, count_connected_components
from config import CONNECTOR_COLOR as CFG_COLOR


class TestComponentConnector(unittest.TestCase):
    def _grid_with_two_cubes(self, gap=5):
        grid = {}
        for x in range(16):
            for y in range(16):
                for z in range(16):
                    grid[(x, y, z)] = {"color": "808080"}
        offset = 16 + gap
        for x in range(offset, offset + 16):
            for y in range(16):
                for z in range(16):
                    grid[(x, y, z)] = {"color": "808080"}
        return grid

    def test_connects_two_islands(self):
        grid = self._grid_with_two_cubes(gap=8)
        self.assertEqual(count_connected_components(set(grid.keys())), 2)
        added = connect_floating_components(grid)
        self.assertGreater(added, 0)
        self.assertEqual(count_connected_components(set(grid.keys())), 1)

    def test_connector_is_indestructible_glass(self):
        from config import CHALLENGE_GLASS_SHAPE_ID, CONNECTOR_SHAPE_ID

        grid = self._grid_with_two_cubes(gap=4)
        connect_floating_components(grid)
        connectors = [p for p, v in grid.items() if v.get("is_connector")]
        self.assertTrue(connectors)
        self.assertEqual(CONNECTOR_SHAPE_ID, CHALLENGE_GLASS_SHAPE_ID)
        for pos in connectors:
            self.assertEqual(grid[pos]["color"], CFG_COLOR)
            self.assertEqual(grid[pos]["shapeId"], CONNECTOR_SHAPE_ID)

    def test_connector_matches_island_color(self):
        grid = self._grid_with_two_cubes(gap=4)
        # second cube (smaller after sort? equal size) — color all of one cube red
        for pos in list(grid):
            if pos[0] >= 16:
                grid[pos] = {"color": "FF0000"}
        connect_floating_components(grid, match_island_color=True)
        connectors = [p for p, v in grid.items() if v.get("is_connector")]
        self.assertTrue(connectors)
        for pos in connectors:
            self.assertIn(grid[pos]["color"], ("FF0000", "808080"))

    def test_single_component_unchanged(self):
        grid = {(0, 0, 0): {"color": "808080"}, (1, 0, 0): {"color": "808080"}}
        self.assertEqual(connect_floating_components(grid), 0)


if __name__ == "__main__":
    unittest.main()
