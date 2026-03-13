# IDF Comparator — Implementation Plan

## Purpose

Compare any two IDF files to identify content differences that can impact energy demand.
This is a **general-purpose comparison method** — it can be applied to any pair of IDF files,
regardless of building type, climate zone, or source software.

The ASHRAE 90.1-2022 Small Office (Denver) files referenced throughout this document are **examples only**,
used to develop and validate the comparison logic. The tool is not tied to this building type.

The primary use case is validating an externally-built IDF against a trusted reference IDF to diagnose
simulation result discrepancies between tools.

**Example — trusted reference:** `Content/ASHRAE901_STD2022/ASHRAE901_OfficeSmall_STD2022_Denver.idf`
**Example — file to question:** `Content/Compare_idfs/smallOffice_HVAC.idf`

---

## Baseline: Trusted Reference Values (from HTML metadata report)

### Zone Metadata — ASHRAE901_OfficeSmall_STD2022_Denver

| Zone | Floor Area | Occupancy | Lighting | Elec Equip | SHW | Infiltration | Ventilation | Htg / Clg Setpoint |
|---|---|---|---|---|---|---|---|---|
| Attic | 567.98 m² | 0 | 0 | 0 | 0 | 0.00033 m³/s·m² | — | 0 / 0 |
| Core_ZN | 149.66 m² | 0.0538 p/m² | 6.18 W/m² | 6.78 W/m² | 0.0974 L/h·m² @ 48.8°C | 0 | 0.00043 m³/s·m² | 21.11 / 23.89°C |
| Perimeter ×4 | 113.45 m² | 0.0538 p/m² | 6.18 W/m² | 6.78 W/m² | 0 | 0.0002 m³/s·m² | 0.00043 m³/s·m² | 21.11 / 23.89°C |

### HVAC
- All conditioned zones: `PSZAC_ASHP` (PSZ-AC with Air-Source Heat Pump)
- DCV: No | Economizer: NoEconomizer

### Construction
| Element | Value |
|---|---|
| Wall R-value | 7.0 m²·K/W |
| Roof R-value | 14.1 m²·K/W |
| Floor R-value | 1.2 m²·K/W |
| Window U-value | 1.09 W/m²·K |

**Wall layers (outside→inside):** 1IN Stucco (2.5 cm) · 8IN CONCRETE HW (20.3 cm) · Wall Insulation HP (33.0 cm) · 1/2IN Gypsum (1.3 cm)
**Roof layers:** Roof Membrane (0.9 cm) · Roof Insulation HP (68.8 cm) · Metal Decking (0.1 cm)
**Floor layers:** HW CONCRETE (10.2 cm) · Slab Insulation HP (4.4 cm) · CP02 CARPET PAD
**Window layers:** ECABS-2 BLEACHED 6MM · ARGON 13MM · CLEAR 12MM · ARGON 13MM · CLEAR 12MM

---

## Already-Identified Differences (pre-implementation analysis, Small Office example)

Impact is scored **0–10**, where 10 = dominant effect on annual energy demand, 0 = no energy effect.

| Category | Trusted (ASHRAE901) | Compare (smallOffice_HVAC) | Impact (0–10) |
|---|---|---|---|
| HVAC system type | PSZ-AC with ASHP (`AirLoopHVAC:UnitaryHeatPump:AirToAir`) | VAV with reheat (`AirTerminal:SingleDuct:VAV:Reheat` + `Boiler:HotWater`) | 10 |
| Heating source | `Coil:Heating:DX:SingleSpeed` (heat pump, COP ~3) | `Coil:Heating:Water` (hydronic, boiler-fed, ~0.8 efficiency) | 10 |
| Cooling coil | `Coil:Cooling:DX:SingleSpeed` | `Coil:Cooling:DX:TwoSpeed` | 7 |
| Fan type | `Fan:OnOff` (cycling) | `Fan:VariableVolume` (continuous, VAV) | 7 |
| Daylighting controls | Present (`Daylighting:Controls`) | Missing | 6 |
| EMS daylighting | Present (5 EMS object types) | Missing | 5 |
| Internal mass | Present (`InternalMass`) | Missing | 4 |
| SHW objects | `WaterHeater:Mixed` only | + `WaterHeater:Sizing` + `Site:WaterMainsTemperature` | 3 |
| Space objects | Absent | Present (`Space`, `SpaceList`) | 2 |
| PV system | Present (`ElectricLoadCenter:*`, `Generator:PVWatts`) | Missing | 2 |
| Schedule format | `Schedule:Compact` | `Schedule:Year/Week:Daily/Day:Interval` | 0 (different format, same intent) |

---

## Implementation

