# EnergyPlus Simulation Pipeline — Implementation Plan

> Based on the architecture in `/Users/orcunkoraliseri/Desktop/idf_reader/examples/eSim_bem_utils_Reference/` and `/BEMSetup_Reference/`.

---

## Project Structure

```
occModeling/
├── main.py                    ← Phase 1: Workflow Controller
├── eSim_bem_utils/
│   ├── config.py              ← Platform paths (EnergyPlus, IDD)
│   ├── idf_optimizer.py       ← Phase 2: IDF Preparation
│   ├── simulation.py          ← Phase 3: Simulation Runner
│   ├── plotting.py            ← Phase 4+5: SQL Extraction & Visualization
│   └── reporting.py           ← Phase 5: Statistical Reporting
├── 0_BEM_Setup/
│   ├── Buildings/             ← Your .idf files
│   ├── WeatherFile/           ← Symlink or copy from .../Content/WeatherFiles/
│   └── SimResults/            ← Runtime output (eplusout.sql, JSON, PNG)
```

> **Note:** Your project at `occModeling/eSim_bem_utils/` already contains `idf_optimizer.py`, `simulation.py`, `plotting.py`, `reporting.py`, and `main.py`. The plan below explains what each must implement, so you can verify and complete each module.

---

## Phase 1 — Workflow Controller (`main.py`)

**Reference:** `eSim_bem_utils_Reference/main.py` + `BEMSetup_Reference/main_BEM.py`

### 1.1 Configuration Block

At the top of `main.py`, read platform paths from `config.py`:

```python
from eSim_bem_utils import config, idf_optimizer, simulation, plotting, reporting

ENERGYPLUS_EXE = config.ENERGYPLUS_EXE   # e.g. /Applications/EnergyPlus-24-2-0/energyplus
IDD_FILE       = config.IDD_FILE
BUILDINGS_DIR  = os.path.join(BASE_DIR, "0_BEM_Setup", "Buildings")
WEATHER_DIR    = "/Users/orcunkoraliseri/Desktop/idf_reader/Content/WeatherFiles"
SIM_RESULTS_DIR = os.path.join(BASE_DIR, "0_BEM_Setup", "SimResults")
```

### 1.2 EPW File Selection

Implement `select_weather_file(weather_dir)` — mirrors `main_BEM.py:37-72`:

```python
def select_weather_file(weather_dir):
    epw_files = glob.glob(os.path.join(weather_dir, '*.epw'))
    for i, f in enumerate(epw_files):
        print(f"  {i+1}. {os.path.basename(f)}")
    choice = int(input("Select EPW: ")) - 1
    return epw_files[choice]
```

Your weather directory already contains `CAN_QC_Montreal-Trudeau.Intl.AP.716270_CWEC2020v2.epw`. The function must glob `*.epw` from `WEATHER_DIR` and present a numbered list.

### 1.3 IDF Discovery

```python
def find_idf_files(buildings_dir):
    return glob.glob(os.path.join(buildings_dir, '**', '*.idf'), recursive=True)
```

### 1.4 Menu Loop

Implement a `while True` menu with these options — mirrors both reference `main.py` files:

| Option | Action |
|--------|--------|
| 1 | Run single simulation (select IDF + EPW) |
| 2 | Run all simulations in parallel |
| 3 | Process results (SQL → JSON) for a selected `SimResults/` subdirectory |
| 4 | Visualize results (load JSON → show plot) |
| q | Quit |

**Critical data hand-off from Option 1 → 3 → 4:**
- Option 1 produces `SimResults/<idf_name>_<epw_name>/eplusout.sql`
- Option 3 consumes `eplusout.sql` and writes `eui_summary.json` + `*_eui_breakdown.png`
- Option 4 loads `eui_summary.json` and shows the plot interactively

### 1.5 Auto-Processing After Simulation

After a successful `run_simulation()` call, immediately call `plotting.process_single_result(output_dir)` — mirrors `main_BEM.py:139-142`:

```python
result = simulation.run_simulation(idf_path, epw_path, output_dir, ENERGYPLUS_EXE)
if result['success']:
    plotting.process_single_result(output_dir)
```

---

## Phase 2 — IDF Preparation & Optimization (`idf_optimizer.py`)

**Reference:** `eSim_bem_utils_Reference/idf_optimizer.py` (full version) and `BEMSetup_Reference/optimize_idfs.py` (simplified version)

### 2.1 Entry Point

```python
def optimize_idf(idf_path: str, idd_file: str) -> str:
    """Modifies the IDF in-place. Returns the path."""
    IDF.setiddname(idd_file)
    idf = IDF(idf_path)
    _inject_sqlite_output(idf)
    _inject_output_meters(idf)
    _inject_output_variables(idf)
    _apply_simulation_fixes(idf)
    idf.save()
    return idf_path
```

