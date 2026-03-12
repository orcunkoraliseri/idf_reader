# Household Aggregation Module

Convert individual occupant schedules into household-level schedules for Building Energy Models (BEM).

## Problem

BEM tools accept household-level inputs, not individual schedules. We need to aggregate multiple occupants per household into unified presence and activity schedules.

## Data Structure

**Input columns from `occBem.csv`:**
| Column | Description |
|--------|-------------|
| `Household_ID` | Unique household identifier |
| `Occupant_ID_in_HH` | Occupant number within household (1, 2, 3...) |
| `Number Family Members` | Total occupants in household (static) |
| `location` | 1 = home, 0 = away |
| `withNOBODY` | 0 = with others, 1 = alone |
| `Metabolic_Rate` | Activity intensity in Watts |
| `hourStart_Activity`, `hourEnd_Activity` | Time range |

## Aggregation Logic

### Step 1: Household Presence Fraction (`occPre`)

**Continuous presence** as a fraction of total household members:

```
occPre = (count of occupants with location=1) / (Number Family Members)
```

**Examples for a 3-person household:**
| Occupants at Home | occPre |
|-------------------|--------|
| 0 | 0.000 |
| 1 | 0.333 |
| 2 | 0.667 |
| 3 | 1.000 |

### Step 2: Household Metabolic Rate (`occMet`)

**Average** metabolic rate of all occupants present at home:

```
occMet = AVERAGE(Metabolic_Rate) for occupants where location=1
```

> [!NOTE]
> Using **average** (not sum) ensures the metabolic rate represents the typical activity level.
> For example, 3 people sleeping = 70W average, not 210W sum.

**Examples:**
| Scenario | Calculation | occMet |
|----------|-------------|--------|
| 3 people sleeping (70W each) | avg(70,70,70) | 70W |
| 2 people: 1 cooking (175W), 1 watching TV (85W) | avg(175,85) | 130W |
| Nobody home | - | 0W |

## Implementation

### [household_aggregation.py](file:///Users/orcunkoraliseri/Desktop/BEMsetupOCC/occ_utils/household_aggregation.py)

Location: `occ_utils/household_aggregation.py`

`HouseholdAggregator` class with:
- `aggregate()` - Main aggregation function
- `_aggregate_hour()` - Per-hour aggregation logic
- Works with hourly resolution
- Groups by `Household_ID`, `months_season`, `week_or_weekend`, `hourStart_Activity`

**Output columns:**
| Column | Type | Description |
|--------|------|-------------|
| `occPre` | float | Presence fraction (0.0 to 1.0) |
| `occMet` | int | Average metabolic rate of present occupants (Watts) |

**Static columns preserved:**
- `Household_ID`
- `Number Family Members`
- `Region`
- `Room Count`
- `months_season`
- `week_or_weekend`

## Output Format

One row per hour per household (24 rows per household per day type):

```csv
Household_ID,hour,occPre,occMet,months_season,week_or_weekend,Region,Number Family Members,Room Count
855,0,1.0,70,1,1,3,3,6
855,1,1.0,70,1,1,3,3,6
...
```

## Verification

✅ Tested with 5 households, 8 occupants → 120 aggregated records
✅ Presence fractions verified (0.333, 0.667, 1.0 for 3-person household)
✅ Average metabolic rates correct (70W for sleeping, not 210W)
