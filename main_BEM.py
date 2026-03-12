"""
main_BEM.py — EnergyPlus Simulation Pipeline — Workflow Controller (Phase 1).

Menu-driven interface for:
  1. Run single simulation  (select IDF + EPW → optimize → simulate → process)
  2. Run all simulations    (parallel batch)
  3. Process results        (SQL → JSON + PNG for a selected SimResults/ subdirectory)
  4. Visualize results      (load eui_summary.json → show bar chart)
  q. Quit

IDF files are discovered from IDF_DIRS (Content sub-folders listed below).
Weather files are read from Content/WeatherFiles/.
Simulation outputs go to 0_BEM_Setup/SimResults/ (created automatically).
"""
import os
import sys
import glob
import json
import shutil
import datetime

# Ensure BEM_utils is importable when running this script directly
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from BEM_utils import config, idf_optimizer, simulation, plotting

def get_idf_version(idf_path: str) -> str:
    """
    Peeks at the IDF file to find the Version object.
    Returns e.g. '22.1' or '24.2'. Defaults to config.DEFAULT_VERSION.
    """
    try:
        with open(idf_path, 'r', encoding='latin-1', errors='ignore') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if 'VERSION' in line.upper():
                    # Look for the value in the next line or same line
                    # Usually: Version, 22.1;
                    content = "".join(lines[i:i+3])
                    import re
                    match = re.search(r'Version\s*,\s*([\d\.]+)', content, re.IGNORECASE)
                    if match:
                        v = match.group(1)
                        # Normalize 22.1.0 -> 22.1
                        parts = v.split('.')
                        return f"{parts[0]}.{parts[1]}"
    except Exception:
        pass
    return config.DEFAULT_VERSION

def organize_output_files(output_dir: str, idf_basename: str):
    """
    Moves all files in output_dir into a subfolder <idf_basename>_H<hour>,
    EXCEPT for the generated breakdown plot (.png).
    """
    hour = datetime.datetime.now().strftime("%H")
    subfolder_name = f"{idf_basename}_H{hour}"
    subfolder_path = os.path.join(output_dir, subfolder_name)
    
    os.makedirs(subfolder_path, exist_ok=True)
    
    # Identify the plot filename (convention: sim_dir_name + _eui_breakdown.png)
    plot_filename = f"{os.path.basename(output_dir)}_eui_breakdown.png"
    
    files_moved = 0
    for file in os.listdir(output_dir):
        file_path = os.path.join(output_dir, file)
        
        # Only move files, skip the recently created subfolder and the plot
        if os.path.isfile(file_path) and file != plot_filename:
            try:
                shutil.move(file_path, os.path.join(subfolder_path, file))
                files_moved += 1
            except Exception as e:
                pass # Silently skip if file is locked or already gone
                
    if files_moved > 0:
        print(f"  [Auto] Grouped results into: {os.path.basename(subfolder_path)}")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ENERGYPLUS_EXE  = config.ENERGYPLUS_EXE
IDD_FILE        = config.IDD_FILE
SIM_RESULTS_DIR = os.path.join(BASE_DIR, "0_BEM_Setup", "SimResults")

# IDF source directories — all are searched recursively for .idf files.
IDF_DIRS = [
    os.path.join(BASE_DIR, "Content", "ASHRAE901_STD2022"),
    os.path.join(BASE_DIR, "Content", "CHV_buildings"),
    os.path.join(BASE_DIR, "Content", "low_rise_Res"),
    os.path.join(BASE_DIR, "Content", "others"),
    os.path.join(BASE_DIR, "0_BEM_Setup", "Buildings"),  # user drop-in folder
]

# Weather files: Content/WeatherFiles/ is primary; 0_BEM_Setup/WeatherFile/ is fallback.
WEATHER_DIRS = [
    os.path.join(BASE_DIR, "Content", "WeatherFiles"),
    os.path.join(BASE_DIR, "0_BEM_Setup", "WeatherFile"),
]


# ---------------------------------------------------------------------------
# Helper: EPW file selection
# ---------------------------------------------------------------------------

def select_weather_file() -> str:
    """
    Lists all .epw files from WEATHER_DIRS and prompts the user to choose one.

    Returns:
        Full path to the selected EPW file, or None if none found.
    """
    epw_files = []
    for wdir in WEATHER_DIRS:
        epw_files.extend(glob.glob(os.path.join(wdir, '*.epw')))

    if not epw_files:
        print(f"  [ERROR] No .epw files found in:")
        for d in WEATHER_DIRS:
            print(f"    {d}")
        return None

    print("\nAvailable Weather Files:")
    for i, f in enumerate(epw_files, 1):
        print(f"  {i}. {os.path.basename(f)}")

    while True:
        try:
            idx = int(input(f"Select EPW (1–{len(epw_files)}): ")) - 1
            if 0 <= idx < len(epw_files):
                selected = epw_files[idx]
                print(f"  Selected: {os.path.basename(selected)}")
                return selected
        except ValueError:
            pass
        print("  Invalid selection. Try again.")


# ---------------------------------------------------------------------------
# Helper: IDF discovery
# ---------------------------------------------------------------------------

