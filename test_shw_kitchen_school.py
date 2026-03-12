"""
test_shw_kitchen_school.py

Standalone verification of the Kitchen SHW calculation for:
    ASHRAE901_SchoolPrimary_STD2022_Denver.idf

Checks that the extractor logic (peak-only, no schedule fraction)
produces the same value reported in the metadata HTML: 2.2532 L/h·m².

Run:
    python test_shw_kitchen_school.py
"""

import os
import math

IDF_PATH = os.path.join(
    os.path.dirname(__file__),
    "Content", "ASHRAE901_STD2022",
    "ASHRAE901_SchoolPrimary_STD2022_Denver.idf",
)

METADATA_VALUE = 2.2532  # L/h·m² as shown in the metadata HTML
TOLERANCE = 0.001        # acceptable rounding difference


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def polygon_area_xy(vertices):
    """Shoelace formula for a flat (z-constant) polygon given (x,y,z) tuples."""
    n = len(vertices)
    area = 0.0
    for i in range(n):
        x1, y1, _ = vertices[i]
        x2, y2, _ = vertices[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def strip_comments(text):
    """Remove inline IDF comments (everything after '!' on each line)."""
    lines = []
    for line in text.split("\n"):
        lines.append(line.split("!")[0])
    return "\n".join(lines)


def parse_idf_blocks(idf_text, object_type):
    """
    Yields lists of field strings for every IDF object of *object_type*.
    Comments are stripped before field splitting so values are preserved.
    """
    clean = strip_comments(idf_text)
    upper = clean.upper()
    search = object_type.upper() + ","
    pos = 0
    while True:
        idx = upper.find(search, pos)
        if idx == -1:
            break
        end = clean.find(";", idx)
        if end == -1:
            break
        block = clean[idx + len(search): end]
        fields = [f.strip() for f in block.split(",")]
        yield fields
        pos = end + 1


# ---------------------------------------------------------------------------
# Step 1 — Load IDF
# ---------------------------------------------------------------------------

print("=" * 60)
print("  Kitchen SHW Verification — SchoolPrimary Denver")
print("=" * 60)

with open(IDF_PATH, "r", encoding="latin-1") as f:
    idf_text = f.read()

print(f"\n[1] IDF loaded: {os.path.basename(IDF_PATH)}")


# ---------------------------------------------------------------------------
# Step 2 — Find WaterUse:Equipment for Kitchen_ZN_1_FLR_1
# ---------------------------------------------------------------------------

TARGET_ZONE = "Kitchen_ZN_1_FLR_1"
peak_m3s = None
flow_sched = None
equip_name = None

for fields in parse_idf_blocks(idf_text, "WaterUse:Equipment"):
    # WaterUse:Equipment field layout:
    # [0] Name, [1] End-Use Subcategory, [2] Peak Flow Rate,
    # [3] Flow Rate Fraction Schedule, [4] Target Temp Sched,
    # [5] Hot Supply Temp Sched, [6] Cold Water Supply Sched, [7] Zone Name
    if len(fields) >= 8 and fields[7].strip() == TARGET_ZONE:
        equip_name  = fields[0].strip()
        peak_m3s    = float(fields[2].strip())
        flow_sched  = fields[3].strip() if len(fields) > 3 else ""
        break

if peak_m3s is None:
    print(f"\n[ERROR] No WaterUse:Equipment found for zone '{TARGET_ZONE}'")
    raise SystemExit(1)

print(f"\n[2] WaterUse:Equipment found: '{equip_name}'")
print(f"    Peak Flow Rate        : {peak_m3s:.8f} m³/s")
print(f"    Flow Rate Sched       : '{flow_sched}'")


# ---------------------------------------------------------------------------
# Step 3 — AlwaysOff guard (mirrors extractor logic)
# ---------------------------------------------------------------------------

if flow_sched.lower() == "alwaysoff":
    print("\n[3] Schedule is AlwaysOff → SHW = 0  (device explicitly disabled)")
    computed = 0.0
else:
    print("\n[3] Schedule is NOT AlwaysOff → proceeding with peak-only formula")
    computed = None  # set after area


# ---------------------------------------------------------------------------
# Step 4 — Compute floor area from BuildingSurface:Detailed
# ---------------------------------------------------------------------------

floor_area = 0.0
floor_surfaces_found = []

for fields in parse_idf_blocks(idf_text, "BuildingSurface:Detailed"):
    # fields[0]=Name, [1]=SurfType, [2]=Construction, [3]=Zone, ...
    # vertices start after the "Number of Vertices" field
    if len(fields) < 5:
        continue
    surf_type = fields[1].strip().lower()
    zone_name = fields[3].strip()
    if zone_name != TARGET_ZONE or surf_type != "floor":
        continue

    # BuildingSurface:Detailed layout (E+ 22.x / 24.x with Space Name field):
    # [0] Name  [1] SurfType  [2] Construction  [3] Zone  [4] Space
    # [5] BC    [6] BC Object [7] Sun  [8] Wind  [9] ViewFactor
    # [10] Number of Vertices  [11+] X,Y,Z per vertex
    try:
        n_vertices = int(fields[10].strip())
    except (IndexError, ValueError):
        continue

    vertex_fields = fields[11: 11 + n_vertices * 3]
    if len(vertex_fields) < n_vertices * 3:
        continue

    vertices = []
    for i in range(n_vertices):
        x = float(vertex_fields[i * 3])
        y = float(vertex_fields[i * 3 + 1])
        z = float(vertex_fields[i * 3 + 2])
        vertices.append((x, y, z))

    area = polygon_area_xy(vertices)
    floor_surfaces_found.append((fields[0].strip(), area))
    floor_area += area

print(f"\n[4] Floor surfaces in '{TARGET_ZONE}':")
for name, a in floor_surfaces_found:
    print(f"    {name}: {a:.4f} m²")
print(f"    Total floor area: {floor_area:.4f} m²")


# ---------------------------------------------------------------------------
# Step 5 — Compute SHW
# ---------------------------------------------------------------------------

if computed is None:  # not AlwaysOff
    computed = peak_m3s * 3_600_000 / floor_area

print(f"\n[5] SHW calculation (peak-only, no schedule fraction):")
print(f"    peak_m3s × 3,600,000 / floor_area")
print(f"    = {peak_m3s:.8f} × 3,600,000 / {floor_area:.4f}")
print(f"    = {computed:.6f} L/h·m²")


# ---------------------------------------------------------------------------
# Step 6 — Compare with metadata
# ---------------------------------------------------------------------------

diff = abs(computed - METADATA_VALUE)
match = diff < TOLERANCE

print(f"\n[6] Comparison with metadata HTML:")
print(f"    Computed : {computed:.4f} L/h·m²")
print(f"    Metadata : {METADATA_VALUE:.4f} L/h·m²")
print(f"    Δ        : {diff:.6f}")
print(f"    Result   : {'✓ MATCH' if match else '✗ MISMATCH'}")

if not match:
    raise SystemExit(f"\n[FAIL] Computed SHW {computed:.4f} differs from metadata {METADATA_VALUE:.4f} by {diff:.4f}")

print("\n  All checks passed.\n")
