"""Shared Minecraft block voxelization and texture sampling."""

from pathlib import Path

from assets_paths import normalize_assets_dir, texture_file_path
from block_model_aliases import (
    is_sparse_shape_block,
    resolve_block_model_name,
    texture_override_paths,
)
from blueprint_writer import get_shape_id_for_block, rgba_to_hex
from config import VOXEL_SCALE


def _assets_path(assets_dir) -> Path:
    return normalize_assets_dir(assets_dir)


def _texture_ref_to_relative(tex_ref: str) -> str:
    if ":" in tex_ref:
        _, tex_path = tex_ref.split(":", 1)
    else:
        tex_path = tex_ref
    if not tex_path.endswith(".png"):
        tex_path = f"{tex_path}.png"
    if "/" not in tex_path:
        tex_path = f"block/{tex_path}"
    return tex_path


def _model_texture_paths(block_name: str, assets_dir) -> list:
    """Collect texture file paths declared on a block's model JSON."""
    from asset_resolution import find_texture_file
    from model_parser import load_model

    base = _assets_path(assets_dir)
    paths = []
    model_name = resolve_block_model_name(block_name)
    try:
        model = load_model(f"minecraft:block/{model_name}", str(base))
    except FileNotFoundError:
        return paths

    for tex_ref in model.get("textures", {}).values():
        if not tex_ref or tex_ref.startswith("#"):
            continue
        rel = _texture_ref_to_relative(tex_ref)
        found = find_texture_file(rel, base)
        paths.append(str(found) if found else str(texture_file_path(base, rel)))
    return paths


def _sample_block_texture_color(block_name: str, assets_dir) -> str | None:
    """Load a representative color from known pack texture paths."""
    from asset_resolution import find_texture_file
    from texture_loader import load_texture, sample_texture

    base = _assets_path(assets_dir)
    candidates = []

    for rel in texture_override_paths(block_name):
        found = find_texture_file(rel, base)
        candidates.append(found if found else texture_file_path(base, rel))

    candidates.extend(_model_texture_paths(block_name, assets_dir))

    for rel in (
        f"block/{block_name}.png",
        f"block/{block_name}_side.png",
        f"block/break/{block_name}.png",
    ):
        found = find_texture_file(rel, base)
        candidates.append(found if found else texture_file_path(base, rel))

    seen = set()
    for full in candidates:
        key = str(full)
        if key in seen:
            continue
        seen.add(key)
        img = load_texture(key, warn=False)
        if img is None:
            continue
        for uv in ((0.5, 0.5), (0.25, 0.25), (0.75, 0.75), (0.1, 0.9)):
            color = sample_texture(img, uv)
            if color and (len(color) < 4 or color[3] >= 128):
                return rgba_to_hex(color[:3])
        # Mostly-transparent textures (glass): average opaque pixels
        if img:
            pixels = [
                p[:3]
                for p in img.getdata()
                if len(p) > 3 and p[3] >= 128
            ]
            if pixels:
                r = sum(p[0] for p in pixels) // len(pixels)
                g = sum(p[1] for p in pixels) // len(pixels)
                b = sum(p[2] for p in pixels) // len(pixels)
                return rgba_to_hex((r, g, b))
    return None


def _rotate_y_local(x: int, y: int, z: int, degrees: int, scale: int = VOXEL_SCALE):
    """
    Rotate voxel coordinates around Y for blockstate model rotation.

    Minecraft convention: y=90 turns a north-facing (-z) model to face east (+x),
    i.e. x' = -z, z' = x in centered coordinates.
    """
    degrees = int(degrees) % 360
    if degrees == 0:
        return x, y, z
    cx = cy = cz = (scale - 1) / 2.0
    rx, ry, rz = x - cx, y - cy, z - cz
    if degrees == 90:
        nx, nz = int(round(-rz + cx)), int(round(rx + cz))
    elif degrees == 180:
        nx, nz = int(round(-rx + cx)), int(round(-rz + cz))
    elif degrees == 270:
        nx, nz = int(round(rz + cx)), int(round(-rx + cz))
    else:
        return x, y, z
    return max(0, min(scale - 1, nx)), y, max(0, min(scale - 1, nz))


def _rotate_x_local(x: int, y: int, z: int, degrees: int, scale: int = VOXEL_SCALE):
    """
    Minecraft convention: x=90 turns a north-facing (-z) model to face down (-y),
    i.e. y' = z, z' = -y in centered coordinates (observer/piston facing=down use x=90).
    """
    degrees = int(degrees) % 360
    if degrees == 0:
        return x, y, z
    cx = cy = cz = (scale - 1) / 2.0
    rx, ry, rz = x - cx, y - cy, z - cz
    if degrees == 90:
        ny, nz = int(round(rz + cy)), int(round(-ry + cz))
    elif degrees == 180:
        ny, nz = int(round(-ry + cy)), int(round(-rz + cz))
    elif degrees == 270:
        ny, nz = int(round(-rz + cy)), int(round(ry + cz))
    else:
        return x, y, z
    return x, max(0, min(scale - 1, ny)), max(0, min(scale - 1, nz))


