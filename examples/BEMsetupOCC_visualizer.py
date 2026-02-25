import sys
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from geomeppy import IDF


def visualize_idf(idf_path, idd_path):
    """
    Loads an IDF file and visualizes it using a custom matplotlib loop
    to ensure correct coordinate handling.
    """
    try:
        IDF.setiddname(idd_path)
        idf = IDF(idf_path)

        print(f"Visualizing {idf_path}...")

        # Check GlobalGeometryRules
        ggr = idf.idfobjects["GLOBALGEOMETRYRULES"]
        is_relative = True
        if ggr:
            coord_sys = ggr[0].Coordinate_System
            if coord_sys.lower() == "absolute":
                is_relative = False

        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")

        surfaces = idf.idfobjects["BUILDINGSURFACE:DETAILED"]

        # Collect all polygons
        counts = {
            "wall": 0,
            "roof": 0,
            "floor": 0,
            "ceiling": 0,
            "window": 0,
            "other": 0,
        }

        for surf in surfaces:
            zone_name = surf.Zone_Name
            zone = idf.getobject("ZONE", zone_name)

            dx, dy, dz = 0, 0, 0
            if is_relative and zone:
                dx = float(zone.X_Origin) if zone.X_Origin else 0
                dy = float(zone.Y_Origin) if zone.Y_Origin else 0
                dz = float(zone.Z_Origin) if zone.Z_Origin else 0

            # Surface Vertices
            coords = surf.coords
            abs_coords = [(x + dx, y + dy, z + dz) for x, y, z in coords]

            # Filter for Exterior Surfaces only
            # We only want to see the shell of the building
            # Determine color based on Surface Type
            surf_type = surf.Surface_Type.lower()

            # Filter for Exterior Surfaces only
            # We only want to see the shell of the building
            bc = surf.Outside_Boundary_Condition.lower()
            if bc not in [
                "outdoors",
                "ground",
                "groundslab",
                "groundbasementpreprocessedaverage",
            ]:
                # Some ground conditions might have different names, but 'ground' is standard.
                # Let's be permissive with 'ground'
                if "ground" not in bc and "outdoors" not in bc:
                    # Special case: Allow walls that are inter-zone or adiabatic to fill gaps
                    if "wall" in surf_type and bc in ["zone", "surface", "adiabatic"]:
                        print(f"DEBUG: Including inter-zone wall {surf.Name} (BC={bc})")
                        print(f"DEBUG: Coords: {abs_coords}")
                        # Draw these in RED to verify visibility
                        poly = Poly3DCollection(
                            [abs_coords],
                            alpha=1.0,
                            facecolors="red",
                            edgecolors="black",
                        )
                        ax.add_collection3d(poly)
                        counts["wall"] += 1
                        continue
                    else:
                        if "wall" in surf_type:
                            print(f"DEBUG: Skipping wall {surf.Name} (BC={bc})")
                        continue

            if "wall" in surf_type:
                color = "tan"
                counts["wall"] += 1
            elif "roof" in surf_type:
                color = "brown"
                counts["roof"] += 1
            elif "floor" in surf_type:
                if "ground" in bc:
                    color = "lightgrey"
                    counts["floor"] += 1
                else:
                    # Exterior floor (e.g. overhang/soffit) -> color as roof
                    color = "brown"
                    counts["floor"] += 1
            elif "ceiling" in surf_type:
                # Exterior ceiling (e.g. soffit) -> color as roof
                color = "brown"
                counts["ceiling"] += 1
            else:
                color = "grey"
                counts["other"] += 1

            poly = Poly3DCollection(
                [abs_coords], alpha=1.0, facecolors=color, edgecolors="black"
            )
            ax.add_collection3d(poly)

            # Subsurfaces
            subsurfs = idf.idfobjects["FENESTRATIONSURFACE:DETAILED"]
            for sub in subsurfs:
                if sub.Building_Surface_Name == surf.Name:
                    sub_coords = sub.coords
                    # Subsurfaces in Relative mode are relative to ZONE, just like Surfaces
                    # So we use the same dx, dy, dz
                    sub_abs_coords = [
                        (x + dx, y + dy, z + dz) for x, y, z in sub_coords
                    ]

                    sub_poly = Poly3DCollection(
                        [sub_abs_coords],
                        alpha=0.8,
                        facecolors="lightblue",
                        edgecolors="black",
                    )
                    ax.add_collection3d(sub_poly)
                    counts["window"] += 1

        print(f"Drawn elements: {counts}")

        # Auto-scale
        # We need to find the limits
        all_coords = []
        for surf in surfaces:
            zone_name = surf.Zone_Name
            zone = idf.getobject("ZONE", zone_name)
            dx, dy, dz = 0, 0, 0
            if is_relative and zone:
                dx = float(zone.X_Origin) if zone.X_Origin else 0
                dy = float(zone.Y_Origin) if zone.Y_Origin else 0
                dz = float(zone.Z_Origin) if zone.Z_Origin else 0
            for p in surf.coords:
                all_coords.append((p[0] + dx, p[1] + dy, p[2] + dz))

        if all_coords:
            xs = [p[0] for p in all_coords]
            ys = [p[1] for p in all_coords]
            zs = [p[2] for p in all_coords]

            ax.set_xlim(min(xs), max(xs))
            ax.set_ylim(min(ys), max(ys))
            ax.set_zlim(min(zs), max(zs))

        plt.show()

    except Exception as e:
        print(f"Error visualizing {idf_path}: {e}")
        import traceback

        traceback.print_exc()
