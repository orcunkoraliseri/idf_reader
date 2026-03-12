# IDF Multiplier Expansion Tool

Expand EnergyPlus zone multipliers into explicit individual thermal zones for detailed zone-level control and complete 3D visualization.

## Problem Statement

ASHRAE prototype building models use **Zone Multipliers** to reduce model complexity:

| Building    | Modeled Zones | Multiplier | Effective Zones |
|-------------|---------------|------------|-----------------|
| MidRise     | 27            | 2x (middle)| 45              |
| HighRise    | 27            | 8x (middle)| 99              |

**Limitations of multipliers:**
1. Cannot assign different inputs to individual apartments on the same floor type
2. 3D visualization only shows the modeled floors, not all physical floors
3. Cannot apply unique occupancy schedules per apartment

## Proposed Solution

Create `expand_idf_multipliers.py` that converts multiplied zones into explicit individual zones using the `eppy` library for IDF manipulation.

---

## Implementation Status

> [!NOTE]
> Last updated: December 2024. Implementation is in progress with significant HVAC handling improvements.

### Completed Features
- ✅ Zone duplication with Z-offset
- ✅ Surface duplication (BuildingSurface:Detailed, FenestrationSurface:Detailed)
- ✅ Zone-level loads (People, Lights, ElectricEquipment, InternalMass)
- ✅ Zone ventilation/infiltration objects
- ✅ Zone HVAC Equipment Connections
- ✅ Zone HVAC Equipment Lists and NodeLists
- ✅ Sizing:Zone objects
- ✅ ZoneControl:Thermostat objects
- ✅ WaterHeater:Mixed objects
- ✅ ERV systems and related components
- ✅ AirLoopHVAC systems (with abbreviated zone naming)
- ✅ SetpointManagers
- ✅ AvailabilityManagers
- ✅ Coils (Heating, Cooling, Fuel)

### In Progress / Known Issues
- ⚠️ EMS (EnergyManagementSystem) sensor/actuator references
- ⚠️ Complex node connection validation

---

## Technical Analysis

### Current IDF Structure (MidRise Example)

```
ZoneGroup,
  Middle Floors,           !- Name
  Mid Floor List,          !- Zone List Name
  2;                       !- Zone List Multiplier (floors 2-3)

ZoneList,
  Mid Floor List,
  M SW Apartment,          !- Zone 1
  M NW Apartment,          !- Zone 2
  ...
  M Corridor;              !- Zone 9
```

### Objects That Reference Zones (Comprehensive List)

> [!IMPORTANT]
> Each of these object types must be duplicated and renamed when expanding zones.

#### Zone-Level Objects (Using Zone Name Field)
| Object Type | Zone Field | Action Required |
|-------------|-----------|-----------------|
| `Zone` | `Name` | Duplicate with new name + Z-offset |
| `BuildingSurface:Detailed` | `Zone_Name` | Duplicate + adjust vertices |
| `FenestrationSurface:Detailed` | (via parent surface) | Duplicate + adjust vertices |
| `InternalMass` | `Zone_or_ZoneList_Name` | Duplicate with zone reference |
| `People` | `Zone_or_ZoneList_or_Space_or_SpaceList_Name` | Duplicate with zone reference |
| `Lights` | `Zone_or_ZoneList_or_Space_or_SpaceList_Name` | Duplicate with zone reference |
| `ElectricEquipment` | `Zone_or_ZoneList_or_Space_or_SpaceList_Name` | Duplicate with zone reference |
| `ZoneInfiltration:DesignFlowRate` | `Zone_or_ZoneList_or_Space_or_SpaceList_Name` | Duplicate with zone reference |
| `ZoneVentilation:DesignFlowRate` | `Zone_or_ZoneList_or_Space_or_SpaceList_Name` | Duplicate with zone reference |
| `ZoneVentilation:WindandStackOpenArea` | `Zone_or_Space_Name` | Duplicate with zone reference |
| `Sizing:Zone` | `Zone_or_ZoneList_Name` | Duplicate with zone reference |
| `ZoneControl:Thermostat` | `Zone_or_ZoneList_Name` | Duplicate with zone reference |
| `WaterHeater:Mixed` | `Ambient_Temperature_Zone_Name` | Duplicate with zone reference |

