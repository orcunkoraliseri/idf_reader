from __future__ import annotations

"""
Visualizer Adapter for IDF Zone Metadata Extractor.

Renders building geometry directly from parsed IDF data using matplotlib,
without requiring eppy or an IDD file. This makes it compatible with all
EnergyPlus IDF versions.

Key behaviours:
  - Reads GlobalGeometryRules to detect Relative vs Absolute coordinate system.
  - Applies zone X/Y/Z origin offsets for all surface and fenestration vertices.
  - Draws opaque surfaces first, then windows in a separate pass so windows
    are never hidden behind walls by matplotlib's 3D painter algorithm.
  - Enforces a 1:1:1 aspect ratio per metre so floor heights look realistic.
"""

import base64
import io
import os
from typing import Optional

os.environ.setdefault("MPLBACKEND", "Agg")

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import numpy as np

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

# ── Surface colours (facecolor, alpha) ──────────────────────────────────────
_SURF_COLOR: dict[str, tuple[str, float]] = {
    "wall": ("#d4a574", 0.75),  # warm tan, slightly transparent
    "roof": ("#8b5e3c", 0.88),  # dark brown
    "ceiling": ("#8b5e3c", 0.88),
    "floor": ("#c0c0c0", 0.60),  # light grey, translucent
}
_DEFAULT_COLOR = ("#aaaaaa", 0.55)
_WIN_FACE = "#5dade2"  # clear blue
_WIN_EDGE = "#1a6fa8"
_WIN_ALPHA = 0.70


# ── Helpers ──────────────────────────────────────────────────────────────────


def _safe_float(val: str, default: float = 0.0) -> float:
    """Parse float from an IDF field string; return default on failure."""
    try:
        return float(val.strip()) if val and val.strip() else default
    except ValueError:
        return default


def _is_relative_coords(idf_data: dict) -> bool:
    """Return True when GlobalGeometryRules uses a Relative coordinate system.

    Args:
        idf_data: Parsed IDF dictionary.

    Returns:
        True if zone-origin offsets must be applied to surface vertices.
    """
    ggr_list = idf_data.get("GLOBALGEOMETRYRULES", [])
    if not ggr_list:
        return True  # EnergyPlus default is Relative
    ggr = ggr_list[0]
    # values[0]=StartingVertex, [1]=Direction, [2]=CoordinateSystem
    if len(ggr) >= 3:
        return ggr[2].strip().lower() != "absolute"
    return True


def _build_zone_origins(
    idf_data: dict,
) -> dict[str, tuple[float, float, float]]:
    """Build zone-name → (dx, dy, dz) origin lookup.

    Args:
        idf_data: Parsed IDF dictionary.

    Returns:
        Mapping of zone name string to world-space offset tuple.
    """
    origins: dict[str, tuple[float, float, float]] = {}
    for zone in idf_data.get("ZONE", []):
        if not zone:
            continue
        # values: 0=Name, 1=DirRelNorth, 2=X_Origin, 3=Y_Origin, 4=Z_Origin
        name = zone[0]
        dx = _safe_float(zone[2]) if len(zone) > 2 else 0.0
        dy = _safe_float(zone[3]) if len(zone) > 3 else 0.0
        dz = _safe_float(zone[4]) if len(zone) > 4 else 0.0
        origins[name] = (dx, dy, dz)
    return origins


# Known EnergyPlus 8.x boundary condition keywords at field[4]
_BOUNDARY_KEYWORDS = {
    "outdoors", "ground", "surface", "zone", "othersidecoefficients",
    "othersideconditionsmodel", "adiabatic", "foundation",
}


