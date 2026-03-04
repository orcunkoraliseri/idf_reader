# EnergyPlus IDF Version Object Reference

> **Purpose:** Documents how to read key EnergyPlus IDF objects across the different file versions present in this repository's `Content/` folder. Field positions, naming differences, calculation methods, and format variations are captured for each version.

---

## 1. Versions Found in This Repository

| EnergyPlus Version | File Count | Folder(s) | Notes |
|--------------------|-----------|-----------|-------|
| **v8.7** | 20 | `CHV_buildings/`, `others/`, `neighbourhoods/` | Most common; legacy commercial + residential |
| **v8.9** | 1 | `neighbourhoods/` | Residential cluster; simplified object format |
| **v22.1** | 16 | `ASHRAE901_STD2022/` | ASHRAE 90.1-2022 prototypes; PNNL DOE reference |
| **v23.1** | 2 | `low_rise_Res/` | US residential IECC 2024; compact inline format |
| **v24.2** | 2 | `others/` | Residential; updated field names; AirflowNetwork |
| **Total** | **41** | | |

> **Format convention note:**
> - **v8.7:** Multiline objects with no leading indentation; `!-` field comments after each value.
> - **v8.9 / v24.2:** Multiline with 2-space/4-space indentation; `!-` field comments.
> - **v22.1:** Multiline with 4-space indentation; `!-` field comments.
> - **v23.1:** Compact inline format — multiple fields on one line, minimal comments, tabs as separators.

---

## 2. Zone Object — Zone Count & Floor Area

The `Zone,` object defines thermal zones. Floor area can be declared explicitly or auto-calculated from geometry.

### Field Structure

| Field # | v8.7 | v8.9 | v22.1 | v23.1 | v24.2 |
|---------|------|------|-------|-------|-------|
| 1 | Name | Name | Name | Name | Name |
| 2 | Direction of Relative North | Direction of Relative North | Direction of Relative North | Direction of Relative North | Direction of Relative North |
| 3 | X Origin | X Origin | X Origin | X Origin | X Origin |
| 4 | Y Origin | Y Origin | Y Origin | Y Origin | Y Origin |
| 5 | Z Origin | Z Origin | Z Origin | Z Origin | Z Origin |
| 6 | Type | Type | Type | Type | Type |
| 7 | Multiplier | Multiplier | Multiplier | Multiplier | Multiplier |
| 8 | Ceiling Height {m} | *(omitted)* | Ceiling Height {m} | *(omitted)* | *(omitted)* |
| 9 | Volume {m3} | *(omitted)* | Volume {m3} | *(omitted)* | *(omitted)* |
| **10** | **Floor Area {m2}** | *(omitted)* | **Floor Area {m2}** | *(omitted)* | *(omitted)* |
| 11 | Zone Inside Convection Algorithm | *(omitted)* | Zone Inside Convection Algorithm | *(omitted)* | *(omitted)* |
| 12 | Zone Outside Convection Algorithm | *(omitted)* | Zone Outside Convection Algorithm | *(omitted)* | *(omitted)* |
| 13 | Part of Total Floor Area | *(omitted)* | Part of Total Floor Area | *(omitted)* | *(omitted)* |

### Reading Logic

- **v8.7 / v22.1:** Floor area may be specified in **field 10** (value or `autocalculate`). When `autocalculate`, derive from `BuildingSurface:Detailed` floor surfaces for that zone.
- **v8.9 / v23.1 / v24.2:** Field 10 does not exist — floor area is **always auto-calculated** from geometry. Use the sum of floor surface areas associated with the zone.

### Example Blocks

**v8.7 format:**
```
Zone,
16_1_G SW Apartment,             !- Name
0.0000,                           !- Direction of Relative North {deg}
0.0000,                           !- X Origin {m}
0.0000,                           !- Y Origin {m}
0.0000,                           !- Z Origin {m}
1,                                !- Type
1,                                !- Multiplier
,                                 !- Ceiling Height {m}
,                                 !- Volume {m3}
autocalculate,                    !- Floor Area {m2}
,                                 !- Zone Inside Convection Algorithm
,                                 !- Zone Outside Convection Algorithm
Yes;                              !- Part of Total Floor Area
```

