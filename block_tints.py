"""Biome tint colors for tintindex faces (grass, foliage, water, ...).

Minecraft ships grayscale textures for tinted surfaces and multiplies them with
a biome color at render time. Without this, grass tops and leaves look white,
as if covered in snow. We use the plains-biome constants.
"""

GRASS_TINT = (0x91, 0xBD, 0x59)
FOLIAGE_TINT = (0x77, 0xAB, 0x2F)
BIRCH_TINT = (0x80, 0xA7, 0x55)
SPRUCE_TINT = (0x61, 0x99, 0x61)
WATER_TINT = (0x3F, 0x76, 0xE4)
LILY_PAD_TINT = (0x20, 0x80, 0x30)
DRY_FOLIAGE_TINT = (0xA0, 0x76, 0x4B)
STEM_TINT = (0x35, 0xC0, 0x35)


def set_biome_tints(grass, foliage, water):
    """Override grass/foliage/water tints (GUI biome setting)."""
    global GRASS_TINT, FOLIAGE_TINT, WATER_TINT
    GRASS_TINT = tuple(grass)
    FOLIAGE_TINT = tuple(foliage)
    WATER_TINT = tuple(water)

_GRASS_BLOCKS = frozenset({
    "grass_block", "grass", "short_grass", "tall_grass", "fern", "large_fern",
    "potted_fern", "sugar_cane", "bush",
})

_FOLIAGE_BLOCKS = frozenset({
    "oak_leaves", "jungle_leaves", "acacia_leaves", "dark_oak_leaves",
    "mangrove_leaves", "vine", "cave_vines", "cave_vines_plant",
})


def tint_for_block(block_name: str) -> tuple[int, int, int] | None:
    """Tint color (r, g, b) applied to faces with a tintindex, or None."""
    name = block_name.lower()
    if ":" in name:
        name = name.split(":", 1)[1]

    if name in _GRASS_BLOCKS:
        return GRASS_TINT
    if name in _FOLIAGE_BLOCKS:
        return FOLIAGE_TINT
    if name == "birch_leaves":
        return BIRCH_TINT
    if name == "spruce_leaves":
        return SPRUCE_TINT
    if name in ("water", "water_cauldron", "bubble_column"):
        return WATER_TINT
    if name == "lily_pad":
        return LILY_PAD_TINT
    if name in ("leaf_litter",):
        return DRY_FOLIAGE_TINT
    if name.endswith("_stem") and ("melon" in name or "pumpkin" in name):
        return STEM_TINT
    if name.endswith("_leaves"):
        # Azalea/cherry/pale oak leaves are pre-colored; default others to foliage
        if name in ("azalea_leaves", "flowering_azalea_leaves", "cherry_leaves",
                    "pale_oak_leaves"):
            return None
        return FOLIAGE_TINT
    return None


def apply_tint(color, tint) -> tuple:
    """Multiply an RGBA sample with a tint color."""
    if tint is None or color is None:
        return color
    r, g, b = color[0], color[1], color[2]
    a = color[3] if len(color) > 3 else 255
    return (
        r * tint[0] // 255,
        g * tint[1] // 255,
        b * tint[2] // 255,
        a,
    )
