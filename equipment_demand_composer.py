"""
Equipment Demand Composer for EnergyPlus IDF Files.

Reads all ElectricEquipment and GasEquipment objects from an IDF file,
resolves their Schedule:Year → Schedule:Week → Schedule:Day:Hourly chains
into full 8760-hour fractional arrays, then computes one weighted-composite
schedule and peak design level (W and W/m²) for each energy-type group.

Two outputs ready for Honeybee additional-string insertion:
  - Electric Equipment: composite W/m² + Schedule:Compact snippet
  - Gas Equipment:      composite W/m² + Schedule:Compact snippet

Usage (from project root):
    python equipment_demand_composer.py \\
        --idf Content/low_rise_Res/US+SF+CZ6A+gasfurnace+unheatedbsmt+IECC_2024.idf \\
        --floor-area 167.22

Outputs (written next to this script):
    equipment_electric_schedule.csv
    equipment_gas_schedule.csv
    equipment_demand_summary.txt
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from collections import defaultdict

# ---------------------------------------------------------------------------
# Re-use the existing project parser
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))
from idf_parser import parse_idf  # noqa: E402


# ---------------------------------------------------------------------------
# Schedule resolution helpers
# ---------------------------------------------------------------------------

def _day_of_year_to_weekday(doy: int) -> str:
    """Return a simplified weekday label (Monday–Friday = Weekday, else Weekend).

    Uses a fixed calendar starting Monday 1 Jan (ISO-style).  EnergyPlus
    uses the ``RunPeriod`` day-of-week-for-start-day, but for the purposes
    of this composer we assume the IDF default (Sunday = day 1 of year,
    matching DOE-2/EnergyPlus defaults for US residential templates).

    Args:
        doy: Day of year [1..365].

    Returns:
        One of ``'Sunday'``, ``'Monday'`` … ``'Saturday'`` as a string.
    """
    # DOE-2 / EnergyPlus residential: Jan 1 = Sunday for this template
    # (validated against ClothesDryerVacation being assigned to a vacation week)
    day_index = (doy - 1) % 7  # 0 = Sunday
    names = [
        "Sunday", "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday",
    ]
    return names[day_index]


def _doy_range(start_month: int, start_day: int,
               end_month: int, end_day: int) -> list[int]:
    """Return list of day-of-year integers for a date range (inclusive).

    Args:
        start_month: Start month [1..12].
        start_day:   Start day of month.
        end_month:   End month [1..12].
        end_day:     End day of month.

    Returns:
        List of day-of-year integers.
    """
    # Non-leap year month lengths
    month_lengths = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    cumulative = [0] + list(
        map(lambda i: sum(month_lengths[:i]), range(1, 13))
    )
    start_doy = cumulative[start_month - 1] + start_day
    end_doy = cumulative[end_month - 1] + end_day
    return list(range(start_doy, end_doy + 1))


def _build_day_hourly_map(
    idf_data: dict[str, list[list[str]]]
) -> dict[str, list[float]]:
    """Index all Schedule:Day:Hourly objects by name → 24-element list.

    Args:
        idf_data: Parsed IDF dictionary.

    Returns:
        Mapping of schedule name (lower) → list of 24 hourly fractions.
    """
    day_map: dict[str, list[float]] = {}
    for obj in idf_data.get("SCHEDULE:DAY:HOURLY", []):
        if len(obj) < 2:
            continue
        name = obj[0].strip().lower()
        # fields 0=name, 1=type-limits, 2..25 = hours 1-24
        try:
            fracs = [float(v) for v in obj[2:26]]
        except (ValueError, IndexError):
            fracs = [0.0] * 24
        # Pad or trim
        fracs = (fracs + [0.0] * 24)[:24]
        day_map[name] = fracs
    return day_map


def _build_compact_map(
    idf_data: dict[str, list[list[str]]]
) -> dict[str, list[float]]:
    """Resolve Schedule:Compact objects to 8760-hour arrays.

    Only handles the simple ``Through/For/Until`` pattern used in this IDF.

    Args:
        idf_data: Parsed IDF dictionary.

    Returns:
        Mapping of schedule name (lower) → 8760-length list of fractions.
    """
    compact_map: dict[str, list[float]] = {}

    for obj in idf_data.get("SCHEDULE:COMPACT", []):
        if not obj:
            continue
        name = obj[0].strip().lower()
        # Parse fields sequentially
        arr = [0.0] * 8760
        cur_doys: list[int] = []
        cur_days_filter: str = "aldays"
        until_pairs: list[tuple[int, float]] = []  # (end_hour, value)

        i = 1  # skip name (idx 0) and type-limits (we've already consumed 0)
        # actually obj[0]=name, obj[1]=type-limits, obj[2..]=fields
        i = 2
        while i < len(obj):
            field = obj[i].strip().lower()
            if field.startswith("through:"):
                # Flush previous
                cur_doys = []
                part = obj[i].split(":", 1)[1].strip()
                try:
                    m_str, d_str = part.split("/")
                    m, d = int(m_str), int(d_str)
                    # "Through: 12/31" means from 1/1 up to this date
                    # We track start cumulatively; just store end
                    cur_doys = list(range(1, _doy_range(1, 1, m, d)[-1] + 1))
                except (ValueError, AttributeError):
                    cur_doys = list(range(1, 366))
                until_pairs = []
            elif field.startswith("for:") or field.startswith("for "):
                cur_days_filter = obj[i].split(":", 1)[-1].strip().lower()
                until_pairs = []
            elif field.startswith("until"):
                # "Until: HH:00, value"  or  "Until HH:00,value"
                rest = obj[i].strip()
                # Extract hour and value
                try:
                    time_part = rest.split(":", 1)[1].strip() if ":" in rest else rest
                    hour_str = time_part.split(":")[0].strip()
                    end_hour = int(hour_str)
                    val_str = obj[i + 1].strip() if i + 1 < len(obj) else "0"
                    val = float(val_str)
                    until_pairs.append((end_hour, val))
                    i += 1  # consume the value field
                except (ValueError, IndexError):
                    pass
                # Apply to array
                if cur_doys and until_pairs:
                    prev_hour = (
                        until_pairs[-2][0] if len(until_pairs) >= 2 else 0
                    )
                    end_h, v = until_pairs[-1]
                    for doy in cur_doys:
                        dow = _day_of_year_to_weekday(doy)
                        if _dow_matches(dow, cur_days_filter):
                            for h in range(prev_hour, end_h):
                                idx = (doy - 1) * 24 + h
                                if idx < 8760:
                                    arr[idx] = v
            i += 1

        compact_map[name] = arr
    return compact_map


def _dow_matches(dow: str, filter_str: str) -> bool:
    """Check if a day-of-week matches a For: filter expression.

    Args:
        dow:        Day name e.g. ``'Monday'``.
        filter_str: One of ``'alldays'``, ``'weekdays'``, ``'weekends'``,
                    ``'saturday'``, ``'sunday'``, etc. (lower-case).

    Returns:
        True if the day matches the filter.
    """
    f = filter_str.lower().strip()
    weekdays = {"monday", "tuesday", "wednesday", "thursday", "friday"}
    weekends = {"saturday", "sunday"}
    if "alldays" in f or "all days" in f:
        return True
    if "weekdays" in f:
        return dow.lower() in weekdays
    if "weekends" in f:
        return dow.lower() in weekends
    # Direct day name
    return dow.lower() in f


def _resolve_week_schedules(
    idf_data: dict[str, list[list[str]]],
    day_map: dict[str, list[float]],
) -> dict[str, list[float]]:
    """Resolve Schedule:Week:Daily and Schedule:Week:Compact objects to 8760 arrays.

    Args:
        idf_data: Parsed IDF dictionary.
        day_map:  Pre-built day-hourly map.

    Returns:
        Mapping of week-schedule name (lower) → 8760-length array.
    """
    week_map: dict[str, list[float]] = {}

    # 1. Schedule:Week:Daily
    for obj in idf_data.get("SCHEDULE:WEEK:DAILY", []):
        if len(obj) < 9:
            continue
        name = obj[0].strip().lower()
        # Fields: Sunday, Monday, ..., Saturday, Holiday (idx 1..8)
        day_names = [
            "sunday", "monday", "tuesday", "wednesday",
            "thursday", "friday", "saturday",
        ]
        day_scheds = {d: obj[i + 1].strip().lower() for i, d in enumerate(day_names)}
        arr = [0.0] * 8760
        for doy in range(1, 366):
            dow = _day_of_year_to_weekday(doy).lower()
            sched_name = day_scheds.get(dow, "")
            day_fracs = day_map.get(sched_name, [0.0] * 24)
            base = (doy - 1) * 24
            for h in range(24):
                if base + h < 8760:
                    arr[base + h] = day_fracs[h]
        week_map[name] = arr

    # 2. Schedule:Week:Compact
    for obj in idf_data.get("SCHEDULE:WEEK:COMPACT", []):
        if len(obj) < 3:
            continue
        name = obj[0].strip().lower()
        arr = [0.0] * 8760
        
        # Compile ordered pairs of (filter_str, sched_name)
        pairs = []
        i = 1
        while i + 1 < len(obj):
            f_str = obj[i].strip()
            if f_str.lower().startswith("for:"):
                f_str = f_str[4:].strip()
            elif f_str.lower().startswith("for "):
                f_str = f_str[4:].strip()
            s_name = obj[i + 1].strip().lower()
            pairs.append((f_str, s_name))
            i += 2
            
        for doy in range(1, 366):
            dow = _day_of_year_to_weekday(doy).lower()
            sched_name = ""
            # Match in order. 'allotherdays' acts as a catch-all.
            for (f_str, s_name) in pairs:
                if _dow_matches(dow, f_str) or "allotherdays" in f_str.lower():
                    sched_name = s_name
                    break
            
            day_fracs = day_map.get(sched_name, [0.0] * 24)
            base = (doy - 1) * 24
            for h in range(24):
                if base + h < 8760:
                    arr[base + h] = day_fracs[h]
        week_map[name] = arr

    return week_map


def _resolve_compact_year_schedules(
    idf_data: dict[str, list[list[str]]],
    week_map: dict[str, list[float]],
) -> dict[str, list[float]]:
    """Resolve Schedule:Year objects to full 8760-hour arrays.

    Args:
        idf_data: Parsed IDF dictionary.
        week_map: Pre-built week-schedule map.

    Returns:
        Mapping of year-schedule name (lower) → 8760-length array.
    """
    year_map: dict[str, list[float]] = {}

    for obj in idf_data.get("SCHEDULE:YEAR", []):
        if len(obj) < 2:
            continue
        name = obj[0].strip().lower()
        arr = [0.0] * 8760
        # Pattern: week_name, start_month, start_day, end_month, end_day (repeat)
        i = 2  # skip name (0) and type-limits (1)
        while i + 4 < len(obj):
            wk_name = obj[i].strip().lower()
            try:
                sm = int(obj[i + 1])
                sd = int(obj[i + 2])
                em = int(obj[i + 3])
                ed = int(obj[i + 4])
            except (ValueError, IndexError):
                i += 5
                continue
            doys = _doy_range(sm, sd, em, ed)
            wk_fracs = week_map.get(wk_name, None)
            if wk_fracs:
                for doy in doys:
                    base = (doy - 1) * 24
                    for h in range(24):
                        if base + h < 8760:
                            arr[base + h] = wk_fracs[base + h]
            i += 5
        year_map[name] = arr
    return year_map


def _resolve_schedule(
    name: str,
    year_map: dict[str, list[float]],
    compact_map: dict[str, list[float]],
    const_map: dict[str, float],
) -> list[float]:
    """Look up a schedule by name across all resolved maps.

    Args:
        name:       Schedule name (any case).
        year_map:   Resolved Schedule:Year arrays.
        compact_map: Resolved Schedule:Compact arrays.
        const_map:  Resolved Schedule:Constant values.

    Returns:
        8760-length list of fractional values.
    """
    key = name.strip().lower()
    if key in year_map:
        return year_map[key]
    if key in compact_map:
        return compact_map[key]
    if key in const_map:
        v = const_map[key]
        return [v] * 8760
    return [1.0] * 8760  # fallback: always-on


def _build_const_map(
    idf_data: dict[str, list[list[str]]]
) -> dict[str, float]:
    """Index Schedule:Constant objects.

    Args:
        idf_data: Parsed IDF dictionary.

    Returns:
        Mapping of name (lower) → constant fraction value.
    """
    const_map: dict[str, float] = {}
    for obj in idf_data.get("SCHEDULE:CONSTANT", []):
        if len(obj) < 3:
            continue
        name = obj[0].strip().lower()
        try:
            const_map[name] = float(obj[2])
        except ValueError:
            const_map[name] = 0.0
    return const_map


# ---------------------------------------------------------------------------
# Equipment parsing
# ---------------------------------------------------------------------------

def _parse_equipment(
    idf_data: dict[str, list[list[str]]],
    obj_type: str,
) -> list[dict]:
    """Extract equipment objects of a given type.

    Field layout (0-indexed after the class keyword):
    0: Name
    1: Zone
    2: Schedule Name
    3: Design Level Calculation Method
    4: Design Level [W]   (when method == EquipmentLevel)
    5: Watts/Zone Floor Area  (when method == Watts/Area)
    6: Watts/Person          (when method == Watts/Person)
    7: Fraction Latent
    8: Fraction Radiant
    9: Fraction Lost

    Args:
        idf_data: Parsed IDF dictionary.
        obj_type: ``'ELECTRICEQUIPMENT'`` or ``'GASEQUIPMENT'``.

    Returns:
        List of dicts with keys: name, zone, schedule, design_level_w,
        frac_latent, frac_radiant, frac_lost.
    """
    results = []
    for obj in idf_data.get(obj_type, []):
        if len(obj) < 5:
            continue
        name = obj[0].strip()
        zone = obj[1].strip()
        sched = obj[2].strip()
        method = obj[3].strip().lower()

        design_level_w = 0.0
        try:
            if "equipmentlevel" in method or method == "":
                design_level_w = float(obj[4]) if obj[4].strip() else 0.0
        except (ValueError, IndexError):
            design_level_w = 0.0

        def _frac(idx: int) -> float:
            try:
                return float(obj[idx]) if obj[idx].strip() else 0.0
            except (ValueError, IndexError):
                return 0.0

        results.append({
            "name": name,
            "zone": zone,
            "schedule": sched,
            "design_level_w": design_level_w,
            "frac_latent": _frac(7),
            "frac_radiant": _frac(8),
            "frac_lost": _frac(9),
        })
    return results


# ---------------------------------------------------------------------------
# Composite schedule computation
# ---------------------------------------------------------------------------

def _compute_composite(
    equipment_list: list[dict],
    year_map: dict[str, list[float]],
    compact_map: dict[str, list[float]],
    const_map: dict[str, float],
) -> dict:
    """Compute the weighted-composite 8760 schedule for a list of equipment.

    The composite hourly power is::

        P(h) = Σ_i [ design_level_i × schedule_i(h) ]

    The composite fractional schedule is::

        f(h) = P(h) / max(P)

    The composite peak design level is::

        DL_peak = max(P(h))

    Weighted-average heat fractions are energy-weighted::

        frac_X = Σ_i(DL_i × EFLH_i × frac_X_i) / Σ_i(DL_i × EFLH_i)

    Args:
        equipment_list: List of equipment dicts from ``_parse_equipment``.
        year_map:        Resolved Schedule:Year arrays.
        compact_map:     Resolved Schedule:Compact arrays.
        const_map:       Resolved Schedule:Constant values.

    Returns:
        Dict with keys: ``p_hourly`` (list[float]), ``composite_fracs``
        (list[float]), ``peak_w`` (float), ``annual_kwh`` (float),
        ``frac_latent`` (float), ``frac_radiant`` (float),
        ``frac_lost`` (float), ``per_appliance`` (list[dict]).
    """
    n = 8760
    p_hourly = [0.0] * n

    # Per-appliance info for the summary
    per_appliance = []

    total_weighted_energy = 0.0
    weighted_latent = 0.0
    weighted_radiant = 0.0
    weighted_lost = 0.0

    for eq in equipment_list:
        dl = eq["design_level_w"]
        if dl == 0.0:
            continue
        sched_arr = _resolve_schedule(
            eq["schedule"], year_map, compact_map, const_map
        )
        eflh = sum(sched_arr)  # equivalent full-load hours
        annual_kwh = dl * eflh / 1000.0

        for h in range(n):
            p_hourly[h] += dl * sched_arr[h]

        weighted_energy = dl * eflh
        total_weighted_energy += weighted_energy
        weighted_latent += weighted_energy * eq["frac_latent"]
        weighted_radiant += weighted_energy * eq["frac_radiant"]
        weighted_lost += weighted_energy * eq["frac_lost"]

        per_appliance.append({
            "name": eq["name"],
            "schedule": eq["schedule"],
            "design_level_w": dl,
            "eflh": round(eflh, 1),
            "annual_kwh": round(annual_kwh, 1),
        })

    peak_w = max(p_hourly) if p_hourly else 0.0
    annual_kwh_total = sum(p_hourly) / 1000.0

    if peak_w > 0:
        composite_fracs = [p / peak_w for p in p_hourly]
    else:
        composite_fracs = [0.0] * n

    if total_weighted_energy > 0:
        frac_latent = weighted_latent / total_weighted_energy
        frac_radiant = weighted_radiant / total_weighted_energy
        frac_lost = weighted_lost / total_weighted_energy
    else:
        frac_latent = frac_radiant = frac_lost = 0.0

    return {
        "p_hourly": p_hourly,
        "composite_fracs": composite_fracs,
        "peak_w": peak_w,
        "annual_kwh": annual_kwh_total,
        "frac_latent": frac_latent,
        "frac_radiant": frac_radiant,
        "frac_lost": frac_lost,
        "per_appliance": per_appliance,
    }


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _write_schedule_csv(
    path: str,
    composite_fracs: list[float],
    label: str,
) -> None:
    """Write hourly composite schedule fractions to a CSV file.

    Args:
        path:            Absolute path to output CSV.
        composite_fracs: 8760-element list of fractions [0..1].
        label:           Column label (e.g. ``'ElectricEquipment_fraction'``).
    """
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["hour_of_year", label])
        for h, v in enumerate(composite_fracs, start=1):
            writer.writerow([h, round(v, 6)])


def _fracs_to_schedule_compact(
    name: str,
    composite_fracs: list[float],
    sig_digits: int = 5,
) -> str:
    """Convert 8760-hour fractions to a ``Schedule:Compact`` IDF snippet.

    Groups consecutive hours with the same (rounded) value into a single
    ``Until:`` field to keep the output compact.

    Args:
        name:            Schedule name for the IDF object.
        composite_fracs: 8760-element list of fractions.
        sig_digits:      Rounding precision for fractional values.

    Returns:
        A multi-line string containing the ``Schedule:Compact`` IDF block.
    """
    lines = [
        f"Schedule:Compact,",
        f"  {name},                   !- Name",
        f"  Fraction,                 !- Schedule Type Limits Name",
        f"  Through: 12/31,           !- Field 1",
        f"  For: AllDays,             !- Field 2",
    ]

    # Collapse consecutive identical (rounded) values
    field_index = 3
    prev_val = round(composite_fracs[0], sig_digits)
    start_hour = 0  # 0-indexed

    def _add_until(end_hour_exclusive: int, val: float) -> None:
        nonlocal field_index
        lines.append(
            f"  Until: {end_hour_exclusive:02d}:00, "
            f"{val:.{sig_digits}f},"
            f"             !- Field {field_index}"
        )
        field_index += 1

    for h in range(1, 8760):
        cur_val = round(composite_fracs[h], sig_digits)
        # New day — force flush at day boundary if values differ
        if cur_val != prev_val or h % 24 == 0:
            _add_until(h % 24 if h % 24 != 0 else 24, prev_val)
            prev_val = cur_val
            start_hour = h

    # Flush last segment
    _add_until(24, prev_val)

    # Fix last line: replace trailing comma with semicolon
    lines[-1] = lines[-1].rstrip(",") + ";"
    return "\n".join(lines)


def _write_summary(
    path: str,
    floor_area_m2: float,
    elec_result: dict,
    gas_result: dict,
) -> None:
    """Write a human-readable summary text file.

    Args:
        path:          Output path for the .txt file.
        floor_area_m2: Conditioned zone floor area [m²].
        elec_result:   Output dict from ``_compute_composite`` for electric.
        gas_result:    Output dict from ``_compute_composite`` for gas.
    """
    lines: list[str] = []

    def h(title: str) -> None:
        lines.append("")
        lines.append("=" * 60)
        lines.append(title)
        lines.append("=" * 60)

    def row(label: str, value: str) -> None:
        lines.append(f"  {label:<38} {value}")

    lines.append("COMBINED EQUIPMENT DEMAND — COMPOSITE SCHEDULE SUMMARY")
    lines.append(f"Zone floor area: {floor_area_m2:.2f} m²")

    for label, res in [("ELECTRIC EQUIPMENT", elec_result),
                        ("GAS EQUIPMENT", gas_result)]:
        h(label)
        peak_w = res["peak_w"]
        peak_wm2 = peak_w / floor_area_m2 if floor_area_m2 > 0 else 0.0
        row("Peak composite design level [W]:", f"{peak_w:.2f}")
        row("Peak composite design level [W/m²]:", f"{peak_wm2:.4f}")
        row("Annual energy (composite) [kWh/yr]:", f"{res['annual_kwh']:.1f}")
        row("Annual energy density [kWh/m²/yr]:",
            f"{res['annual_kwh'] / floor_area_m2:.2f}" if floor_area_m2 else "N/A")
        row("Weighted frac_latent:", f"{res['frac_latent']:.4f}")
        row("Weighted frac_radiant:", f"{res['frac_radiant']:.4f}")
        row("Weighted frac_lost:", f"{res['frac_lost']:.4f}")
        lines.append("")
        lines.append("  Per-appliance breakdown:")
        lines.append(
            f"  {'Name':<30} {'Sched':<28} {'DL(W)':>8}"
            f" {'EFLH':>7} {'kWh/yr':>9}"
        )
        lines.append("  " + "-" * 90)
        for ap in res["per_appliance"]:
            lines.append(
                f"  {ap['name']:<30} {ap['schedule']:<28}"
                f" {ap['design_level_w']:>8.2f}"
                f" {ap['eflh']:>7.1f}"
                f" {ap['annual_kwh']:>9.1f}"
            )

    lines.append("")
    lines.append("=" * 60)
    lines.append("HONEYBEE INSERTION GUIDE")
    lines.append("=" * 60)
    elec_wm2 = elec_result["peak_w"] / floor_area_m2 if floor_area_m2 else 0.0
    gas_wm2 = gas_result["peak_w"] / floor_area_m2 if floor_area_m2 else 0.0
    lines.append(
        f"\n  Electric EquipmentPerFloorArea : {elec_wm2:.4f} W/m²"
        f"\n    → use schedule: 'composite_elec_equip_sch'"
    )
    lines.append(
        f"\n  Gas EquipmentPerFloorArea      : {gas_wm2:.4f} W/m²"
        f"\n    → use schedule: 'composite_gas_equip_sch'"
    )
    lines.append(
        "\n  Insert the Schedule:Compact objects from the .idf snippet "
        "files as\n  additional EnergyPlus strings in Honeybee."
    )

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def _write_idf_snippet(
    path: str,
    electric_compact: str,
    gas_compact: str,
) -> None:
    """Write both Schedule:Compact blocks to a single .idf snippet file.

    Args:
        path:             Output path.
        electric_compact: IDF text for the electric composite schedule.
        gas_compact:      IDF text for the gas composite schedule.
    """
    content = (
        "! ---------------------------------------------------------------\n"
        "! Composite Equipment Demand Schedules — auto-generated\n"
        "! Insert these as EnergyPlus Additional Strings in Honeybee\n"
        "! ---------------------------------------------------------------\n\n"
        + electric_compact
        + "\n\n"
        + gas_compact
        + "\n"
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compose_equipment_demand(
    idf_path: str,
    floor_area_m2: float,
    out_dir: str,
) -> None:
    """Run the full equipment demand composition pipeline.

    Args:
        idf_path:     Absolute path to the EnergyPlus .idf file.
        floor_area_m2: Conditioned zone floor area in m². Used to convert
                       peak W to W/m². If ≤ 0, W/m² outputs are omitted.
        out_dir:      Directory where output files are written.
    """
    print(f"Parsing IDF: {idf_path}")
    idf_data = parse_idf(idf_path)

    print("Resolving schedules …")
    day_map = _build_day_hourly_map(idf_data)
    week_map = _resolve_week_schedules(idf_data, day_map)
    year_map = _resolve_compact_year_schedules(idf_data, week_map)
    compact_map = _build_compact_map(idf_data)
    const_map = _build_const_map(idf_data)

    print(f"  Schedule:Day:Hourly objects resolved : {len(day_map)}")
    print(f"  Schedule:Week:Daily objects resolved : {len(week_map)}")
    print(f"  Schedule:Year objects resolved       : {len(year_map)}")
    print(f"  Schedule:Compact objects resolved    : {len(compact_map)}")
    print(f"  Schedule:Constant objects resolved   : {len(const_map)}")

    print("Parsing equipment objects …")
    elec_equip = _parse_equipment(idf_data, "ELECTRICEQUIPMENT")
    gas_equip = _parse_equipment(idf_data, "GASEQUIPMENT")
    print(f"  ElectricEquipment objects: {len(elec_equip)}")
    print(f"  GasEquipment objects     : {len(gas_equip)}")

    # Filter out zero-watt objects (they contribute nothing)
    elec_equip = [e for e in elec_equip if e["design_level_w"] > 0.0]
    gas_equip = [e for e in gas_equip if e["design_level_w"] > 0.0]
    print(f"  After filtering zero-W: Electric={len(elec_equip)}, Gas={len(gas_equip)}")

    print("Computing composite schedules …")
    elec_result = _compute_composite(elec_equip, year_map, compact_map, const_map)
    gas_result = _compute_composite(gas_equip, year_map, compact_map, const_map)

    os.makedirs(out_dir, exist_ok=True)

    # Write hourly CSV schedules
    csv_elec = os.path.join(out_dir, "equipment_electric_schedule.csv")
    csv_gas = os.path.join(out_dir, "equipment_gas_schedule.csv")
    _write_schedule_csv(csv_elec, elec_result["composite_fracs"],
                        "ElectricEquipment_fraction")
    _write_schedule_csv(csv_gas, gas_result["composite_fracs"],
                        "GasEquipment_fraction")

    # Write Schedule:Compact IDF snippets
    elec_compact = _fracs_to_schedule_compact(
        "composite_elec_equip_sch", elec_result["composite_fracs"]
    )
    gas_compact = _fracs_to_schedule_compact(
        "composite_gas_equip_sch", gas_result["composite_fracs"]
    )
    idf_snippet_path = os.path.join(out_dir, "composite_equipment_schedules.idf")
    _write_idf_snippet(idf_snippet_path, elec_compact, gas_compact)

    # Write human-readable summary
    summary_path = os.path.join(out_dir, "equipment_demand_summary.txt")
    _write_summary(summary_path, floor_area_m2, elec_result, gas_result)

    print("\nOutputs written:")
    print(f"  {csv_elec}")
    print(f"  {csv_gas}")
    print(f"  {idf_snippet_path}")
    print(f"  {summary_path}")

    # Print headline numbers
    print("\n--- RESULTS ---")
    for lbl, res in [("Electric", elec_result), ("Gas", gas_result)]:
        wm2 = res["peak_w"] / floor_area_m2 if floor_area_m2 > 0 else math.nan
        print(
            f"  {lbl:8s}  Peak={res['peak_w']:.2f} W  "
            f"({wm2:.4f} W/m²)  "
            f"Annual={res['annual_kwh']:.1f} kWh/yr"
        )


def _cli() -> None:
    """Command-line interface entry point."""
    parser = argparse.ArgumentParser(
        description="Compose weighted-composite equipment demand schedules "
                    "from an EnergyPlus IDF file."
    )
    parser.add_argument(
        "--idf",
        required=True,
        help="Path to the EnergyPlus .idf file.",
    )
    parser.add_argument(
        "--floor-area",
        type=float,
        default=0.0,
        metavar="M2",
        help="Conditioned zone floor area in m² (for W/m² conversion).",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs",
        help="Output directory (default: outputs/).",
    )
    args = parser.parse_args()
    compose_equipment_demand(
        idf_path=os.path.abspath(args.idf),
        floor_area_m2=args.floor_area,
        out_dir=os.path.abspath(args.out_dir),
    )


if __name__ == "__main__":
    _cli()
