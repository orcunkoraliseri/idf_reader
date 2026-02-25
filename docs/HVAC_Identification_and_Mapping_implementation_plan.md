# HVAC Identification and Mapping Implementation Plan

## Status: ✅ IMPLEMENTED

This document describes the HVAC identification and mapping feature as it has been built
and deployed in the codebase. All sections reflect the **actual implementation**, not just
the original proposal.

---

## Goal Description

Enhance the IDF parsing script to automate the identification and mapping of HVAC systems
for each thermal zone. The script determines the conditioning status of each zone (labelling
them as `Unconditioned` if applicable). For conditioned zones it identifies the specific HVAC
system and maps it to the closest equivalent Honeybee/Ladybug HVAC template (e.g., `PSZ`,
`VAV`, `PTAC`). It additionally extracts:

- **DCV (Demand Controlled Ventilation)** status per zone.
- **Economizer type** per zone.
- A **second dedicated HVAC table** in the HTML report, separate from the primary zone
  metadata table.

---

## Design Notes

> [!IMPORTANT]
> **Heuristic Mapping to Honeybee Templates:** EnergyPlus prototype models don't use
> Honeybee template names directly. HVAC type is inferred via global plant scanning and
> zone equipment chain traversal:
>
> - **Template Classes**: `VAV`, `PVAV`, `PSZ`, `PTAC`, `PTHP`, `WSHP`,
>   `FCUwithDOASAbridged`, `IdealLoads`, `UnitHeater`, `Radiant`, `Baseboard`.
> - **Plant Resolution**: Scans globally for `Boiler:HotWater`, `Chiller:Electric:EIR`,
>   `DistrictHeating`, `DistrictCooling`, `Coil:Heating:Fuel` (Gas), `Coil:Heating:DX`
>   (Heat Pump), `Coil:Heating:Electric`, and DX cooling coil types.
> - **Specific Sub-types**: Resolves to Honeybee Enum-style strings such as
>   `VAV_Chiller_Boiler`, `VAV_DCW_GasCoil`, `PVAV_BoilerElectricReheat`,
>   `PSZAC_GasCoil`, `PSZAC_BoilerBaseboard`, etc.

