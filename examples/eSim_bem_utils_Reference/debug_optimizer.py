
import os
import sys
# Insert path for eSim_bem_utils
sys.path.insert(0, os.getcwd())

from eSim_bem_utils import idf_optimizer, config
from eppy.modeleditor import IDF

def main():
    print(f"IDD: {config.IDD_FILE}")
    if not IDF.getiddname():
        IDF.setiddname(config.IDD_FILE)
        
    idf_path = r"BEM_Setup\Buildings\Baseline_5A_Toronto_US+SF+CZ5A+gasfurnace+heatedbsmt+IECC_2021.idf"
    if not os.path.exists(idf_path):
        print("File not found.")
        return

    print(f"Loading {idf_path}...")
    idf = IDF(idf_path)
    
    print("Checking for missing objects...")
    
    # Manually run the check logic from idf_optimizer
    MISSING_OBJECTS = idf_optimizer.MISSING_OBJECTS
    
    print(f"Defined Missing Objects keys: {list(MISSING_OBJECTS.keys())}")
    
    for obj_name, obj_config in MISSING_OBJECTS.items():
        print(f"\nChecking {obj_name}...")
        obj_type = obj_config['object_type']
        
        # Check if object exists
        existing_objs = idf.idfobjects.get(obj_type.upper(), [])
        obj_exists = any(o.Name.upper() == obj_name for o in existing_objs)
        print(f"  Object Exists? {obj_exists}")
        
        if obj_exists:
            continue
            
        # Check surfaces
        surfaces = idf.idfobjects.get('BUILDINGSURFACE:DETAILED', [])
        print(f"  Found {len(surfaces)} surfaces.")
        
        needs_obj = False
        matching_surfaces = []
        for s in surfaces:
            # Check attribute existence
            if hasattr(s, 'Outside_Boundary_Condition_Object'):
                val = s.Outside_Boundary_Condition_Object
                if val:
                    print(f"    Surface {s.Name} OCBO: '{val}'")
                     
                if val and val.upper().strip() == obj_name:
                    needs_obj = True
                    matching_surfaces.append(s.Name)
            
        print(f"  Needs Object? {needs_obj}")
        if matching_surfaces:
             print(f"  Matches: {len(matching_surfaces)} surfaces (e.g. {matching_surfaces[:2]})")

if __name__ == "__main__":
    main()
