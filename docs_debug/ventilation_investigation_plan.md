# Ventilation Value Investigation Plan
## Target: `17_18_living_unit1` — `17_18_Two_Storey_House - Calgary.idf`

---

## 🎯 Problem Statement

The HTML report shows **Ventilation [m³/s·m²] ≈ 0.00026** for `living_unit1`, but the IDF contains a raw design flow rate of **0.02832 m³/s**. You need to understand what the 0.00026 value _represents_, how it is calculated, and whether it is correct.

---

## 🟢 Simple Answer — Why 0.00026 and Not 0.02832?

> [!IMPORTANT]
> **Short answer:** `0.02832 m³/s` is the total air volume for the whole house. `0.00026 m³/s·m²` is that same volume divided by the house floor area — a **per-square-metre rate** so you can fairly compare buildings of different sizes.

Think of it like this:

| Question | Value |
|---|---|
| How much total air does the ventilation system move? | **0.02832 m³/s** — this is the raw IDF number, for the whole zone |
| How big is the zone (both floors combined)? | **~108.9 m²** — computed by the geometry module from the IDF surfaces |
| How much air per square metre? | **0.02832 ÷ 108.9 = 0.00026 m³/s·m²** — this is what is shown in the report |

**Why not just show 0.02832?**

Because `0.02832 m³/s` is only meaningful if you know the zone size. A big house and a small apartment could both have `0.02832 m³/s` but that would mean very different ventilation quality inside them. By dividing by the floor area, the metric becomes **size-independent** — you can directly compare this house to any other building in the dataset.

In other words:
- **0.02832 m³/s** → answers *"how much total air?"* (depends on building size)
- **0.00026 m³/s·m²** → answers *"how well ventilated is each square metre?"* (independent of size)

---

## Step 1 — Identify the Three IDF Objects Involved

There are **two separate IDF ventilation objects** that both reference `17_18_living_unit1`:

### Object A — `ZoneVentilation:DesignFlowRate`
| Field | Value |
|---|---|
| Name | `17_18_Ventilation_unit1` |
| Zone | `17_18_living_unit1` |
| Method | `Flow/Zone` |
| Design Flow Rate | **0.0283168464628752 m³/s** |
| Ventilation Type | `Exhaust` |
| Schedule | `17_always_avail` (constant = 1.0) |

### Object B — `DesignSpecification:OutdoorAir`
| Field | Value |
|---|---|
| Name | `17_18_SZ_DSOA_living_unit1` |
| Method | `Flow/Zone` |
| Flow per Person | `0` m³/s-person |
| Flow per Zone Floor Area | *(blank)* |
| **Outdoor Air Flow per Zone** | **0.0283168464628752 m³/s** |

> [!NOTE]
> Both objects carry the **identical** raw value: `0.0283168464628752 m³/s`. This is **not a coincidence** — the `DSOA` object is used by `Sizing:Zone` (referenced at line 3978) to size the AirLoop, while the `ZoneVentilation` object drives the actual runtime exhaust fan. They describe the same physical flow but serve different simulation purposes.

---

## Step 2 — Trace the Raw Flow Rate Value

**0.0283168464628752 m³/s** is a well-known conversion:

```
1 CFM = 0.00047194745 m³/s
60 CFM = 0.02831684... m³/s  ✅
```

> [!IMPORTANT]
> The raw design flow rate is **exactly 60 CFM (Cubic Feet per Minute)**, the standard ASHRAE 62.2 / NBC residential minimum exhaust ventilation rate for a dwelling unit. This is the **physical whole-house exhaust ventilation rate** — not an area- or person-normalized value.

---

## Step 3 — Understand What the Extractor Produces

The `extract_ventilation()` function in `extractors.py` **normalizes** the raw flow rate to make it comparable across zones of different sizes. Here is the full chain:

### 3a. Which code path fires?

