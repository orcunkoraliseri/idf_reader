# EUI Visualization Implementation

Generate visual breakdown of Energy Use Intensity (EUI) with semantic color coding for different energy demand types.

## Proposed Changes

### bem_utils/read_results.py

#### New Constants: Energy Color Mapping
```python
ENERGY_COLOR_MAP = {
    # Energy gains (warm colors)
    'heating': '#8A1100',       # Dark Red
    'solar': '#A6F956',         # Yellow-Green
    'equipment': '#EF2700',     # Red
    'people': '#FEF401',        # Yellow
    'lighting': '#FF7900',      # Orange
    
    # Energy losses (cool colors)
    'cooling': '#041991',       # Dark Blue
    'infiltration': '#0730E0',  # Blue
    'ventilation': '#0758FF',   # Medium Blue
    'mechanical ventilation': '#01E8FF',  # Cyan
    
    # Conduction (gray-brown tones)
    'conduction': '#806640',    # Brown
    'glazing': '#01E8FF',       # Cyan
}
```

**Color Logic:**
- **Warm colors** → Energy gains (heating, solar, internal gains)
- **Cool colors** → Energy losses (cooling, air exchange)
- **Brown tones** → Envelope conduction

---

#### New Function: `get_energy_color`
```python
def get_energy_color(category_name):
    """
    Returns the appropriate color for an energy category based on semantic mapping.
    """
```
- Case-insensitive matching
- Partial keyword matching (e.g., "Zone Heating" matches "heating")
- Returns `None` for unknown categories (uses default palette)

---

#### New Function: `plot_eui_breakdown`
```python
def plot_eui_breakdown(eui_results, output_path, show_plot=False):
    """
    Generates a bar plot for the EUI breakdown with semantic energy colors.
    Warm colors = energy gains, Cool colors = energy losses.
    """
```

**Features:**
1. **Semantic coloring** - Each bar colored by energy type
2. **Value labels** - Numbers displayed above each bar
3. **Grid lines** - Horizontal grid for readability
4. **Rotated labels** - 45° rotation for long category names
5. **Professional styling** - Bold fonts, clear axis labels

**Plot specifications:**
- Figure size: 12×7 inches
- DPI: 150 (print quality)
- Format: PNG with tight bounding box

---

#### New Function: `visualize_results`
```python
def visualize_results(output_dir):
    """
    Loads the EUI summary JSON and visualizes the results.
    """
```
- Loads previously calculated `eui_summary.json`
- Displays interactive plot (`show_plot=True`)
- Used for reviewing results after processing

---

### main_file.py

#### New Menu Option: Visualize Results
```diff
+ elif choice == '7':
+     # Visualize simulation results
+     results_dirs = list_simulation_results()
+     selected = get_user_selection(results_dirs)
+     read_results.visualize_results(selected)
```

---

## Color Palette Reference

```
┌────────────────────────────────────────────────────┐
│  ENERGY GAINS (Warm)          ENERGY LOSSES (Cool) │
├────────────────────────────────────────────────────┤
│  ████ Heating   (#8A1100)     ████ Cooling (#041991) │
│  ████ Equipment (#EF2700)     ████ Infiltration (#0730E0) │
│  ████ Lighting  (#FF7900)     ████ Ventilation (#0758FF) │
│  ████ People    (#FEF401)     ████ Mech Vent   (#01E8FF) │
│  ████ Solar     (#A6F956)                          │
├────────────────────────────────────────────────────┤
│  ENVELOPE                                          │
│  ████ Conduction (#806640)    ████ Glazing  (#01E8FF) │
└────────────────────────────────────────────────────┘
```

---

## Example Output

The generated plot displays:
- X-axis: End use categories (Heating, Cooling, Lighting, etc.)
- Y-axis: EUI in kWh/m²
- Bar colors: Semantically mapped to energy type
- Labels: Numerical values above each bar

---

## Integration with process_results

The visualization is automatically generated when `process_results()` is called:

```python
def process_results(output_dir):
    # ... EUI calculation ...
    
    # --- 3. Plotting ---
    print("Generating plot...")
    plot_eui_breakdown(eui_results, output_plot, show_plot=False)
```

For interactive viewing, use `visualize_results()` separately.

---

## Dependencies

```python
import matplotlib.pyplot as plt
```

matplotlib is used for all plotting functionality.

---

## Status: IMPLEMENTED

EUI visualization with semantic color coding is complete and integrated.
