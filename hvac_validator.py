from __future__ import annotations

"""
HVAC Validation Module.

This module cross-checks extracted HVAC template strings, DCV values, and
economizer types from extract_hvac_systems() against the canonical set of
valid Honeybee HVAC templates defined in the Templates/HVAC_templates/ folder.

It uses ast.parse() to extract enum values from the template source files
without importing them, avoiding any dependency on third-party packages such
as pydantic that may not be installed.
"""

import ast
import os


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_TEMPLATE_DIR = os.path.join(
    os.path.dirname(__file__), "Templates", "HVAC_templates"
)

_TEMPLATE_FILES = [
    os.path.join(_TEMPLATE_DIR, "allair.py"),
    os.path.join(_TEMPLATE_DIR, "doas.py"),
    os.path.join(_TEMPLATE_DIR, "heatcool.py"),
]

# ---------------------------------------------------------------------------
# Additional generic labels produced by the extractor that are not formal
# Honeybee equipment-type enum values, but are considered valid outputs.
# ---------------------------------------------------------------------------
_EXTRACTOR_GENERIC_LABELS: set[str] = {
    "Unconditioned",
    "Baseboard",
    "Radiant",
    "UnitHeater",
    "Dehumidifier",
    "IdealLoads",
    "FCUwithDOASAbridged",
    "WSHP",
    "PTAC",
    "PTHP",
}

# ---------------------------------------------------------------------------
# Valid DCV values
# ---------------------------------------------------------------------------
_VALID_DCV: set[str] = {"Yes", "No", "N/A"}

# ---------------------------------------------------------------------------
# Valid economizer values (from AllAirEconomizerType in allair.py)
# ---------------------------------------------------------------------------
_VALID_ECONOMIZER: set[str] = {
    "NoEconomizer",
    "DifferentialDryBulb",
    "DifferentialEnthalpy",
    "DifferentialDryBulbAndEnthalpy",
    "FixedDryBulb",
    "FixedEnthalpy",
    "ElectronicEnthalpy",
}


def build_valid_template_set() -> set[str]:
    """Parse template source files to extract all valid Honeybee equipment strings.

    Uses ast.parse() to safely extract string values from every ``str, Enum``
    class in the template files. This avoids eval(), exec(), and importing
    pydantic-dependent modules.

    Returns:
        A flat set of all valid equipment-type strings drawn from the
        template files, plus the extractor's generic labels.
    """
    valid: set[str] = set()

    for filepath in _TEMPLATE_FILES:
        if not os.path.exists(filepath):
            continue

        with open(filepath, encoding="utf-8") as fh:
            source = fh.read()

        tree = ast.parse(source)

        for node in ast.walk(tree):
            # We only care about class definitions that inherit from (str, Enum)
            if not isinstance(node, ast.ClassDef):
                continue

            is_str_enum = False
            for base in node.bases:
                # Covers both `str` and `Enum` appearing as separate bases
                if isinstance(base, ast.Name) and base.id in ("str", "Enum"):
                    is_str_enum = True
                    break
            if not is_str_enum:
                continue

            # Walk the class body for assignments like:   member = 'SomeValue'
            for item in node.body:
                if not isinstance(item, ast.Assign):
                    continue
                if isinstance(item.value, ast.Constant) and isinstance(
                    item.value.value, str
                ):
                    valid.add(item.value.value)

    # Merge extractor generic labels
    valid.update(_EXTRACTOR_GENERIC_LABELS)
    return valid


def _check_templates(
    hvac_data: dict[str, dict[str, str]],
    valid_templates: set[str],
) -> list[str]:
    """Return a list of (zone, template) error strings for unrecognised templates.

    Args:
        hvac_data: Zone-level HVAC extraction results.
        valid_templates: All valid Honeybee HVAC template strings.

    Returns:
        A list of human-readable error strings, empty when all templates pass.
    """
    errors: list[str] = []
    for zone, data in hvac_data.items():
        t = data.get("template", "")
        if t == "Unknown":
            errors.append(f'    - {zone} → "Unknown" (no equipment matched)')
        elif t not in valid_templates:
            errors.append(f'    - {zone} → "{t}" (not a recognised Honeybee type)')
    return errors


