# Fix Elevator Load Double Counting

This document outlines the changes made to prevent elevator loads from being double-counted in the "Zone Metadata Detail" table while still displaying them in the specialized "Building Process Loads" section.

## Issue Description
Elevator loads were being reported at both the building level and the zone level. In some IDF files, elevators are assigned to specific zones (e.g., `T Corridor`) using `ElectricEquipment` objects. These loads were appearing in the main zone-level metadata table, which inflated total equipment density calculations and led to redundant reporting.

## Implementation Detail

### 1. Unified Identification Pattern
A centralized list of keywords has been established to identify elevator-related equipment:
- `Elevator`
- `Lift`
- `Elev_lights`

### 2. Filtering in `extractors.py`
The `extract_process_loads` function was updated to categorize these loads. Specifically:
- **Identification:** Any `ElectricEquipment` object with a name matching the elevator keywords is flagged.
- **Categorization:** These objects are grouped into the "Elevator" category for the process loads table.
- **Exclusion:** The `extract_zone_loads` function (which feeds the main metadata table) now ignores any equipment objects identified as elevators based on these keywords.

### 3. Reporting Logic
- **Zone Metadata Table:** Successfully excludes elevator loads to ensure clean zone-by-zone comparison of standard occupant-driven loads.
- **Building Process Loads Table:** Explicitly displays elevator loads, fulfilling the requirement to track building-level infrastructure separately.

## Verification Result
Calculations for "Electric Equipment [W/m2]" in the `Zone Metadata Detail` table now reflect true zone loads (lights, plugs, etc.) without the spike caused by building elevators. The elevator totals continue to appear correctly in the specialized building loads summary card.
