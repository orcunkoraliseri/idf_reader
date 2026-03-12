import os
import platform
import sys

# Platform Detection
SYSTEM_PLATFORM = platform.system()

# EnergyPlus Paths
if SYSTEM_PLATFORM == 'Darwin':  # macOS
    DEFAULT_ENERGYPLUS_DIR = '/Applications/EnergyPlus-24-2-0'
elif SYSTEM_PLATFORM == 'Windows':
    DEFAULT_ENERGYPLUS_DIR = r'C:\EnergyPlusV24-2-0'
else:
    DEFAULT_ENERGYPLUS_DIR = '/usr/local/EnergyPlus-24-2-0'

# Allow Override via Environment Variable
ENERGYPLUS_DIR = os.environ.get('ENERGYPLUS_DIR', DEFAULT_ENERGYPLUS_DIR)

# Executable
_exe_ext = '.exe' if SYSTEM_PLATFORM == 'Windows' else ''
ENERGYPLUS_EXE = os.path.join(ENERGYPLUS_DIR, f'energyplus{_exe_ext}')

# IDD File
IDD_FILE = os.path.join(ENERGYPLUS_DIR, 'Energy+.idd')

# Global Environment Setup
def setup_environment():
    """Sets environment variables required for Eppy and other tools."""
    if 'IDD_FILE' not in os.environ:
        os.environ["IDD_FILE"] = IDD_FILE

# Auto-configure on import
setup_environment()