> [!NOTE]
> **Prototype Modeling Rules**:
> - **ASHRAE 90.1**: Used for commercial mid-rise and high-rise buildings.
> - **IECC**: Used for low-rise residential and commercial buildings.
> - **Source of Truth**: [energycodes.gov/prototype-building-models](https://www.energycodes.gov/prototype-building-models)
>   for cross-referencing anomalies.

> [!NOTE]
> **Output Format:** The HVAC metadata is output as a **second dedicated card/table in
> the HTML report only** (not in a separate CSV file). The primary zone metadata table
> remains unchanged. This simplifies output file management while keeping the data visually
> separated.

---

## Implemented Changes

### `extractors.py` — `extract_hvac_systems()`

Location: `extract_hvac_systems(idf_data: dict, zone_names: list[str])` (line ~291)

#### Conditioning status
- Identifies conditioned zones via `ZoneControl:Thermostat`.
- Zones absent from `ZoneHVAC:EquipmentConnections` AND not thermostat-controlled are
  labelled `"Unconditioned"` with `dcv = "N/A"` and `economizer = "N/A"`.

#### Global plant scanning (lines ~328–348)
Builds boolean flags from global IDF scans used to resolve specific Honeybee sub-types:

| Flag | Objects Scanned |
|---|---|
| `has_boiler` | `Boiler:HotWater` |
| `has_district_htg` | `DistrictHeating`, `DistrictHeating:Water` |
| `has_district_clg` | `DistrictCooling`, `DistrictCooling:Water` |
| `has_chiller` | `Chiller:Electric:EIR`, `Chiller:Electric` |
| `has_ac_chiller` | Chiller objects containing `AIRCOOLED` in any field |
| `has_gas_coil` | `Coil:Heating:Fuel`, `Coil:Heating:Gas` |
| `has_elec_coil` | `Coil:Heating:Electric` |
| `has_hp_coil` | `Coil:Heating:DX:SingleMixed/SingleSpeed/MultiSpeed` |
| `has_baseboard` | `ZoneHVAC:Baseboard:Convective:Water/Electric` |
| `has_dx_cooling` | `Coil:Cooling:DX:TwoSpeed/SingleSpeed/MultiSpeed/VariableSpeed` |

#### Honeybee template string resolution (lines ~350–388)

Three template base strings are pre-computed at the building level:

- **`vav_template_base`** (System 7/8 — chilled-water VAV): e.g. `VAV_Chiller_Boiler`
  - Cooling tier: `DCW` > `ACChiller` > `Chiller`
  - Heating tier: `DHW` > `Boiler` > `ASHP` > `GasCoil` > `PFP`
- **`pvav_template_base`** (System 5/6 — DX VAV): e.g. `PVAV_BoilerElectricReheat`
  - Heating tier: `DHW` > `Boiler` > `ASHP` > `BoilerElectricReheat` > `PFP`
- **`psz_template_base`** (System 3/4 — PSZ): e.g. `PSZAC_GasCoil`
  - Priority: `DHW` > `Boiler` > `ASHP` > `GasHeaters/GasCoil` > `ElectricBaseboard/ElectricCoil`

#### Zone equipment list parsing (lines ~306–320)
- Iterates `ZoneHVAC:EquipmentList` fields from index 2 onward.
- Recognises component types prefixed with `ZONEHVAC:`, `AIRTERMINAL:`, or `FAN:`.
- Routes to correct Honeybee template based on equipment type:

| IDF Equipment Type | Honeybee Template |
|---|---|
| `ZoneHVAC:PackagedTerminalAirConditioner` | `PTAC` |
| `ZoneHVAC:PackagedTerminalHeatPump` | `PTHP` |
| `ZoneHVAC:WaterToAirHeatPump` | `WSHP` |
| `ZoneHVAC:FourPipeFanCoil` | `FCUwithDOASAbridged` |
| `ZoneHVAC:IdealLoadsAirSystem` | `IdealLoads` |
| `ZoneHVAC:UnitHeater` | `UnitHeater` |
| `ZoneHVAC:HighTemperatureRadiant` | `Radiant` |
| `ZoneHVAC:LowTemperatureRadiant:*` | `Radiant` |
| `ZoneHVAC:Baseboard:*` | `Baseboard` |
| `ZoneHVAC:AirDistributionUnit` | Resolves via ATU type (VAV → VAV/PVAV, CV → PSZ) |

#### VAV vs PVAV distinction
When a `VAV` air terminal is detected through `ZoneHVAC:AirDistributionUnit`:
- If `has_chiller` or `has_district_clg` → maps to `vav_template_base` (System 7/8)
- Else if `has_dx_cooling` → maps to `pvav_template_base` (System 5/6)
- Otherwise → falls back to `vav_template_base`

#### Zone → AirLoop → Controller mapping (lines ~390–437)
Builds the full chain to resolve DCV and Economizer per zone:

1. **`AIRLOOPHVAC:SupplyPath`** objects map splitter component names to AirLoop names.
2. **`AirLoopHVAC:ZoneSplitter`** outlet nodes are parsed to derive zone names, creating
   `zone_to_airloop` (keyed by uppercase zone name).
3. **`Controller:OutdoorAir`** objects are matched to AirLoop names by normalized string
   prefix comparison → `airloop_to_oa`.
4. **`Controller:MechanicalVentilation`** objects are matched similarly → `airloop_to_mv`.
5. Per zone: economizer is read from `oa[7]` (field 8 of the controller), DCV from
   `mv[2]` (field 3 of the MV controller). Defaults: `NoEconomizer` / `No`.

---

### `main.py` — Entry-Point (as-built)

`main.py` now serves strictly as a thin entry-point delegating to `idf_processor.py`:

- Imports `process_file` and `select_idf_interactive` from `idf_processor`.
- Sets `CONTENT_DIR = Content/` (the parent of `ASHRAE901_STD2022/` and `others/`).
- `process_file()` calls `extract_hvac_systems(idf_data, list(zone_geo.keys()))` and
  passes the result as `hvac_data` to `generate_reports()`.

### `idf_processor.py` — Processing Module (NEW)

A new module extracted from the original `main.py` to satisfy the modular design rule:

- **`find_idf_files(base_dir)`**: Recursively walks `base_dir` using `os.walk`, returning
  `(relative_path, full_path)` tuples for all `.idf` files, sorted alphabetically.
- **`select_idf_interactive(base_dir)`**: Displays the numbered file menu, shows relative
  paths (e.g., `ASHRAE901_STD2022/…`, `others/…`), and returns selected absolute paths.
- **`process_file(idf_path, output_dir)`**: Orchestrates parsing, extraction (including
  HVAC), and report generation for a single IDF file.

---

### `report_generator.py` — As-Built

> [!WARNING]
> **Known Structural Issue:** The file contains **two definitions** of `generate_reports()`
> (at lines 32 and 161). The first definition (lines 32–91) is **unreachable dead code**
> — Python will use only the second definition (line 161+). The dead code block should be
> removed in a future cleanup.

#### Active `generate_reports()` (line 161)
- Accepts `hvac_data: dict[str, dict[str, str]] | None`.
- Deduplicates zone rows via `_collapse_rows()` using `comparison_keys` (all keys except
  `floor_area`).
- Deduplicates HVAC rows via `_collapse_rows()` on keys `["template", "dcv", "economizer"]`.
- Renders a single HTML file (`{output_base_path}.html`) containing both tables.
- **No CSV or Markdown output is generated** (only HTML is written to disk).

#### Helper: `_get_base_name(name)` (line 92)
Strips zone name suffixes using two regex passes:
1. `(_FLR|_Pod|_ZN|_\d)+\d*$` — removes floor/pod/zone indices.
2. `(_top|_mid|_bot|_bottom|…)$` (case-insensitive) — removes elevation keywords.

#### Helper: `_collapse_rows(groups, comparison_keys, tolerance=1e-3)` (line 103)
- Groups zones by base name.
- Within each group, collapses rows with identical values on `comparison_keys` within
  `tolerance` for numerics.
- Sets `floor_area_varies = True` on a collapsed row when constituent zones have
  different floor areas.
- Writes `Count` to each collapsed row.

#### HVAC HTML Table (line 275)
Headers: `"Thermal Zone"`, `"Count"`, `"Honeybee HVAC Template"`, `"DCV Status"`,
`"Economizer Configuration"`.

---

## Verification Plan

### Automated Checks
1. Run:
   ```bash
   python main.py --idf Content/ASHRAE901_STD2022/ASHRAE901_OfficeSmall_STD2022_Denver.idf
   ```
2. Verify the primary zone metadata table remains unmodified in the HTML output.
3. Inspect `outputs/ASHRAE901_OfficeSmall_STD2022_Denver_metadata.html` to confirm the
   second HVAC table appears with the correct headers.
4. Confirm `PSZ` type is identified for the OfficeSmall prototype.
5. Confirm `NoEconomizer` and `No` (DCV) appear where expected.
6. Run with `ASHRAE901_OfficeMedium_STD2022_Denver.idf` and verify `PVAV_*` (not
   `VAV_*`) is reported — the DX cooling distinction test.

### Manual Verification
- Review generated HTML for HVAC section visual correctness.
- Confirm HVAC system classification accuracy against a few benchmark IDF files.

---

## Known Issues / Future Work

| Issue | Description |
|---|---|
| No CSV/Markdown output | CSV and Markdown generation removed during refactor; only HTML produced. |
| Ventilation OA heuristic | `extract_ventilation` uses zone-name substring matching on DSOA object names, which may miss zones with unusual naming. |
| Economizer field index | `oa[7]` assumes a fixed field position; if an IDF omits optional fields, the index may be wrong. |
