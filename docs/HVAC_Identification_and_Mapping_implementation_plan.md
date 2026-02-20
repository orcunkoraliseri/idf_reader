# HVAC Identification and Mapping Implementation Plan

## Goal Description
Enhance the IDF parsing script to automate the identification and mapping of HVAC systems for each thermal zone. The script will determine the conditioning status of each zone (labeling them as 'Unconditioned' if applicable). For conditioned zones, it will identify the specific HVAC system and map it to the closest equivalent Honeybee/Ladybug HVAC template (e.g., PSZ, VAV, PTAC) found in the `HVAC_templates` folder. Additionally, it will extract the presence of Demand Controlled Ventilation (DCV) and the specific Economizer type. Finally, it will output a second, dedicated table summarizing these HVAC metrics in the generated CSV, Markdown, and HTML reports without modifying the primary results table.

## User Review Required

> [!IMPORTANT]
> **Heuristic Mapping to Honeybee Templates:** The EnergyPlus models (like ASHRAE 90.1 prototypes) don't explicitly use the Honeybee template names. We implement global plant scanning to resolve sub-types:
> - **Template Classes**: `VAV`, `PSZ`, `PTAC`, `PTHP`, `WSHP`, `FCU`, `IdealLoads`.
> - **Plant Resolution**: Scans the IDF for `Boiler:HotWater`, `Chiller:Electric:EIR`, `DistrictHeating`, `DistrictCooling`, `Coil:Heating:Fuel` (Gas), and `Coil:Heating:DX` (Heat Pump).
> - **Specific Sub-types**: Maps to explicit Honeybee Enums like `VAV_Chiller_Boiler`, `VAV_ACChiller_ASHP`, `PSZAC_GasCoil`, etc.
>
> [!NOTE]
> **Prototype Modeling Rules**: 
> - **ASHRAE 90.1**: Used for commercial mid-rise and high-rise buildings.
> - **IECC**: Used for low-rise residential and commercial buildings.
> - **Source of Truth**: [energycodes.gov/prototype-building-models](https://www.energycodes.gov/prototype-building-models) for cross-referencing anomalies.

> [!NOTE]
> **CSV Output Format:** The request specifies that the output should be a "second, dedicated table placed below the first". For Markdown and HTML, this is straightforward. For CSV, we will create a **second CSV file** (e.g., `<filename>_hvac_metadata.csv`) to maintain tabular integrity, rather than appending a differently-shaped table at the bottom of the first CSV.

## Proposed Changes

### `extractors.py`
Add new extraction functions to pull HVAC system configurations:
#### [MODIFY] [extractors.py](file:///Users/orcunkoraliseri/Desktop/idf_reader/extractors.py)
- **`extract_hvac_systems(idf_data, zone_geo)`**:
  - **Conditioning Status**: Check if the zone is linked to a thermostat (`ZoneControl:Thermostat`) and/or HVAC equipment. If not, label as 'Unconditioned'.
  - **Honeybee Template Mapping**: Trace the zone's connections in `ZoneHVAC:*` objects or `AirTerminal:*` objects linked to `AirLoopHVAC`.
  - **VAV vs PVAV Distinction**: When a VAV terminal is detected, the system checks for a chiller (System 7/8 → `VAV`) vs DX cooling coils (System 5/6 → `PVAV`). This is critical for buildings like Medium Office which use DX packaged units with VAV terminals.
  - **Plant-Level Inference**: Scans global objects (Chillers, Boilers, DX Coils) to refine generic base classes into specific Honeybee sub-types (e.g., `VAV_Chiller_Boiler`, `PVAV_BoilerElectricReheat`).
  - **Robust Equipment Parsing**: Iterates through `ZoneHVAC:EquipmentList` fields to correctly identify secondary equipment and air distribution units, even when sequence fields are omitted (fixing "Unknown" zone issues).
  - **Zone → AirLoop → Controller Mapping**: Builds a proper chain from `AirLoopHVAC:ZoneSplitter` outlet nodes to AirLoop names, then maps each AirLoop to its `Controller:OutdoorAir` and `Controller:MechanicalVentilation`. This replaces heuristic prefix matching and correctly resolves DCV/Economizer for all prototype buildings.
  - **Economizer Type**: Extracted via AirLoop → Controller:OutdoorAir chain. Defaults to `NoEconomizer` if no controller is found.
  - **DCV Status**: Extracted via AirLoop → Controller:MechanicalVentilation chain. Defaults to `No` if no controller is found (common in Hospital critical zones like ER/OR).

### `main.py`
Update the main entry point to call the new HVAC extractor and pass the results to the report generator.
#### [MODIFY] [main.py](file:///Users/orcunkoraliseri/Desktop/idf_reader/main.py)
- Call `extract_hvac_systems()` to get a dictionary of HVAC metrics per zone.
- Update the structure passed to `generate_reports` to include this new `hvac_data` dictionary or pass it as a separate argument so it can be rendered as a standalone table.

### `report_generator.py`
Update the report generation logic to create and append the second HVAC table.
#### [MODIFY] [report_generator.py](file:///Users/orcunkoraliseri/Desktop/idf_reader/report_generator.py)
- **HTML Output**: Generate a single, detailed HTML report containing both metadata tables and the 3D visualization.
- **Headers**: `"Thermal Zone"`, `"Count"`, `"Honeybee HVAC Template"`, `"DCV Status"`, `"Economizer Configuration"`.
- **HVAC Table Deduplication**:
  - Implement a shared `_collapse_rows` helper to ensure consistency.
  - Groups zones by "Base Name" (stripping floor/pod/vertical suffixes).
  - Within each group, collapse rows where the `Honeybee HVAC Template`, `DCV Status`, and `Economizer Configuration` are all identical.
  - Include a `Count` column to indicate the number of identical zones collapsed.

## Verification Plan

### Automated Tests
1. Run `python3 main.py --idf Content/ASHRAE901_STD2022/ASHRAE901_OfficeSmall_STD2022_Denver.idf`.
2. Verify that the primary metadata tables remain unmodified.
3. Inspect `outputs/ASHRAE901_OfficeSmall_STD2022_Denver_metadata.md` and `.html` to ensure the second table appears correctly with headings: Thermal Zone, Honeybee HVAC Template, DCV Status, Economizer Configuration.
4. Verify the output captures `PSZ` type for the OfficeSmall prototype and accurately lists `NoEconomizer` and `No` (for DCV) where applicable based on the IDF grep results.

### Manual Verification
- Ask the user to review the generated HTML and Markdown files for visual correctness and verifying the layout matches their expectations for a "second, dedicated table".
- Have the user confirm if the heuristics accurately classified the HVAC systems for a few benchmark files.
