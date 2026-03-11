def _resolve_week_schedules(idf_data, day_map):
    week_map = {}
    from equipment_demand_composer import _day_of_year_to_weekday, _dow_matches

    # 1. Schedule:Week:Daily
    for obj in idf_data.get("SCHEDULE:WEEK:DAILY", []):
        if len(obj) < 9: continue
        name = obj[0].strip().lower()
        day_names = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
        day_scheds = {d: obj[i + 1].strip().lower() for i, d in enumerate(day_names)}
        arr = [0.0] * 8760
        for doy in range(1, 366):
            dow = _day_of_year_to_weekday(doy).lower()
            sched_name = day_scheds.get(dow, "")
            day_fracs = day_map.get(sched_name, [0.0] * 24)
            base = (doy - 1) * 24
            for h in range(24):
                if base + h < 8760: arr[base + h] = day_fracs[h]
        week_map[name] = arr

    # 2. Schedule:Week:Compact
    for obj in idf_data.get("SCHEDULE:WEEK:COMPACT", []):
        if len(obj) < 3: continue
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
            # Match in order. In E+, the first matching day type usually wins or it's well-formed.
            # But 'allotherdays' acts as a catch-all.
            for (f_str, s_name) in pairs:
                if _dow_matches(dow, f_str) or "allotherdays" in f_str.lower():
                    sched_name = s_name
                    break
            
            day_fracs = day_map.get(sched_name, [0.0] * 24)
            base = (doy - 1) * 24
            for h in range(24):
                if base + h < 8760: arr[base + h] = day_fracs[h]
        week_map[name] = arr

    return week_map