### 2.2 Inject `Output:SQLite`

This is the **most critical injection** — without it, `eplusout.sql` is never written:

```python
def _inject_sqlite_output(idf):
    existing = idf.idfobjects.get('OUTPUT:SQLITE', [])
    if not existing:
        obj = idf.newidfobject('OUTPUT:SQLITE')
        obj.Output_Type = 'SimpleAndTabular'
```

### 2.3 Inject `Output:Meter` Objects (Monthly)

These feed `get_meter_data()` in Phase 4:

```python
REQUIRED_METERS = [
    'Heating:EnergyTransfer',
    'Cooling:EnergyTransfer',
    'InteriorLights:Electricity',
    'InteriorEquipment:Electricity',
    'Fans:Electricity',
    'WaterSystems:EnergyTransfer',
]

def _inject_output_meters(idf):
    existing_names = {o.Key_Name for o in idf.idfobjects.get('OUTPUT:METER', [])}
    for meter in REQUIRED_METERS:
        if meter not in existing_names:
            obj = idf.newidfobject('OUTPUT:METER')
            obj.Key_Name = meter
            obj.Reporting_Frequency = 'Monthly'
```

### 2.4 Inject `Output:Variable` Objects (Hourly)

These feed `get_hourly_meter_data()` for time-series reporting:

```python
REQUIRED_OUTPUT_VARIABLES = [
    ('Zone Lights Electricity Energy', 'Hourly'),
    ('Zone Electric Equipment Electricity Energy', 'Hourly'),
    ('Fan Electricity Energy', 'Hourly'),
    ('Zone Air System Sensible Heating Energy', 'Hourly'),
    ('Zone Air System Sensible Cooling Energy', 'Hourly'),
    ('Zone Ideal Loads Supply Air Total Heating Energy', 'Hourly'),
    ('Zone Ideal Loads Supply Air Total Cooling Energy', 'Hourly'),
]

def _inject_output_variables(idf):
    existing = {(o.Variable_Name, o.Reporting_Frequency)
                for o in idf.idfobjects.get('OUTPUT:VARIABLE', [])}
    for var_name, freq in REQUIRED_OUTPUT_VARIABLES:
        if (var_name, freq) not in existing:
            obj = idf.newidfobject('OUTPUT:VARIABLE')
            obj.Key_Value = '*'
            obj.Variable_Name = var_name
            obj.Reporting_Frequency = freq
```

### 2.5 Speed Optimizations

Mirrors `BEMSetup_Reference/optimize_idfs.py:24-36` and the full `idf_optimizer.py`:

```python
def _apply_simulation_fixes(idf):
    # 1. Timestep: set to 4 (15-min intervals — faster than 6)
    for ts in idf.idfobjects.get('TIMESTEP', []):
        ts.Number_of_Timesteps_per_Hour = 4

    # 2. Solar Distribution: FullExterior is faster than FullInteriorAndExterior
    for bld in idf.idfobjects.get('BUILDING', []):
        if bld.Solar_Distribution == 'FullInteriorAndExterior':
            bld.Solar_Distribution = 'FullExterior'

    # 3. Shadow Calculation (pixel counting frequency)
    for sc in idf.idfobjects.get('SHADOWCALCULATION', []):
        sc.Calculation_Frequency = 20  # recalculate every 20 days

    # 4. Surface Convection (DOE-2 is faster than detailed)
    for ha in idf.idfobjects.get('HEATBALANCEALGORITHM', []):
        pass  # Leave as-is unless known to be slow

    # 5. Fix deprecated field values (E+ 24.2 compat)
    for p in idf.idfobjects.get('PEOPLE', []):
        if p.Mean_Radiant_Temperature_Calculation_Type in ('ZoneAveraged', 'zoneaveraged'):
            p.Mean_Radiant_Temperature_Calculation_Type = 'EnclosureAveraged'
```

> **Dependency:** `idf_optimizer.optimize_idf()` must be called **before** `simulation.run_simulation()` in `main.py`.

---

## Phase 3 — Simulation Execution (`simulation.py`)

**Reference:** `eSim_bem_utils_Reference/simulation.py` (fully reviewed)

Your `occModeling/eSim_bem_utils/simulation.py` should match this reference exactly. The key logic is:

### 3.1 Single Simulation