### Phase 1 — Core comparison engine: `idf_comparator.py`

**Data flow:**
```
parse both IDFs (reuse idf_parser.py)
        ↓
filter to energy-relevant object types
        ↓
for each object type:
  ├── count instances in each file
  ├── match instances by name (field[0])
  ├── for matched objects: compare field-by-field
  │       ├── numeric: absolute + relative tolerance
  │       └── string: case-insensitive equality
  └── report: missing in A | missing in B | value mismatches
        ↓
return structured diff dict
```

**Energy-relevant object categories:**

1. **Envelope**
   - `BuildingSurface:Detailed`, `FenestrationSurface:Detailed`
   - `Construction`, `Material`, `Material:NoMass`
   - `WindowMaterial:Glazing`, `WindowMaterial:Gas`, `WindowMaterial:SimpleGlazingSystem`

2. **Internal loads**
   - `Lights`, `ElectricEquipment`, `GasEquipment`, `People`, `InternalMass`

3. **Infiltration & ventilation**
   - `ZoneInfiltration:DesignFlowRate`
   - `DesignSpecification:OutdoorAir`, `Controller:MechanicalVentilation`

4. **HVAC equipment**
   - `AirLoopHVAC`, `AirLoopHVAC:UnitaryHeatPump:AirToAir`
   - `Coil:Cooling:DX:SingleSpeed`, `Coil:Cooling:DX:TwoSpeed`
   - `Coil:Heating:DX:SingleSpeed`, `Coil:Heating:Water`, `Coil:Heating:Fuel`
   - `Fan:OnOff`, `Fan:VariableVolume`
   - `Pump:ConstantSpeed`, `Pump:VariableSpeed`
   - `Boiler:HotWater`
   - `AirTerminal:SingleDuct:ConstantVolume:NoReheat`, `AirTerminal:SingleDuct:VAV:Reheat`
   - `ZoneHVAC:EquipmentList`, `ZoneHVAC:AirDistributionUnit`

5. **Controls & setpoints**
   - `ThermostatSetpoint:DualSetpoint`, `ZoneControl:Thermostat`
   - `SetpointManager:Scheduled`, `SetpointManager:MixedAir`

6. **SHW**
   - `WaterHeater:Mixed`, `WaterUse:Equipment`, `WaterUse:Connections`

7. **Schedules**
   - Resolve and compare setpoint, occupancy, and lighting schedule profiles
   - Handle format differences: `Schedule:Compact` vs `Schedule:Year/Week:Daily/Day:Interval`

8. **Site & simulation globals**
   - `Building`, `Site:Location`, `SimulationControl`, `Timestep`

---

### Phase 2 — HTML report generator

Output file: `outputs/<file_a>_vs_<file_b>_comparison.html`
Styled consistently with existing metadata reports.

**Report sections:**

1. **Summary card** — counts: missing objects, value mismatches, matched/identical
2. **Missing objects table** — objects present in A but not B, and vice versa (with severity tag)
3. **Value diff table** — per object, per field:
   - Red = mismatch
   - Green = match
   - Yellow = within tolerance but different
4. **Schedule comparison** — side-by-side resolved setpoint/occupancy profiles
5. **Impact score tagging (0–10)**
   - `9–10`: HVAC system type, heating/cooling source (e.g. heat pump vs boiler)
   - `6–8`: coil type, fan type, construction R/U-values, setpoints, infiltration rates
   - `3–5`: daylighting controls, EMS, internal mass, SHW configuration
   - `1–2`: PV system, space objects, supplementary SHW objects
   - `0`: schedule format differences with equivalent resolved values, output/reporting objects

---

### Phase 3 — Integration with `main.py`

Add menu option: `"Compare two IDF files"`
- Prompts for path to file A (reference) and file B (file to question)
- Runs comparator
- Saves HTML report to `outputs/`
- Prints summary to console

---

## Files to Create / Modify

| File | Action | Description |
|---|---|---|
| `idf_comparator.py` | Create | Core diff engine |
| `compare_report_generator.py` | Create | HTML report generator for comparison output |
| `main.py` | Modify | Add "Compare IDF files" menu option |

---

## Notes

- The `idf_parser.py` tokenizer can be reused as-is — no changes needed.
- Schedule format differences (`Schedule:Compact` vs `Schedule:Year/Week:Daily`) require resolving both to hourly arrays before comparing values.
- Object name matching should be case-insensitive and strip trailing whitespace.
- Some objects (e.g. `Curve:Biquadratic`) have many numeric fields — use 1% relative tolerance for comparison.
- `LifeCycleCost:*` and output-only objects should be excluded from energy-impact analysis.
