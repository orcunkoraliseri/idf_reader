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


def get_idf_version_tuple(idf_data: dict) -> tuple[int, int]:
    """Extracts the IDF version as a tuple (major, minor).
    
    Defaults to (8, 7) if unknown, providing a global approach 
    for version-aware object parsing.
    """
    version_objs = idf_data.get("VERSION", [])
    if version_objs and version_objs[0] and len(version_objs[0]) > 0:
        v_str = str(version_objs[0][0]).strip()
        parts = v_str.split(".")
        try:
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            pass
    return 8, 7


def extract_zone_metadata(idf_data: dict) -> dict[str, dict]:
    """A global approach to extract zone metadata, adjusting for IDF versions.

    Handles structural changes between versions, such as v8.7/v22.1 using 13 fields
    versus v8.9/v23.1/v24.2 omitting the Volume and Floor Area fields.
    """
    major, minor = get_idf_version_tuple(idf_data)
    
    # Identify if the IDF version uses the simplified 7-field Zone object
    is_short_format = (major == 8 and minor >= 9) or (major >= 23)

    zone_metadata = {}
    for zone_fields in idf_data.get("ZONE", []):
        if not zone_fields:
            continue
            
        name = zone_fields[0]
        
        # Multiplier (Field 7, index 6 - consistent across all versions)
        try:
            multiplier = float(zone_fields[6]) if len(zone_fields) > 6 and str(zone_fields[6]).strip() else 1.0
        except (ValueError, IndexError):
            multiplier = 1.0
            
        volume = 0.0
        floor_area = 0.0
        ceiling_height = None
        
        if not is_short_format:
            # v8.7, v22.1 format (13 fields)
            if len(zone_fields) > 7:
                val = str(zone_fields[7]).strip().lower()
                if val not in ("autocalculate", ""):
                    try:
                        ceiling_height = float(val)
                    except ValueError:
                        pass
                        
            if len(zone_fields) > 8:
                val = str(zone_fields[8]).strip().lower()
                if val not in ("autocalculate", ""):
                    try:
                        volume = float(val)
                    except ValueError:
                        pass
                        
            if len(zone_fields) > 9:
                val = str(zone_fields[9]).strip().lower()
                if val not in ("autocalculate", ""):
                    try:
                        floor_area = float(val)
                    except ValueError:
                        pass

        zone_metadata[name] = {
            "multiplier": multiplier,
            "ceiling_height": ceiling_height,
            "volume": volume,
            "floor_area": floor_area
        }
    return zone_metadata


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


def get_schedule_max_value(idf_data: dict, schedule_name: str) -> float:
    """Attempts to find the maximum numeric value for a schedule."""
    if not schedule_name:
        return 1.0
    schedule_name_upper = schedule_name.upper()

    # Check Schedule:Constant
    for sch in idf_data.get("SCHEDULE:CONSTANT", []):
        if sch[0].upper() == schedule_name_upper:
            try:
                return float(sch[2])
            except (ValueError, IndexError):
                pass

    # Check Schedule:Compact
    max_val = 0.0
    found = False
    for sch in idf_data.get("SCHEDULE:COMPACT", []):
        if sch[0].upper() == schedule_name_upper:
            for field in sch[2:]:
                try:
                    val = float(str(field).strip())
                    max_val = max(max_val, val)
                    found = True
                except ValueError:
                    pass
            if found:
                return max_val

    # Default to 1.0 if not found
    return 1.0


# ---------------------------------------------------------------------------
# Annual-average schedule helpers
# ---------------------------------------------------------------------------

# Fraction of annual days each EnergyPlus day-type keyword represents.
_DAY_TYPE_WEIGHTS: dict[str, float] = {
    "WEEKDAYS": 5 / 7,
    "WEEKENDS": 2 / 7,
    "ALLDAYS": 1.0,
    "ALLOTHERDAYS": 2 / 7,
    "SUNDAY": 1 / 7,
    "MONDAY": 1 / 7,
    "TUESDAY": 1 / 7,
    "WEDNESDAY": 1 / 7,
    "THURSDAY": 1 / 7,
    "FRIDAY": 1 / 7,
    "SATURDAY": 1 / 7,
    # Design days / special days contribute 0 to the annual average
    "HOLIDAY": 0.0,
    "CUSTOMDAY1": 0.0,
    "CUSTOMDAY2": 0.0,
    "SUMMERDESIGNDAY": 0.0,
    "WINTERDESIGNDAY": 0.0,
}


def _day_hourly_avg(sch: list) -> float:
    """Mean of the 24 hourly values in a Schedule:Day:Hourly object."""
    vals = []
    for f in sch[2:26]:
        try:
            vals.append(float(f))
        except (ValueError, TypeError):
            pass
    return sum(vals) / len(vals) if vals else 0.0


def _day_schedule_avg(idf_data: dict, day_name: str) -> float:
    """Resolve any day-schedule by name and return its time-weighted average."""
    name_upper = day_name.strip().upper()
    for sch in idf_data.get("SCHEDULE:DAY:HOURLY", []):
        if sch[0].upper() == name_upper:
            return _day_hourly_avg(sch)
    return 0.0


def _week_compact_avg(idf_data: dict, sch: list) -> float:
    """Weighted annual average of a Schedule:Week:Compact.

    Fields after name are alternating ``For: <DayType>`` / ``<DayScheduleName>``
    pairs.  Day types are weighted by their share of the year.
    """
    fields = sch[1:]
    weighted_sum = 0.0
    total_weight = 0.0
    i = 0
    while i < len(fields) - 1:
        f = str(fields[i]).strip().upper()
        if f.startswith("FOR:"):
            day_type = f[4:].strip()
            weight = _DAY_TYPE_WEIGHTS.get(day_type, 0.0)
            day_name = str(fields[i + 1]).strip()
            day_avg = _day_schedule_avg(idf_data, day_name)
            weighted_sum += weight * day_avg
            total_weight += weight
            i += 2
        else:
            i += 1
    return weighted_sum / total_weight if total_weight > 0 else 0.0


def _week_daily_avg(idf_data: dict, sch: list) -> float:
    """Annual average of a Schedule:Week:Daily (Sunday=idx1 … Saturday=idx7)."""
    day_names = sch[1:8]
    return sum(_day_schedule_avg(idf_data, n) for n in day_names if n) / 7


def _year_schedule_avg(idf_data: dict, sch: list) -> float:
    """Annual average of a Schedule:Year, weighted by each range's day count."""
    MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    def doy(month: int, day: int) -> int:
        return sum(MONTH_DAYS[: month - 1]) + day

    weighted_sum = 0.0
    total_days = 0.0
    i = 2  # skip name and type_limits
    while i + 4 < len(sch):
        week_name = str(sch[i]).strip()
        try:
            sm, sd = int(sch[i + 1]), int(sch[i + 2])
            em, ed = int(sch[i + 3]), int(sch[i + 4])
        except (ValueError, IndexError):
            break
        days = max(1, doy(em, ed) - doy(sm, sd) + 1)

        wnu = week_name.upper()
        week_avg = 0.0
        for ws in idf_data.get("SCHEDULE:WEEK:COMPACT", []):
            if ws[0].upper() == wnu:
                week_avg = _week_compact_avg(idf_data, ws)
                break
        else:
            for ws in idf_data.get("SCHEDULE:WEEK:DAILY", []):
                if ws[0].upper() == wnu:
                    week_avg = _week_daily_avg(idf_data, ws)
                    break

        weighted_sum += week_avg * days
        total_days += days
        i += 5

    return weighted_sum / total_days if total_days > 0 else 0.0


