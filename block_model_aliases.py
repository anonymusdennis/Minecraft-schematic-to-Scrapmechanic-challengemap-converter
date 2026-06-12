"""Map schematic block names to Nautilus3D model files and texture fallbacks."""

# From generate_essential_blueprints.py — blocks without block/<name>.json
BLOCK_MODEL_ALIASES = {
    "fence": "oak_fence",
    "wooden_door": "oak_door",
    "bed": "red_bed",
    "snow": "snow_block",
    "bell": "bell_floor",
    "scaffolding": "scaffolding_stable",
    "iron_bars": "iron_bars_post",
    "glass": "glass",
    "torch": "torch",
    "redstone_torch": "redstone_torch",
    "ladder": "ladder",
    "tripwire_hook": "tripwire_hook",
    "waxed_copper_chest": "copper_chest",
    "waxed_exposed_copper_chest": "exposed_copper_chest",
    "waxed_weathered_copper_chest": "weathered_copper_chest",
    "waxed_oxidized_copper_chest": "oxidized_copper_chest",
    "waxed_lightning_rod": "lightning_rod",
    "waxed_exposed_lightning_rod": "lightning_rod",
    "waxed_weathered_lightning_rod": "lightning_rod",
    "waxed_oxidized_lightning_rod": "lightning_rod",
    "red_bed": "bed",
    "chest": "chest",
}

DOOR_MODEL_SUFFIX = "_bottom"
TRAPDOOR_MODEL_SUFFIX = "_bottom"

SPARSE_SHAPE_SUFFIXES = (
    "_trapdoor", "_door", "_fence_gate", "_button", "_pressure_plate",
    "_banner", "_sign", "_hanging_sign", "_shelf", "_bars", "_chain",
    "_lantern", "_rod", "_candle", "_carpet", "_rail", "_torch",
    "_wall_torch", "_redstone_torch", "_soul_torch", "_campfire",
    "_soul_campfire", "_flower_pot", "_lever", "_tripwire_hook",
    "_end_rod", "_lightning_rod", "_bell", "_anvil",
)

# Blocks that should keep sparse geometry (not fill full 16³ weld cube)
SPARSE_SHAPE_BLOCKS = frozenset({
    "chest", "trapped_chest", "ender_chest", "bed",
    "anvil", "chipped_anvil", "damaged_anvil",
    "oak_button", "stone_button", "lever", "ladder", "torch", "redstone_torch",
    "flower_pot", "bell", "bell_floor", "snow", "snow_block",
})

# Extra texture paths when model voxelization fails (Nautilus3D layout)
TEXTURE_PATH_OVERRIDES = {
    "chest": ("block/break/chest.png",),
    "trapped_chest": ("block/break/trapped_chest.png",),
    "ender_chest": ("block/break/ender_chest.png",),
    "copper_chest": ("block/copper_block.png", "block/break/chest.png"),
    "exposed_copper_chest": ("block/copper_block.png", "block/break/chest.png"),
    "weathered_copper_chest": ("block/copper_block.png", "block/break/chest.png"),
    "oxidized_copper_chest": ("block/copper_block.png", "block/break/chest.png"),
    "waxed_copper_chest": ("block/copper_block.png", "block/break/chest.png"),
    "red_bed": ("block/red_wool.png", "block/red_concrete.png"),
    "glass": ("block/glass.png", "block/white_stained_glass.png"),
    "snow": ("block/snow.png",),
    "scaffolding": (
        "block/scaffolding_top.png",
        "block/scaffolding_side.png",
        "block/scaffolding_bottom.png",
    ),
    "bell": ("block/bell_top.png", "block/bell_side.png", "block/bell_bottom.png"),
    "anvil": ("block/anvil_top.png", "block/anvil.png"),
    "spruce_door": (
        "block/spruce_door_bottom.png",
        "block/doors/spruce_door.png",
        "block/doors/spruce_door_bottom.png",
    ),
    "waxed_lightning_rod": ("block/lightning_rod.png",),
}


def is_sparse_shape_block(block_name: str) -> bool:
    name = block_name.lower()
    if name in SPARSE_SHAPE_BLOCKS:
        return True
    if name.endswith(SPARSE_SHAPE_SUFFIXES):
        return True
    if name.endswith("_bed"):
        return True
    if "chest" in name and not name.endswith("_chestplate"):
        return True
    if name.endswith("_anvil"):
        return True
    return False


def resolve_block_model_name(block_name: str) -> str:
    """Return the block model JSON name to load for a schematic block."""
    if block_name in BLOCK_MODEL_ALIASES:
        return BLOCK_MODEL_ALIASES[block_name]

    if block_name.endswith("_door"):
        return f"{block_name}{DOOR_MODEL_SUFFIX}"

    if block_name.endswith("_trapdoor"):
        return f"{block_name}{TRAPDOOR_MODEL_SUFFIX}"

    if block_name.endswith("_stained_glass_pane"):
        color = block_name.replace("_stained_glass_pane", "")
        return f"{color}_stained_glass_pane_post"

    if block_name.endswith("_fence"):
        wood = block_name.replace("_fence", "")
        if wood in ("nether_brick",):
            return block_name
        return f"{wood}_fence_post"

    return block_name


def texture_override_paths(block_name: str) -> tuple:
    """Known Nautilus3D texture paths for blocks that lack a simple block/<name>.png."""
    if block_name in TEXTURE_PATH_OVERRIDES:
        return TEXTURE_PATH_OVERRIDES[block_name]
    if block_name.endswith("_door"):
        wood = block_name.replace("_door", "")
        return (
            f"block/{wood}_door_bottom.png",
            f"block/doors/{wood}_door.png",
            f"block/doors/{wood}_door_bottom.png",
        )
    if block_name.endswith("_bed"):
        color = block_name.replace("_bed", "")
        return (f"block/{color}_wool.png", f"block/{color}_concrete.png")
    if block_name.endswith("_fence"):
        wood = block_name.replace("_fence", "")
        return (f"block/{wood}_planks.png",)
    return ()
