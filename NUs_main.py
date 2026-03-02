"""
NUs_main.py — Neighbourhood IDF Report Orchestrator.

Scans the neighbourhood IDF directory, processes each .idf file with
NUs_parser.parse_neighbourhood, generates an HTML report via
NUs_report.generate_neighbourhood_report, and writes the result to the
output directory.

Usage:
    python NUs_main.py
"""

# Standard library
import os
import sys

# Local
from NUs_parser import parse_neighbourhood
from NUs_report import generate_neighbourhood_report

# ---------------------------------------------------------------------------
# Paths (relative to this script's directory)
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(_SCRIPT_DIR, "Content", "neighbourhoods")
OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "outputs", "neighbourhoods")


def process_idf(idf_path: str, output_dir: str) -> None:
    """Parse one neighbourhood IDF and write its HTML report to disk.

    Args:
        idf_path: Absolute path to the neighbourhood .idf file.
        output_dir: Directory where the resulting HTML file will be saved.

    Returns:
        None
    """
    filename = os.path.splitext(os.path.basename(idf_path))[0]
    print(f"\n{'=' * 60}")
    print(f"Processing: {os.path.basename(idf_path)}")
    print(f"{'=' * 60}")

    try:
        summary = parse_neighbourhood(idf_path)
    except Exception as exc:
        print(f"  ERROR parsing IDF: {exc}")
        return

    print(f"  Building name : {summary.building_name}")
    print(f"  Total zones   : {summary.total_zones}")
    print(f"  Building types detected:")
    for btype, count in sorted(summary.building_counts.items()):
        print(f"    • {btype}: {count}")

    try:
        html_content = generate_neighbourhood_report(
            idf_path=summary.idf_path,
            building_name=summary.building_name,
            building_counts=summary.building_counts,
            total_zones=summary.total_zones,
        )
    except Exception as exc:
        print(f"  ERROR generating report: {exc}")
        return

    # Sanitise the filename to remove characters that are problematic on
    # most operating systems while still preserving readability.
    safe_name = filename.replace(" ", "_").replace("+", "and")
    out_path = os.path.join(output_dir, f"{safe_name}.html")

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html_content)

    print(f"  ✓ Report saved → {out_path}")


def main() -> None:
    """Discover neighbourhood IDFs and generate HTML reports for all of them.

    Returns:
        None
    """
    if not os.path.isdir(INPUT_DIR):
        print(f"ERROR: Input directory not found:\n  {INPUT_DIR}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    idf_files = [
        os.path.join(INPUT_DIR, f)
        for f in sorted(os.listdir(INPUT_DIR))
        if f.lower().endswith(".idf")
    ]

    if not idf_files:
        print(f"No .idf files found in {INPUT_DIR}")
        sys.exit(0)

    print(f"Found {len(idf_files)} neighbourhood IDF file(s).")
    print(f"Output directory: {OUTPUT_DIR}\n")

    for idf_path in idf_files:
        process_idf(idf_path, OUTPUT_DIR)

    print(f"\n{'=' * 60}")
    print(f"Done. {len(idf_files)} report(s) written to: {OUTPUT_DIR}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
