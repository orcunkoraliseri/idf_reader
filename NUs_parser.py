"""
NUs_parser.py — Neighbourhood IDF Zone Extractor.

Reads a neighbourhood EnergyPlus .idf file and produces a summary of
distinct buildings grouped by their ASHRAE 90.1 prototype building type.

Building classification is driven by keywords found in the zone names,
mirroring the naming conventions used in the ASHRAE 90.1 prototype model
library.  Each zone name is expected to carry a numeric prefix that
identifies its parent building (e.g. ``17_24_living_unit1`` → building
``17_24``, type *Single Family Detached*; ``16_6_G SW Apartment`` →
building ``16_6_G``, type *Midrise Apartment*; ``8_Auditorium_ZN_1_FLR_1``
→ building ``8_``, type *Secondary School*).
"""

import re
from collections import defaultdict

# Standard library
from typing import NamedTuple

# Local
from idf_parser import parse_idf
from geometry import get_zone_geometry


# ---------------------------------------------------------------------------
# ASHRAE 90.1 Prototype keyword map
# Each entry maps a human-readable building type to the set of lowercase
# keywords that, if present anywhere in a zone name, identify that type.
# The order matters: more specific types should appear first so that a zone
# containing multiple keywords is assigned the best match.
# ---------------------------------------------------------------------------
_ASHRAE_TYPE_KEYWORDS: dict[str, list[str]] = {
    # ── Residential ────────────────────────────────────────────────────────
    "Single Family Detached": [
        "living_unit", "attic_unit", "crawlspace", "house",
    ],
    "Midrise Apartment": [
        # Core apartment zone names from the ASHRAE 90.1 MidRise prototype
        "apartment",
        # Corridors are an integral part of the MidRise Apartment prototype
        # (G Corridor, M Corridor, T Corridor)
        " corridor",   # space before avoids matching "corridor_pod" (school)
        # Ground-floor Office zone present in each apartment building instance
        # (zone name is simply e.g. "16_6_Office")
        "_office",
    ],
    "Highrise Apartment": [
        "highrise",
    ],
    # ── Schools ─────────────────────────────────────────────────────────────
    "Secondary School": [
        # Unique Secondary School zone fragments
        "auditorium", "aux_gym",
        # Shared with Primary but present in Secondary too
        "corner_class", "mult_class", "corridor_pod",
        "cafeteria", "kitchen_zn", "library_media", "lobby_zn",
        "main_corridor", "mech_zn", "bathrooms",
        # Secondary-specific suffix pattern
        "_flr_2",  # secondary school has FLR_2 zones; primary only has FLR_1
    ],
    "Primary School": [
        # Primary-only zone fragments
        "computer_class", "bath_zn",
    ],
    # ── Offices ─────────────────────────────────────────────────────────────
    "Large Office": [
        # Large office has basement, data centres, and three-tier core/perim
        "core_bottom", "core_mid", "core_top",
        "perimeter_bot", "perimeter_mid", "perimeter_top",
        "datacenter", "groundfloor_plenum", "midfloor_plenum",
        "topfloor_plenum",
    ],
    "Medium Office": [
        # Medium office shares core/perimeter names but has firstfloor_plenum
        "firstfloor_plenum",
    ],
    "Small Office": [
        # Small office uses Core_ZN and Perimeter_ZN (no tier suffix)
        "core_zn", "perimeter_zn",
    ],
    # ── Hotels ──────────────────────────────────────────────────────────────
    "Large Hotel": [
        # Large Hotel-specific zone names
        "banquet", "cafe_flr", "dining_flr", "kitchen_flr",
        "laundry_flr", "lobby_flr", "mech_flr", "storage_flr",
        "room_1_flr", "room_2_flr", "room_3_mult", "room_4_mult",
        "room_5_flr", "room_6_flr",
        "retail_1_flr", "retail_2_flr",
        "corridor_flr",
    ],
    "Small Hotel": [
        "guestroom", "corridorflr", "elevatorcore",
        "employeelounge", "exercisecenter", "frontlounge",
        "frontoffice", "frontstairs", "frontstorage",
        "laundryroom", "mechanicalroom", "meetingroom",
        "rearstairs", "rearstorage", "restroomflr",
    ],
    # ── Restaurants ─────────────────────────────────────────────────────────
    "Quick Service Restaurant": [
        # Fast-food prototype: Dining, Kitchen, attic
        "dining", "kitchen", "attic",
    ],
    "Full Service Restaurant": [
        "full_service",
    ],
    # ── Retail ──────────────────────────────────────────────────────────────
    "Supermarket": [
        "bakery", "deli", "drystorage", "produce", "sales", "grocery",
    ],
    "Standalone Retail": [
        # Standalone Retail prototype zone names
        "back_space", "core_retail", "front_entry",
        "front_retail", "point_of_sale",
    ],
    "Strip Mall": [
        "lgstore", "smstore",
    ],
    # ── Healthcare ──────────────────────────────────────────────────────────
    "Hospital": [
        "icu", "operating", "nursery", "patient_room",
        "patroom", "phystherapy", "radiology",
    ],
    "Outpatient Healthcare": [
        "exam_", "operating_room", "pacu", "pre-op",
        "sterile", "anesthesia", "procedure_room",
        "ne stair", "nw elevator", "nw stair", "sw stair",
    ],
    # ── Warehouse ───────────────────────────────────────────────────────────
    "Warehouse": [
        "fine_storage", "bulk_storage", "zone1 office",
        "zone2 fine", "zone3 bulk",
    ],
}


