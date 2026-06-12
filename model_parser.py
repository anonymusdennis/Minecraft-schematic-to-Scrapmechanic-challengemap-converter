# model_parser.py
import os

import json

from asset_resolution import find_model_file, find_texture_file

# Cache for loaded models to avoid re-parsing
_model_cache = {}


def load_model(model_path, base_dir):
    """
    Load and resolve a Minecraft model JSON (including parent inheritance).
    Searches the full resource pack stack (resourcepacks/ + vanilla fallback).
    :param model_path: Model path in 'namespace:path' format or relative path.
    :param base_dir: Primary assets directory (highest priority root).
    :return: Resolved model dictionary with 'elements' and 'textures'.
    """
    if ":" in model_path:
        namespace, path = model_path.split(":", 1)
    else:
        namespace, path = "minecraft", model_path

    model_file = find_model_file(path, base_dir, namespace=namespace)
    if model_file is None:
        raise FileNotFoundError(f"Model file not found: {namespace}:{path}")
    return _load_model_file(str(model_file), base_dir)


def _pack_root_of(model_file: str) -> str | None:
    """Asset root of the pack a model file came from (parent of 'minecraft')."""
    parts = os.path.normpath(model_file).split(os.sep)
    for i in range(len(parts) - 2, 0, -1):
        if parts[i] == "minecraft" and parts[i + 1] == "models":
            return os.sep.join(parts[:i])
    return None


def _load_model_file(model_file: str, base_dir):
    """Parse one model JSON file and merge its parent chain (by name)."""
    cache_key = (model_file, str(base_dir))
    if cache_key in _model_cache:
        return _model_cache[cache_key]
    with open(model_file, 'r') as f:
        data = json.load(f)
    model = {}
    # Resolve parent model first, if present
    if "parent" in data:
        parent_path = data["parent"]
        try:
            parent_model = load_model(parent_path, base_dir)
        except FileNotFoundError:
            # Some packs inline elements while referencing missing parents.
            parent_model = {"elements": [], "textures": {}}
        # Start with a copy of parent model's elements and textures
        model["elements"] = [elem.copy() for elem in parent_model.get("elements", [])]
        # Deep-copy faces sub-dicts to avoid reference issues
        for elem in model["elements"]:
            elem["faces"] = {face: face_data.copy() for face, face_data in elem.get("faces", {}).items()}
        model["textures"] = parent_model.get("textures", {}).copy()
    else:
        model["elements"] = []
        model["textures"] = {}
    # Override/extend textures with child's textures
    if "textures" in data:
        # In model JSON, values like "block/stone" mean namespace "minecraft" by default
        for key, tex in data["textures"].items():
            # Normalize keys: remove leading # if present (non-standard but some models use it)
            normalized_key = key[1:] if key.startswith("#") else key

            if tex.startswith("#"):
                # Texture variable reference - keep as-is, don't add namespace
                model["textures"][normalized_key] = tex
            elif ":" in tex:
                # Already has namespace
                model["textures"][normalized_key] = tex
            else:
                # No namespace, default to "minecraft"
                model["textures"][normalized_key] = "minecraft:" + tex
    # If the child defines elements, replace the inherited ones
    if "elements" in data:
        model["elements"] = data["elements"]
    # Textures referenced by this model should resolve from ITS pack first,
    # so a 3D model picked from a lower-priority pack keeps matching art.
    model["__pack_root__"] = _pack_root_of(model_file)
    # Store in cache
    _model_cache[cache_key] = model
    return model


def _occupancy_count(model) -> int:
    """
    Approximate voxel-occupancy (16³ grid) of the model's geometry using the
    same majority-coverage rules as the voxelizer. Rotated elements use their
    AABB. Cheap geometry-only pass — no textures.
    """
    from voxelizer import _axis_cells

    occupied = set()
    for elem in model.get("elements") or []:
        f, t = elem.get("from", (0, 0, 0)), elem.get("to", (0, 0, 0))
        # Same micro-detail skip as the voxelizer
        if all(abs(t[i] - f[i]) < 1.0 for i in range(3)):
            continue
        xs = _axis_cells(f[0], t[0], 16)
        ys = _axis_cells(f[1], t[1], 16)
        zs = _axis_cells(f[2], t[2], 16)
        for x in xs:
            for y in ys:
                for z in zs:
                    occupied.add((x, y, z))
        if len(occupied) >= 4096:
            break
    return len(occupied)


def _is_detailed_3d(model) -> bool:
    """
    True when the model shows VISIBLE 3D detail at voxel scale: it contains a
    real box element (>=1 voxel in every axis, so pure flat-quad models don't
    count) and its occupancy is carved (not a plain full 16³ cube — sub-voxel
    surface bumps flatten back into a cube and don't count either).
    """
    elements = model.get("elements") or []
    if not elements:
        return False
    has_box = False
    for elem in elements:
        f, t = elem.get("from", (0, 0, 0)), elem.get("to", (0, 0, 0))
        if min(abs(t[i] - f[i]) for i in range(3)) >= 1.0:
            has_box = True
            break
    if not has_box:
        return False
    return _occupancy_count(model) < 4096