```python
def run_simulation(idf_path, epw_path, output_dir, ep_path, n_jobs=1, quiet=False):
    # 1. Create output_dir
    os.makedirs(output_dir, exist_ok=True)

    # 2. Resolve ep_exe and ep_dir

    # 3. Copy IDF to output_dir/in.idf
    shutil.copy2(idf_path, os.path.join(output_dir, 'in.idf'))

    # 4. Copy Energy+.idd to output_dir (required by ExpandObjects)
    shutil.copy2(idd_path, os.path.join(output_dir, 'Energy+.idd'))

    # 5. Run ExpandObjects (handles HVACTemplate:* objects)
    subprocess.run([expand_objects_exe], cwd=output_dir, check=True, capture_output=quiet)

    # 6. Determine simulation IDF (expanded.idf if it exists, else in.idf)
    simulation_idf = 'expanded.idf' if os.path.exists(...) else 'in.idf'

    # 7. Build and run EnergyPlus command
    cmd = [ep_exe, '-w', epw_path, '-d', output_dir]
    if n_jobs > 1: cmd += ['-j', str(n_jobs)]
    cmd.append(simulation_idf)
    subprocess.run(cmd, check=True, capture_output=quiet)

    return {'success': True, 'name': name, 'output_dir': output_dir, ...}
```

**Why ExpandObjects first?** EnergyPlus `HVACTemplate:*` objects are compact forms that must be expanded into full objects before the main simulation. If your IDFs don't use `HVACTemplate`, the step is a no-op but harmless.

### 3.2 Parallel Execution

```python
def run_simulations_parallel(simulation_jobs, ep_path, max_workers=None):
    # Force n_jobs=1 per worker (avoid CPU oversubscription)
    # Use ProcessPoolExecutor (not ThreadPool — EnergyPlus is CPU-bound)
    # Each job dict: {'idf', 'epw', 'output_dir', 'name'}
    # Progress: threading.Event + background monitor thread (prints elapsed every 30s)
    # Returns: {'successful': [...], 'failed': [...], 'total_time': float}
```

**Key rule from reference:** When running N simulations in parallel, set each simulation's internal thread count to 1 (`n_jobs=1`). Using `-j 4` per simulation while also running 4 parallel processes would require 16 cores.

---

## Phase 4 — Results Extraction (`plotting.py`)

**Reference:** `eSim_bem_utils_Reference/plotting.py:91-221` (fully reviewed)

All SQL extraction logic lives in `plotting.py` in the reference — not a separate `read_results.py`.

### 4.1 Database Connection

```python
import sqlite3
conn = sqlite3.connect(os.path.join(output_dir, 'eplusout.sql'))
```

### 4.2 Floor Area Query

```python
def get_tabular_data(conn, table_name):
    query = """
    SELECT TableName, RowName, ColumnName, Units, Value
    FROM TabularDataWithStrings
    WHERE TableName = ?
    """
    return pd.read_sql_query(query, conn, params=(table_name,))

# Usage:
area_df = get_tabular_data(conn, 'Building Area')
# RowName='Total Building Area'          → total_floor_area (m²)
# RowName='Net Conditioned Building Area' → conditioned_floor_area (m²)
```

> **Watch out:** If the IDF was generated from a US tool, areas may be in `ft²`. The reference checks for `units == 'ft2'` and applies `× 0.092903`.

### 4.3 End-Use Energy Query

```python
query = """
SELECT TableName, RowName, ColumnName, Units, Value
FROM TabularDataWithStrings
WHERE TableName = 'End Uses By Subcategory' OR TableName = 'End Uses'
"""
df = pd.read_sql_query(query, conn)
# Prefer 'End Uses By Subcategory'; fall back to 'End Uses' if empty
```

**Target categories** (from the 6 required end-uses):

| EnergyPlus RowName | Display | Color |
|--------------------|---------|-------|
| `Heating:General` or `Heating` | Space Heating | `#8A1100` Dark Red |
| `Cooling:General` or `Cooling` | Space Cooling | `#041991` Dark Blue |
| `Interior Lighting:General` | Interior Lighting | `#FF7900` Orange |
| `Interior Equipment:General` | Interior Equipment | `#EF2700` Red |
| `Fans:General` | HVAC Fans | `#9370DB` Purple |
| `Water Systems:General` | Water Systems | `#00CED1` Turquoise |

**Skip** any row where `ColumnName` contains `'Water'` or `Units` is `'m3'`.

### 4.4 Unit Conversion

```python
if   units == 'GJ':   val_kwh = val * 277.778     # Primary case for E+ tabular
elif units == 'kWh':  val_kwh = val                # Already correct
elif units == 'J':    val_kwh = val / 3_600_000    # Rare in tabular
elif units == 'kBtu': val_kwh = val * 0.293071
elif units == 'MJ':   val_kwh = val * 0.277778
```