class BuildingEntry(NamedTuple):
    """A single recognised building in the neighbourhood.

    Attributes:
        prefix: The raw zone-name prefix that identifies this building instance
            (e.g. ``'17_24'``, ``'16_6_G'``, ``'8_'``).
        ashrae_type: The matched ASHRAE 90.1 prototype building type string.
    """

    prefix: str
    ashrae_type: str


def _classify_zone(zone_name: str) -> str:
    """Return the ASHRAE 90.1 building type for a single zone name.

    Args:
        zone_name: The raw zone name string extracted from the IDF file.

    Returns:
        A human-readable ASHRAE 90.1 prototype building type string, or
        ``'Unknown'`` when no keyword matches.
    """
    lower = zone_name.lower()
    for btype, keywords in _ASHRAE_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return btype
    return "Unknown"


def _extract_prefix(zone_name: str) -> str:
    """Detect the numeric building-instance prefix from a zone name.

    Neighbourhood IDFs typically encode the building instance as a leading
    ``<int>_<int>`` or ``<int>_<int>_<letter(s)>`` token. To ensure accurate
    building counts, we extract only the numeric root (e.g. ``16_6``) and
    strip story or section indicators like ``_G``, ``_M``, or ``_LIBRARY``.

    Examples:
        • ``17_24_living_unit1``  → prefix ``17_24``
        • ``16_6_G SW Apartment`` → prefix ``16_6``
        • ``8_Auditorium_ZN_1``   → prefix ``8``
        • ``8_LIBRARY_MEDIA``     → prefix ``8``

    Args:
        zone_name: The raw zone name string.

    Returns:
        The extracted numeric prefix string, or the full zone name when the
        pattern cannot be matched.
    """
    # Pattern: match leading digit groups separated by underscores.
    match = re.match(
        r"^(\d+(?:_\d+)*)",
        zone_name.strip(),
    )
    if match:
        return match.group(1)
    return zone_name.strip()


class NeighbourhoodSummary(NamedTuple):
    """High-level summary of a neighbourhood IDF file.

    Attributes:
        idf_path: Absolute path to the source .idf file.
        building_name: Value of the ``Building`` object ``Name`` field.
        building_counts: Mapping of ASHRAE 90.1 building type → count of
            distinct building instances of that type.
        total_zones: Total number of ``Zone`` objects in the file.
    """

    idf_path: str
    building_name: str
    building_counts: dict[str, int]
    total_zones: int


def parse_neighbourhood(idf_path: str) -> NeighbourhoodSummary:
    """Parse a neighbourhood IDF file and return a building count summary.

    Strategy
    --------
    1. Parse all ``Zone`` objects from the IDF using :func:`idf_parser.parse_idf`.
    2. Extract the numeric/alpha prefix from each zone name — this prefix
       identifies one physical building instance.
    3. Classify each building prefix into an ASHRAE 90.1 prototype type using
       keyword matching against its member zone names.
    4. Count unique building instances per type.

    Args:
        idf_path: Absolute path to the EnergyPlus neighbourhood .idf file.

    Returns:
        A :class:`NeighbourhoodSummary` with building type counts.

    Raises:
        FileNotFoundError: If *idf_path* does not exist.
    """
    idf_data = parse_idf(idf_path)

    # Extract Building name (first field of the BUILDING object)
    building_name = "Unknown"
    buildings = idf_data.get("BUILDING", [])
    if buildings and buildings[0]:
        building_name = buildings[0][0].strip() or "Unknown"

    zones = idf_data.get("ZONE", [])
    total_zones = len(zones)

    # Map: prefix → list of zone names for that prefix
    prefix_zones: dict[str, list[str]] = defaultdict(list)
    prefix_types: dict[str, set[str]] = defaultdict(set)

    for zone_fields in zones:
        if not zone_fields:
            continue
        zone_name = zone_fields[0].strip()
        prefix = _extract_prefix(zone_name)
        ztype = _classify_zone(zone_name)
        prefix_zones[prefix].append(zone_name)
        prefix_types[prefix].add(ztype)

    # Determine one canonical ASHRAE type per building prefix.
    # If multiple types were found, prefer the first non-Unknown type.
    # Add geometry-based disambiguation for QSR vs FSR.
    prefix_canonical: dict[str, str] = {}
    
    # Pre-compute geometry when needed
    zone_geo = None

    for prefix, types in prefix_types.items():
        non_unknown = [t for t in types if t != "Unknown"]
        canonical_type = non_unknown[0] if non_unknown else "Unknown"

        # Area-based restaurant disambiguation
        if canonical_type == "Quick Service Restaurant" or canonical_type == "Full Service Restaurant":
            if zone_geo is None:
                zone_geo = get_zone_geometry(idf_data)
            
            # Calculate total restaurant floor area for this prefix (excluding attic)
            total_floor_area = 0.0
            for zn in prefix_zones[prefix]:
                if "attic" not in zn.lower() and zn in zone_geo:
                    total_floor_area += zone_geo[zn].get("floor_area", 0.0)
            
            if total_floor_area >= 350.0:
                canonical_type = "Full Service Restaurant"
            else:
                canonical_type = "Quick Service Restaurant"

        prefix_canonical[prefix] = canonical_type

    # Count unique building prefixes per ASHRAE type
    building_counts: dict[str, int] = defaultdict(int)
    for btype in prefix_canonical.values():
        building_counts[btype] += 1

    return NeighbourhoodSummary(
        idf_path=idf_path,
        building_name=building_name,
        building_counts=dict(building_counts),
        total_zones=total_zones,
    )
