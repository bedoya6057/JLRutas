
import shutil
import pandas as pd
import os

source = r"c:\Users\sodexo\Laptop Sodexo Sincronizada\OneDrive\Documentos\Sodexo\Laptop Sodexo\Descargas\Locales_con_coordenadas.xlsx"
dest = r"c:\Users\sodexo\Laptop Sodexo Sincronizada\OneDrive\Documentos\Sodexo\Laptop Sodexo\Documentos\Nueva carpeta\jlrutas\locales_coords.xlsx"

try:
    if os.path.exists(source):
        shutil.copy2(source, dest)
        print(f"File copied successfully to {dest}")
        
        # Read the file
        df = pd.read_excel(dest)
        print("\nDataFrame Info:")
        print(df.info())
        print("\nFirst 5 rows:")
        print(df.head())
    else:
        print(f"Source file not found: {source}")
    
except Exception as e:
    print(f"Error: {e}")
