# Neighbourhood IDF Report Generator Plan

## Goal Description
The objective is to read neighbourhood `.idf` files generated in `/Users/orcunkoraliseri/Desktop/idf_reader/Content/neighbourhoods`, deduce the buildings and their counts (e.g. 20 Detached Houses, or 6 Apartments + 1 School), and output a concise `.html` report for each IDF in `/Users/orcunkoraliseri/Desktop/idf_reader/outputs/neighbourhoods`. 
The HTML report will exclusively contain an axonometric visual and a table outlining the building contents and their numbers. We will reuse `idf_parser.py` and `visualizer_adapter.py` without modifying them. New files prefixed with `NUs_` will be created to manage this new pipeline independently.

## User Review Required
> [!NOTE]
> Based on recent findings in the `HighDesComm` cluster, the classification logic requires refinement:
> 1. **Restaurant Disambiguation:** Quick Service Restaurants (QSR) and Full Service Restaurants (FSR) share identical zone names (`Dining`, `Kitchen`, `attic`). We must implement a floor area check (from `geometry.py`) to differentiate them (QSR is ~232 m², FSR is ~511 m²).
> 2. **Supermarket Classification:** We need to add a "Supermarket" category to distinguish it from "Standalone Retail", identifying keywords like `Bakery`, `Deli`, `Produce`, and `Sales`.
> 3. **Large Office:** Generic zone names like `Core_bottom`, `Perimeter_bot`, and `Basement` are currently falling through to "Unknown". We need to map these explicitly to **Large Office**.
> 4. **Prefix Extraction:** Ensure the prefix extraction regex strictly pulls the numeric building identifier (e.g., `16_6`) and strips story indicators like `_G`, `_M`, and `_T` to avoid overcounting buildings.

## Proposed Changes

### NUs_main.py (Update)
#### [MODIFY] `NUs_main.py`
This acts as the orchestrator.
- Define `INPUT_DIR = "Content/neighbourhoods"` and `OUTPUT_DIR = "outputs/neighbourhoods"`.
- Find all `.idf` files in `INPUT_DIR`.
- For each file, run the new `NUs_parser.py` logic and `NUs_report.py` logic.

### NUs_parser.py (Update)
#### [MODIFY] `NUs_parser.py`
This module manages the extraction logic specific to neighbourhood IDFs.
- Import `parse_idf` from `idf_parser.py` and `get_zone_geometry` from `geometry.py`.
- **Prefix Extraction:** Use a strict regex `r"^(\d+(?:_\d+)*)"` to isolate the numeric identifier, stripping functional suffixes.
- **Classification Logic:**
  - Group zones by building prefix.
  - Apply keyword matching to identify types like Supermarket (`bakery`, `produce`), Large Office (`core_bottom`, `perimeter_bot`), etc.
  - *Area-based Disambiguation:* For restaurant zones (`dining`, `kitchen`), calculate the total floor area using `get_zone_geometry`. If area < 350 m², classify as `Quick Service Restaurant`; if > 350 m², classify as `Full Service Restaurant`.

### NUs_report.py (Update)
#### [MODIFY] `NUs_report.py`
This generates the HTML string.
- Import `render_idf_to_base64` from `visualizer_adapter.py` to get the image base64 directly from the neighbourhood IDF.
- Receive the building counts from `NUs_parser.py`.
- Output an HTML template tailored to neighbourhood reporting, grouping instances by ASHRAE 90.1 types (now including Supermarket and Full Service Restaurant).

## Verification Plan

### Manual Verification
1. Run `python NUs_main.py`.
2. Inspect the report for `REVISEDlastCluster - HighDesComm_NEWEST – FINAL.idf`.
3. Verify that the Building Content table now correctly states:
   - Large Hotel: 1
   - Large Office: 2 (previously one was Unknown)
   - Midrise Apartment: 1
   - Standalone Retail: 1
   - Supermarket: 1 (previously Standalone Retail)
   - Quick Service Restaurant: 2 (previously 4)
   - Full Service Restaurant (Sit Down): 2 (previously lumped into QSR)
