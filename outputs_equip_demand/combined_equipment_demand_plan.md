# Combined Equipment Demand Investigation Plan
## IDF: `US+SF+CZ6A+gasfurnace+unheatedbsmt+IECC_2024.idf`
## Zone: `living_unit1` | Floor Area: **110.4089 m²**

---

## Background & Problem Statement

Honeybee/Ladybug uses a **single** `EquipmentPerFloorArea` (W/m²) value combined with **one** schedule for all plug/process loads. The EnergyPlus IDF, however, models each appliance with its own `Schedule:Year` → `Schedule:Week:Compact` → `Schedule:Day:Hourly` hierarchy, and splits energy between `ElectricEquipment` and `GasEquipment` objects. Direct import is impossible because:

- **Multiple distinct schedules exist** — each appliance has a unique hourly profile.
- **Gas and electric are in separate IDF classes** — Honeybee has no native field for `GasEquipment` without additional strings.
- **The IDF uses `EquipmentLevel` (absolute Watts)**, whereas Honeybee wants W/m².

**→ Solution adopted:** Two separate composite outputs are produced — one for electric, one for gas — each with a single W/m² and a single weighted schedule. Both are inserted as additional EnergyPlus strings in Honeybee.

---

## Step 1 — Equipment Inventory

All objects from lines 3274–3408 of the IDF:

| Object Type | IDF Name | Schedule | Peak (W) | Notes |
|---|---|---|---|---|
| `ElectricEquipment` | `dishwasher1` | `DishWasher_equip_sch` | 65.70 | |
| `ElectricEquipment` | `refrigerator1` | `Refrigerator` | 91.06 | Nearly constant cycling |
| `ElectricEquipment` | `clotheswasher1` | `ClothesWasher_equip_sch` | 28.48 | |
| `ElectricEquipment` | `gas_dryer1` | `ClothesDryer` | 19.42 | Electric motor/controls of gas dryer |
| `ElectricEquipment` | `gas_range1` | `CookingRange` | 0.00 | Electric ignition only → filtered out |
| `ElectricEquipment` | `television1` | `InteriorLighting` | 0.00 | Zero W → filtered out |
| `ElectricEquipment` | `gas_mels1` | `MiscPlugLoad` | 507.15 | Misc electric loads |
| `ElectricEquipment` | `IECC_Adj1` | `MiscPlugLoad` | 505.40 | IECC code-adjustment credit |
| `GasEquipment` | `gas_dryer1` | `ClothesDryer` | 395.60 | Gas heat of dryer |
| `GasEquipment` | `gas_range1` | `CookingRange` | 540.94 | Gas burner |
| `GasEquipment` | `gas_mels1` | `MiscPlugLoad` | 61.13 | Misc gas loads |

> Objects with `DesignLevel = 0 W` are excluded from the composite (no energy contribution).

---

## Step 2 — Schedule Resolution Chain

Each appliance references a `Schedule:Year`, which chains through:

```
Schedule:Year
  └─ Schedule:Week:Compact  (Weekdays / CustomDay1 / AllOtherDays)
       └─ Schedule:Day:Hourly  (24 explicit fractional values)
```

| Schedule Name | Appliances |
|---|---|
| `DishWasher_equip_sch` (`DishwasherWeek_equip_sch`) | dishwasher (electric) |
| `ClothesWasher_equip_sch` (`ClothesWasherWeek_equip_sch`) | clothes washer (electric) |
| `ClothesDryer` (`ClothesDryerWeek`) | gas_dryer × 2 (gas main + electric motor) |
| `CookingRange` (`CookingRangeWeek`) | gas_range (gas burner only; electric = 0 W) |
| `MiscPlugLoad` (`MiscPlugLoadWeek`) | gas_mels × 2 + IECC_Adj1 |
| `Refrigerator` (`RefrigeratorWeek`) | refrigerator (AllDays) |

A Python script (`equipment_demand_composer.py`) was written to parse and resolve all chains into 8760-hour arrays.

---

## Step 3 — Composite Schedule Method

For each energy-type group (electric, gas), hourly aggregate power is:

```
P(h) = Σ_i [ DesignLevel_i  ×  schedule_i(h) ]
```

The composite fractional schedule:

```
f(h) = P(h) / max(P)
```

The composite peak design level:

```
DL_peak = max_h( P(h) )          [W]
DL_per_m² = DL_peak / floor_area [W/m²]
```

