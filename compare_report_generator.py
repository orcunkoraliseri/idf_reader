"""
Comparison Report Generator.

Generates a styled HTML report from a CompareResult, consistent with the
existing metadata report aesthetic (dark theme, Inter/Outfit fonts, card layout).
"""

from __future__ import annotations

import datetime
import os

from idf_comparator import CompareResult, MissingType, MissingObject, ObjectDiff


# ── Helpers ────────────────────────────────────────────────────────────────────

def _impact_badge(score: int) -> str:
    """Return a coloured HTML badge for an impact score."""
    if score >= 9:
        color = "#ef4444"   # red
    elif score >= 7:
        color = "#f97316"   # orange
    elif score >= 5:
        color = "#eab308"   # yellow
    elif score >= 3:
        color = "#22c55e"   # green
    else:
        color = "#64748b"   # slate
    return (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:999px;'
        f'background:{color}22;color:{color};font-weight:600;font-size:0.78rem;">'
        f'{score}/10</span>'
    )


def _side_label(side: str, name_a: str, name_b: str) -> str:
    if side == "A":
        return f'<span style="color:#818cf8;">only in reference</span>'
    return f'<span style="color:#f472b6;">only in compare file</span>'


def _esc(s: str) -> str:
    """Minimal HTML escaping."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── Section builders ───────────────────────────────────────────────────────────

def _summary_cards(result: CompareResult) -> str:
    total_issues = (
        len(result.missing_types)
        + len(result.missing_objects)
        + len(result.value_diffs)
    )
    cards = [
        ("Missing Types",   len(result.missing_types),   "#ef4444"),
        ("Missing Objects", len(result.missing_objects), "#f97316"),
        ("Value Diffs",     len(result.value_diffs),     "#eab308"),
        ("Perfect Matches", result.perfect_matches,      "#22c55e"),
    ]
    items = ""
    for label, val, color in cards:
        items += f"""
        <div style="flex:1;min-width:160px;background:#1e293b;border:1px solid #334155;
                    border-radius:12px;padding:20px 24px;text-align:center;">
            <div style="font-size:2rem;font-weight:700;color:{color};">{val}</div>
            <div style="color:#94a3b8;font-size:0.85rem;margin-top:4px;">{label}</div>
        </div>"""
    return f'<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:2rem;">{items}</div>'


def _missing_types_table(items: list[MissingType], name_a: str, name_b: str) -> str:
    if not items:
        return ""
    rows = ""
    for mt in items:
        rows += f"""
        <tr>
            <td>{_esc(mt.obj_type)}</td>
            <td style="text-align:center;">{mt.count}</td>
            <td>{_side_label(mt.side, name_a, name_b)}</td>
            <td style="text-align:center;">{_impact_badge(mt.impact)}</td>
        </tr>"""
    return f"""
    <div class="card">
        <div class="card-header">Missing Object Types
            <span style="font-size:0.8rem;color:#94a3b8;font-weight:400;margin-left:8px;">
                entire type absent from one file
            </span>
        </div>
        <div class="table-container">
            <table>
                <thead><tr>
                    <th>Object Type</th>
                    <th style="text-align:center;">Count</th>
                    <th>Present In</th>
                    <th style="text-align:center;">Impact</th>
                </tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </div>"""


def _missing_objects_table(items: list[MissingObject], name_a: str, name_b: str) -> str:
    if not items:
        return ""
    rows = ""
    for mo in items:
        rows += f"""
        <tr>
            <td>{_esc(mo.obj_type)}</td>
            <td>{_esc(mo.obj_name)}</td>
            <td>{_side_label(mo.side, name_a, name_b)}</td>
            <td style="text-align:center;">{_impact_badge(mo.impact)}</td>
        </tr>"""
    return f"""
    <div class="card">
        <div class="card-header">Missing Object Instances
            <span style="font-size:0.8rem;color:#94a3b8;font-weight:400;margin-left:8px;">
                type exists in both files but named instance is absent from one
            </span>
        </div>
        <div class="table-container">
            <table>
                <thead><tr>
                    <th>Object Type</th>
                    <th>Object Name</th>
                    <th>Present In</th>
                    <th style="text-align:center;">Impact</th>
                </tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </div>"""


def _value_diffs_section(items: list[ObjectDiff], name_a: str, name_b: str) -> str:
    if not items:
        return ""

    blocks = ""
    for od in items:
        field_rows = ""
        for fd in od.field_diffs:
            diff_str = ""
            if fd.diff_pct is not None:
                diff_str = f'<span style="color:#94a3b8;font-size:0.8rem;"> ({fd.diff_pct:.1f}% diff)</span>'
            field_rows += f"""
            <tr>
                <td style="color:#94a3b8;text-align:center;">{fd.field_index}</td>
                <td style="color:#818cf8;">{_esc(fd.value_a)}</td>
                <td style="color:#f472b6;">{_esc(fd.value_b)}{diff_str}</td>
            </tr>"""

        blocks += f"""
        <details style="margin-bottom:12px;">
            <summary style="cursor:pointer;padding:10px 16px;background:#27354d;
                            border-radius:8px;list-style:none;display:flex;
                            align-items:center;gap:12px;user-select:none;">
                {_impact_badge(od.impact)}
                <span style="color:#e2e8f0;font-weight:600;">{_esc(od.obj_type)}</span>
                <span style="color:#94a3b8;">::</span>
                <span style="color:#c084fc;">{_esc(od.obj_name)}</span>
                <span style="margin-left:auto;color:#64748b;font-size:0.8rem;">
                    {len(od.field_diffs)} field(s) differ ▾
                </span>
            </summary>
            <div style="padding:0 8px 8px;">
                <table style="width:100%;margin-top:8px;">
                    <thead><tr>
                        <th style="text-align:center;width:60px;">Field #</th>
                        <th style="color:#818cf8;">Reference ({_esc(name_a)})</th>
                        <th style="color:#f472b6;">Compare ({_esc(name_b)})</th>
                    </tr></thead>
                    <tbody>{field_rows}</tbody>
                </table>
            </div>
        </details>"""

    return f"""
    <div class="card">
        <div class="card-header">Field-Level Value Differences
            <span style="font-size:0.8rem;color:#94a3b8;font-weight:400;margin-left:8px;">
                object exists in both files but one or more field values differ
            </span>
        </div>
        <div style="padding:16px 24px;">
            {blocks}
        </div>
    </div>"""


# ── Main report builder ────────────────────────────────────────────────────────

def generate_compare_report(result: CompareResult, output_path: str) -> None:
    """Generate an HTML comparison report and write it to output_path.

    Args:
        result:      CompareResult from idf_comparator.compare_idfs().
        output_path: Full path for the output HTML file.
    """
    name_a = os.path.basename(result.file_a)
    name_b = os.path.basename(result.file_b)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    total_issues = (
        len(result.missing_types)
        + len(result.missing_objects)
        + len(result.value_diffs)
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IDF Comparison Report</title>
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
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.2rem;
            margin-bottom: 0.3rem;
            background: linear-gradient(to right, #818cf8, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .metadata {{ color: var(--text-dim); margin-bottom: 2rem; font-size: 0.9rem; }}
        .file-pill {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 600;
            margin: 0 4px;
        }}
        .file-a {{ background: #818cf822; color: #818cf8; }}
        .file-b {{ background: #f472b622; color: #f472b6; }}
        .card {{
            background: var(--card-bg);
            border-radius: 16px;
            border: 1px solid var(--border);
            box-shadow: 0 10px 25px -5px rgba(0,0,0,0.3);
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
        .table-container {{ overflow: auto; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
            text-align: left;
        }}
        th {{
            background: #27354d;
            padding: 10px 12px;
            font-weight: 600;
            color: var(--accent);
            position: sticky;
            top: 0;
            border-bottom: 2px solid var(--border);
        }}
        td {{
            padding: 9px 12px;
            border-bottom: 1px solid #1e2d40;
            vertical-align: middle;
        }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover td {{ background: #243044; }}
        details summary::-webkit-details-marker {{ display: none; }}
        .no-issues {{
            text-align: center;
            padding: 32px;
            color: #22c55e;
            font-size: 1.1rem;
        }}
    </style>
</head>
<body>
<div class="container">
    <h1>IDF Comparison Report</h1>
    <div class="metadata">
        Generated: {now} &nbsp;|&nbsp;
        <span class="file-pill file-a">Reference: {_esc(name_a)}</span>
        <span class="file-pill file-b">Compare: {_esc(name_b)}</span>
        &nbsp;|&nbsp; {total_issues} issue(s) found across energy-relevant objects
    </div>

    {_summary_cards(result)}

    {_missing_types_table(result.missing_types, name_a, name_b)}

    {_missing_objects_table(result.missing_objects, name_a, name_b)}

    {_value_diffs_section(result.value_diffs, name_a, name_b)}

    {'<div class="no-issues">No energy-relevant differences found — files match on all compared objects.</div>' if total_issues == 0 else ''}

    <div style="text-align:center;color:#475569;font-size:0.8rem;margin-top:40px;padding-top:20px;border-top:1px solid #1e293b;">
        idf_reader · IDF Comparator &nbsp;|&nbsp; Impact scores: 10 = dominant energy effect, 0 = no effect
    </div>
</div>
</body>
</html>"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  Report saved → {output_path}")