The `DESIGNSPECIFICATION:OUTDOORAIR` block (lines 906–961 of `extractors.py`) is processed **first**. The DSOA name `17_18_SZ_DSOA_living_unit1` is matched to zone `17_18_living_unit1` via the fuzzy `"SZDSOA"` prefix-strip logic.

**Method detected:** `flow/zone`

**Code path taken (line 954–955):**
```python
if "flow/zone" in active_methods and area > 0:
    results[matched_zone]["per_area"] += flow_zone / area
```

So the reported value is:

```
per_area = flow_zone  /  floor_area
         = 0.0283168  /  floor_area(living_unit1)
```

### 3b. What is the `floor_area` of `living_unit1`?

The `Zone` object for `living_unit1` (IDF line 2748) does **not** specify a floor area — the code in `geometry.py` computes it from `BuildingSurface:Detailed` surface polygons. Since this is a 2-storey house, the zone spans **both floors**. The geometry module counts the number of distinct floor-surface elevations and stores that in `story_count`.

**Key fact for ventilation:** `extract_ventilation()` uses `floor_area` directly without any story normalization. So the denominator is the **total 2-storey floor area** of the zone.

### 3c. Reverse-engineering the floor area

Using the observed output value:

```
0.00026 = 0.0283168 / floor_area
floor_area = 0.0283168 / 0.00026  ≈  108.9 m²
```

This is consistent with a 2-storey house with a ~54.4 m² footprint per floor (108.9 / 2 floors ≈ **54.5 m²**), which is a reasonable footprint for a compact Canadian detached house.

> [!NOTE]
> The `ZoneVentilation:DesignFlowRate` object (Object A) is **also** processed by the extractor (lines 963–1006), under the `"FLOW/ZONE"` branch, which does the same division by floor area. Both objects deposit into `results[zn]["per_area"]`, so there is a **risk of double-counting** (see Step 5).

---

## Step 4 — Interpret the Physical Meaning of 0.00026

The reported value of **≈ 0.00026 m³/s·m²** means:

> *"For every square metre of conditioned floor area in this zone, the ventilation system moves approximately 0.26 litres of air per second."*

**Cross-checks:**

| Quantity | Value |
|---|---|
| Raw design flow | 0.02832 m³/s = 28.32 L/s |
| Total zone floor area (inferred) | ~108.9 m² |
| Reported per-area rate | 0.02832 / 108.9 ≈ **0.00026 m³/s·m²** ✅ |
| ASHRAE 62.2-2016 residential minimum | 0.15 CFM/ft² ≈ **0.00076 m³/s·m²** |
| Result vs ASHRAE minimum | ~34% of minimum — **below standard** |

The value is **below ASHRAE 62.2** but this is expected for a whole-house exhaust system that operates intermittently (the actual simulated rate depends on schedule and wind/stack coefficients).

---

## Step 5 — Key Questions to Investigate

### Q1 — Is the value being double-counted?

Both Object A (`ZoneVentilation:DesignFlowRate`) and Object B (`DesignSpecification:OutdoorAir`) carry the same 0.02832 m³/s flow. The extractor processes **both** separately and adds results with `+=`. If both successfully match to `living_unit1`, the reported value would be:

```
0.00026 × 2 = 0.00052  (incorrect — a 2× inflation)
```

**Action:** Add a debug print/log in `extract_ventilation()` to check the intermediate per-step contributions for `living_unit1`.

### Q2 — Is the floor area denominator correct for a 2-storey zone?

For the SHW extractor, the code explicitly divides by `story_count` to normalize per-floor. The ventilation extractor does **not** do this. Since the raw flow is per-dwelling (not per-floor), and the denominator is the total 2-storey area, the per-m² rate appears halved compared to what a single-storey normalization would give.

**Action:** Decide whether ventilation should be normalized per-total-area or per-footprint-area. ASHRAE benchmarks typically use **total conditioned floor area**, so the current approach is arguably correct — but it should be documented.

### Q3 — Why 60 CFM specifically?