def _compact_schedule_avg(sch: list) -> float:
    """Time-weighted average of a Schedule:Compact.

    Parses ``Until: HH:MM`` / value pairs inside each ``For:`` block and
    computes a time-weighted mean per block, then returns the mean across
    all blocks (equal-weight approximation suitable for annual averages).
    """
    fields = sch[2:]  # skip name and type_limits
    block_avgs: list[float] = []
    prev_min = 0.0
    weighted_sum = 0.0
    total_min = 0.0
    in_block = False

    i = 0
    while i < len(fields):
        f = str(fields[i]).strip()
        fu = f.upper()

        if "THROUGH:" in fu:
            i += 1
            continue

        if "FOR:" in fu:
            if in_block and total_min > 0:
                block_avgs.append(weighted_sum / total_min)
            prev_min = 0.0
            weighted_sum = 0.0
            total_min = 0.0
            in_block = True
            i += 1
            continue

        if "UNTIL:" in fu:
            time_str = fu.replace("UNTIL:", "").strip()
            parts = time_str.split(":")
            try:
                h = int(parts[0])
                m = int(parts[1]) if len(parts) > 1 else 0
                until_min = h * 60 + m
                if i + 1 < len(fields):
                    val = float(str(fields[i + 1]).strip())
                    duration = until_min - prev_min
                    if duration > 0:
                        weighted_sum += val * duration
                        total_min += duration
                    prev_min = until_min
                    i += 2
                    continue
            except (ValueError, IndexError):
                pass
            i += 1
            continue

        i += 1

    if in_block and total_min > 0:
        block_avgs.append(weighted_sum / total_min)

    return sum(block_avgs) / len(block_avgs) if block_avgs else 0.0


def compute_schedule_annual_average(idf_data: dict, schedule_name: str) -> float:
    """Return the annual time-weighted average value of any EnergyPlus schedule.

    Resolves Schedule:Constant, Schedule:Compact, Schedule:Year,
    Schedule:Week:Compact, Schedule:Week:Daily, and Schedule:Day:Hourly.
    Falls back to 1.0 if the schedule cannot be resolved.
    """
    if not schedule_name:
        return 1.0
    name_upper = schedule_name.strip().upper()

    for sch in idf_data.get("SCHEDULE:CONSTANT", []):
        if sch[0].upper() == name_upper:
            try:
                return float(sch[2])
            except (ValueError, IndexError):
                return 1.0

    for sch in idf_data.get("SCHEDULE:COMPACT", []):
        if sch[0].upper() == name_upper:
            return _compact_schedule_avg(sch)

    for sch in idf_data.get("SCHEDULE:YEAR", []):
        if sch[0].upper() == name_upper:
            return _year_schedule_avg(idf_data, sch)

    for sch in idf_data.get("SCHEDULE:WEEK:COMPACT", []):
        if sch[0].upper() == name_upper:
            return _week_compact_avg(idf_data, sch)

    for sch in idf_data.get("SCHEDULE:WEEK:DAILY", []):
        if sch[0].upper() == name_upper:
            return _week_daily_avg(idf_data, sch)

    for sch in idf_data.get("SCHEDULE:DAY:HOURLY", []):
        if sch[0].upper() == name_upper:
            return _day_hourly_avg(sch)

    return 1.0


def get_zone_from_space(space_name: str, idf_data: dict) -> str | None:
    """Helper to find the zone name associated with a space name (v22.1+)."""
    for space in idf_data.get("SPACE", []):
        if not space:
            continue
        if space[0].upper() == space_name.upper():
            if len(space) > 1:
                return space[1]
    return None


def resolve_target_to_zones(target_name: str, idf_data: dict, zone_geo: dict) -> list[str]:
    """A global approach to resolve a Zone, Space, ZoneList, or SpaceList name 
    into a list of underlying Zone names, supporting newer IDF versions (v22.1+)."""
    target_upper = target_name.upper()
    resolved_zones = []
    
    # 1. Is it directly a Zone? (O(N) search to be case-insensitive)
    for zn in zone_geo:
        if zn.upper() == target_upper:
            return [zn]
            
    # 2. Is it a ZoneList?
    for zl in idf_data.get("ZONELIST", []):
        if not zl:
            continue
        if zl[0].upper() == target_upper:
            for zn_candidate in zl[1:]:
                if not zn_candidate:
                    continue
                zc_upper = zn_candidate.upper()
                for zn in zone_geo:
                    if zn.upper() == zc_upper and zn not in resolved_zones:
                        resolved_zones.append(zn)
            if resolved_zones:
                return resolved_zones
                
    # 3. Is it a Space? (v22.1+)
    for space in idf_data.get("SPACE", []):
        if not space:
            continue
        if space[0].upper() == target_upper:
            if len(space) > 1:
                zn_name = space[1].upper()
                for zn in zone_geo:
                    if zn.upper() == zn_name:
                        return [zn]

    # 4. Is it a SpaceList? (v22.1+)
    for sl in idf_data.get("SPACELIST", []):
        if not sl:
            continue
        if sl[0].upper() == target_upper:
            for sp_candidate in sl[1:]:
                if not sp_candidate:
                    continue
                zn_name = get_zone_from_space(sp_candidate, idf_data)
                if zn_name:
                    zn_upper = zn_name.upper()
                    for zn in zone_geo:
                        if zn.upper() == zn_upper and zn not in resolved_zones:
                            resolved_zones.append(zn)
            if resolved_zones:
                return resolved_zones
    
    return []


def extract_people(idf_data: dict, zone_geo: dict) -> dict[str, float]:
    """Extracts occupancy density (people/m2) using version-aware target resolution."""
    results = {name: 0.0 for name in zone_geo}
    for obj in idf_data.get("PEOPLE", []):
        if len(obj) < 3:
            continue
            
        target_name = obj[1]
        target_zones = resolve_target_to_zones(target_name, idf_data, zone_geo)
        
        if not target_zones:
            continue

        method = obj[3].lower()
        
        # Calculate total valid area of the resolved zones
        total_target_area = sum(zone_geo[zn]["floor_area"] for zn in target_zones if zone_geo[zn]["floor_area"] > 0)
        if total_target_area <= 0:
            continue

        try:
            if method == "people":
                # field 5: Number of People
                absolute_people = float(obj[4])
                # Distribute count proportionally to constituent zone sizes
                for zn in target_zones:
                    zn_area = zone_geo[zn]["floor_area"]
                    if zn_area > 0:
                        allocated_people = absolute_people * (zn_area / total_target_area)
                        results[zn] += allocated_people / zn_area
            elif method in ["people/area", "perarea", "people/floorarea"]:
                # field 6: People per Floor Area
                for zn in target_zones:
                    results[zn] += float(obj[5])
            elif method in ["area/person", "perperson", "floorarea/person"]:
                # field 7: Floor Area per Person
                val = float(obj[6])
                if val > 0:
                    for zn in target_zones:
                        results[zn] += 1.0 / val
        except (ValueError, IndexError):
            continue
    return results


