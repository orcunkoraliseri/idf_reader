# Extract Residential AirflowNetwork and Window Visualization

This plan addresses the missing infiltration values and missing window geometry in the 3D visualizer for residential `.idf` files, and provides clarification on the HVAC system mapping.

## HVAC System Note
You asked if we are sure about the HVAC system. The current script identifies it as `PSZAC_GasCoil`. In the residential IDF, the system is modelled using a `ZoneHVAC:AirDistributionUnit` linked to an `AirTerminal:SingleDuct:ConstantVolume:NoReheat`, combined with a Gas Heating Coil and an ERV. In Honeybee template terminology, a residential split-system AC with a gas furnace is functionally identical to a **Packaged Single Zone AC with Gas Coil (PSZAC_GasCoil)**. So while the name sounds commercial, it correctly describes the physics (constant volume forced air, gas heating, direct expansion cooling). 

## Proposed Changes

### `extractors.py`
Residential models use an advanced AirflowNetwork instead of static design flow rates. We need to trace three linked objects to calculate the total infiltration per zone.
#### [MODIFY] extractors.py
- **`extract_infiltration()`**:
  - Parse `AIRFLOWNETWORK:MULTIZONE:SURFACE:EFFECTIVELEAKAGEAREA` to get the base Effective Leakage Area (ELA) for each leakage component.
  - Parse `AIRFLOWNETWORK:MULTIZONE:SURFACE` to map those leakage components to specific `Surface Names`.
  - Look up the `Surface Name` in `BUILDINGSURFACE:DETAILED` to find the corresponding `Zone Name`.
  - Aggregate the ELA for the zone, convert it to a flow rate at 4Pa (`m3/s approx ELA * 2.58`), and divide by the facade area.

### `visualizer_adapter.py`
Standard `.idf` files use `FenestrationSurface:Detailed` (which provides explicit 3D vertices). The residential models use the `Window` object, which defines geometry relative to its parent wall (Starting X, Starting Z, Length, Height).
#### [MODIFY] visualizer_adapter.py
- **`_parse_window_relative()`** (new function): Add vector math to calculate the 4 global 3D vertices of a `Window` based on its Starting X, Starting Z, Length, and Height, projected onto the plane of its parent `BUILDINGSURFACE:DETAILED`.
- **`render_idf_to_base64()`**: Add a new pass to iterate over `WINDOW` objects in the parsed IDF file. For each window, retrieve its parent wall's vertices, calculate the 3D window vertices, and add them to the visualizer's `pending_windows` list so they render correctly in the HTML report.

## Verification Plan

### Automated Tests
- Run the extractor on the target file:
  `python main.py --idf "C:\Users\o_iseri\Desktop\idf_reader\Content\low_rise_Res\US+SF+CZ6A+gasfurnace+unheatedbsmt+IECC_2024.idf"`
- **Infiltration**: Check the generated `US+SF..._metadata.html` file and ensure the `Infiltration [m3/s.m2 facade]` column for `living_unit1` (and other zones) now reports a positive numeric value instead of `0`.
- **Windows**: Open the HTML report and verify that the 3D building geometry now displays the blue window polygons on the exterior walls of the model.
