"""
plotting.py — SQL Results Extraction & Visualization (Phases 4 + 5).

Provides:
- get_tabular_data()        Query TabularDataWithStrings by table name
- calculate_eui()           Extract EUI, floor area, end-uses from SQL
- process_single_result()   Orchestrator: SQL → JSON + PNG
- plot_eui_breakdown()      Semantic-color bar chart of end-use EUI
- get_meter_data()          Monthly meter data from ReportData table
- get_hourly_meter_data()   Hourly meter data from ReportData table
"""
import os
import sqlite3
import json
import matplotlib.pyplot as plt
import pandas as pd
from collections import OrderedDict
from typing import Optional, List, Dict

# ---------------------------------------------------------------------------
# Semantic color map for energy end-use categories
# ---------------------------------------------------------------------------
ENERGY_COLOR_MAP = {
    'heating':      '#8A1100',  # Dark Red
    'heat':         '#8A1100',
    'cooling':      '#041991',  # Dark Blue
    'cool':         '#041991',
    'lighting':     '#FF7900',  # Orange
    'light':        '#FF7900',
    'equipment':    '#EF2700',  # Red
    'plug':         '#EF2700',
    'fan':          '#9370DB',  # Purple
    'pump':         '#9370DB',
    'water':        '#00CED1',  # Turquoise
    'dhw':          '#00CED1',
    'people':       '#FEF401',  # Yellow
    'solar':        '#A6F956',  # Yellow-Green
    'infiltration': '#0730E0',  # Blue
    'ventilation':  '#0758FF',  # Medium Blue
}

DEFAULT_PALETTE = [
    '#041991', '#0730E0', '#0758FF', '#01E8FF',
    '#A6F956', '#FEF401', '#FF7900', '#EF2700', '#8A1100',
]

# Human-readable display labels for end-use categories
END_USE_LABELS = {
    'heating':            'Space Heating',
    'cooling':            'Space Cooling',
    'interior lighting':  'Interior Lighting',
    'interior equipment': 'Interior Equipment',
    'fans':               'HVAC Fans',
    'pumps':              'HVAC Pumps',
    'water systems':      'Water Systems',
    'exterior lighting':  'Exterior Lighting',
    'heat rejection':     'Heat Rejection',
    'humidification':     'Humidification',
    'refrigeration':      'Refrigeration',
    'generators':         'Generators',
}


# ---------------------------------------------------------------------------
# SQL query helpers
# ---------------------------------------------------------------------------

def get_tabular_data(conn, table_name: str) -> pd.DataFrame:
    """Retrieves all rows from TabularDataWithStrings for a given table name."""
    query = """
    SELECT TableName, RowName, ColumnName, Units, Value
    FROM TabularDataWithStrings
    WHERE TableName = ?
    """
    return pd.read_sql_query(query, conn, params=(table_name,))


# ---------------------------------------------------------------------------
# EUI calculation (Phase 4)
# ---------------------------------------------------------------------------

