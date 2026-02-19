from __future__ import annotations

"""
Reporting Module for IDF Zone Metadata.

This module provides functions to format the extracted zone metadata into
CSV, Markdown, and HTML documents, including summary tables and building models.
"""

import csv
import datetime


def generate_reports(
    zone_data: list[dict], output_base_path: str, viz_b64: str | None = None
):
    """Generates CSV, Markdown, and HTML reports.

    Args:
        zone_data: A list of dictionaries, each containing metadata for a zone.
        output_base_path: The base filename (without extension) for the reports.
        viz_b64: Optional base64-encoded PNG of the 3D visualization.
    """
    if not zone_data:
        print("No zone data to report.")
        return

    csv_path = f"{output_base_path}.csv"
    md_path = f"{output_base_path}.md"

    # Define headers
    headers = [
        "Zone",
        "Floor Area [m2]",
        "Multiplier",
        "Occupancy [people/m2]",
        "Lighting [W/m2]",
        "Electric Equipment [W/m2]",
        "Gas Equipment [W/m2]",
        "SHW [L/h.m2]",
        "Infiltration [m3/s.m2 facade]",
        "Ventilation [m3/s.person]",
        "Ventilation [m3/s.m2]",
        "Htg Setpoint [C]",
        "Clg Setpoint [C]",
    ]

    # Map internal keys to headers
    key_map = {
        "Zone": "name",
        "Floor Area [m2]": "floor_area",
        "Multiplier": "multiplier",
        "Occupancy [people/m2]": "people",
        "Lighting [W/m2]": "lights",
        "Electric Equipment [W/m2]": "electric",
        "Gas Equipment [W/m2]": "gas",
        "SHW [L/h.m2]": "water",
        "Infiltration [m3/s.m2 facade]": "infiltration",
        "Ventilation [m3/s.person]": "vent_person",
        "Ventilation [m3/s.m2]": "vent_area",
        "Htg Setpoint [C]": "htg_sp",
        "Clg Setpoint [C]": "clg_sp",
    }

    # 1. Generate CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for zone in zone_data:
            row = {h: zone.get(key_map[h], 0) for h in headers}
            writer.writerow(row)

    # 2. Generate Markdown
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Zone Metadata Summary Report\n\n")
        f.write(
            f"**Generated on:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )

        # Write table header
        f.write("| " + " | ".join(headers) + " |\n")
        f.write("| " + " | ".join(["---"] * len(headers)) + " |\n")

        # Write table rows
        for zone in zone_data:
            row_vals = []
            for h in headers:
                val = zone.get(key_map[h], 0)
                if isinstance(val, float):
                    row_vals.append(f"{val:.4f}")
                else:
                    row_vals.append(str(val))
            f.write("| " + " | ".join(row_vals) + " |\n")

    # 3. Generate HTML
    html_path = f"{output_base_path}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(generate_html_content(zone_data, headers, key_map, viz_b64))

    print(f"Reports generated:\n  - {csv_path}\n  - {md_path}\n  - {html_path}")


def generate_html_content(
    zone_data: list[dict], headers: list[str], key_map: dict, viz_b64: str | None = None
) -> str:
    """Creates a premium HTML document with a styled table."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Visualization Section
    viz_html = ""
    if viz_b64:
        viz_html = f"""
        <div class="card viz-container">
            <div class="card-header">3D Building Geometry</div>
            <img src="data:image/png;base64,{viz_b64}" alt="3D Building Model">
        </div>
        """
    else:
        viz_html = """
        <div class="card viz-placeholder">
            <span class="warning-icon">⚠</span>
            3D visualization unavailable (eppy not installed or IDD_FILE environment variable not set).
        </div>
        """

    rows_html = ""
    for zone in zone_data:
        cells_html = ""
        for h in headers:
            val = zone.get(key_map[h], 0)
            formatted_val = f"{val:.4f}" if isinstance(val, float) else str(val)
            cells_html += f"<td>{formatted_val}</td>"
        rows_html += f"<tr>{cells_html}</tr>"

    headers_html = "".join([f"<th>{h}</th>" for h in headers])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zone Metadata Report</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Outfit:wght@600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #6366f1;
            --bg: #0f172a;
            --card-bg: #1e293b;
            --text: #f8fafc;
            --text-dim: #94a3b8;
            --border: #334155;
            --accent: #818cf8;
        }}
        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 40px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(to right, #818cf8, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .metadata {{
            color: var(--text-dim);
            margin-bottom: 2rem;
            font-size: 0.9rem;
        }}
        .card {{
            background: var(--card-bg);
            border-radius: 16px;
            border: 1px solid var(--border);
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
            margin-bottom: 2rem;
            overflow: hidden;
        }}
        .card-header {{
            padding: 16px 24px;
            background: #27354d;
            border-bottom: 1px solid var(--border);
            font-family: 'Outfit', sans-serif;
            color: var(--accent);
            font-size: 1.1rem;
        }}
        .viz-container {{
            text-align: center;
            padding-bottom: 20px;
        }}
        .viz-container img {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            margin-top: 10px;
        }}
        .viz-placeholder {{
            padding: 40px;
            text-align: center;
            color: var(--text-dim);
            font-style: italic;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
        }}
        .warning-icon {{
            font-size: 1.5rem;
            color: #fbbf24;
        }}
        .table-container {{
            overflow: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
            text-align: left;
        }}
        th {{
            background: #27354d;
            padding: 16px;
            font-weight: 600;
            color: var(--accent);
            position: sticky;
            top: 0;
            border-bottom: 2px solid var(--border);
            white-space: nowrap;
        }}
        td {{
            padding: 14px 16px;
            border-bottom: 1px solid var(--border);
            color: #e2e8f0;
        }}
        tr:hover td {{
            background: rgba(99, 102, 241, 0.05);
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        /* Minimalist scrollbar */
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-track {{ background: var(--bg); }}
        ::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: var(--accent); }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Zone Metadata Summary</h1>
        <div class="metadata">Generated on: {timestamp}</div>
        
        {viz_html}

        <div class="card">
            <div class="card-header">Zone Metadata Detail</div>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>{headers_html}</tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>"""