### 4.5 Category Parsing

```python
if ':' in row_name:
    cat, sub = row_name.split(':', 1)
    eu_cat = cat if sub.strip() in ('General', 'Other', '') else sub.strip()
else:
    eu_cat = row_name
```

### 4.6 EUI Calculation

```python
area = conditioned_floor_area or total_floor_area  # prefer conditioned
eui = total_energy_kwh / area                       # kWh/m²
end_uses_normalized = {k: v / area for k, v in end_uses.items()}
```

### 4.7 Results Dictionary Schema

```python
{
    'eui': float,                    # Total EUI kWh/m²
    'total_floor_area': float,       # m²
    'conditioned_floor_area': float, # m²
    'total_energy': float,           # kWh
    'end_uses': dict,                # category → absolute kWh
    'end_uses_normalized': dict      # category → kWh/m²
}
```

### 4.8 `process_single_result()` — The Orchestrator

```python
def process_single_result(output_dir, plot_output_dir=None, scaling_factor=1.0):
    conn = sqlite3.connect(os.path.join(output_dir, 'eplusout.sql'))
    eui_results = calculate_eui(conn)
    conn.close()

    # 1. Save JSON
    json.dump(eui_results, open(os.path.join(output_dir, 'eui_summary.json'), 'w'), indent=4)

    # 2. Generate breakdown plot
    plot_path = os.path.join(output_dir, f"{os.path.basename(output_dir)}_eui_breakdown.png")
    plot_eui_breakdown(eui_results, plot_path)

    return eui_results
```

> **Data hand-off:** `process_single_result()` is the bridge between Phase 3 and Phase 5. It reads `eplusout.sql` (Phase 3 output) and produces `eui_summary.json` + `*_eui_breakdown.png` (Phase 5 inputs).

---

## Phase 5 — Visualization & Reporting (`plotting.py` + `reporting.py`)

**Reference:** `eSim_bem_utils_Reference/plotting.py:17-55, 274-329`

### 5.1 Semantic Color Map

Defined as a module-level constant in `plotting.py`:

```python
ENERGY_COLOR_MAP = {
    'heating':      '#8A1100',  # Dark Red   — energy gain
    'heat':         '#8A1100',
    'cooling':      '#041991',  # Dark Blue  — energy loss
    'cool':         '#041991',
    'lighting':     '#FF7900',  # Orange     — internal gain
    'light':        '#FF7900',
    'equipment':    '#EF2700',  # Red        — internal gain
    'plug':         '#EF2700',
    'fan':          '#9370DB',  # Purple
    'water':        '#00CED1',  # Turquoise
    'people':       '#FEF401',  # Yellow
    'infiltration': '#0730E0',
    'ventilation':  '#0758FF',
}

DEFAULT_PALETTE = [
    '#041991', '#0730E0', '#0758FF', '#01E8FF',
    '#A6F956', '#FEF401', '#FF7900', '#EF2700', '#8A1100',
]
```

### 5.2 Color Lookup Function

```python
def get_energy_color(category_name: str) -> Optional[str]:
    lower = category_name.lower()
    for key, color in ENERGY_COLOR_MAP.items():
        if key in lower:
            return color
    return None  # caller falls back to DEFAULT_PALETTE[idx]
```

### 5.3 EUI Breakdown Bar Chart

```python
def plot_eui_breakdown(eui_results: dict, output_path: str) -> None:
    end_uses = eui_results['end_uses_normalized']
    labels = list(end_uses.keys())
    values = list(end_uses.values())

    # Human-readable labels via END_USE_LABELS dict
    display_labels = [END_USE_LABELS.get(l.lower(), l) for l in labels]

    # Assign semantic colors
    default_idx = 0
    colors = []
    for label in labels:
        c = get_energy_color(label)
        if c:
            colors.append(c)
        else:
            colors.append(DEFAULT_PALETTE[default_idx % len(DEFAULT_PALETTE)])
            default_idx += 1

    fig, ax = plt.subplots(figsize=(14, 7))
    bars = ax.bar(display_labels, values, color=colors, edgecolor='black', linewidth=0.5)

    # Value labels above bars
    for bar, val in zip(bars, values):
        ax.annotate(f'{val:.1f}',
                    xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                    xytext=(0, 3), textcoords='offset points',
                    ha='center', va='bottom', fontsize=9)

    ax.set_xlabel('End Use Category', fontsize=12, fontweight='bold')
    ax.set_ylabel('EUI (kWh/m²)', fontsize=12, fontweight='bold')
    ax.set_title(os.path.basename(output_path).replace('_eui_breakdown.png', ''), fontsize=13)
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)
    ax.set_axisbelow(True)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
```