**v8.9 / v23.1 / v24.2 format (7 fields only):**
```
  Zone,
    living_unit1,                 !- Name
    0.0,                          !- Direction of Relative North {deg}
    0.0,                          !- X Origin {m}
    0.0,                          !- Y Origin {m}
    0.0,                          !- Z Origin {m}
    ,                             !- Type
    1;                            !- Multiplier
```

---

## 3. People Object — Occupancy [people/m²]

### Field Structure

| Field # | v8.7 | v8.9 | v22.1 | v23.1 | v24.2 |
|---------|------|------|-------|-------|-------|
| 1 | Name | Name | Name | Name | Name |
| 2 | Zone or ZoneList Name | Zone or ZoneList Name | **Zone or ZoneList or Space or SpaceList Name** | Zone or ZoneList Name | **Zone or ZoneList or Space or SpaceList Name** |
| 3 | Number of People Schedule Name | Number of People Schedule Name | Number of People Schedule Name | Number of People Schedule Name | Number of People Schedule Name |
| **4** | **Number of People Calculation Method** | **Number of People Calculation Method** | **Number of People Calculation Method** | **Number of People Calculation Method** | **Number of People Calculation Method** |
| 5 | Number of People | Number of People | Number of People | Number of People | Number of People |
| **6** | **People per Zone Floor Area {person/m²}** | **People per Zone Floor Area {person/m²}** | **People per Floor Area {person/m²}** | **People per Zone Floor Area {person/m²}** | **People per Floor Area {person/m²}** |
| **7** | **Zone Floor Area per Person {m²/person}** | **Zone Floor Area per Person {m²/person}** | **Floor Area per Person {m²/person}** | **Zone Floor Area per Person {m²/person}** | **Floor Area per Person {m²/person}** |
| 8 | Fraction Radiant | Fraction Radiant | Fraction Radiant | Fraction Radiant | Fraction Radiant |
| 9 | Sensible Heat Fraction | Sensible Heat Fraction | Sensible Heat Fraction | Sensible Heat Fraction | Sensible Heat Fraction |
| 10 | Activity Level Schedule Name | Activity Level Schedule Name | Activity Level Schedule Name | Activity Level Schedule Name | Activity Level Schedule Name |

### Calculation Methods & Reading Logic

**Field 4 — `Number of People Calculation Method`** controls which density field is populated:

| Method | Active Field | Unit | How to Get [people/m²] |
|--------|-------------|------|------------------------|
| `People` | Field 5 | absolute count | divide by zone floor area |
| `People/Area` | Field 6 | person/m² | **use directly** |
| `Area/Person` | Field 7 | m²/person | take reciprocal (1 / field 7) |

### Key Field Name Change
- **v8.7 / v8.9 / v23.1:** `"People per Zone Floor Area"` and `"Zone Floor Area per Person"`
- **v22.1 / v24.2:** `"People per Floor Area"` and `"Floor Area per Person"` (dropped "Zone")

Both refer to the same concept — the field **position** (6 and 7) is unchanged.

---

## 4. Lights Object — Lighting [W/m²]

### Field Structure

| Field # | v8.7 | v8.9 | v22.1 | v23.1 | v24.2 |
|---------|------|------|-------|-------|-------|
| 1 | Name | Name | Name | Name | Name |
| 2 | Zone or ZoneList Name | Zone or ZoneList Name | Zone or ZoneList or Space or SpaceList Name | Zone or ZoneList Name | Zone or ZoneList or Space or SpaceList Name |
| 3 | Schedule Name | Schedule Name | Schedule Name | Schedule Name | Schedule Name |
| **4** | **Design Level Calculation Method** | **Design Level Calculation Method** | **Design Level Calculation Method** | **Design Level Calculation Method** | **Design Level Calculation Method** |
| 5 | Lighting Level {W} | Lighting Level {W} | Lighting Level {W} | Lighting Level {W} | Lighting Level {W} |
| **6** | **Watts per Zone Floor Area {W/m²}** | **Watts per Zone Floor Area {W/m²}** | **Watts per Zone Floor Area {W/m²}** | **Watts per Zone Floor Area {W/m²}** | **Watts per Floor Area {W/m²}** |
| 7 | Watts per Person {W/person} | Watts per Person {W/person} | Watts per Person {W/person} | Watts per Person {W/person} | Watts per Person {W/person} |

