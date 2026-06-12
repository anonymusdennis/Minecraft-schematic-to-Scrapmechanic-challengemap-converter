#!/usr/bin/env python3
"""
Download the complete vanilla Minecraft asset base:
all block/item models, blockstates, and textures from the official client jar
into ``vanilla_assets/minecraft/``. This is the lowest-priority fallback for the
converter; resource packs in ``resourcepacks/`` override it.

Usage:
    python3 download_vanilla_assets.py [--version 1.21.10]
"""

from __future__ import annotations

import argparse
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT = PROJECT_ROOT / "vanilla_assets" / "minecraft"

WANTED_PREFIXES = (
    "models/",
    "blockstates/",
    "textures/block/",
    "textures/item/",
    "textures/entity/chest/",
    "textures/entity/bed/",
    "textures/entity/signs/",
    "textures/painting/",
    "textures/colormap/",
)


def _fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read())


def _resolve_version(version: str | None) -> dict:
    manifest = _fetch_json(
        "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
    )
    if version is None or version == "latest":
        version = manifest["latest"]["release"]
        print(f"Using latest release: {version}")
    for entry in manifest["versions"]:
        if entry["id"] == version:
            return _fetch_json(entry["url"])
    raise SystemExit(f"Version {version} not found in Mojang manifest")


def download_vanilla_assets(version: str | None = None) -> Path:
    meta = _resolve_version(version)
    client_url = meta["downloads"]["client"]["url"]
    jar_path = PROJECT_ROOT / ".cache" / f"mc-{meta['id']}-client.jar"
    jar_path.parent.mkdir(parents=True, exist_ok=True)

    if not jar_path.is_file():
        print(f"Downloading Minecraft {meta['id']} client jar...")
        urllib.request.urlretrieve(client_url, jar_path)
    else:
        print(f"Using cached jar: {jar_path}")

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    extracted = 0
    with zipfile.ZipFile(jar_path) as zf:
        for name in zf.namelist():
            if not name.startswith("assets/minecraft/"):
                continue
            rel = name[len("assets/minecraft/"):]
            if not rel.startswith(WANTED_PREFIXES):
                continue
            if name.endswith("/"):
                continue
            dest = OUTPUT / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(name))
            extracted += 1

    print(f"Extracted {extracted} vanilla asset files to {OUTPUT}")
    return OUTPUT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        default=None,
        help="Minecraft version (default: latest release)",
    )
    args = parser.parse_args(argv)
    download_vanilla_assets(args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