def find_idf_files(idf_dirs: list) -> list:
    """
    Recursively finds all .idf files in each directory in idf_dirs.

    Files are grouped by source directory so the menu shows them in a
    logical order (ASHRAE → CHV → low_rise_Res → others → drop-in).
    """
    files = []
    for d in idf_dirs:
        if os.path.isdir(d):
            files.extend(sorted(glob.glob(os.path.join(d, '**', '*.idf'), recursive=True)))
    return files


# ---------------------------------------------------------------------------
# Helper: generic file selection menu
# ---------------------------------------------------------------------------

def select_file(files: list, prompt: str) -> str:
    """
    Displays a numbered list and returns the selected file path.
    Shows the parent folder name alongside the filename to disambiguate
    files with identical basenames from different source directories.
    """
    print(f"\n{prompt}")
    for i, f in enumerate(files, 1):
        parent = os.path.basename(os.path.dirname(f))
        print(f"  {i:>3}. [{parent}]  {os.path.basename(f)}")
    while True:
        try:
            idx = int(input(f"Select number (1–{len(files)}): ")) - 1
            if 0 <= idx < len(files):
                return files[idx]
        except ValueError:
            pass
        print("  Invalid selection. Try again.")


# ---------------------------------------------------------------------------
# Menu options
# ---------------------------------------------------------------------------

def option_run_single():
    """Option 1: Optimize + simulate one IDF with a chosen EPW."""
    idf_files = find_idf_files(IDF_DIRS)
    if not idf_files:
        print(f"\n  No IDF files found in any of the configured IDF directories:")
        for d in IDF_DIRS:
            print(f"    {d}")
        return

    idf_path = select_file(idf_files, "Select IDF file:")
    epw_path  = select_weather_file()
    if not epw_path:
        return

    idf_name = os.path.splitext(os.path.basename(idf_path))[0]
    epw_name = os.path.splitext(os.path.basename(epw_path))[0]
    output_dir = os.path.join(SIM_RESULTS_DIR, f"{idf_name}_{epw_name}")

    # Detect version and get relevant paths
    version = get_idf_version(idf_path)
    paths = config.get_ep_paths(version)
    print(f"  Detected IDF Version: {version} -> Using EnergyPlus at: {paths['dir']}")

    # Step 1: Optimize IDF (inject Output:SQLite, meters, variables, fixes)
    print(f"\n[1/2] Optimizing IDF: {os.path.basename(idf_path)}")
    try:
        idf_optimizer.optimize_idf(idf_path, paths['idd'], ep_version=version)
    except Exception as e:
        print(f"  Warning: IDF optimization failed — {e}")
        print("  Proceeding with unmodified IDF (eplusout.sql may not be generated).")

    # Step 2: Run simulation
    print(f"\n[2/2] Running simulation → {output_dir}")
    result = simulation.run_simulation(idf_path, epw_path, output_dir, paths['exe'])

    # Auto-process results on success (Section 1.5 of plan)
    if result.get('success'):
        print("\n[Auto] Extracting EUI and generating plot...")
        plotting.process_single_result(output_dir)
        organize_output_files(output_dir, idf_name)
    else:
        print(f"\n  Simulation failed: {result.get('message', 'Unknown error')}")


def option_run_parallel():
    """Option 2: Optimize + simulate all IDFs from IDF_DIRS in parallel."""
    idf_files = find_idf_files(IDF_DIRS)
    if not idf_files:
        print(f"\n  No IDF files found in any configured IDF directory.")
        return

    epw_path = select_weather_file()
    if not epw_path:
        return

    epw_name = os.path.splitext(os.path.basename(epw_path))[0]
    confirm = input(
        f"\n  Run {len(idf_files)} simulations in parallel with "
        f"{os.path.basename(epw_path)}? (y/n): "
    ).strip().lower()
    if confirm != 'y':
        return

    max_cpus = os.cpu_count() or 4
    try:
        n_workers_str = input(f"  Max parallel workers (default {max_cpus}): ").strip()
        n_workers = int(n_workers_str) if n_workers_str else max_cpus
    except ValueError:
        n_workers = max_cpus

    # Optimize IDFs first (each using its own version-specific IDD)
    print(f"\n  Optimizing {len(idf_files)} IDF files...")
    jobs = []
    for idf_path in idf_files:
        version = get_idf_version(idf_path)
        paths = config.get_ep_paths(version)
        try:
            idf_optimizer.optimize_idf(idf_path, paths['idd'], ep_version=version)
        except Exception as e:
            print(f"    Warning: {os.path.basename(idf_path)} — {e}")

        # Build job list
        idf_name = os.path.splitext(os.path.basename(idf_path))[0]
        jobs.append({
            'idf': idf_path,
            'epw': epw_path,
            'output_dir': os.path.join(SIM_RESULTS_DIR, f"{idf_name}_{epw_name}"),
            'name': os.path.basename(idf_path),
            'ep_path': paths['exe'], # Specific EXE per job
        })

    # Run simulations in parallel
    # Note: we pass ENERGYPLUS_EXE as a dummy here because each job now has its own 'ep_path'
    # but we need to update simulation.py to PRIORITIZE job['ep_path'] if provided.
    results = simulation.run_simulations_parallel(jobs, config.ENERGYPLUS_EXE, max_workers=n_workers)

    # Auto-process successful results
    if results['successful']:
        print("\n  Auto-processing results for successful simulations...")
        for res in results['successful']:
            try:
                plotting.process_single_result(res['output_dir'])
                # res.get('name') is the idf filename (e.g. 'ASHRAE...idf')
                idf_base = os.path.splitext(res['name'])[0]
                organize_output_files(res['output_dir'], idf_base)
            except Exception as e:
                print(f"    Warning: could not process {res.get('name', '?')} — {e}")


