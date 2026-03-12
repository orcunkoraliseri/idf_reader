# EUI Calculation Implementation

Calculate Energy Use Intensity (EUI) from EnergyPlus simulation results by reading tabular data from the SQL output file.

## Proposed Changes

### bem_utils/read_results.py

#### New Function: `get_connection`
```python
def get_connection(sql_file_path):
    """
    Establishes a connection to the SQLite database.
    """
```
- Validates file existence before connection
- Returns SQLite connection object

---

#### New Function: `get_tabular_data`
```python
def get_tabular_data(conn, table_name):
    """
    Retrieves tabular data for a specific table name.
    Returns a DataFrame with RowName, ColumnName, Value.
    """
```
- Queries `TabularDataWithStrings` table
- Returns structured DataFrame with all columns including Units

---

#### New Function: `calculate_eui`
```python
def calculate_eui(conn):
    """
    Calculates EUI, Total Floor Area, and End Uses from the SQL connection.
    Returns a dictionary with the results.
    """
```

**Key implementation details:**

1. **Building Area Extraction**
   - Query `Building Area` table from SQL
   - Extract `Total Building Area` and `Net Conditioned Building Area`

2. **End Uses Processing**
   - Primary source: `End Uses By Subcategory` table
   - Fallback: `End Uses` table if subcategory not available
   - Skip non-energy columns (Water, m³ units)

3. **Unit Conversion**
   - EnergyPlus reports energy in GJ
   - Convert to kWh: `1 GJ = 277.778 kWh`
   - Handle J and kWh units as well

4. **Category Parsing**
   - Parse subcategory format: `Category:Subcategory`
   - If subcategory is 'General' or 'Other', use main category
   - Otherwise, use subcategory name

5. **Results Dictionary**
```python
{
    'eui': float,                    # Total EUI in kWh/m²
    'total_floor_area': float,       # Total building area in m²
    'conditioned_floor_area': float, # Net conditioned area in m²
    'total_energy': float,           # Total energy in kWh
    'end_uses': dict,                # Absolute energy by category
    'end_uses_normalized': dict      # EUI by category (kWh/m²)
}
```

---

#### New Function: `process_results`
```python
def process_results(output_dir):
    """
    Processes the eplusout.sql file in the given directory.
    1. Extracts Zone Energy Demand to CSV.
    2. Calculates EUI and saves to JSON.
    3. Generates EUI breakdown plot.
    """
```

**Output files generated:**
- `zone_energy_demand.csv` - Pivoted time-series data
- `eui_summary.json` - Complete EUI results
- `eui_breakdown.png` - Visual breakdown plot

---

### main_file.py

#### New Menu Option: Process Results
```diff
+ elif choice == '6':
+     # Process simulation results
+     results_dirs = list_simulation_results()
+     selected = get_user_selection(results_dirs)
+     read_results.process_results(selected)
```

---

## Data Flow Diagram

```
eplusout.sql
     │
     ▼
┌─────────────────┐
│ get_connection  │
└─────────────────┘
     │
     ▼
┌─────────────────┐     ┌──────────────────┐
│ calculate_eui   │────▶│ Building Area    │
└─────────────────┘     │ End Uses Tables  │
     │                  └──────────────────┘
     ▼
┌─────────────────┐
│ Unit conversion │
│ GJ → kWh        │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ Calculate EUI:  │
│ Energy / Area   │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ eui_summary.json│
└─────────────────┘
```

---

## Notes

**SQL Tables Used:**
- `TabularDataWithStrings` - Contains all tabular report data
- `ReportDataDictionary` - Variable definitions
- `ReportData` - Time-series values
- `Time` - Timestamp information

**Units:**
- Input: GJ (EnergyPlus default for tabular reports)
- Output: kWh/m² (industry standard EUI)

---

## Status: IMPLEMENTED

Core EUI calculation functionality is complete and integrated into the main workflow.
