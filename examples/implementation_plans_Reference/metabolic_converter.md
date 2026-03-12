# Metabolic Rate Converter Implementation

Convert occupant activity descriptions to metabolic rates (Watts) using the 2024 Compendium of Physical Activities for Building Energy Modeling (BEM) occupant internal gains.

## Background

- **MET (Metabolic Equivalent of Task):** Standard unit measuring energy expenditure
- **Conversion:** 1 MET ≈ 70 Watts (for average 70kg adult)
- **Data Source:** Italian Time Use Survey with 145 activity categories

---

## Proposed Changes

### occ_utils/metabolic_converter.py

#### Core Mapping: `METABOLIC_RATE_MAP`
```python
METABOLIC_RATE_MAP = {
    'Sleeping': 70,           # 1.0 MET
    'Eating/Drinking': 105,   # 1.5 MET
    'House Cleaning': 210,    # 3.0 MET
    'Walking/Hiking': 280,    # 4.0 MET
    'Jogging/Running': 490,   # 7.0 MET
    # ... 145 activities total
}
```

**MET Category Ranges:**
| Category | MET Range | Watts |
|----------|-----------|-------|
| Sleep/Rest | 1.0 | 70W |
| Sedentary (TV, reading) | 1.2-1.5 | 85-105W |
| Light (eating, personal care) | 1.5-2.0 | 105-140W |
| Moderate (household, walking) | 2.0-3.0 | 140-210W |
| Active (sports, gardening) | 3.0-6.0 | 210-420W |
| Vigorous (running) | 6.0-8.0 | 420-560W |

---

#### Function: `get_metabolic_rate`
```python
def get_metabolic_rate(activity_description):
    """
    Get metabolic rate in Watts for a given activity description.
    Returns DEFAULT_METABOLIC_RATE (100W) for unknown activities.
    """
```

---

#### Function: `convert_activities_to_watts`
```python
def convert_activities_to_watts(df, activity_column='Occupant_Activity', 
                                 output_column='Metabolic_Rate'):
    """
    Converts activity descriptions to metabolic rates (Watts).
    Adds 'Metabolic_Rate' column next to activity column.
    """
```

**Input DataFrame:**
| Household_ID | Occupant_Activity | ... |
|--------------|-------------------|-----|
| 1 | Sleeping | ... |
| 1 | Eating/Drinking | ... |

**Output DataFrame:**
| Household_ID | Occupant_Activity | Metabolic_Rate | ... |
|--------------|-------------------|----------------|-----|
| 1 | Sleeping | 70 | ... |
| 1 | Eating/Drinking | 105 | ... |

---

#### Function: `print_activity_statistics`
```python
def print_activity_statistics(df, activity_column, metabolic_column):
    """
    Print formatted statistics about activities and metabolic rates.
    Shows distribution, top activities, and rate ranges.
    """
```

---

## Data Flow Diagram

```
classified_occ.csv
       │
       ▼
┌──────────────────────┐
│  read_occupancy_data │
└──────────────────────┘
       │
       ▼
┌──────────────────────┐
│ convert_activity_    │
│ codes (code → desc)  │
└──────────────────────┘
       │
       ▼
┌──────────────────────┐
│ convert_activities_  │
│ to_watts             │
└──────────────────────┘
       │
       ▼
┌──────────────────────┐
│ DataFrame with       │
│ Metabolic_Rate (W)   │
└──────────────────────┘
```

---

## Usage Example

```python
from occ_utils.read_occupancy import read_occupancy_data, convert_activity_codes
from occ_utils.metabolic_converter import convert_activities_to_watts

# Load and process data
df = read_occupancy_data()
df = convert_activity_codes(df)
df = convert_activities_to_watts(df)

# Result: DataFrame with 'Metabolic_Rate' column in Watts
```

---

## Verification Results

| Metric | Value |
|--------|-------|
| Total records | 984,936 |
| Mapping success | 100% |
| Unique activities | 145 |
| Rate range | 70W - 490W |
| Mean rate | 112.3W |
| Std deviation | 56.0W |

**Top Activities by Frequency:**
1. Sleeping (37.1%) @ 70W
2. Eating/Drinking (8.7%) @ 105W
3. Watching TV/Video (8.2%) @ 85W
4. Main Job Work (6.2%) @ 125W
5. Washing/dressing (3.7%) @ 170W

---

## Cross-Platform Compatibility

- ✅ **Windows:** Uses `os.path` for platform-agnostic paths
- ✅ **macOS:** Tested on Darwin 22.6.0
- ✅ **Python:** Requires Python 3.6+ (tested on 3.9.2)

---

## Status: IMPLEMENTED

Core metabolic rate conversion functionality is complete.
- Module: `occ_utils/metabolic_converter.py`
- Sample output: `occupancy/samples/occupancy_with_metabolic_rates.csv`
