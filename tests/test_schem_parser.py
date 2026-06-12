"""Tests for WorldEdit .schem schematic parsing."""

import unittest
from pathlib import Path

from config import DEFAULT_SCHEMATIC_PATH
from schematic_parser import parse_schematic_file

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestSchemParser(unittest.TestCase):
    @unittest.skipUnless(DEFAULT_SCHEMATIC_PATH.is_file(), "default schematic not present")
    def test_default_newhouse_schem_parses(self):
        data = parse_schematic_file(DEFAULT_SCHEMATIC_PATH)
        self.assertGreater(data["width"], 0)
        self.assertGreater(data["height"], 0)
        self.assertGreater(data["length"], 0)
        self.assertGreater(len(data["blocks"]), 0)
        sample = data["blocks"][0]
        self.assertIn("name", sample)
        self.assertIn("properties", sample)


if __name__ == "__main__":
    unittest.main()
