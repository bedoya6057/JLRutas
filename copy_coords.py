
import shutil
import pandas as pd
import os

source = r"c:\Users\sodexo\Laptop Sodexo Sincronizada\OneDrive\Documentos\Sodexo\Laptop Sodexo\Descargas\Listado de provincias- latidud y longitud standard.XLSX"
dest = r"c:\Users\sodexo\Laptop Sodexo Sincronizada\OneDrive\Documentos\Sodexo\Laptop Sodexo\Documentos\Nueva carpeta\jlrutas\district_coords.xlsx"

try:
    shutil.copy2(source, dest)
    print(f"File copied successfully to {dest}")
    
    # Read the file
    df = pd.read_excel(dest)
    print("\nDataFrame Info:")
    print(df.info())
    print("\nFirst 5 rows:")
    print(df.head())
    
except Exception as e:
    print(f"Error: {e}")
