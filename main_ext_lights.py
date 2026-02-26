"""
Neighbourhood Exterior Lights Aggregator
=========================================
Interactively builds a neighbourhood definition (name + buildings),
collects Exterior:Lights objects from each building's IDF (auto-assigned
by building type), scales by building count, and writes a consolidated
EnergyPlus IDF snippet to outputs_txt/<neighbourhood_name>_exterior_lights.txt.

Run:
    py exterior_lights_aggregator.py
"""

from __future__ import annotations

import os
import sys

from idf_parser import parse_idf

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONTENT_DIR = os.path.join(os.path.dirname(__file__), "Content")
OUTPUT_DIR  = os.path.join(os.path.dirname(__file__), "outputs_txt")

# Predefined building type labels and their category groupings.
# Extend this list as you add new building types to your neighbourhoods.
BUILDING_TYPES: list[tuple[str, str]] = [
    ("DetachedHouse",       "RESIDENTIAL"),
    ("AttachedHouse",       "RESIDENTIAL"),
    ("ApartmentMidRise",    "RESIDENTIAL"),
    ("ApartmentHighRise",   "RESIDENTIAL"),
    ("SmallOffice",         "COMMERCIAL"),
    ("MediumOffice",        "COMMERCIAL"),
    ("LargeOffice",         "COMMERCIAL"),
    ("SmallRetail",         "COMMERCIAL"),
    ("StripMallRetail",     "COMMERCIAL"),
    ("Warehouse",           "COMMERCIAL"),
    ("Hospital",            "COMMERCIAL"),
    ("SmallHotel",          "COMMERCIAL"),
    ("LargeHotel",          "COMMERCIAL"),
    ("SchoolPrimary",       "COMMERCIAL"),
    ("SchoolSecondary",     "COMMERCIAL"),
    ("OutpatientCare",      "COMMERCIAL"),
    ("QSR",                 "RESTAURANT"),   # Quick-Service Restaurant
    ("FSR",                 "RESTAURANT"),   # Full-Service Restaurant
]

# ---------------------------------------------------------------------------
# Auto-assignment: building type → relative IDF path under Content/
# ---------------------------------------------------------------------------
# The IDF is parsed to extract Exterior:Lights automatically.
# If the IDF has no Exterior:Lights, the WATTAGE_FALLBACKS table is used.
# If neither provides a value, the building is skipped.

IDF_DEFAULTS: dict[str, str] = {
    "DetachedHouse":    os.path.join("others",           "TwoStoreyHouse_V242.idf"),
    "AttachedHouse":    os.path.join("others",           "TwoStoreyHouse_V242.idf"),
    "ApartmentMidRise": os.path.join("ASHRAE901_STD2022", "ASHRAE901_ApartmentMidRise_STD2022_Denver.idf"),
    "ApartmentHighRise":os.path.join("ASHRAE901_STD2022", "ASHRAE901_ApartmentHighRise_STD2022_Denver.idf"),
    "SmallOffice":      os.path.join("ASHRAE901_STD2022", "ASHRAE901_OfficeSmall_STD2022_Denver.idf"),
    "MediumOffice":     os.path.join("ASHRAE901_STD2022", "ASHRAE901_OfficeMedium_STD2022_Denver.idf"),
    "LargeOffice":      os.path.join("ASHRAE901_STD2022", "ASHRAE901_OfficeLarge_STD2022_Denver.idf"),
    "SmallRetail":      os.path.join("others",           "MT5_HPE_NV_ECW_LED Small_Retail - Calgary.idf"),
    "StripMallRetail":  os.path.join("ASHRAE901_STD2022", "ASHRAE901_RetailStripmall_STD2022_Denver.idf"),
    "Warehouse":        os.path.join("ASHRAE901_STD2022", "ASHRAE901_Warehouse_STD2022_Denver.idf"),
    "Hospital":         os.path.join("ASHRAE901_STD2022", "ASHRAE901_Hospital_STD2022_Denver.idf"),
    "SmallHotel":       os.path.join("ASHRAE901_STD2022", "ASHRAE901_HotelSmall_STD2022_Denver.idf"),
    "LargeHotel":       os.path.join("ASHRAE901_STD2022", "ASHRAE901_HotelLarge_STD2022_Denver.idf"),
    "SchoolPrimary":    os.path.join("ASHRAE901_STD2022", "ASHRAE901_SchoolPrimary_STD2022_Denver.idf"),
    "SchoolSecondary":  os.path.join("ASHRAE901_STD2022", "ASHRAE901_SchoolSecondary_STD2022_Denver.idf"),
    "OutpatientCare":   os.path.join("ASHRAE901_STD2022", "ASHRAE901_OutPatientHealthCare_STD2022_Denver.idf"),
    "QSR":              os.path.join("ASHRAE901_STD2022", "ASHRAE901_RestaurantFastFood_STD2022_Denver.idf"),
    "FSR":              os.path.join("ASHRAE901_STD2022", "ASHRAE901_RestaurantSitDown_STD2022_Denver.idf"),
}

