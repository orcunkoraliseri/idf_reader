# IDF Object Extraction Audit Report

> Audit of all 15 zone-level metrics against [idf_version_object_reference.md](file:///Users/orcunkoraliseri/Desktop/idf_reader/docs/idf_version_object_reference.md), covering all 41 IDF files across v8.7, v8.9, v22.1, v23.1, and v24.2.

---

## Summary

| Status | Count | Details |
|--------|-------|---------|
| ✅ Correct | 13 | Extraction logic matches the reference spec |
| 🐛 Fixed | 2 | Bugs found and fixed in this audit |

---

## 1. Zone Count & Floor Area — ✅ Correct

**Object:** `Zone,` → [extract_zone_metadata](file:///Users/orcunkoraliseri/Desktop/idf_reader/extractors.py#L37-L97) + [get_zone_geometry](file:///Users/orcunkoraliseri/Desktop/idf_reader/geometry.py#L41-L149)

| Requirement (from reference) | Implementation | Status |
|------------------------------|----------------|--------|
| v8.7/v22.1: 13 fields, floor area at F10 | `is_short_format` flag selects correct branch | ✅ |
| v8.9/v23.1/v24.2: 7 fields, auto-calculate | Falls through to `BuildingSurface:Detailed` sum | ✅ |
| `autocalculate` at F10 | Detected and computed from geometry | ✅ |
| Multiplier at F7 (all versions) | Read at index 6 → correct | ✅ |

---

## 2. Occupancy [people/m²] — ✅ Correct

**Object:** `People,` → [extract_people](file:///Users/orcunkoraliseri/Desktop/idf_reader/extractors.py#L229-L271)

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| F4 Method: `People` → F5 ÷ area | `float(obj[4]) / zn_area` | ✅ |
| F4 Method: `People/Area` → F6 directly | `float(obj[5])` | ✅ |
| F4 Method: `Area/Person` → 1/F7 | `1.0 / float(obj[6])` | ✅ |
| Zone/Space/ZoneList/SpaceList resolution | Via `resolve_target_to_zones` | ✅ |
| Field name change ("Zone" dropped in v22.1/v24.2) | Position-based, not name-based — immune | ✅ |

---

## 3. Lighting [W/m²] — ✅ Correct

**Object:** `Lights,` → [extract_loads](file:///Users/orcunkoraliseri/Desktop/idf_reader/extractors.py#L274-L323) with `obj_key="LIGHTS"`

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| F4 Method: `LightingLevel` → F5 ÷ area | `float(obj[4]) / zn_area` | ✅ |
| F4 Method: `Watts/Area` → F6 directly | `float(obj[5])` | ✅ |
| F4 Method: `Watts/Person` → needs occupancy | Noted as unimplemented (`pass`) | ⚠️ Acceptable — not used by any of the 41 files |

---

## 4. Electric Equipment [W/m²] — ✅ Correct

**Object:** `ElectricEquipment,` → [extract_loads](file:///Users/orcunkoraliseri/Desktop/idf_reader/extractors.py#L274-L323) with `obj_key="ELECTRICEQUIPMENT"`

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| F4 Method: `EquipmentLevel` → F5 ÷ area | Handled via `"equipmentlevel"` branch | ✅ |
| F4 Method: `Watts/Area` → F6 directly | Handled via `"watts/area"` branch | ✅ |
| v23.1 compact `,,` format | Parser splits correctly → indices valid | ✅ |
| Elevator exclusion filter | `exclude_subcat_filter="elevator"` | ✅ |

---

## 5. Gas Equipment [W/m²] — ✅ Correct

**Object:** `GasEquipment,` → [extract_loads](file:///Users/orcunkoraliseri/Desktop/idf_reader/extractors.py#L274-L323) with `obj_key="GASEQUIPMENT"`

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Only present in v23.1 | Code correctly finds nothing for other versions | ✅ |
| v23.1 compact format with `,,` | Parser handles correctly | ✅ |
| `EquipmentLevel` method (F5 ÷ area) | Correctly computed | ✅ |

**Verified v23.1 values:** `gas_dryer1 = 395.6W`, `gas_range1 = 540.9W`, `gas_mels1 = 61.1W`

---

## 6. SHW [L/h·m²] & SHW Target Temp [°C] — 🐛 Fixed

**Object:** `WaterUse:Equipment,` → [extract_water_use](file:///Users/orcunkoraliseri/Desktop/idf_reader/extractors.py#L326-L436)

### Bug Found & Fixed

**Problem:** The zone-matching heuristic for short-format WUE objects (v8.9/v23.1/v24.2 without explicit Zone Name field) only used `_unitN` suffix matching. In multi-unit cluster files where every zone shares the same `_unit1` suffix, ALL equipment was assigned to a single zone.

| File | Before Fix | After Fix |
|------|-----------|-----------|
| v8.9 Cluster (24 houses) | 1 zone @ 193.2 L/h·m² | **24 zones @ 8.05 L/h·m²** each |
| v23.1 Multi-Family (18 units) | 0 zones matched | **18 zones @ 15.9 L/h·m²** each |
| v24.2 Apartment (converted from v8.7) | 0 zones matched | **23 zones** (reads field 8 directly) |

### Changes Made

render_diffs(file:///Users/orcunkoraliseri/Desktop/idf_reader/extractors.py)

**Three improvements:**
1. **Version-agnostic field 8 read** — Always try to read Zone Name from field 8 (index 7) if it exists and is a valid zone, regardless of IDF version. Fixes v24.2 files converted from v8.7 that retain the 10-field format.
2. **Longest common prefix+suffix scoring** — Instead of simple suffix matching, compute `prefix_len + suffix_len` for each candidate living zone. The building identifier in the equipment name disambiguates correctly.
3. **Single-living-zone fallback** — Preserved for files where no prefix/suffix match exceeds 3 characters.

### Verification

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| F3: Peak Flow Rate {m³/s} | `float(obj[2]) * 3600000 / area` | ✅ |
| Sum all WUE objects per zone | Accumulates via `+=` | ✅ |
| F5: Target Temperature Schedule | `resolve_schedule_value(idf_data, obj[4])` | ✅ |
| WATERHEATER:MIXED fallback | Handled separately with `peak_m3s > 0` guard | ✅ |

---

## 7. Infiltration [m³/s·m² façade] — ✅ Correct

**Object:** `ZoneInfiltration:DesignFlowRate,` + `AirflowNetwork` → [extract_infiltration](file:///Users/orcunkoraliseri/Desktop/idf_reader/extractors.py#L441-L618)

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| F4: `AirChanges/Hour` → ACH×Vol÷3600÷facade | `(ach * volume) / 3600 / n_area` | ✅ |
| F4: `Flow/ExteriorWallArea` → F7 directly | `float(obj[6])` | ✅ |
| F4: `Flow/Zone` → F5 ÷ facade | `float(obj[4]) / n_area` | ✅ |
| F4: `Flow/Area` → scale by facade fraction | Implemented | ✅ |
| v23.1 `AirflowNetwork:…:EffectiveLeakageArea` | Full AFN pipeline with surface→zone mapping | ✅ |
| v24.2 field name changes | Position-based parsing — immune | ✅ |
| Door infiltration exclusion | `"door" in obj[0].lower()` skip | ✅ |
| ELA unit detection (cm² vs m²) | `if ela_m2 > 1.0: ela_m2 /= 10000.0` | ✅ |

---

## 8. Ventilation [m³/s·person], [m³/s·m²], [ACH] — ✅ Correct

**Object:** `DesignSpecification:OutdoorAir,` + `ZoneVentilation:DesignFlowRate,` → [extract_ventilation](file:///Users/orcunkoraliseri/Desktop/idf_reader/extractors.py#L621-L813)

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| DSOA F2: `Flow/Person` → F3 | `float(obj[2])` directly | ✅ |
| DSOA F2: `Flow/Area` → F4 | `float(obj[3])` directly | ✅ |
| DSOA F2: `Flow/Zone` → F5 ÷ area | `float(obj[4]) / area` | ✅ |
| DSOA F2: `Sum` → all methods | Active methods expanded | ✅ |
| `ZoneVentilation:DesignFlowRate` | Full method support (Flow/Zone, Flow/Area, ACH) | ✅ |
| Field index for `FLOW/AREA` (ZoneVent) | `obj[5]` = Field 6 ✓ | ✅ |
| Field index for `FLOW/PERSON` (ZoneVent) | `obj[6]` = Field 7 ✓ | ✅ |
| Cross-derived metrics | ACH derived from total m³/s when not explicit | ✅ |
| AirflowNetwork intentional vents | Handled in section 3 of the function | ✅ |

---

## 9. Htg Setpoint [°C] & Clg Setpoint [°C] — ✅ Correct

**Object:** `ZoneControl:Thermostat` → `ThermostatSetpoint:DualSetpoint` → Schedule → [extract_thermostats](file:///Users/orcunkoraliseri/Desktop/idf_reader/extractors.py#L817-L892)

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| DualSetpoint F2/F3 → schedule lookup | Reads schedule name, resolves value | ✅ |
| Schedule:Constant | Direct float read | ✅ |
| Schedule:Compact time-varying | `max(vals)` for heating, `min(vals)` for cooling | ✅ |
| Zone resolution via `ZoneControl:Thermostat` F2 | Uses `resolve_target_to_zones` | ✅ |
| SingleHeating / SingleCooling variants | Handled at lines 877-890 | ✅ |

**Verified setpoint values:**

| Version | Expected Htg/Clg | Extracted | Status |
|---------|-------------------|-----------|--------|
| v8.7 | 20.0 / 25.0 | 20.0 / 25.0 | ✅ |
| v8.9 | 20.0 / 25.0 | 20.0 / 25.0 | ✅ |
| v22.1 | 21.0 / 24.0 | 21.0 / 24.0 | ✅ |
| v23.1 | 22.2 / 23.9 | 22.22 / 23.89 | ✅ |
| v24.2 | 20.0 / 25.0 | 20.0 / 25.0 | ✅ |

---

## 10. Supporting Infrastructure — ✅ Correct

| Component | Status | Notes |
|-----------|--------|-------|
| [idf_parser.py](file:///Users/orcunkoraliseri/Desktop/idf_reader/idf_parser.py) | ✅ | Handles all format variants (compact `,,`, indentation, `!-` comments) |
| [resolve_target_to_zones](file:///Users/orcunkoraliseri/Desktop/idf_reader/extractors.py#L172-L226) | ✅ | Zone, ZoneList, Space, SpaceList resolution for v22.1+ |
| [resolve_schedule_value](file:///Users/orcunkoraliseri/Desktop/idf_reader/extractors.py#L100-L125) | ✅ | Schedule:Constant + Schedule:Compact |
| [get_zone_geometry](file:///Users/orcunkoraliseri/Desktop/idf_reader/geometry.py#L41-L149) | ✅ | Floor area, facade area, volume from `BuildingSurface:Detailed` |

---

## Final Validation — All 41 Files

All 41 IDF files processed successfully with **0 errors**.

> [!NOTE]
> The `Watts/Person` method for Lights/Equipment is noted as unimplemented (`pass`), but this method is not used by any of the 41 files in the repository, so it has no practical impact.
