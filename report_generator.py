from __future__ import annotations

"""
Reporting Module for IDF Zone Metadata.

This module provides functions to format the extracted zone metadata into
a polished HTML report, including summary tables and building models.
"""

import datetime


def _format_val(val: any, precision: int = 4) -> str:
    """Intelligently format a value: round to specified decimals and strip trailing zeros.

    Args:
        val: The value to format (int, float, or other).
        precision: Number of decimal places.

    Returns:
        A cleaned string representation.
    """
    if not isinstance(val, (int, float)):
        return str(val)

    # Use precision decimals max, then strip trailing zeros and potential trailing dot
    format_str = f"{{:.{precision}f}}"
    s = format_str.format(val)
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s if s else "0"



def _get_base_name(name: str) -> str:
    """Extracts the base name of a zone by stripping typical indices and elevation suffixes."""
    import re
    # 1. Strip typical pod/floor/zone indices
    base = re.sub(r"(_FLR|_Pod|_ZN|_\d)+\d*$", "", name.strip())
    # 2. Aggressively strip elevation keywords common in prototype buildings
    base = re.sub(r"(_top|_mid|_bot|_bottom|_top floor|_mid floor|_bottom floor)$", "", base, flags=re.IGNORECASE)
    # 3. Strip any remaining trailing underscores or whitespaces
    return base.rstrip("_ ").strip()


def _collapse_rows(
    groups: dict[str, list[dict]], comparison_keys: list[str], numeric_tolerance: float = 1e-3
) -> list[dict]:
    """Collapses identical rows within groups and adds a 'Count' field."""
    final_rows: list[dict] = []
    for base_name, group in groups.items():
        if len(group) == 1:
            row = group[0].copy()
            row["Count"] = 1
            final_rows.append(row)
            continue

        unique_variants: list[tuple[dict, int]] = []  # [(data_dict, count)]

        for item in group:
            found = False
            for idx, (variant, count) in enumerate(unique_variants):
                match = True
                for k in comparison_keys:
                    v1 = variant.get(k, 0)
                    v2 = item.get(k, 0)

                    if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                        if abs(v1 - v2) > numeric_tolerance:
                            match = False
                            break
                    elif v1 != v2:
                        match = False
                        break

                if match:
                    # Specific to main zone_data: track floor_area variations within a collapsed cluster
                    if "floor_area" in item and "floor_area" in variant:
                        if abs(variant["floor_area"] - item["floor_area"]) > numeric_tolerance:
                            variant["floor_area_varies"] = True
                    
                    unique_variants[idx] = (variant, count + 1)
                    found = True
                    break

            if not found:
                item_copy = item.copy()
                if "floor_area" in item_copy:
                    item_copy["floor_area_varies"] = False
                unique_variants.append((item_copy, 1))

        if len(unique_variants) == 1:
            row, count = unique_variants[0]
            row["name"] = base_name
            row["Count"] = count
            final_rows.append(row)
        else:
            for row, count in unique_variants:
                row["Count"] = 1
                final_rows.append(row)
    return final_rows


def _build_construction_html(construction_data: list[dict]) -> str:
    """Creates the 'construction' table matching the user's specialized layout with theme colors."""
    if not construction_data:
        return ""

    # Determine max layers for row iteration
    max_layers = max(len(c["layers"]) for c in construction_data)

    # 1. Surface Headers
    header_cells = ""
    for c in construction_data:
        header_cells += f'<th colspan="2" style="background:#27354d; color:var(--accent); text-align:center; border: 1px solid var(--border);">{c["label"]}</th>'

    # 2. Metric Row (R-values / U-values)
    metric_cells = ""
    for c in construction_data:
        val = _format_val(c["metric_value"])
        metric_cells += (
            f'<td style="font-weight:600; background:#2d3a4f; color:var(--accent); border: 1px solid var(--border);">{c["metric_label"]}</td>'
            f'<td style="background:var(--card-bg); color:var(--text); border: 1px solid var(--border);">{val}</td>'
        )

    # 3. Layer Rows
    layer_rows_html = ""
    for i in range(max_layers):
        cells = ""
        for c in construction_data:
            label = "Layers (outside to inside)" if i == 0 else ""
            layer_name = c["layers"][i] if i < len(c["layers"]) else ""
            # Label side (left col of each pair)
            label_bg = "#2d3a4f" if label else "transparent"
            cells += (
                f'<td style="background:{label_bg}; color:var(--text-dim); border: 1px solid var(--border); font-size:0.75rem;">{label}</td>'
                f'<td style="background:var(--card-bg); color:var(--text); border: 1px solid var(--border);">{layer_name}</td>'
            )
        layer_rows_html += f"<tr>{cells}</tr>"

    return f"""
    <div class="card">
        <div class="card-header" style="text-align:center;">construction</div>
        <div class="table-container">
            <style>
                .const-table {{ border-collapse: collapse; width: 100%; border: 1px solid var(--border); }}
                .const-table th, .const-table td {{ padding: 10px 8px !important; }}
            </style>
            <table class="const-table">
                <thead>
                    <tr>{header_cells}</tr>
                </thead>
                <tbody>
                    <tr>{metric_cells}</tr>
                    {layer_rows_html}
                </tbody>
            </table>
        </div>
    </div>
    """


