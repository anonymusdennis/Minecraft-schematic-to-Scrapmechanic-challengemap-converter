"""Performance validation against reference Scrap Mechanic challenge maps."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from config import (
    FAIL_TOTAL_PARTS,
    MAX_CHUNK_FILE_MB,
    MAX_PARTS_PER_CHUNK,
    MAX_SINGLE_FILE_MB,
    SM_REFERENCE_PRIVATE_DIR,
    SM_REFERENCE_WORKSHOP_DIR,
    WARN_TOTAL_PARTS,
)


@dataclass
class ChunkStats:
    index: int
    part_count: int
    estimated_mb: float


@dataclass
class ValidationResult:
    passed: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    chunks: List[ChunkStats] = field(default_factory=list)
    total_parts: int = 0
    reference_summary: Optional[str] = None


def _count_parts_in_blueprint(blueprint: dict) -> int:
    return sum(len(body.get("childs", [])) for body in blueprint.get("bodies", []))


def _estimate_json_mb(blueprint: dict) -> float:
    return len(json.dumps(blueprint, separators=(",", ":"))) / (1024 * 1024)


def _scan_reference_maps(*search_dirs: Path):
    """Collect part-count stats from reference challenge maps."""
    stats = []
    for base_dir in search_dirs:
        if not base_dir.is_dir():
            continue
        for blueprint_path in base_dir.glob("**/LevelCreation_*.blueprint"):
            try:
                with open(blueprint_path) as f:
                    data = json.load(f)
                count = _count_parts_in_blueprint(data)
                size_mb = blueprint_path.stat().st_size / (1024 * 1024)
                stats.append((count, size_mb))
            except (json.JSONDecodeError, OSError):
                continue
    return stats


def load_reference_summary() -> str:
    private = _scan_reference_maps(SM_REFERENCE_PRIVATE_DIR)
    workshop = _scan_reference_maps(SM_REFERENCE_WORKSHOP_DIR)
    all_stats = private + workshop
    if not all_stats:
        return "No reference maps found for benchmarking."

    counts = sorted(c for c, _ in all_stats)
    sizes = sorted(s for _, s in all_stats)
    p50 = counts[len(counts) // 2]
    p95 = counts[int(len(counts) * 0.95)] if len(counts) > 1 else counts[0]
    max_count = max(counts)
    max_size = max(sizes)
    return (
        f"Reference maps: {len(all_stats)} LevelCreation files | "
        f"parts p50={p50} p95={p95} max={max_count} | "
        f"max chunk size={max_size:.2f} MB"
    )


def validate_chunks(
    chunk_blueprints: List[dict],
    schematic_bounds: Optional[dict] = None,
) -> ValidationResult:
    """Validate blueprint chunks before challenge export."""
    result = ValidationResult()
    result.reference_summary = load_reference_summary()

    if not chunk_blueprints:
        result.passed = False
        result.errors.append("No blueprint chunks to export.")
        return result

    single_file = len(chunk_blueprints) == 1

    for i, blueprint in enumerate(chunk_blueprints, start=1):
        part_count = _count_parts_in_blueprint(blueprint)
        estimated_mb = _estimate_json_mb(blueprint)
        result.chunks.append(
            ChunkStats(index=i, part_count=part_count, estimated_mb=estimated_mb)
        )
        result.total_parts += part_count

        if part_count == 0:
            result.passed = False
            result.errors.append(f"LevelCreation_{i}: empty chunk (0 parts).")
        if not single_file and part_count > MAX_PARTS_PER_CHUNK:
            result.passed = False
            result.errors.append(
                f"LevelCreation_{i}: {part_count} parts exceeds limit of {MAX_PARTS_PER_CHUNK}."
            )
        body_count = len(blueprint.get("bodies", []))
        joint_count = len(blueprint.get("joints", []))
        if body_count > 1 and joint_count == 0:
            result.warnings.append(
                f"LevelCreation_{i}: {body_count} physics bodies with no bearing joints "
                f"({part_count} parts) — parts may collide separately in-game."
            )
        if single_file:
            if estimated_mb > MAX_SINGLE_FILE_MB:
                result.passed = False
                result.errors.append(
                    f"LevelCreation_{i}: {estimated_mb:.2f} MB exceeds single-file limit "
                    f"of {MAX_SINGLE_FILE_MB} MB."
                )
            elif estimated_mb > MAX_CHUNK_FILE_MB:
                result.warnings.append(
                    f"LevelCreation_{i}: {estimated_mb:.2f} MB single-file export "
                    f"(recommended under {MAX_CHUNK_FILE_MB} MB for small maps)."
                )
        elif estimated_mb > MAX_CHUNK_FILE_MB:
            result.passed = False
            result.errors.append(
                f"LevelCreation_{i}: {estimated_mb:.2f} MB exceeds limit of {MAX_CHUNK_FILE_MB} MB."
            )

    if single_file and result.chunks:
        chunk = result.chunks[0]
        if chunk.part_count > WARN_TOTAL_PARTS:
            result.warnings.append(
                f"Single structure: {chunk.part_count} weld-welded parts "
                f"(large build — may affect load time)."
            )

    from conversion_settings import CURRENT as settings

    fail_total = settings.max_parts or FAIL_TOTAL_PARTS
    if result.total_parts > fail_total:
        result.passed = False
        result.errors.append(
            f"Total parts {result.total_parts} exceeds hard limit of {fail_total}."
        )
    if result.total_parts > WARN_TOTAL_PARTS:
        result.warnings.append(
            f"Total parts {result.total_parts} is high (recommended under {WARN_TOTAL_PARTS} "
            f"for best in-game performance)."
        )

    if schematic_bounds:
        margin = 16
        for i, blueprint in enumerate(chunk_blueprints, start=1):
            for body in blueprint.get("bodies", []):
                for part in body.get("childs", []):
                    pos = part["pos"]
                    bounds = part.get("bounds", {"x": 1, "y": 1, "z": 1})
                    max_x = pos["x"] + bounds.get("x", 1)
                    max_y = pos["y"] + bounds.get("y", 1)
                    max_z = pos["z"] + bounds.get("z", 1)
                    if (
                        pos["x"] < schematic_bounds["min_x"] - margin
                        or pos["y"] < schematic_bounds["min_y"] - margin
                        or pos["z"] < schematic_bounds["min_z"] - margin
                        or max_x > schematic_bounds["max_x"] + margin
                        or max_y > schematic_bounds["max_y"] + margin
                        or max_z > schematic_bounds["max_z"] + margin
                    ):
                        result.warnings.append(
                            f"LevelCreation_{i}: part at ({pos['x']}, {pos['y']}, {pos['z']}) "
                            "extends outside schematic bounds."
                        )
                        break

    return result


def print_validation_report(result: ValidationResult):
    print("\n" + "=" * 60)
    print("Performance Validation Report")
    print("=" * 60)
    if result.reference_summary:
        print(f"  {result.reference_summary}")
    print(f"\n  Total parts: {result.total_parts}")
    print(f"  Chunks: {len(result.chunks)}")
    for chunk in result.chunks:
        print(
            f"    LevelCreation_{chunk.index}: {chunk.part_count} parts, "
            f"~{chunk.estimated_mb:.2f} MB"
        )
    if result.warnings:
        print("\n  Warnings:")
        for w in result.warnings:
            print(f"    - {w}")
    if result.errors:
        print("\n  Errors:")
        for e in result.errors:
            print(f"    - {e}")
    status = "PASSED" if result.passed else "FAILED"
    print(f"\n  Result: {status}")
    print("=" * 60 + "\n")
