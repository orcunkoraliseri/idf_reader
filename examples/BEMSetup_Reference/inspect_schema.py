import sqlite3
import os

db_path = r'c:\Users\o_iseri\Desktop\bem_ubemSetup\SimResults\ASHRAE901_ApartmentMidRise_STD2022_Atlanta_3A\eplusout.sql'

if not os.path.exists(db_path):
    print("DB not found")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get info about TabularDataWithStrings
    cursor.execute("PRAGMA table_info(TabularDataWithStrings)")
    columns = cursor.fetchall()
    print("Columns in TabularDataWithStrings:")
    for col in columns:
        print(col)
        
    # Also check ReportDataDictionary for the other error
    cursor.execute("PRAGMA table_info(ReportDataDictionary)")
    columns = cursor.fetchall()
    print("\nColumns in ReportDataDictionary:")
    for col in columns:
        print(col)

    conn.close()