def _build_schedule_html(schedule_data: list[dict]) -> str:
    """Creates the 'Zone Schedule Assignments' table."""
    if not schedule_data:
        return ""

    rows_html = ""
    for item in schedule_data:
        # Group zones by base name for compact display
        from collections import defaultdict
        groups = defaultdict(int)
        for z in item["zones"]:
            base = _get_base_name(z)
            groups[base] += 1
        
        # Format: BaseName1, BaseName2 (xCount)
        zone_list = []
        total_count = 0
        for base, count in sorted(groups.items()):
            zone_list.append(base)
            total_count += count
        
        zone_str = f"{', '.join(zone_list)} (×{total_count})"
        
        rows_html += f"""
        <tr>
            <td style="font-weight:600; color:var(--accent);">{item['load_type']}</td>
            <td class="wrap-txt">{item['schedule_name']}</td>
            <td class="wrap-txt">{zone_str}</td>
        </tr>
        """

    return f"""
    <div class="card">
        <div class="card-header">Zone Schedule Assignments</div>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th style="width:120px;">Load Type</th>
                        <th style="min-width:1200px; width:1200px;">Schedule Name</th>
                        <th>Zones (Count)</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
    </div>
    """


def _build_process_loads_html(process_data: list[dict]) -> str:
    """Creates the 'Building Process Loads' table."""
    if not process_data:
        return ""

    rows_html = ""
    for item in process_data:
        zone = item.get("zone") or "-"
        power = _format_val(item.get("power_w", 0))
        rows_html += f"""
        <tr>
            <td>{item.get('category')}</td>
            <td class="wrap-txt">{item.get('name')}</td>
            <td>{power}</td>
            <td>{zone}</td>
            <td>{item.get('subcategory')}</td>
            <td>{item.get('details')}</td>
        </tr>
        """

    return f"""
    <div class="card">
        <div class="card-header">Building Process Loads</div>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>Name</th>
                        <th>Power [W]</th>
                        <th>Zone Location</th>
                        <th>Subcategory</th>
                        <th>Details</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
    </div>
    """


def _build_natural_ventilation_html(natural_vent_data: dict[str, list[dict]]) -> str:
    """Creates the 'Natural Ventilation Parameters' table."""
    if not natural_vent_data:
        return ""

    rows_html = ""
    # Only show zones that actually have natural ventilation
    for zone_name in sorted(natural_vent_data.keys()):
        objs = natural_vent_data[zone_name]
        if not objs:
            continue
            
        for obj in objs:
            rows_html += f"""
            <tr>
                <td class="wrap-txt">{zone_name}</td>
                <td class="wrap-txt">{obj['name']}</td>
                <td>{_format_val(obj['opening_area'])}</td>
                <td class="wrap-txt">{obj['schedule']}</td>
                <td>{_format_val(obj['min_in_temp'])}</td>
                <td>{_format_val(obj['max_in_temp'])}</td>
                <td>{_format_val(obj['min_out_temp'])}</td>
                <td>{_format_val(obj['max_out_temp'])}</td>
            </tr>
            """

    if not rows_html:
        return ""

    return f"""
    <div class="card">
        <div class="card-header">Natural Ventilation Parameters</div>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Zone</th>
                        <th>Object Name</th>
                        <th>Opening Area [m2]</th>
                        <th>Schedule</th>
                        <th>Min Indoor Temp [C]</th>
                        <th>Max Indoor Temp [C]</th>
                        <th>Min Outdoor Temp [C]</th>
                        <th>Max Outdoor Temp [C]</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
    </div>
    """