Heat fractions (latent, radiant, lost) are energy-weighted across all appliances.

---

## Step 4 — Final Results ✅

### Electric Equipment Composite

| Parameter | Value |
|---|---|
| **Peak Design Level** | **1180.57 W** |
| **Peak Design Level (W/m²)** | **10.6927 W/m²** |
| **Annual Energy** | **7047.6 kWh/yr** |
| **Annual Energy Density** | 63.83 kWh/m²/yr |
| Weighted Fraction Latent | 0.0564 |
| Weighted Fraction Radiant | 0.6038 |
| Weighted Fraction Lost | 0.2233 |
| Honeybee Schedule Name | `composite_elec_equip_sch` |

**Per-appliance breakdown (electric):**

| Appliance | Schedule | DL (W) | EFLH | kWh/yr |
|---|---|---|---|---|
| dishwasher1 | DishWasher_equip_sch | 65.70 | 3134.0 | 205.9 |
| refrigerator1 | Refrigerator | 91.06 | 7343.4 | 668.7 |
| clotheswasher1 | ClothesWasher_equip_sch | 28.48 | 3692.4 | 105.2 |
| gas_dryer1 (motor) | ClothesDryer | 19.42 | 3910.9 | 75.9 |
| gas_mels1 (elec) | MiscPlugLoad | 507.15 | 5917.6 | 3001.1 |
| IECC_Adj1 | MiscPlugLoad | 505.40 | 5917.6 | 2990.8 |

---

### Gas Equipment Composite

| Parameter | Value |
|---|---|
| **Peak Design Level** | **858.04 W** |
| **Peak Design Level (W/m²)** | **7.7714 W/m²** |
| **Annual Energy** | **3225.7 kWh/yr** |
| **Annual Energy Density** | 29.22 kWh/m²/yr |
| Weighted Fraction Latent | 0.0552 |
| Weighted Fraction Radiant | 0.4070 |
| Weighted Fraction Lost | 0.5378 |
| Honeybee Schedule Name | `composite_gas_equip_sch` |

**Per-appliance breakdown (gas):**

| Appliance | Schedule | DL (W) | EFLH | kWh/yr |
|---|---|---|---|---|
| gas_dryer1 | ClothesDryer | 395.60 | 3910.9 | 1547.1 |
| gas_range1 | CookingRange | 540.94 | 2434.3 | 1316.8 |
| gas_mels1 | MiscPlugLoad | 61.13 | 5917.6 | 361.7 |

---

## Step 5 — Outputs Generated

All files written to `outputs_equip_demand/`:

| File | Description |
|---|---|
| `equipment_electric_schedule.csv` | 8760-hour fractional schedule for electric composite |
| `equipment_gas_schedule.csv` | 8760-hour fractional schedule for gas composite |
| `composite_equipment_schedules.idf` | Both `Schedule:Compact` blocks ready for Honeybee additional strings |
| `equipment_demand_summary.txt` | Full numerical breakdown with weighted heat fractions |

---

## Step 6 — Honeybee Insertion (Assumption)

> **Modelling assumption**: Electric and gas equipment are modelled separately using energy-weighted composite schedules derived from the IECC 2024 US Single-Family IDF. Values represent the combined internal gain from all appliances in each fuel category.

| Parameter | Electric | Gas |
|---|---|---|
| `EquipmentPerFloorArea` | **10.6927 W/m²** | **7.7714 W/m²** |
| Schedule | `composite_elec_equip_sch` | `composite_gas_equip_sch` |
| Insertion method | Honeybee Additional EnergyPlus String | Honeybee Additional EnergyPlus String |

Insert the `Schedule:Compact` blocks from `composite_equipment_schedules.idf` as additional EnergyPlus strings alongside the `ElectricEquipment` and `GasEquipment` objects in the Honeybee model.

---

## Appendix — Script

Script: `equipment_demand_composer.py` (project root)

```
python equipment_demand_composer.py \
    --idf Content/low_rise_Res/US+SF+CZ6A+gasfurnace+unheatedbsmt+IECC_2024.idf \
    --floor-area 110.4089 \
    --out-dir outputs_equip_demand
```

> **Scope**: This script is written specifically for `US+SF+CZ6A+gasfurnace+unheatedbsmt+IECC_2024.idf`. It is not applied globally to other IDF files in the project.
