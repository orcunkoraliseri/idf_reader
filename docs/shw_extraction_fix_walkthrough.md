# SHW Extraction Walkthrough: Support for WaterHeater:Mixed

## 1. Problem Identification
In certain EnergyPlus prototype files, specifically the **MidRise Apartment**, Service Hot Water (SHW) usage was reported as **0** in the and metadata reports. However, in the **HighRise Apartment**, these values were populated correctly.

### Root Cause
- **HighRise Apartment:** Uses the `WaterUse:Equipment` object, which maps directly to a zone or uses a heuristic suffix mapping.
- **MidRise Apartment:** Omits `WaterUse:Equipment` entirely. Instead, it defines SHW usage natively within `WaterHeater:Mixed` objects by assigning a `Peak Use Flow Rate` ($m^3/s$) directly to the heater and linking the heater to a thermal zone via the `Ambient Temperature Zone Name` field.

## 2. Implemented Solution
We updated the `extract_water_use` function in `extractors.py` to support both modeling workflows.

### New Logic Flow:
1. **Primary Extraction:** The script continues to look for `WaterUse:Equipment` objects.
2. **Supplemental Extraction:** The script now also checks all `WaterHeater:Mixed` objects.
3. **Zone Mapping:** 
   - It checks if the heater's `Ambient Temperature Indicator` is set to `Zone`.
   - It retrieves the `Ambient Temperature Zone Name` to associate the water load with the specific apartment unit.
4. **Data Normalization:** 
   - It retrieves the `Peak Use Flow Rate` (Field 28, index 27).
   - It converts $m^3/s$ to $L/h \cdot m^2$ and attributes it to the mapped zone.

## 3. Verification
Below is the comparison of the extracted metadata for MidRise after the update:

### ASHRAE 90.1 MidRise Apartment (Denver)
| Zone | Floor Area | SHW [L/h.m2] | Status |
| :--- | :--- | :--- | :--- |
| G N1 Apartment | 88.25 | **0.1332** | ✅ Resolved |
| M N1 Apartment | 88.25 | **0.2664** | ✅ Resolved |
| Office | 88.25 | 0 | ✅ Correct (No SHW) |

The SHW values are now correctly attributed to the individual residential units based on their specific water heater assignments.
