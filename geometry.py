"""
Geometry Calculation Module for EnergyPlus Zones.

This module provides tools to calculate zone-level geometric attributes,
such as floor area, exterior facade area, and volume, primarily by
parsing and processing BuildingSurface:Detailed objects.
"""

import numpy as np
from extractors import extract_zone_metadata
from visualizer_adapter import _bsd_offsets


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
    zone_metadata = extract_zone_metadata(idf_data)
    for name, metadata in zone_metadata.items():
        zone_geo[name] = {
            "floor_area": metadata["floor_area"],
            "facade_area": 0.0,
            "exterior_roof_area": 0.0,
            "volume": metadata["volume"],
            "multiplier": metadata["multiplier"],
            "story_count": 1,
            "_floor_elevations": set(),
        }

    # Process BuildingSurface:Detailed to handle 'autocalculate' and facade area
    for surf in idf_data.get("BUILDINGSURFACE:DETAILED", []):
        # Use _bsd_offsets to handle EnergyPlus 8.x vs 9+/22.x field layout
        z_idx, bc_idx, nv_idx, vs_idx = _bsd_offsets(surf)
        if len(surf) <= vs_idx:
            continue

        surf_type = surf[1].lower() if len(surf) > 1 else ""
        zone_name = surf[z_idx] if len(surf) > z_idx else ""
        boundary = surf[bc_idx].lower() if len(surf) > bc_idx else ""

        if zone_name not in zone_geo:
            continue

        # Extract vertices — handle autocalculate for num_vertices
        try:
            raw_count = surf[nv_idx].strip().lower()
            if raw_count in ("", "autocalculate"):
                verts_flat = [float(v) for v in surf[vs_idx:] if v.strip()]
                num_vertices = len(verts_flat) // 3
            else:
                num_vertices = int(raw_count)
                verts_flat = [
                    float(v)
                    for v in surf[vs_idx : vs_idx + num_vertices * 3]
                    if v.strip()
                ]

            vertices = [
                verts_flat[i : i + 3] for i in range(0, num_vertices * 3, 3)
            ]
            
            # 1. Calculate Area and Normal-based Volume Pyramid
            # Area Calculation
            v_arr = [np.array(v) for v in vertices]
            face_area_vec = np.zeros(3)
            for i in range(len(v_arr)):
                v1 = v_arr[i]
                v2 = v_arr[(i + 1) % len(v_arr)]
                face_area_vec += np.cross(v1, v2)
            
            surf_area = 0.5 * np.linalg.norm(face_area_vec)
            
            # Volume Calculation (Signed pyramid volume from origin to face)
            # Vol = (1/6) * sum( dot(v_i, v_next x v_next_next) ) is for specific triangle meshes.
            # For general polygon: Vol = (1/3) * dot(any_vertex, face_area_vector_sum_half)
            # Note: face_area_vec is 2x the actual vector area
            zone_geo[zone_name]["volume"] += (1.0/6.0) * np.dot(v_arr[0], face_area_vec)

            if surf_type == "floor":
                if "sum_floor" not in zone_geo[zone_name]:
                    zone_geo[zone_name]["sum_floor"] = 0.0
                zone_geo[zone_name]["sum_floor"] += surf_area
                
                # Use the Z coordinate of the first vertex to identify the floor's elevation
                # Round to 1 decimal place to group surfaces on the same story
                z_elev = round(v_arr[0][2], 1)
                zone_geo[zone_name]["_floor_elevations"].add(z_elev)

            if surf_type == "wall" and "outdoors" in boundary:
                zone_geo[zone_name]["facade_area"] += surf_area
            
            if surf_type in ["roof", "roofceiling"] and "outdoors" in boundary:
                zone_geo[zone_name]["exterior_roof_area"] += surf_area

        except (ValueError, IndexError):
            continue

    # Finalize floor_area and volume
    for name, data in zone_geo.items():
        data["volume"] = abs(data["volume"])

    # Finalize floor_area if it was autocalculated
    for name, data in zone_geo.items():
        if data["floor_area"] <= 0.001 and "sum_floor" in data:
            data["floor_area"] = data["sum_floor"]

        if "_floor_elevations" in data:
            elevations = data["_floor_elevations"]
            if len(elevations) > 0:
                data["story_count"] = len(elevations)
            del data["_floor_elevations"]

        # Cleanup temporary keys
        if "sum_floor" in data:
            del data["sum_floor"]

    return zone_geo