### 5.4 Readable Label Map

```python
END_USE_LABELS = {
    'heating':            'Space Heating',
    'cooling':            'Space Cooling',
    'interior lighting':  'Interior Lighting',
    'interior equipment': 'Interior Equipment',
    'fans':               'HVAC Fans',
    'water systems':      'Water Systems',
    'pumps':              'HVAC Pumps',
    'exterior lighting':  'Exterior Lighting',
}
```

### 5.5 Reporting (`reporting.py`)

`ReportGenerator` handles **multi-run statistical analysis**. For a standard single-simulation workflow you only need it for batch/comparative runs. Its key sections are:

- **Annual Metrics:** mean ± std per end-use per scenario
- **Statistical Variability:** ANOVA + Tukey HSD + Cohen's d (requires `scipy.stats`)
- **Raw Data:** per-run EUI values in CSV
- **Hourly Load Profiles:** 24-hour winter/summer weekday/weekend profiles (requires hourly meter data from `get_hourly_meter_data()`)
- **Peak Loads:** max W/m² for Heating and Cooling per scenario
- **Summary of Key Findings:** plain-language % change vs. Default scenario

For a **minimal first implementation**, skip `reporting.py` and rely on `plot_eui_breakdown()` alone.

---

## Critical Dependencies & Data Hand-Offs

```
main.py
  │
  ├─[1]─► idf_optimizer.optimize_idf(idf_path, IDD_FILE)
  │              └─ requires: eppy, Energy+.idd, IDF file
  │              └─ produces: modified .idf with Output:SQLite + meters
  │
  ├─[2]─► simulation.run_simulation(idf_path, epw_path, output_dir, ep_exe)
  │              └─ requires: modified .idf (from [1]), EPW, EnergyPlus binary
  │              └─ requires: Energy+.idd copied to output_dir for ExpandObjects
  │              └─ produces: output_dir/eplusout.sql  ← KEY OUTPUT
  │
  ├─[3]─► plotting.process_single_result(output_dir)
  │              └─ requires: output_dir/eplusout.sql (from [2])
  │              └─ queries: TabularDataWithStrings (Building Area, End Uses)
  │              └─ produces: output_dir/eui_summary.json
  │              └─ produces: output_dir/*_eui_breakdown.png
  │
  └─[4]─► plotting.plot_eui_breakdown(json.load('eui_summary.json'), ...)
                 └─ requires: eui_summary.json (from [3])
                 └─ produces: interactive/static PNG chart
```

### Checklist of Common Failure Points

| Failure | Root Cause | Fix |
|---------|-----------|-----|
| `eplusout.sql` not generated | `Output:SQLite` missing from IDF | Step 2.2 — inject before simulation |
| `ExpandObjects` crashes | `Energy+.idd` not in `output_dir` | Step 3.1 — copy IDD before running |
| `Building Area` table empty | Wrong table name | Query `TabularDataWithStrings` with `TableName = 'Building Area'` exactly |
| All EUI values = 0 | Units not `GJ` (e.g. `kBtu`) | Add all unit branches in conversion (Step 4.4) |
| `End Uses By Subcategory` empty | Older IDF/E+ version | Fall back to `End Uses` table (Step 4.3) |
| Areas in `ft²` not `m²` | US-origin IDF | Check `Units` column and multiply by `0.092903` |
| Parallel sim crashes silently | Missing `if __name__ == '__main__'` guard | Required on macOS/Windows for `ProcessPoolExecutor` |

### macOS `ProcessPoolExecutor` Guard

In `main.py`, the entry point **must** be protected:

```python
if __name__ == '__main__':
    main()
```

Without this, `ProcessPoolExecutor` will recursively spawn processes on macOS/Windows.

---

## Recommended Implementation Order

1. **`config.py`** — Set `ENERGYPLUS_DIR`, `ENERGYPLUS_EXE`, `IDD_FILE` for macOS
2. **`idf_optimizer.py`** — Inject `Output:SQLite` and meters; test on one IDF
3. **`simulation.py`** — Single `run_simulation()`; verify `eplusout.sql` is produced
4. **`plotting.py`** — Implement `calculate_eui()` + `process_single_result()`; test on the SQL file
5. **`plotting.py`** — Implement `plot_eui_breakdown()`; verify PNG output
6. **`main.py`** — Wire the menu loop (Options 1 → 3 → 4)
7. **`simulation.py`** — Add `run_simulations_parallel()` for batch runs
8. **`reporting.py`** — Add `ReportGenerator` for multi-scenario statistical output
