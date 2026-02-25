# IDF Zone Metadata Extractor — Implementation Plan

Parse any EnergyPlus `.idf` file, extract zone-level metadata, normalize all values to the specified units, then export a polished **HTML** summary report.

**N.B.** All target `.idf` files are located under: `/Users/orcunkoraliseri/Desktop/idf_reader/Content/ASHRAE901_STD2022`

## User Review Required

> [!IMPORTANT]
> **Floor-area calculation for `autocalculate` zones:** The script will compute floor area from `BuildingSurface:Detailed` surfaces whose `Surface Type = Floor` and that belong to the zone. If the IDF already provides an explicit floor area in the `Zone` object, that value will be used directly instead.

> [!IMPORTANT]
> **Facade area for infiltration normalization:** The user's request asks to normalize infiltration to *m³/s per m² of facade*. The script will sum exterior wall surface areas per zone from `BuildingSurface:Detailed` (where `Surface Type = Wall` and `Outside Boundary Condition = Outdoors`). If a zone has no exterior walls a warning is logged and infiltration is reported as raw m³/s.

> [!WARNING]
> **Thermostat setpoints:** EnergyPlus stores thermostat setpoints as *schedule references*, not numeric constants. The script will extract the **schedule name** and attempt to parse the first numeric value from the corresponding `Schedule:Compact` or `Schedule:Constant` object. If a schedule cannot be resolved, the schedule name is reported instead.

---

## Proposed Changes

### IDF Parser (`idf_parser.py`)

A generic IDF tokeniser that reads any `.idf` file and returns a dictionary of `{ObjectType: [list of parsed objects]}`. Each parsed object is a list of field values (stripped, with inline `!-` comments removed).

Key design:
- Stream-reads the file line-by-line (memory efficient for 20 K+ line files)
- Handles multi-line objects terminated by `;`
- Ignores full-line `!` comments
- Strips inline comments after `!-`

---

### Geometry Calculator (`geometry.py`)

Computes zone floor areas and facade (exterior wall) areas from `BuildingSurface:Detailed` vertex data.

- **`compute_surface_area(vertices)`** — Shoelace / cross-product method for 3-D polygon area
- **`get_zone_floor_areas(idf_data)`** — Returns `{zone_name: floor_area_m2}`
- **`get_zone_facade_areas(idf_data)`** — Returns `{zone_name: facade_area_m2}`
- Falls back to explicit `Zone` floor-area field when not `autocalculate`

---

### Data Extractors (`extractors.py`)

One function per IDF object type. Each returns a dict of `{zone_name: normalised_value}`.

| Extractor function | IDF Object(s) | Output unit | Normalisation logic |
|---|---|---|---|
| `extract_people()` | `People` | people/m² | Handles `People`, `People/Area`, `Area/Person` methods; divides by zone floor area |
| `extract_lights()` | `Lights` | W/m² | Handles `LightingLevel` (W), `Watts/Area`, `Watts/Person` methods; sums multiple `Lights` per zone |
| `extract_electric_equipment()` | `ElectricEquipment` | W/m² | Same 3-method handling as Lights |
| `extract_gas_equipment()` | `GasEquipment` | W/m² | Same pattern as ElectricEquipment |
| `extract_water_use()` | `WaterUse:Equipment` | L/(h·m²) | Converts peak flow rate from m³/s → L/h, divides by floor area |
| `extract_infiltration()` | `ZoneInfiltration:DesignFlowRate` | m³/(s·m²_facade) | Handles 4 methods (`Flow/Zone`, `Flow/Area`, `Flow/ExteriorWallArea`, `AirChanges/Hour`); converts ACH → m³/s using zone volume; normalises to facade area |
| `extract_ventilation()` | `DesignSpecification:OutdoorAir` | m³/(s·person) or m³/(s·m²) | Reports per-person or per-area rates (matching the IDF method) |
| `extract_thermostat()` | `ZoneControl:Thermostat` + `ThermostatSetpoint:DualSetpoint/SingleHeating/SingleCooling` | °C | Resolves schedule names, extracts first constant value from `Schedule:Compact` / `Schedule:Constant` |
| `extract_process_loads()` | `ElectricEquipment` (elevator subcategory), `Exterior:Lights`, `OtherEquipment` | W/m² | Filters by `End-Use Subcategory` patterns (elevator, refrigeration, etc.) |