def extract_loads(
    idf_data: dict, zone_geo: dict, obj_key: str, subcat_filter: str | None = None, exclude_subcat_filter: str | None = None
) -> dict[str, float]:
    """Helper to extract Lights or Equipment loads (W/m2) using version-aware target resolution."""
    results = {name: 0.0 for name in zone_geo}
    for obj in idf_data.get(obj_key.upper(), []):
        if len(obj) < 3:
            continue
            
        target_name = obj[1]
        target_zones = resolve_target_to_zones(target_name, idf_data, zone_geo)
        
        if not target_zones:
            continue

        # Optional filters by subcategory
        if subcat_filter or exclude_subcat_filter:
            subcat = obj[-1].lower() if obj else ""
            if subcat_filter and subcat_filter not in subcat:
                continue
            if exclude_subcat_filter and exclude_subcat_filter in subcat:
                continue

        method = obj[3].lower()
        
        total_target_area = sum(zone_geo[zn]["floor_area"] for zn in target_zones if zone_geo[zn]["floor_area"] > 0)
        if total_target_area <= 0:
            continue

        try:
            if method in ["lightinglevel", "equipmentlevel", "level"]:
                # field 5 in IDF
                absolute_load = float(obj[4])
                # Distribute load proportionally to constituent zone sizes
                for zn in target_zones:
                    zn_area = zone_geo[zn]["floor_area"]
                    if zn_area > 0:
                        allocated_load = absolute_load * (zn_area / total_target_area)
                        results[zn] += allocated_load / zn_area
            elif method in ["watts/area", "perarea", "watts/floorarea"]:
                # field 6 in IDF
                val = float(obj[5])
                for zn in target_zones:
                    results[zn] += val
            elif method in ["watts/person", "perperson"]:
                # field 7 in IDF (needs occupancy relation, presently unimplemented)
                pass
        except (ValueError, IndexError):
            continue
    return results


def extract_water_use(idf_data: dict, zone_geo: dict) -> dict[str, dict[str, float]]:
    """Extracts SHW usage (L/h.m2) and Target Temperature (C) using version-aware logic."""

    results = {name: {"avg_lh_m2": 0.0, "target_temp_c": 0.0} for name in zone_geo}
    zones_with_water_use = set()  # Track zones to prevent double-counting
    for obj in idf_data.get("WATERUSE:EQUIPMENT", []):
        if len(obj) < 3:
            continue

        # Field 8 (index 7) is the Zone Name in the full 10-field
        # format.  Try it regardless of version because some files
        # retain the long form even for newer EnergyPlus versions.
        zone_name = ""
        if len(obj) >= 8 and obj[7].strip():
            candidate = obj[7].strip()
            if candidate in zone_geo:
                zone_name = candidate

        # For short formats, or if field 8 was omitted, we fallback to heuristics
        if not zone_name or zone_name not in zone_geo:
            # Heuristic for residential: match equipment name to
            # the living zone sharing the longest common prefix
            # or suffix.  Prefix handles clusters like
            # 17_24_living_unit1 <- 17_24_Sinks_unit1.  Suffix
            # handles multi-family like living_unit1_FrontRow
            # <- Clothes Washer_unit1_FrontRow.
            obj_name_upper = obj[0].upper()
            best_zone = ""
            best_score = 0
            for zn in zone_geo:
                zn_upper = zn.upper()
                if "LIVING" not in zn_upper:
                    continue
                # Longest common prefix
                plen = 0
                for c1, c2 in zip(
                    obj_name_upper, zn_upper
                ):
                    if c1 == c2:
                        plen += 1
                    else:
                        break
                # Longest common suffix
                slen = 0
                for c1, c2 in zip(
                    reversed(obj_name_upper),
                    reversed(zn_upper),
                ):
                    if c1 == c2:
                        slen += 1
                    else:
                        break
                score = plen + slen
                if score > best_score:
                    best_score = score
                    best_zone = zn

            if best_zone and best_score >= 3:
                zone_name = best_zone

            # Fallback: if still no match and there's only one
            # living zone, use it
            if not zone_name:
                living_zones = [
                    zn for zn in zone_geo
                    if "LIVING" in zn.upper()
                ]
                if len(living_zones) == 1:
                    zone_name = living_zones[0]

        if not zone_name or zone_name not in zone_geo:
            continue

        area = zone_geo[zone_name]["floor_area"]
        if area <= 0:
            continue

        # For multi-story residential zones (e.g. detached house), normalize SHW
        # by footprint area rather than total floor area. DHW demand is per
        # dwelling-unit, not per floor — the same fixtures serve the whole unit
        # regardless of how many stories it spans.
        story_count = zone_geo[zone_name].get("story_count", 1)
        if story_count > 1:
            area = area / story_count

        try:
            # field 3: Peak Flow Rate {m3/s} (index 2)
            peak_m3s = float(obj[2])

            # field 4: Flow Rate Fraction Schedule Name (index 3)
            flow_sched = obj[3].strip() if len(obj) > 3 and obj[3] else ""

            # Special case: AlwaysOff means the fixture is explicitly disabled in this
            # zone (e.g. ASHRAE prototype Hotel rooms that share SHW via another zone).
            # Treat as zero — consistent with original behaviour and the Hotel Small doc.
            if flow_sched.lower() == "alwaysoff":
                continue

            # For non-residential (WaterUse:Equipment) report PEAK design intensity.
            # The schedule controls *when* hot water is drawn — it is a temporal pattern,
            # not a sizing parameter. Peak flow rate is what ASHRAE 90.1 defines as the
            # SHW design value. Multiplying by avg_fraction converts to annual-average
            # consumption, which is schedule-dependent and ~10× lower for offices.
            results[zone_name]["avg_lh_m2"] += (peak_m3s * 3600000) / area

            # field 5: Target Temperature Schedule Name (index 4)
            if len(obj) > 4 and obj[4]:
                temp_c = resolve_schedule_value(idf_data, obj[4])
                if temp_c is not None:
                    # Often there are multiple SHW objects per zone; take the max target temperature
                    if temp_c > results[zone_name]["target_temp_c"]:
                        results[zone_name]["target_temp_c"] = temp_c
            
            # Record that this zone has been successfully processed via WATERUSE:EQUIPMENT
            zones_with_water_use.add(zone_name)
        except (ValueError, IndexError):
            continue

    # 2. Add support for WATERHEATER:MIXED (used in MidRise Apartment)
    for obj in idf_data.get("WATERHEATER:MIXED", []):
        if len(obj) < 28:
            continue
        
        # Mapping via Ambient Temperature Zone Name (common in residential)
        # Field 20 (index 19) is Indicator. Field 22 (index 21) is Zone Name.
        zone_name = ""
        if obj[19].lower() == "zone":
            zone_name = obj[21]
        
        if not zone_name or zone_name not in zone_geo:
            continue
        
        # If this zone already has data from WATERUSE:EQUIPMENT, skip this object to avoid double-counting
        if zone_name in zones_with_water_use:
            continue

        area = zone_geo[zone_name]["floor_area"]
        if area <= 0:
            continue

        try:
            # field 28: Peak Use Flow Rate {m3/s} (index 27)
            peak_m3s = float(obj[27])
            if peak_m3s > 0:
                # field 29: Use Flow Rate Fraction Schedule Name (index 28)
                flow_sched = obj[28].strip() if len(obj) > 28 and obj[28] else ""
                avg_fraction = compute_schedule_annual_average(idf_data, flow_sched) if flow_sched else 1.0

                # Heuristic: MidRise apartments physically double the peak capacity of the middle floor ("M ")
                # water heaters to simulate stacking 2 floors, instead of using a standard zone multiplier.
                # To get the accurate per-floor SHW density (L/h.m2), we normalize it.
                if "Apartment" in zone_name and zone_name.startswith("M ") and peak_m3s > 5e-6:
                    peak_m3s /= 2.0

                # Residential (WaterHeater:Mixed): keep avg_fraction — the tank peak capacity
                # is a physical limit, not a design-intensity target. The schedule fraction
                # reflects actual occupant draw patterns and is meaningful for residential.
                results[zone_name]["avg_lh_m2"] += (peak_m3s * avg_fraction * 3600000) / area
            
                # field 3: Setpoint Temperature Schedule Name (index 2)
                if len(obj) > 2 and obj[2]:
                    target_val = resolve_schedule_value(idf_data, obj[2])
                    if target_val is not None:
                        if target_val > results[zone_name]["target_temp_c"]:
                            results[zone_name]["target_temp_c"] = target_val
        except (ValueError, IndexError):
            continue

    # 3. Post-process to fix 10x typos in WATERUSE:EQUIPMENT
    max_density = 0.0
    for z in results:
        if results[z]["avg_lh_m2"] > max_density:
            max_density = results[z]["avg_lh_m2"]

    if max_density > 0:
        for z in results:
            density = results[z]["avg_lh_m2"]
            if density > 0:
                ratio = max_density / density
                if 9.9 <= ratio <= 10.1:
                    results[z]["avg_lh_m2"] = max_density

    return results


