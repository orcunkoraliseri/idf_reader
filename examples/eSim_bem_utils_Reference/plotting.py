"""
Plotting module for BEM simulation results.

Provides:
- EUI histogram for comparing multiple households
- Disaggregated energy demand breakdown per simulation
"""
import os
import sqlite3
import json
import matplotlib.pyplot as plt
import pandas as pd
from collections import OrderedDict
from typing import Optional, List, Dict

# Energy category color mapping (semantic colors)
ENERGY_COLOR_MAP = {
    # Energy gains (warm colors)
    'heating': '#8A1100',       # Dark Red
    'heat': '#8A1100',
    'solar': '#A6F956',         # Yellow-Green
    'equipment': '#EF2700',     # Red
    'plug': '#EF2700',
    'people': '#FEF401',        # Yellow
    'occupant': '#FEF401',
    'lighting': '#FF7900',      # Orange
    'light': '#FF7900',
    
    # Energy losses (cool colors)
    'cooling': '#041991',       # Dark Blue
    'cool': '#041991',
    'infiltration': '#0730E0',  # Blue
    'ventilation': '#0758FF',   # Medium Blue
    'vent': '#0758FF',
    'mechanical ventilation': '#01E8FF',  # Cyan
    
    # Conduction (gray-brown tones)
    'conduction': '#806640',    # Brown
    'wall': '#806640',
    'roof': '#806640',
    'floor': '#806640',
    'glazing': '#01E8FF',       # Cyan
    'window': '#01E8FF',
    
    # Other
    'fan': '#9370DB',           # Purple
    'pump': '#9370DB',
    'water': '#00CED1',         # Turquoise
    'dhw': '#00CED1',
}

DEFAULT_PALETTE = [
    '#041991', '#0730E0', '#0758FF', '#01E8FF', '#61F69C',
    '#A6F956', '#FEF401', '#FF7900', '#EF2700', '#8A1100', '#806640'
]

# Readable labels for end-use categories
END_USE_LABELS = {
    'cooling': 'Space Cooling',
    'heating': 'Space Heating',
    'interior lighting': 'Interior Lighting',
    'interior-lights': 'Interior Lighting',
    'exterior lighting': 'Exterior Lighting',
    'exterior-lights': 'Exterior Lighting',
    'garage-lights': 'Garage Lighting',
    'dishwasher': 'Dishwasher',
    'refrigerator': 'Refrigerator',
    'clotheswasher': 'Clothes Washer',
    'gas_dryer': 'Gas Clothes Dryer', 
    'gas_mels': 'Gas Misc Loads',
    'iecc_adj': 'Code Adjustment',
    'ventilation': 'Ventilation',
    'fans': 'HVAC Fans',
    'gas_range': 'Gas Range/Stove',
    'water heater': 'Water Heater',
    'water systems': 'Water Systems',
    'interior equipment': 'Interior Equipment',
    'pumps': 'HVAC Pumps',
}


def get_energy_color(category_name: str) -> Optional[str]:
    """Returns the appropriate color for an energy category."""
    category_lower = category_name.lower()
    for key, color in ENERGY_COLOR_MAP.items():
        if key in category_lower:
            return color
    return None


def get_tabular_data(conn, table_name: str) -> pd.DataFrame:
    """Retrieves tabular data for a specific table name."""
    query = """
    SELECT TableName, RowName, ColumnName, Units, Value
    FROM TabularDataWithStrings
    WHERE TableName = ?
    """
    return pd.read_sql_query(query, conn, params=(table_name,))


