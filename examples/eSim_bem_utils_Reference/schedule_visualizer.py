
import os
import matplotlib.pyplot as plt
from eSim_bem_utils import schedule_generator

# Default schedules constants (optional usage, but good for reference lines)
DEFAULT_LIGHT = [
    0.1, 0.1, 0.1, 0.1, 0.1, 0.2, 0.4, 0.5, 0.3, 0.2,
    0.2, 0.2, 0.2, 0.2, 0.2, 0.3, 0.5, 0.7, 0.9, 0.9,
    0.8, 0.6, 0.4, 0.2
]
DEFAULT_EQUIP = [
    0.3, 0.2, 0.2, 0.2, 0.2, 0.3, 0.5, 0.6, 0.5, 0.4,
    0.4, 0.4, 0.5, 0.4, 0.4, 0.4, 0.5, 0.6, 0.7, 0.7,
    0.6, 0.5, 0.4, 0.3
]
DEFAULT_WATER = [
    0.05, 0.05, 0.05, 0.05, 0.1, 0.3, 0.5, 0.4, 0.2, 0.1,
    0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.2, 0.4, 0.5, 0.4,
    0.3, 0.2, 0.1, 0.05
]

class ScheduleVisualizer:
    def __init__(self, epw_path: str = None):
        """
        Initialize the visualizer.
        args:
            epw_path: Path to EPW file (used for Solar Radiation overlay).
        """
        self.solar_profile = None
        if epw_path and os.path.exists(epw_path):
            try:
                lg = schedule_generator.LightingGenerator(epw_path=epw_path)
                self.solar_profile = lg._get_annual_average_solar()
            except Exception as e:
                print(f"Warning: Could not load EPW for visualization: {e}")

    def visualize_schedule_integration(
        self,
        presence_schedule: list[float],
        proj_light: list[float],
        proj_equip: list[float],
        proj_water: list[float],
        output_path: str,
        title: str,
        active_load_equip: float = None,
        base_load_equip: float = None,
        active_load_water: float = None,
        base_load_water: float = None,
        default_light: list[float] = None,
        default_equip: list[float] = None,
        default_water: list[float] = None,
        default_presence: list[float] = None
    ) -> None:
        """
        Generates a 4-panel comparison plot of the integrated schedules.
        """
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Use provided defaults or fallback to module constants
        def_light = default_light or DEFAULT_LIGHT
        def_equip = default_equip or DEFAULT_EQUIP
        def_water = default_water or DEFAULT_WATER

        hours = range(24)
        fig, axes = plt.subplots(4, 1, figsize=(12, 14), sharex=True)
        fig.suptitle(title, fontsize=14, fontweight='bold')

        # Color scheme
        COLOR_PRESENCE = '#4CAF50'
        COLOR_DEFAULT = '#FF5722'
        COLOR_PROJECTED = '#2196F3'
        COLOR_SOLAR = '#FFC107'

        # Panel 1: Presence
        ax = axes[0]
        ax.bar(hours, presence_schedule, color=COLOR_PRESENCE, alpha=0.7, label='Presence (Assigned)')
        if default_presence:
            ax.step(hours, default_presence, where='mid', color=COLOR_DEFAULT, linestyle='--', label='Default', alpha=0.9, linewidth=2)
        
        ax.set_title("1. Presence Schedule", fontsize=12, fontweight='bold')
        ax.set_ylabel("Occupancy")
        ax.set_ylim(0, 1.2)
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)

        # Panel 2: Lighting
        ax = axes[1]
        if self.solar_profile:
            ax2 = ax.twinx()
            ax2.fill_between(hours, 0, self.solar_profile, color=COLOR_SOLAR, alpha=0.2, label='Solar')
            ax2.axhline(150, color=COLOR_SOLAR, linestyle=':', linewidth=2)
            ax2.set_ylabel("Solar (Wh/m²)", color=COLOR_SOLAR)
            ax2.tick_params(axis='y', labelcolor=COLOR_SOLAR)
            ax2.set_ylim(0, max(self.solar_profile)*1.2 if max(self.solar_profile) > 0 else 300)
        
        ax.step(hours, def_light, where='mid', color=COLOR_DEFAULT, linestyle='--', label='Default', alpha=0.7)
        ax.step(hours, proj_light, where='mid', color=COLOR_PROJECTED, linewidth=2, label='Projected')
        ax.set_title("2. Lighting (Daylight Gatekeeper)", fontsize=12, fontweight='bold')
        ax.set_ylabel("Fraction")
        ax.set_ylim(0, 1.2)
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)

        # Panel 3: Equipment
        ax = axes[2]
        ax.step(hours, def_equip, where='mid', color=COLOR_DEFAULT, linestyle='--', label='Default', alpha=0.7)
        ax.step(hours, proj_equip, where='mid', color=COLOR_PROJECTED, linewidth=2, label='Projected')
        if active_load_equip is not None:
             ax.axhline(active_load_equip, color='green', linestyle=':', alpha=0.5)
        if base_load_equip is not None:
             ax.axhline(base_load_equip, color='gray', linestyle=':', alpha=0.5)
        
        # Add Green Shading for Presence
        ax.fill_between(hours, 0, 1, where=[p > 0 for p in presence_schedule],
                        color=COLOR_PRESENCE, alpha=0.1)
                        
        ax.set_title("3. Equipment (Presence Filter)", fontsize=12, fontweight='bold')
        ax.set_ylabel("Fraction")
        ax.set_ylim(0, 1.2)
        ax.grid(True, alpha=0.3)

        # Panel 4: DHW
        ax = axes[3]
        ax.step(hours, def_water, where='mid', color=COLOR_DEFAULT, linestyle='--', label='Default', alpha=0.7)
        ax.step(hours, proj_water, where='mid', color=COLOR_PROJECTED, linewidth=2, label='Projected')
        if active_load_water is not None:
             ax.axhline(active_load_water, color='green', linestyle=':', alpha=0.5)
        if base_load_water is not None:
             ax.axhline(base_load_water, color='gray', linestyle=':', alpha=0.5)
             
        # Add Green Shading for Presence
        ax.fill_between(hours, 0, 1, where=[p > 0 for p in presence_schedule],
                        color=COLOR_PRESENCE, alpha=0.1)
                        
        ax.set_title("4. DHW (Presence Filter)", fontsize=12, fontweight='bold')
        ax.set_ylabel("Fraction")
        ax.set_xlabel("Hour")
        ax.set_ylim(0, 1.2)
        ax.grid(True, alpha=0.3)

        plt.xticks(range(0, 24, 2))
        plt.tight_layout()
        plt.savefig(output_path, dpi=100)
        plt.close()
        print(f"    [PLOT] Schedule plot saved: {os.path.basename(output_path)}")