#### HVAC Objects (Using Zone Name or Zone-Based Naming Pattern)
| Object Type | Naming Pattern | Action Required |
|-------------|---------------|-----------------|
| `ZoneHVAC:EquipmentConnections` | Zone_Name field | Update zone and node references |
| `ZoneHVAC:EquipmentList` | `{ZoneName} Equipment` | Duplicate with new zone name |
| `NodeList` | `{ZoneName} Inlet Nodes` | Duplicate with new zone name |
| `ZoneHVAC:EnergyRecoveryVentilator` | `{ZoneName} ERV` | Duplicate and update all fields |
| `ZoneHVAC:EnergyRecoveryVentilator:Controller` | `{ZoneName} ERV Ctrl` | Duplicate |
| `ZoneHVAC:IdealLoadsAirSystem` | `{ZoneName}` in name | Duplicate |
| `ZoneHVAC:AirDistributionUnit` | `{ZoneName} PSZ ADU` | Duplicate |
| `HeatExchanger:AirToAir:SensibleAndLatent` | `{ZoneName} OA Heat Exchanger` | Duplicate |
| `OutdoorAir:Node` | `{ZoneName} Outside Air Node` | Duplicate |
| `Fan:SystemModel`, `Fan:OnOff`, `Fan:ConstantVolume` | Zone-based naming | Duplicate |
| `Coil:Heating:Electric`, `Coil:Heating:Fuel` | Zone-based naming | Duplicate |
| `Coil:Cooling:DX:SingleSpeed`, `Coil:Heating:DX:SingleSpeed` | Zone-based naming | Duplicate |

#### AirLoopHVAC Objects (Using Abbreviated Zone Codes)
> [!WARNING]
> These objects use abbreviated zone codes (e.g., "M SW Apartment" → "MSW") in their names.

| Object Type | Naming Pattern Example | Action Required |
|-------------|----------------------|-----------------|
| `AirLoopHVAC` | `Split MSW` | Duplicate with abbreviated name replacement |
| `AirLoopHVAC:UnitarySystem` | `Split MSW_Unitary_Package_DX` | Duplicate |
| `AirLoopHVAC:ZoneSplitter` | `Split MSW Zone Splitter` | Duplicate |
| `AirLoopHVAC:ZoneMixer` | `Split MSW Zone Mixer` | Duplicate |
| `AirLoopHVAC:SupplyPath` | `Split MSW Supply Path` | Duplicate |
| `AirLoopHVAC:ReturnPath` | `Split MSW Return Path` | Duplicate |
| `AirLoopHVAC:OutdoorAirSystem` | `Split MSW_OA_Sys` | Duplicate |
| `AirLoopHVAC:ControllerList` | `Split MSW Controllers` | Duplicate |
| `BranchList` | `Split MSW Air Loop Branches` | Duplicate |
| `Branch` | `Split MSW Air Loop Main Branch` | Duplicate |
| `Sizing:System` | References AirLoop by `AirLoop_Name` | Duplicate |
| `AvailabilityManagerAssignmentList` | `Split MSW Availability Manager List` | Duplicate |
| `AvailabilityManager:Scheduled` | `Split MSW Availability Manager` | Duplicate |
| `SetpointManager:SingleZone:Heating` | `SupAirTemp MngrMSW - Htg` | Duplicate |
| `SetpointManager:SingleZone:Cooling` | `SupAirTemp MngrMSW - Clg` | Duplicate |
| `SetpointManager:MixedAir` | `Split MSW_OAMixed Air Temp Manager` | Duplicate |
| `Controller:OutdoorAir` | `Split MSW_OA_Controller` | Duplicate |
| `OutdoorAir:Mixer` | `Split MSW_OAMixer` | Duplicate |
| `OutdoorAir:NodeList` | `Split MSW_OANode List` | Duplicate |

---

## Implementation Details

### Zone Naming Convention

```
Original: M SW Apartment (multiplier=2)

Expanded: 
  M2 SW Apartment (first expanded floor)
  M3 SW Apartment (second expanded floor)

Abbreviated:
  MSW → M2SW, M3SW (for AirLoopHVAC objects)
```

### Floor Height Calculation

Using standard ASHRAE prototype value:
```python
FLOOR_HEIGHT = 3.048  # meters (10 feet)
```

### Key Implementation Methods

