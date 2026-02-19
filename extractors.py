from __future__ import annotations

"""
Extraction Module for Zone Metadata.

This module contains specialized functions to extract and normalize various
building parameters from EnergyPlus objects, converting them to standard units
per square meter of floor area (or facade area where appropriate).
"""

import re


def get_first_num(text: str) -> float | None:
    """Helper to extract the first numeric value from a string."""
    match = re.search(r"[-+]?\d*\.?\d+", text)
    return float(match.group()) if match else None


def resolve_schedule_value(idf_data: dict, schedule_name: str) -> float | None:
    """Attempts to find a representative numeric value for a schedule."""
    schedule_name_upper = schedule_name.upper()

    # Check Schedule:Constant
    for sch in idf_data.get("SCHEDULE:CONSTANT", []):
        if sch[0].upper() == schedule_name_upper:
            try:
                return float(sch[2])
            except (ValueError, IndexError):
                pass

    # Check Schedule:Compact
    for sch in idf_data.get("SCHEDULE:COMPACT", []):
        if sch[0].upper() == schedule_name_upper:
            # Compact schedules have interleaved fields.
            # We look for fields that are strictly numeric (no THROUGH, FOR, UNTIL, :, /)
            for field in sch[2:]:
                f_upper = field.upper()
                if any(k in f_upper for k in ["THROUGH", "FOR", "UNTIL", ":", "/"]):
                    continue

                val = get_first_num(field)
                if val is not None:
                    return val
    return None


def extract_people(idf_data: dict, zone_geo: dict) -> dict[str, float]:
    """Extracts occupancy density (people/m2)."""
    results = {name: 0.0 for name in zone_geo}
    for obj in idf_data.get("PEOPLE", []):
        if len(obj) < 3:
            continue
        zone_name = obj[1]
        if zone_name not in zone_geo:
            continue

        method = obj[3].lower()
        area = zone_geo[zone_name]["floor_area"]
        if area <= 0:
            continue

        try:
            if method == "people":
                # field 5: Number of People
                results[zone_name] += float(obj[4]) / area
            elif method in ["people/area", "perarea"]:
                # field 6: People per Floor Area
                results[zone_name] += float(obj[5])
            elif method in ["area/person", "perperson"]:
                # field 7: Floor Area per Person
                val = float(obj[6])
                if val > 0:
                    results[zone_name] += 1.0 / val
        except (ValueError, IndexError):
            continue
    return results


def extract_loads(
    idf_data: dict, zone_geo: dict, obj_key: str, subcat_filter: str | None = None
) -> dict[str, float]:
    """Helper to extract Lights or Equipment loads (W/m2)."""
    results = {name: 0.0 for name in zone_geo}
    for obj in idf_data.get(obj_key.upper(), []):
        if len(obj) < 3:
            continue
        zone_name = obj[1]
        if zone_name not in zone_geo:
            continue

        # Optional filter by subcategory (for process loads)
        if subcat_filter:
            subcat = obj[-1].lower() if obj else ""
            if subcat_filter not in subcat:
                continue

        method = obj[3].lower()
        area = zone_geo[zone_name]["floor_area"]
        if area <= 0:
            continue

        try:
            if method in ["lightinglevel", "equipmentlevel", "level"]:
                # field 5 in IDF
                results[zone_name] += float(obj[4]) / area
            elif method in ["watts/area", "perarea"]:
                # field 6 in IDF
                results[zone_name] += float(obj[5])
            elif method in ["watts/person", "perperson"]:
                # field 7 in IDF
                pass
        except (ValueError, IndexError):
            continue
    return results


def extract_water_use(idf_data: dict, zone_geo: dict) -> dict[str, float]:
    """Extracts SHW usage (L/h.m2)."""
    results = {name: 0.0 for name in zone_geo}
    for obj in idf_data.get("WATERUSE:EQUIPMENT", []):
        if len(obj) < 8:
            continue
        zone_name = obj[7]  # Zone Name is field 8 in IDF
        if zone_name not in zone_geo:
            continue

        area = zone_geo[zone_name]["floor_area"]
        if area <= 0:
            continue

        try:
            # field 3: Peak Flow Rate {m3/s} (index 2)
            peak_m3s = float(obj[2])
            # Normalize to L/h.m2: m3/s * 3600000 / area
            results[zone_name] += (peak_m3s * 3600000) / area
        except (ValueError, IndexError):
            continue
    return results