def _bsd_offsets(fields: list[str]) -> tuple[int, int, int, int]:
    """Detect field layout for BuildingSurface:Detailed objects.

    EnergyPlus 9+ added a 'Space Name' field at index 4, shifting all
    subsequent fields by one position.  EnergyPlus 8.x files do not have
    this field so boundary conditions start at index 4 instead of 5.

    Args:
        fields: Raw field list from the IDF parser (0-indexed, name at 0).

    Returns:
        Tuple of (zone_idx, boundary_idx, num_vertices_idx, vertex_start_idx).
    """
    # If field[4] matches a boundary keyword the Space Name is absent (8.x)
    if len(fields) > 4 and fields[4].strip().lower() in _BOUNDARY_KEYWORDS:
        return 3, 4, 9, 10   # 8.x layout (no Space Name)
    return 3, 5, 10, 11      # 9+ layout (Space Name at field[4])


def _parse_bsd_vertices(
    fields: list[str],
    dx: float,
    dy: float,
    dz: float,
    num_v_idx: int = 10,
    vertex_start: int = 11,
) -> list[tuple[float, float, float]]:
    """Extract world-space vertex list from a BuildingSurface:Detailed record.

    The vertex count field index and vertex start index vary between
    EnergyPlus 8.x (no Space Name) and 9+/22.x (Space Name at field[4]).
    Pass the values returned by ``_bsd_offsets()`` for full compatibility.

    Args:
        fields: Raw field list from idf_parser (values only, 0-indexed).
        dx: Zone X-origin offset.
        dy: Zone Y-origin offset.
        dz: Zone Z-origin offset.
        num_v_idx: Field index of the Number of Vertices value.
        vertex_start: Field index where the first X coordinate lives.

    Returns:
        List of (x, y, z) tuples in absolute world coordinates.
    """
    try:
        # Number of Vertices may be 'autocalculate' or an explicit integer.
        raw_count = fields[num_v_idx].strip().lower()
        if raw_count in ("", "autocalculate"):
            raw_floats = [v for v in fields[vertex_start:] if v.strip()]
            num_v = len(raw_floats) // 3
        else:
            num_v = int(raw_count)
            raw_floats = [
                v for v in fields[vertex_start : vertex_start + num_v * 3]
                if v.strip()
            ]
        raw = [float(v) for v in raw_floats]
        return [
            (raw[i] + dx, raw[i + 1] + dy, raw[i + 2] + dz)
            for i in range(0, num_v * 3, 3)
        ]
    except (ValueError, IndexError):
        return []



def _parse_fen_vertices(
    fields: list[str],
    dx: float,
    dy: float,
    dz: float,
) -> list[tuple[float, float, float]]:
    """Extract world-space vertex list from a FenestrationSurface:Detailed record.

    IDF values (after object-type stripped), 0-indexed:
      0  Name
      1  Surface Type (Window / Door …)
      2  Construction Name
      3  Building Surface Name    ← parent wall
      4  Outside Boundary Condition Object
      5  View Factor to Ground
      6  Frame and Divider Name
      7  Multiplier
      8  Number of Vertices       ← parse from here
      9+ X1, Y1, Z1, X2, Y2, Z2, …

    Args:
        fields: Raw field list from idf_parser.
        dx: Zone X-origin offset (same zone as the parent wall).
        dy: Zone Y-origin offset.
        dz: Zone Z-origin offset.

    Returns:
        List of (x, y, z) tuples in absolute world coordinates.
    """
    # FenestrationSurface:Detailed field layout differs between EnergyPlus
    # versions.  Rather than hardcode the offset, we scan forward from
    # field[5] (ViewFactor) looking for the first field that can be parsed
    # as a positive integer — that is the Number of Vertices.
    try:
        nv_idx = None
        for k in range(5, min(12, len(fields))):
            val = fields[k].strip().lower()
            if not val or val == "autocalculate":
                # EnergyPlus 22.1+ often has 'AutoCalculate' for View Factor to Ground (field 5).
                # Skip it and keep looking for the integer 'Number of Vertices' field (usually index 9).
                continue
            try:
                candidate = int(val)
                if 3 <= candidate <= 120:
                    nv_idx = k
                    num_v = candidate
                    vs_idx = k + 1
                    break
            except ValueError:
                pass
        if nv_idx is None:
            return []
        raw_floats = [v for v in fields[vs_idx : vs_idx + num_v * 3] if v.strip()]
        raw = [float(v) for v in raw_floats]
        return [
            (raw[i] + dx, raw[i + 1] + dy, raw[i + 2] + dz)
            for i in range(0, num_v * 3, 3)
        ]
    except (ValueError, IndexError):
        return []