#### `_duplicate_zone_objects()` - Zone-Level Loads
Handles objects with direct zone name fields:
```python
zone_objects = [
    ('PEOPLE', 'Zone_or_ZoneList_or_Space_or_SpaceList_Name'),
    ('LIGHTS', 'Zone_or_ZoneList_or_Space_or_SpaceList_Name'),
    ('ELECTRICEQUIPMENT', 'Zone_or_ZoneList_or_Space_or_SpaceList_Name'),
    ('ZONEVENTILATION:WINDANDSTACKOPENAREA', 'Zone_or_Space_Name'),
    ('INTERNALMASS', 'Zone_or_ZoneList_Name'),
    ('SIZING:ZONE', 'Zone_or_ZoneList_Name'),
    ('ZONECONTROL:THERMOSTAT', 'Zone_or_ZoneList_Name'),
    ('WATERHEATER:MIXED', 'Ambient_Temperature_Zone_Name'),
    # ... etc
]
```

#### `_duplicate_hvac_equipment()` - Zone HVAC Equipment
Handles EquipmentConnections, EquipmentList, and NodeList with consistent naming:
```python
# Example: M SW Apartment → M2 SW Apartment
new_obj.Zone_Name = new_zone
new_obj.Zone_Air_Node_Name = f"{new_zone} Air Node"  # NOT suffix pattern
new_obj.Zone_Conditioning_Equipment_List_Name = f"{new_zone} Equipment"
```

#### HVAC Pattern-Based Duplication
Handles complex HVAC objects with both full and abbreviated zone names:
```python
# Create abbreviated zone code (M SW Apartment -> MSW)
zone_parts = old_zone.split()
old_zone_abbrev = zone_parts[0] + zone_parts[1]  # e.g., "MSW"
new_zone_abbrev = new_zone_parts[0] + new_zone_parts[1]  # e.g., "M2SW"

# Check both patterns and replace both
if old_zone in obj_field or old_zone_abbrev in obj_field:
    new_val = obj_field.replace(old_zone, new_zone)
    new_val = new_val.replace(old_zone_abbrev, new_zone_abbrev)
```

---

## Output Structure

### Expanded IDF Naming
```
Original: ASHRAE901_ApartmentMidRise_STD2022_Atlanta_3A.idf
Expanded: ASHRAE901_ApartmentMidRise_STD2022_Atlanta_3A_EXPANDED.idf
```

### Zone Naming Convention

| Floor | Original Name | Expanded Name |
|-------|---------------|---------------|
| Ground | G SW Apartment | G SW Apartment (unchanged) |
| Floor 2 | M SW Apartment | M2 SW Apartment |
| Floor 3 | M SW Apartment | M3 SW Apartment |
| Top | T SW Apartment | T SW Apartment (unchanged) |

### Object Count Changes (MidRise Example)

| Category | Before | After |
|----------|--------|-------|
| Zones | 27 | 45 |
| Objects Removed | - | ~400-450 |
| Objects Created | - | ~800-900 |

---

## Integration with optimize_idfs.py

> [!IMPORTANT]
> Expansion happens **automatically** when loading IDF files with multipliers.

### Automatic Expansion Flow

```
User adds new IDF → optimize_idfs.py detects multipliers → Auto-expand → Save expanded version
```

#### Usage
```python
from bem_utils.expand_idf_multipliers import expand_idf_multipliers

expanded_path = expand_idf_multipliers(
    idf_path='/path/to/original.idf',
    idd_path='/path/to/Energy+.idd',
    output_path=None  # Auto-generates _EXPANDED.idf suffix
)
```

---

## Verification Plan

### Automated Tests
1. Zone count verification: `expanded_zones == original_effective_zones`
2. HVAC object count balance: Equipment lists == Equipment connections
3. Simulation runs without FATAL errors

### Manual Verification
1. 3D visualization shows all floors correctly
2. Simulation runs to completion
3. Energy results match within tolerance (accounting for zone multiplier differences)

---

## Known Limitations

> [!CAUTION]
> The following areas may require additional work:

1. **EMS Programs**: EnergyManagementSystem sensors/actuators that reference zones may need manual review
2. **Complex Node Connections**: Some HVAC node connections may need validation
3. **Inter-zone Surfaces**: Floor/ceiling adjacencies between expanded zones require careful handling
4. **Output Variables**: Zone-specific output variables may need configuration

---

## Dependencies

- `eppy` - IDF object manipulation
- `geomeppy` - IDF loading with geometry support
- EnergyPlus IDD file for validation (Energy+.idd from EnergyPlus installation)