### Calculation Methods & Reading Logic

**Field 4 — `Design Level Calculation Method`:**

| Method | Active Field | How to Get [W/m²] |
|--------|-------------|-------------------|
| `Watts/Area` | Field 6 | **use directly** |
| `LightingLevel` | Field 5 | divide by zone floor area |
| `Watts/Person` | Field 7 | multiply by occupant density |

### Key Field Name Change
- **v8.7 / v8.9 / v22.1 / v23.1:** `"Watts per Zone Floor Area"`
- **v24.2:** `"Watts per Floor Area"` (dropped "Zone") — **same field position 6**

---

## 5. ElectricEquipment Object — Electric Equipment [W/m²]

### Field Structure

| Field # | All Versions | Notes |
|---------|-------------|-------|
| 1 | Name | |
| 2 | Zone or ZoneList Name | v22.1/v24.2 add "or Space or SpaceList" |
| 3 | Schedule Name | |
| **4** | **Design Level Calculation Method** | |
| 5 | Design Level {W} | populated when Method = `EquipmentLevel` |
| **6** | **Watts per Zone Floor Area / Watts per Floor Area {W/m²}** | populated when Method = `Watts/Area`; v24.2 drops "Zone" |
| 7 | Watts per Person {W/person} | populated when Method = `Watts/Person` |
| 8 | Fraction Latent | |
| 9 | Fraction Radiant | |
| 10 | Fraction Lost | |
| 11 | End-Use Subcategory | optional |

### Calculation Methods & Reading Logic

**Field 4 — `Design Level Calculation Method`:**

| Method | Active Field | How to Get [W/m²] |
|--------|-------------|-------------------|
| `Watts/Area` | Field 6 | **use directly** |
| `EquipmentLevel` | Field 5 | divide by zone floor area |
| `Watts/Person` | Field 7 | multiply by occupant density |

### Format Difference — v23.1 Compact Format

In v23.1, ElectricEquipment objects generated from templates use a compact inline format with **no field comments** and fields run together without spacing:

```
ElectricEquipment,
dishwasher1,
living_unit1,
DishWasher_equip_sch,
EquipmentLevel,
65.698787492023,
,,
0.15,
0.6,
0.25,
dishwasher;
```

Note the `,,` at position 6-7 — two empty comma-separated fields in one line (Watts per Floor Area and Watts per Person are both blank because Method = `EquipmentLevel`).

---

## 6. GasEquipment Object — Gas Equipment [W/m²]

### Presence by Version

| Version | Present | Notes |
|---------|---------|-------|
| v8.7 | No | Commercial buildings use electric equipment only |
| v8.9 | No | Residential cluster |
| v22.1 | No | ASHRAE prototype buildings |
| **v23.1** | **Yes** | Residential appliances (dryer, range/oven) |
| v24.2 | No | Uses electric equivalents |

### Field Structure (v23.1)

| Field # | Description |
|---------|-------------|
| 1 | Name |
| 2 | Zone or ZoneList Name |
| 3 | Schedule Name |
| **4** | **Design Level Calculation Method** |
| 5 | Design Level {W} — active when Method = `EquipmentLevel` |
| 6 | Watts per Zone Floor Area {W/m²} — active when Method = `Watts/Area` |
| 7 | Watts per Person {W/person} |
| 8 | Fraction Latent |
| 9 | Fraction Radiant |
| 10 | Fraction Lost |
| 11 | *(optional)* CO₂ Generation Rate |
| 12 | End-Use Subcategory |

