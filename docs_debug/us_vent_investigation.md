# US Model Ventilation Investigation Plan

## 🎯 Problem Statement
In the Canadian (CHV) model (`17_18_Two_Storey_House - Calgary.idf`), the `ZoneVentilation:DesignFlowRate` object explicitly drives the exhaust fan flow rate (`0.02832 m³/s`). 

However, in the US Low-Rise model (`US+SF+CZ6A+gasfurnace+unheatedbsmt+IECC_2024.idf`), the `ZoneVentilation:DesignFlowRate` object is defined with a `0 m³/s` flow rate, while the equivalent `0.02832 m³/s` flow is assigned to the `DesignSpecification:OutdoorAir` (DSOA) object. 

**Question:** Which Honeybee component (`HB Fan Ventilation` vs `HB Ventilation`) should be used to map this US model configuration?

---

## 🔍 Investigation Steps

### Step 1 — Review the Honeybee Components again
*   **`HB Fan Ventilation`**: Direct mapping to `ZoneVentilation:DesignFlowRate`. (It models a dedicated, standalone fan).
*   **`HB Ventilation`**: Direct mapping to `DesignSpecification:OutdoorAir`. (It specifies the minimum outdoor air that an HVAC unit needs to supply to a zone).

### Step 2 — Investigate the US Model's HVAC Architecture
Why did the US model author put the flow into DSOA instead of ZoneVentilation?
*   **Hypothesis A (System Type):** The US model uses a central forced-air system (e.g., Gas Furnace with an AirLoopHVAC) that includes a fresh air intake duct. In this design, the HVAC system itself fulfills the ventilation requirement. EnergyPlus requires DSOA objects to tell the AirLoop controller how much outdoor air to mix in.
*   **Hypothesis B (Placeholder):** The ZoneVentilation object with `0` flow was left as a placeholder by the modeling script (like EnergyPlus's OpenStudio measures), and the actual ventilation is entirely handled by the HVAC system.

### Step 3 — Determine the Correct Honeybee Action
If the US model delivers ventilation *through the HVAC system*, then `HB Ventilation` is the correct component. If it delivers ventilation *via a standalone fan*, then `HB Fan Ventilation` is correct.

*   **Action Plan:** Let's look inside `US+SF+CZ6A...idf` to see the HVAC system (e.g., `Controller:OutdoorAir` and `AirLoopHVAC`) and confirm if it links to the `SZ_DSOA_living_unit1` object.

## 📊 Investigation Results

By inspecting the US Low-Rise model (`US+SF+CZ6A...idf`), we found exactly how the ventilation is being handled. 

The US model uses a whole-house **Energy Recovery Ventilator (ERV)** integrated into the forced-air HVAC system, rather than a standalone exhaust fan. 

Here is the exact object from the US IDF:
```idf
ZoneHVAC:EnergyRecoveryVentilator,
    ERV_unit1,                     !- Name
    always_avail,            !- Availability Schedule Name
    OA_Heat_Recovery_Unit1,  !- Heat Exchanger Name
    0.0283168464628752,       !- Supply Air Flow Rate {m3/s}
    0.0283168464628752,       !- Exhaust Air Flow Rate {m3/s}
    OASupplyFan_unit1,       !- Supply Air Fan Name
    OAExhaustFan_unit1;      !- Exhaust Air Fan Name
```

### ✨ What this means

1.  **Why is `ZoneVentilation:DesignFlowRate` set to 0?**
    Because the house does not use a standalone "dumb" exhaust fan (like a basic bathroom fan) for its primary whole-house ventilation. The `ZoneVentilation` object was intentionally zeroed out so it wouldn't double-count against the ERV.

2.  **Why is `DesignSpecification:OutdoorAir` set to 0.02832 m³/s?**
    The `DesignSpecification:OutdoorAir` (DSOA) object is used by EnergyPlus's sizing and AirLoop systems to define the *minimum fresh air requirement* that the HVAC equipment (in this case, the `ZoneHVAC:EnergyRecoveryVentilator`) must bring in from the outside. 
    Notice that the ERV's Supply Air Flow Rate is exactly `0.0283168464628752 m³/s` — it was sized perfectly to meet the DSOA requirement!

---

## 🏁 Conclusion & Recommendations for Honeybee

You asked: *"Should I use the HB Ventilation component to model the ventilation as this one has DesignSpecification:OutdoorAir?"*

**Answer: YES.**

If you are trying to replicate the architecture of the **US Low-Rise Model**, you should use the **HB Ventilation** component, **NOT** the HB Fan Ventilation component.

| Goal | Which Component to Use? | What EnergyPlus Object it Creates | Why? |
| :--- | :--- | :--- | :--- |
| **Replicate CHV Model (Canada)** | `HB Fan Ventilation` | `ZoneVentilation:DesignFlowRate` | Models a standalone exhaust fan blowing air directly outside (no heat recovery). |
| **Replicate US Low-Rise Model** | `HB Ventilation` | `DesignSpecification:OutdoorAir` | Specifies the fresh air load for an HVAC system (like an ERV or AirLoop) to process and condition. |

### How to set up `HB Ventilation` in Grasshopper:
```
HB Ventilation
  └── flow_per_area = 0
  └── flow_per_person = 0
  └── flow_per_zone = 0.02832 m³/s  <-- USE THIS INPUT
  └── ach = 0
```
*Note: Make sure your underlying Honeybee HVAC system (e.g., Ideal Air Loads or a detailed Ironbug system) is configured with Heat Recovery if you want to perfectly match the US model's ERV energy performance.*
