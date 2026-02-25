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
        if len(obj) < 3:
            continue

        # If field 8 (index 7) exists, use it.
        zone_name = obj[7] if len(obj) >= 8 else ""

        if not zone_name or zone_name not in zone_geo:
            # Heuristic for residential: match equipment name suffix (e.g., _unit1) 
            # with zone name suffix or living zone
            obj_name = obj[0]
            unit_match = re.search(r"(_unit\d+)$", obj_name, re.IGNORECASE)
            if unit_match:
                suffix = unit_match.group(1).upper()
                # Find the 'living' zone for this unit
                for zn in zone_geo:
                    if zn.upper().endswith(suffix) and "LIVING" in zn.upper():
                        zone_name = zn
                        break
            
            # Fallback: if still no match and there's only one living zone, use it
            if not zone_name:
                living_zones = [zn for zn in zone_geo if "LIVING" in zn.upper()]
                if len(living_zones) == 1:
                    zone_name = living_zones[0]

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

    # Add support for EFFECTIVELEAKAGEAREA (common in residential)
    # Estimate flow at 4Pa: V [m3/s] = ELA [m2] * 1.0 * sqrt(2 * 4 / 1.2) approx ELA * 2.58
    for obj in idf_data.get("ZONEINFILTRATION:EFFECTIVELEAKAGEAREA", []):
        if len(obj) < 4:
            continue
        zone_name = obj[1]
        if zone_name not in zone_geo:
            continue
        facade_area = zone_geo[zone_name]["facade_area"]
        norm_area = facade_area if facade_area > 0 else zone_geo[zone_name]["floor_area"]
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
        if len(obj) < 3:
            continue
        try:
            ela_m2 = float(obj[2])
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
        norm_area = facade_area if facade_area > 0 else zone_geo[zone_name]["floor_area"]
        if norm_area <= 0:
            continue

        # Add to results
        results[zone_name] += (ela_m2 * 2.58) / norm_area

    return results


def extract_ventilation(idf_data: dict, zone_geo: dict) -> dict[str, dict[str, float]]:
    """Extracts ventilation (m3/s per person AND m3/s per m2)."""
    results = {name: {"per_person": 0.0, "per_area": 0.0} for name in zone_geo}
    for obj in idf_data.get("DESIGNSPECIFICATION:OUTDOORAIR", []):
        name = obj[0]
        # Heuristic: Match "SZ DSOA ZoneName"
        matched_zone = None
        best_len = 0
        for zn in zone_geo:
            if zn.upper() in name.upper() and len(zn) > best_len:
                matched_zone = zn
                best_len = len(zn)

        if not matched_zone:
            continue

        try:
            # Field 3: Flow per Person
            if len(obj) > 2 and obj[2]:
                results[matched_zone]["per_person"] = float(obj[2])
            # Field 4: Flow per Area
            if len(obj) > 3 and obj[3]:
                results[matched_zone]["per_area"] = float(obj[3])
            # Field 5: Flow per Zone
            if len(obj) > 4 and obj[4]:
                flow_zone = float(obj[4])
                area = zone_geo[matched_zone]["floor_area"]
                if area > 0:
                    results[matched_zone]["per_area"] += flow_zone / area
        except (ValueError, IndexError):
            continue

    # Also check ZoneVentilation:DesignFlowRate for mechanical ventilation
    for obj in idf_data.get("ZONEVENTILATION:DESIGNFLOWRATE", []):
        if len(obj) < 5:
            continue
        zone_name = obj[1]
        if zone_name not in zone_geo:
            continue
        
        method = obj[3].lower()
        area = zone_geo[zone_name]["floor_area"]
        if area <= 0:
            continue
            
        try:
            if method in ["flow/zone", "level"]:
                results[zone_name]["per_area"] += float(obj[4]) / area
            elif method == "flow/area":
                results[zone_name]["per_area"] += float(obj[5])
            elif method in ["flow/person", "perperson"]:
                results[zone_name]["per_person"] += float(obj[6])
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