# ---------------------------------------------------------------------------
# Wattage fallbacks: per-unit Design Level [W] for building types whose
# standard IDF does not contain Exterior:Lights objects.
# Values collected from project-specific IDFs. Update as needed.
# ---------------------------------------------------------------------------

WATTAGE_FALLBACKS: dict[str, float] = {
    "SmallOffice":      734.92,
    "MediumOffice":     734.92,   # placeholder – update if available
    "LargeOffice":      734.92,   # placeholder – update if available
    "SmallRetail":      130.22,
    "StripMallRetail":  130.22,   # placeholder – update if available
    "QSR":              209.35,
    "FSR":             1305.94,
    "SchoolPrimary":    900.00,   # placeholder – update if available
    "SchoolSecondary":  900.00,   # placeholder – update if available
    "Hospital":        1000.00,   # placeholder – update if available
    "SmallHotel":       500.00,   # placeholder – update if available
    "LargeHotel":      1000.00,   # placeholder – update if available
    "Warehouse":        200.00,   # placeholder – update if available
    "OutpatientCare":   500.00,   # placeholder – update if available
    "ApartmentMidRise":  47.34,   # placeholder – update if available
    "ApartmentHighRise": 47.34,   # placeholder – update if available
}

# Subcategories to ignore (case-insensitive).
# Garage lights exist as Exterior:Lights in some residential IDFs, but should be excluded.
EXCLUDED_SUBCATEGORIES = {"garage-lights"}

# Categories printed in this order in the output file.
CATEGORY_ORDER = ["RESIDENTIAL", "COMMERCIAL", "RESTAURANT"]



# ---------------------------------------------------------------------------
# IDF extraction helpers
# ---------------------------------------------------------------------------

def extract_exterior_lights_from_idf(idf_path: str) -> list[dict]:
    """Parse an IDF and return all Exterior:Lights entries whose subcategory
    matches EXTERIOR_LIGHTS_SUBCATEGORY.

    Returns a list of dicts: {name, schedule, design_level_w, control_option, subcategory}
    """
    try:
        idf_data = parse_idf(idf_path)
    except Exception as exc:
        print(f"    [!] Could not parse {os.path.basename(idf_path)}: {exc}")
        return []

    results = []
    for obj in idf_data.get("EXTERIOR:LIGHTS", []):
        # Fields: Name(0), Schedule(1), Design Level(2), Control Option(3), Subcategory(4)
        try:
            name         = obj[0].strip() if len(obj) > 0 else ""
            schedule     = obj[1].strip() if len(obj) > 1 else ""
            design_level = float(obj[2])  if len(obj) > 2 and obj[2].strip() else 0.0
            control_opt  = obj[3].strip() if len(obj) > 3 else ""
            subcategory  = obj[4].strip() if len(obj) > 4 else ""

            if subcategory.lower() not in EXCLUDED_SUBCATEGORIES:
                results.append({
                    "name":           name,
                    "schedule":       schedule,
                    "design_level_w": design_level,
                    "control_option": control_opt,
                    "subcategory":    subcategory,
                })
        except (ValueError, IndexError):
            continue

    return results


def resolve_idf_for_type(type_label: str) -> tuple[str | None, str | None]:
    """Return (full_idf_path, relative_display_name) for the auto-assigned IDF
    of the given building type, or (None, None) if no default is configured.
    """
    rel = IDF_DEFAULTS.get(type_label)
    if rel is None:
        return None, None
    full = os.path.join(CONTENT_DIR, rel)
    if not os.path.exists(full):
        return None, rel   # mapping exists but file missing
    return full, rel


# ---------------------------------------------------------------------------
# Interactive input helpers
# ---------------------------------------------------------------------------

def find_idf_files(base_dir: str) -> list[tuple[str, str]]:
    """Recursively find all .idf files under base_dir.

    Returns a sorted list of (relative_path, full_path) tuples.
    """
    found: list[tuple[str, str]] = []
    if not os.path.exists(base_dir):
        return found
    for root, _, files in os.walk(base_dir):
        for f in files:
            if f.lower().endswith(".idf"):
                full = os.path.join(root, f)
                rel  = os.path.relpath(full, base_dir)
                found.append((rel, full))
    found.sort(key=lambda x: x[0].lower())
    return found


