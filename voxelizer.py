# voxelizer.py
import math
from collections import Counter, deque

# Sentinel for voxels with no sampled face color (interior / missing texture)
_FALLBACK = (128, 128, 128, 255)

from block_tints import apply_tint
from texture_loader import load_texture, sample_texture


def _axis_cells(start, end, N):
    """Cells along one axis covered by >= half a voxel; symmetric at boundaries."""
    lo, hi = (start, end) if start <= end else (end, start)
    cells = []
    for i in range(max(0, math.floor(lo)), min(N, math.ceil(hi))):
        overlap = min(hi, i + 1) - max(lo, i)
        # Strictly more than half a voxel: exactly-half boundary cells are
        # dropped on BOTH sides so off-grid elements stay symmetric, and
        # sub-half detail layers (0.5-thick pack bumps) vanish instead of
        # inflating to a full voxel (slabs must stay 8 voxels tall).
        if overlap > 0.5 + 1e-9:
            cells.append(i)
    if not cells:
        extent = hi - lo
        is_half = 0.5 - 1e-6 <= extent <= 0.5 + 1e-6
        on_boundary = abs(lo - round(lo)) < 1e-6 or abs(hi - round(hi)) < 1e-6
        if is_half and on_boundary:
            # Exactly 0.5-thick layer sitting on a voxel boundary: a pack
            # surface-detail bump (e.g. on slab tops) — drop it so slabs
            # stay 8 voxels tall.
            return cells
        # Otherwise extrude to the midpoint voxel so flat planes (cross
        # plants, vines) and boundary-straddling elements (ladder rungs at
        # 14.5-15.5, bar posts at 7.75-8.25) don't vanish.
        mid = (lo + hi) / 2
        if 0 <= mid < N:
            cells = [min(N - 1, int(mid))]
    return cells


def _is_fire_billboard(elem) -> bool:
    """True when every textured face of the element is a fire/flame texture."""
    import os

    found = False
    for face_data in elem.get("faces", {}).values():
        tex = face_data.get("texture_file") or face_data.get("texture") or ""
        base = os.path.basename(str(tex)).lower()
        if not base:
            continue
        stem = base.rsplit(".", 1)[0]
        # campfire_fire / soul_campfire_fire / fire_0 / fire_1 / flame — but
        # NOT campfire_log ("fire" substring) or campfire_log_lit.
        is_fire = (
            stem == "fire"
            or stem.endswith("_fire")
            or stem.startswith("fire_")
            or "flame" in stem
        )
        if not is_fire:
            return False
        found = True
    return found