def _check_economizers(hvac_data: dict[str, dict[str, str]]) -> list[str]:
    """Return error strings for zones with invalid economizer values.

    Args:
        hvac_data: Zone-level HVAC extraction results.

    Returns:
        A list of human-readable error strings, empty when all values pass.
    """
    errors: list[str] = []
    for zone, data in hvac_data.items():
        template = data.get("template", "")
        econ = data.get("economizer", "")
        # Unconditioned zones use N/A — skip
        if template == "Unconditioned":
            continue
        if econ not in _VALID_ECONOMIZER and econ != "N/A":
            errors.append(f'    - {zone} → "{econ}"')
    return errors


def _check_dcv(hvac_data: dict[str, dict[str, str]]) -> list[str]:
    """Return error strings for zones with invalid DCV values.

    Args:
        hvac_data: Zone-level HVAC extraction results.

    Returns:
        A list of human-readable error strings, empty when all values pass.
    """
    errors: list[str] = []
    for zone, data in hvac_data.items():
        dcv = data.get("dcv", "")
        if dcv not in _VALID_DCV:
            errors.append(f'    - {zone} → "{dcv}"')
    return errors


def _check_unconditioned_consistency(
    hvac_data: dict[str, dict[str, str]],
) -> list[str]:
    """Return error strings for unconditioned zones with non-N/A DCV or economizer.

    Args:
        hvac_data: Zone-level HVAC extraction results.

    Returns:
        A list of human-readable error strings, empty when all values pass.
    """
    errors: list[str] = []
    for zone, data in hvac_data.items():
        if data.get("template") == "Unconditioned":
            if data.get("dcv") != "N/A" or data.get("economizer") != "N/A":
                errors.append(
                    f"    - {zone} → dcv={data.get('dcv')!r}, "
                    f"economizer={data.get('economizer')!r} (expected N/A)"
                )
    return errors


def validate_hvac_results(
    hvac_data: dict[str, dict[str, str]],
    file_label: str,
) -> bool:
    """Cross-check extracted HVAC data against the Honeybee template definitions.

    Performs five checks:
    1. Template name is a recognised Honeybee equipment type (or a known generic label).
    2. Economizer value is a valid ``AllAirEconomizerType`` string.
    3. DCV value is one of ``{Yes, No, N/A}``.
    4. Unconditioned zones have DCV and Economizer both set to ``N/A``.
    5. No zone retains the catch-all ``Unknown`` template.

    Prints a formatted pass/fail summary to stdout.

    Args:
        hvac_data: The dictionary returned by ``extract_hvac_systems()``.
        file_label: A human-readable label for the file being validated
            (typically the IDF filename stem).

    Returns:
        ``True`` if every check passes, ``False`` if any check fails.
    """
    if not hvac_data:
        _print_line(file_label)
        print("  [WARN] No HVAC data to validate.")
        _print_result(True, 0)
        return True

    valid_templates = build_valid_template_set()
    total_zones = len(hvac_data)
    all_errors: list[str] = []

    # --- Check 1: Template names ---
    tmpl_errors = _check_templates(hvac_data, valid_templates)

    # --- Check 2: Economizer values ---
    econ_errors = _check_economizers(hvac_data)

    # --- Check 3: DCV values ---
    dcv_errors = _check_dcv(hvac_data)

    # --- Check 4: Unconditioned consistency ---
    uncond_errors = _check_unconditioned_consistency(hvac_data)

    _print_line(file_label)
    print(f"  [INFO] {total_zones} zone(s) validated")
    _print_zone_detail_table(hvac_data, valid_templates)

    if tmpl_errors:
        print(f"  [FAIL] {len(tmpl_errors)} zone(s) have unrecognised templates:")
        for e in tmpl_errors:
            print(e)
        all_errors.extend(tmpl_errors)
    else:
        print("  [OK] All templates are recognised Honeybee types")

    if econ_errors:
        print(f"  [FAIL] {len(econ_errors)} zone(s) have invalid economizer values:")
        for e in econ_errors:
            print(e)
        all_errors.extend(econ_errors)
    else:
        print("  [OK] All economizer values are valid")

    if dcv_errors:
        print(f"  [FAIL] {len(dcv_errors)} zone(s) have invalid DCV values:")
        for e in dcv_errors:
            print(e)
        all_errors.extend(dcv_errors)
    else:
        print("  [OK] All DCV values are valid")

    if uncond_errors:
        print(
            f"  [FAIL] {len(uncond_errors)} unconditioned zone(s) have "
            "inconsistent DCV/Economizer:"
        )
        for e in uncond_errors:
            print(e)
        all_errors.extend(uncond_errors)
    else:
        print("  [OK] Unconditioned zone consistency check passed")

    passed = len(all_errors) == 0
    _print_result(passed, len(all_errors))
    return passed