def extract_infiltration(idf_data: dict, zone_geo: dict) -> dict[str, float]:
    """Extracts infiltration (m3/s per m2 facade)."""
    results = {name: 0.0 for name in zone_geo}
    for obj in idf_data.get("ZONEINFILTRATION:DESIGNFLOWRATE", []):
        if len(obj) < 3:
            continue
        # Skip door infiltration based on object name
        if "door" in obj[0].lower():
            continue
            
        target_name = obj[1]
        target_zones = resolve_target_to_zones(target_name, idf_data, zone_geo)
        
        if not target_zones:
            continue

        method = obj[3].lower()
        
        # Pre-compute norm_area for each targeted zone
        zones_norm_area = {}
        for zn in target_zones:
            facade_area = zone_geo[zn]["facade_area"]
            exterior_roof = zone_geo[zn].get("exterior_roof_area", 0.0)
            floor_area = zone_geo[zn]["floor_area"]
            
            exterior_area = facade_area + exterior_roof
            
            norm_area = exterior_area
            if exterior_area <= 0 or (floor_area > 0 and exterior_area < 0.05 * floor_area):
                norm_area = floor_area
                
            zones_norm_area[zn] = norm_area

        total_target_norm_area = sum(zones_norm_area[zn] for zn in target_zones if zones_norm_area[zn] > 0)
        
        if total_target_norm_area <= 0:
            continue

        try:
            if method in ["flow/zone", "level"]:
                absolute_m3s = float(obj[4])
                for zn in target_zones:
                    n_area = zones_norm_area[zn]
                    if n_area > 0:
                        allocated_m3s = absolute_m3s * (n_area / total_target_norm_area)
                        results[zn] += allocated_m3s / n_area
            elif method in ["flow/area", "flow/floorarea", "flowrate/floorarea"]:
                # Value is per unit of floor area
                val = float(obj[5])
                for zn in target_zones:
                    n_area = zones_norm_area[zn]
                    if n_area > 0:
                        results[zn] += (val * zone_geo[zn]["floor_area"]) / n_area
            elif method in ["flow/exteriorwallarea", "flowrate/exteriorwallarea"]:
                # Value is per unit of exterior wall area
                val = float(obj[6])
                for zn in target_zones:
                    n_area = zones_norm_area[zn]
                    if n_area > 0:
                        results[zn] += (val * zone_geo[zn]["facade_area"]) / n_area
            elif method in ["flow/exteriorarea", "flowrate/exteriorsurfacearea", "flow/exteriorsurfacearea"]:
                # Value is per m2 of total exterior surface (walls + roof).
                val = float(obj[6])
                for zn in target_zones:
                    n_area = zones_norm_area[zn]
                    if n_area > 0:
                        ext_area = zone_geo[zn]["facade_area"] + zone_geo[zn].get("exterior_roof_area", 0.0)
                        results[zn] += (val * ext_area) / n_area
            elif method == "airchanges/hour":
                # ACH * Volume / 3600
                ach = float(obj[7])
                for zn in target_zones:
                    n_area = zones_norm_area[zn]
                    volume = zone_geo[zn]["volume"]
                    if n_area > 0 and volume > 0:
                        m3s = (ach * volume) / 3600
                        results[zn] += m3s / n_area
        except (ValueError, IndexError):
            continue

    # Add support for EFFECTIVELEAKAGEAREA (common in residential)
    # Estimate flow at 4Pa: V [m3/s] = ELA [m2] * 1.0 * sqrt(2 * 4 / 1.2) approx ELA * 2.58
    for obj in idf_data.get("ZONEINFILTRATION:EFFECTIVELEAKAGEAREA", []):
        if len(obj) < 4:
            continue
        zone_name = obj[1]
        if zone_name not in zone_geo:
            continue
        facade_area = zone_geo[zone_name]["facade_area"]
        exterior_roof = zone_geo[zone_name].get("exterior_roof_area", 0.0)
        exterior_area = facade_area + exterior_roof
        
        norm_area = exterior_area if exterior_area > 0 else zone_geo[zone_name]["floor_area"]
        if norm_area <= 0:
            continue
        try:
            ela_m2 = float(obj[3])
            # If ELA is > 1.0, it's almost certainly in cm2 (typical m2 values are < 0.1)
            if ela_m2 > 1.0:
                ela_m2 /= 10000.0
            results[zone_name] += (ela_m2 * 2.58) / norm_area
        except (ValueError, IndexError):
            continue

    # Add support for AIRFLOWNETWORK
    # Map AirflowNetwork Leakage Components -> Effective Leakage Area
    afn_ela = {}
    for obj in idf_data.get("AIRFLOWNETWORK:MULTIZONE:SURFACE:EFFECTIVELEAKAGEAREA", []):
        if len(obj) < 2:
            continue
        # Skip intentional vents (e.g. ATTICVENT, CRAWLVENT) which inflate infiltration
        if "VENT" in obj[0].upper():
            continue
        try:
            # Field 2 is ELA. Field 3 is Discharge Coefficient.
            ela_m2 = float(obj[1])
            # If ELA is > 1.0, it's likely in cm2
            if ela_m2 > 1.0:
                ela_m2 /= 10000.0
            afn_ela[obj[0].upper()] = ela_m2
        except (ValueError, IndexError):
            continue

    # Map AirflowNetwork Surfaces -> Zone Name
    # BuildingSurface:Detailed map: Surface Name -> Zone Name
    surf_to_zone = {}
    for obj in idf_data.get("BUILDINGSURFACE:DETAILED", []):
        if len(obj) > 4:
            surf_to_zone[obj[0].upper()] = obj[3]  # Standard position for zone name if field 4 is not boundary
            # Handle EnergyPlus 8.x vs 9.x difference (Space Name field)
            if obj[4].strip().lower() in ["outdoors", "ground", "surface", "zone", "othersidecoefficients", "othersideconditionsmodel", "adiabatic", "foundation"]:
                surf_to_zone[obj[0].upper()] = obj[3] # 8.x
            elif len(obj) > 5:
                surf_to_zone[obj[0].upper()] = obj[3] # 9.x (Zone name is still at pos 3, Space is at pos 4)

    # Process AirflowNetwork Surfaces to assign ELA to zones
    for obj in idf_data.get("AIRFLOWNETWORK:MULTIZONE:SURFACE", []):
        if len(obj) < 2:
            continue
        surf_name = obj[0].upper()
        leakage_comp_name = obj[1].upper()
        
        zone_name = surf_to_zone.get(surf_name)
        if not zone_name or zone_name not in zone_geo:
            # Fallback heuristic: Try to find substring match for zone (e.g. Roof_unit1 -> unit1)
            for zn in zone_geo:
                if zn.upper() in surf_name:
                    zone_name = zn
                    break
        
        if not zone_name or zone_name not in zone_geo:
            continue

        ela_m2 = afn_ela.get(leakage_comp_name, 0.0)
        if ela_m2 <= 0:
            continue

        facade_area = zone_geo[zone_name]["facade_area"]
        exterior_roof = zone_geo[zone_name].get("exterior_roof_area", 0.0)
        floor_area = zone_geo[zone_name]["floor_area"]
        
        # Total exterior surface area (Face + Roof)
        exterior_area = facade_area + exterior_roof
        
        # Norm area logic: Prefer exterior area, but fallback to floor area if 
        # exterior area is 0 or disproportionately small (< 5% of floor area)
        # to avoid massive inflation of values in basement/attic zones.
        norm_area = exterior_area
        if exterior_area <= 0 or (floor_area > 0 and exterior_area < 0.05 * floor_area):
            norm_area = floor_area
            
        if norm_area <= 0:
            continue

        # Add to results
        results[zone_name] += (ela_m2 * 2.58) / norm_area

    return results


