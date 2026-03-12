import os
import shutil
import subprocess
import re

# Configuration
ENERGYPLUS_ROOT = r"C:\EnergyPlusV24-2-0"
IDF_VERSION_UPDATER_DIR = os.path.join(ENERGYPLUS_ROOT, "PreProcess", "IDFVersionUpdater")
TARGET_VERSION = "24.2"

# Map of version transitions
# Key: Current Version, Value: (Next Version, Transition Executable Name)
TRANSITION_CHAIN = {
    "22.1": ("22.2", "Transition-V22-1-0-to-V22-2-0.exe"),
    "22.2": ("23.1", "Transition-V22-2-0-to-V23-1-0.exe"),
    "23.1": ("23.2", "Transition-V23-1-0-to-V23-2-0.exe"),
    "23.2": ("24.1", "Transition-V23-2-0-to-V24-1-0.exe"),
    "24.1": ("24.2", "Transition-V24-1-0-to-V24-2-0.exe"),
}

def get_idf_version(file_path):
    """Reads the IDF file to find the Version object."""
    with open(file_path, 'r', errors='ignore') as f:
        content = f.read()
        
    # Look for Version,X.Y; or Version, X.Y;
    match = re.search(r"Version,\s*(\d+\.\d+);", content, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

def copy_idd_files(target_dir):
    """Copies all IDD files from the updater directory to the target directory."""
    print(f"Copying IDD files to {target_dir}...")
    for file in os.listdir(IDF_VERSION_UPDATER_DIR):
        if file.endswith(".idd") or file.endswith(".dll"): # Copy DLLs too just in case
            src = os.path.join(IDF_VERSION_UPDATER_DIR, file)
            dst = os.path.join(target_dir, file)
            if not os.path.exists(dst):
                 shutil.copy2(src, dst)

def cleanup_idd_files(target_dir):
    """Removes IDD and DLL files copied to the target directory."""
    print(f"Cleaning up IDD files from {target_dir}...")
    # Get list of files in updater dir to know what to remove
    updater_files = set(os.listdir(IDF_VERSION_UPDATER_DIR))
    
    for file in os.listdir(target_dir):
        if file in updater_files:
             try:
                os.remove(os.path.join(target_dir, file))
             except OSError as e:
                print(f"Error deleting {file}: {e}")

def update_idf(file_path):
    """Updates the IDF file to the target version."""
    current_version = get_idf_version(file_path)
    if not current_version:
        print(f"Could not determine version for {file_path}. Skipping.")
        return

    print(f"Checking {file_path} (Version: {current_version})")

    if current_version == TARGET_VERSION:
        print(f"  Already at target version {TARGET_VERSION}.")
        return

    file_dir = os.path.dirname(file_path)
    file_name = os.path.basename(file_path)
    
    # Backup the original file
    backup_path = file_path + ".orig"
    if not os.path.exists(backup_path):
        shutil.copy2(file_path, backup_path)
        print(f"  Created backup: {backup_path}")

    # Ensure IDD files are present
    copy_idd_files(file_dir)

    try:
        while current_version != TARGET_VERSION:
            if current_version not in TRANSITION_CHAIN:
                print(f"  No transition found for version {current_version}. Stopping update.")
                break

            next_version, exe_name = TRANSITION_CHAIN[current_version]
            exe_path = os.path.join(IDF_VERSION_UPDATER_DIR, exe_name)
            
            print(f"  Updating from {current_version} to {next_version}...")
            
            # The transition tool expects the file to be in the current working directory or fully qualified?
            # Based on previous manual run, we ran it from the updater dir but passed full path.
            # However, it failed to find IDD if not in CWD.
            # So we copied IDD to the file's dir. Let's run from the file's dir.
            
            cmd = [exe_path, file_name]
            
            result = subprocess.run(cmd, cwd=file_dir, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"  Update failed!")
                print(result.stdout)
                print(result.stderr)
                break
            
            # Verify version update
            current_version = get_idf_version(file_path)
            if current_version != next_version:
                 # Sometimes it updates but the file content version string format might be slightly different?
                 # Or maybe it failed silently.
                 print(f"  Warning: Version check after update shows {current_version}, expected {next_version}.")
                 # If it didn't update, we might be stuck in a loop.
                 if current_version != next_version:
                     print("  Aborting update chain.")
                     break
            
            print(f"  Successfully updated to {current_version}")

    finally:
        cleanup_idd_files(file_dir)

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # bem_ubemSetup
    print(f"Scanning for IDF files in {root_dir}...")
    
    idf_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.endswith(".idf"):
                idf_files.append(os.path.join(dirpath, f))
    
    print(f"Found {len(idf_files)} IDF files.")
    
    for idf_file in idf_files:
        update_idf(idf_file)

if __name__ == "__main__":
    main()
