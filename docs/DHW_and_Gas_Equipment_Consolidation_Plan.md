# Consolidate Gas and DHW Equipment

## 1. Consolidate Gas Equipment

### Analysis of Gas Equipment (4.518 W/m²)
In the IDF file, there are three distinct `GasEquipment` objects assigned to the `living_unit1` zone:
1. **gas_dryer1**: 395.6 W
2. **gas_range1**: 540.9 W
3. **gas_mels1**: 61.1 W

**Total Gas Load** = 395.6 + 540.9 + 61.1 = **997.6 Watts**
Distributed across the 2-story thermal zone floor area of **220.8 m²**:
**Density** = 997.6 W / 220.8 m² = **4.518 W/m²**.

### Modeling Strategy
You can consolidate these three objects into a single `GasEquipment` object using the density of **4.518 W/m²**.

### Which Schedule to Use?
The `gas_range1` accounts for over 54% of the load. If you want to use an existing schedule without creating a new one, the best choice is:
**`D_SFm_Living_Cook_Yr`**

---

## 2. Consolidate DHW Schedules

### Analysis of DHW Equipment
The Domestic Hot Water (DHW) loads are split into five `WaterUse:Equipment` objects. Based on daily volume in the IDF:
1. **Shower (`Showers_unit1`)**: 23.9 gallons / day
2. **Sink (`Sinks_unit1`)**: 21.1 gallons / day
3. **Bath (`Baths_unit1`)**: 6.0 gallons / day

### Which Schedule to Use?
Since the **Shower** consumes the most hot water daily and typically dictates the highest spikes in residential demand, the best schedule to use is:
**`D_SFm_All_DHW_Shwr_Yr`**

---

## 3. Implementation Note
No Python code changes to the parsing scripts are required. The current `extractors.py` already aggregates all loads within a zone to provide the total `L/h·m²` (for water) and `W/m²` (for gas) densities accurately.

**Honeybee/EnergyPlus Modeling Recommendation:**
- **Gas**: Create 1 object @ **4.518 W/m²** with **`D_SFm_Living_Cook_Yr`**.
- **DHW**: Create 1 object with total flow rate with **`D_SFm_All_DHW_Shwr_Yr`**.
