"""Project configuration with environment variable overrides."""

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller binary: keep data (vanilla_assets, resourcepacks, .cache)
    # next to the executable, not in the temp extraction dir.
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent

_DEFAULT_CHALLENGES = (
    Path.home()
    / ".local/share/Steam/steamapps/compatdata/387990/pfx/drive_c/users/steamuser"
    / "AppData/Roaming/Axolot Games/Scrap Mechanic"
    / "User/User_76561198429631328/Challenges"
)

_DEFAULT_WORKSHOP = (
    Path.home() / ".local/share/Steam/steamapps/workshop/content/387990"
)

SM_CHALLENGES_DIR = Path(os.environ.get("SM_CHALLENGES_DIR", _DEFAULT_CHALLENGES))
SM_REFERENCE_PRIVATE_DIR = Path(
    os.environ.get("SM_REFERENCE_PRIVATE_DIR", _DEFAULT_CHALLENGES)
)
SM_REFERENCE_WORKSHOP_DIR = Path(
    os.environ.get("SM_REFERENCE_WORKSHOP_DIR", _DEFAULT_WORKSHOP)
)
SM_ASSETS_DIR = Path(os.environ.get("SM_ASSETS_DIR", PROJECT_ROOT / "MyResourcePack/assets"))

_DEFAULT_SCHEMATIC = (
    Path.home()
    / ".local/share/PrismLauncher/instances/1.21.10(1)/.minecraft/config/worldedit/schematics/newhouse.schem"
)
DEFAULT_SCHEMATIC_PATH = Path(os.environ.get("MC_SCHEMATIC_PATH", _DEFAULT_SCHEMATIC))

MAX_PARTS_PER_CHUNK = int(os.environ.get("MAX_PARTS_PER_CHUNK", "12000"))
MAX_CHUNK_FILE_MB = float(os.environ.get("MAX_CHUNK_FILE_MB", "4.0"))
# Single-file challenge exports (one LevelCreation, one weld-welded body)
MAX_SINGLE_FILE_MB = float(os.environ.get("MAX_SINGLE_FILE_MB", "64.0"))
SINGLE_LEVEL_CREATION = os.environ.get("SINGLE_LEVEL_CREATION", "1").lower() in (
    "1", "true", "yes",
)
WARN_TOTAL_PARTS = int(os.environ.get("WARN_TOTAL_PARTS", "25000"))
# Large schematic imports can legitimately exceed small-map budgets.
# Reference workshop maps reach ~321k parts; stay below that by default.
FAIL_TOTAL_PARTS = int(os.environ.get("FAIL_TOTAL_PARTS", "320000"))

VOXEL_SCALE = 16
DEFAULT_SHAPE_ID = "628b2d61-5ceb-43e9-8334-a4135566df7a"

# Indestructible challenge glass — connector bridges blend in and cannot break
CHALLENGE_GLASS_SHAPE_ID = "17baf3ba-0b40-4eef-9823-119059d5c12d"
CONNECTOR_COLOR = os.environ.get("CONNECTOR_COLOR", "FFFFFF")
CONNECTOR_SHAPE_ID = os.environ.get("CONNECTOR_SHAPE_ID", CHALLENGE_GLASS_SHAPE_ID)

# Parts per physics body inside a LevelCreation blueprint.
# 0 = one weld-welded body for the entire export (default).
_parts_per_body_env = os.environ.get("PARTS_PER_BODY", "")
PARTS_PER_BODY = int(_parts_per_body_env) if _parts_per_body_env else 0

# Bearing joints (4a1b886b…) connect separate bodies — only needed when PARTS_PER_BODY < chunk size.
# Off by default; static builds should use one weld-welded body instead.
WELD_BODIES = os.environ.get("WELD_BODIES", "0").lower() in ("1", "true", "yes")
BEARING_JOINT_SHAPE_ID = os.environ.get(
    "BEARING_JOINT_SHAPE_ID",
    os.environ.get("WELD_JOINT_SHAPE_ID", "4a1b886b-913e-4aad-b5b6-6e41b0db23a6"),
)
WELD_JOINT_SHAPE_ID = BEARING_JOINT_SHAPE_ID  # backwards compatibility
