"""User-tunable conversion settings shared across the pipeline.

The GUI (and CLI flags) write to ``CURRENT``; pipeline modules read from it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Biome presets: grass / foliage / water tint colors
BIOME_PRESETS = {
    "Plains": ((0x91, 0xBD, 0x59), (0x77, 0xAB, 0x2F), (0x3F, 0x76, 0xE4)),
    "Forest": ((0x79, 0xC0, 0x5A), (0x59, 0xAE, 0x30), (0x3F, 0x76, 0xE4)),
    "Birch Forest": ((0x88, 0xBB, 0x67), (0x6B, 0xA9, 0x41), (0x3F, 0x76, 0xE4)),
    "Dark Forest": ((0x50, 0x7A, 0x32), (0x59, 0xAE, 0x30), (0x3F, 0x76, 0xE4)),
    "Jungle": ((0x59, 0xC9, 0x3C), (0x30, 0xBB, 0x0B), (0x3F, 0x76, 0xE4)),
    "Swamp": ((0x6A, 0x70, 0x39), (0x6A, 0x70, 0x39), (0x61, 0x7B, 0x64)),
    "Savanna": ((0xBF, 0xB7, 0x55), (0xAE, 0xA4, 0x2A), (0x3F, 0x76, 0xE4)),
    "Taiga": ((0x86, 0xB7, 0x83), (0x68, 0xA4, 0x64), (0x3F, 0x76, 0xE4)),
    "Snowy": ((0x80, 0xB4, 0x97), (0x60, 0xA1, 0x7B), (0x39, 0x38, 0xC9)),
    "Badlands": ((0x90, 0x81, 0x4D), (0x9E, 0x81, 0x4D), (0x3F, 0x76, 0xE4)),
    "Cherry Grove": ((0xB6, 0xDB, 0x61), (0xB6, 0xDB, 0x61), (0x5D, 0xB7, 0xEF)),
    "Mushroom Fields": ((0x55, 0xC9, 0x3F), (0x2B, 0xBB, 0x0F), (0x3F, 0x76, 0xE4)),
}

WATER_MODES = ("glass", "solid", "skip")
COLOR_DETAIL_STEPS = {"High": 4, "Normal": 8, "Low": 16}

# Part type used for weld connectors / anchor pole
CONNECTOR_MATERIALS = {
    "Indestructible glass": "17baf3ba-0b40-4eef-9823-119059d5c12d",  # challenge glass
    "Glass": "b5ee5539-75a2-4fef-873b-ef7c9398b3f5",  # armored glass (paintable)
}


@dataclass
class ConversionSettings:
    # Appearance
    biome: str = "Plains"
    color_detail: str = "Normal"  # quantization step for mesh merging

    # Water / lava
    water_mode: str = "glass"  # glass | solid | skip

    # Structure
    wall_thickness: int = 2  # voxel layers kept when hollowing (1 = thin shell)
    hollow: bool = True
    merge: bool = True
    connect_islands: bool = True

    # Lights
    lights_enabled: bool = True
    light_mode: str = "embed"  # embed (glitchweld inside voxel) | replace (cutout)
    lamps_per_face: int = 1  # lamps per face (6 faces, symmetric from center)
    lamp_luminance: int = 50  # 0-100

    # Anchor pole: glass pole below the structure down to the ground/platform
    anchor_pole: bool = True
    anchor_pole_height: int = 32  # voxels

    # Weld connectors / anchor pole part type
    connector_material: str = "Indestructible glass"

    # Extras
    include_entities: bool = True  # paintings etc.
    # OFF by default: startCreations spawn as LOOSE physics creations at the
    # spawn platform (this caused ~50 colliding blocks under the platform).
    include_prefabs: bool = False

    # Limits
    max_parts: int = 320000

    def quantize_step(self) -> int:
        return COLOR_DETAIL_STEPS.get(self.color_detail, 8)

    def connector_shape_id(self) -> str:
        from config import CONNECTOR_SHAPE_ID

        return CONNECTOR_MATERIALS.get(self.connector_material, CONNECTOR_SHAPE_ID)

    def biome_tints(self):
        return BIOME_PRESETS.get(self.biome, BIOME_PRESETS["Plains"])


CURRENT = ConversionSettings()


def apply(settings: ConversionSettings):
    """Install settings globally and sync dependent modules."""
    global CURRENT
    CURRENT = settings

    import block_tints

    grass, foliage, water = settings.biome_tints()
    block_tints.set_biome_tints(grass, foliage, water)
