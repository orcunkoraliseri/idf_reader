# SHW Flow Rate Metric: Peak vs. Average — Research Report

## Question

Should Service Hot Water (SHW) load intensity be reported as:
1. **Peak flow density** (L/h.m²) — the instantaneous design maximum
2. **Average flow density** (L/h.m²) — `peak × annual average schedule fraction`

## Conclusion

**Average flow density (`peak × avg_schedule_fraction`) is the correct metric for building characterization in both residential and non-residential buildings.**

---

## 1. What EnergyPlus `Peak Flow Rate` Actually Represents

From the EnergyPlus Input-Output Reference (Group Water Systems):

> "The peak demanded hot water flow rate [m3/s]. This value is multiplied by the Flow Rate Fraction Schedule to determine the actual volumetric flow rate."

At every simulation timestep:
```
Actual Flow Rate = Peak Flow Rate × Schedule Fraction (0–1)
```

The peak is a design instantaneous maximum — the upper bound of demand. The schedule fraction modulates it to produce a realistic time-varying profile. This is structurally identical to how `Lights` objects work (installed watts × schedule fraction).

---

## 2. Why the Two Building Types Behave Differently

### Residential (e.g., Two Storey House)
- Multiple `WaterUse:Equipment` objects per zone (bathtub, shower, sinks, washer, dishwasher)
- Individual fixture peaks are extreme (bathtub = ~1,000 L/h, shower = ~511 L/h) — physical maximums if tap is fully open
- Schedule fractions are tiny (0.001–0.014) — fixtures almost never run at full flow
- Summing raw peaks gives an unrealistic ~1,777 L/h (→ 8.5 L/h.m²)
- `peak × avg_fraction` gives a realistic ~11.4 L/h (→ 0.05 L/h.m²)

### Non-Residential (e.g., Hospital, Office)
- One `WaterUse:Equipment` object per zone
- Peak is a moderate design value (3.8 L/h per hospital exam room, 37.4 L/h per office core)
- Schedule fractions are moderate (0.13–0.44)
- `peak × avg_fraction` gives the actual average consumption rate

In both cases, `peak × avg_fraction` is the meaningful characterization metric.

---

## 3. ASHRAE Handbook Guidance

**ASHRAE Handbook — HVAC Applications, Chapter 51 (Service Water Heating)** provides hot-water demand for various building types with three distinct columns:

| Column | Meaning |
|---|---|
| Maximum Hourly | Design capacity for equipment sizing (98th-percentile demand) |
| Maximum Daily | Daily peak for storage sizing |
| **Average Daily** | **Reference value for building characterization** |

Selected values (from Table 6):

| Building Type | Max Hourly | Avg Daily |
|---|---|---|
| Office | 0.4 gal/person | 1.0 gal/person/day |
| Elementary school | 0.6 gal/student | 0.6 gal/student/day |
| Full-service restaurant | 1.5 gal/peak meal/h | 2.4 gal/avg meal/day |
| Quick-service restaurant | 0.7 gal/peak meal/h | 0.7 gal/avg meal/day |

**Key finding:** ASHRAE uses *Average Daily* for building characterization, not the maximum hourly peak. ASHRAE normalizes by occupant/seat/bed, not by floor area — conversion to L/h.m² requires an occupant density assumption.

---

## 4. DOE Prototype Building Calibration

From PNNL-23269 (*Enhancements to ASHRAE Standard 90.1 Prototype Building Models*):

DOE prototype IDF files set `WaterUse:Equipment` peak flow rates so that:
```
peak × Σ(schedule_fraction over day) = ASHRAE average daily consumption target
```

This means the peak flow rate in the IDF is intentionally set *higher* than the average, and the schedule is designed to bring the product down to the realistic average. Reporting the raw peak would produce values 2–8× higher than the ASHRAE reference, making inter-building comparison misleading.

Approximate area-normalized SHW intensities for DOE prototype buildings (derived from occupancy assumptions):

| Building Type | Approx. SHW Intensity |
|---|---|
| Office | ~0.04 L/h.m² (~0.87 L/day.m²) |
| Hospital | ~0.20 L/h.m² (~4.7 L/day.m²) |
| Hotel (large) | ~0.16 L/h.m² (~3.8 L/day.m²) |
| Full-service restaurant | ~2.4 L/h.m² (~57 L/day.m²) |
| Retail | ~0.008 L/h.m² (~0.2 L/day.m²) |

---

## 5. Benchmarking Standards

**ENERGY STAR Portfolio Manager** and **CBECS** express SHW benchmarks as volumetric consumption per unit area per year (L/m²/year or gal/ft²/year) — average consumption, not peak flow density.

---

## 6. The Lighting Analogy — and Why It Breaks Down for SHW

| | Lighting | SHW |
|---|---|---|
| EnergyPlus input | Design Level (W) | Peak Flow Rate (m³/s) |
| Schedule role | Fraction of installed power in use | Fraction of peak flow in use |
| ASHRAE design reference | LPD tables (W/m²) — *installed capacity* | Avg Daily tables — *average consumption* |
| Correct reporting metric | Installed power density (W/m²) | **Average flow density (L/h.m²)** |

Lighting W/m² is correctly reported as installed capacity because ASHRAE 90.1 Section 9 LPD limits are expressed the same way. For SHW, the ASHRAE reference values are average consumption — so the extractor metric must match.

---

## 7. Implementation in This Codebase

**Function:** `compute_schedule_annual_average(idf_data, schedule_name)` in `extractors.py`

Handles the full EnergyPlus schedule hierarchy:
- `Schedule:Constant`
- `Schedule:Compact` (time-weighted average of `Until:` blocks)
- `Schedule:Year` → `Schedule:Week:Compact` / `Schedule:Week:Daily` → `Schedule:Day:Hourly`

**Usage in `extract_water_use`:**
```python
avg_fraction = compute_schedule_annual_average(idf_data, flow_sched)
results[zone_name]["avg_lh_m2"] += (peak_m3s * avg_fraction * 3600000) / area
```

**Tip:** To convert to L/day.m² for cross-checking against ASHRAE Handbook values, multiply `avg_lh_m2 × 24`.

---

## Sources

- EnergyPlus 22.1 Input-Output Reference — Group Water Systems (Big Ladder Software)
- ASHRAE Handbook — HVAC Applications (2019), Chapter 51: Service Water Heating, Table 6
- PNNL-23269: Enhancements to ASHRAE Standard 90.1 Prototype Building Models
- DOE Commercial Reference Buildings Program
- ENERGY STAR Water Use Intensity (WUI) documentation
