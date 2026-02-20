from __future__ import annotations

"""
Main Entry Point for the IDF Zone Metadata Extractor.

This script orchestrates the parsing of an EnergyPlus IDF file, geometric
calculations, data extraction, and report generation.
"""

import argparse
import os
import sys

from extractors import (
    extract_infiltration,
    extract_loads,
    extract_people,
    extract_process_loads,
    extract_thermostats,
    extract_ventilation,
    extract_water_use,
    extract_hvac_systems,
)
from geometry import get_zone_geometry
from idf_parser import parse_idf
from report_generator import generate_reports
from visualizer_adapter import render_idf_to_base64


DEFAULT_IDF_DIR = os.path.join(os.path.dirname(__file__), "Content", "ASHRAE901_STD2022")


def process_file(idf_path: str, output_dir: str):
    """Parses a single IDF file and generates reports."""
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

    # NEW: Generate 3D Visualization
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

    generate_reports(summarized_data, output_base, viz_b64, hvac_data)


def select_idf_interactive(idf_dir: str) -> list[str]:
    """Displays a menu to select one or all IDF files from a directory."""
    if not os.path.exists(idf_dir):
        print(f"Error: IDF directory not found: {idf_dir}")
        return []

    files = sorted([f for f in os.listdir(idf_dir) if f.lower().endswith(".idf")])
    if not files:
        print(f"No .idf files found in {idf_dir}")
        return []

    print(f"\nFound {len(files)} IDF files in {os.path.basename(idf_dir)}/:\n")
    for i, f in enumerate(files, 1):
        print(f" [{i:2}]  {f}")

    print("\n [a]   Process ALL files")
    print(" [q]   Quit")

    while True:
        choice = input(f"\nSelect a file (1-{len(files)}, a, q): ").strip().lower()
        if choice == "q":
            sys.exit(0)
        if choice == "a":
            return [os.path.join(idf_dir, f) for f in files]

        try:
            idx = int(choice)
            if 1 <= idx <= len(files):
                return [os.path.join(idf_dir, files[idx - 1])]
        except ValueError:
            pass

        print("Invalid selection. Please try again.")


def main():
    """Main function to parse IDF and generate reports."""
    parser = argparse.ArgumentParser(
        description="Extract and analyze zone-level metadata from an EnergyPlus .idf file."
    )
    parser.add_argument(
        "--idf",
        required=False,
        help="Path to the EnergyPlus .idf file. If omitted, starts interactive mode.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory to save the reports. Defaults to 'outputs' in project folder.",
    )

    args = parser.parse_args()

    output_dir = args.output_dir or os.path.join(os.getcwd(), "outputs")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if args.idf:
        # Explicit mode
        idf_path = os.path.abspath(args.idf)
        if not os.path.exists(idf_path):
            print(f"Error: File not found: {idf_path}")
            sys.exit(1)
        process_file(idf_path, output_dir)
    else:
        # Interactive mode loop
        while True:
            targets = select_idf_interactive(DEFAULT_IDF_DIR)
            if not targets:
                break

            for target in targets:
                process_file(target, output_dir)

            print("\n" + "=" * 50)
            print("Processing complete.")
            print("=" * 50)

    print("\nExecution completed successfully.")


if __name__ == "__main__":
    main()