def _parse_window_relative(
    fields: list[str],
    parent_verts: list[tuple[float, float, float]],
) -> list[tuple[float, float, float]]:
    """Convert relative Window object geometry to absolute 3D coordinates.

    IDF values for Window, 0-indexed:
      0  Name
      1  Construction Name
      2  Building Surface Name (parent wall)
      3  Frame and divider name
      4  Multiplier
      5  Starting X coordinate (relative to wall bottom-left)
      6  Starting Z coordinate (relative to wall bottom-left)
      7  Length
      8  Height

    Args:
        fields: Raw field list from idf_parser.
        parent_verts: Absolute 3D coordinates of the parent wall.

    Returns:
        List of 4 (x, y, z) tuples in absolute world coordinates.
    """
    if len(fields) < 9 or len(parent_verts) < 3:
        return []

    try:
        start_x = float(fields[5])
        start_z = float(fields[6])
        length = float(fields[7])
        height = float(fields[8])

        # Step 1: Find the "Bottom Left" vertex of the parent wall.
        # EnergyPlus surfaces are CCW from outside. 
        # The bottom-left is the first vertex of the bottom-most horizontal edge.
        n = len(parent_verts)
        zs = [v[2] for v in parent_verts]
        min_z = min(zs)
        
        # Check for the transition from "not min_z" to "min_z" in the CCW sequence
        origin_idx = 0
        for i in range(n):
            if abs(zs[i] - min_z) < 1e-4 and abs(zs[(i-1)%n] - min_z) > 1e-4:
                origin_idx = i
                break
        
        v1_p = parent_verts[origin_idx]
        v2_p = parent_verts[(origin_idx + 1) % n] # Next vertex should be Bottom Right
        v0_p = parent_verts[(origin_idx - 1) % n] # Previous vertex should be Top Left

        v1 = np.array(v1_p)
        v2 = np.array(v2_p)
        v0 = np.array(v0_p)

        # X direction vector (along the bottom edge: BL -> BR)
        vec_x_full = v2 - v1
        len_x = np.linalg.norm(vec_x_full)
        if len_x == 0: return []
        dir_x = vec_x_full / len_x

        # Z direction vector (up the left edge: BL -> TL)
        vec_z_full = v0 - v1
        len_z = np.linalg.norm(vec_z_full)
        if len_z == 0: return []
        dir_z = vec_z_full / len_z

        # Calculate the 4 window vertices
        w_bl = v1 + (dir_x * start_x) + (dir_z * start_z)
        w_br = w_bl + (dir_x * length)
        w_tl = w_bl + (dir_z * height)
        w_tr = w_br + (dir_z * height)

        return [tuple(w_tl), tuple(w_bl), tuple(w_br), tuple(w_tr)]

    except (ValueError, IndexError):
        return []


