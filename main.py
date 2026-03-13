from __future__ import annotations

"""
Main Entry Point for the IDF Zone Metadata Extractor.

This script orchestrates the parsing of an EnergyPlus IDF file, geometric
calculations, data extraction, and report generation by utilizing modular
processors.
"""

import argparse
import os
import sys

from idf_processor import process_file, select_idf_interactive
from idf_comparator import compare_idfs, print_summary
from compare_report_generator import generate_compare_report


# The base directory containing IDF subfolders (e.g., ASHRAE901_STD2022, others)
CONTENT_DIR = os.path.join(os.path.dirname(__file__), "Content")


def main() -> None:
    """Main entry point for extracting and analyzing IDF metadata.

    This function parses command-line arguments and determines whether to run
    in interactive mode or process a specific file provided as an argument.
    It discovers IDF files in the Content directory and its subdirectories.
    """
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
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("REFERENCE_IDF", "COMPARE_IDF"),
        help="Compare two IDF files. Pass the trusted reference first, then the file to question.",
    )

    args = parser.parse_args()

    # Base output directory
    base_output_dir = args.output_dir or os.path.join(os.getcwd(), "outputs")
    
    def get_output_dir_for_idf(idf_path: str) -> str:
        """Helper to determine the output directory based on the IDF source folder."""
        # Normalize to forward slashes for cross-platform comparison
        abs_idf = os.path.abspath(idf_path).replace("\\", "/")
        # Selective output routing based on source folder
        if "Content/CHV_buildings" in abs_idf:
            target = os.path.join(base_output_dir, "output_CHV_buildings")
        elif "Content/neighbourhoods" in abs_idf:
            target = os.path.join(base_output_dir, "neighbourhoods")
        elif "Content/low_rise_Res" in abs_idf:
            target = os.path.join(base_output_dir, "low_rise_Res")
        elif "Content/others" in abs_idf:
            target = os.path.join(base_output_dir, "others")
        else:
            target = base_output_dir
            
        if not os.path.exists(target):
            os.makedirs(target)
        return target

    if args.compare:
        # Compare mode: diff two IDF files and generate HTML report
        path_a = os.path.abspath(args.compare[0])
        path_b = os.path.abspath(args.compare[1])
        for p in (path_a, path_b):
            if not os.path.exists(p):
                print(f"Error: File not found: {p}")
                sys.exit(1)

        print(f"\nComparing IDF files...")
        print(f"  Reference : {path_a}")
        print(f"  Compare   : {path_b}")

        result = compare_idfs(path_a, path_b)
        print_summary(result)

        name_a = os.path.splitext(os.path.basename(path_a))[0]
        name_b = os.path.splitext(os.path.basename(path_b))[0]
        report_name = f"{name_a}_vs_{name_b}_comparison.html"
        output_dir = os.path.join(
            args.output_dir or os.path.join(os.getcwd(), "outputs"),
            "output_comparator",
        )
        os.makedirs(output_dir, exist_ok=True)
        generate_compare_report(result, os.path.join(output_dir, report_name))

    elif args.idf:
        # Explicit mode: process the provided file path
        idf_path = os.path.abspath(args.idf)
        if not os.path.exists(idf_path):
            print(f"Error: File not found: {idf_path}")
            sys.exit(1)
            
        output_dir = get_output_dir_for_idf(idf_path)
        process_file(idf_path, output_dir)
    else:
        # Interactive mode: allow user to select files from all content subfolders
        while True:
            targets = select_idf_interactive(CONTENT_DIR)
            if not targets:
                break

            for target in targets:
                output_dir = get_output_dir_for_idf(target)
                process_file(target, output_dir)

            print("\n" + "=" * 50)
            print("Processing complete.")
            print("=" * 50)

    print("\nExecution completed successfully.")



if __name__ == "__main__":
    main()