def extract_ventilation(idf_data: dict, zone_geo: dict) -> dict[str, dict[str, float]]:
    """Extracts ventilation metrics ([m3/s/person], [m3/s/m2], and [ACH]) using a global evaluation approach."""
    results = {name: {"per_person": 0.0, "per_area": 0.0, "ach": 0.0} for name in zone_geo}
    
    # Needs occupancy density to convert absolute metrics to per_person metrics
    people_density = extract_people(idf_data, zone_geo) # People per m2

    # 1. Support for DESIGNSPECIFICATION:OUTDOORAIR
    for obj in idf_data.get("DESIGNSPECIFICATION:OUTDOORAIR", []):
        if len(obj) < 2:
            continue
            
        name = obj[0].upper()
        
        # 1. Attempt exact match after stripping common prefixes
        stripped_name = name.replace("SZ DSOA ", "").replace("SZ DSOA", "").strip()
        matched_zone = None
        
        for zn in zone_geo:
            if zn.upper() == stripped_name:
                matched_zone = zn
                break
                
        # 2. Fallback to robust substring matching
        if not matched_zone:
            search_name = name.replace("_", "").replace(" ", "").replace("SZDSOA", "")
            best_len = 0
            for zn in zone_geo:
                clean_zn = zn.upper().replace("_", "").replace(" ", "")
                if (clean_zn in search_name or search_name in clean_zn) and len(zn) > best_len:
                    matched_zone = zn
                    best_len = len(zn)

        if not matched_zone:
            continue

        method = obj[1].lower() if len(obj) > 1 else ""
        area = zone_geo[matched_zone]["floor_area"]
        volume = zone_geo[matched_zone]["volume"]
        occupants = people_density.get(matched_zone, 0.0) * area

        try:
            flow_per_person = float(obj[2]) if len(obj) > 2 and obj[2] else 0.0
            flow_per_area = float(obj[3]) if len(obj) > 3 and obj[3] else 0.0
            flow_zone = float(obj[4]) if len(obj) > 4 and obj[4] else 0.0
            ach = float(obj[5]) if len(obj) > 5 and obj[5] else 0.0

            # Compute actual flows depending on the method
            active_methods = [method] if method not in ("sum", "maximum") else ["flow/person", "flow/area", "flow/zone", "airchanges/hour"]
            
            if "flow/person" in active_methods and occupants > 0:
                results[matched_zone]["per_person"] += flow_per_person
            
            if "flow/area" in active_methods and area > 0:
                results[matched_zone]["per_area"] += flow_per_area
                
            if "flow/zone" in active_methods and area > 0:
                results[matched_zone]["per_area"] += flow_zone / area
                    
            if "airchanges/hour" in active_methods and volume > 0:
                results[matched_zone]["ach"] += ach

        except (ValueError, IndexError):
            continue

    # 2. Add support for ZONEVENTILATION:DESIGNFLOWRATE
    for obj in idf_data.get("ZONEVENTILATION:DESIGNFLOWRATE", []):
        if len(obj) < 4:
            continue
            
        target_name = obj[1]
        target_zones = resolve_target_to_zones(target_name, idf_data, zone_geo)
        
        if not target_zones:
            continue
            
        method = obj[3].upper()
        
        # Calculate total target dimensions
        total_target_area = sum(zone_geo[zn]["floor_area"] for zn in target_zones if zone_geo[zn]["floor_area"] > 0)
        total_target_volume = sum(zone_geo[zn]["volume"] for zn in target_zones if zone_geo[zn]["volume"] > 0)
        
        try:
            if method == "FLOW/ZONE":
                if len(obj) > 4 and obj[4] and total_target_area > 0:
                    absolute_flow = float(obj[4])
                    for zn in target_zones:
                        zn_area = zone_geo[zn]["floor_area"]
                        if zn_area > 0:
                            allocated_flow = absolute_flow * (zn_area / total_target_area)
                            results[zn]["per_area"] += allocated_flow / zn_area
            elif method in ["FLOW/AREA", "FLOWRATE/FLOORAREA"]:
                if len(obj) > 5 and obj[5]:
                    val = float(obj[5])
                    for zn in target_zones:
                        if zone_geo[zn]["floor_area"] > 0:
                            results[zn]["per_area"] += val
            elif method == "FLOW/PERSON":
                if len(obj) > 6 and obj[6]:
                    val = float(obj[6])
                    for zn in target_zones:
                        results[zn]["per_person"] += val
            elif method == "AIRCHANGES/HOUR":
                if len(obj) > 7 and obj[7]:
                    ach = float(obj[7])
                    for zn in target_zones:
                        results[zn]["ach"] += ach
        except (ValueError, IndexError):
            continue

    # 3. Add support for AIRFLOWNETWORK Natural Ventilation (Intentional Vents)
    # Map AirflowNetwork Leakage Components -> ELA (only for Vents)
    afn_vent_ela = {}
    for obj in idf_data.get("AIRFLOWNETWORK:MULTIZONE:SURFACE:EFFECTIVELEAKAGEAREA", []):
        if len(obj) < 2:
            continue
        # Intentional vents (e.g. ATTICVENT, CRAWLVENT)
        if "VENT" in obj[0].upper():
            try:
                ela_m2 = float(obj[1])
                if ela_m2 > 1.0:
                    ela_m2 /= 10000.0
                afn_vent_ela[obj[0].upper()] = ela_m2
            except (ValueError, IndexError):
                continue

    if afn_vent_ela:
        # BuildingSurface:Detailed map: Surface Name -> Zone Name
        surf_to_zone = {}
        for obj in idf_data.get("BUILDINGSURFACE:DETAILED", []):
            if len(obj) > 4:
                surf_to_zone[obj[0].upper()] = obj[3]
                if obj[4].strip().lower() in ["outdoors", "ground", "surface", "zone", "foundation"]:
                    surf_to_zone[obj[0].upper()] = obj[3]

        # Process AirflowNetwork Surfaces to assign vent flow to zones
        for obj in idf_data.get("AIRFLOWNETWORK:MULTIZONE:SURFACE", []):
            if len(obj) < 2:
                continue
            surf_name = obj[0].upper()
            leakage_comp_name = obj[1].upper()
            
            zone_name = surf_to_zone.get(surf_name)
            if not zone_name or zone_name not in zone_geo:
                # Fallback substring match
                for zn in zone_geo:
                    if zn.upper() in surf_name:
                        zone_name = zn
                        break
            
            if not zone_name or zone_name not in zone_geo:
                continue

            ela_m2 = afn_vent_ela.get(leakage_comp_name, 0.0)
            if ela_m2 <= 0:
                continue

            # For intentional vents in unconditioned spaces, calculate ACH
            volume = zone_geo[zone_name].get("volume", 0.0)
            if volume > 0:
                # ACH = (m3/s at 4Pa * 3600) / volume
                results[zone_name]["ach"] += (ela_m2 * 2.58 * 3600) / volume
            else:
                # Fallback to per_area if volume is missing (e.g. old IDFs)
                facade_area = zone_geo[zone_name]["facade_area"]
                exterior_roof = zone_geo[zone_name].get("exterior_roof_area", 0.0)
                floor_area = zone_geo[zone_name]["floor_area"]
                
                exterior_area = facade_area + exterior_roof
                norm_area = exterior_area
                if exterior_area <= 0 or (floor_area > 0 and exterior_area < 0.05 * floor_area):
                    norm_area = floor_area
                
                if norm_area > 0:
                    results[zone_name]["per_area"] += (ela_m2 * 2.58) / norm_area

    return results