**v23.1 compact example:**
```
GasEquipment,
gas_dryer1,
living_unit1,
ClothesDryer,
EquipmentLevel,
395.595891809135,
,,
0.05,
0.1,
0.85,
,
gas_dryer;
```

Same `,,` convention as ElectricEquipment for two empty fields on one line.

---

## 7. WaterUse:Equipment Object — SHW [L/h·m²] & SHW Target Temp [°C]

### Field Structure

| Field # | v8.7 | v8.9 | v22.1 | v23.1 | v24.2 |
|---------|------|------|-------|-------|-------|
| 1 | Name | Name | Name | Name | Name |
| 2 | End-Use Subcategory | End-Use Subcategory | End-Use Subcategory | End-Use Subcategory | End-Use Subcategory |
| **3** | **Peak Flow Rate {m³/s}** | **Peak Flow Rate {m³/s}** | **Peak Flow Rate {m³/s}** | **Peak Flow Rate {m³/s}** | **Peak Flow Rate {m³/s}** |
| 4 | Flow Rate Fraction Schedule Name | Flow Rate Fraction Schedule Name | Flow Rate Fraction Schedule Name | Flow Rate Fraction Schedule Name | Flow Rate Fraction Schedule Name |
| **5** | **Target Temperature Schedule Name** | **Target Temperature Schedule Name** | **Target Temperature Schedule Name** | **Target Temperature Schedule Name** | **Target Temperature Schedule Name** |
| 6 | Hot Water Supply Temperature Schedule Name | *(omitted)* | Hot Water Supply Temperature Schedule Name | *(omitted)* | *(omitted)* |
| 7 | Cold Water Supply Temperature Schedule Name | *(omitted)* | Cold Water Supply Temperature Schedule Name | *(omitted)* | *(omitted)* |
| 8 | Zone Name | *(omitted)* | Zone Name | *(omitted)* | *(omitted)* |
| 9 | Sensible Fraction Schedule Name | *(omitted)* | Sensible Fraction Schedule Name | *(omitted)* | *(omitted)* |
| 10 | Latent Fraction Schedule Name | *(omitted)* | Latent Fraction Schedule Name | *(omitted)* | *(omitted)* |

### Reading Logic

**SHW Flow [L/h·m²]:**
1. Read **Field 3** (`Peak Flow Rate` in m³/s).
2. Convert: `L/h = m³/s × 3,600,000`.
3. Divide by zone floor area to get `L/h·m²`.
4. There are typically **multiple `WaterUse:Equipment` objects per zone** (e.g., clothes washer, dishwasher, shower, sinks). **Sum all peak flow rates** for the zone.

**SHW Target Temperature [°C]:**
1. Read **Field 5** (Target Temperature Schedule Name).
2. Locate the corresponding `Schedule:Compact` or `Schedule:Constant` object.
3. Extract the temperature value from the schedule.

| Version | Typical Target Temp Found |
|---------|---------------------------|
| v8.7 | 43.3 °C (`Schedule:Compact`, constant 24h) |
| v8.9 | Referenced schedule (external or inherited template) |
| v22.1 | 60.0 °C (`Schedule:Compact`, constant 24h) |
| v23.1 | 48.9 °C (`Schedule:Constant` — `CWWaterTempSchedule`) |
| v24.2 | Referenced schedule (external or inherited template) |

### Format Differences

**v8.7 / v22.1 (full 10-field form):**
```
WaterUse:Equipment,
16_1_G SW Apartment Water Equipment,  !- Name
,                                      !- End-Use Subcategory
3.66e-006,                             !- Peak Flow Rate {m3/s}
16_APT_DHW_SCH,                        !- Flow Rate Fraction Schedule Name
16_Apartment Water Equipment Temp Sched,  !- Target Temperature Schedule Name
16_Apartment Water Equipment Hot Supply Temp Sched,  !- Hot Water Supply Temperature Schedule Name
,                                      !- Cold Water Supply Temperature Schedule Name
16_1_G SW Apartment,                   !- Zone Name
16_Apartment Water Equipment Sensible fract sched,  !- Sensible Fraction Schedule Name
16_Apartment Water Equipment Latent fract sched;    !- Latent Fraction Schedule Name
```

