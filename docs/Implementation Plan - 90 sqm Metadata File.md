# Implementation Plan: 90 sqm Metadata File

## Goal Description
Create a new version of the metadata summary report (`US+SF+CZ6A+gasfurnace+unheatedbsmt+IECC_2024_metadata.html`) scaled from the original 110.4 sqm footprint area down to a 90 sqm footprint area. Based on user feedback, interior loads (occupancy, lighting, etc.) will be presented as **normalized values**, matching the original unit formats (e.g. `[W/m2]`, `[people/m2]`, etc.), and the **garage will be excluded entirely** from the report.

## Proposed Changes

### 1. File Creation
- [NEW] `outputs/low_rise_Res/US+SF+CZ6A+gasfurnace+unheatedbsmt_90sqm_IECC_2024_metadata.html`
  - This file will be a direct copy of the original HTML, with the floor area variables adjusted and garage references removed.

### 2. Update Floor Area Summary
The general areas will be updated to reflect a 90 sqm footprint without the garage (originally 37.16 sqm):
- **Total Conditioned Area [m2]**: Decrease from `220.8178` to `180.0` (Assuming 2 stories: 90 x 2).
- **Total Unconditioned Area [m2]**: Decrease from `147.5701` to `90.0` (Basement footprint is adjusted to 90 sqm, and the garage is removed).
- **Total Built Area [m2]**: Decrease from `368.388` to `270.0` (180.0 + 90.0).

### 3. Update Zone Metadata Detail & Interior Loads
For a 90 sqm footprint, the areas will be scaled, while the normalized internal loads will be retained exactly as they were:
- **living_unit1**: 
  - Floor Area [m2]: Update to `90 (Footprint)`
  - Occupancy [people/m2]: `0.0136` (No change)
  - Lighting [W/m2]: `1.5306` (No change)
  - Electric Equipment [W/m2]: `5.5122` (No change)
  - Gas Equipment [W/m2]: `4.518` (No change)
  - SHW [L/h.m2]: `0.0582` (No change)
  - Ventilation [m3/s.m2]: `0.00013` (No change)
- **unheatedbsmt_unit1**: Floor Area [m2] updated to `90`.
- **attic_unit1**: Floor Area [m2] scaled proportionally from `165.28` to `134.72`.
- **garage1**: *Entire row will be removed.*

### 4. Remove Other Garage References
- **HVAC System Metadata**: The row for `garage1` will be removed.

### 5. Update Building Process Loads
- **Exterior Lighting**: 
  - `Exterior-Lights_unit1`: Scale power proportionally from 110.4 sqm down to 90 sqm. Value decreases from `43.2425` W to `35.25` W.
  - `Garage-Lights_unit1`: *Entire row will be removed.*

## Verification Plan
### Automated & Manual Verification
- After generating the new HTML file, I will parse it via Python to ensure the tables display the updated 90 sqm area, the garage has been successfully stripped from all tables, and the normalized load values are preserved exactly.
- Ensure the base64 image and CSS styling from the original file remain intact.