def calculate_eui(conn) -> dict:
    """
    Calculates EUI, floor area, and disaggregated end-uses from an open SQL connection.

    Data flow:
      TabularDataWithStrings['Building Area']              → floor areas (m²)
      TabularDataWithStrings['End Uses By Subcategory']   → energy per end-use (GJ → kWh)
      Fallback: TabularDataWithStrings['End Uses']         if subcategory table is empty

    Returns:
        {
          'eui': float,                    # kWh/m²  (total / conditioned area)
          'total_floor_area': float,       # m²
          'conditioned_floor_area': float, # m²
          'total_energy': float,           # kWh
          'end_uses': dict,                # category → absolute kWh
          'end_uses_normalized': dict,     # category → kWh/m²
        }
    """
    results = {
        'eui': 0.0,
        'total_floor_area': 0.0,
        'conditioned_floor_area': 0.0,
        'total_energy': 0.0,
        'end_uses': {},
        'end_uses_normalized': {},
    }

    # --- 1. Floor areas ---
    area_df = get_tabular_data(conn, 'Building Area')
    if not area_df.empty:
        for _, row in area_df.iterrows():
            try:
                val = float(row['Value'])
            except ValueError:
                continue
            units = row.get('Units', '')
            # Convert ft² → m² for US-origin IDFs
            if units in ('ft2', 'ft²'):
                val = val * 0.092903
            if row['RowName'] == 'Total Building Area':
                results['total_floor_area'] = val
            elif row['RowName'] == 'Net Conditioned Building Area':
                results['conditioned_floor_area'] = val

    # --- 2. End-use energy ---
    query = """
    SELECT TableName, RowName, ColumnName, Units, Value
    FROM TabularDataWithStrings
    WHERE TableName = ? OR TableName = ?
    """
    df = pd.read_sql_query(query, conn,
                           params=('End Uses By Subcategory', 'End Uses'))

    # Prefer subcategory table; fall back to aggregate table for older IDFs
    target = 'End Uses By Subcategory'
    subset = df[df['TableName'] == target]
    if subset.empty:
        target = 'End Uses'
        subset = df[df['TableName'] == target]

    total_energy = 0.0
    end_uses = OrderedDict()

    for _, row in subset.iterrows():
        row_name = row['RowName']
        col_name = row['ColumnName']
        units = row['Units']
        val_str = row['Value']

        # Skip water-volume columns (m³)
        if 'Water' in col_name or 'm3' in str(units):
            continue

        try:
            val = float(val_str)
        except ValueError:
            continue

        # Unit conversion → kWh
        if units == 'GJ':
            val_kwh = val * 277.778      # Primary E+ tabular unit
        elif units == 'kWh':
            val_kwh = val
        elif units == 'J':
            val_kwh = val / 3_600_000
        elif units == 'kBtu':
            val_kwh = val * 0.293071
        elif units == 'Btu':
            val_kwh = val * 0.000293071
        elif units == 'MJ':
            val_kwh = val * 0.277778
        else:
            val_kwh = val  # unknown unit — pass through

        if val_kwh == 0:
            continue

        total_energy += val_kwh

        # Parse category name
        if ':' in row_name:
            cat, sub = row_name.split(':', 1)
            eu_cat = cat.strip() if sub.strip() in ('General', 'Other', '') else sub.strip()
        else:
            eu_cat = row_name

        end_uses[eu_cat] = end_uses.get(eu_cat, 0.0) + val_kwh

    results['total_energy'] = round(total_energy, 3)
    results['end_uses'] = {k: round(v, 3) for k, v in end_uses.items()}

    # EUI uses conditioned area when available; falls back to total
    area = results['conditioned_floor_area'] or results['total_floor_area']
    if area > 0:
        results['eui'] = round(total_energy / area, 3)
        results['end_uses_normalized'] = {
            k: round(v / area, 3) for k, v in end_uses.items()
        }

    return results


# ---------------------------------------------------------------------------
# Process single result directory (Phase 4 orchestrator)
# ---------------------------------------------------------------------------

def process_single_result(output_dir: str,
                          plot_output_dir: str = None,
                          scaling_factor: float = 1.0) -> dict:
    """
    Processes one simulation result directory.

    Reads  →  output_dir/eplusout.sql
    Writes →  output_dir/eui_summary.json
    Writes →  output_dir/<name>_eui_breakdown.png

    Args:
        output_dir:      Directory containing eplusout.sql.
        plot_output_dir: Where to save the PNG (defaults to output_dir).
        scaling_factor:  Scale factor for partial-year simulations.

    Returns:
        dict: EUI results (empty dict on failure).
    """
    sql_path = os.path.join(output_dir, 'eplusout.sql')
    if not os.path.exists(sql_path):
        print(f"  [plotting] SQL file not found: {sql_path}")
        return {}

    if plot_output_dir is None:
        plot_output_dir = output_dir
    os.makedirs(plot_output_dir, exist_ok=True)

    try:
        conn = sqlite3.connect(sql_path)
        eui_results = calculate_eui(conn)
        conn.close()

        # Scale if needed (e.g. 52/24 for 24-week simulation)
        if scaling_factor != 1.0:
            eui_results = _scale_eui_results(eui_results, scaling_factor)

        # Save JSON summary
        json_path = os.path.join(output_dir, 'eui_summary.json')
        with open(json_path, 'w') as f:
            json.dump(eui_results, f, indent=4)
        print(f"  [plotting] JSON saved: {json_path}")

        # Generate breakdown bar chart
        sim_name = os.path.basename(output_dir)
        plot_path = os.path.join(plot_output_dir, f"{sim_name}_eui_breakdown.png")
        plot_eui_breakdown(eui_results, plot_path)

        return eui_results

    except Exception as e:
        print(f"  [plotting] Error processing {output_dir}: {e}")
        return {}


def _scale_eui_results(results: dict, factor: float) -> dict:
    """Scales all energy values by factor (used for partial-year upscaling)."""
    scaled = results.copy()
    scaled['eui'] = round(results['eui'] * factor, 3)
    scaled['total_energy'] = round(results['total_energy'] * factor, 3)
    scaled['end_uses'] = {k: round(v * factor, 3) for k, v in results['end_uses'].items()}
    scaled['end_uses_normalized'] = {
        k: round(v * factor, 3) for k, v in results['end_uses_normalized'].items()
    }
    return scaled


