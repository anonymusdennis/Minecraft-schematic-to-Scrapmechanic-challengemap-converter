"""Tests for auto-numbered map names."""

import json
import tempfile
import unittest
from pathlib import Path

from map_naming import allocate_map_name


class TestMapNaming(unittest.TestCase):
    def _write_challenge(self, folder: Path, name: str):
        folder.mkdir(parents=True)
        with open(folder / "description.json", "w") as f:
            json.dump({"name": name, "type": "Challenge Level"}, f)

    def test_first_export_is_number_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(allocate_map_name("My House", Path(tmp)), "My House 1")

    def test_increments_from_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_challenge(root / "aaa", "My House 1")
            self._write_challenge(root / "bbb", "My House 2")
            self.assertEqual(allocate_map_name("My House", root), "My House 3")

    def test_legacy_unnumbered_counts_as_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_challenge(root / "legacy", "My House")
            self.assertEqual(allocate_map_name("My House", root), "My House 2")

    def test_legacy_hash_suffix_still_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_challenge(root / "legacy", "My House #2")
            self.assertEqual(allocate_map_name("My House", root), "My House 3")

    def test_strips_suffix_from_input_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_challenge(root / "a", "Castle 5")
            self.assertEqual(allocate_map_name("Castle 99", root), "Castle 6")


if __name__ == "__main__":
    unittest.main()
