# Add Zone Schedule Table to HTML Reports

## Problem Summary

The current HTML reports show zone-level load **values** (W/m², people/m², etc.) but do not display which **schedules** drive those loads. Schedules are the time-varying multipliers that determine when and how much each load is active. Knowing which schedule is assigned to which zone and load is critical for model review and QA.

## IDF Schedule Structure

Each load object in the IDF references a named `Schedule:Compact` object at a fixed field index:

| Load Type | IDF Object | Zone Field | Schedule Field | Example Schedule |
|---|---|---|---|---|
| Occupancy | `People` | idx 1 | idx 2 | `BLDG_OCC_SCH` |
| Lighting | `Lights` | idx 1 | idx 2 | `ltg_sch_classroom` |
| Electric Equipment | `ElectricEquipment` | idx 1 | idx 2 | `BLDG_EQUIP_SCH` |
| Gas Equipment | `GasEquipment` | idx 1 | idx 2 | `KITCHEN_GAS_EQUIP_SCH` |
| Infiltration | `ZoneInfiltration:DesignFlowRate` | idx 1 | idx 2 | `INFIL_SCH_PNNL` |
| Service Hot Water | `WaterUse:Equipment` | idx 7 | idx 3 | `BLDG_SWH_SCH` |
| Htg Thermostat | `ThermostatSetpoint:DualSetpoint` | via name | idx 1 | `HTGSETP_SCH_YES_OPTIMUM` |
| Clg Thermostat | `ThermostatSetpoint:DualSetpoint` | via name | idx 2 | `CLGSETP_SCH_YES_OPTIMUM` |

> [!NOTE]
> A single schedule can be shared across many zones (e.g., `BLDG_OCC_SCH` serves 38 of 46 zones in the Secondary School). The table will show this relationship clearly by grouping zones per schedule.

---

## Proposed Table Layout

The table will be placed **below the Zone Metadata Detail table** and **above the Building Process Loads table** in the HTML output. It will have five columns:

| Load Type | Schedule Name | Zones (Count) |
|---|---|---|
| Occupancy | `BLDG_OCC_SCH` | Corner_Class, Mult_Class, Corridor, ... (×38) |
| Occupancy | `BLDG_OCC_SCH_Gym` | Gym, Aux_Gym (×2) |
| Occupancy | `BLDG_OCC_SCH_Auditorium` | Auditorium (×1) |
| Lighting | `ltg_sch_classroom` | Corner_Class, Mult_Class (×24) |
| Lighting | `ltg_sch_corridor` | Corridor_Pod, Main_Corridor (×8) |
| Lighting | `ltg_sch_gym` | Gym, Aux_Gym (×2) |
| Electric Equipment | `BLDG_EQUIP_SCH` | All zones (×44) |
| Electric Equipment | `BLDG_ELEVATORS` | Mech (×1) |
| Gas Equipment | `KITCHEN_GAS_EQUIP_SCH` | Kitchen (×1) |
| Infiltration | `INFIL_SCH_PNNL` | All zones (×45) |
| Infiltration | `INFIL_Door_Opening_SCH` | Lobby (×1) |
| Service Hot Water | `BLDG_SWH_SCH` | Bathrooms, Kitchen (×3) |
| Htg Thermostat | `HTGSETP_SCH_YES_OPTIMUM` | Corner_Class, Mult_Class, ... |
| Clg Thermostat | `CLGSETP_SCH_YES_OPTIMUM` | Corner_Class, Mult_Class, ... |

### Load types to include (in order)

1. **Occupancy** — from `People` objects
2. **Lighting** — from `Lights` objects
3. **Electric Equipment** — from `ElectricEquipment` objects
4. **Gas Equipment** — from `GasEquipment` objects
5. **Infiltration** — from `ZoneInfiltration:DesignFlowRate` objects
6. **Service Hot Water** — from `WaterUse:Equipment` objects
7. **Heating Setpoint** — from `ThermostatSetpoint:DualSetpoint` (idx 1)
8. **Cooling Setpoint** — from `ThermostatSetpoint:DualSetpoint` (idx 2)

### Zone display format

To keep the table compact, zones will be shown as **deduplicated base names** (using the existing `_get_base_name()` function), with a count in parentheses. For example:
- `Corner_Class, Mult_Class, Corridor, Lobby (×38)` instead of listing all 38 full zone names.

---

## Proposed Changes

### Extractors Module

#### [NEW] [schedule_extractor.py](file:///Users/orcunkoraliseri/Desktop/idf_reader/schedule_extractor.py)

New module with a single public function:

```python
def extract_zone_schedules(idf_data: dict) -> list[dict[str, str]]:
    """Extracts schedule-to-zone mappings for all load types.

    Returns:
        A list of dicts, each representing one row in the schedule table:
        {
            "load_type": str,        # "Occupancy", "Lighting", etc.
            "schedule_name": str,    # e.g. "BLDG_OCC_SCH"
            "zones": list[str],      # List of full zone names
        }
    """
```

**Extraction logic:**

| Load Type | Object Key | Zone Idx | Schedule Idx |
|---|---|---|---|
| Occupancy | `PEOPLE` | 1 | 2 |
| Lighting | `LIGHTS` | 1 | 2 |
| Electric Equipment | `ELECTRICEQUIPMENT` | 1 | 2 |
| Gas Equipment | `GASEQUIPMENT` | 1 | 2 |
| Infiltration | `ZONEINFILTRATION:DESIGNFLOWRATE` | 1 | 2 |
| Service Hot Water | `WATERUSE:EQUIPMENT` | 7 | 3 |
| Heating Setpoint | `THERMOSTATSETPOINT:DUALSETPOINT` | name-based | 1 |
| Cooling Setpoint | `THERMOSTATSETPOINT:DUALSETPOINT` | name-based | 2 |

For thermostat setpoints, the zone name is extracted from the object name by stripping the ` Dual SP Control` suffix.

---

### Report Generator

#### [MODIFY] [report_generator.py](file:///Users/orcunkoraliseri/Desktop/idf_reader/report_generator.py)

1. Add a new private function `_build_schedule_html(schedule_data)` that creates an HTML table card titled **"Zone Schedule Assignments"**.
2. The function will use `_get_base_name()` to deduplicate zone names for compact display.
3. Update `generate_reports()` and `generate_html_content()` to accept and render the schedule data.
4. Insert the new card **below the Zone Metadata Detail table** and **above the Building Process Loads table**.

---

### Processor Module

#### [MODIFY] [idf_processor.py](file:///Users/orcunkoraliseri/Desktop/idf_reader/idf_processor.py)

- Import `extract_zone_schedules` from `schedule_extractor`
- Call it after parsing `idf_data`
- Pass the result to `generate_reports()`

---

## Verification Plan

### Automated Tests

```bash
python main.py --idf Content/ASHRAE901_STD2022/ASHRAE901_SchoolSecondary_STD2022_Denver.idf
python main.py --idf Content/ASHRAE901_STD2022/ASHRAE901_Hospital_STD2022_Denver.idf
```

**Expected for Secondary School:**
- 6 Occupancy schedules, 11 Lighting schedules, 5 Electric Equipment schedules, 1 Gas Equipment schedule, 2 Infiltration schedules, 1 SHW schedule, + thermostat schedules
- Total ~30 rows in the table

### Manual Verification

Open the generated HTML files and verify:
1. Schedule table appears below the zone table, above the process loads table
2. Table styling matches the existing dark theme
3. Zone counts are correct and base names are properly deduplicated