def _set_equal_aspect_3d(
    ax: "Axes3D",
    xs: list[float],
    ys: list[float],
    zs: list[float],
    z_scale: float = 1.0,
) -> None:
    """Force a 1:1 aspect ratio in all three axes so buildings look realistic.

    Matplotlib 3D does not natively support equal-aspect; we work around it
    by setting all axis limits to the same half-range centred on each midpoint.

    Args:
        ax: The 3D axes object.
        xs: All X coordinates of plotted geometry.
        ys: All Y coordinates.
        zs: All Z coordinates.
        z_scale: Scale factor applied to the Z half-range; values > 1 exaggerate
            height (useful when a building is very flat relative to footprint).
    """
    x_mid, y_mid, z_mid = (
        (max(xs) + min(xs)) / 2,
        (max(ys) + min(ys)) / 2,
        (max(zs) + min(zs)) / 2,
    )
    xy_range = max(max(xs) - min(xs), max(ys) - min(ys)) / 2
    z_range = (max(zs) - min(zs)) / 2

    # Use the larger of XY spread or Z spread (with scale factor) as the half-range
    half = max(xy_range, z_range * z_scale)

    if hasattr(ax, "set_box_aspect"):
        # Modern Matplotlib (>= 3.3.0) can set the visual bounding box to match the data's
        # physical dimensions, allowing for a tight, physically-accurate bounding box!
        x_span = max(0.1, max(xs) - min(xs))
        y_span = max(0.1, max(ys) - min(ys))
        z_span = max(0.1, max(zs) - min(zs))
        
        ax.set_box_aspect((x_span, y_span, z_span * z_scale))
        
        # Because the box aspect handles proportions, we can just tightly wrap the data
        ax.set_xlim(min(xs) - 1, max(xs) + 1)
        ax.set_ylim(min(ys) - 1, max(ys) + 1)
        ax.set_zlim(min(zs) - 1, max(zs) * z_scale + 1)
    else:
        # Fallback for older Matplotlib: force all axes limits to span the exact same range (2 * half).
        # This draws a large cubic bounding box but forces the building inside to look correctly scaled. 
        ax.set_xlim(x_mid - half, x_mid + half)
        ax.set_ylim(y_mid - half, y_mid + half)
        ax.set_zlim(z_mid - half, z_mid + half)


# ── Public API ───────────────────────────────────────────────────────────────