def generate_reports(
    zone_data: list[dict],
    output_base_path: str,
    viz_b64: str | None = None,
    hvac_data: dict[str, dict[str, str]] | None = None,
    construction_data: list[dict] | None = None,
    process_data: list[dict] | None = None,
    schedule_data: list[dict] | None = None,
    natural_vent_data: dict[str, list[dict]] | None = None,
):

    """Generates CSV, Markdown, and HTML reports with zone deduplication.

    Args:
        zone_data: A list of dictionaries, each containing metadata for a zone.
        output_base_path: The base filename (without extension) for the reports.
        viz_b64: Optional base64-encoded PNG of the 3D visualization.
        hvac_data: Optional dictionary containing HVAC metadata per zone.
        construction_data: Optional list of construction details for the baseline.
        process_data: Optional list of building-level process loads.
        schedule_data: Optional list of zone schedule assignments.
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
        "SHW Target Temp [C]": "water_temp",
        "Infiltration [m3/s.m2 facade]": "infiltration",
        "Ventilation [m3/s.person]": "vent_person",
        "Ventilation [m3/s.m2]": "vent_area",
        "Ventilation [ACH]": "vent_ach",
        "Htg Setpoint [C]": "htg_sp",
        "Clg Setpoint [C]": "clg_sp",
    }
    data_headers = list(key_map.keys())[1:]  # Everything except "Zone"

    # 2. Process Zone Data Deduplication
    groups: dict[str, list[dict]] = {}
    for zone in zone_data:
        base = _get_base_name(zone["name"])
        groups.setdefault(base, []).append(zone)

    internal_data_keys = [key_map[h] for h in data_headers]
    comparison_keys = [k for k in internal_data_keys if k != "floor_area"]
    final_rows = _collapse_rows(groups, comparison_keys)

    # 3. Process HVAC Data Deduplication
    final_hvac_rows: list[dict] = []
    if hvac_data:
        hvac_list = []
        for z, data in hvac_data.items():
            row = data.copy()
            row["name"] = z
            hvac_list.append(row)

        hvac_groups: dict[str, list[dict]] = {}
        for h in hvac_list:
            base = _get_base_name(h["name"])
            hvac_groups.setdefault(base, []).append(h)

        final_hvac_rows = _collapse_rows(hvac_groups, ["template", "dcv", "economizer"])

    # 4. Final output setup
    headers = ["Zone", "Count"] + data_headers
    html_path = f"{output_base_path}.html"

    # 5. Generate HTML
    with open(html_path, "w", encoding="utf-8") as f:
        # Re-build key_map for HTML (adding Count)
        html_key_map = {"Zone": "name", "Count": "Count"}
        for h in data_headers:
            html_key_map[h] = key_map[h]
        f.write(generate_html_content(
            final_rows, headers, html_key_map, viz_b64, 
            final_hvac_rows, construction_data, process_data, schedule_data,
            natural_vent_data
        ))

    print(f"Report generated:\n  - {html_path}")


def generate_html_content(
    zone_data: list[dict],
    headers: list[str],
    key_map: dict,
    viz_b64: str | None = None,
    hvac_data: list[dict] | None = None,
    construction_data: list[dict] | None = None,
    process_data: list[dict] | None = None,
    schedule_data: list[dict] | None = None,
    natural_vent_data: dict[str, list[dict]] | None = None,
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
            # Use 5 decimals for Infiltration and Ventilation, otherwise 4
            precision = 5 if ("Infiltration" in h or "Ventilation" in h) else 4
            formatted_val = _format_val(val, precision)
            cls = ' class="wrap-txt"' if h in ["Zone", "Thermal Zone"] else ""
            cells_html += f"<td{cls}>{formatted_val}</td>"
        rows_html += f"<tr>{cells_html}</tr>"

    headers_html = "".join([f"<th>{h}</th>" for h in headers])

    hvac_html = ""
    if hvac_data:
        hvac_headers = ["Thermal Zone", "Count", "Honeybee HVAC Template", "DCV Status", "Economizer Configuration"]
        hvac_rows = ""
        for row in hvac_data:
            hvac_rows += f"<tr><td class=\"wrap-txt\">{row['name']}</td><td>{row['Count']}</td><td>{row.get('template', 'Unknown')}</td><td>{row.get('dcv', 'Unknown')}</td><td>{row.get('economizer', 'Unknown')}</td></tr>"
        
        hvac_html = f"""
        <div class="card">
            <div class="card-header">HVAC System Metadata</div>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>{"".join([f"<th>{h}</th>" for h in hvac_headers])}</tr>
                    </thead>
                    <tbody>
                        {hvac_rows}
                    </tbody>
                </table>
            </div>
        </div>
        """

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
            line-height: 1.2;
        }}
        td {{
            padding: 10px 8px;
            border-bottom: 1px solid var(--border);
            color: #e2e8f0;
        }}
        .wrap-txt {{
            word-wrap: break-word;
            overflow-wrap: break-word;
            word-break: break-all;
            max-width: 250px;
            min-width: 150px;
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

        {hvac_html}

        {_build_schedule_html(schedule_data) if schedule_data else ""}

        {_build_process_loads_html(process_data) if process_data else ""}
        
        {_build_natural_ventilation_html(natural_vent_data) if natural_vent_data else ""}

        {_build_construction_html(construction_data) if construction_data else ""}
    </div>
</body>
</html>"""
