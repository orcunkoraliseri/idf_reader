"""
reporting.py — Statistical Reporting for Multi-Run / Batch Results (Phase 5).

For a single-simulation workflow, this module is not required.
Use plotting.plot_eui_breakdown() for individual run visualization.

This module is a stub — extend it for comparative / Monte-Carlo analysis.
"""


class ReportGenerator:
    """
    Placeholder for multi-scenario statistical reporting.

    Planned capabilities:
    - Annual Metrics: mean ± std per end-use per scenario
    - Statistical Variability: ANOVA + Tukey HSD + Cohen's d (scipy.stats)
    - Raw Data: per-run EUI values exported to CSV
    - Hourly Load Profiles: winter/summer weekday/weekend 24-hour profiles
    - Peak Loads: max W/m² for Heating and Cooling per scenario
    - Summary of Key Findings: plain-language % change vs. baseline scenario
    """

    def __init__(self, results: list, output_dir: str):
        """
        Args:
            results:    List of EUI result dicts (from plotting.calculate_eui).
            output_dir: Directory to save reports.
        """
        self.results = results
        self.output_dir = output_dir

    def generate(self):
        """Generate all reports. Not yet implemented."""
        raise NotImplementedError(
            "ReportGenerator is a stub. Implement in Phase 5 for multi-scenario analysis."
        )
