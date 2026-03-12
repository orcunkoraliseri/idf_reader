# Unified Main Entry Point Restructuring

## Goal
Create a single `main_control.py` that serves as the unified entry point for all project workflows including occupancy-based BEM simulations.

---

## Menu Options

```
============================================================
OCCUPANCY-BEM SIMULATION FRAMEWORK
============================================================
1. Visualize a building
2. Run a simulation
3. Run all simulations  
4. Process & Visualize results
5. Run Comparative Simulation (single building)
6. Run ALL Comparative Simulations (batch)
q. Quit
```

---

## Option 5: Single Building Comparative Workflow

```
Step 1: Generate occupancy schedules (from occBem.csv)
Step 2: Modify IDF with occupancy data → Creates _OCCUPANCY.idf
Step 3: Run simulations (both default & modified) - PARALLEL
Step 4: Process results
Step 5: Compare & visualize results
```

**Outputs:**
- `SimResults/comparison_{BuildingName}/end_use_comparison.png`
- `SimResults/comparison_{BuildingName}/daily_energy_comparison.png`
- `SimResults/comparison_{BuildingName}/zone_schedules_comparison.png`

---

## Option 6: Batch Comparative Workflow (Fully Parallel)

```
PHASE 1: Load occupancy data
PHASE 2: Prepare ALL modified IDFs
PHASE 3: Collect simulation jobs
PHASE 4: Run ALL simulations in parallel
PHASE 5: Process ALL results
PHASE 6: Generate individual comparisons
PHASE 7: Cross-building summary charts
```

**Summary Charts (SimResults/batch_summary/):**
- `all_buildings_pct_change.png` - % energy change by category
- `all_buildings_absolute.png` - Absolute kWh/m² comparison
- `all_buildings_daily.png` - Daily Heating/Cooling for all buildings

---

## File Structure

```
BEMsetupOCC/
├── main_control.py               ← Unified entry point
├── bem_utils/
│   ├── runner.py                 ← Simulation runner (parallel support)
│   ├── read_results.py           ← SQL result processing
│   ├── optimize_idfs.py          ← IDF optimization + output variables
│   └── viewer.py                 ← 3D IDF visualization
├── integration_utils/
│   ├── main_integration.py       ← Schedule generation orchestration
│   ├── schedule_generator.py     ← Occupancy/Activity/Lighting/Equipment schedules
│   ├── household_matcher.py      ← Zone-to-household assignment
│   ├── idf_occupancy_modifier.py ← Modifies People/Lights/Equipment in IDF
│   ├── results_comparator.py     ← Energy comparison charts
│   ├── schedule_visualizer.py    ← Schedule visualization grids
│   └── schedule_validation.py    ← Schedule validation tests
├── occ_utils/
│   ├── main_occupancy.py         ← Occupancy data processing
│   ├── activity_converter.py     ← Activity code to description
│   └── metabolic_converter.py    ← Activity to metabolic rate
├── Building/
│   ├── 3A/                       ← Climate zone 3A IDFs
│   └── 4A/                       ← Climate zone 4A IDFs
├── WeatherFile/                  ← EPW weather files
├── SimResults/                   ← Simulation outputs
│   ├── comparison_*/             ← Individual building comparisons
│   └── batch_summary/            ← Cross-building summary charts
└── occupancy/
    └── occBem.csv                ← 100 households, 28,800 records
```

---

## Key Results

| Category | Default → Modified | Explanation |
|----------|-------------------|-------------|
| Heating | +33% to +52% | Less internal heat gains |
| Cooling | -14% to -16% | Less internal heat to remove |
| Equipment | -14% to -17% | Follows occupancy schedules |
| Lighting | -3% to -6% | Follows occupancy presence |
| Fans | -5% to -8% | Less HVAC demand |

---

## Usage

```bash
# Run unified control
python main_control.py

# Direct batch simulation
python main_control.py  # Then select option 6
```