# ---------------------------------------------------------------------------
# EUI breakdown bar chart (Phase 5)
# ---------------------------------------------------------------------------

def get_energy_color(category_name: str) -> Optional[str]:
    """Returns semantic color for an energy category, or None to use palette."""
    lower = category_name.lower()
    for key, color in ENERGY_COLOR_MAP.items():
        if key in lower:
            return color
    return None


def plot_eui_breakdown(eui_results: dict, output_path: str) -> None:
    """
    Generates a semantic-color bar chart of normalized end-use energy (kWh/m²).

    Args:
        eui_results: Result dict from calculate_eui().
        output_path: Full path for the output PNG file.
    """
    end_uses = eui_results.get('end_uses_normalized', {})
    if not end_uses:
        print("  [plotting] No end-use data to plot.")
        return

    labels = list(end_uses.keys())
    values = list(end_uses.values())

    # Map to human-readable labels
    display_labels = [END_USE_LABELS.get(l.lower(), l) for l in labels]

    # Assign semantic colors; fall back to default palette
    colors = []
    palette_idx = 0
    for label in labels:
        c = get_energy_color(label)
        if c:
            colors.append(c)
        else:
            colors.append(DEFAULT_PALETTE[palette_idx % len(DEFAULT_PALETTE)])
            palette_idx += 1

    fig, ax = plt.subplots(figsize=(14, 7))
    bars = ax.bar(display_labels, values, color=colors, edgecolor='black', linewidth=0.5)

    # Value labels above each bar
    for bar, val in zip(bars, values):
        ax.annotate(
            f'{val:.1f}',
            xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 3), textcoords='offset points',
            ha='center', va='bottom', fontsize=9,
        )

    sim_name = os.path.basename(output_path).replace('_eui_breakdown.png', '')
    eui_total = eui_results.get('eui', 0)
    area = eui_results.get('conditioned_floor_area') or eui_results.get('total_floor_area', 0)

    ax.set_xlabel('End Use Category', fontsize=12, fontweight='bold')
    ax.set_ylabel('EUI (kWh/m²)', fontsize=12, fontweight='bold')
    ax.set_title(
        f"{sim_name}\nTotal EUI: {eui_total:.1f} kWh/m²  |  Floor area: {area:.1f} m²",
        fontsize=13,
    )
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)
    ax.set_axisbelow(True)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"  [plotting] Plot saved: {output_path}")
    plt.close()


# ---------------------------------------------------------------------------
# Monthly meter data extraction
# ---------------------------------------------------------------------------

def get_meter_data(conn) -> Dict[str, List[float]]:
    """
    Extracts monthly meter values from ReportData (requires Output:Meter injected).

    Returns:
        Dict mapping meter name → list of monthly kWh values (12 items for annual run).
    """
    query_meta = """
    SELECT ReportDataDictionaryIndex, KeyValue, Name, Units
    FROM ReportDataDictionary
    WHERE ReportingFrequency = 5 OR ReportingFrequency = 'Monthly'
    """
    try:
        meta_df = pd.read_sql_query(query_meta, conn)
    except Exception as e:
        print(f"  [plotting] Error querying meter dictionary: {e}")
        return {}

    index_map = {
        row['ReportDataDictionaryIndex']: (row['Name'], row['Units'])
        for _, row in meta_df.iterrows()
    }
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
        # Convert to kWh
        if units == 'J':
            values = [v / 3_600_000.0 for v in values]
        elif units == 'GJ':
            values = [v * 277.778 for v in values]
        elif units == 'kBtu':
            values = [v * 0.293071 for v in values]
        results[name] = values

    return results


# ---------------------------------------------------------------------------
# Hourly meter data extraction
# ---------------------------------------------------------------------------

def get_hourly_meter_data(conn) -> Dict[str, List[float]]:
    """
    Extracts hourly output variable values from ReportData (requires Output:Variable injected).

    Returns:
        Dict mapping variable name → list of hourly values in Joules (up to 8760 items).
    """
    query_meta = """
    SELECT ReportDataDictionaryIndex, KeyValue, Name, Units
    FROM ReportDataDictionary
    WHERE ReportingFrequency = 3 OR ReportingFrequency = 'Hourly'
    """
    try:
        meta_df = pd.read_sql_query(query_meta, conn)
    except Exception:
        return {}

    index_map = {}
    for _, row in meta_df.iterrows():
        name = row['Name']
        # Filter to relevant meters to reduce memory usage
        if any(x in name for x in ['EnergyTransfer', 'Electricity', 'WaterSystems']):
            index_map[row['ReportDataDictionaryIndex']] = (name, row['Units'])

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
        results[name] = subset['Value'].tolist()  # raw Joules (typical E+ hourly unit)

    return results
