"""
Reporting module for BEM simulation results.

Handles statistical analysis (ANOVA, Tukey HSD, Cohen's d),
profile extraction, and CSV report generation for Option 4 (K-Fold Comparative).
"""
import os
import csv
import numpy as np
import scipy.stats as stats
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any

# Map internal end-use categories to display names
DISPLAY_CATEGORIES = {
    'heating': 'Heating',
    'cooling': 'Cooling',
    'interiorlights': 'Lighting',
    'interiorequipment': 'Equipment',
    'watersystems': 'DHW'
}

class ReportGenerator:
    """
    Generates detailed CSV reports for K-Fold Comparative Simulations.
    """
    
    def __init__(self, results: Dict[str, List[Dict]], output_dir: str, region: str = "Unknown"):
        """
        Args:
            results: Dictionary mapping Scenario Name -> List of Result Dicts (one per run).
                     Each Result Dict contains 'eui_data' and 'meter_data'.
            output_dir: Directory to save the report.
            region: Region name for filename.
        """
        self.results = results
        self.output_dir = output_dir
        self.region = region
        self.scenarios = list(results.keys())
        
        # Flattened EUI data for easy access: {category: {scenario: [values...]}}
        self.eui_by_cat = defaultdict(lambda: defaultdict(list))
        self._organize_eui_data()

    def _organize_eui_data(self):
        """Organizes raw EUI data by category and scenario."""
        for scenario, run_list in self.results.items():
            for run in run_list:
                eui_data = run.get('eui_data', {})
                end_uses = eui_data.get('end_uses_normalized', {})
                
                # Normalize keys to match DISPLAY_CATEGORIES
                for cat, val in end_uses.items():
                    # clean key: 'Heating:EnergyTransfer' -> 'heating'
                    clean_key = cat.split(':')[0].lower()
                    
                    # Map common keys
                    if 'heating' in clean_key: key = 'heating'
                    elif 'cooling' in clean_key: key = 'cooling'
                    elif 'lights' in clean_key: key = 'interiorlights'
                    elif 'equipment' in clean_key: key = 'interiorequipment'
                    elif 'water' in clean_key: key = 'watersystems'
                    else: continue # Skip others for now or add if needed
                    
                    self.eui_by_cat[key][scenario].append(val)

    def generate_report(self) -> str:
        """
        Generates the full CSV report.

        Returns:
            Path to the generated CSV file.
        """
        filename = f"{self.region}_Comparative_Analysis_Report.csv"
        filepath = os.path.join(self.output_dir, filename)

        # Get simulation details
        sim_id = os.path.basename(self.output_dir)
        total_runs = sum(len(runs) for runs in self.results.values())

        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header Section
            writer.writerow([f"SIMULATION RESULTS SUMMARY - {self.region.upper()}"])
            writer.writerow([f"Simulation ID: {sim_id}"])
            writer.writerow([f"Total Simulations: {total_runs}"])
            writer.writerow([f"Scenarios: {', '.join(self.scenarios)}"])
            writer.writerow([])

            # 1. Annual Energy Demand Metrics
            self._write_annual_metrics(writer)

            # 2. Statistical Variability
            self._write_statistical_analysis(writer)

            # 3. Raw Simulation Data
            self._write_raw_data(writer)

            # 4. Hourly Load Profiles
            self._write_hourly_profiles(writer)

            # 5. Peak Load Characteristics
            self._write_peak_loads(writer)

            # 6. Summary of Key Findings
            self._write_summary(writer)

        print(f"\n{'='*80}")
        print(f"COMPREHENSIVE REPORT GENERATED")
        print(f"{'='*80}")
        print(f"Location: {self.region}")
        print(f"File: {filepath}")
        print(f"Total Simulations: {total_runs}")
        print(f"Scenarios: {', '.join(self.scenarios)}")
        print(f"{'='*80}")
        return filepath

    def _write_annual_metrics(self, writer):
        """Writes Annual Energy Demand Metrics section."""
        writer.writerow(["="*80])
        writer.writerow(["[SECTION] Annual Energy Demand Metrics (Aggregated)"])
        writer.writerow(["="*80])
        writer.writerow(["Category", "Scenario", "Mean(kWh/m2)", "StdDev", "CI_Lower", "CI_Upper"])

        for cat_key, cat_name in DISPLAY_CATEGORIES.items():
            if cat_key not in self.eui_by_cat: continue

            for scenario in self.scenarios:
                values = self.eui_by_cat[cat_key][scenario]
                if not values:
                    writer.writerow([cat_name, scenario, "N/A", "N/A", "N/A", "N/A"])
                    continue

                mean = np.mean(values)
                std = np.std(values, ddof=1) if len(values) > 1 else 0.0

                # 95% Confidence Interval
                if len(values) > 1 and std > 0:
                    # Only calculate CI if we have variance
                    se = std / np.sqrt(len(values))
                    with np.errstate(invalid='ignore'):  # Suppress warnings for edge cases
                        ci = stats.t.interval(0.95, len(values)-1, loc=mean, scale=se)
                    # Check for invalid results
                    if np.isnan(ci[0]) or np.isnan(ci[1]) or np.isinf(ci[0]) or np.isinf(ci[1]):
                        ci = (mean, mean)
                elif len(values) == 1 or std == 0:
                    # Zero variance: CI equals the mean
                    ci = (mean, mean)
                else:
                    ci = (mean, mean)

                writer.writerow([
                    cat_name, scenario,
                    f"{mean:.4f}", f"{std:.4f}",
                    f"{ci[0]:.4f}", f"{ci[1]:.4f}"
                ])
        writer.writerow([]) # Spacer

    def _write_statistical_analysis(self, writer):
        """Writes Statistical Variability section (ANOVA, Tukey, Cohen's d)."""
        writer.writerow(["="*80])
        writer.writerow(["[SECTION] Statistical Variability (Reference: Default)"])
        writer.writerow(["="*80])
        writer.writerow(["Category", "Comparison", "P-Value", "Significant?", "Cohens_D"])
        
        ref_scenario = 'Default'
        if ref_scenario not in self.scenarios:
            writer.writerow(["Note:", "Default scenario not found for comparison"])
            writer.writerow([])
            return

        for cat_key, cat_name in DISPLAY_CATEGORIES.items():
            if cat_key not in self.eui_by_cat: continue
            
            # ANOVA
            all_groups = [self.eui_by_cat[cat_key][s] for s in self.scenarios if self.eui_by_cat[cat_key][s]]
            if len(all_groups) < 2: continue
            
            try:
                f_stat, p_val_anova = stats.f_oneway(*all_groups)
            except Exception:
                continue

            # If ANOVA is significant, proceed to post-hoc
            # We compare everything against 'Default'
            ref_values = self.eui_by_cat[cat_key].get(ref_scenario, [])
            if not ref_values: continue
            
            for scenario in self.scenarios:
                if scenario == ref_scenario: continue

                scen_values = self.eui_by_cat[cat_key].get(scenario, [])
                if not scen_values: continue

                # Check for zero variance in either group (e.g., Default scenario)
                scen_std = np.std(scen_values, ddof=1) if len(scen_values) > 1 else 0.0
                ref_std = np.std(ref_values, ddof=1) if len(ref_values) > 1 else 0.0

                # Skip statistical test if either group has zero variance
                if scen_std == 0 or ref_std == 0:
                    # Can't perform meaningful statistical test on constant values
                    p_val = 1.0  # No difference if both are constant
                    cohens_d = 0.0
                    sig = "No"
                else:
                    # Tukey HSD (Pairwise)
                    try:
                        with np.errstate(divide='ignore', invalid='ignore'):
                            res = stats.tukey_hsd(scen_values, ref_values)
                            p_val = res.pvalue[0, 1]  # p-value comparing group 0 and 1

                        # Check for invalid p-value
                        if np.isnan(p_val) or np.isinf(p_val):
                            p_val = 1.0
                    except Exception:
                        p_val = 1.0

                    sig = "Yes" if p_val < 0.05 else "No"

                    # Cohen's d
                    n1, n2 = len(scen_values), len(ref_values)
                    var1, var2 = np.var(scen_values, ddof=1), np.var(ref_values, ddof=1)

                    with np.errstate(divide='ignore', invalid='ignore'):
                        pooled_std = np.sqrt(((n1-1)*var1 + (n2-1)*var2) / (n1+n2-2))
                        cohens_d = (np.mean(scen_values) - np.mean(ref_values)) / pooled_std if pooled_std > 0 else 0.0

                    # Check for invalid Cohen's d
                    if np.isnan(cohens_d) or np.isinf(cohens_d):
                        cohens_d = 0.0

                writer.writerow([
                    cat_name, f"{scenario} vs {ref_scenario}",
                    f"{p_val:.5f}", sig, f"{cohens_d:.4f}"
                ])
        writer.writerow([])

    def _write_raw_data(self, writer):
        """Writes Raw Simulation Data section."""
        writer.writerow(["="*80])
        writer.writerow(["[SECTION] Raw Simulation Data (Per Simulation)"])
        writer.writerow(["="*80])
        header = ["Run_ID", "Scenario"] + list(DISPLAY_CATEGORIES.values())
        writer.writerow(header)

        # Re-iterate to align rows by Run ID if possible, or just list them
        # We assume lists are ordered by run k
        max_runs = max(len(v) for s in self.results.values() for v in s) if self.results else 0

        run_idx = 1
        # Loop scenarios, then runs
        for scenario in self.scenarios:
            runs = self.results[scenario]
            for i, run in enumerate(runs):
                row = [i+1, scenario]
                eui_data = run.get('eui_data', {}).get('end_uses_normalized', {})

                # Use the same matching logic as _organize_eui_data
                for cat_key in DISPLAY_CATEGORIES:
                    val = 0.0
                    for k, v in eui_data.items():
                        clean_key = k.split(':')[0].lower()

                        # Match using same logic as _organize_eui_data
                        matched = False
                        if 'heating' in clean_key and cat_key == 'heating':
                            matched = True
                        elif 'cooling' in clean_key and cat_key == 'cooling':
                            matched = True
                        elif 'lights' in clean_key and cat_key == 'interiorlights':
                            matched = True
                        elif 'equipment' in clean_key and cat_key == 'interiorequipment':
                            matched = True
                        elif 'water' in clean_key and cat_key == 'watersystems':
                            matched = True

                        if matched:
                            val = v
                            break
                    row.append(f"{val:.4f}")
                writer.writerow(row)
        writer.writerow([])

    def _write_hourly_profiles(self, writer):
        """Writes Hourly Load Profiles section."""
        writer.writerow(["="*80])
        writer.writerow(["[SECTION] Hourly Load Profiles (kW)"])
        writer.writerow(["="*80])
        # Columns: Season, DayType, Hour, Scen1_Mean, Scen2_Mean...
        header = ["Season", "DayType", "Hour"] + [f"{s}_Mean" for s in self.scenarios]
        writer.writerow(header)

        # Define profile windows (Day of Year 1-365)
        # Jan: 1-31
        # Jul: 182-212 (approx)
        jan_days = range(1, 32)
        jul_days = range(182, 213)
        
        # EnergyPlus Default: Jan 1 is Sunday (if not specified)
        # 0=Sunday, 1=Monday... 6=Saturday
        def is_weekend(doy): # 1-based doy
            # If Jan 1 is Sunday (0):
            # (doy - 1) % 7 == 0 (Sun) or 6 (Sat) ?
            # Jan 1: (1-1)%7 = 0 -> Sun
            # Jan 2: (2-1)%7 = 1 -> Mon
            # ...
            # Jan 7: (7-1)%7 = 6 -> Sat
            wd = (doy - 1) % 7
            return wd == 0 or wd == 6

        seasons = {
            'Winter': {'days': jan_days},
            'Summer': {'days': jul_days}
        }
        
        day_types = ['Weekday', 'Weekend']
        
        # We need to aggregate hourly data for each scenario
        # hourly_data structure: {'meter_name': [8760 values]} in each run
        # We want Total Energy (Heating+Cooling+...) or just Heating/Cooling load?
        # Request says: "Representative Daily Profiles: 24-hour profiles of heating and cooling loads"
        # So we produce separate rows for Heating and Cooling?
        # The CSV structure implied one table. "Season, DayType, Hour, Scen1_Mean..."
        # But for WHICH metric?
        # "24-hour profiles of heating and cooling loads" implies we need distinct profiles.
        # I will add a "Category" column to appropriate the structure.
        
        writer.writerow(["Note: Profiles are for Total Heating + Cooling Load (kW)"])
        # Actually, let's output separate blocks or add a Category column.
        # The user's example: 
        # "Season,DayType,Hour,2025_Mean,..."
        # This implies mixed or single metric.
        # I'll add "Category" column.
        
        refined_header = ["Category", "Season", "DayType", "Hour"] + [f"{s}_Mean" for s in self.scenarios]
        writer.writerow(refined_header)

        target_meters = {
            'Heating': ['Heating:EnergyTransfer'],
            'Cooling': ['Cooling:EnergyTransfer']
        }

        for cat_name, meter_keys in target_meters.items():
            for season_name, season_info in seasons.items():
                days = list(season_info['days'])
                
                for dtype in day_types:
                    # Filter days
                    if dtype == 'Weekend':
                        selected_days = [d for d in days if is_weekend(d)]
                    else:
                        selected_days = [d for d in days if not is_weekend(d)]
                    
                    if not selected_days: continue

                    # Initialize sums [24 hours] for each scenario
                    scen_hourly_means = {s: np.zeros(24) for s in self.scenarios}
                    
                    for scenario in self.scenarios:
                        runs = self.results[scenario]
                        if not runs: continue
                        
                        # Collect all profiles for this scenario/season/dtype
                        all_profiles = []
                        
                        for run in runs:
                            h_data = run.get('hourly_data', {})
                            if not h_data: continue
                            
                            # Sum relevant meters (e.g. heating)
                            # Data is 8760 list
                            combined_ts = np.zeros(8760)
                            found_any = False
                            for mk in meter_keys:
                                if mk in h_data:
                                    combined_ts += np.array(h_data[mk])
                                    found_any = True
                            
                            if not found_any: continue
                            
                            # Extract days and average to 24h
                            # J to kW? 
                            # E+ Hourly EnergyTransfer is in Joules (J). 
                            # Power (kW) = J / 3600 / 1000
                            combined_kw = combined_ts / 3600000.0
                            
                            daily_profiles = []
                            for d in selected_days:
                                start_h = (d - 1) * 24
                                end_h = start_h + 24
                                if end_h <= 8760:
                                    daily_profiles.append(combined_kw[start_h:end_h])
                            
                            if daily_profiles:
                                # Average this run's relevant days -> 1 day profile
                                avg_run_profile = np.mean(daily_profiles, axis=0)
                                all_profiles.append(avg_run_profile)
                        
                        if all_profiles:
                            # Average across all runs
                            scen_hourly_means[scenario] = np.mean(all_profiles, axis=0)
                    
                    # Write rows for 0..23 hours
                    for h in range(24):
                        row = [cat_name, season_name, dtype, h]
                        for s in self.scenarios:
                            val = scen_hourly_means[s][h]
                            row.append(f"{val:.4f}")
                        writer.writerow(row)
        writer.writerow([])

    def _write_peak_loads(self, writer):
        """Writes Peak Load Characteristics section."""
        writer.writerow(["="*80])
        writer.writerow(["[SECTION] Peak Load Characteristics"])
        writer.writerow(["="*80])
        writer.writerow(["Category", "Scenario", "Peak_Load(W/m2)", "Peak_Time"])
        
        target_meters = {
            'Heating': ['Heating:EnergyTransfer'],
            'Cooling': ['Cooling:EnergyTransfer']
        }
        
        # Note: W/m2 requires floor area. 
        # We need to extract floor area from EUI data (first run).
        
        for cat_name, meter_keys in target_meters.items():
            for scenario in self.scenarios:
                runs = self.results[scenario]
                if not runs:
                    writer.writerow([cat_name, scenario, "N/A", "N/A"])
                    continue
                
                # We need to find the GLOBAL peak across all runs? 
                # Or average peak? Usually "Peak of the average" or "Average of the peaks".
                # Request: "Peak Heating Load: The maximum ... for each scenario"
                # usually means the Worst Case or the Average Peak.
                # Let's do Average Peak to be robust against outliers, 
                # OR Max Peak to be safe for sizing. 
                # Given "Comparative", Mean Peak is likely better statistically.
                # But let's find the max peak in the set for now to represent "Peak Demand".
                
                peak_vals = []
                peak_times = []
                
                for run in runs:
                    h_data = run.get('hourly_data', {})
                    eui = run.get('eui_data', {})
                    area = eui.get('conditioned_floor_area', 1.0) or 1.0
                    
                    if not h_data: continue
                    
                    combined_ts = np.zeros(8760)
                    for mk in meter_keys:
                        if mk in h_data:
                            combined_ts += np.array(h_data[mk])
                    
                    # J to W: J / 3600 ? No, Hourly Energy J = Avg Power W * 3600 s
                    # So Power W = Energy J / 3600
                    power_w = combined_ts / 3600.0
                    
                    max_w = np.max(power_w)
                    max_idx = np.argmax(power_w)
                    
                    peak_vals.append(max_w / area) # W/m2
                    peak_times.append(max_idx)
                
                if not peak_vals:
                    writer.writerow([cat_name, scenario, "N/A", "N/A"])
                    continue
                
                # Report the Mean of the Peaks
                avg_peak_w_m2 = np.mean(peak_vals)
                
                # Representative time (mode or average?)
                # Time is tricky. Let's take the time of the run with the highest peak
                # or just the most frequent hour.
                # Let's use the time from the max peak run.
                max_peak_idx = np.argmax(peak_vals)
                best_time_idx = peak_times[max_peak_idx]
                
                # Convert hour idx to Date
                # hour 0 = Jan 1 00:00-01:00
                doy = (best_time_idx // 24) + 1
                hour = best_time_idx % 24
                
                # Approximate Month/Day
                # Simplistic map
                months_lens = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
                cum_days = [0] + list(np.cumsum(months_lens))
                
                month = 1
                day = doy
                for i, cd in enumerate(cum_days):
                    if doy > cd:
                        month = i + 1
                        day = doy - cd
                
                time_str = f"{month}/{day} {hour:02d}:00"
                
                writer.writerow([
                    cat_name, scenario,
                    f"{avg_peak_w_m2:.2f}", time_str
                ])
        writer.writerow([])

    def _write_summary(self, writer):
        """Writes Summary of Key Findings section."""
        writer.writerow(["="*80])
        writer.writerow(["[SECTION] Summary of Key Findings"])
        writer.writerow(["="*80])
        writer.writerow([])

        # Calculate key statistics for heating and cooling
        heating_data = self.eui_by_cat.get('heating', {})
        cooling_data = self.eui_by_cat.get('cooling', {})

        if heating_data and 'Default' in heating_data:
            writer.writerow(["1. HEATING PERFORMANCE:"])
            default_heating = np.mean(heating_data['Default'])

            for scenario in ['2025', '2015', '2005']:
                if scenario in heating_data:
                    scen_mean = np.mean(heating_data[scenario])
                    scen_std = np.std(heating_data[scenario], ddof=1) if len(heating_data[scenario]) > 1 else 0.0
                    diff = scen_mean - default_heating
                    pct_change = (diff / default_heating * 100) if default_heating > 0 else 0
                    writer.writerow([f"   - {scenario}: {scen_mean:.2f} kWh/m² (±{scen_std:.2f}), {pct_change:+.1f}% vs Default"])
            writer.writerow([])

        if cooling_data and 'Default' in cooling_data:
            writer.writerow(["2. COOLING PERFORMANCE:"])
            default_cooling = np.mean(cooling_data['Default'])

            for scenario in ['2025', '2015', '2005']:
                if scenario in cooling_data:
                    scen_mean = np.mean(cooling_data[scenario])
                    scen_std = np.std(cooling_data[scenario], ddof=1) if len(cooling_data[scenario]) > 1 else 0.0
                    diff = scen_mean - default_cooling
                    pct_change = (diff / default_cooling * 100) if default_cooling > 0 else 0
                    writer.writerow([f"   - {scenario}: {scen_mean:.2f} kWh/m² (±{scen_std:.2f}), {pct_change:+.1f}% vs Default"])
            writer.writerow([])

        writer.writerow(["3. DATA QUALITY:"])
        for scenario, runs in self.results.items():
            writer.writerow([f"   - {scenario}: {len(runs)} simulation(s) completed"])
        writer.writerow([])

        writer.writerow(["4. STATISTICAL SIGNIFICANCE:"])
        writer.writerow(["   - P-values < 0.05 indicate statistically significant differences"])
        writer.writerow(["   - Cohen's D > 0.8 indicates large practical effect size"])
        writer.writerow(["   - See Statistical Variability section for detailed test results"])
        writer.writerow([])

        writer.writerow(["="*80])
        writer.writerow(["END OF REPORT"])
        writer.writerow(["="*80])