**v8.9 / v23.1 / v24.2 (compact 5-field form — terminates at field 5):**
```
  WaterUse:Equipment,
    17_24_Clothes Washer_unit1,        !- Name
    Domestic Hot Water,                !- End-Use Subcategory
    1.6219189818e-06,                  !- Peak Flow Rate {m3/s}
    17_ClothesWasher,                  !- Flow Rate Fraction Schedule Name
    17_CWWaterTempSchedule;
```

---

## 8. ZoneInfiltration:DesignFlowRate — Infiltration [m³/s·m² façade]

### Field Structure

| Field # | v8.7 | v8.9 | v22.1 | v23.1 | v24.2 |
|---------|------|------|-------|-------|-------|
| 1 | Name | Name | Name | *(not used — see note)* | Name |
| 2 | Zone or ZoneList Name | Zone or ZoneList Name | Zone or ZoneList Name | — | Zone or ZoneList Name |
| 3 | Schedule Name | Schedule Name | Schedule Name | — | Schedule Name |
| **4** | **Design Flow Rate Calculation Method** | **Design Flow Rate Calculation Method** | **Design Flow Rate Calculation Method** | — | **Design Flow Rate Calculation Method** |
| 5 | Design Flow Rate {m³/s} | Design Flow Rate {m³/s} | Design Flow Rate {m³/s} | — | Design Flow Rate {m³/s} |
| 6 | Flow per Zone Floor Area {m³/s·m²} | Flow per Zone Floor Area {m³/s·m²} | Flow per Zone Floor Area {m³/s·m²} | — | **Flow Rate per Floor Area {m³/s·m²}** |
| 7 | Flow per Exterior Surface Area {m³/s·m²} | Flow per Exterior Surface Area {m³/s·m²} | Flow per Exterior Surface Area {m³/s·m²} | — | **Flow Rate per Exterior Surface Area {m³/s·m²}** |
| 8 | Air Changes per Hour {1/hr} | Air Changes per Hour {1/hr} | Air Changes per Hour {1/hr} | — | Air Changes per Hour {1/hr} |
| 9–12 | Wind/Temp coefficients | Wind/Temp coefficients | Wind/Temp coefficients | — | Wind/Temp coefficients |

### Calculation Methods & Reading Logic

**Field 4 — `Design Flow Rate Calculation Method`:**

| Method | Active Field | How to Get [m³/s·m² façade] |
|--------|-------------|------------------------------|
| `AirChanges/Hour` | Field 8 | multiply ACH by zone volume / 3600 / exterior wall area |
| `Flow/ExteriorWallArea` | Field 7 | **use directly** as [m³/s·m²] |
| `Flow/ExteriorSurfaceArea` | Field 7 | **use directly** as [m³/s·m²] |
| `Flow/Zone` | Field 5 | divide by exterior wall area |
| `Flow/Area` | Field 6 | divide by zone area, then scale by façade fraction |

| Version | Typical Method Used |
|---------|--------------------|
| v8.7 | `AirChanges/Hour` (field 8) |
| v8.9 | `AirChanges/Hour` (field 8) |
| v22.1 | `Flow/ExteriorWallArea` (field 7) |
| v23.1 | **Not present** — uses `AirflowNetwork:MultiZone:Surface:EffectiveLeakageArea` |
| v24.2 | `AirChanges/Hour` (field 8) |

### v23.1 — AirflowNetwork Infiltration

v23.1 files use `AirflowNetwork:MultiZone:Surface:EffectiveLeakageArea` instead of `ZoneInfiltration:DesignFlowRate`:

```
AirflowNetwork:MultiZone:Surface:EffectiveLeakageArea,
    ZoneLeak_LongWall,             !- Name
    0.00283343730883696,           !- Effective Leakage Area {m2}
    1.15,                          !- Discharge Coefficient {dimensionless}
    4,                             !- Reference Pressure Difference {Pa}
    0.65;                          !- Air Mass Flow Exponent
```

