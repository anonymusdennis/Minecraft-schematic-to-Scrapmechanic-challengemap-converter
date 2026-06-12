"""Multi-resource-pack asset resolution with vanilla fallback.

Search order for every asset (blockstate, model, texture):

1. The explicitly requested assets dir (``--assets`` / ``SM_ASSETS_DIR``)
2. Every pack in ``resourcepacks/`` sorted alphabetically (``1 foo`` beats ``2 bar``).
   Both plain folders and ``.zip`` packs are supported; zips are extracted once
   into ``.cache/resourcepacks/``.
3. ``supplement_assets/`` (generated chest/bed geometry)
4. ``vanilla_assets/`` (full vanilla models/blockstates/textures —
   run ``python3 download_vanilla_assets.py`` to populate)
"""

from __future__ import annotations

import shutil
import sys
import zipfile
from functools import lru_cache
from pathlib import Path

from assets_paths import normalize_assets_dir
from config import PROJECT_ROOT

RESOURCEPACKS_DIR = PROJECT_ROOT / "resourcepacks"
SUPPLEMENT_ASSETS = PROJECT_ROOT / "supplement_assets"
VANILLA_ASSETS = PROJECT_ROOT / "vanilla_assets"
_ZIP_CACHE = PROJECT_ROOT / ".cache" / "resourcepacks"


def bootstrap_bundled_packs():
    """
    Frozen (PyInstaller) builds ship the required 3D resource packs inside the
    executable. Copy any missing pack into the user-visible resourcepacks/
    folder next to the binary so they load like normal packs and the user can
    add or replace packs alongside them.
    """
    if not getattr(sys, "frozen", False):
        return
    bundled = Path(getattr(sys, "_MEIPASS", "")) / "resourcepacks"
    if not bundled.is_dir():
        return
    try:
        RESOURCEPACKS_DIR.mkdir(parents=True, exist_ok=True)
        for entry in bundled.iterdir():
            dest = RESOURCEPACKS_DIR / entry.name
            if dest.exists():
                continue
            if entry.is_dir():
                shutil.copytree(entry, dest)
            else:
                shutil.copy2(entry, dest)
    except Exception as e:  # never block conversion on bootstrap problems
        print(f"Warning: could not unpack bundled resource packs: {e}")


def _extract_zip_pack(zip_path: Path) -> Path | None:
    """Extract a zipped resource pack once; return its extraction dir."""
    dest = _ZIP_CACHE / zip_path.stem
    marker = dest / ".extracted"
    if marker.is_file():
        return dest
    try:
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(dest)
        marker.write_text("ok", encoding="utf-8")
        return dest
    except Exception as e:
        print(f"Warning: could not extract resource pack {zip_path.name}: {e}")
        return None


def _pack_assets_root(pack_dir: Path) -> Path | None:
    """Return the ``assets`` root inside a pack folder, if present."""
    for candidate in (pack_dir / "assets", pack_dir):
        if (candidate / "minecraft").is_dir():
            return candidate
    return None


@lru_cache(maxsize=8)
def _resourcepack_roots() -> tuple[Path, ...]:
    bootstrap_bundled_packs()
    roots: list[Path] = []
    if RESOURCEPACKS_DIR.is_dir():
        for entry in sorted(RESOURCEPACKS_DIR.iterdir(), key=lambda p: p.name.lower()):
            if entry.is_dir():
                root = _pack_assets_root(entry)
                if root:
                    roots.append(root)
            elif entry.suffix.lower() == ".zip":
                extracted = _extract_zip_pack(entry)
                if extracted:
                    root = _pack_assets_root(extracted)
                    if root:
                        roots.append(root)
    return tuple(roots)


@lru_cache(maxsize=64)
def _roots_for_primary(primary: Path | None) -> tuple[Path, ...]:
    roots: list[Path] = []

    seen: set[Path] = set()

    def _add(path: Path | None):
        if path is None:
            return
        path = normalize_assets_dir(path)
        if not path.is_dir():
            return
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            roots.append(resolved)

    _add(primary)
    for pack_root in _resourcepack_roots():
        _add(pack_root)

    # Default pack (kept for backwards compatibility with --assets omitted)
    from config import SM_ASSETS_DIR

    _add(SM_ASSETS_DIR)
    _add(SUPPLEMENT_ASSETS)
    _add(VANILLA_ASSETS)
    return tuple(roots)


def asset_roots(primary=None) -> tuple[Path, ...]:
    """Ordered assets roots (each containing ``minecraft/``)."""
    if primary is not None and not isinstance(primary, Path):
        primary = Path(primary)
    return _roots_for_primary(primary)


def find_asset(relative: str, primary=None) -> Path | None:
    """Return the first existing ``<root>/<relative>`` across the pack stack."""
    rel = relative.replace("\\", "/").lstrip("/")
    for root in asset_roots(primary):
        candidate = root / rel
        if candidate.is_file():
            return candidate
    return None


def find_asset_all(relative: str, primary=None) -> list[Path]:
    """Return every existing ``<root>/<relative>`` in priority order."""
    rel = relative.replace("\\", "/").lstrip("/")
    hits: list[Path] = []
    for root in asset_roots(primary):
        candidate = root / rel
        if candidate.is_file():
            hits.append(candidate)
    return hits


def find_model_files_all(model_path: str, primary=None, namespace: str = "minecraft") -> list[Path]:
    """All ``models/<model_path>.json`` hits across the pack stack, best first."""
    if ":" in model_path:
        namespace, model_path = model_path.split(":", 1)
    return find_asset_all(f"{namespace}/models/{model_path}.json", primary)


def find_model_file(model_path: str, primary=None, namespace: str = "minecraft") -> Path | None:
    """Locate ``models/<model_path>.json`` across the pack stack."""
    if ":" in model_path:
        namespace, model_path = model_path.split(":", 1)
    return find_asset(f"{namespace}/models/{model_path}.json", primary)


def find_blockstate_file(block_name: str, primary=None) -> Path | None:
    return find_asset(f"minecraft/blockstates/{block_name}.json", primary)


def find_texture_file(tex_path: str, primary=None, namespace: str = "minecraft") -> Path | None:
    """Locate ``textures/<tex_path>`` (``.png`` appended when missing)."""
    if ":" in tex_path:
        namespace, tex_path = tex_path.split(":", 1)
    if not tex_path.endswith(".png"):
        tex_path = f"{tex_path}.png"
    return find_asset(f"{namespace}/textures/{tex_path}", primary)


def clear_caches():
    _resourcepack_roots.cache_clear()
    _roots_for_primary.cache_clear()