def load_model_prefer_3d(model_path, base_dir):
    """
    Like load_model, but searches the WHOLE pack stack and returns the first
    candidate with detailed 3D geometry (3D packs lower in the stack beat a
    flat/plain-cube model from a higher-priority pack). Falls back to normal
    priority order when no candidate is detailed.
    """
    from asset_resolution import find_model_files_all

    if ":" in model_path:
        namespace, path = model_path.split(":", 1)
    else:
        namespace, path = "minecraft", model_path

    candidates = find_model_files_all(path, base_dir, namespace=namespace)
    if not candidates:
        raise FileNotFoundError(f"Model file not found: {namespace}:{path}")

    first = None
    loaded = []
    for model_file in candidates:
        try:
            model = _load_model_file(str(model_file), base_dir)
        except Exception:
            continue
        if first is None:
            first = model
        loaded.append(model)
    if first is None:
        raise FileNotFoundError(f"Model file not found: {namespace}:{path}")

    # Quality gate: when the block is a full cube somewhere in the stack, a
    # "detailed" candidate that voxelizes to under half a cube is a broken or
    # too-sparse remodel (e.g. a dispenser with only its face plate) — skip it.
    occs = [_occupancy_count(m) for m in loaded]
    max_occ = max(occs) if occs else 0
    min_occ = 2048 if max_occ >= 4096 else 0
    for model, occ in zip(loaded, occs):
        if occ >= min_occ and _is_detailed_3d(model):
            return model
    return first


def _auto_uv(face: str, elem_from, elem_to):
    """
    Minecraft default UV when a face omits "uv": the projection of the element
    bounds onto the face plane. Matches the voxelizer's u/v conventions
    (u ascending along +x / +z, v measured from the top).
    """
    x1, y1, z1 = elem_from
    x2, y2, z2 = elem_to
    if face in ("up", "down"):
        return [x1, z1, x2, z2]
    if face in ("north", "south"):
        return [x1, 16 - y2, x2, 16 - y1]
    # west / east
    return [z1, 16 - y2, z2, 16 - y1]


def resolve_model(model, base_dir):
    """
    Given a loaded model dict (with elements and texture variables),
    resolve texture variables to actual images (file paths).
    Returns a new dict with resolved 'elements'.
    """
    resolved_elements = []
    textures = model.get("textures", {})
    pack_root = model.get("__pack_root__")
    for elem in model.get("elements", []):
        # Copy element's basic properties
        res_elem = {
            "from": elem["from"][:],  # copy lists
            "to": elem["to"][:]
        }
        # Rotation (if any)
        if "rotation" in elem:
            res_elem["rotation"] = elem["rotation"].copy()
        if "shade" in elem:
            res_elem["shade"] = elem["shade"]
        res_faces = {}
        for face, face_data in elem.get("faces", {}).items():
            tex_var = face_data.get("texture")
            if tex_var is None:
                continue

            if tex_var.startswith("##"):
                tex_var = "#" + tex_var[2:]

            tex_key = tex_var[1:] if tex_var.startswith("#") else tex_var
            if tex_var.startswith("#") or tex_var in textures:
                if tex_var in textures:
                    tex_ref = textures[tex_var]
                elif tex_key in textures:
                    tex_ref = textures[tex_key]
                else:
                    if tex_key != "missing":
                        print(
                            f"Warning: texture variable '{tex_key}' not found in model textures, "
                            "trying as direct path"
                        )
                    tex_ref = tex_key
                depth = 0
                while tex_ref.startswith("#") and depth < 10:
                    inner_key = tex_ref[1:]
                    if inner_key in textures:
                        tex_ref = textures[inner_key]
                        depth += 1
                    else:
                        break
                if tex_ref.startswith("#"):
                    unresolved_key = tex_ref[1:]
                    if unresolved_key != "missing":
                        print(
                            f"Warning: texture variable '{unresolved_key}' not found in model textures, "
                            "trying as direct path"
                        )
                    tex_ref = unresolved_key
            else:
                tex_ref = tex_var
            # Determine texture file path
            if tex_ref.endswith(":"):
                tex_ref = tex_ref[:-1]
            if ":" in tex_ref:
                ns, tex_path = tex_ref.split(":", 1)
            else:
                ns, tex_path = "minecraft", tex_ref
            # Packs use "missing" as an intentional no-render face
            if tex_path == "missing":
                continue
            # If tex_path doesn't have a folder, assume it's under 'block/'
            if "/" not in tex_path:
                tex_path = f"block/{tex_path}"
            # Textures might omit the '.png' in JSON; we ensure it ends with .png
            if not tex_path.endswith(".png"):
                tex_path = f"{tex_path}.png"
            tex_file = None
            if pack_root:
                local = os.path.join(pack_root, ns, "textures", tex_path.replace("/", os.sep))
                if os.path.isfile(local):
                    tex_file = local
            if tex_file is None:
                found = find_texture_file(tex_path, base_dir, namespace=ns)
                if found is not None:
                    tex_file = str(found)
                else:
                    tex_file = os.path.join(
                        str(base_dir), ns, "textures", tex_path.replace("/", os.sep)
                    )
            res_face = {
                "texture_file": tex_file,
            }
            # UV mapping: explicit, or Minecraft's auto-UV from element bounds
            if "uv" in face_data:
                res_face["uv"] = face_data["uv"][:]
            else:
                res_face["uv"] = _auto_uv(face, elem["from"], elem["to"])
            # Texture rotation (if any, 0/90/180/270)
            if "rotation" in face_data:
                res_face["rotation"] = face_data["rotation"]
            if "tintindex" in face_data:
                res_face["tintindex"] = face_data["tintindex"]
            res_faces[face] = res_face
        res_elem["faces"] = res_faces
        resolved_elements.append(res_elem)
    return resolved_elements
