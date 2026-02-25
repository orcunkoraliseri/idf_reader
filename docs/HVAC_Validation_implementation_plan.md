# HVAC Validation Implementation Plan

## Status: ✅ IMPLEMENTED

---

## Goal Description

Create a **post-extraction validation function** that cross-checks the HVAC template
strings produced by `extract_hvac_systems()` against the **canonical set of valid
Honeybee HVAC templates** defined in `Templates/HVAC_templates/`. The validator runs
automatically after each HTML report is generated and prints a clear pass/fail summary
to the terminal.

The purpose is **not** to re-run the extraction — it is to verify that the extracted
HVAC template strings, DCV values, and economizer types are valid members of the
Honeybee taxonomy and flag anything suspicious.

---

## Design Overview

### What Gets Validated

| Check | Description | Pass Condition |
|---|---|---|
| **Template Name** | Is the extracted `Honeybee HVAC Template` string a recognised Honeybee equipment type? | String exists in the canonical enum set built from `allair.py`, `doas.py`, `heatcool.py` |
| **Economizer Type** | Is the `Economizer Configuration` a valid `AllAirEconomizerType` value? | String exists in `{NoEconomizer, DifferentialDryBulb, DifferentialEnthalpy, DifferentialDryBulbAndEnthalpy, FixedDryBulb, FixedEnthalpy, ElectronicEnthalpy}` |
| **DCV Value** | Is the `DCV Status` a recognised value? | String is one of `{Yes, No, N/A}` |
| **Unconditioned Consistency** | If template is `Unconditioned`, DCV and Economizer must be `N/A` | Both fields are `N/A` |
| **Unknown Template** | Template should never be `Unknown` after extraction | Template ≠ `Unknown` |

### What Gets Printed

After each file's HTML report is generated, the validator prints a console summary:

```
━━━ HVAC Validation: ASHRAE901_OfficeSmall_STD2022_Denver ━━━
  ✔ 5 zones validated
  ✔ All templates are recognised Honeybee types
  ✔ All economizer values are valid
  ✔ All DCV values are valid
  Result: PASS ✅
```

Or, if issues exist:

```
━━━ HVAC Validation: ASHRAE901_Hospital_STD2022_Denver ━━━
  ✔ 45 zones validated
  ✘ 2 zones have unrecognised templates:
      - OR1 → "Unknown"
      - ER_Triage → "Unknown"
  ✔ All economizer values are valid
  ✘ 1 zone has unexpected DCV value:
      - Kitchen → "Maybe"
  Result: FAIL ❌ (3 issues)
```

---

## Proposed Changes

### New File: `hvac_validator.py`

A self-contained validation module with no external dependencies beyond the standard
library and the local template files.

#### [CREATE] `hvac_validator.py`

**Functions:**

1. **`build_valid_template_set() -> set[str]`**
   - Reads `Templates/HVAC_templates/allair.py`, `doas.py`, and `heatcool.py`.
   - Parses every `str, Enum` class to extract the string values from each member.
   - Uses `ast.parse()` to safely extract enum member values (no `eval`, no `exec`,
     no `import` of the template files — they depend on pydantic, which may not be
     installed).
   - Returns a flat `set[str]` of all valid equipment-type strings. Also includes
     special strings: `Unconditioned`, `Baseboard`, `Radiant`, `UnitHeater`,
     `Dehumidifier`, `IdealLoads`, since the extractor may produce these as generic
     class-level labels.

2. **`build_valid_economizer_set() -> set[str]`**
   - Returns the fixed set from `AllAirEconomizerType`:
     ```python
     {"NoEconomizer", "DifferentialDryBulb", "DifferentialEnthalpy",
      "DifferentialDryBulbAndEnthalpy", "FixedDryBulb", "FixedEnthalpy",
      "ElectronicEnthalpy"}
     ```

3. **`build_valid_dcv_set() -> set[str]`**
   - Returns `{"Yes", "No", "N/A"}`.

4. **`validate_hvac_results(hvac_data: dict[str, dict[str, str]], file_label: str) -> bool`**
   - The main validation entry point called from `idf_processor.py`.
   - Accepts:
     - `hvac_data`: The same dictionary returned by `extract_hvac_systems()`.
     - `file_label`: A human-readable file name for the printed summary.
   - Performs all checks listed in the table above.
   - Prints the coloured pass/fail summary to stdout.
   - Returns `True` if all checks pass, `False` if any fail.

**Design Decisions:**
- Uses `ast.parse()` to read template enum values — this avoids `eval()` / `exec()` /
  importing pydantic-dependent modules and complies with the safety rules.
