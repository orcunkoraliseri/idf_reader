import sqlite3
import pandas as pd
import os
import json
import matplotlib.pyplot as plt
from collections import OrderedDict

def get_connection(sql_file_path):
    """
    Establishes a connection to the SQLite database.
    """
    if not os.path.exists(sql_file_path):
        raise FileNotFoundError(f"SQL file not found: {sql_file_path}")
    return sqlite3.connect(sql_file_path)

def list_available_variables(conn):
    """
    Lists all available report variables in the database.
    """
    query = """
    SELECT DISTINCT Name, Units 
    FROM ReportDataDictionary
    ORDER BY Name
    """
    return pd.read_sql_query(query, conn)

def get_tabular_data(conn, table_name):
    """
    Retrieves tabular data for a specific table name.
    Returns a DataFrame with RowName, ColumnName, Value.
    """
    query = """
    SELECT TableName, RowName, ColumnName, Units, Value
    FROM TabularDataWithStrings
    WHERE TableName = ?
    """
    df = pd.read_sql_query(query, conn, params=(table_name,))
    return df

def calculate_eui(conn):
    """
    Calculates EUI, Total Floor Area, and End Uses from the SQL connection.
    Returns a dictionary with the results.
    """
    results = {
        'eui': 0.0,
        'total_floor_area': 0.0,
        'conditioned_floor_area': 0.0,
        'total_energy': 0.0,
        'end_uses': {}
    }

    # 1. Get Building Areas
    area_df = get_tabular_data(conn, 'Building Area')
    if not area_df.empty:
        # Look for 'Total Building Area' and 'Net Conditioned Building Area'
        # Values are strings in the DB, need to convert to float
        for _, row in area_df.iterrows():
            try:
                val = float(row['Value'])
                if row['RowName'] == 'Total Building Area':
                    results['total_floor_area'] = val
                elif row['RowName'] == 'Net Conditioned Building Area':
                    results['conditioned_floor_area'] = val
            except ValueError:
                continue

    # 2. Get End Uses
    # We use 'End Uses By Subcategory' to get detailed breakdown
    # If not available, 'End Uses' table is a fallback, but user requested 'End Uses By Subcategory' logic
    end_use_df = get_tabular_data(conn, 'End Uses By Subcategory')
    
    if end_use_df.empty:
        # Fallback to standard 'End Uses' if subcategory table is missing
        end_use_df = get_tabular_data(conn, 'End Uses')

    total_energy = 0.0
    end_uses = OrderedDict()

    if not end_use_df.empty:
        # Pivot to have Columns as Fuel Types and Rows as Categories
        # But simple iteration is enough. We want to sum all energy columns for each category.
        # Columns to exclude (not energy): 'Water' is usually in there but we want Energy.
        # EnergyPlus columns: Electricity, Natural Gas, Gasoline, etc.
        # We should sum everything that looks like energy (GJ or kWh). 
        # The table usually contains values in GJ. We need to convert to kWh if they are in GJ.
        # Wait, the user snippet assumes values are already compatible or handles them. 
        # Honeybee's SQLiteResult usually handles unit conversion if requested, but raw SQL has units in the 'Units' column of TabularDataWithStrings?
        # Let's check units.
        
        # Actually, TabularDataWithStrings has a 'Units' column.
        # Let's update get_tabular_data to fetch Units too.
        
        query = """
        SELECT TableName, RowName, ColumnName, Units, Value
        FROM TabularDataWithStrings
        WHERE TableName = ? OR TableName = ?
        """
        # Fetching both potential table names to be safe, though we filter in Python
        df = pd.read_sql_query(query, conn, params=('End Uses By Subcategory', 'End Uses'))
        
        # Filter for the specific table we want to use
        target_table = 'End Uses By Subcategory'
        subset = df[df['TableName'] == target_table]
        if subset.empty:
            target_table = 'End Uses'
            subset = df[df['TableName'] == target_table]
            
        for _, row in subset.iterrows():
            row_name = row['RowName']
            col_name = row['ColumnName']
            units = row['Units']
            val_str = row['Value']
            
            # Skip totals or non-energy columns if necessary
            # Honeybee snippet sums first 12 columns. 
            # We'll sum columns that are energy types.
            # Common columns: Electricity, Natural Gas, District Cooling, District Heating, etc.
            # Exclude: Water [m3]
            
            if 'Water' in col_name or 'm3' in str(units):
                continue
                
            try:
                val = float(val_str)
            except ValueError:
                continue
                
            # Convert to kWh if necessary. E+ tabular data is often in GJ.
            # 1 GJ = 277.778 kWh
            if units == 'GJ':
                val_kwh = val * 277.778
            elif units == 'kWh':
                val_kwh = val
            elif units == 'J':
                 val_kwh = val / 3600000.0
            else:
                # Assume kWh if unknown or 0? Or skip? 
                # If it's energy, it's likely GJ in standard reports.
                # Let's assume GJ if unit is GJ, otherwise keep as is (risky but standard E+ is GJ)
                # Actually, let's look at the user snippet. It doesn't show conversion. 
                # Honeybee might set the report to kWh or convert implicitly.
                # Standard E+ HTML/SQL report is usually GJ.
                # Let's assume GJ and convert to kWh.
                if units == 'GJ':
                    val_kwh = val * 277.778
                else:
                    val_kwh = val

            if val_kwh != 0:
                total_energy += val_kwh
                
                # Category parsing from user snippet: cat, sub_cat = category.split(':')
                if ':' in row_name:
                    parts = row_name.split(':')
                    cat = parts[0]
                    sub_cat = parts[1] if len(parts) > 1 else ''
                    
                    if sub_cat in ['General', 'Other']:
                        eu_cat = cat
                    else:
                        eu_cat = sub_cat
                else:
                    eu_cat = row_name
                
                if eu_cat not in end_uses:
                    end_uses[eu_cat] = 0.0
                end_uses[eu_cat] += val_kwh

    results['total_energy'] = round(total_energy, 3)
    results['end_uses'] = {k: round(v, 3) for k, v in end_uses.items()} # Dict for JSON serialization
    
    if results['total_floor_area'] > 0:
        results['eui'] = round(total_energy / results['total_floor_area'], 3)
        # Normalize end uses by area
        results['end_uses_normalized'] = {k: round(v / results['total_floor_area'], 3) for k, v in end_uses.items()}
    
    return results