To compare with the other versions, convert using: `Q [m³/s] = Cd × A_eff × sqrt(2 × ΔP / ρ_air)`.

### Field Name Change in v24.2
- v8.7/v8.9/v22.1: `"Flow per Zone Floor Area"`, `"Flow per Exterior Surface Area"`
- v24.2: `"Flow Rate per Floor Area"`, `"Flow Rate per Exterior Surface Area"` — **same positions (6 and 7)**

---

## 9. Ventilation Objects — Ventilation [m³/s·person], [m³/s·m²], [ACH]

Two object types are used across versions for ventilation:

### 9a. DesignSpecification:OutdoorAir

Used by all versions. Defines the design outdoor air rate referenced by HVAC systems.

| Field # | All Versions | Notes |
|---------|-------------|-------|
| 1 | Name | |
| **2** | **Outdoor Air Method** | determines active field |
| **3** | **Outdoor Air Flow per Person {m³/s·person}** | active when Method = `Flow/Person` or `Sum` |
| **4** | **Outdoor Air Flow per Zone Floor Area {m³/s·m²}** | active when Method = `Flow/Area` or `Sum` |
| **5** | **Outdoor Air Flow per Zone {m³/s}** | active when Method = `Flow/Zone` |
| 6 | Outdoor Air Flow Air Changes per Hour | active when Method = `AirChanges/Hour` |

**Outdoor Air Methods by version:**

| Version | Method | Active Field | Notes |
|---------|--------|-------------|-------|
| v8.7 | `Flow/Zone` | Field 5 | Absolute per-zone value in m³/s |
| v8.9 | `Flow/Zone` | Field 5 | Absolute per-zone value in m³/s |
| v22.1 | `Flow/Area` | Field 4 | Per floor area in m³/s·m² |
| v23.1 | `Flow/Zone` | Field 5 | Absolute per-zone value in m³/s |
| v24.2 | `Flow/Zone` | Field 5 | Absolute per-zone value in m³/s |

### 9b. ZoneVentilation:DesignFlowRate

Used for direct (non-HVAC-system) ventilation or exhaust in residential files.

| Field # | Description | Notes |
|---------|-------------|-------|
| 1 | Name | |
| 2 | Zone or ZoneList Name | |
| 3 | Schedule Name | |
| **4** | **Design Flow Rate Calculation Method** | |
| 5 | Design Flow Rate {m³/s} | active when Method = `Flow/Zone` |
| 6 | Flow Rate per Zone Floor Area / per Floor Area {m³/s·m²} | v8.7/v8.9/v23.1 = "Zone"; v24.2 drops "Zone" |
| 7 | Flow Rate per Person {m³/s·person} | |
| 8 | Air Changes per Hour {1/hr} | |
| 9 | Ventilation Type | `Natural`, `Exhaust`, `Intake`, `Balanced` |

**Presence by version:**

| Version | Present | Typical Method |
|---------|---------|---------------|
| v8.7 | No | Uses HVAC system OA only |
| v8.9 | Yes | `Flow/Zone` (absolute m³/s; `Exhaust` type) |
| v22.1 | No | Uses AirLoop with DesignSpec:OA |
| v23.1 | Yes | `Flow/Zone` (Design Flow Rate = 0 for exhaust placeholder) |
| v24.2 | Yes | `Flow/Zone` (absolute m³/s; `Exhaust` type) |

### Reading Logic — Unified Ventilation Extraction

To derive each ventilation metric per zone:

| Output Metric | Source Object | Field/Logic |
|---------------|--------------|-------------|
| **[m³/s·person]** | `DesignSpecification:OutdoorAir` | Field 3 directly; or Field 5 ÷ number of occupants; or Field 4 × area ÷ occupants |
| **[m³/s·m²]** | `DesignSpecification:OutdoorAir` | Field 4 directly; or Field 5 ÷ zone floor area |
| **[ACH]** | `DesignSpecification:OutdoorAir` | Field 6 directly; or (Field 5 × 3600) ÷ zone volume |

---

## 10. Thermostat Setpoints — Htg Setpoint [°C] & Clg Setpoint [°C]

