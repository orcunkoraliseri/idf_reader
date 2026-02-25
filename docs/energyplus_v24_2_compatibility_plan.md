# EnergyPlus V24.2 Extraction Compatibility Plan

## Goal Description
The new EnergyPlus 24.2 prototype `Reference_16_1_Midrise Apartment - Calgary_V242.idf` introduces structural changes compared to older IDFs. Currently, the extraction script is failing to extract Ventilation (reads 0) and Thermostat Setpoints (reads 0).

### Investigation Findings
1.  **Ventilation (`DESIGNSPECIFICATION:OUTDOORAIR`):**
    -   In earlier IDFs, ventilation was primarily given in `per person` or `per area` fields.
    -   In V24.2, ventilation is strictly defined as `Flow/Zone` (m3/s per zone) in Field 4 (index 4). Our current parser limits the index check, sometimes missing Field 4 if the list length varies in newer versions.
2.  **Thermostats (`ZONECONTROL:THERMOSTAT` -> `THERMOSTATSETPOINT:DUALSETPOINT`):**
    -   Older IDFs mapped directly to explicit heating/cooling schedules in the thermostat object.
    -   V24.2 maps `ZONECONTROL:THERMOSTAT` to a `ThermostatSetpoint:DualSetpoint` object. This dual setpoint object then points to the actual Heating/Cooling schedules (e.g., `16_APT_HTGSETP_SCH`).
    -   Our script doesn't trace this nested relationship.
3.  **Water Use (`WATERUSE:EQUIPMENT` vs `WATERHEATER:MIXED`):** 
    -   V24.2 maps water use explicitly via `WATERUSE:EQUIPMENT` linked by zone name (Field 7/index 7), which is partially supported but needs a robust exact-match fallback.


## Proposed Changes

### [MODIFY] extractors.py

#### 1. `extract_ventilation`
- Update the index parsing for `DESIGNSPECIFICATION:OUTDOORAIR` to safely check if the `Outdoor Air Method` (Field 1, index 1) is `Flow/Zone`. 
- If `Flow/Zone`, extract the value from Field 4 (index 4) and manually normalize it to per-area (m3/s.m2) using the zone's floor area.

#### 2. `extract_thermostats`
- Add a lookup dictionary for `ThermostatSetpoint:DualSetpoint` objects to easily find heating/cooling schedule names based on the DualSetpoint object name.
- Update the `ZONECONTROL:THERMOSTAT` loop to check if the control type is `ThermostatSetpoint:DualSetpoint`. If so, trace it to the nested schedule names before extracting the constant values from `SCHEDULE:COMPACT`.

## Verification Plan

### Automated Tests
- Process the `Reference_16_1_Midrise Apartment - Calgary_V242.idf` file.
- Verify that **Ventilation [m3/s.m2]** is successfully populated (e.g., ~$0.00048 m3/s.m2).
- Verify that **Htg Setpoint [C]** and **Clg Setpoint [C]** are non-zero (e.g., 20/25 for apartments, 15.6/29.4 for office).
