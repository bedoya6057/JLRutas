
import pandas as pd
import numpy as np

file_path = "locales_coords.xlsx"

try:
    df = pd.read_excel(file_path)
    print("Columns:", df.columns.tolist())
    
    # Check sample of Lat/Lon
    print("\nSample Data (Raw):")
    print(df[['DISTRITO', 'PROVINCIA', 'Latitud', 'Longitud']].head(10))
    
    def clean_coord(val):
        try:
            if pd.isna(val): return None
            s_val = str(val).strip().replace(',', '.')
            # Fix weird formats like -7.712.329...
            # If multiple dots, keep only the first one? Or is it a thousand separator?
            # usually coords are -12.1234. If it looks like -12.123.456 it's garbage or needs specific parsing.
            
            # Simple check: is it a float?
            return float(s_val)
        except:
            return None

    df['lat_clean'] = df['Latitud'].apply(clean_coord)
    df['lon_clean'] = df['Longitud'].apply(clean_coord)
    
    print("\nCleaned Data Stats:")
    print(df[['lat_clean', 'lon_clean']].describe())
    
    # Check for failures
    failures = df[df['lat_clean'].isna()]
    print(f"\nFailed to parse {len(failures)} rows.")
    if not failures.empty:
        print(failures[['Latitud', 'Longitud']].head())

    # Create a dictionary of the first valid coord per district
    # Group by District and take the first valid
    valid_df = df.dropna(subset=['lat_clean', 'lon_clean'])
    
    # Normalize keys
    valid_df['key'] = valid_df.apply(lambda row: (str(row['PROVINCIA']).upper().strip(), str(row['DISTRITO']).upper().strip()), axis=1)
    
    dist_map = {}
    for _, row in valid_df.iterrows():
        if row['key'] not in dist_map:
            dist_map[row['key']] = (row['lat_clean'], row['lon_clean'])
            
    print(f"\nGenerated Map with {len(dist_map)} districts.")
    
    # Check Arequipa districts sample
    print("\nSample Arequipa Districts:")
    for k, v in list(dist_map.items())[:10]:
        if "AREQUIPA" in k[0]:
            print(k, v)

except Exception as e:
    print(f"Error: {e}")