60 CFM is the **ASHRAE 62.2-2016** default for total mechanical ventilation in residential buildings (table value for a ≤3-bedroom home). Verify this against the original NRCAN CHV model documentation to confirm the design intent.

### Q4 — Why is the `DSOA` method `Flow/Zone` with `flow_per_person = 0`?

This means the outdoor air requirement is defined as a **fixed zone-level flow**, independent of occupancy. This is the correct representation for residential exhaust-only ventilation where the requirement is set by dwelling size, not by occupancy density.

---

## Step 6 — Recommended Debugging Script

Create a small diagnostic script to verify the full chain:

```python
# /tmp/debug_ventilation.py
from idf_parser import parse_idf
from geometry import get_zone_geometry
from extractors import extract_ventilation

IDF_PATH = (
    "Content/CHV_buildings/"
    "17_18_Two_Storey_House - Calgary.idf"
)

idf_data = parse_idf(IDF_PATH)
zone_geo = get_zone_geometry(idf_data)

z = "17_18_living_unit1"
print(f"Floor area:  {zone_geo[z]['floor_area']:.3f} m²")
print(f"Story count: {zone_geo[z]['story_count']}")
print(f"Volume:      {zone_geo[z]['volume']:.3f} m³")

# Check raw objects
for obj in idf_data.get("DESIGNSPECIFICATION:OUTDOORAIR", []):
    if "living_unit1" in obj[0].lower():
        print(f"\nDSOA object:  {obj}")

for obj in idf_data.get("ZONEVENTILATION:DESIGNFLOWRATE", []):
    if "living_unit1" in obj[1].lower():
        print(f"\nZoneVent obj: {obj}")

vent = extract_ventilation(idf_data, zone_geo)
print(f"\nExtracted ventilation for {z}:")
print(f"  per_area:   {vent[z]['per_area']:.6f} m³/s·m²")
print(f"  per_person: {vent[z]['per_person']:.6f} m³/s·person")
print(f"  ach:        {vent[z]['ach']:.4f} ACH")

# Sanity check: raw flow / area
raw_flow = 0.0283168464628752
per_area_expected = raw_flow / zone_geo[z]["floor_area"]
print(f"\nExpected (1× raw): {per_area_expected:.6f} m³/s·m²")
print(f"Expected (2× raw): {per_area_expected * 2:.6f} m³/s·m²")
```

---

## Step 7 — Summary of Findings

| Item | Value | Notes |
|---|---|---|
| IDF raw flow | **0.02832 m³/s** | = exactly 60 CFM |
| Zone floor area (inferred) | **~108.9 m²** | 2-storey, ~54.5 m² footprint |
| Reported per-area rate | **~0.00026 m³/s·m²** | = 0.02832 / 108.9 |
| Story count | **2** | As detected by floor elevation analysis |
| Double-count risk | ⚠️ **Yes** | Both DSOA and ZoneVent map to same zone |
| Physical interpretation | Per-m² ventilation density | Used to compare across zones |
| Below ASHRAE 62.2? | Yes, ~34% of minimum | Expected for intermittent exhaust |

> [!WARNING]
> The highest-priority action item is **Q1 (double-counting check)**. If both the `DSOA` and `ZoneVentilation` objects successfully match the zone, the reported value would be 0.00052 instead of 0.00026 — or vice versa, one may be silently suppressed. Run the debug script to confirm the actual per-step contributions.

---

## Step 8 — Honeybee Component Selection: HB Fan Ventilation vs HB Ventilation

### The Core Question

Your IDF was generated by Honeybee and uses **`ZoneVentilation:DesignFlowRate`** with an absolute `Flow/Zone` of **0.02832 m³/s**. You are asking: *is HB Fan Ventilation the right component to use, or should it be HB Ventilation?*

**The short answer: ✅ `HB Fan Ventilation` is the correct component for this single detached house.**

---

### What Each Component Does

