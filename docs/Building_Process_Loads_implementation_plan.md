# Add Building-Level Process Loads Table to HTML Reports

## Problem Summary

The current HTML reports only show **zone-level** loads (lights, plug loads, gas equipment). However, IDF files also contain significant **building-level process loads** — exterior lights, elevators, and refrigeration systems — that are not assigned to specific zones and are therefore invisible in the current output. These process loads represent a major share of overall building energy consumption.

## IDF Objects to Extract

Survey across all prototypes revealed five categories:

| IDF Object Type | Present In | Zone-Assigned? | Key Fields |
|---|---|---|---|
| `Exterior:Lights` | All prototypes | ❌ No | Name, Schedule, Design Level [W], Subcategory |
| `Exterior:FuelEquipment` | Large Office, Hospital, Large Hotel | ❌ No | Name, Fuel Type, Schedule, Design Level [W], Subcategory |
| `ElectricEquipment` (elevator subcategory) | Sec. School, Hospital | ✅ Yes (Mech zone) | Subcategory = `ElevatorLift` / `ElevatorLightsFan` |
| `Refrigeration:Case` | Schools, Restaurants, Hotel | ✅ Yes (Kitchen zone) | Case Length [m], Rated Cooling Capacity/m [W/m], Operating Temp [°C] |
| `Refrigeration:CompressorRack` | Schools, Restaurants, Hotel | ❌ No (building-level) | Design COP, Condenser Fan Power [W], Subcategory |

> [!IMPORTANT]
> Elevators appear in two different IDF patterns depending on the prototype:
> - **Newer prototypes** (Large Office, Hospital): use `Exterior:FuelEquipment` (building-level)
> - **Older prototypes** (Secondary School): use zone-assigned `ElectricEquipment` in the Mech zone with `ElevatorLift` subcategory
>
> Both must be captured.

---

## Proposed Changes

### Extractors Module

#### [NEW] [process_load_extractor.py](file:///Users/orcunkoraliseri/Desktop/idf_reader/process_load_extractor.py)

New module with a single public function `extract_building_process_loads(idf_data)` that returns a list of dicts, one per process load item. Each dict has:

```python
{
    "category": str,       # "Exterior Lighting" | "Elevator" | "Refrigeration Case" | "Compressor Rack"
    "name": str,           # Object name from IDF
    "power_w": float,      # Design Level [W] (or total capacity for refrig cases)
    "subcategory": str,    # End-Use Subcategory (e.g., "General", "ElevatorLift")
    "zone": str | None,    # Zone name if zone-assigned, None if building-level
    "details": str,        # Extra info (e.g., "COP=2.34", "Case Length=7.32m")
}
```

**Extraction logic per category:**

1. **Exterior Lighting** — Iterate `EXTERIOR:LIGHTS`, read Name (idx 0), Design Level (idx 2)
2. **Exterior Fuel Equipment (Elevators)** — Iterate `EXTERIOR:FUELEQUIPMENT`, read Name (idx 0), Fuel Type (idx 1), Design Level (idx 3), Subcategory (idx 4)
3. **Zone-Assigned Elevators** — Iterate `ELECTRICEQUIPMENT`, filter by subcategory containing `elevator`, read Design Level [W]
4. **Refrigeration Cases** — Iterate `REFRIGERATION:CASE`, read Name (idx 0), Zone (idx 2), Rated Capacity/m (idx 5), Case Length (idx 8), compute total capacity = capacity/m × length
5. **Compressor Racks** — Iterate `REFRIGERATION:COMPRESSORRACK`, read Name (idx 0), Design COP (idx 2), Condenser Fan Power (idx 4)

---

### Report Generator

#### [MODIFY] [report_generator.py](file:///Users/orcunkoraliseri/Desktop/idf_reader/report_generator.py)

Add a new private function `_build_process_loads_html(process_data)` that creates an HTML table card titled **"Building Process Loads"** matching the existing theme. Table columns:

| Category | Name | Power [W] | Zone | Subcategory | Details |
|---|---|---|---|---|---|

Insert this new card **below the Zone Metadata table** and **above the HVAC table** in the HTML output. Update `generate_reports()` and `generate_html_content()` to accept and render the process loads data.

---

### Processor Module

#### [MODIFY] [idf_processor.py](file:///Users/orcunkoraliseri/Desktop/idf_reader/idf_processor.py)

- Import `extract_building_process_loads` from `process_load_extractor`
- Call it after parsing `idf_data`
- Pass the result to `generate_reports()`

---

## Verification Plan

### Automated Tests

Run the tool against the **Secondary School** and **Hospital** IDFs and verify:

```bash
python main.py --idf Content/ASHRAE901_STD2022/ASHRAE901_SchoolSecondary_STD2022_Denver.idf
python main.py --idf Content/ASHRAE901_STD2022/ASHRAE901_Hospital_STD2022_Denver.idf
```

**Expected results for Secondary School:**
- 3× Exterior Lights (453.7 W + 2195.85 W + 2015.29 W)
- 2× Elevator equipment (11793.19 W + 105.31 W in Mech zone)
- 2× Refrigeration Cases (Walk-in Freezer + Display Case in Kitchen)
- 2× Compressor Racks (COP 2.34 + COP 7.12)

**Expected results for Hospital:**
- 1× Exterior Lights (7940.01 W)
- 2× Exterior:FuelEquipment elevators (34667.95 W + 421.26 W)
- 2× Refrigeration Cases
- 2× Compressor Racks

### Manual Verification

Open the generated HTML files and verify:
1. New "Building Process Loads" table appears between the zone table and HVAC table
2. Table styling matches the existing dark theme
3. All values match the source IDF data