def get_zone_energy_demand(conn, variables=None):
    """
    Extracts energy demand data for all zones.
    
    Args:
        conn: SQLite connection object.
        variables: List of variable names to extract. 
                   If None, defaults to common heating/cooling energy variables.
    
    Returns:
        DataFrame with columns: Date, Time, Zone, Variable, Value
    """
    if variables is None:
        # Common variables for energy demand
        # First try IdealLoads, then fallback to Zone Air System variables
        variables = [
            'Zone Ideal Loads Supply Air Total Heating Energy',
            'Zone Ideal Loads Supply Air Total Cooling Energy',
            'Zone Air System Sensible Heating Energy',
            'Zone Air System Sensible Cooling Energy',
            'Zone Thermostat Heating Setpoint Temperature',
            'Zone Thermostat Cooling Setpoint Temperature'
        ]
    
    # Format variables for SQL IN clause
    placeholders = ','.join(['?'] * len(variables))
    
    query = f"""
    SELECT 
        t.TimeIndex,
        rdd.KeyValue as ZoneName,
        rdd.Name as VariableName,
        rd.Value
    FROM ReportData rd
    JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
    JOIN Time t ON rd.TimeIndex = t.TimeIndex
    WHERE rdd.Name IN ({placeholders})
    """
    
    df = pd.read_sql_query(query, conn, params=variables)
    
    # We need to reconstruct the actual timestamp from TimeIndex or Time table
    # For simplicity, let's pull the Time table details to construct a DateTime
    time_query = "SELECT TimeIndex, Year, Month, Day, Hour, Minute FROM Time"
    time_df = pd.read_sql_query(time_query, conn)
    
    # Merge to get time details
    df = df.merge(time_df, on='TimeIndex')
    
    # Create a datetime column (assuming Year is correct, or use a dummy year if simulation is weather file dependent)
    # EnergyPlus "24:00" is "00:00" of the next day, which pandas doesn't like directly.
    # We'll adjust the hour/minute to create a proper datetime.
    
    def create_datetime(row):
        # Basic handling, might need refinement for end-of-day wrap around
        try:
            return pd.Timestamp(year=row['Year'], month=row['Month'], day=row['Day'], hour=row['Hour']-1, minute=row['Minute']) + pd.Timedelta(hours=1)
        except:
            return None

    df['DateTime'] = df.apply(create_datetime, axis=1)
    
    return df

def pivot_and_save(df, output_path):
    """
    Pivots the data to a tabular format and saves to CSV.
    Format: Rows = Time, Columns = Zone_Variable
    """
    if df.empty:
        print("No data found for the specified variables.")
        return

    # Pivot: Index=DateTime, Columns=[ZoneName, VariableName], Values=Value
    pivot_df = df.pivot_table(index='DateTime', columns=['ZoneName', 'VariableName'], values='Value')
    
    # Flatten column names
    pivot_df.columns = [f"{col[0]}_{col[1]}" for col in pivot_df.columns]
    
    # Save
    pivot_df.to_csv(output_path)
    print(f"Data saved to {output_path}")