def calculate_eui(conn) -> dict:
    """
    Calculates EUI, Total Floor Area, and End Uses from SQL connection.
    
    Returns:
        dict: Results including EUI, floor area, and disaggregated end uses.
    """
    results = {
        'eui': 0.0,
        'total_floor_area': 0.0,
        'conditioned_floor_area': 0.0,
        'total_energy': 0.0,
        'end_uses': {},
        'end_uses_normalized': {}
    }

    # 1. Get Building Areas
    area_df = get_tabular_data(conn, 'Building Area')
    if not area_df.empty:
        for _, row in area_df.iterrows():
            try:
                val = float(row['Value'])
                units = row.get('Units', '')
                
                # Convert ft² to m² if needed (1 ft² = 0.092903 m²)
                if units == 'ft2' or units == 'ft²':
                    val = val * 0.092903
                
                if row['RowName'] == 'Total Building Area':
                    results['total_floor_area'] = val
                elif row['RowName'] == 'Net Conditioned Building Area':
                    results['conditioned_floor_area'] = val
            except ValueError:
                continue

    # 2. Get End Uses
    query = """
    SELECT TableName, RowName, ColumnName, Units, Value
    FROM TabularDataWithStrings
    WHERE TableName = ? OR TableName = ?
    """
    df = pd.read_sql_query(query, conn, 
                           params=('End Uses By Subcategory', 'End Uses'))
    
    target_table = 'End Uses By Subcategory'
    subset = df[df['TableName'] == target_table]
    if subset.empty:
        target_table = 'End Uses'
        subset = df[df['TableName'] == target_table]

    total_energy = 0.0
    end_uses = OrderedDict()

    for _, row in subset.iterrows():
        row_name = row['RowName']
        col_name = row['ColumnName']
        units = row['Units']
        val_str = row['Value']
        
        # Skip water columns
        if 'Water' in col_name or 'm3' in str(units):
            continue
            
        try:
            val = float(val_str)
        except ValueError:
            continue
            
        # Convert to kWh (E+ tabular data is in GJ)
        if units == 'GJ':
            val_kwh = val * 277.778
        elif units == 'kWh':
            val_kwh = val
        elif units == 'J':
            val_kwh = val / 3600000.0
        elif units == 'kBtu':
            # 1 kBtu = 0.293071 kWh
            val_kwh = val * 0.293071
        elif units == 'Btu':
            # 1 Btu = 0.000293071 kWh
            val_kwh = val * 0.000293071
        elif units == 'MJ':
            # 1 MJ = 0.277778 kWh
            val_kwh = val * 0.277778
        else:
            # Unknown unit - skip or assume kWh
            val_kwh = val

        if val_kwh != 0:
            total_energy += val_kwh
            
            # Parse category
            if ':' in row_name:
                parts = row_name.split(':')
                cat = parts[0].strip()
                sub_cat = parts[1].strip() if len(parts) > 1 else ''
                if sub_cat in ['General', 'Other', '']:
                    eu_cat = cat
                else:
                    eu_cat = sub_cat
            else:
                eu_cat = row_name
            
            if eu_cat not in end_uses:
                end_uses[eu_cat] = 0.0
            end_uses[eu_cat] += val_kwh

    results['total_energy'] = round(total_energy, 3)
    results['end_uses'] = {k: round(v, 3) for k, v in end_uses.items()}
    
    # Use conditioned floor area for EUI (more accurate), fallback to total
    area_for_eui = results['conditioned_floor_area'] or results['total_floor_area']
    
    if area_for_eui > 0:
        results['eui'] = round(total_energy / area_for_eui, 3)
        results['end_uses_normalized'] = {
            k: round(v / area_for_eui, 3) 
            for k, v in end_uses.items()
        }
    
    return results


def scale_eui_results(results: dict, factor: float) -> dict:
    """
    Scales energy values in EUI results dictionary by a factor.
    Used for upscaling partial year simulations (e.g. 24 weeks -> 52 weeks).
    """
    if factor == 1.0:
        return results
        
    scaled = results.copy()
    scaled['eui'] = round(results['eui'] * factor, 3)
    scaled['total_energy'] = round(results['total_energy'] * factor, 3)
    
    scaled['end_uses'] = {k: round(v * factor, 3) for k, v in results['end_uses'].items()}
    scaled['end_uses_normalized'] = {k: round(v * factor, 3) for k, v in results['end_uses_normalized'].items()}
    
    return scaled


def scale_meter_results(meter_results: Dict[str, List[float]], factor: float) -> Dict[str, List[float]]:
    """
    Scales extracted meter data values by a factor.
    
    For weekly mode (24 periods), aggregates to 12 monthly values and scales
    to estimate full-year equivalent monthly totals.
    
    NOTE: Data is kept as monthly totals - daily normalization happens in plotting.
    """
    if factor == 1.0:
        return meter_results
        
    scaled = {}
    for key, values in meter_results.items():
        # Handle Weekly mode (24 items) -> Convert to Monthly (12 items)
        # Weekly mode produces 24 periods (2 per month). Sum to get monthly total.
        if len(values) == 24:
            aggregated = []
            for i in range(12):
                # Sum the two periods for this month (each is ~14 days)
                month_val = values[i*2] + values[i*2+1]
                aggregated.append(month_val)
            
            # Scale by factor (52/24) to estimate full-year monthly totals
            # The 14-day periods already captured the pattern - just extrapolate
            scaled[key] = [val * factor for val in aggregated]
        else:
            # Standard mode (12 items) - scale as-is
            scaled[key] = [v * factor for v in values]
    return scaled