def render_idf_to_base64(idf_path: str) -> Optional[str]:
    """Render the building geometry to a base64-encoded PNG.

    Handles both Relative and Absolute EnergyPlus coordinate systems.
    Windows are drawn in a separate pass (after all opaque surfaces) so they
    are always visible on top of walls.

    Args:
        idf_path: Absolute path to the EnergyPlus .idf file.

    Returns:
        Base64-encoded PNG string, or None if rendering could not proceed.
    """
    if not HAS_DEPS:
        print("  Warning: matplotlib/numpy not installed – skipping 3D visualization.")
        return None

    import sys

    _root = os.path.dirname(__file__)
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from idf_parser import parse_idf

    try:
        idf_data = parse_idf(idf_path)
    except Exception as exc:
        print(f"  Warning: Could not parse IDF for visualization: {exc}")
        return None

    surfaces = idf_data.get("BUILDINGSURFACE:DETAILED", [])
    fenestr = idf_data.get("FENESTRATIONSURFACE:DETAILED", [])
    windows = idf_data.get("WINDOW", [])

    if not surfaces:
        print("  Warning: No surfaces found – skipping visualization.")
        return None

    # ── Coordinate system ────────────────────────────────────────────────────
    is_relative = _is_relative_coords(idf_data)
    coord_label = "Relative" if is_relative else "Absolute"
    zone_origins = _build_zone_origins(idf_data) if is_relative else {}

    # Build: parent surf name → list of fenestration field-lists
    # Also build: surf name → zone name (for fenestration offset lookup)
    fen_by_parent: dict[str, list[list[str]]] = {}
    for fen in fenestr:
        if len(fen) >= 4 and fen[3].strip():
            fen_by_parent.setdefault(fen[3].upper(), []).append(fen)
            
    win_by_parent: dict[str, list[list[str]]] = {}
    for win in windows:
        if len(win) >= 3 and win[2].strip():
            win_by_parent.setdefault(win[2].upper(), []).append(win)

    surf_to_zone: dict[str, str] = {
        surf[0]: surf[3] for surf in surfaces if len(surf) >= 4
    }

    # ── Figure setup ─────────────────────────────────────────────────────────
    plt.close("all")
    fig = plt.figure(figsize=(13, 10), facecolor="#0f172a")
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("#0f172a")
    for pane in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
        pane.fill = False
        pane.set_edgecolor("#334155")

    counts: dict[str, int] = {"wall": 0, "roof": 0, "floor": 0, "window": 0}
    all_x: list[float] = []
    all_y: list[float] = []
    all_z: list[float] = []

    # Raw polygon buffer: (verts, color, alpha, edge_color, linewidth, is_window)
    # We defer adding to the axes until after re-centring (see below).
    _raw_polys: list[tuple] = []

    # Collect pending window polygons so they are drawn AFTER all opaque surfaces
    pending_windows: list[list[tuple[float, float, float]]] = []

    # ── Pass 1: All building surfaces ────────────────────────────────────────
    # Strategy:
    #   • Exterior walls/roofs (bc=Outdoors): full colour, full alpha
    #   • Ground-contact floors (bc=Ground*): floor colour
    #   • Interior walls (bc=Surface/Zone): same wall colour, lower alpha
    #     → needed so complex multi-zone buildings (e.g. Hospital) don't look
    #       like hollow cage frames with missing panels
    #   • Interior ceilings/floors: skip (they create visual clutter)
    for surf in surfaces:
        if len(surf) < 12:
            continue

        surf_name = surf[0]
        surf_type = surf[1].strip().lower() if surf[1] else ""

        # Detect EnergyPlus version layout: 8.x has no Space Name at field[4]
        z_idx, bc_idx, nv_idx, vs_idx = _bsd_offsets(surf)

        zone_name = surf[z_idx].strip() if len(surf) > z_idx else ""
        boundary = surf[bc_idx].strip().lower() if len(surf) > bc_idx and surf[bc_idx] else ""

        is_exterior_wall = surf_type == "wall" and "outdoors" in boundary
        is_exterior_roof = surf_type in ("roof", "ceiling") and "outdoors" in boundary
        is_ground_floor = surf_type == "floor" and "ground" in boundary
        is_interior_wall = surf_type == "wall" and boundary in (
            "surface",
            "zone",
            "adiabatic",
        )

        if not any(
            [is_exterior_wall, is_exterior_roof, is_ground_floor, is_interior_wall]
        ):
            continue

        # Zone origin offset
        dx, dy, dz = zone_origins.get(zone_name, (0.0, 0.0, 0.0))

        verts = _parse_bsd_vertices(surf, dx, dy, dz,
                                     vertex_start=vs_idx, num_v_idx=nv_idx)
        if len(verts) < 3:
            continue

        all_x.extend(v[0] for v in verts)
        all_y.extend(v[1] for v in verts)
        all_z.extend(v[2] for v in verts)

        # Pick colour + alpha based on surface category
        if is_interior_wall:
            color, alpha = "#d4a574", 0.30  # same tan, much more transparent
        elif is_exterior_roof:
            color, alpha = _SURF_COLOR["roof"]
        elif is_ground_floor:
            color, alpha = _SURF_COLOR["floor"]
        else:
            color, alpha = _SURF_COLOR.get(surf_type, _DEFAULT_COLOR)

        edge_col = "#0f172a" if not is_interior_wall else "#1e293b"
        _raw_polys.append((verts, color, alpha, edge_col, 0.3, False))
        counts[surf_type if surf_type in counts else "wall"] += 1

        # Collect this surface's windows for pass 2 (only exterior walls have them)
        if is_exterior_wall:
            # Type 1: FenestrationSurface:Detailed
            for fen in fen_by_parent.get(surf_name.upper(), []):
                fen_verts = _parse_fen_vertices(fen, dx, dy, dz)
                if len(fen_verts) >= 3:
                    pending_windows.append(fen_verts)
            
            # Type 2: Window (Relative)
            for win in win_by_parent.get(surf_name.upper(), []):
                win_verts = _parse_window_relative(win, verts)
                if len(win_verts) >= 3:
                    pending_windows.append(win_verts)

    # ── Pass 2: Windows (always drawn on top) ────────────────────────────────
    for win_verts in pending_windows:
        _raw_polys.append((
            win_verts, _WIN_FACE, _WIN_ALPHA, _WIN_EDGE, 0.8, True
        ))
        counts["window"] += 1
        all_x.extend(v[0] for v in win_verts)
        all_y.extend(v[1] for v in win_verts)
        all_z.extend(v[2] for v in win_verts)

    # ── Re-centre geometry if building has a large baked-in XY offset ─────────
    # Some EnergyPlus 8.x IDF files store surface vertices in world-space
    # coordinates (e.g. X≈-456 m, Y≈-194 m) even when GlobalGeometryRules
    # declares Relative. Detect this by checking whether the centroid of all
    # collected X/Y coordinates is far from the origin and, if so, shift every
    # polygon back to near zero. This is purely additive — 22.x files whose
    # centroids are already close to the origin are unaffected.
    _RECENTRE_THRESHOLD = 50.0  # metres; triggers re-centring when exceeded
    if all_x and all_y:
        cx = (max(all_x) + min(all_x)) / 2.0
        cy = (max(all_y) + min(all_y)) / 2.0
        cz = min(all_z)  # shift Z floor to 0
        if abs(cx) > _RECENTRE_THRESHOLD or abs(cy) > _RECENTRE_THRESHOLD:
            coord_label += " [recentred]"
            _raw_polys = [
                (
                    [(x - cx, y - cy, z - cz) for x, y, z in verts],
                    color, alpha, edge_col, lw, is_win
                )
                for verts, color, alpha, edge_col, lw, is_win in _raw_polys
            ]
            all_x = [x - cx for x in all_x]
            all_y = [y - cy for y in all_y]
            all_z = [z - cz for z in all_z]

    # ── Flush all polygon buffers to the axes ─────────────────────────────────
    for verts, color, alpha, edge_col, lw, is_win in _raw_polys:
        poly = Poly3DCollection(
            [verts],
            alpha=alpha,
            facecolors=color,
            edgecolors=edge_col,
            linewidths=lw,
            zorder=10 if is_win else 1,
        )
        ax.add_collection3d(poly)

    # ── Axis limits: equal aspect per metre ──────────────────────────────────
    if all_x:
        # We use a 1:1:1 aspect ratio so floor heights and building proportions 
        # reflect the physical reality of the IDF geometry.
        _set_equal_aspect_3d(ax, all_x, all_y, all_z, z_scale=1.0)

    ax.view_init(elev=30, azim=-50)

    # ── Labels & legend ───────────────────────────────────────────────────────
    building_name = os.path.splitext(os.path.basename(idf_path))[0]
    ax.set_xlabel("X (m)", color="#94a3b8", fontsize=8, labelpad=6)
    ax.set_ylabel("Y (m)", color="#94a3b8", fontsize=8, labelpad=6)
    ax.set_zlabel("Z (m)", color="#94a3b8", fontsize=8, labelpad=6)
    ax.tick_params(colors="#94a3b8", labelsize=7)
    ax.set_title(
        f"3D Building Geometry  [{coord_label} coords]\n{building_name}",
        color="#c4b5fd",
        fontsize=10,
        pad=10,
    )

    from matplotlib.patches import Patch

    legend_items = [
        Patch(facecolor="#d4a574", label=f"Walls ({counts['wall']})"),
        Patch(facecolor="#8b5e3c", label=f"Roof/Ceiling ({counts['roof']})"),
        Patch(facecolor="#c0c0c0", label=f"Floor ({counts['floor']})"),
        Patch(facecolor=_WIN_FACE, label=f"Windows ({counts['window']})"),
    ]
    ax.legend(
        handles=legend_items,
        loc="upper left",
        fontsize=7,
        facecolor="#1e293b",
        edgecolor="#334155",
        labelcolor="#e2e8f0",
    )

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(
        buf, format="png", dpi=140, bbox_inches="tight", facecolor=fig.get_facecolor()
    )
    plt.close("all")
    buf.seek(0)

    img_b64 = base64.b64encode(buf.read()).decode("utf-8")
    print(
        f"  3D visualization [{coord_label}]: {counts['wall']} walls, "
        f"{counts['roof']} roof/ceiling, {counts['floor']} floors, "
        f"{counts['window']} windows."
    )
    return img_b64