# Energy category color mapping
# Warm colors for gains, cool colors for losses
ENERGY_COLOR_MAP = {
    # Energy gains (warm colors)
    'heating': '#8A1100',       # Dark Red - Heating
    'heat': '#8A1100',
    'solar': '#A6F956',         # Yellow-Green - Solar gains
    'equipment': '#EF2700',     # Red - Equipment
    'plug': '#EF2700',
    'people': '#FEF401',        # Yellow - People/Occupants
    'occupant': '#FEF401',
    'lighting': '#FF7900',      # Orange - Lighting
    'light': '#FF7900',
    
    # Energy losses (cool colors)
    'cooling': '#041991',       # Dark Blue - Cooling
    'cool': '#041991',
    'infiltration': '#0730E0',  # Blue - Infiltration
    'ventilation': '#0758FF',   # Medium Blue - Ventilation
    'vent': '#0758FF',
    'mechanical ventilation': '#01E8FF',  # Cyan - Mechanical Ventilation
    
    # Conduction (gray-brown tones)
    'conduction': '#806640',    # Brown - Opaque Conduction
    'wall': '#806640',
    'roof': '#806640',
    'floor': '#806640',
    'glazing': '#01E8FF',       # Cyan - Glazing conduction
    'window': '#01E8FF',
    
    # Storage
    'storage': '#806640',       # Brown - Thermal mass storage
}

# Default palette for categories not in the map
DEFAULT_PALETTE = [
    '#041991', '#0730E0', '#0758FF', '#01E8FF', '#61F69C',
    '#A6F956', '#FEF401', '#FF7900', '#EF2700', '#8A1100', '#806640'
]


def get_energy_color(category_name):
    """
    Returns the appropriate color for an energy category based on semantic mapping.
    """
    category_lower = category_name.lower()
    
    # Check for exact or partial matches in the color map
    for key, color in ENERGY_COLOR_MAP.items():
        if key in category_lower:
            return color
    
    # Return None if no match found (will use default palette)
    return None