### Object Chain

All versions use `ThermostatSetpoint:DualSetpoint` referenced via `ZoneControl:Thermostat`:

```
ZoneControl:Thermostat,
    Core_bottom Thermostat,
    Core_bottom,                              !- Zone Name
    Dual Zone Control Type Sched,             !- Control Type Schedule Name
    ThermostatSetpoint:DualSetpoint,          !- Control 1 Object Type
    Core_bottom Dual SP Control;              !- Control 1 Name

ThermostatSetpoint:DualSetpoint,
    Core_bottom Dual SP Control,              !- Name
    HTGSETP_SCH_YES_OPTIMUM,                  !- Heating Setpoint Temperature Schedule Name
    CLGSETP_SCH_YES_OPTIMUM;                  !- Cooling Setpoint Temperature Schedule Name
```

### ThermostatSetpoint:DualSetpoint Field Structure

| Field # | All Versions |
|---------|-------------|
| 1 | Name |
| **2** | **Heating Setpoint Temperature Schedule Name** |
| **3** | **Cooling Setpoint Temperature Schedule Name** |

> **Consistent across all versions** — format and field positions are identical.

### Reading Logic

1. Find `ThermostatSetpoint:DualSetpoint` for the zone via `ZoneControl:Thermostat`.
2. Read **Field 2** (heating schedule name) and **Field 3** (cooling schedule name).
3. Locate the corresponding `Schedule:Compact` or `Schedule:Constant` object.
4. Extract the **dominant/design temperature value** from the schedule.

### Typical Setpoint Values by Version

| Version | Heating Schedule Pattern | Htg Setpoint | Cooling Schedule Pattern | Clg Setpoint |
|---------|-------------------------|-------------|-------------------------|-------------|
| v8.7 | `16_APT_HTGSETP_SCH` constant | **20.0 °C** | `16_APT_CLGSETP_SCH` constant | **25.0 °C** |
| v8.9 | `17_heating_sch` constant | **21.1 °C** | `17_cooling_sch` constant | **23.9 °C** |
| v22.1 | `HTGSETP_SCH_YES_OPTIMUM` time-varying | **21.0 °C** (occupied) | `CLGSETP_SCH_YES_OPTIMUM` time-varying | **24.0 °C** (occupied) |
| v23.1 | `heating_sch` constant | **22.2 °C** | `cooling_sch` constant | **23.9 °C** |
| v24.2 | `17_heating_sch` constant | **21.1 °C** | `17_cooling_sch` constant | **23.9 °C** |

> For **time-varying schedules** (v22.1), the **occupied/design temperature** should be extracted — typically the value active during occupied hours. The occupied period value is the most relevant for reporting.

---

## 11. Summary Table — Object-by-Object Parsing Guide