def extract_thermostats(idf_data: dict, zone_geo: dict) -> dict[str, dict[str, float]]:
    """Extracts heating and cooling setpoints (°C) using version-aware targeting and occupied design evaluation."""
    results = {name: {"heating": 0.0, "cooling": 0.0} for name in zone_geo}

    # Helper to find occupied/design values across different schedule patterns
    def get_design_setpoint(schedule_name: str, is_heating: bool) -> float | None:
        if not schedule_name:
            return None
        sch_upper = schedule_name.upper()
        
        # Check Schedule:Constant
        for sch in idf_data.get("SCHEDULE:CONSTANT", []):
            if sch[0].upper() == sch_upper:
                try:
                    return float(sch[2])
                except (ValueError, IndexError):
                    pass
                    
        # Check Schedule:Compact
        vals = []
        for sch in idf_data.get("SCHEDULE:COMPACT", []):
            if sch[0].upper() == sch_upper:
                for field in sch[2:]:
                    f_str = field.strip()
                    try:
                        vals.append(float(f_str))
                    except ValueError:
                        pass
        if vals:
            # For time-varying heating schedules: the occupied period is the highest temp
            # For time-varying cooling schedules: the occupied period is the lowest temp
            return max(vals) if is_heating else min(vals)
            
        return None

    for obj in idf_data.get("ZONECONTROL:THERMOSTAT", []):
        if len(obj) < 2:
            continue
            
        target_name = obj[1]
        target_zones = resolve_target_to_zones(target_name, idf_data, zone_geo)
        
        if not target_zones:
            continue

        # Look at the Control types (fields 4, 6, 8...)
        for i in range(3, len(obj), 2):
            control_type = obj[i].upper()
            control_name = obj[i + 1]

            if control_type == "THERMOSTATSETPOINT:DUALSETPOINT":
                for sp in idf_data.get("THERMOSTATSETPOINT:DUALSETPOINT", []):
                    if sp[0].upper() == control_name.upper():
                        h = get_design_setpoint(sp[1] if len(sp) > 1 else "", is_heating=True)
                        c = get_design_setpoint(sp[2] if len(sp) > 2 else "", is_heating=False)
                        for zn in target_zones:
                            if h is not None:
                                results[zn]["heating"] = h
                            if c is not None:
                                results[zn]["cooling"] = c
            elif control_type == "THERMOSTATSETPOINT:SINGLEHEATING":
                for sp in idf_data.get("THERMOSTATSETPOINT:SINGLEHEATING", []):
                    if sp[0].upper() == control_name.upper():
                        h = get_design_setpoint(sp[1] if len(sp) > 1 else "", is_heating=True)
                        for zn in target_zones:
                            if h is not None:
                                results[zn]["heating"] = h
            elif control_type == "THERMOSTATSETPOINT:SINGLECOOLING":
                for sp in idf_data.get("THERMOSTATSETPOINT:SINGLECOOLING", []):
                    if sp[0].upper() == control_name.upper():
                        c = get_design_setpoint(sp[1] if len(sp) > 1 else "", is_heating=False)
                        for zn in target_zones:
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


