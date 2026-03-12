"""
idf_optimizer.py — IDF Preparation & Optimization (Phase 2).

Prepares IDF files for EnergyPlus simulation by:
1. Injecting Output:SQLite so eplusout.sql is written
2. Injecting required Output:Meter objects (monthly)
3. Injecting required Output:Variable objects (hourly)
4. Applying speed optimizations (timestep, solar distribution, shadow calc)

No existing IDF objects (PEOPLE, schedules, constructions, etc.) are modified.
"""
import os
from eppy.modeleditor import IDF
from BEM_utils import config

# Monthly meters needed for EUI extraction in plotting.py
REQUIRED_METERS = [
    'Heating:EnergyTransfer',
    'Cooling:EnergyTransfer',
    'InteriorLights:Electricity',
    'InteriorEquipment:Electricity',
    'Fans:Electricity',
    'WaterSystems:EnergyTransfer',
]

# Hourly output variables needed for time-series reporting
REQUIRED_OUTPUT_VARIABLES = [
    ('Zone Lights Electricity Energy', 'Hourly'),
    ('Zone Electric Equipment Electricity Energy', 'Hourly'),
    ('Fan Electricity Energy', 'Hourly'),
    ('Zone Air System Sensible Heating Energy', 'Hourly'),
    ('Zone Air System Sensible Cooling Energy', 'Hourly'),
    ('Zone Ideal Loads Supply Air Total Heating Energy', 'Hourly'),
    ('Zone Ideal Loads Supply Air Total Cooling Energy', 'Hourly'),
]

def optimize_idf(idf_path: str, idd_file: str = None, ep_version: str = None) -> str:
    """
    Modifies the IDF in-place to prepare it for simulation.

    Steps (in order):
      1. Inject Output:SQLite    — required for eplusout.sql generation
      2. Inject Output:Meter     — monthly energy meters for EUI
      3. Inject Output:Variable  — hourly variables for time-series
      4. Apply simulation fixes  — speed settings (timestep, solar, shadow)

    No existing IDF objects are modified — only new Output:* objects are added.

    Args:
        idf_path:   Absolute path to the .idf file.
        idd_file:   Path to Energy+.idd. Defaults to config.IDD_FILE.
        ep_version: Accepted but unused (kept for call-site compatibility).

    Returns:
        idf_path (unchanged) after saving the modified IDF.
    """
    if idd_file is None:
        idd_file = config.IDD_FILE

    IDF.setiddname(idd_file)
    idf = IDF(idf_path)

    _inject_sqlite_output(idf)
    _inject_output_meters(idf)
    _inject_output_variables(idf)
    _apply_simulation_fixes(idf)

    idf.save()
    print(f"  [optimizer] Saved: {os.path.basename(idf_path)}")
    return idf_path


def _inject_sqlite_output(idf) -> None:
    """
    Ensures Output:SQLite is present in the IDF.

    Without this object, EnergyPlus never writes eplusout.sql,
    which means plotting.py cannot extract any results.
    """
    existing = idf.idfobjects.get('OUTPUT:SQLITE', [])
    if not existing:
        obj = idf.newidfobject('OUTPUT:SQLITE')
        # E+ 24.2 renamed 'Output Type' to 'Option Type'
        try:
            obj.Option_Type = 'SimpleAndTabular'
        except AttributeError:
            try:
                obj.Output_Type = 'SimpleAndTabular'
            except AttributeError:
                print("  [optimizer] Warning: Could not set Output:SQLite type field (schema mismatch)")
        print("  [optimizer] Injected Output:SQLite")


def _inject_output_meters(idf) -> None:
    """
    Injects monthly Output:Meter objects for each required energy end-use.

    These meters populate the ReportData table in eplusout.sql, which
    get_meter_data() in plotting.py reads for monthly profiles.
    """
    existing_names = {
        o.Key_Name
        for o in idf.idfobjects.get('OUTPUT:METER', [])
    }
    added = []
    for meter in REQUIRED_METERS:
        if meter not in existing_names:
            obj = idf.newidfobject('OUTPUT:METER')
            obj.Key_Name = meter
            obj.Reporting_Frequency = 'Monthly'
            added.append(meter)
    if added:
        print(f"  [optimizer] Injected Output:Meter: {added}")


def _inject_output_variables(idf) -> None:
    """
    Injects hourly Output:Variable objects for time-series data.

    These populate the ReportDataDictionary / ReportData tables for
    hourly extraction via get_hourly_meter_data() in plotting.py.
    """
    existing = {
        (o.Variable_Name, o.Reporting_Frequency)
        for o in idf.idfobjects.get('OUTPUT:VARIABLE', [])
    }
    added = []
    for var_name, freq in REQUIRED_OUTPUT_VARIABLES:
        if (var_name, freq) not in existing:
            obj = idf.newidfobject('OUTPUT:VARIABLE')
            obj.Key_Value = '*'
            obj.Variable_Name = var_name
            obj.Reporting_Frequency = freq
            added.append(var_name)
    if added:
        print(f"  [optimizer] Injected Output:Variable ({len(added)} variables)")




def _apply_simulation_fixes(idf) -> None:
    """
    Applies speed and compatibility fixes to simulation settings.

    Changes applied:
    - Timestep: 4 steps/hour (15-min intervals, faster than 6)
    - Solar Distribution: FullExterior (faster than FullInteriorAndExterior)
    - ShadowCalculation: recalculate every 20 days (reduces runtime)
    """
    # 1. Timestep — 4 per hour (15 min) is a good balance of speed vs accuracy
    for ts in idf.idfobjects.get('TIMESTEP', []):
        ts.Number_of_Timesteps_per_Hour = 4

    # 2. Solar Distribution — FullExterior is significantly faster
    for bld in idf.idfobjects.get('BUILDING', []):
        if bld.Solar_Distribution == 'FullInteriorAndExterior':
            bld.Solar_Distribution = 'FullExterior'

    # 3. Shadow Calculation — reduce pixel-counting frequency
    for sc in idf.idfobjects.get('SHADOWCALCULATION', []):
        try:
            sc.Calculation_Frequency = 20  # recalculate every 20 days
        except Exception:
            pass