def plot_eui_breakdown(eui_results: dict, output_path: str) -> None:
    """
    Generates a bar plot for the EUI breakdown with semantic energy colors.
    
    Args:
        eui_results: Dictionary from calculate_eui().
        output_path: Path to save the plot.
    """
    end_uses = eui_results.get('end_uses_normalized', {})
    if not end_uses:
        print("No end use data to plot.")
        return

    labels = list(end_uses.keys())
    values = list(end_uses.values())
    
    # Map labels to readable names
    display_labels = []
    for label in labels:
        mapped = END_USE_LABELS.get(label.lower(), label)
        display_labels.append(mapped)
    
    # Assign colors (use original labels for color matching)
    colors = []
    default_idx = 0
    for label in labels:
        color = get_energy_color(label)
        if color:
            colors.append(color)
        else:
            colors.append(DEFAULT_PALETTE[default_idx % len(DEFAULT_PALETTE)])
            default_idx += 1

    fig, ax = plt.subplots(figsize=(14, 7))
    bars = ax.bar(display_labels, values, color=colors, edgecolor='black', linewidth=0.5)
    
    ax.set_xlabel('End Use Category', fontsize=12, fontweight='bold')
    ax.set_ylabel('EUI (kWh/m²)', fontsize=12, fontweight='bold')
    plt.title(f"Monte Carlo Comparison (N={{K}}) - {{region_str}}\n{{idf_str}}", fontsize=14)
    
    # Add value labels on bars
    for bar, value in zip(bars, values):
        height = bar.get_height()
        ax.annotate(f'{value:.1f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9)
    
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Plot saved to {output_path}")
    plt.close()


def process_single_result(output_dir: str, plot_output_dir: str = None, scaling_factor: float = 1.0) -> dict:
    """
    Processes a single simulation result directory.
    
    Args:
        output_dir: Path to directory containing eplusout.sql.
        plot_output_dir: Optional path to save plots. Uses output_dir if not specified.
        scaling_factor: Factor to scale results (e.g. 52/24 for weekly sim).
    
    Returns:
        dict: EUI results dictionary.
    """
    sql_path = os.path.join(output_dir, 'eplusout.sql')
    if not os.path.exists(sql_path):
        print(f"SQL file not found: {sql_path}")
        return {}
    
    if plot_output_dir is None:
        plot_output_dir = output_dir
    
    if not os.path.exists(plot_output_dir):
        os.makedirs(plot_output_dir)
    
    try:
        conn = sqlite3.connect(sql_path)
        eui_results = calculate_eui(conn)
        conn.close()
        
        # Scale if needed
        eui_results = scale_eui_results(eui_results, scaling_factor)
        
        # Save JSON summary
        json_path = os.path.join(output_dir, 'eui_summary.json')
        with open(json_path, 'w') as f:
            json.dump(eui_results, f, indent=4)
        
        # Generate breakdown plot
        sim_name = os.path.basename(output_dir)
        plot_path = os.path.join(plot_output_dir, f"{sim_name}_eui_breakdown.png")
        plot_eui_breakdown(eui_results, plot_path)
        
        return eui_results
        
    except Exception as e:
        print(f"Error processing {output_dir}: {e}")
        return {}


def plot_eui_histogram(simulation_results: list, title: str = "EUI Distribution", 
                       output_dir: str = None, scaling_factor: float = 1.0) -> None:
    """
    Plots a histogram of EUI results from multiple simulations.
    Also generates individual breakdown plots for each simulation.
    
    Args:
        simulation_results: List of dicts with 'output_dir' key.
        title: Title for the histogram.
        output_dir: Directory to save plots.
    """
    eui_values = []
    
    print("\nProcessing simulation results...")
    
    for res in simulation_results:
        res_output_dir = res.get('output_dir')
        if not res_output_dir:
            continue
        
        # Process each result to get EUI and generate breakdown
        eui_result = process_single_result(res_output_dir, output_dir, scaling_factor=scaling_factor)
        if eui_result and eui_result.get('eui', 0) > 0:
            eui_values.append(eui_result['eui'])
            
    if not eui_values:
        print("No valid EUI data found to plot.")
        return
    
    # If only 1 result, a histogram is meaningless. 
    # The user prefers the disaggregated plot (which is already generated per-sim).
    if len(eui_values) == 1:
        print("\nSingle simulation found. Skipping histogram.")
        print("Please check the disaggregated breakdown plot generated above.")
        return

    # Generate histogram for multiple results
    plt.figure(figsize=(10, 6))
    plt.hist(eui_values, bins=min(20, len(eui_values)), 
             color='skyblue', edgecolor='black')
    plt.title(title.replace('_', ' '))
    plt.xlabel('EUI (kWh/m²)')
    plt.ylabel('Number of Households')
    
    # Force integer ticks on y-axis
    from matplotlib.ticker import MaxNLocator
    plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True))
    
    plt.grid(True, alpha=0.3)
    
    # Add statistics
    if len(eui_values) > 1:
        mean_eui = sum(eui_values) / len(eui_values)
        plt.axvline(mean_eui, color='red', linestyle='--', 
                   label=f'Mean: {mean_eui:.1f} kWh/m²')
        plt.legend()
    
    # Save
    filename = f"{title.replace(' ', '_')}_histogram.png"
    if output_dir:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_file = os.path.join(output_dir, filename)
    else:
        output_file = filename
    
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Histogram saved to {output_file}")
    plt.close()
    
    print(f"Also generated {len(eui_values)} individual disaggregated plots in {output_dir}")


