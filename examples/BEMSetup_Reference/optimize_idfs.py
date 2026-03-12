import os
import glob
import platform

# Cross-platform EnergyPlus paths
if platform.system() == 'Darwin':  # macOS
    ENERGYPLUS_DIR = '/Applications/EnergyPlus-24-2-0'
elif platform.system() == 'Windows':
    ENERGYPLUS_DIR = r'C:\EnergyPlusV24-2-0'
else:
    ENERGYPLUS_DIR = '/usr/local/EnergyPlus-24-2-0'

IDD_FILE = os.path.join(ENERGYPLUS_DIR, 'Energy+.idd')


def optimize_idf(file_path):
    """Optimize an IDF file for simulation."""
    print(f"Optimizing {file_path}...")
    with open(file_path, 'r') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        # Update Timestep
        if 'Timestep,' in line and ';' in line:
            parts = line.split(',')
            if parts[0].strip() == 'Timestep':
                new_lines.append('  Timestep,4;\n')
                continue
        
        # Update Solar Distribution
        if 'FullInteriorAndExterior' in line:
            line = line.replace('FullInteriorAndExterior', 'FullExterior')
        
        new_lines.append(line)

    # Add output variables for Lights, Equipment, and Fans if not present
    content = ''.join(new_lines)
    output_vars_to_add = []
    
    # Check and add missing output variables
    if 'Zone Lights Electricity Energy' not in content:
        output_vars_to_add.append('''
Output:Variable,
    *,                       !- Key Value
    Zone Lights Electricity Energy,  !- Variable Name
    Hourly;                  !- Reporting Frequency
''')
    
    if 'Zone Electric Equipment Electricity Energy' not in content:
        output_vars_to_add.append('''
Output:Variable,
    *,                       !- Key Value
    Zone Electric Equipment Electricity Energy,  !- Variable Name
    Hourly;                  !- Reporting Frequency
''')
    
    if 'Fan Electricity Energy' not in content:
        output_vars_to_add.append('''
Output:Variable,
    *,                       !- Key Value
    Fan Electricity Energy,  !- Variable Name
    Hourly;                  !- Reporting Frequency
''')
    
    # Add Zone Air System energy for buildings with detailed HVAC (HighRise, etc.)
    if 'Zone Air System Sensible Heating Energy' not in content:
        output_vars_to_add.append('''
Output:Variable,
    *,                       !- Key Value
    Zone Air System Sensible Heating Energy,  !- Variable Name
    Hourly;                  !- Reporting Frequency
''')
    
    if 'Zone Air System Sensible Cooling Energy' not in content:
        output_vars_to_add.append('''
Output:Variable,
    *,                       !- Key Value
    Zone Air System Sensible Cooling Energy,  !- Variable Name
    Hourly;                  !- Reporting Frequency
''')
    
    # Also add IdealLoads variables for buildings that use them (MidRise, etc.)
    if 'Zone Ideal Loads Supply Air Total Heating Energy' not in content:
        output_vars_to_add.append('''
Output:Variable,
    *,                       !- Key Value
    Zone Ideal Loads Supply Air Total Heating Energy,  !- Variable Name
    Hourly;                  !- Reporting Frequency
''')
    
    if 'Zone Ideal Loads Supply Air Total Cooling Energy' not in content:
        output_vars_to_add.append('''
Output:Variable,
    *,                       !- Key Value
    Zone Ideal Loads Supply Air Total Cooling Energy,  !- Variable Name
    Hourly;                  !- Reporting Frequency
''')
    
    if output_vars_to_add:
        new_lines.append('\n! ===== Added Output Variables for Energy Analysis =====\n')
        for var in output_vars_to_add:
            new_lines.append(var)
        print(f"  Added {len(output_vars_to_add)} output variables")

    with open(file_path, 'w') as f:
        f.writelines(new_lines)


def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    idf_files = glob.glob(os.path.join(root_dir, 'Building', '**', '*.idf'), recursive=True)
    
    # Filter out already expanded files
    idf_files = [f for f in idf_files if '_EXPANDED' not in f]
    
    print(f"Found {len(idf_files)} IDF files.")
    print("=" * 60)
    
    for idf in idf_files:
        optimize_idf(idf)
    
    print("=" * 60)
    print("Optimization complete.")

if __name__ == "__main__":
    main()
