"""Tests for Scrap Mechanic blueprint JSON normalization."""

import json
import tempfile
import unittest
from pathlib import Path

from sm_format import normalize_level_creation_blueprint, write_sm_json


class TestSmFormat(unittest.TestCase):
    def test_normalize_matches_game_types(self):
        parts = [{
            "bounds": {"x": 3, "y": 1, "z": 2},
            "shapeId": "628b2d61-5ceb-43e9-8334-a4135566df7a",
            "color": "787878",
            "pos": {"x": 16, "y": 48, "z": 48},
            "xaxis": 1,
            "zaxis": 3,
        }]
        bp = normalize_level_creation_blueprint(parts)
        self.assertEqual(bp["version"], 3.0)
        self.assertEqual(bp["joints"], [])
        body = bp["bodies"][0]
        self.assertEqual(body["type"], 0.0)
        self.assertIn("transform", body)
        part = body["childs"][0]
        self.assertIsInstance(part["xaxis"], float)
        self.assertIsInstance(part["bounds"]["x"], float)

    def test_single_body_when_parts_per_body_matches_chunk(self):
        parts = [{"pos": {"x": 0, "y": 0, "z": 0}, "color": "808080"} for _ in range(150)]
        bp = normalize_level_creation_blueprint(parts, parts_per_body=150)
        self.assertEqual(len(bp["bodies"]), 1)
        self.assertEqual(bp["joints"], [])

    def test_multi_body_only_when_parts_per_body_capped(self):
        parts = [{"pos": {"x": 0, "y": 0, "z": 0}, "color": "808080"} for _ in range(150)]
        bp = normalize_level_creation_blueprint(parts, parts_per_body=100)
        self.assertEqual(len(bp["bodies"]), 2)
        self.assertEqual(bp["joints"], [])

    def test_multi_body_gets_bearing_joints_when_enabled(self):
        parts = [{"pos": {"x": 0, "y": 0, "z": 0}, "color": "808080"} for _ in range(150)]
        bp = normalize_level_creation_blueprint(
            parts, parts_per_body=100, weld_bodies=True
        )
        self.assertEqual(len(bp["joints"]), 1)
        self.assertEqual(bp["joints"][0]["childA"], 0.0)
        self.assertEqual(bp["joints"][0]["childB"], 100.0)
        self.assertEqual(
            bp["joints"][0]["shapeId"], "4a1b886b-913e-4aad-b5b6-6e41b0db23a6"
        )
        anchor = bp["bodies"][0]["childs"][0]
        self.assertEqual(len(anchor.get("joints", [])), 1)

    def test_write_uses_tabs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.blueprint"
            write_sm_json({"version": 3.0}, path)
            text = path.read_text()
            self.assertIn('\t"', text)
            self.assertTrue(text.endswith("\n"))


if __name__ == "__main__":
    unittest.main()
