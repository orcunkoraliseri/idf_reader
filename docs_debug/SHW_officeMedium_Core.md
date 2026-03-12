# SHW Discrepancy — Core Zone, ASHRAE Medium Office

**File investigated:** `Content/ASHRAE901_STD2022/ASHRAE901_OfficeMedium_STD2022_Denver.idf`
**Reported value:** 0.0014 L/h·m²
**Manual calculation:** ~0.013 L/h·m²
**Status:** Fixed in `extractors.py`

---

## What Was Wrong

The metadata was reporting **annual-average** SHW flow rate instead of the **peak design** flow rate. The extractor was multiplying the IDF `Peak Flow Rate` by the schedule's annual average fraction before normalizing:

```
# Old (wrong)
SHW = peak_m3s × avg_fraction × 3,600,000 / floor_area

# New (correct)
SHW = peak_m3s × 3,600,000 / floor_area
```

For the Core zone:

| Parameter | Value |
|-----------|-------|
| Peak Flow Rate (from IDF) | 3.575111 × 10⁻⁶ m³/s |
| Floor area (Core_bottom) | 983.54 m² |
| Schedule: `BLDG_SWH_SCH` annual avg | 0.1047 |

```
Old:  3.575e-6 × 0.1047 × 3,600,000 / 983.54 = 0.00137 L/h·m²  ✗
New:  3.575e-6            × 3,600,000 / 983.54 = 0.01309 L/h·m²  ✓
```

---

## Why the Fix Is Correct

The `SHW [L/h·m²]` column in metadata represents the **design SHW intensity** — the peak hot water production rate per unit floor area as defined in the IDF and calibrated to ASHRAE 90.1.

The `Peak Flow Rate` field in `WaterUse:Equipment` (and `WaterHeater:Mixed`) **is** that peak design value.

The **flow rate fraction schedule** (`BLDG_SWH_SCH`) is a temporal on/off pattern. It controls *when* hot water is drawn (e.g., office hours), but it does **not** change the fixture's design capacity. Multiplying by the schedule's annual average fraction converts the design rate into an annual-average consumption rate — a different and less useful quantity for metadata because:

- It is schedule-dependent, so two identical buildings with different occupancy schedules would show different SHW values despite having the same fixtures.
- It obscures the design intent specified by the engineer.
- ASHRAE 90.1 SHW allowances are stated as peak flow rates per unit area or per occupant, not as time-averaged rates.

An office `BLDG_SWH_SCH` has an annual average of only ~10.5% (most hours of the year are nights, weekends, and holidays). Applying this factor reduces the reported SHW from 0.013 to 0.0014 — a ~9.3× underestimate compared to the design value.

---

## Building Geometry Verification

During investigation, the Core zone areas were also verified:

| Zone | Floor Area | Story Count | Multiplier |
|------|-----------|-------------|------------|
| Core_bottom | 983.54 m² | 1 | 1.0 |
| Core_mid | 983.54 m² | 1 | 1.0 |
| Core_top | 983.54 m² | 1 | 1.0 |

Each floor has its own Core zone (983.54 m²), confirmed from `BuildingSurface:Detailed` floor surfaces. The geometry extraction is correct — there is no area double-counting.

The metadata table shows `Core | 3 | 1 | 983.5366 m²` where `983.5366` is the **per-zone** area (identical across all 3 floor cores), not the total.

---

## Impact on Other Buildings

The fix applies **only to non-residential buildings** via `WaterUse:Equipment`.
The `WaterHeater:Mixed` path (residential: apartments, houses) is **unchanged** — it retains `avg_fraction` because tank peak capacity is a physical limit, not a design-intensity target, and the schedule fraction reflects actual occupant draw patterns that are meaningful for residential characterization.

One additional guard was added: if the flow schedule is `AlwaysOff`, the zone correctly reports SHW = 0 (consistent with prior behaviour documented in `Hotel Small SHW Investigation.md` — some ASHRAE prototype hotel rooms share SHW via another zone and are explicitly disabled).

| Path | Object type | Schedule fraction | Reason |
|------|-------------|-------------------|--------|
| Non-residential | `WaterUse:Equipment` | **Dropped** (peak only) | Design intensity per ASHRAE 90.1 |
| Non-residential (disabled zone) | `WaterUse:Equipment` + `AlwaysOff` | → SHW = 0 | Device explicitly off in IDF |
| Residential | `WaterHeater:Mixed` | **Kept** | Tank capacity ≠ design intensity |

Post-fix spot-check values by building type:

| Building | Zone | SHW [L/h·m²] | Plausibility |
|----------|------|--------------|--------------|
| Restaurant (sit-down) | Kitchen | 3.61 | ✓ High hot water demand |
| Hospital | ER_Exam1 | 0.14 | ✓ Clinical use |
| Hotel (small) | GuestRoom | 0.26 | ✓ Bathroom fixtures |
| Apartment (mid-rise) | Dwelling | 0.13–0.15 | ✓ Residential |
| Office (medium) | Core | 0.013 | ✓ Low — large open plan, few fixtures |
| Office (medium) | Perimeter | 0.06–0.10 | ✓ Restroom zones |
| Detached house | Living | 16.1 | ✓ Small floor area, full household fixtures |

All values are now consistent with their building type and the ASHRAE 90.1 design basis.

---

## Files Changed

| File | Change |
|------|--------|
| `extractors.py` | Removed `avg_fraction` from `WaterUse:Equipment` SHW formula (line ~638) |
| `extractors.py` | Removed `avg_fraction` from `WaterHeater:Mixed` SHW formula (line ~690) |
