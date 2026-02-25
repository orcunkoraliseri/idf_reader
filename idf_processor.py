from __future__ import annotations

import os
import sys

from extractors import (
    extract_hvac_systems,
    extract_infiltration,
    extract_loads,
    extract_people,
    extract_process_loads,
    extract_thermostats,
    extract_ventilation,
    extract_water_use,
)
from construction_extractor import extract_baseline_constructions
from geometry import get_zone_geometry
from hvac_validator import validate_hvac_results
from idf_parser import parse_idf
from process_load_extractor import extract_building_process_loads
from report_generator import generate_reports
from schedule_extractor import extract_zone_schedules
from visualizer_adapter import render_idf_to_base64


def find_idf_files(base_dir: str) -> list[tuple[str, str]]:
    """Recursively find all .idf files in the given directory.

    Args:
        base_dir: The directory to search for IDF files.

    Returns:
        A list of tuples, each containing (relative_path, full_path).
    """
    idf_files: list[tuple[str, str]] = []
    if not os.path.exists(base_dir):
        return idf_files

    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.lower().endswith(".idf") and file.lower() != "construction_baseline.idf":
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, base_dir)
                idf_files.append((rel_path, full_path))

    idf_files.sort(key=lambda x: x[0].lower())
    return idf_files


def select_idf_interactive(base_dir: str) -> list[str]:
    """Provide an interactive menu for selecting IDF files.

    Args:
        base_dir: The base directory where IDF files are searched.

    Returns:
        A list of absolute paths to the selected IDF files.
    """
    idf_files = find_idf_files(base_dir)
    if not idf_files:
        print(f"No .idf files found in {base_dir}")
        return []

    print(f"\nFound {len(idf_files)} IDF files in {os.path.basename(base_dir)}/:\n")
    for i, (rel_path, _) in enumerate(idf_files, 1):
        print(f" [{i:2}]  {rel_path}")

    print("\n [a]   Process ALL files")
    print(" [q]   Quit")

    while True:
        prompt = f"\nSelect a file (1-{len(idf_files)}, a, q): "
        choice = input(prompt).strip().lower()
        if choice == "q":
            sys.exit(0)
        if choice == "a":
            return [f[1] for f in idf_files]

        try:
            idx = int(choice)
            if 1 <= idx <= len(idf_files):
                return [idf_files[idx - 1][1]]
        except ValueError:
            pass

        print("Invalid selection. Please try again.")


def process_file(idf_path: str, output_dir: str) -> None:
    """Parse a single IDF file and generate metadata reports.

    Args:
        idf_path: The absolute path to the .idf file.
        output_dir: The directory where the reports will be saved.
    """
    file_name = os.path.splitext(os.path.basename(idf_path))[0]
    output_base = os.path.join(output_dir, f"{file_name}_metadata")

    print(f"\nProcessing: {file_name}...")
    try:
        idf_data = parse_idf(idf_path)
    except Exception as e:
        print(f"  Failed to parse IDF: {e}")
        return

    zone_geo = get_zone_geometry(idf_data)
    if not zone_geo:
        print("  No zones found in the IDF file.")
        return

    people = extract_people(idf_data, zone_geo)
    lights = extract_loads(idf_data, zone_geo, "LIGHTS")
    electric = extract_loads(idf_data, zone_geo, "ELECTRICEQUIPMENT")
    gas = extract_loads(idf_data, zone_geo, "GASEQUIPMENT")
    water = extract_water_use(idf_data, zone_geo)
    infiltration = extract_infiltration(idf_data, zone_geo)
    ventilation = extract_ventilation(idf_data, zone_geo)
    thermostats = extract_thermostats(idf_data, zone_geo)
    process = extract_process_loads(idf_data, zone_geo)
    hvac_data = extract_hvac_systems(idf_data, list(zone_geo.keys()))
    
    # Extract building-level process loads (Exterior lights, elevators, refrig)
    building_process_loads = extract_building_process_loads(idf_data)

    # Extract zone schedule assignments (Occupancy, Lighting, etc.)
    schedule_assignments = extract_zone_schedules(idf_data)

    # Generate 3D Visualization
    print("Generating 3D visualization...")
    viz_b64 = render_idf_to_base64(idf_path)

    summarized_data = []
    for zone_name in sorted(zone_geo.keys()):
        geo = zone_geo[zone_name]
        summarized_data.append(
            {
                "name": zone_name,
                "floor_area": geo["floor_area"],
                "multiplier": geo["multiplier"],
                "people": people.get(zone_name, 0.0),
                "lights": lights.get(zone_name, 0.0),
                "electric": electric.get(zone_name, 0.0),
                "gas": gas.get(zone_name, 0.0),
                "water": water.get(zone_name, 0.0),
                "infiltration": infiltration.get(zone_name, 0.0),
                "vent_person": ventilation.get(zone_name, {}).get("per_person", 0.0),
                "vent_area": ventilation.get(zone_name, {}).get("per_area", 0.0),
                "htg_sp": thermostats.get(zone_name, {}).get("heating", 0.0),
                "clg_sp": thermostats.get(zone_name, {}).get("cooling", 0.0),
                "process": process.get(zone_name, 0.0),
            }
        )

    # Extract baseline constructions
    construction_data = None
    baseline_path = os.path.join(os.path.dirname(__file__), "Content", "construction", "construction_baseline.idf")
    if os.path.exists(baseline_path):
        try:
            construction_data = extract_baseline_constructions(baseline_path)
        except Exception as e:
            print(f"  Warning: Could not extract baseline constructions: {e}")

    generate_reports(
        summarized_data, output_base, viz_b64, hvac_data, 
        construction_data, building_process_loads, schedule_assignments
    )


    # Validate extracted HVAC data against Honeybee template definitions
    validate_hvac_results(hvac_data, file_name)