---

### Report Generator (`report_generator.py`)

- **`generate_reports(zone_data, output_path, viz_b64=None)`** — Orchestrates the generation of CSV, Markdown, and HTML reports.

- **`generate_csv(zone_data, output_path)`** — Writes a standard CSV with headers.

- **`generate_markdown(zone_data, output_path)`** — Writes a Markdown document with a summary table.

- **`generate_html(zone_data, output_path, viz_b64=None)`** — Generates a modern, responsive HTML preview with a metadata table and optional 3D visualization.

#### [NEW] Table Deduplication Logic

Many ASHRAE prototype buildings contain multiple identical thermal zones (e.g. 30 identical classroom zones across floors and pods). Repeating their rows adds no analytical value when all internal-load values are the same.

**Rules:**

1. **Zone-name prefix grouping:** Zones are considered *duplicates* if they share the same **base name**. The script aggressively strips indices (`_FLR_1`, `_ZN_2`, etc.) and elevation suffixes (`_top`, `_mid`, `_bot`, `_bottom`) to capture vertical zone stacks common in prototype buildings.

2. **Deduplication condition:** Within a group sharing the same base name, if **all internal load columns are identical** (occupancy, lighting, equipment, infiltration, ventilation, setpoints), only the **first representative row** is kept and a `Count` column records how many identical copies were collapsed. **Nota Bene:** Floor area is explicitly excluded from this comparison; zones with different areas but identical loads will be collapsed.

3. **Variation preserved:** If **any** column value differs beyond a small float tolerance (1e-3) within the group — even by a single field (e.g. one floor has a different equipment load) — **every distinct variant in the group is preserved** with its own `Count`.

4. **Column ordering:** The `Count` column appears immediately after the `Zone` column.

5. **Scope:** Deduplication applies to all three output formats (CSV, Markdown, HTML).

---

### 3D Geometry Visualizer (`examples/visualizer.py` → `visualizer_adapter.py`)

> [!IMPORTANT]
> **Dependency:** The existing `examples/visualizer.py` uses `eppy` (a separate third-party library) to load IDF objects. `eppy` must be installed (`pip install eppy`) and requires an **EnergyPlus IDD file** pointed to by the `IDD_FILE` environment variable. If `eppy` is unavailable, the visualizer step will be skipped gracefully and the HTML report will show a placeholder message.

#### [NEW] [visualizer_adapter.py](file:///Users/orcunkoraliseri/Desktop/idf_reader/visualizer_adapter.py)

A thin adapter module that wraps `examples/visualizer.py` and provides a **report-friendly** interface — returning a base64-encoded PNG instead of calling `plt.show()`.

**Key design decisions:**
- Imports `visualize_idf` internals from `examples/visualizer.py`.
- Replaces `plt.show()` with `plt.savefig()` to an in-memory `io.BytesIO` buffer.
- Returns the result as a base64-encoded string ready for direct HTML embedding.

---

### Entry Point (`main.py`)

**Interactive mode (no arguments):**
When `main.py` is run without any arguments, it automatically scans the default IDF directory, displays a menu, and lets the user pick files to process.

**Explicit mode (with --idf flag):**
- `python3 main.py --idf <path>` for targeted processing.

---

## Verification Plan

Run the script against a known IDF:
1. Verify script exits with code 0.
2. Verify all output files (.csv, .md, .html) are created in the `outputs/` directory.
3. Confirm the HTML report contains an embedded `<img>` tag with the 3D model visualization.
4. Verify graceful fallback if `eppy` is missing.
5. **Deduplication check (SchoolSecondary IDF):** Run against `Content/ASHRAE901_STD2022/ASHRAE901_SchoolSecondary_STD2022_Denver.idf`. Confirm that:
   - Classroom zones with identical loads (e.g. all `Mult_Class_1_Pod_*_FLR_*`) are collapsed into a single row with `Count > 1`.
   - Mechanical zones with differing loads (e.g. `Mech_ZN_1_FLR_1` vs `Mech_ZN_1_FLR_2`) are **not** collapsed and both appear as individual rows with `Count = 1`.
