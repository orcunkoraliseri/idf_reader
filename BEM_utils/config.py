"""
config.py — Platform-aware EnergyPlus path configuration.

Provides lookup for multiple EnergyPlus versions and dynamic path resolution.
"""
import os
import platform

SYSTEM_PLATFORM = platform.system()

# Known EnergyPlus installation directories per platform
# This mapping allows the code to pick the correct version based on IDF file content.
if SYSTEM_PLATFORM == 'Darwin':       # macOS
    ENERGYPLUS_INSTALLS = {
        "22.1": "/Applications/EnergyPlus-22-1-0",
        "24.2": "/Applications/EnergyPlus-24-2-0",
    }
    DEFAULT_VERSION = "24.2"
elif SYSTEM_PLATFORM == 'Windows':
    ENERGYPLUS_INSTALLS = {
        "22.1": r"C:\EnergyPlusV22-1-0",
        "24.2": r"C:\EnergyPlusV24-2-0",
    }
    DEFAULT_VERSION = "24.2"
else:                                  # Linux
    ENERGYPLUS_INSTALLS = {
        "22.1": "/usr/local/EnergyPlus-22-1-0",
        "24.2": "/usr/local/EnergyPlus-24-2-0",
    }
    DEFAULT_VERSION = "24.2"


def get_ep_paths(version: str = None) -> dict:
    """
    Returns the executable and IDD paths for a specific EnergyPlus version.

    Args:
        version: Version string (e.g., "22.1"). If None or missing, uses DEFAULT_VERSION.

    Returns:
        dict: {'exe': str, 'idd': str, 'dir': str}
    """
    # Clean version string (e.g. "22.1.0" -> "22.1")
    if version:
        parts = version.split('.')
        if len(parts) >= 2:
            version = f"{parts[0]}.{parts[1]}"

    ep_dir = ENERGYPLUS_INSTALLS.get(version, ENERGYPLUS_INSTALLS.get(DEFAULT_VERSION))
    
    _exe_ext = '.exe' if SYSTEM_PLATFORM == 'Windows' else ''
    return {
        'exe': os.path.join(ep_dir, f'energyplus{_exe_ext}'),
        'idd': os.path.join(ep_dir, 'Energy+.idd'),
        'dir': ep_dir
    }


# For backward compatibility (global defaults)
_default_paths = get_ep_paths(DEFAULT_VERSION)
ENERGYPLUS_DIR = _default_paths['dir']
ENERGYPLUS_EXE = _default_paths['exe']
IDD_FILE       = _default_paths['idd']


def setup_environment(version: str = None):
    """Sets environment variables required for Eppy and EnergyPlus tools."""
    paths = get_ep_paths(version)
    os.environ['IDD_FILE'] = paths['idd']


# Auto-configure on import
setup_environment()