def _print_line(file_label: str) -> None:
    """Print the section header for the validation summary.

    Args:
        file_label: The IDF file label to display.
    """
    separator = "=" * (len(file_label) + 22)
    print(f"\n{separator}")
    print(f"  HVAC Validation: {file_label}")
    print(separator)


def _print_zone_detail_table(
    hvac_data: dict[str, dict[str, str]],
    valid_templates: set[str],
) -> None:
    """Print a formatted table of zone → Honeybee HVAC template mappings.

    Each row shows the zone name, the matched Honeybee template, DCV status,
    and economizer configuration. An inline status marker flags any value
    that fails validation so issues are visible at a glance.

    Args:
        hvac_data: Zone-level HVAC extraction results.
        valid_templates: Set of recognised Honeybee template strings.
    """
    if not hvac_data:
        return

    # Determine column widths dynamically
    zone_w = max(len(z) for z in hvac_data) + 2
    tmpl_w = max(
        len(d.get("template", "")) for d in hvac_data.values()
    ) + 2
    dcv_w = 6
    econ_w = max(
        len(d.get("economizer", "")) for d in hvac_data.values()
    ) + 2

    # Header row
    h_zone = "Zone".ljust(zone_w)
    h_tmpl = "Honeybee HVAC Template".ljust(tmpl_w)
    h_dcv  = "DCV".ljust(dcv_w)
    h_econ = "Economizer"
    div = "-" * (zone_w + tmpl_w + dcv_w + econ_w + 10)

    print(f"\n  {div}")
    print(f"  {h_zone}  {h_tmpl}  {h_dcv}  {h_econ}")
    print(f"  {div}")

    for zone, data in sorted(hvac_data.items()):
        template  = data.get("template", "")
        dcv       = data.get("dcv", "")
        economizer = data.get("economizer", "")

        # Build status markers
        tmpl_flag = (
            "  [WARN]" if (template not in valid_templates or template == "Unknown")
            else ""
        )
        dcv_flag   = "  [WARN]" if dcv not in _VALID_DCV else ""
        econ_ok    = economizer in _VALID_ECONOMIZER or economizer == "N/A"
        econ_flag  = "  [WARN]" if not econ_ok else ""

        print(
            f"  {zone.ljust(zone_w)}"
            f"  {(template + tmpl_flag).ljust(tmpl_w + 9)}"
            f"  {(dcv + dcv_flag).ljust(dcv_w + 9)}"
            f"  {economizer}{econ_flag}"
        )

    print(f"  {div}\n")


def _print_result(passed: bool, issue_count: int) -> None:
    """Print the final result line.

    Args:
        passed: Whether all checks passed.
        issue_count: Total number of individual issues found.
    """
    if passed:
        print("  Result: PASS")
    else:
        print(f"  Result: FAIL  ({issue_count} issue(s) found)")
    print("")
