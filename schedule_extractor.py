"""
Extractor Module for Zone Schedule Assignments.

This module extracts schedule names referenced by various zone-level load objects
(People, Lights, Equipment, Infiltration, etc.) and maps them to zones.
"""

from collections import defaultdict
from typing import Any


def extract_zone_schedules(idf_data: dict) -> list[dict[str, Any]]:
    """Extracts schedule-to-zone mappings for all load types.

    Returns:
        A list of dicts, each containing:
        {
            "load_type": str,
            "schedule_name": str,
            "zones": list[str]
        }
    """
    # Mapping of Load Type -> Schedule Name -> Set of Zones
    mappings = {
        "Occupancy": defaultdict(set),
        "Lighting": defaultdict(set),
        "Electric Equipment": defaultdict(set),
        "Gas Equipment": defaultdict(set),
        "Infiltration": defaultdict(set),
        "Service Hot Water": defaultdict(set),
        "Heating Setpoint": defaultdict(set),
        "Cooling Setpoint": defaultdict(set),
    }

    # 1. Occupancy (People) - Zone idx 1, Sched idx 2
    for obj in idf_data.get("PEOPLE", []):
        if len(obj) > 2:
            zone, sched = obj[1], obj[2]
            if zone and sched:
                mappings["Occupancy"][sched].add(zone)

    # 2. Lighting (Lights) - Zone idx 1, Sched idx 2
    for obj in idf_data.get("LIGHTS", []):
        if len(obj) > 2:
            zone, sched = obj[1], obj[2]
            if zone and sched:
                mappings["Lighting"][sched].add(zone)

    # 3. Electric Equipment - Zone idx 1, Sched idx 2
    for obj in idf_data.get("ELECTRICEQUIPMENT", []):
        if len(obj) > 2:
            zone, sched = obj[1], obj[2]
            if zone and sched:
                mappings["Electric Equipment"][sched].add(zone)

    # 4. Gas Equipment - Zone idx 1, Sched idx 2
    for obj in idf_data.get("GASEQUIPMENT", []):
        if len(obj) > 2:
            zone, sched = obj[1], obj[2]
            if zone and sched:
                mappings["Gas Equipment"][sched].add(zone)

    # 5. Infiltration - Zone idx 1, Sched idx 2
    for obj in idf_data.get("ZONEINFILTRATION:DESIGNFLOWRATE", []):
        if len(obj) > 2:
            zone, sched = obj[1], obj[2]
            if zone and sched:
                mappings["Infiltration"][sched].add(zone)

    # 6. Service Hot Water - Sched idx 3, Zone idx 7
    for obj in idf_data.get("WATERUSE:EQUIPMENT", []):
        if len(obj) > 7:
            sched, zone = obj[3], obj[7]
            if zone and sched:
                mappings["Service Hot Water"][sched].add(zone)

    # 7 & 8. Thermostats (Dual Setpoint) - Htg idx 1, Clg idx 2
    for obj in idf_data.get("THERMOSTATSETPOINT:DUALSETPOINT", []):
        if len(obj) > 2:
            # Zone name is typically Name stripping " Dual SP Control"
            name = obj[0]
            zone = name.replace(" Dual SP Control", "")
            htg_sched, clg_sched = obj[1], obj[2]
            if htg_sched:
                mappings["Heating Setpoint"][htg_sched].add(zone)
            if clg_sched:
                mappings["Cooling Setpoint"][clg_sched].add(zone)

    # Convert to flat list of records
    results = []
    # Use explicit order to keep table consistent
    load_order = [
        "Occupancy", "Lighting", "Electric Equipment", "Gas Equipment",
        "Infiltration", "Service Hot Water", "Heating Setpoint", "Cooling Setpoint"
    ]
    
    for lt in load_order:
        sched_map = mappings[lt]
        for sched in sorted(sched_map.keys()):
            results.append({
                "load_type": lt,
                "schedule_name": sched,
                "zones": sorted(list(sched_map[sched]))
            })

    return results
