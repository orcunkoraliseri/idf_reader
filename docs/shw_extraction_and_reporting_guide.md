# Service Hot Water (SHW) Extraction and Reporting Guide

This document serves as the authoritative guide on how Service Hot Water (SHW) is modeled in EnergyPlus IDF files, how it is accurately extracted by our parser, and how we handle edge cases between different building prototypes.

---

## 1. The Core Metric: Peak vs. Average Flow Density

When characterizing building SHW intensity, the most accurate parameter is **Average flow density (L/h.m²)** rather than the peak instantaneous flow.

### What EnergyPlus `Peak Flow Rate` Actually Represents
At every simulation timestep, the actual flow rate is simply:
`Actual Flow Rate = Peak Flow Rate × Schedule Fraction (0–1)`

The **peak** is a design instantaneous maximum—representing the upper bound of demand if a fixture is fully open. The **schedule fraction** modulates it to produce a realistic time-varying profile.

### The Problem with Raw Peaks
- **Residential (e.g., Two Storey House):** Individual fixture peaks are extreme (bathtub = ~1,000 L/h, shower = ~511 L/h) but schedule fractions are tiny (0.001–0.014) because fixtures rarely run fully open simultaneously. Summing raw peaks gives an unrealistic `~1,777 L/h` (8.5 L/h.m²), whereas taking the schedule-adjusted average gives a realistic `~11.4 L/h` (0.05 L/h.m²).
- **Non-Residential (e.g., Hospital, Office):** Peaks are lower and schedules are more moderate, but the same mathematical rule applies.

### Standard Practice
ASHRAE Handbook (HVAC Applications, Ch. 51), DOE Prototype Buildings, ENERGY STAR, and CBECS all utilize average daily or hourly consumption for building characterization rather than raw sizing peaks. Therefore, our extractor algorithm strictly calculates:
**Area-Normalized SHW [L/h.m²] = `(Peak_m3/s × Average_Fraction × 3,600,000) / Zone_Area`**

---

## 2. IDF Extraction Logic & Supported Objects

EnergyPlus prototype files assign SHW loads using two distinct objects. Our parser (`extractors.py`) handles both concurrently.

### A. `WaterUse:Equipment` (Primary Method)
Used heavily in HighRise Apartments and most standard templates.
*   **Peak Value:** Extracted from Field 3.
*   **Schedule Fraction:** Extracted from Field 4. The `compute_schedule_annual_average()` function collapses Constant, Compact, and Year/Week/Day hierarchies to find the time-weighted annual mean.
*   **Target Temperature:** Extracted from Field 5.
*   **Mapping:** Directly references the Zone Name. If the zone name is omitted, it falls back to a longest-common prefix/suffix heuristic against the building's zones.

### B. `WaterHeater:Mixed` (Supplemental Method)
Used frequently in older or alternative boiler setups, such as the MidRise Apartment, where the `WaterUse:Equipment` objects are sometimes missing or duplicate standard assignments.
*   **Peak Value:** Extracted from Field 28 (`Peak Use Flow Rate`).
*   **Schedule Fraction:** Extracted from Field 29 (`Use Flow Rate Fraction Schedule Name`).
*   **Target Temperature:** Extracted from Field 3.
*   **Mapping:** Maps to the zone listed in `Ambient Temperature Zone Name` (Field 22) if the `Ambient Temperature Indicator` (Field 20) is set to `Zone`.

---

## 3. Resolving Extraction Edge Cases

### The "Double-Counting" Bug
In certain generation models (such as the MidRise Apartment), both `WaterUse:Equipment` **and** `WaterHeater:Mixed` are populated in the IDF for the exact same zone, defining the exact same peak flow rate. 
*   **Fix:** The `extract_water_use` algorithm tracks which zones have successfully processed a `WaterUse:Equipment` object. If `WaterHeater:Mixed` encounters a zone already in this tracker, it skips extraction to prevent double-counting.

### Missing Schedule Multipliers
Historically, the script assumed `WaterHeater:Mixed` ran at a 100% fraction.
*   **Fix:** The script now successfully retrieves Field 29 (`Use Flow Rate Fraction Schedule Name`) for Mixed heaters, accurately multiplying the peak by the schedule (e.g., `APT_DHW_SCH` at 0.5225), bringing over-inflated values down to reality.

### Target Temperature Variations (Fixture vs. Tank)
You may observe differing Target Temperatures between identical zone types (e.g., HighRise calculating `43.3 °C` and MidRise calculating `60.0 °C`). Both are **correct**, representing how the IDF specifically programmed its object:
*   HighRise's `WaterUse:Equipment` utilizes the `SHW TARGET TEMP SCHED`, which is explicitly set to `43.3 °C` (`110 °F`), representing **fixture-level use limits**.
*   MidRise's `WaterHeater:Mixed` utilizes the `Hot Water Setpoint Temp Schedule`, which is explicitly set to `60.0 °C` (`140 °F`), representing **tank-level storage rules**.

### Unorthodox Floor Sizing Techniques
Some Department of Energy prototypes employ unconventional modeling to bypass Zone Multipliers. For example, in the MidRise apartment block, the ground floor (`G N1`) unit will correctly extract `0.069 L/h.m²`. However, the middle floor (`M N1`) above it will extract exactly double (`0.139 L/h.m²`). 
*   **Reason:** The internal `WaterHeater:Mixed` peak flow capacity was literally hard-coded to double the capacity (`6.529e-06 m³/s` vs `3.264e-06 m³/s`) on the middle floor to simulate multiple units stacked together without increasing the physical simulated zone size. The code correctly extracts what is drawn in the IDF.