def plot_comparative_eui(
    results_dict: Dict[str, dict],
    hh_id: str,
    output_dir: Optional[str] = None,
    region: Optional[str] = None,
    idf_name: Optional[str] = None
) -> None:
    """
    Generates a grouped bar chart comparing EUI across scenarios.
    
    Args:
        results_dict: Dict mapping scenario name to result dict (from calculate_eui).
        hh_id: Household ID or Building Name for labeling.
        output_dir: Directory to save the plot.
        region: Region name to include in title (optional).
        idf_name: IDF filename to include in title (optional).
    """
    if not results_dict:
        print("No results to plot.")
        return
    
    # Collect all unique end-use categories across all scenarios
    all_categories = set()
    for scenario_name, data in results_dict.items():
        if 'end_uses_normalized' in data:
            all_categories.update(data['end_uses_normalized'].keys())
    
    # Sort categories for consistent ordering
    categories = sorted(list(all_categories))
    
    # Map to readable labels
    display_categories = [END_USE_LABELS.get(c.lower(), c) for c in categories]
    
    # Prepare data for each scenario
    scenario_names = list(results_dict.keys())
    scenario_colors = ['#041991', '#0758FF', '#A6F956', '#8A1100']  # Blue to Red gradient
    
    # Build data matrix
    import numpy as np
    x = np.arange(len(categories))
    width = 0.2  # Bar width
    
    fig, ax = plt.subplots(figsize=(16, 8))
    
    for i, scenario_name in enumerate(scenario_names):
        data = results_dict.get(scenario_name, {})
        end_uses = data.get('end_uses_normalized', {})
        
        values = [end_uses.get(cat, 0) for cat in categories]
        offset = (i - len(scenario_names) / 2 + 0.5) * width
        
        bars = ax.bar(x + offset, values, width, label=scenario_name, 
                     color=scenario_colors[i % len(scenario_colors)],
                     edgecolor='black', linewidth=0.5)
    
    ax.set_xlabel('End Use Category', fontsize=12, fontweight='bold')
    ax.set_ylabel('EUI (kWh/m²)', fontsize=12, fontweight='bold')
    
    title = f"Comparative End-Use Intensity (EUI) - {hh_id}"
    if idf_name:
        title += f"\nModel: {idf_name}"
    if region:
        title += f" | Region: {region}"
    
    plt.title(title, fontsize=11, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(display_categories, rotation=45, ha='right', fontsize=8)
    ax.legend(title='Scenario', loc='upper right')
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    
    # Save with timestamp to avoid overwrites
    import time
    timestamp = int(time.time())
    filename = f"Comparative_Summary_HH_{hh_id}_{timestamp}.png"
    if output_dir:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_file = os.path.join(output_dir, filename)
    else:
        output_file = filename
    
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Comparative plot saved to {output_file}")
    plt.close()


def get_meter_data(conn) -> Dict[str, List[float]]:
    """
    Retrieves monthly meter data for key energy categories.
    
    Returns:
        Dict[meter_name, list_of_12_monthly_values_in_kWh]
    """
    # 1. Get ReportDataDictionary IDs for our target meters (Monthly)
    # We look for ReportingFrequency=Monthly (check numeric code if needed, usually 5 or similar string)
    # Actually, SQL output stores string 'Monthly' in ReportingFrequency for tabular, 
    # but for time series it uses integers in ReportDataDictionary.ReportingFrequency
    # Month=5
    
    query_meta = """
    SELECT ReportDataDictionaryIndex, KeyValue, Name, Units 
    FROM ReportDataDictionary 
    WHERE ReportingFrequency = 5 OR ReportingFrequency = 'Monthly'
    """
    
    try:
        meta_df = pd.read_sql_query(query_meta, conn)
    except Exception as e:
        print(f"Error querying dictionary: {e}")
        return {}
    
    # Map Index -> Name
    index_map = {}
    for _, row in meta_df.iterrows():
        # Name format usually 'MeterName'
        name = row['Name']
        units = row['Units']
        index_map[row['ReportDataDictionaryIndex']] = (name, units)
        
    if not index_map:
        return {}
        
    # 2. Get Data
    # Month indices are typically 1-12 in TimeIndex (or we can just order by time)
    # We want 12 values per meter
    
    query_data = """
    SELECT rd.ReportDataDictionaryIndex, rd.Value
    FROM ReportData rd
    JOIN Time t ON rd.TimeIndex = t.TimeIndex
    JOIN EnvironmentPeriods ep ON t.EnvironmentPeriodIndex = ep.EnvironmentPeriodIndex
    WHERE ep.EnvironmentType = 3
    ORDER BY t.TimeIndex ASC
    """
    
    data_df = pd.read_sql_query(query_data, conn)
    
    results = {}
    
    for idx, (name, units) in index_map.items():
        # Filter for this meter
        subset = data_df[data_df['ReportDataDictionaryIndex'] == idx]
        values = subset['Value'].tolist()
        
        # We expect 12 values for annual monthly simulation
        # If run period is partial, we take what we get
        
        # Convert units to kWh
        # Meters usually in J or kWh directly
        converted_values = []
        for v in values:
            if units == 'J':
                converted_values.append(v / 3600000.0)
            elif units == 'GJ':
                converted_values.append(v * 277.778)
            elif units == 'kBtu':
                converted_values.append(v * 0.293071)
            else:
                converted_values.append(v) # Assume kWh or similar
        
        results[name] = converted_values
        
    return results


def get_hourly_meter_data(conn) -> Dict[str, List[float]]:
    """
    Retrieves HOURLY meter data for key energy categories.

    Returns:
        Dict[meter_name, list_of_8760_values_in_J]
    """
    # ReportingFrequency: 3 = Hourly (numeric) OR 'Hourly' (string)
    query_meta = """
    SELECT ReportDataDictionaryIndex, KeyValue, Name, Units
    FROM ReportDataDictionary
    WHERE ReportingFrequency = 3 OR ReportingFrequency = 'Hourly'
    """
    
    try:
        meta_df = pd.read_sql_query(query_meta, conn)
    except Exception as e:
        return {}
    
    index_map = {}
    for _, row in meta_df.iterrows():
        name = row['Name']
        units = row['Units']
        # Filter for relevant meters to save memory
        if any(x in name for x in ['EnergyTransfer', 'Electricity', 'WaterSystems']):
             index_map[row['ReportDataDictionaryIndex']] = (name, units)

    if not index_map:
        return {}

    query_data = """
    SELECT rd.ReportDataDictionaryIndex, rd.Value
    FROM ReportData rd
    JOIN Time t ON rd.TimeIndex = t.TimeIndex
    JOIN EnvironmentPeriods ep ON t.EnvironmentPeriodIndex = ep.EnvironmentPeriodIndex
    WHERE ep.EnvironmentType = 3
    ORDER BY t.TimeIndex ASC
    """
    
    data_df = pd.read_sql_query(query_data, conn)
    
    results = {}
    for idx, (name, units) in index_map.items():
        subset = data_df[data_df['ReportDataDictionaryIndex'] == idx]
        values = subset['Value'].tolist()
        
        # Keep in Joules (W*3600s) or Watts? 
        # Usually Hourly data is Energy (J) or Power (W). E+ reports Energy in J usually.
        # We'll return raw extracted values (likely J) and convert in reporting.
        results[name] = values
        
    return results

def plot_comparative_timeseries_subplots(
    results_dict: Dict[str, dict],
    hh_id: str,
    output_dir: Optional[str] = None,
    floor_area: float = 0.0,
    region: Optional[str] = None,
    idf_name: Optional[str] = None,
    sim_mode: str = 'standard'
) -> None:
    """
    Generates a figure with subplots (one per meter) comparing scenario traces.
    
    Args:
        results_dict: Dict mapping scenario name to meter data dict.
        hh_id: Household ID for labeling.
        output_dir: Directory to save the plot.
        floor_area: Conditioned floor area in m2 for normalization (optional).
        region: Region name for title (optional).
        idf_name: IDF filename for title (optional).
        sim_mode: Simulation mode ('standard' or 'weekly'). Weekly mode skips
                  daily normalization to avoid sawtooth pattern from sample data.
    """
    if not results_dict:
        return
        
    # Identifying common meters
    first_scenario = list(results_dict.keys())[0]
    meters = list(results_dict[first_scenario].keys())
    
    # Filter for interesting meters only
    interesting_meters = [
        'Heating:EnergyTransfer', 'Cooling:EnergyTransfer',
        'InteriorLights:Electricity', 'InteriorEquipment:Electricity', 
        'InteriorEquipment:Gas', 'Fans:Electricity', 'WaterSystems:EnergyTransfer'
    ]
    
    display_meters = [m for m in meters if m in interesting_meters]
    if not display_meters:
        # Fallback to whatever is available if exact matches fail
        display_meters = meters[:9] # Max 9
        
    n_plots = len(display_meters)
    if n_plots == 0:
        print("No meter data found to plot.")
        return
        
    # Setup subplots (3 columns grid)
    cols = 3
    rows = (n_plots + cols - 1) // cols
    
    fig, axes = plt.subplots(rows, cols, figsize=(15, 4 * rows))
    axes = axes.flatten()
    
    # Colors (consistent with bar chart)
    scenario_colors = {
        '2025': '#041991', '2015': '#0758FF', 
        '2005': '#A6F956', 'Default': '#8A1100'
    }
    
    months = range(1, 13)
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # Days per month (using 2024 leap year for consistency with EnergyPlus)
    days_per_month = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    
    # Determine unit label based on simulation mode
    # Weekly mode: skip daily normalization to avoid sawtooth (data represents sample periods)
    # Standard mode: normalize to daily average
    use_daily_norm = (sim_mode != 'weekly')
    if use_daily_norm:
        y_unit = 'kWh/m²/day' if floor_area > 0 else 'kWh/day'
    else:
        y_unit = 'kWh/m²/month' if floor_area > 0 else 'kWh/month'
    
    for i, meter in enumerate(display_meters):
        ax = axes[i]
        
        for scenario_name, data in results_dict.items():
            values = data.get(meter, [])
            # Pad or truncate to 12
            if len(values) > 12: values = values[:12]
            if len(values) < 12: values = values + [0]*(12-len(values))
            
            # Normalize by days per month to get daily average (only for standard mode)
            if use_daily_norm:
                values = [v / days for v, days in zip(values, days_per_month)]
            
            # Normalize if floor area is provided
            if floor_area > 0:
                values = [v / floor_area for v in values]
            
            color = scenario_colors.get(scenario_name, 'gray')
            ax.plot(months, values, marker='o', markersize=4, 
                   linewidth=2, label=scenario_name, color=color, alpha=0.8)
            
        ax.set_title(meter.replace(':', ' - ').replace('EnergyTransfer', 'Energy Demand'), fontsize=10, fontweight='bold')
        ax.set_ylabel(y_unit, fontsize=9)
        ax.set_xticks(months)
        ax.set_xticklabels(month_labels, rotation=45, fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # Expand y-axis for lighting and equipment to avoid exaggerated visual differences
        # Set y-axis to start at 0 and expand range by 20% above max
        # Enforce y-axis starting at 0 for all plots (User Request)
        ax.set_ylim(bottom=0)

        # Expand y-axis for lighting and equipment to avoid exaggerated visual differences
        if 'InteriorLights' in meter or 'InteriorEquipment' in meter:
            current_ylim = ax.get_ylim()
            ax.set_ylim(bottom=0, top=current_ylim[1] * 1.2)
        
        # Legend only on first plot to save space
        if i == 0:
            ax.legend()
            
    # Hide empty subplots
    for i in range(n_plots, len(axes)):
        axes[i].axis('off')
        
    plt.tight_layout()
    plt.subplots_adjust(top=0.92)
    
    title_str = f'Comparative Annual Time-Series (kWh/m²/day) - {hh_id}'
    if idf_name:
        title_str += f"\nModel: {idf_name}"
    if region:
        title_str += f" | Region: {region}"
        
    fig.suptitle(title_str, fontsize=11, fontweight='bold')
    
    # Save with timestamp to avoid overwrites
    import time
    timestamp = int(time.time())
    filename = f"Comparative_TimeSeries_HH_{hh_id}_{timestamp}.png"
    if output_dir:
        output_file = os.path.join(output_dir, filename)
    else:
        output_file = filename
        
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Time-series plot saved to {output_file}")
    plt.close()


def plot_kfold_comparative_eui(
    aggregated: dict,
    categories: list,
    output_path: str,
    K: int = 5,
    region: Optional[str] = None,
    idf_name: Optional[str] = None
) -> None:
    """
    Generates a grouped bar chart with error bars for Monte Carlo simulation results.
    
    Args:
        aggregated: Dict with 'mean' and 'std' sub-dicts, each scenario -> category -> value.
        categories: List of end-use category names.
        output_path: Path to save the plot.
        K: Number of iterations (for title).
        region: Region name for title.
        idf_name: IDF filename for title.
    """
    import numpy as np
    
    scenarios = list(aggregated['mean'].keys())
    n_categories = len(categories)
    n_scenarios = len(scenarios)
    
    if n_categories == 0 or n_scenarios == 0:
        print("Warning: No data to plot for Monte Carlo results.")
        return
    
    # Color mapping for scenarios
    scenario_colors = {
        '2025': '#041991',  # Dark Blue
        '2015': '#0758FF',  # Blue
        '2005': '#61F69C',  # Green
        'Default': '#8A1100' # Red
    }
    
    # Prepare data
    x = np.arange(n_categories)
    bar_width = 0.2
    
    fig, ax = plt.subplots(figsize=(14, 7))
    
    for idx, scenario in enumerate(scenarios):
        means = [aggregated['mean'].get(scenario, {}).get(cat, 0.0) for cat in categories]
        stds = [aggregated['std'].get(scenario, {}).get(cat, 0.0) for cat in categories]
        
        offset = (idx - (n_scenarios - 1) / 2) * bar_width
        color = scenario_colors.get(scenario, DEFAULT_PALETTE[idx % len(DEFAULT_PALETTE)])
        
        ax.bar(
            x + offset, means, bar_width,
            yerr=stds, capsize=3,
            label=scenario, color=color, alpha=0.85
        )
    
    # Formatting
    ax.set_xlabel('End Use Category', fontsize=12)
    ax.set_ylabel('EUI (kWh/m²)', fontsize=12)
    
    # Create labels with END_USE_LABELS mapping
    x_labels = [END_USE_LABELS.get(cat.lower().replace('_', ' '), cat) for cat in categories]
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=9)
    
    # Title
    title_parts = [f"Monte Carlo Comparative EUI (N={K})"]
    if idf_name:
        title_parts.append(f"Model: {idf_name}")
    if region:
        title_parts.append(f"Region: {region}")
    ax.set_title(" | ".join(title_parts), fontsize=12)

    ax.legend(title="Scenario", loc='upper right')
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Monte Carlo EUI plot saved to {output_path}")
    plt.close()


def plot_kfold_timeseries(
    aggregated_meters: dict,
    meter_names: list,
    output_path: str,
    floor_area: float = 0.0,
    K: int = 5,
    region: Optional[str] = None,
    idf_name: Optional[str] = None,
    sim_mode: str = 'standard'
) -> None:
    """
    Generates multi-panel time-series plots for Monte Carlo results with mean ± std shading.
    
    Args:
        aggregated_meters: Dict with 'mean' and 'std' sub-dicts.
        meter_names: List of meter names to plot.
        output_path: Path to save the plot.
        floor_area: Floor area for normalization (m²).
        K: Number of iterations.
        region: Region name for title.
        idf_name: IDF filename for title.
        sim_mode: Simulation mode ('standard' or 'weekly'). Weekly mode skips
                  daily normalization to avoid sawtooth pattern from sample data.
    """
    import numpy as np
    
    scenarios = list(aggregated_meters['mean'].keys())
    
    # Select key meters to display (limit to 6 for readability)
    key_meters = [
        'InteriorLights:Electricity',
        'InteriorEquipment:Electricity',
        'Fans:Electricity',
        'Heating:EnergyTransfer',
        'Cooling:EnergyTransfer',
        'WaterSystems:EnergyTransfer'
    ]
    meters_to_plot = [m for m in key_meters if m in meter_names]
    if not meters_to_plot:
        meters_to_plot = meter_names[:6]
    
    n_meters = len(meters_to_plot)
    if n_meters == 0:
        print("Warning: No meter data to plot for Monte Carlo time-series.")
        return
    
    # Layout
    n_cols = 3
    n_rows = (n_meters + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(14, 4 * n_rows), squeeze=False)
    
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    x = np.arange(12)
    
    # Days per month (using 2024 leap year for consistency with EnergyPlus)
    days_per_month = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    
    scenario_colors = {
        '2025': '#041991',
        '2015': '#0758FF',
        '2005': '#61F69C',
        'Default': '#8A1100'
    }
    
    # Determine unit label based on simulation mode
    use_daily_norm = (sim_mode != 'weekly')
    if use_daily_norm:
        y_unit = 'kWh/m²/day' if floor_area > 0 else 'kWh/day'
    else:
        y_unit = 'kWh/m²/month' if floor_area > 0 else 'kWh/month'
    
    for idx, meter in enumerate(meters_to_plot):
        row, col = divmod(idx, n_cols)
        ax = axes[row, col]
        
        for scenario in scenarios:
            mean_vals = aggregated_meters['mean'].get(scenario, {}).get(meter, [0]*12)
            std_vals = aggregated_meters['std'].get(scenario, {}).get(meter, [0]*12)
            
            # Normalize by days per month to get daily average (only for standard mode)
            if use_daily_norm:
                mean_vals = [v / days for v, days in zip(mean_vals, days_per_month)]
                std_vals = [v / days for v, days in zip(std_vals, days_per_month)]
            
            # Normalize by floor area (data is already in kWh from get_meter_data)
            if floor_area > 0:
                mean_vals = [v / floor_area for v in mean_vals]
                std_vals = [v / floor_area for v in std_vals]
            
            color = scenario_colors.get(scenario, '#666666')
            
            # Plot mean line
            ax.plot(x, mean_vals, '-o', markersize=3, label=scenario, color=color)
            
            # Plot std shading
            lower = [max(0, m - s) for m, s in zip(mean_vals, std_vals)]
            upper = [m + s for m, s in zip(mean_vals, std_vals)]
            ax.fill_between(x, lower, upper, alpha=0.15, color=color)
        
        # Format subplot
        meter_label = meter.replace(':Electricity', ' - Electricity').replace(':EnergyTransfer', ' - Energy Demand')
        ax.set_title(meter_label, fontsize=10)
        ax.set_xticks(x)
        ax.set_xticklabels(months, fontsize=8, rotation=45)
        ax.set_ylabel(y_unit, fontsize=9)
        ax.grid(alpha=0.3)
        
        # Enforce y-axis starting at 0 for all plots (User Request)
        ax.set_ylim(bottom=0)
        
        # Expand y-axis for lighting and equipment to avoid exaggerated visual differences
        # (Optional: could apply to all, but keeping specific logic for these flat profiles)
        if 'InteriorLights' in meter or 'InteriorEquipment' in meter:
            current_ylim = ax.get_ylim()
            ax.set_ylim(bottom=0, top=current_ylim[1] * 1.2)
        
        if idx == 0:
            ax.legend(fontsize=8, loc='upper right')
    
    # Hide empty subplots
    for idx in range(n_meters, n_rows * n_cols):
        row, col = divmod(idx, n_cols)
        axes[row, col].axis('off')
    
    # Title
    title_parts = [f"Monte Carlo Time-Series (N={K})"]
    if idf_name:
        title_parts.append(f"Model: {idf_name}")
    if region:
        title_parts.append(f"Region: {region}")
    fig.suptitle(" | ".join(title_parts), fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.subplots_adjust(top=0.92)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Monte Carlo time-series plot saved to {output_path}")
    plt.close()


def plot_validation_comparison(
    sim_eui: float, 
    ref_eui: float, 
    output_dir: str, 
    model_name: str, 
    zone: str
) -> None:
    """
    Plots a comparison bar chart between Simulated EUI and Reference EUI.
    
    Args:
        sim_eui: Simulated Energy Use Intensity.
        ref_eui: IECC Reference EUI.
        output_dir: Directory to save the plot.
        model_name: Name of the model (for title/filename).
        zone: Climate Zone (for context).
    """
    import numpy as np
    
    # Data
    labels = ['Simulated', 'Reference (IECC 2021)']
    values = [sim_eui, ref_eui]
    colors = ['#1f77b4', '#ff7f0e'] # Blue, Orange
    
    fig, ax = plt.subplots(figsize=(8, 6))
    bars = ax.bar(labels, values, color=colors, width=0.5)
    
    # Add values on top of bars
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.2f}\nkWh/m²',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    # Calculate difference
    if ref_eui > 0:
        diff_pct = (sim_eui - ref_eui) / ref_eui * 100
        diff_text = f"Difference: {diff_pct:+.1f}%"
        title_color = 'green' if abs(diff_pct) < 10 else 'red'
    else:
        diff_text = "Reference Not Available"
        title_color = 'black'
        
    ax.set_title(f"Validation Result: {model_name} (Zone {zone})\n{diff_text}", fontsize=14, color=title_color)
    ax.set_ylabel('EUI (kWh/m²)')
    ax.set_ylim(0, max(values) * 1.2) # Add headroom
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Note
    plt.tight_layout()
    
    # Save
    filename = f"Validation_Comparison_{model_name}.png"
    filepath = os.path.join(output_dir, filename)
    plt.savefig(filepath, dpi=300)
    plt.close()
    print(f"    [PLOT] Validation comparison saved: {filename}")

