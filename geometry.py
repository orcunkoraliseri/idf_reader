"""
Geometry Calculation Module for EnergyPlus Zones.

This module provides tools to calculate zone-level geometric attributes,
such as floor area, exterior facade area, and volume, primarily by
parsing and processing BuildingSurface:Detailed objects.
"""

import numpy as np


def calculate_polygon_area(vertices: list[list[float]]) -> float:
    """Calculates the area of a 3D polygon using the cross product method.

    Args:
        vertices: A list of [x, y, z] coordinates defining the polygon vertices.

    Returns:
        The area of the polygon in square meters.
    """
    if len(vertices) < 3:
        return 0.0

    # Convert to numpy array for vector operations
    v_arr = [np.array(v) for v in vertices]

    # Calculate the vector cross product sum
    total_area_vec = np.zeros(3)
    for i in range(len(v_arr)):
        v1 = v_arr[i]
        v2 = v_arr[(i + 1) % len(v_arr)]
        total_area_vec += np.cross(v1, v2)

    # The area is half the magnitude of the resulting vector
    return float(0.5 * np.linalg.norm(total_area_vec))


def get_zone_geometry(
    idf_data: dict[str, list[list[str]]],
) -> dict[str, dict[str, float]]:
    """Extracts and computes geometric data for all zones in the IDF.

    Args:
        idf_data: Parsed IDF data dictionary from idf_parser.

    Returns:
        A dictionary mapping zone names to a dictionary of their geometric properties:
        {
            'ZoneName': {
                'floor_area': float,
                'facade_area': float,
                'volume': float,
                'multiplier': float
            }
        }
    """
    zone_geo: dict[str, dict[str, float]] = {}

    # Initialize zone data from ZONE objects
    for zone_fields in idf_data.get("ZONE", []):
        if not zone_fields:
            continue

        name = zone_fields[0]

        # Multiplier (field 7 in IDF, index 6 in values)
        try:
            multiplier = float(zone_fields[6]) if zone_fields[6] else 1.0
        except (ValueError, IndexError):
            multiplier = 1.0

        # Volume (field 9 in IDF, index 8 in values)
        volume = 0.0
        if len(zone_fields) > 8:
            val = zone_fields[8].lower()
            if val != "autocalculate" and val != "":
                try:
                    volume = float(val)
                except ValueError:
                    pass

        # Floor Area (field 10 in IDF, index 9 in values)
        floor_area = 0.0
        if len(zone_fields) > 9:
            val = zone_fields[9].lower()
            if val != "autocalculate" and val != "":
                try:
                    floor_area = float(val)
                except ValueError:
                    pass

        zone_geo[name] = {
            "floor_area": floor_area,
            "facade_area": 0.0,
            "volume": volume,
            "multiplier": multiplier,
        }

    # Process BuildingSurface:Detailed to handle 'autocalculate' and facade area
    for surf in idf_data.get("BUILDINGSURFACE:DETAILED", []):
        if len(surf) < 12:
            continue

        surf_type = surf[1].lower()
        zone_name = surf[3]
        boundary = surf[5].lower()

        if zone_name not in zone_geo:
            continue

        # Extract vertices
        try:
            num_vertices = int(surf[10])
            vertices_flat = [float(v) for v in surf[11:] if v.strip()]
            vertices = []
            for i in range(0, num_vertices * 3, 3):
                vertices.append(vertices_flat[i : i + 3])

            surf_area = calculate_polygon_area(vertices)

            # Add to floor area if explicitly 'autocalculate' or currently 0
            if surf_type == "floor":
                # We check if we need to aggregate floor area
                # (Simple heuristic: if explicit floor_area is 0, we sum surfaces)
                if zone_geo[zone_name]["floor_area"] <= 0.001:
                    # Note: We don't overwrite every time, we sum them
                    pass  # Handled below

                # We always track the sum of floor surfaces in a temporary variable if needed
                # But for simplicity, if it's 0 we just start summing
                if "sum_floor" not in zone_geo[zone_name]:
                    zone_geo[zone_name]["sum_floor"] = 0.0
                zone_geo[zone_name]["sum_floor"] += surf_area

            # Facade area (Exterior walls)
            if surf_type == "wall" and boundary == "outdoors":
                zone_geo[zone_name]["facade_area"] += surf_area

        except (ValueError, IndexError):
            continue

    # Finalize floor_area if it was autocalculated
    for name, data in zone_geo.items():
        if data["floor_area"] <= 0.001 and "sum_floor" in data:
            data["floor_area"] = data["sum_floor"]

        # Cleanup temporary keys
        if "sum_floor" in data:
            del data["sum_floor"]

    return zone_geo
