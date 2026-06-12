#!/usr/bin/env python3
"""
Download vanilla Minecraft block models/blockstates and generate geometry
for block-entity blocks (chest, bed) from item templates and OptiFine CEM.

Usage:
    python3 download_supplement_models.py [--version 1.21.6]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT = PROJECT_ROOT / "supplement_assets" / "minecraft"

KEYWORDS = (
    "chest", "bed", "anvil", "fence", "door", "trapdoor",
    "gate", "bars", "button", "lever", "lantern", "chain",
)


def _fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read())


def _version_manifest(version: str) -> dict:
    manifest = _fetch_json(
        "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
    )
    for entry in manifest["versions"]:
        if entry["id"] == version:
            return _fetch_json(entry["url"])
    raise SystemExit(f"Version {version} not found in Mojang manifest")


def download_vanilla_assets(version: str = "1.21.6") -> Path:
    meta = _version_manifest(version)
    client_url = meta["downloads"]["client"]["url"]
    jar_path = PROJECT_ROOT / ".cache" / f"mc-{version}-client.jar"
    jar_path.parent.mkdir(parents=True, exist_ok=True)

    if not jar_path.is_file():
        print(f"Downloading Minecraft {version} client jar...")
        urllib.request.urlretrieve(client_url, jar_path)
    else:
        print(f"Using cached jar: {jar_path}")

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT.parent)
    OUTPUT.mkdir(parents=True)

    extracted = 0
    with zipfile.ZipFile(jar_path) as zf:
        for name in zf.namelist():
            if not name.startswith("assets/minecraft/"):
                continue
            rel = name[len("assets/minecraft/"):]
            if not rel.startswith(("models/", "blockstates/")):
                continue
            base = Path(rel).name
            if not any(k in base for k in KEYWORDS):
                continue
            dest = OUTPUT / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(name))
            extracted += 1

    print(f"Extracted {extracted} vanilla model/blockstate files to {OUTPUT}")
    return OUTPUT


def generate_derived_models(assets_dir: Path) -> int:
    """
    Write block model JSON with elements for chest/bed by copying geometry
    from item templates and CEM where vanilla block models are empty.
    """
    from cem_parser import cem_part_to_model
    from dynamic_model_loader import _load_chest_item_model

    generated = OUTPUT / "models" / "block" / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    count = 0

    chest_blocks = (
        "chest", "trapped_chest", "ender_chest",
        "copper_chest", "exposed_copper_chest",
        "weathered_copper_chest", "oxidized_copper_chest",
    )
    for name in chest_blocks:
        model = _load_chest_item_model(name, assets_dir, "single")
        if not model.get("elements"):
            continue
        out = generated / f"{name}.json"
        out.write_text(json.dumps(model, indent=2), encoding="utf-8")
        count += 1

    for part in ("head", "foot"):
        for color in (
            "red", "white", "black", "blue", "brown", "cyan", "gray",
            "green", "light_blue", "light_gray", "lime", "magenta",
            "orange", "pink", "purple", "yellow",
        ):
            model = cem_part_to_model(assets_dir, part, color)
            if not model.get("elements"):
                continue
            out = generated / f"{color}_bed_{part}.json"
            out.write_text(json.dumps(model, indent=2), encoding="utf-8")
            count += 1

    print(f"Generated {count} derived block models in {generated}")
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="1.21.6", help="Minecraft version")
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Only regenerate derived models from the local resource pack",
    )
    args = parser.parse_args(argv)

    pack_assets = PROJECT_ROOT / "MyResourcePack" / "assets"
    if not pack_assets.is_dir():
        print("Warning: MyResourcePack/assets not found; derived models may be empty")

    if not args.skip_download:
        download_vanilla_assets(args.version)

    if pack_assets.is_dir():
        generate_derived_models(pack_assets)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
