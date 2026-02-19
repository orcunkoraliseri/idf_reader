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


def _parse_bsd_vertices(
    fields: list[str],
    dx: float,
    dy: float,
    dz: float,
) -> list[tuple[float, float, float]]:
    """Extract world-space vertex list from a BuildingSurface:Detailed record.

    IDF values (after object-type is stripped), 0-indexed:
      0  Name
      1  Surface Type
      2  Construction Name
      3  Zone Name                ← used for origin offset lookup
      4  Space Name
      5  Outside Boundary Condition
      6  Outside Boundary Condition Object
      7  Sun Exposure
      8  Wind Exposure
      9  View Factor to Ground
      10 Number of Vertices       ← parse from here
      11+ X1, Y1, Z1, X2, Y2, Z2, …

    Args:
        fields: Raw field list from idf_parser (values only, 0-indexed).
        dx: Zone X-origin offset.
        dy: Zone Y-origin offset.
        dz: Zone Z-origin offset.

    Returns:
        List of (x, y, z) tuples in absolute world coordinates.
    """
    try:
        num_v = int(fields[10])
        raw = [float(v) for v in fields[11 : 11 + num_v * 3] if v.strip()]
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
    try:
        num_v = int(fields[8])
        raw = [float(v) for v in fields[9 : 9 + num_v * 3] if v.strip()]
        return [
            (raw[i] + dx, raw[i + 1] + dy, raw[i + 2] + dz)
            for i in range(0, num_v * 3, 3)
        ]
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

    ax.set_xlim(x_mid - half, x_mid + half)
    ax.set_ylim(y_mid - half, y_mid + half)
    ax.set_zlim(z_mid - z_range * z_scale - 0.5, z_mid + z_range * z_scale + 0.5)


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
            fen_by_parent.setdefault(fen[3], []).append(fen)

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
    all_x, all_y, all_z = [], [], []

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
        zone_name = surf[3].strip()
        boundary = surf[5].strip().lower() if len(surf) > 5 and surf[5] else ""

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

        verts = _parse_bsd_vertices(surf, dx, dy, dz)
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
        poly = Poly3DCollection(
            [verts],
            alpha=alpha,
            facecolors=color,
            edgecolors=edge_col,
            linewidths=0.3,
        )
        ax.add_collection3d(poly)
        counts[surf_type if surf_type in counts else "wall"] += 1

        # Collect this surface's windows for pass 2 (only exterior walls have them)
        if is_exterior_wall:
            for fen in fen_by_parent.get(surf_name, []):
                fen_verts = _parse_fen_vertices(fen, dx, dy, dz)
                if len(fen_verts) >= 3:
                    pending_windows.append(fen_verts)

    # ── Pass 2: Windows (always drawn on top) ────────────────────────────────
    for win_verts in pending_windows:
        win_poly = Poly3DCollection(
            [win_verts],
            alpha=_WIN_ALPHA,
            facecolors=_WIN_FACE,
            edgecolors=_WIN_EDGE,
            linewidths=0.8,
            zorder=10,
        )
        ax.add_collection3d(win_poly)
        counts["window"] += 1
        all_x.extend(v[0] for v in win_verts)
        all_y.extend(v[1] for v in win_verts)
        all_z.extend(v[2] for v in win_verts)

    # ── Axis limits: equal aspect per metre (Z boosted for readability) ───────
    if all_x:
        # Compute actual Z span; if building is wider than tall boost Z slightly
        xy_span = max(max(all_x) - min(all_x), max(all_y) - min(all_y))
        z_span = max(all_z) - min(all_z)
        # Scale factor: ensure Z occupies at least 30 % of the XY range visually
        z_boost = max(1.0, (xy_span * 0.30) / z_span) if z_span > 0 else 1.5
        _set_equal_aspect_3d(ax, all_x, all_y, all_z, z_scale=z_boost)

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