- Does **not** read or parse the `.html` output file. Instead, it validates the
  in-memory `hvac_data` dictionary directly after extraction, which is simpler and more
  reliable than HTML scraping. The HTML output is generated from this same dictionary,
  so validating the source data is equivalent.
- Hardcodes the economizer and DCV sets since they are small and stable — this keeps
  the validator independent of the template files for these two checks.

---

### Modified File: `idf_processor.py`

#### [MODIFY] `idf_processor.py`

- Import `validate_hvac_results` from `hvac_validator`.
- After the call to `generate_reports()` in `process_file()`, add:
  ```python
  # Validate HVAC extraction results
  validate_hvac_results(hvac_data, file_name)
  ```

---

## File-by-File Summary

| File | Action | Description |
|---|---|---|
| `hvac_validator.py` | **CREATE** | New module: enum parsing, validation checks, terminal output |
| `idf_processor.py` | **MODIFY** | Add validation call after report generation |
| `main.py` | No change | — |
| `extractors.py` | No change | — |
| `report_generator.py` | No change | — |

---

## Template Enum Values Inventory

Below is the complete set of valid template strings that `build_valid_template_set()`
will extract. This serves as the reference for the validation.

### From `allair.py`
| Enum Class | Values |
|---|---|
| `VAVEquipmentType` | `VAV_Chiller_Boiler`, `VAV_Chiller_ASHP`, `VAV_Chiller_DHW`, `VAV_Chiller_PFP`, `VAV_Chiller_GasCoil`, `VAV_ACChiller_Boiler`, `VAV_ACChiller_ASHP`, `VAV_ACChiller_DHW`, `VAV_ACChiller_PFP`, `VAV_ACChiller_GasCoil`, `VAV_DCW_Boiler`, `VAV_DCW_ASHP`, `VAV_DCW_DHW`, `VAV_DCW_PFP`, `VAV_DCW_GasCoil` |
| `PVAVEquipmentType` | `PVAV_Boiler`, `PVAV_ASHP`, `PVAV_DHW`, `PVAV_PFP`, `PVAV_BoilerElectricReheat` |
| `PSZEquipmentType` | `PSZAC_ElectricBaseboard`, `PSZAC_BoilerBaseboard`, `PSZAC_DHWBaseboard`, `PSZAC_GasHeaters`, `PSZAC_ElectricCoil`, `PSZAC_GasCoil`, `PSZAC_Boiler`, `PSZAC_ASHP`, `PSZAC_DHW`, `PSZAC`, `PSZAC_DCW_ElectricBaseboard`, `PSZAC_DCW_BoilerBaseboard`, `PSZAC_DCW_GasHeaters`, `PSZAC_DCW_ElectricCoil`, `PSZAC_DCW_GasCoil`, `PSZAC_DCW_Boiler`, `PSZAC_DCW_ASHP`, `PSZAC_DCW_DHW`, `PSZAC_DCW`, `PSZHP` |
| `PTACEquipmentType` | `PTAC_ElectricBaseboard`, `PTAC_BoilerBaseboard`, `PTAC_DHWBaseboard`, `PTAC_GasHeaters`, `PTAC_ElectricCoil`, `PTAC_GasCoil`, `PTAC_Boiler`, `PTAC_ASHP`, `PTAC_DHW`, `PTAC`, `PTHP` |
| `FurnaceEquipmentType` | `Furnace`, `Furnace_Electric` |

### From `doas.py`
| Enum Class | Values |
|---|---|
| `FCUwithDOASEquipmentType` | `DOAS_FCU_Chiller_Boiler`, `DOAS_FCU_Chiller_ASHP`, `DOAS_FCU_Chiller_DHW`, `DOAS_FCU_Chiller_ElectricBaseboard`, `DOAS_FCU_Chiller_GasHeaters`, `DOAS_FCU_Chiller`, `DOAS_FCU_ACChiller_Boiler`, `DOAS_FCU_ACChiller_ASHP`, `DOAS_FCU_ACChiller_DHW`, `DOAS_FCU_ACChiller_ElectricBaseboard`, `DOAS_FCU_ACChiller_GasHeaters`, `DOAS_FCU_ACChiller`, `DOAS_FCU_DCW_Boiler`, `DOAS_FCU_DCW_ASHP`, `DOAS_FCU_DCW_DHW`, `DOAS_FCU_DCW_ElectricBaseboard`, `DOAS_FCU_DCW_GasHeaters`, `DOAS_FCU_DCW` |
| `WSHPwithDOASEquipmentType` | `DOAS_WSHP_FluidCooler_Boiler`, `DOAS_WSHP_CoolingTower_Boiler`, `DOAS_WSHP_GSHP`, `DOAS_WSHP_DCW_DHW` |
| `VRFwithDOASEquipmentType` | `DOAS_VRF` |
| `RadiantwithDOASEquipmentType` | `DOAS_Radiant_Chiller_Boiler`, `DOAS_Radiant_Chiller_ASHP`, `DOAS_Radiant_Chiller_DHW`, `DOAS_Radiant_ACChiller_Boiler`, `DOAS_Radiant_ACChiller_ASHP`, `DOAS_Radiant_ACChiller_DHW`, `DOAS_Radiant_DCW_Boiler`, `DOAS_Radiant_DCW_ASHP`, `DOAS_Radiant_DCW_DHW` |