def extract_hvac_systems(idf_data: dict, zone_names: list[str]) -> dict[str, dict[str, str]]:
    """Extracts HVAC templates, economizer limits, and DCV settings.
    
    Args:
        idf_data: Parsed IDF dictionary.
        zone_names: List of zone names.
        
    Returns:
        A dictionary mapping zone names to their HVAC template, dcv, and economizer types.
    """
    conditioned_zones = set()
    for obj in idf_data.get("ZONECONTROL:THERMOSTAT", []):
        if len(obj) >= 2:
            conditioned_zones.add(obj[1])

    zone_equip_list = {}
    for obj in idf_data.get("ZONEHVAC:EQUIPMENTCONNECTIONS", []):
        if len(obj) > 4:
            zone_equip_list[obj[0]] = obj[1]

    equip_list_objects = {}
    for obj in idf_data.get("ZONEHVAC:EQUIPMENTLIST", []):
        if len(obj) >= 2:
            name = obj[0]
            types_names = []
            # Start at index 1 to support both EnergyPlus 8.x (equipment type
            # at field[1]) and 22.x (optional LoadDistributionScheme at
            # field[1] then types at field[2]+). The startswith checks skip
            # numeric/sequence fields safely.
            for i in range(1, len(obj) - 1):
                part = str(obj[i]).upper()
                if (
                    part.startswith("ZONEHVAC:")
                    or part.startswith("AIRTERMINAL:")
                    or part.startswith("FAN:")
                ):
                    types_names.append((obj[i], obj[i + 1]))
            equip_list_objects[name] = types_names

    controller_oa = idf_data.get("CONTROLLER:OUTDOORAIR", [])
    mech_vent = idf_data.get("CONTROLLER:MECHANICALVENTILATION", [])
    zone_mixers = idf_data.get("AIRLOOPHVAC:ZONEMIXER", [])
    zone_splitters = idf_data.get("AIRLOOPHVAC:ZONESPLITTER", [])

    # Global building-level checks to refine Honeybee templates (e.g., Boiler, Chiller, District loops)
    has_boiler = "BOILER:HOTWATER" in idf_data
    has_district_htg = ("DISTRICTHEATING" in idf_data) or ("DISTRICTHEATING:WATER" in idf_data)
    has_district_clg = ("DISTRICTCOOLING" in idf_data) or ("DISTRICTCOOLING:WATER" in idf_data)
    
    has_ac_chiller = False
    has_chiller = False
    for c in idf_data.get("CHILLER:ELECTRIC:EIR", []) + idf_data.get("CHILLER:ELECTRIC", []):
        has_chiller = True
        if any("AIRCOOLED" in str(val).upper().replace(" ", "") for val in c):
            has_ac_chiller = True
            
    has_gas_coil = ("COIL:HEATING:FUEL" in idf_data) or ("COIL:HEATING:GAS" in idf_data)
    has_elec_coil = "COIL:HEATING:ELECTRIC" in idf_data
    has_hp_coil = ("COIL:HEATING:DX:SINGLEMIXED" in idf_data) or ("COIL:HEATING:DX:SINGLESPEED" in idf_data) or ("COIL:HEATING:DX:MULTISPEED" in idf_data)
    has_baseboard = ("ZONEHVAC:BASEBOARD:CONVECTIVE:WATER" in idf_data) or ("ZONEHVAC:BASEBOARD:CONVECTIVE:ELECTRIC" in idf_data)
    has_dx_cooling = (
        "COIL:COOLING:DX:TWOSPEED" in idf_data
        or "COIL:COOLING:DX:SINGLESPEED" in idf_data
        or "COIL:COOLING:DX:MULTISPEED" in idf_data
        or "COIL:COOLING:DX:VARIABLESPEED" in idf_data
        # EnergyPlus 8.x uses CoilSystem:Cooling:DX as a wrapper —
        # treat its presence as equivalent to a DX cooling coil.
        or "COILSYSTEM:COOLING:DX" in idf_data
    )

    # Resolve specific VAV Base (System 7/8: chilled water cooling)
    vav_cool = "DCW" if has_district_clg else ("ACChiller" if has_ac_chiller else "Chiller")
    if has_district_htg:
        vav_heat = "DHW"
    elif has_boiler:
        vav_heat = "Boiler"
    elif has_hp_coil:
        vav_heat = "ASHP"
    elif has_gas_coil:
        vav_heat = "GasCoil"
    else:
        vav_heat = "PFP" 
    vav_template_base = f"VAV_{vav_cool}_{vav_heat}"

    # Resolve specific PVAV Base (System 5/6: DX cooling)
    if has_district_htg:
        pvav_heat = "DHW"
    elif has_boiler:
        pvav_heat = "Boiler"
    elif has_hp_coil:
        pvav_heat = "ASHP"
    elif has_gas_coil:
        pvav_heat = "BoilerElectricReheat"
    else:
        pvav_heat = "PFP"
    pvav_template_base = f"PVAV_{pvav_heat}"

    # Resolve specific PSZ Base
    psz_template_base = "PSZAC"
    if has_district_htg:
        psz_template_base = "PSZAC_DHWBaseboard" if has_baseboard else "PSZAC_DHW"
    elif has_boiler:
        psz_template_base = "PSZAC_BoilerBaseboard" if has_baseboard else "PSZAC_Boiler"
    elif has_hp_coil:
        psz_template_base = "PSZAC_ASHP"
    elif has_gas_coil:
        psz_template_base = "PSZAC_GasHeaters" if has_baseboard else "PSZAC_GasCoil"
    elif has_elec_coil:
        psz_template_base = "PSZAC_ElectricBaseboard" if has_baseboard else "PSZAC_ElectricCoil"

    # Build zone → AirLoop name mapping via ZoneSplitter
    # ZoneSplitter outlet nodes are named like "<ZoneName> VAV Box Inlet Node"
    # The AirLoop name is derived from the splitter name prefix.
    zone_to_airloop: dict[str, str] = {}

    # First, map splitter names to AirLoop names via AirLoopHVAC objects
    splitter_to_airloop: dict[str, str] = {}
    for airloop in idf_data.get("AIRLOOPHVAC:SUPPLYPATH", []):
        # Fields: Name, Supply Inlet Node, Component Type, Component Name
        if len(airloop) >= 4:
            airloop_name = airloop[0]
            for i in range(2, len(airloop) - 1, 2):
                comp_type = str(airloop[i]).upper()
                if "ZONESPLITTER" in comp_type:
                    splitter_to_airloop[airloop[i + 1]] = airloop_name

    for splitter in zone_splitters:
        if len(splitter) >= 3:
            splitter_name = splitter[0]
            airloop_name = splitter_to_airloop.get(
                splitter_name, splitter_name.replace(" Supply Air Splitter", "")
            )
            # Outlet nodes (index 2+) are zone inlet nodes
            for outlet_node in splitter[2:]:
                # Extract zone name from node: "<ZoneName> VAV Box Inlet Node"
                zone_from_node = outlet_node.rsplit(" VAV Box", 1)[0]
                if " " in zone_from_node:
                    zone_from_node = outlet_node.rsplit(" ", 3)[0]
                zone_to_airloop[zone_from_node.upper()] = airloop_name

    # Build AirLoop → Controller:OutdoorAir mapping
    airloop_to_oa: dict[str, list] = {}
    for oa in controller_oa:
        oa_name = oa[0].upper()
        # Match by finding the AirLoop whose name is a prefix of the OA controller
        for airloop_name in set(zone_to_airloop.values()):
            if airloop_name.upper().replace(" ", "_") in oa_name.replace(" ", "_"):
                airloop_to_oa[airloop_name] = oa
                break

    # Build AirLoop → Controller:MechanicalVentilation mapping
    airloop_to_mv: dict[str, list] = {}
    for mv in mech_vent:
        mv_name = mv[0].upper()
        for airloop_name in set(zone_to_airloop.values()):
            if airloop_name.upper().replace(" ", "_") in mv_name.replace(" ", "_"):
                airloop_to_mv[airloop_name] = mv
                break

    results = {}
    
    for z in zone_names:
        if z not in conditioned_zones and z not in zone_equip_list:
            results[z] = {"template": "Unconditioned", "dcv": "N/A", "economizer": "N/A"}
            continue
        
        template = "Unknown"
        dcv = "No"
        economizer = "NoEconomizer"

        eq_list_name = zone_equip_list.get(z)
        equipments = equip_list_objects.get(eq_list_name, [])

        if not equipments:
            results[z] = {"template": "Unconditioned", "dcv": "N/A", "economizer": "N/A"}
            continue

        for eq_type, eq_name in equipments:
            eq_typ = eq_type.upper()
            if "PACKAGEDTERMINALAIRCONDITIONER" in eq_typ:
                template = "PTAC"
            elif "PACKAGEDTERMINALHEATPUMP" in eq_typ:
                template = "PTHP"
            elif "WATERTOAIRHEATPUMP" in eq_typ:
                template = "WSHP"
            elif "FOURPIPEFANCOIL" in eq_typ:
                template = "FCUwithDOASAbridged"
            elif "IDEALLOADSAIRSYSTEM" in eq_typ:
                template = "IdealLoads"
            elif "UNITHEATER" in eq_typ:
                template = "UnitHeater"
            elif "HIGHTEMPERATURERADIANT" in eq_typ:
                template = "Radiant"
            elif "LOWTEMPERATURERADIANT" in eq_typ:
                template = "Radiant"
            elif "BASEBOARD" in eq_typ:
                template = "Baseboard"
            elif "DEHUMIDIFIER" in eq_typ:
                template = "Dehumidifier"
            elif "AIRDISTRIBUTIONUNIT" in eq_typ:
                # Find the ATU
                for adu in idf_data.get("ZONEHVAC:AIRDISTRIBUTIONUNIT", []):
                    if adu[0] == eq_name:
                        atu_type = adu[2].upper() if len(adu) > 2 else ""
                        if "VAV" in atu_type:
                            # VAV terminal found — distinguish VAV vs PVAV
                            # by cooling source: chiller → VAV, DX → PVAV
                            if has_chiller or has_district_clg:
                                template = vav_template_base
                            elif has_dx_cooling:
                                template = pvav_template_base
                            else:
                                template = vav_template_base
                        elif "CONSTANTVOLUME" in atu_type:
                            template = psz_template_base
                        break
            # ----------------------------------------------------------------
            # EnergyPlus 8.x legacy: AirTerminal:SingleDuct:Uncontrolled
            # was renamed to AirTerminal:SingleDuct:ConstantVolume:NoReheat
            # in EnergyPlus 9.x.  Both indicate a constant-volume PSZ-style
            # direct-air terminal with no reheat.
            # ----------------------------------------------------------------
            elif "SINGLEDUCT:UNCONTROLLED" in eq_typ:
                template = psz_template_base
            elif "SINGLEDUCT:CONSTANTVOLUME:NOREHEAT" in eq_typ:
                template = psz_template_base
            
            if template == "Unknown":
                if "PSZ" in eq_name.upper(): template = psz_template_base
                elif "VAV" in eq_name.upper():
                    if has_chiller or has_district_clg:
                        template = vav_template_base
                    elif has_dx_cooling:
                        template = pvav_template_base
                    else:
                        template = vav_template_base
                elif "FCU" in eq_name.upper(): template = "FCUwithDOASAbridged"

        # Look up DCV and Economizer via zone → AirLoop → Controller chain
        airloop_name = zone_to_airloop.get(z.upper())
        if airloop_name:
            oa = airloop_to_oa.get(airloop_name)
            if oa:
                economizer = oa[7] if len(oa) > 7 else "NoEconomizer"
            mv = airloop_to_mv.get(airloop_name)
            if mv:
                dcv = mv[2] if len(mv) > 2 else "No"

        results[z] = {"template": template, "dcv": dcv, "economizer": economizer}
    return results