def _rotate_z_local(x: int, y: int, z: int, degrees: int, scale: int = VOXEL_SCALE):
    degrees = int(degrees) % 360
    if degrees == 0:
        return x, y, z
    cx = cy = cz = (scale - 1) / 2.0
    rx, ry, rz = x - cx, y - cy, z - cz
    if degrees == 90:
        nx, ny = int(round(-ry + cx)), int(round(rx + cy))
    elif degrees == 180:
        nx, ny = int(round(-rx + cx)), int(round(-ry + cy))
    elif degrees == 270:
        nx, ny = int(round(ry + cx)), int(round(-rx + cy))
    else:
        return x, y, z
    return max(0, min(scale - 1, nx)), max(0, min(scale - 1, ny)), z


def merge_local_voxels_rotated(
    target: dict,
    source: dict,
    x_rotation: int = 0,
    y_rotation: int = 0,
    z_rotation: int = 0,
    scale: int = VOXEL_SCALE,
):
    """Apply Minecraft blockstate model rotations (x, then y, then z) to local voxels."""
    for (x, y, z), color in source.items():
        rx, ry, rz = int(x), int(y), int(z)
        if x_rotation:
            rx, ry, rz = _rotate_x_local(rx, ry, rz, x_rotation, scale)
        if y_rotation:
            rx, ry, rz = _rotate_y_local(rx, ry, rz, y_rotation, scale)
        if z_rotation:
            rx, ry, rz = _rotate_z_local(rx, ry, rz, z_rotation, scale)
        target[(rx, ry, rz)] = color


def _merge_local_voxels(target: dict, source: dict, y_rotation: int = 0):
    merge_local_voxels_rotated(target, source, y_rotation=y_rotation)


def voxelize_block_local(
    block_name: str,
    assets_dir,
    mc_block: dict | None = None,
    block_at=None,
) -> dict:
    """Return dict of local (x, y, z) -> rgba for a block's 16³ cell."""
    from dynamic_model_loader import load_block_geometry

    try:
        return load_block_geometry(
            block_name, assets_dir, mc_block=mc_block, block_at=block_at
        )
    except Exception:
        return {}


def solid_cube_local(block_name: str, assets_dir) -> dict:
    color_hex = _sample_block_texture_color(block_name, assets_dir) or "808080"
    rgba = (
        int(color_hex[0:2], 16),
        int(color_hex[2:4], 16),
        int(color_hex[4:6], 16),
        255,
    )
    return {
        (x, y, z): rgba
        for x in range(VOXEL_SCALE)
        for y in range(VOXEL_SCALE)
        for z in range(VOXEL_SCALE)
    }


def opaque_cell_voxels(
    block_name: str,
    assets_dir,
    mc_block: dict | None = None,
    block_at=None,
) -> dict:
    """
    Per-voxel colors for an opaque MC block cell.
    Sparse / blockstate-driven blocks keep model geometry only; full cubes fill to 16³.
    """
    from blockstate_resolver import has_blockstate_definition

    local = voxelize_block_local(block_name, assets_dir, mc_block=mc_block, block_at=block_at)
    sparse = is_sparse_shape_block(block_name)
    has_bs = has_blockstate_definition(block_name, assets_dir)
    partial_model = 0 < len(local) < VOXEL_SCALE ** 3

    if not local:
        if sparse or has_bs:
            return {}
        local = solid_cube_local(block_name, assets_dir)

    if sparse or (has_bs and partial_model):
        return local

    if len(local) >= VOXEL_SCALE ** 3:
        return local

    samples = list(local.values())
    if samples and isinstance(samples[0], tuple):
        fill = samples[len(samples) // 2]
    else:
        fill_hex = _sample_block_texture_color(block_name, assets_dir) or "808080"
        fill = (
            int(fill_hex[0:2], 16),
            int(fill_hex[2:4], 16),
            int(fill_hex[4:6], 16),
            255,
        )
    for x in range(VOXEL_SCALE):
        for y in range(VOXEL_SCALE):
            for z in range(VOXEL_SCALE):
                local.setdefault((x, y, z), fill)

    return local


def block_appearance(
    block_name: str,
    assets_dir,
    local_voxels=None,
    mc_block: dict | None = None,
    block_at=None,
) -> dict:
    """Shape id + representative color + whether textures were resolved."""
    local = local_voxels
    if local is None:
        local = opaque_cell_voxels(
            block_name, assets_dir, mc_block=mc_block, block_at=block_at
        )
    colors = []
    for color in local.values():
        if isinstance(color, tuple):
            colors.append(rgba_to_hex(color))
        elif isinstance(color, str):
            colors.append(color.upper())
    sample = _sample_block_texture_color(block_name, assets_dir)
    found = sample is not None and sample != "808080"
    return {
        "color": colors[len(colors) // 2] if colors else (sample or "808080"),
        "shapeId": get_shape_id_for_block(block_name),
        "found": found,
        "local_voxels": local,
    }