### From `heatcool.py`
| Enum Class | Values |
|---|---|
| `FCUEquipmentType` | `FCU_Chiller_Boiler`, `FCU_Chiller_ASHP`, `FCU_Chiller_DHW`, `FCU_Chiller_ElectricBaseboard`, `FCU_Chiller_GasHeaters`, `FCU_Chiller`, `FCU_ACChiller_Boiler`, `FCU_ACChiller_ASHP`, `FCU_ACChiller_DHW`, `FCU_ACChiller_ElectricBaseboard`, `FCU_ACChiller_GasHeaters`, `FCU_ACChiller`, `FCU_DCW_Boiler`, `FCU_DCW_ASHP`, `FCU_DCW_DHW`, `FCU_DCW_ElectricBaseboard`, `FCU_DCW_GasHeaters`, `FCU_DCW` |
| `BaseboardEquipmentType` | `ElectricBaseboard`, `BoilerBaseboard`, `ASHPBaseboard`, `DHWBaseboard` |
| `EvaporativeCoolerEquipmentType` | `EvapCoolers_ElectricBaseboard`, `EvapCoolers_BoilerBaseboard`, `EvapCoolers_ASHPBaseboard`, `EvapCoolers_DHWBaseboard`, `EvapCoolers_Furnace`, `EvapCoolers_UnitHeaters`, `EvapCoolers` |
| `WSHPEquipmentType` | `WSHP_FluidCooler_Boiler`, `WSHP_CoolingTower_Boiler`, `WSHP_GSHP`, `WSHP_DCW_DHW` |
| `ResidentialEquipmentType` | `ResidentialAC_ElectricBaseboard`, `ResidentialAC_BoilerBaseboard`, `ResidentialAC_ASHPBaseboard`, `ResidentialAC_DHWBaseboard`, `ResidentialAC_ResidentialFurnace`, `ResidentialAC`, `ResidentialHP`, `ResidentialHPNoCool`, `ResidentialFurnace` |
| `WindowACEquipmentType` | `WindowAC_ElectricBaseboard`, `WindowAC_BoilerBaseboard`, `WindowAC_ASHPBaseboard`, `WindowAC_DHWBaseboard`, `WindowAC_Furnace`, `WindowAC_GasHeaters`, `WindowAC` |
| `VRFEquipmentType` | `VRF` |
| `GasUnitHeaterEquipmentType` | `GasHeaters` |
| `RadiantEquipmentType` | `Radiant_Chiller_Boiler`, `Radiant_Chiller_ASHP`, `Radiant_Chiller_DHW`, `Radiant_ACChiller_Boiler`, `Radiant_ACChiller_ASHP`, `Radiant_ACChiller_DHW`, `Radiant_DCW_Boiler`, `Radiant_DCW_ASHP`, `Radiant_DCW_DHW` |

### Additional valid labels (from extractor, not in Honeybee enums)
These are generic labels the extractor may produce when the zone doesn't match a
specific equipment type enum:
- `Unconditioned`, `Baseboard`, `Radiant`, `UnitHeater`, `Dehumidifier`, `IdealLoads`,
  `FCUwithDOASAbridged`, `WSHP`, `PTAC`, `PTHP`

---

## Verification Plan

### Automated
1. Run `python main.py` and select a single file (e.g., OfficeSmall).
2. Confirm the validation summary prints after the report generation line.
3. Verify the result says `PASS ✅` for a known-good file.

### Edge Cases
4. Run with Hospital IDF — verify no `Unknown` templates remain (they were
   fixed previously, but this will catch regressions).
5. Manually inject a bad template name into `hvac_data` (temporarily) and confirm
   the validator prints `FAIL ❌`.

### Manual
6. Review the validator's printed output for visual clarity and completeness.
