@echo off
echo Iniciando JLRutas (Sodexo)...
echo ==================================================
echo.
cd /d "%~dp0"

echo Verificando dependencias...
pip install streamlit streamlit-folium pandas folium ortools openpyxl > nul

echo Lanzando Aplicacion...
streamlit run app.py

pause
