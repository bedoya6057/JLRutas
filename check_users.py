import pandas as pd

FILE_PATH = r"C:\Users\sodexo\Laptop Sodexo Sincronizada\OneDrive\Documentos\Sodexo\Laptop Sodexo\Descargas\Personal Mystery Shopper.xlsx"

try:
    df = pd.read_excel(FILE_PATH)
    print("Columns:", df.columns.tolist())
    print(df.head(3))
except Exception as e:
    print(e)
