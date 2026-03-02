"""
NUs_report.py — Neighbourhood IDF HTML Report Generator.

Produces a clean, self-contained HTML report for a neighbourhood IDF.
The report contains:
  1. An axonometric 3-D visualisation of all building geometry (base64 PNG).
  2. A "Building Content" table listing each ASHRAE 90.1 building type and
     its count of distinct building instances within the neighbourhood.

This module only generates the HTML string; writing it to disk is handled
by the orchestrator (``NUs_main.py``).
"""

# Standard library
import os


def _style() -> str:
    """Return the embedded CSS used by the neighbourhood HTML report.

    Returns:
        A string containing a ``<style>`` block.
    """
    return """<style>
  :root {
    --bg: #0f172a;
    --surface: #1e293b;
    --border: #334155;
    --text: #e2e8f0;
    --sub: #94a3b8;
    --accent: #818cf8;
    --accent2: #38bdf8;
    --row-alt: #243047;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    padding: 2.5rem 3rem;
    min-height: 100vh;
  }

  h1 {
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--accent);
    letter-spacing: -0.02em;
    margin-bottom: 0.35rem;
  }

  .subtitle {
    font-size: 0.85rem;
    color: var(--sub);
    margin-bottom: 2rem;
  }

  /* ── Visual Section ─────────────────────────────────────────── */
  .visual-section {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.25rem;
    margin-bottom: 2rem;
    text-align: center;
  }

  .visual-section h2 {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--sub);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 1rem;
  }

  .axon-img {
    max-width: 100%;
    border-radius: 8px;
    border: 1px solid var(--border);
  }

  .no-visual {
    color: var(--sub);
    font-size: 0.85rem;
    padding: 3rem 0;
  }

  /* ── Building Content Table ─────────────────────────────────── */
  .table-section {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.25rem;
  }

  .table-section h2 {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--sub);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 1rem;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }

  thead th {
    background: var(--bg);
    color: var(--accent2);
    text-align: left;
    padding: 0.65rem 1rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    border-bottom: 1px solid var(--border);
  }

  tbody tr:nth-child(even) { background: var(--row-alt); }
  tbody tr:hover { background: #2d3f5a; }

  td {
    padding: 0.6rem 1rem;
    border-bottom: 1px solid var(--border);
    color: var(--text);
  }

  td.count {
    font-weight: 700;
    color: var(--accent);
    text-align: right;
    width: 120px;
  }

  .total-row td {
    border-top: 2px solid var(--accent);
    font-weight: 700;
    color: var(--accent2);
  }

  footer {
    margin-top: 2rem;
    font-size: 0.75rem;
    color: var(--sub);
    text-align: center;
  }
</style>"""


def _building_table(building_counts: dict[str, int]) -> str:
    """Render the building content summary as an HTML table string.

    Args:
        building_counts: Mapping of ASHRAE 90.1 building type name to the
            number of distinct instances found in the neighbourhood.

    Returns:
        An HTML string containing a ``<table>`` element.
    """
    if not building_counts:
        return "<p style='color:var(--sub)'>No building types recognised.</p>"

    rows_html = ""
    total = 0
    for btype, count in sorted(building_counts.items()):
        rows_html += (
            f"<tr><td>{btype}</td>"
            f"<td class='count'>{count}</td></tr>\n"
        )
        total += count

    rows_html += (
        f"<tr class='total-row'>"
        f"<td>Total</td>"
        f"<td class='count'>{total}</td>"
        f"</tr>\n"
    )

    return f"""<table>
  <thead>
    <tr>
      <th>ASHRAE 90.1 Building Type</th>
      <th style="text-align:right">Count</th>
    </tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>"""


def generate_neighbourhood_report(
    idf_path: str,
    building_name: str,
    building_counts: dict[str, int],
    total_zones: int,
) -> str:
    """Generate a complete, self-contained neighbourhood HTML report.

    The report embeds:
    - The ASHRAE 90.1 building type counts as an HTML table.
    - An axonometric 3-D view of the neighbourhood geometry as a base64
      PNG rendered by ``visualizer_adapter.render_idf_to_base64``.

    Args:
        idf_path: Absolute path to the source .idf file (used for rendering
            and deriving the display title).
        building_name: Value extracted from the IDF ``Building`` object.
        building_counts: Mapping of ASHRAE 90.1 building type → count.
        total_zones: Total zone count in the IDF (shown in the subtitle).

    Returns:
        A UTF-8 HTML string ready to be written to a ``.html`` file.
    """
    # Deferred import so the module can be imported without heavy deps
    from visualizer_adapter import render_idf_to_base64  # noqa: WPS433

    filename = os.path.splitext(os.path.basename(idf_path))[0]
    print(f"  Rendering 3-D visualisation for: {filename} …")
    img_b64 = render_idf_to_base64(idf_path)

    if img_b64:
        visual_block = (
            f"<img class='axon-img' "
            f"src='data:image/png;base64,{img_b64}' "
            f"alt='Axonometric view of {filename}'>"
        )
    else:
        visual_block = (
            "<div class='no-visual'>"
            "⚠ Axonometric visualisation could not be generated."
            "</div>"
        )

    table_html = _building_table(building_counts)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Neighbourhood Report — {filename}</title>
  {_style()}
</head>
<body>
  <h1>Neighbourhood Report — {filename}</h1>
  <p class="subtitle">
    IDF Building Name: <strong>{building_name}</strong> &nbsp;|&nbsp;
    Total Zones: <strong>{total_zones}</strong>
  </p>

  <div class="visual-section">
    <h2>Axonometric Visualisation</h2>
    {visual_block}
  </div>

  <div class="table-section">
    <h2>Building Content</h2>
    {table_html}
  </div>

  <footer>Generated by idf_reader · NUs_report.py</footer>
</body>
</html>
"""
    return html