def extract_infiltration(idf_data: dict, zone_geo: dict) -> dict[str, float]:
    """Extracts infiltration (m3/s per m2 facade)."""
    results = {name: 0.0 for name in zone_geo}
    for obj in idf_data.get("ZONEINFILTRATION:DESIGNFLOWRATE", []):
        if len(obj) < 3:
            continue
        zone_name = obj[1]
        if zone_name not in zone_geo:
            continue

        method = obj[3].lower()
        facade_area = zone_geo[zone_name]["facade_area"]
        floor_area = zone_geo[zone_name]["floor_area"]
        volume = zone_geo[zone_name]["volume"]

        # Use floor_area if facade_area is 0 (fallback)
        norm_area = facade_area if facade_area > 0 else floor_area
        if norm_area <= 0:
            continue

        try:
            if method in ["flow/zone", "level"]:
                results[zone_name] += float(obj[4]) / norm_area
            elif method == "flow/area":
                results[zone_name] += (float(obj[5]) * floor_area) / norm_area
            elif method == "flow/exteriorwallarea":
                results[zone_name] += float(obj[6])
            elif method == "airchanges/hour":
                # ACH * Volume / 3600
                if volume > 0:
                    m3s = (float(obj[7]) * volume) / 3600
                    results[zone_name] += m3s / norm_area
        except (ValueError, IndexError):
            continue
    return results


def extract_ventilation(idf_data: dict, zone_geo: dict) -> dict[str, dict[str, float]]:
    """Extracts ventilation (m3/s per person AND m3/s per m2)."""
    results = {name: {"per_person": 0.0, "per_area": 0.0} for name in zone_geo}
    for obj in idf_data.get("DESIGNSPECIFICATION:OUTDOORAIR", []):
        name = obj[0]
        # Heuristic: Match "SZ DSOA ZoneName"
        matched_zone = None
        for zn in zone_geo:
            if zn.upper() in name.upper():
                matched_zone = zn
                break

        if not matched_zone:
            continue

        try:
            # Field 3: Flow per Person
            if obj[2]:
                results[matched_zone]["per_person"] = float(obj[2])
            # Field 4: Flow per Area
            if obj[3]:
                results[matched_zone]["per_area"] = float(obj[3])
        except (ValueError, IndexError):
            continue
    return results


def extract_thermostats(idf_data: dict, zone_geo: dict) -> dict[str, dict[str, float]]:
    """Extracts heating and cooling setpoints (°C)."""
    results = {name: {"heating": 0.0, "cooling": 0.0} for name in zone_geo}

    # 1. Map Zone to Thermostat Object via ZoneControl:Thermostat
    zone_to_thermo = {}
    for obj in idf_data.get("ZONECONTROL:THERMOSTAT", []):
        if len(obj) < 2:
            continue
        zone_name = obj[1]
        thermo_name = obj[0]
        zone_to_thermo[zone_name] = thermo_name

    # 2. Extract Setpoints from Thermostat Objects
    for obj in idf_data.get("ZONECONTROL:THERMOSTAT", []):
        zn = obj[1]
        if zn not in results:
            continue

        # Look at the Control types (fields 4, 6, 8...)
        for i in range(3, len(obj), 2):
            control_type = obj[i].upper()
            control_name = obj[i + 1]

            if control_type == "THERMOSTATSETPOINT:DUALSETPOINT":
                for sp in idf_data.get("THERMOSTATSETPOINT:DUALSETPOINT", []):
                    if sp[0] == control_name:
                        h = resolve_schedule_value(idf_data, sp[1])
                        c = resolve_schedule_value(idf_data, sp[2])
                        if h is not None:
                            results[zn]["heating"] = h
                        if c is not None:
                            results[zn]["cooling"] = c
            elif control_type == "THERMOSTATSETPOINT:SINGLEHEATING":
                for sp in idf_data.get("THERMOSTATSETPOINT:SINGLEHEATING", []):
                    if sp[0] == control_name:
                        h = resolve_schedule_value(idf_data, sp[1])
                        if h is not None:
                            results[zn]["heating"] = h
            elif control_type == "THERMOSTATSETPOINT:SINGLECOOLING":
                for sp in idf_data.get("THERMOSTATSETPOINT:SINGLECOOLING", []):
                    if sp[0] == control_name:
                        c = resolve_schedule_value(idf_data, sp[1])
                        if c is not None:
                            results[zn]["cooling"] = c

    return results


def extract_process_loads(idf_data: dict, zone_geo: dict) -> dict[str, float]:
    """Extracts process loads like elevators and refrigeration (W/m2)."""
    results = {name: 0.0 for name in zone_geo}
    keywords = ["elevator", "refrig", "process", "laundry", "kitchen"]

    for obj in idf_data.get("ELECTRICEQUIPMENT", []) + idf_data.get(
        "OTHEREQUIPMENT", []
    ):
        if len(obj) < 4:
            continue
        zone_name = obj[1]
        if zone_name not in zone_geo:
            continue

        is_process = False
        for field in obj:
            if any(k in field.lower() for k in keywords):
                is_process = True
                break

        if is_process:
            area = zone_geo[zone_name]["floor_area"]
            if area <= 0:
                continue
            method = obj[3].lower()
            try:
                if method in ["equipmentlevel", "level"]:
                    results[zone_name] += float(obj[4]) / area
                elif method in ["watts/area", "perarea"]:
                    results[zone_name] += float(obj[5])
            except (ValueError, IndexError):
                continue

    return results
