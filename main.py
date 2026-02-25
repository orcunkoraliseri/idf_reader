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

    args = parser.parse_args()

    # Determine output directory
    output_dir = args.output_dir or os.path.join(os.getcwd(), "outputs")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if args.idf:
        # Explicit mode: process the provided file path
        idf_path = os.path.abspath(args.idf)
        if not os.path.exists(idf_path):
            print(f"Error: File not found: {idf_path}")
            sys.exit(1)
        process_file(idf_path, output_dir)
    else:
        # Interactive mode: allow user to select files from all content subfolders
        while True:
            targets = select_idf_interactive(CONTENT_DIR)
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
