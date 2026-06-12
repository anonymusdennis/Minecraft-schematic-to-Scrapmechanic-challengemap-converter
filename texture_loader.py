# texture_loader.py
import os
from pathlib import Path

from PIL import Image

# Cache loaded images to avoid reloading
_texture_cache = {}


def _texture_search_paths(file_path):
    """Primary path plus common Nautilus3D / vanilla alternate locations."""
    path = Path(file_path)
    yield path
    if path.suffix.lower() != ".png" or "textures" not in path.parts:
        return

    textures_idx = path.parts.index("textures")
    rel = Path(*path.parts[textures_idx + 1 :])
    if len(rel.parts) < 2 or rel.parts[0] != "block":
        return

    block_dir = path.parent
    name = path.name
    stem = path.stem
    yield block_dir / "break" / name
    yield block_dir / f"{stem}_side.png"
    yield block_dir / f"{stem}_top.png"
    yield block_dir / f"{stem}_front.png"
    if stem.endswith("_door_bottom"):
        wood = stem[: -len("_door_bottom")]
        doors = block_dir / "doors"
        yield doors / f"{wood}_door.png"
        yield doors / name


def load_texture(file_path, *, warn=True):
    """Load an image and return a Pillow Image object. Returns None if file doesn't exist."""
    key = str(file_path)
    if key in _texture_cache:
        return _texture_cache[key]

    for candidate in _texture_search_paths(file_path):
        candidate_key = str(candidate)
        if candidate_key in _texture_cache:
            if _texture_cache[candidate_key] is not None:
                _texture_cache[key] = _texture_cache[candidate_key]
                return _texture_cache[key]
            continue
        if not candidate.is_file():
            continue
        try:
            img = Image.open(candidate)
            img = img.convert("RGBA")
            # Animated textures are vertical frame strips with a .mcmeta file:
            # crop to the first frame so UV sampling hits real pixels.
            w, h = img.size
            if h > w and h % w == 0 and Path(f"{candidate}.mcmeta").is_file():
                img = img.crop((0, 0, w, w))
            _texture_cache[candidate_key] = img
            _texture_cache[key] = img
            return img
        except Exception as e:
            if warn:
                print(f"Warning: failed to load texture {candidate}: {e}")
            _texture_cache[candidate_key] = None

    if warn:
        print(f"Warning: texture file not found: {file_path}")
    _texture_cache[key] = None
    return None

def sample_texture(img, uv_coords):
    """
    Sample the color from the image at the given UV coordinates.
    :param img: Pillow Image (RGBA) or None.
    :param uv_coords: (u, v) tuple in [0,1] range (normalized texture coords).
    :return: (r, g, b, a) color tuple, or None if img is None.
    """
    if img is None:
        return None
    width, height = img.size
    if width == 0 or height == 0:
        return None
    # Compute pixel coordinates – note that (0,0) in UV is top-left of the image
    # Clamp UV coordinates to [0, 1] range first
    u = max(0.0, min(1.0, uv_coords[0]))
    v = max(0.0, min(1.0, uv_coords[1]))
    px = int(u * width)
    py = int(v * height)
    # Clamp to image bounds (in case of 1.0 exactly, use last pixel index)
    if px >= width:  px = width - 1
    if py >= height: py = height - 1
    if px < 0: px = 0
    if py < 0: py = 0
    try:
        color = img.getpixel((px, py))
        return color
    except (IndexError, TypeError):
        # Fallback if getpixel fails for any reason
        return None
