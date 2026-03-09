# Add Construction Table to HTML Output

Parse high-performance construction sets from `construction_baseline.idf` and add a new "Construction" table section to every HTML report.

## Resolved Items
- ✅ File renamed to `construction_baseline.idf` by user.
- ✅ Window U-value will be read from the `WindowMaterial:SimpleGlazingSystem` / `WindowMaterial:Glazing` objects. Opaque R-values calculated dynamically from `Material` / `Material:NoMass`.

---

## Measurement Method for U-Values and R-Values

### 1. Opaque Surfaces (R-Values)
R-values for opaque constructions (Wall, Roof, Floor) are calculated dynamically by summing the thermal resistance of each individual material layer from outside to inside.

*   **For `Material` objects (Mass materials):**
    The thermal resistance of each layer is calculated as: 
    `Resistance (R) = Thickness (m) / Conductivity (W/m-K)`
*   **For `Material:NoMass` objects:**
    The thermal resistance is taken directly from the `Thermal Resistance {m2-K/W}` field in the IDF definition.

**Validation Example (HPWall - 6.9999 m2-K/W):**
*   `1IN Stucco`: 0.0253m / 0.6918 W/m-K = 0.0366
*   `8IN CONCRETE HW`: 0.2032m / 1.3110 W/m-K = 0.1550
*   `Wall Insulation HP`: 0.32972m / 0.049 W/m-K = 6.7290
*   `1/2IN Gypsum`: 0.0127m / 0.1600 W/m-K = 0.0794
*   *Total Sum = ~7.0 m2-K/W*

### 2. Windows (U-Values)
Calculating a true dynamic U-factor for complex window assemblies requires simulating internal convective and radiative gas loops between glass panes. Therefore, rather than calculating it from raw properties, the window U-value is currently defined directly by the approved template NFRC/EnergyPlus rating.
*   **Target Window (`Dbl Elec Abs Bleached 6mm/13mm Air`):** Hardcoded to the approved value `1.08826 m2-K/W`.

### 3. Construction Thickness
Total construction thickness is the sum of the physical thicknesses of all material layers, displayed in **millimetres (mm)**.

*   **For `Material` objects (Mass materials):**
    Thickness is read directly from `fields[2]` — the same field already parsed for R-value calculation — and converted: `Thickness (mm) = Thickness (m) × 1000`.
*   **For `Material:NoMass` objects:**
    These represent pure thermal resistance with no physical dimension. Stored internally as `0.0`; displayed as `—` in the table.
*   **For Window constructions:**
    Thickness is not reported (displayed as `—`) since the assembly is defined via a hardcoded U-value rather than individual layer geometry.

**Validation Example (HPWall):**
*   `1IN Stucco`: 0.0253 m = **25.3 mm**
*   `8IN CONCRETE HW`: 0.2032 m = **203.2 mm**
*   `Wall Insulation HP`: thickness from IDF `fields[2]` → **variable by climate zone**
*   `1/2IN Gypsum`: 0.0127 m = **12.7 mm**
*   *Total = sum of above layers*

---

## Construction Table Layout

The table will appear as a new card inside the HTML report, placed **between the 3D visualization and the Zone Metadata table**. It uses a paired-column layout (label | value) for each surface type.

### Target Constructions from `construction_baseline.idf`

| Surface | Construction Name | Layers (outside → inside) |
|---------|------------------|--------------------------|
| Wall    | `HPWall`         | 1IN Stucco → 8IN CONCRETE HW → Wall Insulation HP → 1/2IN Gypsum |
| Roof    | `HPRoof`         | Roof Membrane → Roof Insulation HP → Metal Decking |
| Floor   | `HPSlab`         | HW CONCRETE → Slab Insulation HP → CP02 CARPET PAD |
| Window  | `Dbl Elec Abs Bleached 6mm/13mm Air` | ECABS-2 BLEACHED 6MM → ARGON 13MM → CLEAR 12MM → ARGON 13MM → CLEAR 12MM |