def prompt_neighbourhood_name() -> str:
    """Ask the user to enter a neighbourhood name (used as prefix in output)."""
    print("\n" + "=" * 60)
    print("  NEIGHBOURHOOD EXTERIOR LIGHTS AGGREGATOR")
    print("=" * 60)
    while True:
        name = input("\nEnter neighbourhood name (e.g. CR0_V2_IAL): ").strip()
        if name:
            return name
        print("  Name cannot be empty. Please try again.")


def prompt_building_type() -> tuple[str, str] | None:
    """Show a numbered list of building types and let the user pick one.

    Returns (type_label, category) or None if the user is done adding buildings.
    """
    print("\n  Available building types:")
    for i, (label, category) in enumerate(BUILDING_TYPES, 1):
        idf_rel = IDF_DEFAULTS.get(label, "")
        tag = f"→ {os.path.basename(idf_rel)}" if idf_rel else "→ no default IDF"
        print(f"    [{i:2}]  {label:<22} ({category})  {tag}")
    print("    [ d]  Done – no more buildings")

    while True:
        choice = input(f"\n  Select building type (1-{len(BUILDING_TYPES)}, d): ").strip().lower()
        if choice == "d":
            return None
        try:
            idx = int(choice)
            if 1 <= idx <= len(BUILDING_TYPES):
                return BUILDING_TYPES[idx - 1]
        except ValueError:
            pass
        print("  Invalid selection. Please try again.")


def prompt_building_count(type_label: str) -> int:
    """Ask the user how many buildings of this type are in the neighbourhood."""
    while True:
        raw = input(f"  How many {type_label} buildings? ").strip()
        try:
            count = int(raw)
            if count > 0:
                return count
            print("  Count must be at least 1.")
        except ValueError:
            print("  Please enter a valid integer.")



# ---------------------------------------------------------------------------
# Aggregation logic
# ---------------------------------------------------------------------------

def aggregate_exterior_lights(
    neighbourhood_name: str,
    buildings: list[dict],
) -> list[dict]:
    """For each building entry, extract or use override wattage, multiply by
    count, and return an aggregated list suitable for TXT generation.

    Each item in 'buildings' has:
        {type, category, count, idf_path (str|None), override_w (float|None)}

    Returns a list of dicts:
        {type, category, count, per_unit_w, total_w, control_option}
    """
    aggregated: list[dict] = []

    for bldg in buildings:
        btype    = bldg["type"]
        category = bldg["category"]
        count    = bldg["count"]

        if bldg["idf_path"]:
            print(f"  Extracting from IDF for {btype}...")
            entries = extract_exterior_lights_from_idf(bldg["idf_path"])
            if entries:
                per_unit_w     = sum(e["design_level_w"] for e in entries)
                control_option = entries[0]["control_option"] or "AstronomicalClock"
                print(f"    ✓ {len(entries)} Exterior:Lights object(s) found → {per_unit_w:.4f} W per unit")
            else:
                # IDF has no Exterior:Lights — check the fallback table
                fallback = WATTAGE_FALLBACKS.get(btype)
                if fallback is not None:
                    per_unit_w     = fallback
                    control_option = "AstronomicalClock"
                    print(f"    [i] No Exterior:Lights in IDF — using fallback: {per_unit_w:.2f} W per unit")
                else:
                    print(f"    [!] No Exterior:Lights in IDF and no fallback configured — skipping {btype}.")
                    continue  # skip this building only
        else:
            per_unit_w     = 0.0
            control_option = "AstronomicalClock"

        aggregated.append({
            "type":           btype,
            "category":       category,
            "count":          count,
            "per_unit_w":     per_unit_w,
            "total_w":        round(per_unit_w * count, 2),
            "control_option": control_option,
        })

    return aggregated


# ---------------------------------------------------------------------------
# TXT generation
# ---------------------------------------------------------------------------

