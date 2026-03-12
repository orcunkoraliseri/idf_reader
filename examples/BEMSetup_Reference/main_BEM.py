import os
import sys
import collections.abc
import importlib

# Monkeypatch for geomeppy compatibility with Python 3.10+
if not hasattr(collections, 'MutableSequence'):
    collections.MutableSequence = collections.abc.MutableSequence

from eSim_bem_utils import loader, visualizer, runner, read_results

# Force reload to ensure updates are picked up
importlib.reload(loader)
importlib.reload(visualizer)
importlib.reload(runner)
importlib.reload(read_results)

# --- CONFIGURATION ---
# Cross-platform EnergyPlus paths
import platform

if platform.system() == 'Darwin':  # macOS
    ENERGYPLUS_DIR = '/Applications/EnergyPlus-24-2-0'
    ENERGYPLUS_EXE = os.path.join(ENERGYPLUS_DIR, 'energyplus')
elif platform.system() == 'Windows':
    ENERGYPLUS_DIR = r'C:\EnergyPlusV24-2-0'
    ENERGYPLUS_EXE = os.path.join(ENERGYPLUS_DIR, 'energyplus.exe')
else:  # Linux or other
    ENERGYPLUS_DIR = '/usr/local/EnergyPlus-24-2-0'
    ENERGYPLUS_EXE = os.path.join(ENERGYPLUS_DIR, 'energyplus')

IDD_FILE = os.path.join(ENERGYPLUS_DIR, 'Energy+.idd')
# ---------------------

import glob

