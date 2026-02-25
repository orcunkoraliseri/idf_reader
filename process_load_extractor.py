"""
Extractor Module for Building-Level and Zone-Assigned Process Loads.

This module extracts exterior lights, elevators, and refrigeration equipment
from IDF data into a unified structure for building-level reporting.
"""

from typing import Any


def extract_building_process_loads(idf_data: dict) -> list[dict[str, Any]]:
    """Extracts building-level and zone-assigned process loads.

    Returns:
        A list of dictionaries containing process load metadata.
    """
    results = []

    # 1. Exterior Lighting (Exterior:Lights)
    # Fields: Name, Schedule, Design Level [W], Control Option, Subcategory
    for obj in idf_data.get("EXTERIOR:LIGHTS", []):
        try:
            results.append({
                "category": "Exterior Lighting",
                "name": obj[0],
                "power_w": float(obj[2]) if obj[2] else 0.0,
                "zone": "Building-Level",
                "subcategory": obj[4] if len(obj) > 4 else "General",
                "details": f"Control: {obj[3]}" if len(obj) > 3 else ""
            })
        except (ValueError, IndexError):
            continue

    # 2. Exterior Fuel Equipment (Elevators in newer prototypes)
    # Fields: Name, Fuel Type, Schedule, Design Level [W], Subcategory
    for obj in idf_data.get("EXTERIOR:FUELEQUIPMENT", []):
        try:
            results.append({
                "category": "Exterior Equipment",
                "name": obj[0],
                "power_w": float(obj[3]) if obj[3] else 0.0,
                "zone": "Building-Level",
                "subcategory": obj[4] if len(obj) > 4 else "General",
                "details": f"Fuel: {obj[1]}"
            })
        except (ValueError, IndexError):
            continue

    # 3. Zone-Assigned Elevators (ElectricEquipment)
    # Fields: Name(0), Zone(1), Schedule(2), Method(3), Level(4)... Subcategory(10)
    for obj in idf_data.get("ELECTRICEQUIPMENT", []):
        try:
            subcategory = obj[10] if len(obj) > 10 else ""
            if "elevator" in subcategory.lower():
                results.append({
                    "category": "Elevator",
                    "name": obj[0],
                    "power_w": float(obj[4]) if obj[4] else 0.0,
                    "zone": obj[1],
                    "subcategory": subcategory,
                    "details": "Zone-assigned equipment"
                })
        except (ValueError, IndexError):
            continue

    # 4. Refrigeration Case
    # Fields: Name(0), Schedule(1), Zone(2), ..., Rated Total Cooling Cap/m (5), ..., Case Length(8)...
    for obj in idf_data.get("REFRIGERATION:CASE", []):
        try:
            capacity_per_m = float(obj[5]) if obj[5] else 0.0
            length = float(obj[8]) if obj[8] else 0.0
            results.append({
                "category": "Refrigeration Case",
                "name": obj[0],
                "power_w": capacity_per_m * length,
                "zone": obj[2],
                "subcategory": "Refrigeration",
                "details": f"Length: {length}m, Capacity/m: {capacity_per_m}W/m"
            })
        except (ValueError, IndexError):
            continue

    # 5. Compressor Rack
    # Fields: Name(0), Location(1), COP(2), ..., Fan Power(4)... Subcategory(23)
    for obj in idf_data.get("REFRIGERATION:COMPRESSORRACK", []):
        try:
            # Subcategory is usually at the end, let's look for a string that looks like a subcategory
            subcategory = "Refrigeration"
            if len(obj) > 23:
                subcategory = obj[23]
            
            results.append({
                "category": "Compressor Rack",
                "name": obj[0],
                "power_w": float(obj[4]) if obj[4] else 0.0,
                "zone": obj[1], # Location (usually ZONE or OUTDOOR)
                "subcategory": subcategory,
                "details": f"Design COP: {obj[2]}" if len(obj) > 2 else ""
            })
        except (ValueError, IndexError):
            continue

    return results