def generate_exterior_lights_txt(
    neighbourhood_name: str,
    aggregated: list[dict],
    output_dir: str,
) -> str:
    """Write the formatted EnergyPlus IDF snippet to a .txt file.

    Returns the full path of the written file.
    """
    os.makedirs(output_dir, exist_ok=True)

    prefix     = neighbourhood_name
    sched_name = f"{prefix}_ALWAYS_ON"
    out_path   = os.path.join(output_dir, f"{neighbourhood_name}_exterior_lights.txt")

    lines: list[str] = []

    # Header
    lines += [
        f"!- {'=' * 59}",
        f"!- {neighbourhood_name} EXTERIOR LIGHTS - ADDITIONAL IDF STRING",
        f"!- {'=' * 59}",
        "",
        "!- SCHEDULE (declared once, shared by all objects)",
        "",
        "  Schedule:Compact,",
        f"    {sched_name + ',':<42} !- Name",
        "    On/Off,                      !- Schedule Type Limits Name",
        "    Through: 12/31,",
        "    For: AllDays,",
        "    Until: 24:00, 1;",
        "",
    ]

    # Group by category in defined order
    category_map: dict[str, list[dict]] = {cat: [] for cat in CATEGORY_ORDER}
    for item in aggregated:
        cat = item["category"]
        if cat not in category_map:
            category_map[cat] = []
        category_map[cat].append(item)

    for category in CATEGORY_ORDER:
        items = category_map.get(category, [])
        if not items:
            continue

        lines += [
            f"!- {'=' * 59}",
            f"!- {category}",
            f"!- {'=' * 59}",
            "",
        ]

        for item in items:
            obj_name = f"{prefix}_ExtLights_{item['type']}"
            total_w  = item["total_w"]
            per_unit = item["per_unit_w"]
            count    = item["count"]
            ctrl     = item["control_option"] or "AstronomicalClock"

            note = f"({count} x {per_unit:.2f} W)" if count > 1 else f"({per_unit:.2f} W)"

            lines += [
                "  Exterior:Lights,",
                f"    {obj_name + ',':<42} !- Name",
                f"    {sched_name + ',':<42} !- Schedule Name",
                f"    {str(total_w) + ',':<42} !- Design Level {{W}} {note}",
                f"    {ctrl + ',':<42} !- Control Option",
                "    Exterior-Lights;",
                "",
            ]

    content = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    return out_path


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def print_summary(neighbourhood_name: str, aggregated: list[dict]) -> None:
    """Print a summary table to the console before writing."""
    print(f"\n{'=' * 60}")
    print(f"  SUMMARY – {neighbourhood_name}")
    print(f"{'=' * 60}")
    print(f"  {'Building Type':<22} {'Count':>6}  {'Per Unit (W)':>13}  {'Total (W)':>11}")
    print(f"  {'-' * 57}")
    for item in aggregated:
        src = "(override)" if item.get("from_override") else "(from IDF)"
        print(
            f"  {item['type']:<22} {item['count']:>6}  "
            f"{item['per_unit_w']:>13.2f}  {item['total_w']:>11.2f}"
        )
    total_all = sum(i["total_w"] for i in aggregated)
    print(f"  {'-' * 57}")
    print(f"  {'TOTAL':<22} {'':>6}  {'':>13}  {total_all:>11.2f}")
    print(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    while True:
        # --- Step 1: neighbourhood name ---
        neighbourhood_name = prompt_neighbourhood_name()

        # --- Step 2: collect buildings ---
        buildings: list[dict] = []
        print(f"\n  Now add buildings for '{neighbourhood_name}'.")
        print(f"  IDF files will be auto-assigned per building type.")
        print(f"  Select 'd' when you have added all buildings.\n")

        while True:
            result = prompt_building_type()
            if result is None:
                if not buildings:
                    print("  At least one building is required. Please add a building.")
                    continue
                break  # done

            type_label, category = result
            count = prompt_building_count(type_label)

            # --- Auto-assign IDF ---
            idf_path, idf_rel = resolve_idf_for_type(type_label)

            if idf_path:
                print(f"  Auto-assigned IDF: {idf_rel}")
                entries = extract_exterior_lights_from_idf(idf_path)
                if not entries:
                    print(f"  [!] No Exterior:Lights found in auto-assigned IDF — skipping {type_label}.")
                    continue
            elif idf_rel:
                # Mapping defined but file not present on disk
                print(f"  [!] Auto-assigned IDF not found on disk: {idf_rel} — skipping {type_label}.")
                continue
            else:
                # No default mapping at all
                print(f"  [!] No default IDF configured for '{type_label}' — skipping {type_label}.")
                continue

            buildings.append({
                "type":       type_label,
                "category":   category,
                "count":      count,
                "idf_path":   idf_path,
                "override_w": 0.0,
            })
            print(f"  ✓ Added: {count}× {type_label}")

        # --- Step 3: aggregate ---
        print(f"\nAggregating exterior lights for '{neighbourhood_name}'...")
        aggregated = aggregate_exterior_lights(neighbourhood_name, buildings)

        # --- Step 4: summary ---
        print_summary(neighbourhood_name, aggregated)

        # --- Step 5: write file ---
        out_path = generate_exterior_lights_txt(neighbourhood_name, aggregated, OUTPUT_DIR)
        print(f"\n✓ Output written to: {out_path}")

        # --- Continue? ---
        again = input("\nProcess another neighbourhood? (y/n): ").strip().lower()
        if again != "y":
            break

    print("\nDone.")


if __name__ == "__main__":
    main()
