# Hotel Small SHW Investigation

## Issue Reported
The user reported that in the `ASHRAE901_HotelSmall_STD2022_Denver.idf` output (`ASHRAE901_HotelSmall_STD2022_Denver_metadata.html`), certain zones like `GuestRoom101` show an **SHW Rate of `0`** while still showing a **Target Temperature of `60 [C]`**.

## Investigation Findings
The reported behavior is not a bug in the code, but an explicit modeling artifact in the ASHRAE prototype IDE file for Denver:

1. **IDF Object Definition**:
   In `ASHRAE901_HotelSmall_STD2022_Denver.idf`, `GuestRoom101` is assigned the `WATERUSE:EQUIPMENT` object named `101_SWH`.
   However, its flow rate fraction schedule is hardcoded to `AlwaysOff`.
   
   ```idf
     WaterUse:Equipment,
       101_SWH,                 !- Name
       WaterUse,             !- End-Use Subcategory
       2.337e-06,   !- Peak Flow Rate {m3/s}
       AlwaysOff,               !- Flow Rate Fraction Schedule Name
       SHW Shower Temp Sched,   !- Target Temperature Schedule Name
       ...
       GuestRoom101,            !- Zone Name
   ```

2. **Why SHW is `0`**:
   The `AlwaysOff` schedule forces the flow fraction to zero for every hour of the year. The extractor code correctly averages this schedule to `0.0`. Since `Peak Flow * 0 = 0`, the total SHW demand output for the room becomes `0 L/h.m2`.

3. **Why Target Temperature is `60`**:
   Despite turning the flow "off", the IDF still statically assigns `SHW Shower Temp Sched` as the target temperature. The extractor parses this schedule and pulls the exact `60 [C]` value. The code correctly extracts what the IDF describes: a device set to 60C that never gets turned on.

4. **Other Guest Rooms**:
   Other Guest Rooms, such as `GuestRoom103`, `GuestRoom104`, and `GuestRoom105` use the schedule `GuestRoom_SHW_Sch` instead of `AlwaysOff`, which yields non-zero flow rates. This implies ASHRAE is clustering hot water usage onto specific guest room blocks to implement diversity factors or simplify the thermal solver load.

## Conclusion
The extractor accurately reflects the data present in the IDF. The IDF explicitly shuts off the water flow for `GuestRoom101` using the `AlwaysOff` schedule.

No fixes are needed in the parser or extraction pipeline. If you would like all Guest Rooms to report hot water loads uniformly, you would need to edit the source `ASHRAE901_HotelSmall_STD2022_Denver.idf` file to replace `AlwaysOff` with `GuestRoom_SHW_Sch` in the corresponding `WATERUSE:EQUIPMENT` definitions.