def select_weather_file(base_dir):
    """
    Lists available weather files and lets user select one.
    Returns the path to the selected weather file.
    """
    weather_dir = os.path.join(base_dir, 'WeatherFile')
    epw_files = glob.glob(os.path.join(weather_dir, '*.epw'))
    
    if not epw_files:
        print("No weather files found in WeatherFile folder!")
        return None
    
    print("\nAvailable Weather Files:")
    for i, epw in enumerate(epw_files):
        name = os.path.basename(epw)
        # Extract zone from filename if present
        zone = ""
        if "_3A" in name or "_3A." in name:
            zone = " (Zone 3A)"
        elif "_4A" in name or "_4A." in name:
            zone = " (Zone 4A)"
        print(f"  {i+1}. {name}{zone}")
    
    try:
        epw_choice = input("Select weather file number: ").strip()
        epw_idx = int(epw_choice) - 1
        if 0 <= epw_idx < len(epw_files):
            selected = epw_files[epw_idx]
            print(f"Selected: {os.path.basename(selected)}")
            return selected
        else:
            print("Invalid selection. Using default (first file).")
            return epw_files[0]
    except ValueError:
        print("Invalid input. Using default (first file).")
        return epw_files[0]


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Load Files
    print("Scanning for files...")
    pairs = loader.find_files(base_dir)
    
    if not pairs:
        print("No matching IDF and Weather files found.")
        return

    print(f"Found {len(pairs)} simulation pairs.")
    for i, p in enumerate(pairs):
        print(f"{i+1}. {p['name']} (Zone: {p['zone']})")

    # 2. User Interaction Loop
    while True:
        print("\nOptions:")
        print("1. Visualize a building")
        print("2. Run a simulation")
        print("3. Run all simulations")
        print("4. Process simulation results")
        print("5. Visualize performance results")
        print("q. Quit")
        
        choice = input("Enter choice: ").strip().lower()
        
        if choice == 'q':
            break
            
        elif choice == '1':
            idx = int(input("Enter building number to visualize: ")) - 1
            if 0 <= idx < len(pairs):
                visualizer.visualize_idf(pairs[idx]['idf'], IDD_FILE)
            else:
                print("Invalid number.")
                
        elif choice == '2':
            idx = int(input("Enter building number to simulate: ")) - 1
            if 0 <= idx < len(pairs):
                p = pairs[idx]
                
                # Select weather file
                selected_epw = select_weather_file(base_dir)
                if not selected_epw:
                    continue
                
                # Ask for number of CPUs
                max_cpus = os.cpu_count()
                try:
                    n_jobs_input = input(f"Enter number of CPUs to use (default {max_cpus}): ").strip()
                    if not n_jobs_input:
                        n_jobs = max_cpus
                    else:
                        n_jobs = int(n_jobs_input)
                except ValueError:
                    print(f"Invalid input. Using default {max_cpus}.")
                    n_jobs = max_cpus
                
                # Include weather file name in output folder for clarity
                epw_name = os.path.basename(selected_epw).replace('.epw', '')
                output_dir = os.path.join(base_dir, 'SimResults', f"{p['name'].replace('.idf', '')}_{epw_name}")
                result = runner.run_simulation(p['idf'], selected_epw, output_dir, ENERGYPLUS_EXE, n_jobs=n_jobs)
                
                # Auto-process results after simulation
                if result and result.get('success'):
                    print("\nAuto-processing simulation results...")
                    read_results.process_results(output_dir)
            else:
                print("Invalid number.")
                
        elif choice == '3':
            # Select weather file for all simulations
            selected_epw = select_weather_file(base_dir)
            if not selected_epw:
                continue
            
            confirm = input(f"This will run {len(pairs)} simulations in parallel with {os.path.basename(selected_epw)}. Continue? (y/n): ")
            if confirm.lower() == 'y':
                max_cpus = os.cpu_count() or 4
                try:
                    n_workers_input = input(f"2Max parallel simulations (default {max_cpus}): ").strip()
                    if not n_workers_input:
                        n_workers = max_cpus
                    else:
                        n_workers = int(n_workers_input)
                except ValueError:
                    print(f"Invalid input. Using default {max_cpus}.")
                    n_workers = max_cpus
                
                # Build job list for parallel execution
                epw_name = os.path.basename(selected_epw).replace('.epw', '')
                jobs = []
                for p in pairs:
                    jobs.append({
                        'idf': p['idf'],
                        'epw': selected_epw,
                        'output_dir': os.path.join(base_dir, 'SimResults', f"{p['name'].replace('.idf', '')}_{epw_name}"),
                        'name': p['name']
                    })
                
                results = runner.run_simulations_parallel(jobs, ENERGYPLUS_EXE, max_workers=n_workers)
                
                # Auto-process results for successful simulations
                if results['successful']:
                    print("\nAuto-processing results for successful simulations...")
                    for job in jobs:
                        if job['name'] in results['successful']:
                            try:
                                read_results.process_results(job['output_dir'])
                            except Exception as e:
                                print(f"Warning: Could not process results for {job['name']}: {e}")


        elif choice == '4':
            # List available result directories
            sim_results_dir = os.path.join(base_dir, 'SimResults')
            result_dirs = [d for d in os.listdir(sim_results_dir) 
                          if os.path.isdir(os.path.join(sim_results_dir, d)) 
                          and os.path.exists(os.path.join(sim_results_dir, d, 'eplusout.sql'))]
            
            if not result_dirs:
                print("No simulation results found with SQL output.")
            else:
                print("\nAvailable simulation results:")
                for i, d in enumerate(result_dirs, 1):
                    print(f"  {i}. {d}")
                idx = int(input("Enter number to process results: ")) - 1
                if 0 <= idx < len(result_dirs):
                    output_dir = os.path.join(sim_results_dir, result_dirs[idx])
                    read_results.process_results(output_dir)
                else:
                    print("Invalid number.")

        elif choice == '5':
            # List available result directories
            sim_results_dir = os.path.join(base_dir, 'SimResults')
            result_dirs = [d for d in os.listdir(sim_results_dir) 
                          if os.path.isdir(os.path.join(sim_results_dir, d)) 
                          and os.path.exists(os.path.join(sim_results_dir, d, 'eui_summary.json'))]
            
            if not result_dirs:
                print("No processed results found. Run option 4 first.")
            else:
                print("\nAvailable results to visualize:")
                for i, d in enumerate(result_dirs, 1):
                    print(f"  {i}. {d}")
                idx = int(input("Enter number to visualize: ")) - 1
                if 0 <= idx < len(result_dirs):
                    output_dir = os.path.join(sim_results_dir, result_dirs[idx])
                    read_results.visualize_eui(output_dir)
                else:
                    print("Invalid number.")

        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main()
