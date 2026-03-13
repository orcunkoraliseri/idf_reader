"""
IDF Comparator Module.

Compares two EnergyPlus IDF files and identifies differences in energy-relevant
objects: missing object types, missing named instances, and field-level value
mismatches. Results are sorted by impact score (0–10).

This is a general-purpose comparison tool — any two IDF files can be compared
regardless of building type or source software.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from idf_parser import parse_idf


# ── Impact scores (0–10) for energy-relevant object types ─────────────────────
# 10 = dominant effect on annual energy demand, 0 = no energy effect.
OBJECT_IMPACT: dict[str, int] = {
    # Site & simulation globals
    "BUILDING": 8,
    "SITE:LOCATION": 8,
    "SIMULATIONCONTROL": 5,
    "TIMESTEP": 4,
    # Envelope geometry (construction/material excluded — intentional differences expected)
    "BUILDINGSURFACE:DETAILED": 9,
    "FENESTRATIONSURFACE:DETAILED": 8,
    # Internal loads
    "LIGHTS": 8,
    "ELECTRICEQUIPMENT": 7,
    "GASEQUIPMENT": 7,
    "PEOPLE": 8,
    "INTERNALMASS": 4,
    # Infiltration & ventilation
    "ZONEINFILTRATION:DESIGNFLOWRATE": 8,
    "DESIGNSPECIFICATION:OUTDOORAIR": 7,
    "CONTROLLER:MECHANICALVENTILATION": 6,
    # HVAC — system-level
    "AIRLOOPHVAC": 9,
    "AIRLOOPHVAC:UNITARYHEATPUMP:AIRTOAIR": 10,
    "COILSYSTEM:COOLING:DX": 7,
    # HVAC — coils
    "COIL:COOLING:DX:SINGLESPEED": 7,
    "COIL:COOLING:DX:TWOSPEED": 7,
    "COIL:HEATING:DX:SINGLESPEED": 10,
    "COIL:HEATING:WATER": 10,
    "COIL:HEATING:FUEL": 9,
    # HVAC — fans & pumps
    "FAN:ONOFF": 7,
    "FAN:VARIABLEVOLUME": 7,
    "PUMP:CONSTANTSPEED": 6,
    "PUMP:VARIABLESPEED": 6,
    # HVAC — plant
    "BOILER:HOTWATER": 10,
    "PLANTLOOP": 6,
    # HVAC — terminals & zone equipment
    "AIRTERMINAL:SINGLEDUCT:CONSTANTVOLUME:NOREHEAT": 7,
    "AIRTERMINAL:SINGLEDUCT:VAV:REHEAT": 7,
    "ZONEHVAC:EQUIPMENTLIST": 8,
    "ZONEHVAC:AIRDISTRIBUTIONUNIT": 7,
    # Controls & setpoints
    "THERMOSTATSETPOINT:DUALSETPOINT": 9,
    "ZONECONTROL:THERMOSTAT": 8,
    "SETPOINTMANAGER:SCHEDULED": 7,
    "SETPOINTMANAGER:MIXEDAIR": 6,
    "SETPOINTMANAGER:SINGLEZONE:COOLING": 6,
    "SETPOINTMANAGER:SINGLEZONE:HEATING": 6,
    "AVAILABILITYMANAGER:NIGHTCYCLE": 5,
    # Daylighting
    "DAYLIGHTING:CONTROLS": 6,
    "DAYLIGHTING:REFERENCEPOINT": 5,
    # SHW
    "WATERHEATER:MIXED": 5,
    "WATERUSE:EQUIPMENT": 4,
    "WATERUSE:CONNECTIONS": 3,
    # Schedules
    "SCHEDULE:COMPACT": 7,
    "SCHEDULE:YEAR": 7,
    "SCHEDULE:WEEK:DAILY": 6,
    "SCHEDULE:DAY:INTERVAL": 6,
    "SCHEDULE:CONSTANT": 5,
    # Sizing
    "SIZING:ZONE": 5,
    "SIZING:SYSTEM": 5,
    "SIZING:PLANT": 4,
    "SIZING:PARAMETERS": 3,
    # Performance curves
    "CURVE:BIQUADRATIC": 6,
    "CURVE:QUADRATIC": 5,
    "CURVE:CUBIC": 5,
}

# Relative tolerance (%) for numeric field comparison.
# Differences below this threshold are treated as matching.
NUMERIC_TOLERANCE_PCT = 1.0
NUMERIC_TOLERANCE_ABS = 1e-9  # fallback when both values are near zero


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class FieldDiff:
    """A single field-level difference between two matched objects."""
    field_index: int        # 0-based index within the object's field list
    value_a: str            # value in file A
    value_b: str            # value in file B
    is_numeric: bool
    diff_pct: float | None  # relative difference in %; None if not numeric


@dataclass
class ObjectDiff:
    """All field differences for a single named IDF object."""
    obj_type: str
    obj_name: str
    impact: int
    field_diffs: list[FieldDiff]


@dataclass
class MissingObject:
    """A named object instance present in one file but absent in the other."""
    obj_type: str
    obj_name: str
    impact: int
    side: str  # 'A' = exists only in file_a; 'B' = exists only in file_b


@dataclass
class MissingType:
    """An entire object type present in one file but completely absent from the other."""
    obj_type: str
    count: int   # number of instances in the file that has it
    impact: int
    side: str    # 'A' = exists only in file_a; 'B' = exists only in file_b


@dataclass
class CompareResult:
    """Full comparison result between two IDF files."""
    file_a: str
    file_b: str
    missing_types: list[MissingType]
    missing_objects: list[MissingObject]
    value_diffs: list[ObjectDiff]
    perfect_matches: int  # count of objects that matched with zero field differences


# ── Internal helpers ───────────────────────────────────────────────────────────

def _is_numeric(s: str) -> bool:
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def _numeric_diff_pct(a: str, b: str) -> float | None:
    try:
        fa, fb = float(a), float(b)
    except (ValueError, TypeError):
        return None
    if abs(fa) < NUMERIC_TOLERANCE_ABS and abs(fb) < NUMERIC_TOLERANCE_ABS:
        return 0.0
    denom = max(abs(fa), abs(fb))
    if denom == 0:
        return 0.0
    return abs(fa - fb) / denom * 100.0


def _compare_fields(fields_a: list[str], fields_b: list[str]) -> list[FieldDiff]:
    """Compare two field lists (index 0 = name, skipped) and return diffs."""
    diffs: list[FieldDiff] = []
    max_len = max(len(fields_a), len(fields_b))
    for i in range(1, max_len):  # index 0 is the object name — skip
        va = fields_a[i] if i < len(fields_a) else ""
        vb = fields_b[i] if i < len(fields_b) else ""

        if va.strip().lower() == vb.strip().lower():
            continue

        both_numeric = _is_numeric(va) and _is_numeric(vb)
        diff_pct = _numeric_diff_pct(va, vb) if both_numeric else None

        # Ignore numeric differences within tolerance
        if diff_pct is not None and diff_pct <= NUMERIC_TOLERANCE_PCT:
            continue

        diffs.append(FieldDiff(
            field_index=i,
            value_a=va,
            value_b=vb,
            is_numeric=both_numeric,
            diff_pct=diff_pct,
        ))
    return diffs


def _match_objects(
    objs_a: list[list[str]],
    objs_b: list[list[str]],
) -> tuple[list[tuple[list[str], list[str]]], list[list[str]], list[list[str]]]:
    """Match object instances by name (field[0], case-insensitive).

    Returns:
        matched: list of (fields_a, fields_b) pairs
        only_a:  objects in A with no name match in B
        only_b:  objects in B with no name match in A
    """
    index_b: dict[str, list[str]] = {}
    for obj in objs_b:
        name = obj[0].strip().lower() if obj else ""
        index_b[name] = obj

    matched: list[tuple[list[str], list[str]]] = []
    only_a: list[list[str]] = []
    used_b: set[str] = set()

    for obj_a in objs_a:
        name = obj_a[0].strip().lower() if obj_a else ""
        if name in index_b:
            matched.append((obj_a, index_b[name]))
            used_b.add(name)
        else:
            only_a.append(obj_a)

    only_b = [
        obj for obj in objs_b
        if (obj[0].strip().lower() if obj else "") not in used_b
    ]
    return matched, only_a, only_b


# ── Public API ─────────────────────────────────────────────────────────────────

def compare_idfs(path_a: str, path_b: str) -> CompareResult:
    """Compare two IDF files and return a structured diff result.

    Only object types listed in OBJECT_IMPACT are analysed. Objects are matched
    by name (field[0]). Field comparisons use a 1% numeric tolerance.

    Args:
        path_a: Path to the trusted reference IDF file.
        path_b: Path to the IDF file being questioned.

    Returns:
        CompareResult sorted by impact score (highest first).
    """
    if not os.path.exists(path_a):
        raise FileNotFoundError(f"Reference IDF not found: {path_a}")
    if not os.path.exists(path_b):
        raise FileNotFoundError(f"Comparison IDF not found: {path_b}")

    idf_a = {k.upper(): v for k, v in parse_idf(path_a).items()}
    idf_b = {k.upper(): v for k, v in parse_idf(path_b).items()}

    types_a = set(idf_a.keys())
    types_b = set(idf_b.keys())
    relevant = set(OBJECT_IMPACT.keys())

    missing_types: list[MissingType] = []
    missing_objects: list[MissingObject] = []
    value_diffs: list[ObjectDiff] = []
    perfect_matches = 0

    # ── Entire types missing from one file ────────────────────────────────────
    for t in sorted((types_a - types_b) & relevant):
        missing_types.append(MissingType(
            obj_type=t,
            count=len(idf_a[t]),
            impact=OBJECT_IMPACT[t],
            side="A",
        ))
    for t in sorted((types_b - types_a) & relevant):
        missing_types.append(MissingType(
            obj_type=t,
            count=len(idf_b[t]),
            impact=OBJECT_IMPACT[t],
            side="B",
        ))

    # ── Types present in both files — instance-level comparison ───────────────
    for obj_type in sorted((types_a & types_b) & relevant):
        objs_a = idf_a[obj_type]
        objs_b = idf_b[obj_type]
        impact = OBJECT_IMPACT[obj_type]

        # Skip degenerate empty objects
        if not objs_a or not objs_b:
            continue

        has_names = any(obj and obj[0].strip() for obj in objs_a)

        if has_names:
            matched, only_a, only_b = _match_objects(objs_a, objs_b)
        else:
            # No name field — match positionally
            min_len = min(len(objs_a), len(objs_b))
            matched = list(zip(objs_a[:min_len], objs_b[:min_len]))
            only_a = objs_a[min_len:]
            only_b = objs_b[min_len:]

        for obj in only_a:
            name = obj[0].strip() if obj else "(unnamed)"
            missing_objects.append(MissingObject(
                obj_type=obj_type, obj_name=name, impact=impact, side="A"
            ))
        for obj in only_b:
            name = obj[0].strip() if obj else "(unnamed)"
            missing_objects.append(MissingObject(
                obj_type=obj_type, obj_name=name, impact=impact, side="B"
            ))

        for fields_a, fields_b in matched:
            diffs = _compare_fields(fields_a, fields_b)
            name = fields_a[0].strip() if fields_a else "(unnamed)"
            if diffs:
                value_diffs.append(ObjectDiff(
                    obj_type=obj_type,
                    obj_name=name,
                    impact=impact,
                    field_diffs=diffs,
                ))
            else:
                perfect_matches += 1

    # Sort all results by impact descending
    missing_types.sort(key=lambda x: x.impact, reverse=True)
    missing_objects.sort(key=lambda x: x.impact, reverse=True)
    value_diffs.sort(key=lambda x: x.impact, reverse=True)

    return CompareResult(
        file_a=path_a,
        file_b=path_b,
        missing_types=missing_types,
        missing_objects=missing_objects,
        value_diffs=value_diffs,
        perfect_matches=perfect_matches,
    )


def print_summary(result: CompareResult) -> None:
    """Print a compact console summary of the comparison result."""
    name_a = os.path.basename(result.file_a)
    name_b = os.path.basename(result.file_b)
    print(f"\n{'='*60}")
    print(f"  IDF Comparison Summary")
    print(f"  Reference : {name_a}")
    print(f"  Compare   : {name_b}")
    print(f"{'='*60}")
    print(f"  Missing object types : {len(result.missing_types)}")
    print(f"  Missing objects      : {len(result.missing_objects)}")
    print(f"  Objects with diffs   : {len(result.value_diffs)}")
    print(f"  Perfect matches      : {result.perfect_matches}")

    if result.missing_types:
        print(f"\n  Top missing types (by impact):")
        for mt in result.missing_types[:10]:
            side_label = f"only in {'reference' if mt.side == 'A' else 'compare file'}"
            print(f"    [{mt.impact}/10] {mt.obj_type}  ({mt.count} instance(s), {side_label})")

    if result.value_diffs:
        print(f"\n  Top value differences (by impact):")
        for vd in result.value_diffs[:10]:
            print(f"    [{vd.impact}/10] {vd.obj_type} :: {vd.obj_name}  ({len(vd.field_diffs)} field(s) differ)")

    print(f"{'='*60}\n")
