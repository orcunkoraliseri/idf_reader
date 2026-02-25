"""
Building Visualizer Module.

Provides 3D visualization of IDF building models using matplotlib.
"""

import os
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from eppy.modeleditor import IDF


def visualize_idf(idf_path: str) -> None:
    """
    Loads an IDF file and visualizes it in 3D.

    Args:
        idf_path: Path to the IDF file.
    """
    try:
        idd_file = os.environ.get("IDD_FILE")
        if idd_file:
            IDF.setiddname(idd_file)

        idf = IDF(idf_path)

        print(f"Visualizing {os.path.basename(idf_path)}...")

        # Check GlobalGeometryRules for coordinate system
        ggr = idf.idfobjects.get("GLOBALGEOMETRYRULES", [])
        is_relative = True
        if ggr:
            coord_sys = ggr[0].Coordinate_System
            if coord_sys.lower() == "absolute":
                is_relative = False

        fig = plt.figure(figsize=(12, 10))
        ax = fig.add_subplot(111, projection="3d")

        surfaces = idf.idfobjects.get("BUILDINGSURFACE:DETAILED", [])

        counts = {"wall": 0, "roof": 0, "floor": 0, "window": 0}
        all_coords = []

        for surf in surfaces:
            zone_name = surf.Zone_Name
            zone = idf.getobject("ZONE", zone_name)

            # Get zone origin offsets for relative coordinates
            dx, dy, dz = 0, 0, 0
            if is_relative and zone:
                dx = float(zone.X_Origin) if zone.X_Origin else 0
                dy = float(zone.Y_Origin) if zone.Y_Origin else 0
                dz = float(zone.Z_Origin) if zone.Z_Origin else 0

            # Get surface vertices
            coords = surf.coords
            abs_coords = [(x + dx, y + dy, z + dz) for x, y, z in coords]
            all_coords.extend(abs_coords)

            # Filter for exterior surfaces only
            bc = (
                surf.Outside_Boundary_Condition.lower()
                if surf.Outside_Boundary_Condition
                else ""
            )
            if bc not in [
                "outdoors",
                "ground",
                "groundslab",
                "groundbasementpreprocessedaverage",
            ]:
                if "ground" not in bc and "outdoors" not in bc:
                    continue

            # Determine color based on surface type
            surf_type = surf.Surface_Type.lower() if surf.Surface_Type else ""

            if "wall" in surf_type:
                color = "tan"
                counts["wall"] += 1
            elif "roof" in surf_type:
                color = "brown"
                counts["roof"] += 1
            elif "floor" in surf_type:
                color = "lightgrey"
                counts["floor"] += 1
            elif "ceiling" in surf_type:
                color = "brown"
                counts["roof"] += 1
            else:
                color = "grey"

            poly = Poly3DCollection(
                [abs_coords], alpha=0.9, facecolors=color, edgecolors="black"
            )
            ax.add_collection3d(poly)

            # Draw windows/doors (subsurfaces)
            subsurfs = idf.idfobjects.get("FENESTRATIONSURFACE:DETAILED", [])
            for sub in subsurfs:
                if sub.Building_Surface_Name == surf.Name:
                    sub_coords = sub.coords
                    sub_abs_coords = [
                        (x + dx, y + dy, z + dz) for x, y, z in sub_coords
                    ]

                    sub_poly = Poly3DCollection(
                        [sub_abs_coords],
                        alpha=0.7,
                        facecolors="lightblue",
                        edgecolors="darkblue",
                    )
                    ax.add_collection3d(sub_poly)
                    counts["window"] += 1

        print(
            f"Drawn: {counts['wall']} walls, {counts['roof']} roofs, "
            f"{counts['floor']} floors, {counts['window']} windows"
        )

        # Auto-scale axes
        if all_coords:
            xs = [p[0] for p in all_coords]
            ys = [p[1] for p in all_coords]
            zs = [p[2] for p in all_coords]

            # Enforce equal aspect ratio to prevent distortion
            max_range = (
                max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) / 2.0
            )

            mid_x = (max(xs) + min(xs)) * 0.5
            mid_y = (max(ys) + min(ys)) * 0.5
            mid_z = (max(zs) + min(zs)) * 0.5

            ax.set_xlim(mid_x - max_range, mid_x + max_range)
            ax.set_ylim(mid_y - max_range, mid_y + max_range)
            ax.set_zlim(mid_z - max_range, mid_z + max_range)

        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_zlabel("Z (m)")
        ax.set_title(f"Building Model: {os.path.basename(idf_path)}")

        plt.tight_layout()
        plt.show()

    except Exception as e:
        print(f"Error visualizing {idf_path}: {e}")
        import traceback

        traceback.print_exc()
