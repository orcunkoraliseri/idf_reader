# Neighbourhood Exterior Lights Aggregator

Generate a consolidated `Exterior:Lights` IDF string for a neighbourhood by collecting exterior lighting objects from each building type's IDF, scaling by building count, and writing a formatted `.txt` file.

## Proposed Changes

### New Module

#### [NEW] [main_ext_lights.py](file:///c:/Users/o_iseri/Desktop/idf_reader/main_ext_lights.py)

A standalone Python script containing:

**1. Neighbourhood definition (input)**

An interactive workflow that prompts for the neighbourhood name and then allows adding buildings one by one.

**2. Auto-assignment & Fallbacks**

- Building types are automatically mapped to standard IDFs in the `Content/` directory.
- If an IDF lacks `Exterior:Lights` objects (common in ASHRAE prototype commercial buildings), the script uses a `WATTAGE_FALLBACKS` table populated with project-specific values (e.g., 209W for QSR, 1305W for FSR).

**3. Aggregation Logic**

- For each building entry, it attempts to extract all `EXTERIOR:LIGHTS` objects.
- It filters out specific subcategories like `Garage-Lights`.
- Power is multiplied by the building count.

**4. Consolidated Output**

Writes a formatted `.txt` output file in `outputs_txt/`:
- Header with neighbourhood name.
- Shared `Schedule:Compact` (`{PREFIX}_ALWAYS_ON`).
- Grouped sections: Residential, Commercial, Restaurant.
- Formatted `Exterior:Lights` objects with total wattage and unit counts in comments.

## Design Decisions

| Decision | Rationale |
|---|---|
| **Exclusion Filter** (`Garage-Lights`) | Prevents unintentional inclusion of residential garage lighting in the exterior totals. |
| **Wattage Fallbacks** | Ensures all building types are accounted for even when prototype IDFs lack exterior lighting objects. |
| **Shared Schedule** | Simplifies the final IDF string and ensures consistency across the neighbourhood cluster. |

## Verification Plan

### Manual Verification
1. Run `python main_ext_lights.py` from the project root.
2. Define a neighbourhood (e.g., `CR1_IAL`).
3. Add buildings (e.g., 14 Attached Houses, 1 QSR).
4. Verify the output in `outputs_txt/`:
   - `CR1_IAL_ExtLights_AttachedHouse` should show scaled wattage (14 x per-unit).
   - `CR1_IAL_ExtLights_QSR` should use the fallback value since ASHRAE QSR has no exterior lights.
