"""Tests for LevelCreation export."""

import json
import tempfile
import unittest
from pathlib import Path

from challenge_exporter import export_block_prefabs, split_into_level_creations

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS = PROJECT_ROOT / "MyResourcePack/assets"


def _part(x, y=0, z=0):
    return {
        "pos": {"x": float(x), "y": float(y), "z": float(z)},
        "bounds": {"x": 1, "y": 1, "z": 1},
        "color": "808080",
        "shapeId": "628b2d61-5ceb-43e9-8334-a4135566df7a",
        "xaxis": 1,
        "zaxis": 3,
    }


class TestChallengeExporter(unittest.TestCase):
    def test_default_is_single_level_creation(self):
        parts = [_part(i) for i in range(200)]
        blueprint = {"bodies": [{"childs": parts}], "version": 4}
        chunks = split_into_level_creations(blueprint)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(len(chunks[0]["bodies"]), 1)
        self.assertEqual(len(chunks[0]["bodies"][0]["childs"]), 200)
        self.assertEqual(chunks[0].get("joints", []), [])

    @unittest.skipUnless(ASSETS.is_dir(), "resource pack not present")
    def test_export_block_prefabs_writes_start_creation_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            challenge_dir = Path(tmp)
            blocks = [
                {"name": "cobblestone", "properties": {}},
                {"name": "oak_stairs", "properties": {"facing": "south", "half": "bottom", "shape": "straight"}},
            ]
            paths = export_block_prefabs(blocks, challenge_dir, ASSETS)
            self.assertEqual(len(paths), 2)
            self.assertTrue(all(p.startswith("$CONTENT_DATA/Blueprints/Block_") for p in paths))
            written = list((challenge_dir / "Blueprints").glob("Block_*.blueprint"))
            self.assertEqual(len(written), 2)
            data = json.loads(written[0].read_text())
            self.assertIn("bodies", data)

    def test_split_mode_produces_multiple_chunks(self):
        parts = [_part(i % 80, (i // 80) % 80, i // 6400) for i in range(15000)]
        blueprint = {"bodies": [{"childs": parts}], "version": 4}
        chunks = split_into_level_creations(blueprint, split=True)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertEqual(chunk.get("joints", []), [])
            for body in chunk.get("bodies", []):
                for child in body.get("childs", []):
                    self.assertNotIn("joints", child)


if __name__ == "__main__":
    unittest.main()
