import pandas as pd

import shutil
import os

FILE_PATH = r"C:\Users\sodexo\Laptop Sodexo Sincronizada\OneDrive\Documentos\Sodexo\Laptop Sodexo\Descargas\Personal Mystery Shopper.xlsx"
TEMP_FILE = "temp_users_extract.xlsx"

try:
    if os.path.exists(TEMP_FILE):
        os.remove(TEMP_FILE)
    shutil.copy2(FILE_PATH, TEMP_FILE)
    
    # Read with header=1 as discovered before
    df = pd.read_excel(TEMP_FILE, header=1)
    df.columns = df.columns.str.strip().str.upper()
    
    users_dict = {}
    
    # Iterate and populate dict
    # We want to store {EMAIL: {'password': DNI, 'label': NAME}}
    
    users_dict = {}
    
    col_correo = next((c for c in df.columns if 'CORREO' in c), None)
    col_dni = next((c for c in df.columns if 'DNI' in c), None)
    col_nombre = next((c for c in df.columns if 'ENCUESTADOR' in c or 'NOMBRE' in c), None)
    col_ciudad = next((c for c in df.columns if 'CIUDAD' in c or 'SEDE' in c or 'BASE' in c), None) # NEW: City column
    
    if col_correo and col_dni:
        for _, row in df.iterrows():
            email = str(row[col_correo]).strip()
            dni = str(row[col_dni]).strip().replace('.0', '')
            
            # Get Name if available
            label = email.split('@')[0].capitalize() # Fallback
            if col_nombre:
                val = str(row[col_nombre]).strip()
                if val and val != 'nan':
                    label = val
            
            # Get City if available
            city = "Desconocida"
            if col_ciudad:
                val = str(row[col_ciudad]).strip().upper()
                if val and val != 'nan':
                    city = val

            if email and email != 'nan' and dni and dni != 'nan':
                 users_dict[email] = {'password': dni, 'label': label, 'city': city}
                
    print("USERS_DB = {")
    for k, v in users_dict.items():
        print(f"    '{k}': {v},")
    print("}")
    
except Exception as e:
    print(f"Error: {e}")