### HTML Table Layout (matching your template)

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              construction                                           │
├──────────────────────┬──────────────────────┬──────────────────────┬─────────────────┤
│ Wall                 │ Roof                 │ Floor                │ Window          │
├──────────────────────┼──────────────────────┼──────────────────────┼─────────────────┤
│ R-values (m2-K/W)    │ R-values (m2-K/W)    │ R-values (m2-K/W)    │ U-values        │
│ <calculated>         │ <calculated>         │ <calculated>         │ (m2-K/W)        │
│                      │                      │                      │ 1.08826         │
├──────────────────────┼──────────────────────┼──────────────────────┼─────────────────┤
│ Layers (out→in)      │ Layers (out→in)      │ Layers (out→in)      │ Layers (out→in) │
│  1IN Stucco          │  Roof Membrane       │  HW CONCRETE         │ ECABS-2         │
│  8IN CONCRETE HW     │  Roof Insulation HP  │  Slab Insulation HP  │   BLEACHED 6MM  │
│  Wall Insulation HP  │  HP Metal Decking    │  CP02 CARPET PAD     │ ARGON 13MM      │
│  1/2IN Gypsum        │                      │                      │ CLEAR 12MM      │
│                      │                      │                      │ ARGON 13MM      │
│                      │                      │                      │ CLEAR 12MM      │
└──────────────────────┴──────────────────────┴──────────────────────┴─────────────────┘
```

> [!NOTE]
> Each surface type occupies **two HTML columns** (label + value). Empty cells fill where layer counts differ across surfaces.

### Updated HTML Table Layout — with Thickness (proposed)

A new **Thickness (mm)** row is inserted immediately after the R/U-value row. Each layer name in the layer rows is annotated with its individual thickness in mm. `MATERIAL:NOMASS` layers and Window show `—` for thickness.

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                    construction                                          │
├──────────────────────────┬──────────────────────────┬──────────────────────┬─────────────┤
│          Wall            │          Roof            │        Floor         │   Window    │
├──────────────────────────┼──────────────────────────┼──────────────────────┼─────────────┤
│ R-values (m2-K/W) │ 7.00 │ R-values (m2-K/W) │ 14.1 │ R-values (m2-K/W) │ 1.20 │ U-values (m2-K/W) │ 1.09 │
├──────────────────────────┼──────────────────────────┼──────────────────────┼─────────────┤
│ Thickness (mm)    │ XXX  │ Thickness (mm)    │ XXX  │ Thickness (mm) │ XXX  │ Thickness (mm) │  —  │
├──────────────────────────┼──────────────────────────┼──────────────────────┼─────────────┤
│ Layers (out→in)          │ Layers (out→in)          │ Layers (out→in)      │ Layers (out→in)    │
│  1IN Stucco · 25.3 mm    │  Roof Membrane · X mm    │  HW CONCRETE · X mm  │  ECABS-2 BLEACHED 6MM      │
│  8IN CONCRETE HW · 203 mm│  Roof Insulation HP · X mm│  Slab Insulation HP · X mm │  ARGON 13MM  │
│  Wall Insulation HP · X mm│  Metal Decking · X mm   │  CP02 CARPET PAD · X mm │  CLEAR 12MM │
│  1/2IN Gypsum · 12.7 mm  │                          │                      │  ARGON 13MM │
│                          │                          │                      │  CLEAR 12MM │
└──────────────────────────┴──────────────────────────┴──────────────────────┴─────────────┘
```

> [!NOTE]
> `X mm` entries are populated dynamically at runtime from each material's `Thickness {m}` field in the IDF.
> `MATERIAL:NOMASS` layers (pure thermal resistance) show no thickness annotation.
> The total `Thickness (mm)` row value = sum of all opaque layer thicknesses for that construction.

---

## Proposed Changes

### Data Extraction
#### [NEW] [construction_extractor.py](file:///Users/orcunkoraliseri/Desktop/idf_reader/construction_extractor.py)
New module (keeps `extractors.py` focused on zone loads):
- **`extract_baseline_constructions(file_path: str) -> list[dict]`**
  - Calls `idf_parser.parse_idf` on `construction_baseline.idf`.
  - Builds a materials lookup from `MATERIAL`, `MATERIAL:NOMASS`, `WINDOWMATERIAL:GLAZING`, `WINDOWMATERIAL:GAS`, and `WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM`.
  - For each target construction (`HPWall`, `HPRoof`, `HPSlab`, `Dbl Elec Abs Bleached 6mm/13mm Air`):
    - Collects layer names in order.
    - Computes total R-value = Σ(thickness / conductivity) for opaque, or reads U-factor for glazing.
  - Returns a list of dicts: `[{label, metric_label, metric_value, layers}, ...]`.

#### [UPDATE] `construction_extractor.py` — add thickness data
Alongside the existing `materials_r` dict, build a parallel `materials_thickness` dict:
```python
materials_thickness: dict[str, float] = {}

for fields in idf_data.get("MATERIAL", []):
    name = fields[0]
    materials_thickness[name] = float(fields[2])   # Thickness (m), same field used for R-value

for fields in idf_data.get("MATERIAL:NOMASS", []):
    name = fields[0]
    materials_thickness[name] = 0.0  # no physical dimension
```
For each target construction, compute and include in the result dict:
```python
layer_thicknesses = [materials_thickness.get(layer, 0.0) for layer in layers]
total_thickness   = sum(layer_thicknesses)   # in metres
```
Return dict shape becomes: `{label, metric_label, metric_value, layers, layer_thicknesses, total_thickness}`.

---

### Report Generation
#### [MODIFY] [report_generator.py](file:///Users/orcunkoraliseri/Desktop/idf_reader/report_generator.py)
- Add a helper **`_build_construction_html(construction_data: list[dict]) -> str`** that renders the paired-column table shown above.
- Update `generate_reports` signature to accept optional `construction_data`.
- Update `generate_html_content` to inject the construction card between the 3D viz and the zone metadata card.

#### [UPDATE] `_build_construction_html()` — render thickness
1. **New metric row** inserted after the R/U-value row:
   - Label cell: `Thickness (mm)`
   - Value cell: `total_thickness * 1000` rounded to 1 decimal, or `—` when `total_thickness == 0`
2. **Layer name annotation**: each layer value cell shows `"layer_name · XX mm"` when `layer_thickness > 0`, or just `layer_name` for `NOMASS` layers and empty cells.
   - Conversion: `round(layer_thicknesses[i] * 1000, 1)` mm

---

### Main Entrypoint
#### [MODIFY] [main.py](file:///Users/orcunkoraliseri/Desktop/idf_reader/main.py)
- Resolve path to `Templates/construction/construction_baseline.idf`.
- Call `extract_baseline_constructions(...)` once.
- Pass result into `generate_reports(...)`.

---

## Verification Plan
### Automated
- Run `python main.py`, select an example IDF, verify no errors.

### Manual
- Open resulting `.html` in a browser.
- Confirm the "construction" table appears with correct R/U-values and layers matching the template layout.
- Verify the **Thickness (mm)** row appears for Wall, Roof, and Floor; Window shows `—`.
- Cross-check a layer: `1IN Stucco` thickness in IDF = 0.0253 m → expect `25.3 mm` in the table.
- Confirm `MATERIAL:NOMASS` layers show no thickness annotation (no ` · X mm` suffix).