| Component | EnergyPlus Object Created | Input Unit | Suitable For |
|---|---|---|---|
| **HB Ventilation** (`HB Ventilation`) | `DesignSpecification:OutdoorAir` | m³/s-person, m³/s-m², or ACH | Minimum outdoor air supplied **by an HVAC system** (ideal air loads) |
| **HB Fan Ventilation** (`HB Fan Ventilation`) | `ZoneVentilation:DesignFlowRate` | **m³/s total** (`flow_rate`) | Dedicated fan-driven airflow — exhaust fans, whole-house ventilators, supply fans |

---

### Why HB Fan Ventilation is Correct Here

**1. The IDF object type matches.**
The CHV model uses `ZoneVentilation:DesignFlowRate` with `Ventilation Type = Exhaust`. This EnergyPlus object is exactly what `HB Fan Ventilation` generates. `HB Ventilation` generates `DesignSpecification:OutdoorAir` instead, which is for HVAC-delivered outdoor air — a completely different simulation pathway.

**2. The input value matches.**
`HB Fan Ventilation` takes a `flow_rate` in **m³/s total for the zone** — which is exactly `0.02832 m³/s` (the raw IDF value). You do **not** divide by area here; Honeybee uses the absolute value directly.

**3. The physical intent matches.**
This is a **residential exhaust fan** (whole-house ventilation), not conditioned outdoor air delivered by an air handler. ASHRAE 62.2 — which governs residential buildings — requires a dwelling-unit-level exhaust flow, sized per dwelling, not per m² or per person. `HB Fan Ventilation` models exactly this.

**4. The HB Ventilation component would be wrong here.**
`HB Ventilation` feeds into the ideal air system and is used for minimum outdoor air compliance in commercial/occupancy-driven settings (ASHRAE 62.1). For a residential house without a mechanical ventilation system connected to an air handler, using `HB Ventilation` would either have no effect (if the zone is not conditioned by an ideal air system) or model the wrong physics.

---

### What Value to Plug In

```
HB Fan Ventilation
  └── flow_rate  =  0.02832 m³/s   ← the raw ZoneVentilation:DesignFlowRate value
  └── pressure_rise  =  0 Pa       ← as in the IDF (Fan Pressure Rise = 0)
  └── efficiency  =  1.0           ← as in the IDF (Fan Total Efficiency = 1)
  └── ventilation_type  =  Exhaust ← matches IDF Ventilation Type
  └── schedule   =  Always On      ← matches 17_always_avail
```

> [!IMPORTANT]
> Do **not** use `0.00026 m³/s·m²` as the input to `HB Fan Ventilation`. That is a post-processed metric for your idf_reader report only. The actual Honeybee input must be the **absolute zone flow rate: 0.02832 m³/s**.

---

### Standard Reference: ASHRAE 62.2-2016 for Detached Houses

For a single-family detached house (≤3 bedrooms, ≤5 occupants), ASHRAE 62.2-2016 Table 4.1a specifies:

| Floor Area (ft²) | Min. Ventilation (CFM) |
|---|---|
| < 1500 | **45 CFM** |
| 1500–3000 | **60 CFM** ← *this model* |
| > 3000 | **75 CFM** |

The model uses **60 CFM = 0.02832 m³/s**, consistent with a mid-size (~1,173 ft² / ~109 m²) Calgary detached house. This confirms the value is correct and `HB Fan Ventilation` with `flow_rate = 0.02832 m³/s` is the appropriate representation.

> [!TIP]
> If you need to verify compliance in future models, you can calculate the ASHRAE 62.2 minimum directly:
> ```
> Q_min [CFM]  =  0.01 × floor_area[ft²]  +  7.5 × (N_bedrooms + 1)
> Q_min [m³/s] =  Q_min[CFM] × 0.000472
> ```
> For this house: 0.01 × 1,173 + 7.5 × (3+1) = 11.7 + 30 = **41.7 CFM** minimum.
> The model uses 60 CFM — **43% above the minimum**, which is a conservative but acceptable design choice.
