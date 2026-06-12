"""Minecraft block-local and world coordinate mapping for Scrap Mechanic."""

from config import VOXEL_SCALE


def model_voxel_to_local(x, y, z) -> tuple[int, int, int]:
    """Map a model-space voxel index to MC block-local coordinates (X, Y up, Z)."""
    return int(x), int(y), int(z)


def local_to_sm_world(mc_x, mc_y, mc_z, local_x, local_y, local_z, scale: int = VOXEL_SCALE):
    """Place MC block-local coordinates into SM world space (Y-up)."""
    return (
        mc_x * scale + local_x,
        mc_y * scale + local_y,
        mc_z * scale + local_z,
    )


def sm_world_to_mc_block(sm_x, sm_y, sm_z, scale: int = VOXEL_SCALE):
    """Inverse of block origin from an SM world position."""
    return sm_x // scale, sm_y // scale, sm_z // scale