def option_process_results():
    """Option 3: Process an existing eplusout.sql → eui_summary.json + PNG."""
    if not os.path.isdir(SIM_RESULTS_DIR):
        print(f"\n  SimResults directory not found: {SIM_RESULTS_DIR}")
        return

    result_dirs = sorted([
        d for d in os.listdir(SIM_RESULTS_DIR)
        if os.path.isdir(os.path.join(SIM_RESULTS_DIR, d))
        and os.path.exists(os.path.join(SIM_RESULTS_DIR, d, 'eplusout.sql'))
    ])

    if not result_dirs:
        print("  No simulation results with eplusout.sql found.")
        print("  Run a simulation first (Option 1 or 2).")
        return

    print("\nAvailable simulation results (with eplusout.sql):")
    for i, d in enumerate(result_dirs, 1):
        print(f"  {i}. {d}")

    try:
        idx = int(input(f"Select number (1–{len(result_dirs)}): ")) - 1
        if 0 <= idx < len(result_dirs):
            output_dir = os.path.join(SIM_RESULTS_DIR, result_dirs[idx])
            plotting.process_single_result(output_dir)
        else:
            print("  Invalid number.")
    except ValueError:
        print("  Invalid input.")


def option_visualize_results():
    """Option 4: Load eui_summary.json and regenerate the bar chart."""
    if not os.path.isdir(SIM_RESULTS_DIR):
        print(f"\n  SimResults directory not found: {SIM_RESULTS_DIR}")
        return

    result_dirs = sorted([
        d for d in os.listdir(SIM_RESULTS_DIR)
        if os.path.isdir(os.path.join(SIM_RESULTS_DIR, d))
        and os.path.exists(os.path.join(SIM_RESULTS_DIR, d, 'eui_summary.json'))
    ])

    if not result_dirs:
        print("  No processed results found (eui_summary.json missing).")
        print("  Run Option 3 to process simulation results first.")
        return

    print("\nAvailable processed results:")
    for i, d in enumerate(result_dirs, 1):
        print(f"  {i}. {d}")

    try:
        idx = int(input(f"Select number (1–{len(result_dirs)}): ")) - 1
        if 0 <= idx < len(result_dirs):
            sim_name = result_dirs[idx]
            output_dir = os.path.join(SIM_RESULTS_DIR, sim_name)
            json_path = os.path.join(output_dir, 'eui_summary.json')
            with open(json_path) as f:
                eui_results = json.load(f)
            plot_path = os.path.join(output_dir, f"{sim_name}_eui_breakdown.png")
            plotting.plot_eui_breakdown(eui_results, plot_path)
        else:
            print("  Invalid number.")
    except ValueError:
        print("  Invalid input.")
    except Exception as e:
        print(f"  Error: {e}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    os.makedirs(SIM_RESULTS_DIR, exist_ok=True)

    idf_count = len(find_idf_files(IDF_DIRS))
    print("=" * 60)
    print("  BEM Simulation Pipeline")
    print(f"  EnergyPlus: {ENERGYPLUS_EXE}")
    print(f"  IDF sources ({idf_count} files found):")
    for d in IDF_DIRS:
        if os.path.isdir(d):
            n = len(glob.glob(os.path.join(d, '**', '*.idf'), recursive=True))
            print(f"    [{n:>2}] {os.path.relpath(d, BASE_DIR)}")
    print(f"  Results:    {os.path.relpath(SIM_RESULTS_DIR, BASE_DIR)}")
    print("=" * 60)

    while True:
        print("\nOptions:")
        print("  1. Run single simulation  (select IDF + EPW)")
        print("  2. Run all simulations    (parallel batch)")
        print("  3. Process results        (SQL → JSON + PNG)")
        print("  4. Visualize results      (JSON → bar chart)")
        print("  q. Quit")

        choice = input("\nEnter choice: ").strip().lower()

        if choice == 'q':
            print("Goodbye.")
            break
        elif choice == '1':
            option_run_single()
        elif choice == '2':
            option_run_parallel()
        elif choice == '3':
            option_process_results()
        elif choice == '4':
            option_visualize_results()
        else:
            print("  Invalid choice. Enter 1, 2, 3, 4, or q.")


# macOS / Windows: ProcessPoolExecutor requires this guard to prevent
# recursive subprocess spawning when running parallel simulations.
if __name__ == '__main__':
    main()