def voxelize_model(resolved_elements, texture_cache, tint=None):
    """
    Voxelize the given model elements onto the fixed 16³ block grid.
    Model coordinates are always 0-16 regardless of texture resolution;
    higher-resolution pack textures are simply sampled at the UV point.
    :param resolved_elements: List of model elements (from resolve_model) with 'from', 'to', 'faces'.
    :param texture_cache: A dict to store loaded textures (to avoid reloading).
    :param tint: Optional (r, g, b) biome tint for faces with a tintindex.
    :return: A dict mapping voxel (x,y,z) -> RGBA color.
    """
    N = 16
    # Pre-load face textures and mark missing ones as invalid
    for elem in resolved_elements:
        for face, face_data in elem["faces"].items():
            tex_file = face_data.get("texture_file")
            if tex_file is None:
                continue  # Skip faces with missing textures
            img = load_texture(tex_file)
            if img is None:
                face_data["texture_file"] = None

    # Drop fire/flame billboard elements (campfire fire X-planes, soul fire):
    # they voxelize into ugly walls. Lit blocks get real lamps instead.
    resolved_elements = [e for e in resolved_elements if not _is_fire_billboard(e)]
    # 3D grid to mark filled voxels
    filled = [[[False for _ in range(N)] for _ in range(N)] for _ in range(N)]
    # Which element "owns" each voxel for face sampling. Smaller (detail)
    # elements win over big body elements so carved fronts keep their art.
    owner = {}

    def _claim(pos, vol, elem):
        prev = owner.get(pos)
        if prev is None or vol < prev[0]:
            owner[pos] = (vol, elem)

    # Fill grid for each element
    for elem in resolved_elements:
        # Pre-calc element bounds in voxel indices
        fx, fy, fz = elem["from"]; tx, ty, tz = elem["to"]
        elem_vol = abs((tx - fx) * (ty - fy) * (tz - fz)) or 1e9
        # Skip micro-detail elements smaller than a voxel in every axis
        # (decorative bolts/knobs) — they'd inflate into ugly 1-voxel warts.
        if abs(tx - fx) < 1.0 and abs(ty - fy) < 1.0 and abs(tz - fz) < 1.0:
            continue
        # If element has rotation, we'll need to test each voxel in its AABB
        rotated = False
        rot_origin = None
        rot_axis = None
        rot_angle = None
        sin_a = cos_a = 0
        if "rotation" in elem:
            rot = elem["rotation"]
            rot_origin = tuple(rot.get("origin", (0,0,0)))
            rot_axis = rot.get("axis", None)  # 'x','y', or 'z'
            rot_angle = rot.get("angle", 0)
            if rot_axis and rot_angle and abs(rot_angle) > 1e-6:
                rotated = True
                # Convert angle to radians
                theta = math.radians(rot_angle)
                sin_a = math.sin(theta); cos_a = math.cos(theta)
        # Determine voxel index range to consider for this element
        if rotated:
            # Rotate the 8 corners forward to get the true world AABB
            ox, oy, oz = rot_origin
            wxs, wys, wzs = [], [], []
            for cx in (fx, tx):
                for cy in (fy, ty):
                    for cz in (fz, tz):
                        px, py, pz = cx - ox, cy - oy, cz - oz
                        # Use both rotation signs — over-scanning is harmless
                        for s in (1, -1):
                            sa = sin_a * s
                            if rot_axis == 'x':
                                rx, ry, rz = px, py * cos_a - pz * sa, py * sa + pz * cos_a
                            elif rot_axis == 'y':
                                rx, ry, rz = px * cos_a - pz * sa, py, px * sa + pz * cos_a
                            else:
                                rx, ry, rz = px * cos_a + py * sa, -px * sa + py * cos_a, pz
                            wxs.append(rx + ox); wys.append(ry + oy); wzs.append(rz + oz)
            min_x = max(0, math.floor(min(wxs) - 0.5))
            max_x = min(N, math.ceil(max(wxs) + 0.5))
            min_y = max(0, math.floor(min(wys) - 0.5))
            max_y = min(N, math.ceil(max(wys) + 0.5))
            min_z = max(0, math.floor(min(wzs) - 0.5))
            max_z = min(N, math.ceil(max(wzs) + 0.5))
        else:
            min_x = max(0, math.floor(min(fx, tx)))
            max_x = min(N, math.ceil(max(fx, tx)))
            min_y = max(0, math.floor(min(fy, ty)))
            max_y = min(N, math.ceil(max(fy, ty)))
            min_z = max(0, math.floor(min(fz, tz)))
            max_z = min(N, math.ceil(max(fz, tz)))
        if not rotated:
            # Symmetric fill: a voxel is filled when the element covers at
            # least half of it (ties included on BOTH sides). The previous
            # half-open center test biased off-grid elements toward -X/-Y/-Z.
            xs = _axis_cells(fx, tx, N)
            ys = _axis_cells(fy, ty, N)
            zs = _axis_cells(fz, tz, N)
            for i in xs:
                for j in ys:
                    for k in zs:
                        filled[i][j][k] = True
                        _claim((i, j, k), elem_vol, elem)
            continue
        for i in range(min_x, max_x):
            for j in range(min_y, max_y):
                for k in range(min_z, max_z):
                    if rotated:
                        # Transform voxel center back to element's local coordinates (subtract origin, inverse rotate, add origin back)
                        # Voxel center in world coords:
                        wx = i + 0.5; wy = j + 0.5; wz = k + 0.5
                        ox, oy, oz = rot_origin
                        # translate to origin
                        tx_ = wx - ox; ty_ = wy - oy; tz_ = wz - oz
                        if rot_axis == 'x':
                            # rotate around X-axis
                            x_ = tx_
                            y_ = ty_ * cos_a + tz_ * sin_a
                            z_ = -ty_ * sin_a + tz_ * cos_a
                        elif rot_axis == 'y':
                            x_ = tx_ * cos_a + tz_ * sin_a
                            y_ = ty_
                            z_ = -tx_ * sin_a + tz_ * cos_a
                        elif rot_axis == 'z':
                            x_ = tx_ * cos_a - ty_ * sin_a
                            y_ = tx_ * sin_a + ty_ * cos_a
                            z_ = tz_
                        # translate back from origin
                        x_local = x_ + ox; y_local = y_ + oy; z_local = z_ + oz
                        # Pad flat axes to a half voxel each side so rotated
                        # planes (45-degree cross plants) still fill voxels
                        efx, etx = (fx, tx) if tx - fx >= 0.5 else (fx - 0.5, tx + 0.5)
                        efy, ety = (fy, ty) if ty - fy >= 0.5 else (fy - 0.5, ty + 0.5)
                        efz, etz = (fz, tz) if tz - fz >= 0.5 else (fz - 0.5, tz + 0.5)
                        if x_local < efx or x_local >= etx or \
                           y_local < efy or y_local >= ety or \
                           z_local < efz or z_local >= etz:
                            continue  # this voxel center is outside the element
                        filled[i][j][k] = True
                        _claim((i, j, k), elem_vol, elem)
                    else:
                        # Axis-aligned element
                        if i + 0.5 < fx or i + 0.5 >= tx: 
                            continue
                        if j + 0.5 < fy or j + 0.5 >= ty: 
                            continue
                        if k + 0.5 < fz or k + 0.5 >= tz: 
                            continue
                        filled[i][j][k] = True
                        _claim((i, j, k), elem_vol, elem)
    
    # Note: Individual block blueprints are now generated as solid (not hollowed)
    # This allows proper assembly where adjacent blocks can merge and then be 
    # hollowed out as a complete structure in the schematic assembler
    # Determine voxel colors
    voxel_colors = {}
    for i in range(0, N):
        for j in range(0, N):
            for k in range(0, N):
                if not filled[i][j][k]:
                    continue
                # Determine the color of this voxel
                color = None
                # Priority: up face color > side face > down face
                face_order = ["up","north","south","east","west","down"]
                for face in face_order:
                    # Check if this face of voxel is exposed
                    di, dj, dk = 0,0,0
                    if face == "up":    dj = 1
                    if face == "down":  dj = -1
                    if face == "north": dk = -1
                    if face == "south": dk = 1
                    if face == "west":  di = -1
                    if face == "east":  di = 1
                    neighbor = (i+di, j+dj, k+dk)
                    if 0 <= neighbor[0] < N and 0 <= neighbor[1] < N and 0 <= neighbor[2] < N:
                        if filled[neighbor[0]][neighbor[1]][neighbor[2]]:
                            continue  # neighbor filled, not an exposed face
                    # Now find which element's face covers this voxel on the given side.
                    # The element that FILLED this voxel is tried first so surface
                    # voxels sample their own element's texture, not whatever
                    # nearby element happens to come first in the model.
                    face_data = None  # Initialize before loop
                    elem_bounds = None  # Store element bounds for UV calculation
                    own = owner.get((i, j, k))
                    candidates = resolved_elements
                    if own is not None:
                        candidates = [own[1]] + [e for e in resolved_elements if e is not own[1]]
                    for elem in candidates:
                        fx, fy, fz = elem["from"]; tx, ty, tz = elem["to"]
                        voxel_center_x, voxel_center_y, voxel_center_z = i + 0.5, j + 0.5, k + 0.5

                        # Half-voxel margin: boundary voxels filled by the
                        # symmetric >=50% rule have centers slightly outside.
                        m = 0.5
                        if not (
                            fx - m <= voxel_center_x <= tx + m
                            and fy - m <= voxel_center_y <= ty + m
                            and fz - m <= voxel_center_z <= tz + m
                        ):
                            continue
                            
                        # Face-plane proximity: the plane may sit up to one voxel
                        # OUTSIDE the voxel on the exposed side ("negative inset"
                        # skins, e.g. a front face at z=0.5 outside the body) but
                        # only slightly inside (-0.6) on the other side.
                        def _near(dist_outward):
                            return -0.6 < dist_outward < 1.1

                        if face == "up":
                            if _near(ty - voxel_center_y):
                                if fx - m <= voxel_center_x <= tx + m and fz - m <= voxel_center_z <= tz + m:
                                    face_data = elem["faces"].get("up")
                                    if face_data:
                                        elem_bounds = (fx, fy, fz, tx, ty, tz)
                                        break
                        elif face == "down":
                            if _near(voxel_center_y - fy):
                                if fx - m <= voxel_center_x <= tx + m and fz - m <= voxel_center_z <= tz + m:
                                    face_data = elem["faces"].get("down")
                                    if face_data:
                                        elem_bounds = (fx, fy, fz, tx, ty, tz)
                                        break
                        elif face == "north":
                            if _near(voxel_center_z - fz):
                                if fx - m <= voxel_center_x <= tx + m and fy - m <= voxel_center_y <= ty + m:
                                    face_data = elem["faces"].get("north")
                                    if face_data:
                                        elem_bounds = (fx, fy, fz, tx, ty, tz)
                                        break
                        elif face == "south":
                            if _near(tz - voxel_center_z):
                                if fx - m <= voxel_center_x <= tx + m and fy - m <= voxel_center_y <= ty + m:
                                    face_data = elem["faces"].get("south")
                                    if face_data:
                                        elem_bounds = (fx, fy, fz, tx, ty, tz)
                                        break
                        elif face == "west":
                            if _near(voxel_center_x - fx):
                                if fz - m <= voxel_center_z <= tz + m and fy - m <= voxel_center_y <= ty + m:
                                    face_data = elem["faces"].get("west")
                                    if face_data:
                                        elem_bounds = (fx, fy, fz, tx, ty, tz)
                                        break
                        elif face == "east":
                            if _near(tx - voxel_center_x):
                                if fz - m <= voxel_center_z <= tz + m and fy - m <= voxel_center_y <= ty + m:
                                    face_data = elem["faces"].get("east")
                                    if face_data:
                                        elem_bounds = (fx, fy, fz, tx, ty, tz)
                                        break
                    
                    if face_data and elem_bounds:
                        fx, fy, fz, tx, ty, tz = elem_bounds
                        tex_file = face_data.get("texture_file")
                        if tex_file is None:
                            continue  # Skip faces with missing textures
                        img = load_texture(tex_file)
                        if img is None:
                            continue  # Skip if texture couldn't be loaded
                        # Determine UV of voxel center relative to that face
                        u1, v1, u2, v2 = face_data.get("uv", [0,0,16,16])
                        # Normalize UV coordinates (0-1)
                        # Note: u corresponds to horizontal axis of face texture, v to vertical axis.
                        if face in ("north","south","east","west"):
                            # Vertical faces: horizontal = x (or z for east/west), vertical = y
                            # For north/south: x-axis corresponds to u, y-axis corresponds to v (top is v=0).
                            # For east/west: z-axis corresponds to u (since east/west faces run north-south horizontally), y-axis to v.
                            if face == "north":
                                # North face: u goes from west to east (fx to tx)
                                u_frac = (i + 0.5 - fx) / (tx - fx) if tx != fx else 0
                            elif face == "south":
                                # South face: u goes from east to west (mirrored), so flip u
                                u_frac = 1.0 - ((i + 0.5 - fx) / (tx - fx) if tx != fx else 0)
                            elif face == "west":
                                # West face: u goes from north to south (fz to tz)
                                u_frac = (k + 0.5 - fz) / (tz - fz) if tz != fz else 0
                            else:  # east
                                # East face: u goes from south to north (mirrored), so flip u
                                u_frac = 1.0 - ((k + 0.5 - fz) / (tz - fz) if tz != fz else 0)
                            # vertical frac: top of block = v=0
                            v_frac = (ty - (j + 0.5)) / (ty - fy) if ty != fy else 0
                        else:
                            # Horizontal faces (up/down): horizontal = x, vertical = z (north-> top or bottom of texture)
                            u_frac = (i + 0.5 - fx) / (tx - fx) if tx != fx else 0
                            if face == "up":
                                # north side of face = v=0
                                v_frac = (k + 0.5 - fz) / (tz - fz) if tz != fz else 0
                            else:  # down face, likely rotated 180 by default
                                # for down, north edge corresponds to top of texture as well (assuming no rotation or handled via face rotation)
                                v_frac = (tz - (k + 0.5)) / (tz - fz) if tz != fz else 0
                        u_frac = min(1.0, max(0.0, u_frac))
                        v_frac = min(1.0, max(0.0, v_frac))
                        # Apply face-specific 90-degree rotation if any
                        rot = face_data.get("rotation", 0)
                        if rot == 90:
                            # 90 deg: swap axes, u becomes 1-v_orig, v becomes u_orig
                            orig_u = u_frac; orig_v = v_frac
                            u_frac = 1.0 - orig_v
                            v_frac = orig_u
                        elif rot == 180:
                            orig_u = u_frac; orig_v = v_frac
                            u_frac = 1.0 - orig_u
                            v_frac = 1.0 - orig_v
                        elif rot == 270:
                            orig_u = u_frac; orig_v = v_frac
                            u_frac = orig_v
                            v_frac = 1.0 - orig_u
                        # Now map into the face's UV rectangle:
                        u_norm = (u1 + u_frac * (u2 - u1)) / 16.0
                        v_norm = (v1 + v_frac * (v2 - v1)) / 16.0
                        # Sample the texture
                        sampled_color = sample_texture(img, (u_norm, v_norm))
                        if sampled_color is not None:
                            if tint is not None and "tintindex" in face_data:
                                sampled_color = apply_tint(sampled_color, tint)
                            color = sampled_color
                            break
                    if color is not None:  # if we found a face and got a valid color
                        break
                if color is None:
                    color = _FALLBACK  # resolved to the dominant color below
                voxel_colors[(i, j, k)] = color

    # Interior voxels (no exposed face) get the block's dominant sampled
    # color instead of neutral gray — fixes e.g. gray/"wooden" leaf cores.
    sampled = Counter(
        c for c in voxel_colors.values()
        if c is not _FALLBACK and (len(c) < 4 or c[3] > 0)
    )
    if sampled:
        dominant = sampled.most_common(1)[0][0]
        for pos, c in voxel_colors.items():
            if c is _FALLBACK:
                voxel_colors[pos] = dominant
    else:
        for pos in voxel_colors:
            voxel_colors[pos] = (128, 128, 128, 255)
    return voxel_colors
