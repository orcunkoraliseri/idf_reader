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
    """Generates CSV, Markdown, and HTML reports with zone deduplication.

    Args:
        zone_data: A list of dictionaries, each containing metadata for a zone.
        output_base_path: The base filename (without extension) for the reports.
        viz_b64: Optional base64-encoded PNG of the 3D visualization.
    """
    if not zone_data:
        print("No zone data to report.")
        return

    # 1. Define internal key map and display headers
    key_map = {
        "Zone": "name",
        "Floor Area [m2]": "floor_area",
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
    data_headers = list(key_map.keys())[1:]  # Everything except "Zone"

    # 2. Extract deduplication groupings
    import re

    def get_base_name(name: str) -> str:
        # Regex to strip common EnergyPlus prototype suffixes like _FLR_1, _Pod_2, _ZN_1, _1, etc.
        # We look for underscores followed by typical keywords and digits at the end.
        return re.sub(r"(_FLR|_Pod|_ZN|_\d)+\d*$", "", name.strip())

    # Build groups of zones that share a base name
    groups: dict[str, list[dict]] = {}
    for zone in zone_data:
        base = get_base_name(zone["name"])
        groups.setdefault(base, []).append(zone)

    # 3. Process groups to collapse identical rows
    final_rows: list[dict] = []
    for base_name, group in groups.items():
        if len(group) == 1:
            row = group[0].copy()
            row["Count"] = 1
            final_rows.append(row)
            continue

        # Check if all data values (except zone name) are identical across the group
        # This preserves variations (e.g. Mech rooms with different loads) as separate rows.
        unique_variants: list[tuple[dict, int]] = []  # [(data_dict, count)]

        for zone in group:
            # We must use the internal keys (the values of key_map) to look into the zone dict
            internal_data_keys = [key_map[h] for h in data_headers]
            data_fingerprint = {k: zone.get(k, 0) for k in internal_data_keys}
            
            # Find matching existing variant
            found = False
            for idx, (variant, count) in enumerate(unique_variants):
                match = True
                for k in internal_data_keys:
                    v1 = variant.get(k, 0)
                    v2 = data_fingerprint.get(k, 0)
                    
                    # Numeric comparison with tolerance
                    if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                        if abs(v1 - v2) > 1e-6:
                            match = False
                            break
                    else:
                        # String or None comparison
                        if v1 != v2:
                            match = False
                            break
                
                if match:
                    unique_variants[idx] = (variant, count + 1)
                    found = True
                    break
            
            if not found:
                row_copy = zone.copy()
                unique_variants.append((row_copy, 1))

        # If a group resulted in only ONE variant, we use the base name for the row
        if len(unique_variants) == 1:
            row, count = unique_variants[0]
            row["name"] = base_name  # Use the simplified base name (e.g. "Classroom")
            row["Count"] = count
            final_rows.append(row)
        else:
            # Variations detected; keep individual zone names and report separately
            for row, count in unique_variants:
                row["Count"] = 1
                final_rows.append(row)

    # 4. Final output setup
    headers = ["Zone", "Count"] + data_headers
    csv_path = f"{output_base_path}.csv"
    md_path = f"{output_base_path}.md"

    # 5. Generate CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for zone in final_rows:
            row = {"Zone": zone["name"], "Count": zone["Count"]}
            for h in data_headers:
                row[h] = zone.get(key_map[h], 0)
            writer.writerow(row)

    # 6. Generate Markdown
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Zone Metadata Summary Report\n\n")
        f.write(f"**Generated on:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("| " + " | ".join(headers) + " |\n")
        f.write("| " + " | ".join(["---"] * len(headers)) + " |\n")
        for zone in final_rows:
            row_vals = [zone["name"], str(zone["Count"])]
            for h in data_headers:
                val = zone.get(key_map[h], 0)
                row_vals.append(f"{val:.4f}" if isinstance(val, float) else str(val))
            f.write("| " + " | ".join(row_vals) + " |\n")

    # 7. Generate HTML
    html_path = f"{output_base_path}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        # Re-build key_map for HTML (adding Count)
        html_key_map = {"Zone": "name", "Count": "Count"}
        for h in data_headers:
            html_key_map[h] = key_map[h]
        f.write(generate_html_content(final_rows, headers, html_key_map, viz_b64))

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
            padding: 10px 8px;
            font-weight: 600;
            color: var(--accent);
            position: sticky;
            top: 0;
            border-bottom: 2px solid var(--border);
            vertical-align: bottom;
            min-width: 80px;
            max-width: 120px;
            line-height: 1.2;
        }}
        td {{
            padding: 10px 8px;
            border-bottom: 1px solid var(--border);
            color: #e2e8f0;
        }}
        /* Specific scaling for the Count column */
        th:nth-child(2), td:nth-child(2) {{
            min-width: 40px !important;
            max-width: 60px !important;
            text-align: center;
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