def extract_natural_ventilation(idf_data: dict, zone_geo: dict) -> dict[str, list[dict]]:
    """Extracts natural ventilation parameters from ZoneVentilation:WindandStackOpenArea."""
    results = {name: [] for name in zone_geo}
    
    # Target Parameters:
    # Field 1: Zone Name
    # Field 2: Opening Area [m2]
    # Field 3: Ventilation Schedule
    # Field 8: Minimum Indoor Temp [C] (index 8)
    # Field 10: Maximum Indoor Temp [C] (index 10)
    # Field 14: Minimum Outdoor Temp [C] (index 14)
    # Field 16: Maximum Outdoor Temp [C] (index 16)
    
    for obj in idf_data.get("ZONEVENTILATION:WINDANDSTACKOPENAREA", []):
        if len(obj) < 2:
            continue
            
        zone_name = obj[1]
        if zone_name not in zone_geo:
            # Try to match the zone name robustly if it doesn't match exactly
            matched = False
            for zn in zone_geo:
                if zn.upper() == zone_name.upper():
                    zone_name = zn
                    matched = True
                    break
            if not matched:
                continue

        params = {
            "name": obj[0],
            "opening_area": 0.0,
            "schedule": "",
            "min_in_temp": -100.0,
            "max_in_temp": 100.0,
            "min_out_temp": -100.0,
            "max_out_temp": 100.0,
        }
        
        try:
            if len(obj) > 2 and obj[2]: params["opening_area"] = float(obj[2])
            if len(obj) > 3: params["schedule"] = obj[3]
            if len(obj) > 8 and obj[8]: params["min_in_temp"] = float(obj[8])
            if len(obj) > 10 and obj[10]: params["max_in_temp"] = float(obj[10])
            if len(obj) > 14 and obj[14]: params["min_out_temp"] = float(obj[14])
            if len(obj) > 16 and obj[16]: params["max_out_temp"] = float(obj[16])
        except (ValueError, IndexError):
            pass
            
        results[zone_name].append(params)
        
    return results

