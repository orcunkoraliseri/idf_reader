import os
import glob

def find_files(base_dir):
    """
    Scans the Building and WeatherFile directories to find IDF and EPW files.
    Matches them based on climate zone (3A/4A).
    """
    building_dir = os.path.join(base_dir, 'Building')
    weather_dir = os.path.join(base_dir, 'WeatherFile')
    
    simulation_pairs = []
    
    # Climate zones to look for
    zones = ['3A', '4A']
    
    for zone in zones:
        # Find IDFs for this zone
        idf_pattern = os.path.join(building_dir, zone, '*.idf')
        idfs = glob.glob(idf_pattern)
        
        # Find EPW for this zone
        # Assuming there is one EPW file per zone in the WeatherFile folder or subfolders
        # The user said "under the WeatherFile folder there are weather files that are suitable for 4A and 3A"
        # And "we have two set of weather, 4A and 3A"
        # Let's look for files containing the zone name in WeatherFile root or subdirs
        
        # Try specific subfolder first if it exists (based on user description "under the WeatherFile folder there are weather files")
        # But user also said "under the WeatherFile folder there are weather files that are suitable for 4A and 3A simulations"
        # and list_dir showed direct files in WeatherFile (actually list_dir showed 3A and 4A folders? No, wait.)
        
        # Let's re-check list_dir output from Step 8.
        # Step 8 output:
        # {"name":"ITA_LZ_Rome-Fiumicino-da.Vinci.AP.162420_TMYx.2009-2023_3A.epw","sizeBytes":"1601706"}
        # {"name":"ITA_PM_Torino-Caselle.AP.160590_TMYx.2009-2023_4A.epw","sizeBytes":"1586795"}
        # So they are directly in WeatherFile.
        
        epw_pattern = os.path.join(weather_dir, f'*{zone}*.epw')
        epws = glob.glob(epw_pattern)
        
        if not epws:
            print(f"Warning: No weather file found for zone {zone}")
            continue
            
        # Assuming one weather file per zone for now, or use the first one found
        epw_file = epws[0]
        
        for idf in idfs:
            simulation_pairs.append({
                'idf': idf,
                'epw': epw_file,
                'zone': zone,
                'name': os.path.basename(idf)
            })
            
    return simulation_pairs