| Metric | IDF Object | Key Field | Calculation Method Field | Method Values | v8.7 | v8.9 | v22.1 | v23.1 | v24.2 |
|--------|-----------|-----------|--------------------------|---------------|------|------|-------|-------|-------|
| **Zone Count** | `Zone,` | F1: Name | — | — | ✓ 13F | ✓ 7F | ✓ 13F | ✓ 7F | ✓ 7F |
| **Floor Area [m²]** | `Zone,` F10 or geometry | F10 or `BuildingSurface:Detailed` | `autocalculate` | — | F10 explicit or auto | auto only | F10 explicit or auto | auto only | auto only |
| **Occupancy [people/m²]** | `People,` | F5, F6, or F7 | F4: Method | `People` / `People/Area` / `Area/Person` | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Lighting [W/m²]** | `Lights,` | F5, or F6 | F4: Method | `LightingLevel` / `Watts/Area` / `Watts/Person` | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Electric Equipment [W/m²]** | `ElectricEquipment,` | F5, or F6 | F4: Method | `EquipmentLevel` / `Watts/Area` / `Watts/Person` | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Gas Equipment [W/m²]** | `GasEquipment,` | F5, or F6 | F4: Method | `EquipmentLevel` / `Watts/Area` / `Watts/Person` | ✗ | ✗ | ✗ | ✓ | ✗ |
| **SHW [L/h·m²]** | `WaterUse:Equipment,` | F3: Peak Flow Rate {m³/s} | — | Sum all objects per zone; convert m³/s→L/h÷area | ✓ 10F | ✓ 5F | ✓ 10F | ✓ 5F | ✓ 5F |
| **SHW Target Temp [°C]** | `WaterUse:Equipment,` F5 schedule | Schedule:Compact/Constant value | — | Look up schedule by name | 43.3°C | ~49°C | 60.0°C | 48.9°C | ~49°C |
| **Infiltration [m³/s·m² façade]** | `ZoneInfiltration:DesignFlowRate,` | F5/F6/F7/F8 | F4: Method | `AirChanges/Hour` / `Flow/ExteriorWallArea` / `Flow/Zone` | ACH | ACH | FlowExt | AFN | ACH |
| **Ventilation [m³/s·person]** | `DesignSpecification:OutdoorAir,` | F3 or derived | F2: OA Method | `Flow/Person` / `Flow/Zone` / `Flow/Area` | derived | derived | derived | derived | derived |
| **Ventilation [m³/s·m²]** | `DesignSpecification:OutdoorAir,` | F4 or derived | F2: OA Method | `Flow/Area` / `Flow/Zone` | derived | derived | F4 direct | derived | derived |
| **Ventilation [ACH]** | `DesignSpecification:OutdoorAir,` | F6 or derived | F2: OA Method | `AirChanges/Hour` / `Flow/Zone` | derived | derived | derived | derived | derived |
| **Htg Setpoint [°C]** | `ThermostatSetpoint:DualSetpoint,` F2 schedule | Schedule value | — | Look up schedule by name | 20.0°C | 21.1°C | 21.0°C | 22.2°C | 21.1°C |
| **Clg Setpoint [°C]** | `ThermostatSetpoint:DualSetpoint,` F3 schedule | Schedule value | — | Look up schedule by name | 25.0°C | 23.9°C | 24.0°C | 23.9°C | 23.9°C |

> **Legend:** ✓ = object present in this version, ✗ = absent; F = field number; AFN = AirflowNetwork method; derived = calculated from other field values.

---

## 12. Common Format Differences — Quick Reference

| Aspect | v8.7 | v8.9 | v22.1 | v23.1 | v24.2 |
|--------|------|------|-------|-------|-------|
| **Indentation** | None | 2–4 spaces | 4 spaces | None / tabs | 2–4 spaces |
| **Field comments** | `!- Field name` on every line | `!- Field name` on most lines | `!- Field name` on most lines | Minimal — first field only | `!- Field name` on most lines |
| **Inline compact fields** | No | No | No | Yes (`,,` for two empties) | No |
| **Zone field count** | 13 | 7 | 13 | 7 | 7 |
| **"Zone" prefix in field names** | `"per Zone Floor Area"` | `"per Zone Floor Area"` | `"per Floor Area"` (no "Zone") | `"per Zone Floor Area"` | `"per Floor Area"` (no "Zone") |
| **WaterUse:Equipment fields** | 10 (full) | 5 (short) | 10 (full) | 5 (short) | 5 (short) |
| **Infiltration approach** | `ZoneInfiltration:DesignFlowRate` | `ZoneInfiltration:DesignFlowRate` | `ZoneInfiltration:DesignFlowRate` | `AirflowNetwork:MultiZone:Surface:EffectiveLeakageArea` | `ZoneInfiltration:DesignFlowRate` |
| **Ventilation approach** | `DesignSpec:OA` (HVAC system) | `DesignSpec:OA` + `ZoneVentilation` | `DesignSpec:OA` (AirLoop) | `DesignSpec:OA` + `ZoneVentilation` | `DesignSpec:OA` + `ZoneVentilation` |
| **Space/SpaceList support** | No | No | Yes (field 2 expanded) | No | Yes (field 2 expanded) |

---

*Generated: 2026-03-04 | Repository: idf_reader | Source folder: `/Content/` (41 IDF files)*