def plot_eui_breakdown(eui_results, output_path, show_plot=False):
    """
    Generates a bar plot for the EUI breakdown with semantic energy colors.
    Warm colors = energy gains, Cool colors = energy losses.
    """
    end_uses = eui_results.get('end_uses_normalized', {})
    if not end_uses:
        print("No end use data to plot.")
        return

    labels = list(end_uses.keys())
    values = list(end_uses.values())
    
    # Assign colors based on energy category semantics
    colors = []
    default_idx = 0
    for label in labels:
        color = get_energy_color(label)
        if color:
            colors.append(color)
        else:
            # Use default palette for unknown categories
            colors.append(DEFAULT_PALETTE[default_idx % len(DEFAULT_PALETTE)])
            default_idx += 1

    # Create figure with dark background for better contrast
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Create bars
    bars = ax.bar(labels, values, color=colors, edgecolor='black', linewidth=0.5)
    
    # Styling
    ax.set_xlabel('End Use Category', fontsize=12, fontweight='bold')
    ax.set_ylabel('EUI (kWh/m²)', fontsize=12, fontweight='bold')
    ax.set_title('End Use Intensity Breakdown', fontsize=14, fontweight='bold')
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=10)
    
    # Add value labels on bars
    for bar, value in zip(bars, values):
        height = bar.get_height()
        ax.annotate(f'{value:.1f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9)
    
    # Add grid for readability
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Plot saved to {output_path}")
    
    if show_plot:
        plt.show()
    
    plt.close()


def visualize_results(output_dir):
    """
    Loads the EUI summary JSON and visualizes the results.
    """
    json_path = os.path.join(output_dir, 'eui_summary.json')
    plot_path = os.path.join(output_dir, 'eui_breakdown.png')
    
    if not os.path.exists(json_path):
        print(f"Error: Summary file not found at {json_path}. Please process results first.")
        return

    try:
        with open(json_path, 'r') as f:
            eui_results = json.load(f)
            
        print(f"Visualizing results for {os.path.basename(output_dir)}...")
        plot_eui_breakdown(eui_results, plot_path, show_plot=True)
        
    except Exception as e:
        print(f"Error visualizing results: {e}")

def get_thermal_zone_count(conn):
    """
    Gets the total number of thermal zones from the simulation database.
    
    Args:
        conn: SQLite connection object.
    
    Returns:
        dict: Zone count information including modeled and effective (with multipliers)
    """
    result = {
        'modeled_zones': 0,
        'effective_zones': 0,
        'zone_multiplier_info': {}
    }
    
    try:
        # Method 1: Count from Zones table
        query = "SELECT ZoneName, Multiplier FROM Zones"
        zones_df = pd.read_sql_query(query, conn)
        
        result['modeled_zones'] = len(zones_df)
        
        # Calculate effective zones with multipliers
        if 'Multiplier' in zones_df.columns:
            zones_df['Multiplier'] = pd.to_numeric(zones_df['Multiplier'], errors='coerce').fillna(1)
            result['effective_zones'] = int(zones_df['Multiplier'].sum())
            
            # Count zones by multiplier
            multiplier_counts = zones_df['Multiplier'].value_counts().to_dict()
            result['zone_multiplier_info'] = {int(k): int(v) for k, v in multiplier_counts.items()}
        else:
            result['effective_zones'] = result['modeled_zones']
            
    except Exception as e:
        try:
            # Fallback: Count unique zones from ReportDataDictionary
            query = """
            SELECT COUNT(DISTINCT KeyValue) 
            FROM ReportDataDictionary 
            WHERE KeyValue LIKE '%ZONE%' OR KeyValue LIKE '%Zone%'
            """
            count_result = pd.read_sql_query(query, conn)
            result['modeled_zones'] = int(count_result.iloc[0, 0])
            result['effective_zones'] = result['modeled_zones']
        except:
            pass
    
    return result


def process_results(output_dir):
    """
    Processes the eplusout.sql file in the given directory.
    1. Extracts Zone Energy Demand to CSV.
    2. Calculates EUI and saves to JSON.
    3. Generates EUI breakdown plot.
    """
    sql_path = os.path.join(output_dir, 'eplusout.sql')
    output_csv = os.path.join(output_dir, 'zone_energy_demand.csv')
    output_json = os.path.join(output_dir, 'eui_summary.json')
    output_plot = os.path.join(output_dir, 'eui_breakdown.png')
    
    if not os.path.exists(sql_path):
        print(f"Error: SQL file not found at {sql_path}. Please run simulation first.")
        return

    try:
        conn = get_connection(sql_path)
        
        print(f"\nProcessing results for {os.path.basename(output_dir)}...")
        
        # --- Get Thermal Zone Count ---
        zone_info = get_thermal_zone_count(conn)
        print(f"\n{'=' * 50}")
        print(f"BUILDING MODEL SUMMARY")
        print(f"{'=' * 50}")
        print(f"Modeled Thermal Zones:   {zone_info['modeled_zones']}")
        print(f"Effective Zones (w/mult): {zone_info['effective_zones']}")
        if zone_info['zone_multiplier_info']:
            print(f"Zone Multipliers:")
            for mult, count in sorted(zone_info['zone_multiplier_info'].items()):
                print(f"  Multiplier {mult}x: {count} zones")
        print(f"{'=' * 50}")
        
        # --- 1. Zone Energy Demand ---
        print("\nExtracting Zone Energy Demand...")
        df = get_zone_energy_demand(conn) 
        pivot_and_save(df, output_csv)
        
        # --- 2. EUI Calculation ---
        print("Calculating EUI...")
        eui_results = calculate_eui(conn)
        
        # Add zone count to results
        eui_results['modeled_zones'] = zone_info['modeled_zones']
        eui_results['effective_zones'] = zone_info['effective_zones']
        eui_results['zone_multiplier_info'] = zone_info['zone_multiplier_info']
        
        with open(output_json, 'w') as f:
            json.dump(eui_results, f, indent=4)
            
        print(f"EUI Summary saved to {output_json}")
        print(f"\n{'=' * 50}")
        print(f"ENERGY DEMAND RESULTS")
        print(f"{'=' * 50}")
        print(f"Total Floor Area:     {eui_results.get('total_floor_area', 0):.1f} m²")
        print(f"Total Energy:         {eui_results.get('total_energy', 0):.1f} kWh")
        print(f"Total EUI:            {eui_results['eui']} kWh/m²")
        print(f"{'=' * 50}")
        print("\nEnd Use Intensity Breakdown (kWh/m²):")
        for use, value in eui_results.get('end_uses_normalized', {}).items():
            print(f"  {use}: {value}")
            
        # --- 3. Plotting ---
        print("\nGenerating plot...")
        plot_eui_breakdown(eui_results, output_plot, show_plot=False)
        
    except Exception as e:
        print(f"Error processing results: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    # Example usage
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Adjust this path to match your actual result file
    test_dir = os.path.join(base_dir, 'SimResults', 'ASHRAE901_ApartmentMidRise_STD2022_Atlanta_3A')
    process_results(test_dir)
