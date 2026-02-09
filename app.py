
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from vrp_solver import solve_vrp_data, format_solution, generate_folium_map
import io
import os
import math
import json

st.set_page_config(page_title="Gestión de Rutas - JLMarketing", layout="wide", page_icon="🚛")

# --- CUSTOM CSS (JLMARKETING BRANDING) ---
st.markdown("""
    <style>
    /* Main Background */
    .stApp {
        background-color: #F4F6F8;
    }
    
    /* Headers - JLMarketing Navy */
    h1, h2, h3, h4, h5, h6 {
        color: #262262 !important;
        font-family: 'Segoe UI', sans-serif;
    }
    
    /* Buttons - JLMarketing Red */
    .stButton button {
        background-color: #EF4044 !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
        transition: all 0.3s ease !important;
    }
    .stButton button:hover {
        background-color: #D12F33 !important;
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.2) !important;
    }
    
    /* Metrics Styles */
    div[data-testid="stMetricValue"] {
        color: #EF4044 !important;
        font-weight: bold;
    }
    div[data-testid="stMetricLabel"] {
        color: #5D5D5D !important;
    }
    
    /* Cards/Containers (Simulated with standard Streamlit containers, but we can style markers) */
    div[data-testid="stExpander"] {
        border-color: #E0E0E0 !important;
        border-radius: 8px !important;
        background-color: white !important;
    }
    
    /* Tables */
    thead tr th:first-child {display:none}
    tbody th {display:none}
    
    /* INPUTS & MENUS - Gray Background, Blue Text */
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] > div, .stTextArea textarea {
        background-color: #E0E4E8 !important;
        color: #262262 !important;
        border-radius: 5px;
        border: 1px solid #B0B0B0 !important;
    }
    
    /* Dropdown Menu Container - TARGET POP OVERS */
    div[data-baseweb="popover"], div[data-baseweb="popover"] > div, ul[data-baseweb="menu"] {
        background-color: #E0E4E8 !important;
    }
    
    /* Dropdown Options Text */
    li[data-baseweb="option"] span, li[data-baseweb="option"] div, .stSelectbox [data-baseweb="menu"] li {
        color: #262262 !important;
    }
    
    /* Selected Option Background (Hover) */
    li[data-baseweb="option"]:hover, li[data-baseweb="option"][aria-selected="true"] {
        background-color: #CCD3D9 !important;
    }

    /* Selected Text in Input Box */
    div[data-baseweb="select"] span {
        color: #262262 !important;
    }
    
    /* Remove white/dark default backgrounds on the list container */
    .stSelectbox ul { 
        background-color: #E0E4E8 !important; 
    }
    
    /* HEADERS - FORCE BLUE (Fix for White Text Issue) */
    h1, h2, h3, h4, h5, h6, 
    .stHeadingContainer h1, .stHeadingContainer h2, .stHeadingContainer h3,
    div[data-testid="stMarkdownContainer"] h1, div[data-testid="stMarkdownContainer"] h2, div[data-testid="stMarkdownContainer"] h3,
    div[data-testid="stMarkdownContainer"] p, 
    .stMarkdown label p {
        color: #262262 !important;
        font-family: 'Segoe UI', sans-serif;
    }
    
    /* Ensure widgets label texts are also blue */
    .stSelectbox label, .stTextInput label, .stNumberInput label {
        color: #262262 !important;
    }
    
    /* Metric Labels */
    div[data-testid="stMetricLabel"] {
        color: #262262 !important;
    }
    
    /* DATAFRAMES / TABLES - Force Gray Background */
    [data-testid="stDataFrame"], [data-testid="stTable"] {
        background-color: #E0E4E8 !important;
    }
    
    </style>
""", unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if 'stage' not in st.session_state:
    st.session_state.stage = 'input_tickets' # input_tickets, fleet_config, results
if 'daily_tickets' not in st.session_state:
    st.session_state.daily_tickets = [] # List of dicts
if 'master_db' not in st.session_state:
    st.session_state.master_db = None
if 'optimization_result' not in st.session_state:
    st.session_state.optimization_result = None

# --- CONSTANTS ---
MASTER_FILE_PATH = "Base Arequipa .xlsx"
DEPARTMENT_DEPOTS = {
    "AREQUIPA": (-16.398803, -71.536906), # Plaza de Armas Arequipa
    "LIMA": (-12.046374, -77.042793), # Plaza Mayor Lima
    "CUSCO": (-13.516806, -71.979043), # Plaza de Armas Cusco
    "LA LIBERTAD": (-8.111867, -79.028689), # Plaza de Armas Trujillo
    "LAMBAYEQUE": (-6.771373, -79.840883), # Parque Principal Chiclayo
    "PIURA": (-5.194493, -80.632821), # Plaza de Armas Piura
    "JUNIN": (-12.065133, -75.204863), # Plaza Constitución Huancayo
    "ANCASH": (-9.527376, -77.528414), # Plaza de Armas Huaraz
    "ICA": (-14.063852, -75.729092), # Plaza de Armas Ica
    "TACNA": (-18.013998, -70.252378), # Plaza de Armas Tacna
    "PUNO": (-15.840291, -70.028249), # Plaza de Armas Puno
    "CAJAMARCA": (-7.163784, -78.500272), # Plaza de Armas Cajamarca
    "LORETO": (-3.749117, -73.244367), # Plaza de Armas Iquitos
    "SAN MARTIN": (-6.495000, -76.368300), # Plaza de Armas Tarapoto approx
    "HUANUCO": (-9.929562, -76.239617), # Plaza de Armas Huánuco
    "AYACUCHO": (-13.160444, -74.225725) # Plaza Mayor Ayacucho
}

import shutil

# --- HELPER FUNCTIONS ---
@st.cache_data
def load_master_db(path):
    if not os.path.exists(path):
        return None
    try:
        # Try reading directly
        df = pd.read_excel(path, sheet_name='Hoja2') # Updated to Hoja2 as per user request
        df.columns = df.columns.str.strip()
        
        # COLUMN MAPPING (New DB -> App Schema)
        # We map: Lat -> Latitud (y), Long -> Longitud (x), gerencia -> Habla a
        rename_map = {
            'Lat': 'Latitud (y)',
            'Long': 'Longitud (x)',
            'gerencia': 'Habla a'
        }
        df.rename(columns=rename_map, inplace=True)

        # FORCE NUMERIC
        for col in ['Latitud (y)', 'Longitud (x)']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except PermissionError:
        # File might be open. Copy to temp and read.
        try:
            temp_path = "temp_master_copy.xlsm" # Consider renaming to .xlsx if source is xlsx
            shutil.copy2(path, temp_path)
            df = pd.read_excel(temp_path, sheet_name='Hoja2')
            df.columns = df.columns.str.strip()
            
            # COLUMN MAPPING (New DB -> App Schema)
            rename_map = {
                'Lat': 'Latitud (y)',
                'Long': 'Longitud (x)',
                'gerencia': 'Habla a'
            }
            df.rename(columns=rename_map, inplace=True)

            # FORCE NUMERIC
            for col in ['Latitud (y)', 'Longitud (x)']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        except Exception as e:
            st.error(f"El archivo parece estar abierto y no se pudo copiar. Por favor ciérrelo. Error: {e}")
            return None
    except Exception as e:
        st.error(f"Error al cargar la base de datos maestra: {e}")
        return None

def style_dataframe(df):
    """Applies JLMarketing branding to DataFrames"""
    return df.style.set_properties(**{
        'background-color': '#E0E4E8',
        'color': '#262262',
        'border-color': '#FFFFFF'
    }).set_table_styles([
        {'selector': 'th', 'props': [('background-color', '#CCD3D9'), ('color', '#262262'), ('font-weight', 'bold')]}
    ])

def reset_app():
    st.session_state.stage = 'input_tickets'
    st.session_state.daily_tickets = []
    st.session_state.optimization_result = None

# --- AUTHENTICATION & LOGIN ---
# Hardcoded Users (Datos extraídos de Personal Mystery Shopper.xlsx - NO requiere archivo en ejecución)
USERS_DB = {
    'encuestador1@jlmarketing.com': {'password': '10871096', 'label': 'LUZ MARGARITA RUGEL NASTARES', 'city': 'LIMA'},
    'encuestador2@jlmarketing.com': {'password': '10615349', 'label': 'ROSA HERMELINDA BASILIO CÓRDOVA', 'city': 'LIMA'},
    'encuestador3@jlmarketing.com': {'password': '6596211', 'label': 'MANUEL ROBER CHUQUIZUTA GALVEZ', 'city': 'LIMA'},
    'encuestador4@jlmarketing.com': {'password': '46212120', 'label': 'PAOLA MERCEDES JACHILLA DUEÑAS', 'city': 'LIMA'},
    'encuestador5@jlmarketing.com': {'password': '10630322', 'label': 'MARIA DEL CARMEN AGAPTO DÍAZ', 'city': 'LIMA'},
    'encuestador6@jlmarketing.com': {'password': '40628021', 'label': 'CALUDIA ARMAS PRINCIPE', 'city': 'LIMA'},
    'encuestador7@jlmarketing.com': {'password': '40592640', 'label': 'MARIA JOSÉ MONTOYA CRUZ', 'city': 'LIMA'},
    'encuestador8@jlmarketing.com': {'password': '8174337', 'label': 'ENMA ROSIO BASILIO  MARTINEZ', 'city': 'LIMA'},
    'encuestador9@jlmarketing.com': {'password': '9573688', 'label': 'JORGE ARIAS', 'city': 'LIMA'},
    'encuestador10@jlmarketing.com': {'password': '7496552', 'label': 'CARLOS PALACIOS', 'city': 'LIMA'},
    'encuestador11@jlmarketing.com': {'password': '7460034', 'label': 'CRISTINA DE LA TORRE', 'city': 'LIMA'},
    'encuestador12@jlmarketing.com': {'password': '9903517', 'label': 'BERTHA CESPEDES', 'city': 'LIMA'},
    'encuestador13@jlmarketing.com': {'password': '6075547', 'label': 'LILIAN SALDARRIAGA', 'city': 'LIMA'},
    'encuestador14@jlmarketing.com': {'password': '40723569', 'label': 'JOSÉ POMALAZA', 'city': 'LIMA'},
    'encuestador15@jlmarketing.com': {'password': '10241304', 'label': 'CAROL LAZARTE', 'city': 'LIMA'},
    'encuestador16@jlmarketing.com': {'password': '40513619', 'label': 'ROBERT WILLIAM FARFAN', 'city': 'PIURA'},
    'encuestador17@jlmarketing.com': {'password': '10649956', 'label': 'CYNTHIA REYES', 'city': 'CUSCO'},
    'encuestador18@jlmarketing.com': {'password': '80436187', 'label': 'GIULIANA ALVAREZ', 'city': 'AREQUIPA'},
    'encuestador19@jlmarketing.com': {'password': '40541598', 'label': 'MARIBEL AGUILAR', 'city': 'AREQUIPA'},
    'encuestador20@jlmarketing.com': {'password': '18184974', 'label': 'ANGELICA MELON', 'city': 'AREQUIPA'},
    'encuestador21@jlmarketing.com': {'password': '29527444', 'label': 'NELLY GUTIERREZ', 'city': 'AREQUIPA'},
    'encuestador22@jlmarketing.com': {'password': '30675399', 'label': 'FLOR MALAGA', 'city': 'AREQUIPA'},
    'encuestador23@jlmarketing.com': {'password': '2934906', 'label': 'MAGDA CHAVEZ', 'city': 'AREQUIPA'},
    'encuestador24@jlmarketing.com': {'password': '10344914', 'label': 'MARCO GALVEZ', 'city': 'AREQUIPA'},
    'encuestador25@jlmarketing.com': {'password': '70212319', 'label': 'SEBASTIAN PAZ', 'city': 'AREQUIPA'},
    'encuestador26@jlmarketing.com': {'password': '62218407', 'label': 'KEVIN RAMOS', 'city': 'AREQUIPA'},
    'encuestador27@jlmarketing.com': {'password': '10649956', 'label': 'MARIA ROSARIO ESPINOZA', 'city': 'ICA'},
    'encuestador28@jlmarketing.com': {'password': '16658463', 'label': 'MARIA URRUTIA SAMAME', 'city': 'CHICLAYO'},
    'encuestador29@jlmarketing.com': {'password': '16705601', 'label': 'ALEIDA JANET  URRUTIA SAMAME', 'city': 'CHICLAYO'},
    'encuestador30@jlmarketing.com': {'password': '16751960', 'label': 'MARIA TERESA SANTIESTEBAN', 'city': 'CHICLAYO'},
    'encuestador31@jlmarketing.com': {'password': '41634387', 'label': 'CYNTHIA PACHERRES', 'city': 'CHICLAYO'},
    'encuestador32@jlmarketing.com': {'password': '40231744', 'label': 'CARMEN LILIANA CARDENAS', 'city': 'TRUJILLO'},
    'encuestador33@jlmarketing.com': {'password': '18216054', 'label': 'ADA LITO ALVARADO', 'city': 'TRUJILLO'},
    'encuestador34@jlmarketing.com': {'password': '9451836', 'label': 'CELINDA VELASQUEZ', 'city': 'NAN'},
}

ASSIGNMENTS_FILE = "assignments.json"

def save_assignments(assignments_data):
    try:
        with open(ASSIGNMENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(assignments_data, f, indent=4, default=str)
        st.toast("Asignaciones guardadas correctamente.", icon="💾")
    except Exception as e:
        st.error(f"Error guardando asignaciones: {e}")

def load_assignments():
    if os.path.exists(ASSIGNMENTS_FILE):
        try:
            with open(ASSIGNMENTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def render_route_details(vehicle_route, vid, v_type, is_admin=False, route_city="AREQUIPA", unique_key_suffix=""):
    icon = "🚙" if v_type == "Auto" else "🚶"
    
    # Use simple ID for display if possible, or handle string inputs gracefully
    display_id = vid
    if isinstance(vid, int): display_id = vid + 1
    
    with st.expander(f"{icon} {v_type} #{display_id} ({len(vehicle_route)} paradas) - {route_city}", expanded=True):
        st.write(f"**Tiempo Estimado:** {vehicle_route['AccumulatedDuration_Mins'].max()} min")
        
        # --- ADMIN ASSIGNMENT UI ---
        if is_admin:
            # Filter users by City
            filtered_users = {email: data for email, data in USERS_DB.items() if data.get('city', 'Desconocida') == route_city}
            
            # Format function for names
            def format_func(email):
                if not email: return "Seleccione encuestador"
                return f"{USERS_DB[email]['label']} ({USERS_DB[email]['city']})"

            # If no users found for city, show message or defaults
            options = [""] + list(filtered_users.keys())
            
            # Unique Key Construction
            widget_key = f"assign_{vid}{unique_key_suffix}"
            
            st.selectbox(
                f"Asignar ruta ({route_city}) a:", 
                options, 
                format_func=format_func,
                key=widget_key,
                index=0
            ) 
            if not filtered_users:
                st.warning(f"No hay encuestadores registrados en {route_city}") 
        
        # VISUAL FLOW SEQUENCE & MAPS LINK
        path_steps = []
        
        # Origin & Dest: Centro de Arequipa
        depot_coords = "-16.398803,-71.536906"
        
        # Collect Waypoints
        waypoints_list = []
        
        for _, row in vehicle_route.iterrows():
            loc_str = row['LocationName']
            if row['Client']:
                loc_str += f" ({row['Client']})"
            path_steps.append(loc_str)
            
            if 'Latitude' in row and 'Longitude' in row and pd.notnull(row['Latitude']) and pd.notnull(row['Longitude']):
                waypoints_list.append(f"{row['Latitude']},{row['Longitude']}")
        
        flow_str = " ➝ ".join(path_steps)
        st.info(f"**Secuencia de Visita:**\n\n🏁 Inicio ➝ {flow_str} ➝ 🏁 Fin")
        
        if waypoints_list:
            full_path_coords = [depot_coords] + waypoints_list + [depot_coords]
            stride = 9 
            total_points = len(full_path_coords)
            
            if total_points <= 10:
                wps = "|".join(full_path_coords[1:-1])
                tm = "driving" if v_type == "Auto" else "walking"
                maps_url = f"https://www.google.com/maps/dir/?api=1&origin={full_path_coords[0]}&destination={full_path_coords[-1]}&waypoints={wps}&travelmode={tm}"
                st.link_button("🗺️ Ver Ruta Completa", maps_url)
            else:
                st.write("**🗺️ Rutas Google Maps (Por Tramos):**")
                cols = st.columns(4) 
                
                button_idx = 0
                for i in range(0, total_points - 1, stride):
                    end_idx = i + stride + 1
                    if end_idx > total_points: end_idx = total_points
                    
                    segment = full_path_coords[i:end_idx]
                    if len(segment) < 2: break
                    
                    s_origin = segment[0]
                    s_dest = segment[-1]
                    s_waypoints = "|".join(segment[1:-1])
                    
                    tm = "driving" if v_type == "Auto" else "walking"
                    maps_url = f"https://www.google.com/maps/dir/?api=1&origin={s_origin}&destination={s_dest}&waypoints={s_waypoints}&travelmode={tm}"
                    
                    label = f"Tramo {button_idx+1} (Pts {i+1}-{end_idx})"
                    
                    if button_idx < 4:
                        cols[button_idx].link_button(label, maps_url)
                    else:
                        st.link_button(label, maps_url)
                    
                    button_idx += 1
        
        # Create a nice timeline list
        for _, stop in vehicle_route.iterrows():
            client_str = f" ({stop['Client']})" if stop['Client'] else ""
            st.markdown(f"**{stop['OrderInRoute']}. {stop['LocationName']}{client_str}**")

def check_login(username, password):
    # 0. Normalize Input
    if not username or not password:
        return False, None
        
    username = username.strip().lower()
    password = password.strip()

    # 1. Admin Check
    # Allow both 'abedoya@jlmarketing' AND 'abedoya@jlmarketing.com'
    if username in ["abedoya@jlmarketing", "abedoya@jlmarketing.com"] and password == "cbnmpp2344":
        return True, "admin"
    
    # 2. User Check (Hardcoded DB)
    if username in USERS_DB:
        user_data = USERS_DB[username]
        # Handle dict format
        if isinstance(user_data, dict):
             if user_data['password'] == password:
                 return True, "user"
        # Fallback for old str format if any remaining
        elif user_data == password:
             return True, "user"
            
    return False, None

def login_screen():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=200)
        
        st.markdown("<h3 style='text-align: center; color: #262262;'>🔐 Iniciar Sesión</h3>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            user = st.text_input("Usuario (Correo)", placeholder="ejemplo@jlmarketing.com")
            pwd = st.text_input("Contraseña (DNI / Clave)", type="password")
            submitted = st.form_submit_button("Ingresar", type="primary", use_container_width=True)
            
            if submitted:
                valid, role = check_login(user, pwd)
                if valid:
                    st.session_state.logged_in = True
                    st.session_state.role = role
                    st.session_state.username = user
                    st.rerun()
                else:
                    st.error("❌ Credenciales incorrectas")

# --- MAIN APP AUTH CHECK ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'role' not in st.session_state:
    st.session_state.role = None

if not st.session_state.logged_in:
    login_screen()
    st.stop() # Stop here if not logged in

# --- LOGOUT & USER INFO ---
with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    
    st.write(f"👤 **{st.session_state.username}**")
    st.caption(f"Rol: {st.session_state.role.upper()}")
    if st.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.rerun()

    st.divider()
    if st.button("🔄 Recargar Base Maestra"):
        load_master_db.clear()
        # clear session state caches
        if 'address_map' in st.session_state:
            del st.session_state.address_map
        if 'districts_list' in st.session_state:
            del st.session_state.districts_list
        st.cache_data.clear()
        st.success("Base Maestra recargada. Reiniciando...")
        st.rerun()

# --- ROLE RESTRICTION & USER VIEW ---
if st.session_state.role != 'admin':
    # Get Label
    user_label = st.session_state.username
    if st.session_state.username in USERS_DB and isinstance(USERS_DB[st.session_state.username], dict):
        user_label = USERS_DB[st.session_state.username]['label']
        
    st.title(f"👋 Bienvenido, {user_label}")
    
    assignments = load_assignments()
    my_data = assignments.get(st.session_state.username)
    
    if my_data:
        st.success("✅ Tiene una ruta asignada.")
        try:
            # Reconstruct DF from JSON
            vehicle_route = pd.read_json(my_data['route_df_json'], orient='records')
            vid = my_data['vid']
            v_type = my_data['v_type']
            
            render_route_details(vehicle_route, vid, v_type, is_admin=False, route_city="AREQUIPA") # Default for user view
        except Exception as e:
            st.error(f"Error cargando ruta asignada: {e}")
    else:
        st.info("Actualmente no tiene rutas asignadas para visualización en este módulo.")
    
    st.stop() # Stop here for non-admins

# --- APP HEADER (Admin Only) ---
# --- APP HEADER ---
# 1. Logo (Left Aligned)
if os.path.exists("logo.png"):
    st.image("logo.png", width=300)
else:
    # Fallback text
    st.markdown("<h1 style='color: #262262; font-size: 40px; margin:0; padding:0;'>SODEXO</h1>", unsafe_allow_html=True)

# 2. Title (Centered and Below Logo)
st.markdown("<h1 style='text-align: center; color: #262262; padding-top: 10px;'>JLRutas - Planificador</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #5D5D5D; font-weight: bold;'>Gestión Inteligente de Flota y Entregas - JLMarketing Perú</p>", unsafe_allow_html=True)

if st.button("🔄 Reiniciar Aplicación"):
    reset_app()
    st.rerun()

# --- LOAD DATABASE (ONCE) ---
if st.session_state.master_db is None:
    df_db = load_master_db(MASTER_FILE_PATH)
    if df_db is not None:
        st.session_state.master_db = df_db
        st.success("✅ Base de Datos de Oficinas cargada correctamente.")
    else:
        st.error(f"❌ No se encontró el archivo maestro en: {MASTER_FILE_PATH}")
        uploaded = st.file_uploader("Por favor cargue el archivo 'VRP_Spreadsheet_Solver_v3.8 14.05.xlsm' manualmente:", type=["xlsx", "xlsm"])
        if uploaded:
            st.session_state.master_db = pd.read_excel(uploaded, sheet_name='1 ubicaciones')
            st.session_state.master_db.columns = st.session_state.master_db.columns.str.strip()
            st.rerun()
        else:
            st.stop()

# --- STAGE 1: INGRESO DE TICKETS ---
if st.session_state.stage == 'input_tickets':
    st.header("1️⃣ Ingreso de Tickets del Día")
    
    col_input, col_table = st.columns([1, 2])
    
    with col_input:
        tab_manual, tab_import = st.tabs(["📝 Manual", "📂 Importar Excel"])
        
        with tab_manual:
            st.subheader("Nuevo Ticket Individual")

            # --- CLIENT FILTER ---
            if 'Habla a' in st.session_state.master_db.columns:
                clients = sorted(st.session_state.master_db['Habla a'].astype(str).unique().tolist())
                selected_client = st.selectbox("Filtrar por Cliente", options=["Todos"] + clients)
            else:
                options_clients = ["Todos"]
                selected_client = st.selectbox("Filtrar por Cliente", options=options_clients, disabled=True)

            # Filter Options
            if selected_client != "Todos":
                filtered_db = st.session_state.master_db[st.session_state.master_db['Habla a'].astype(str) == selected_client]
                office_options = filtered_db['domicilio'].astype(str).unique().tolist() if 'domicilio' in filtered_db.columns else filtered_db['Nombre'].unique().tolist()
            else:
                office_options = st.session_state.master_db['domicilio'].astype(str).unique().tolist() if 'domicilio' in st.session_state.master_db.columns else st.session_state.master_db['Nombre'].unique().tolist()

            # --- MANUAL ENTRY FORM ---
            with st.form("ticket_form", clear_on_submit=True):
                selected_office = st.selectbox("Seleccionar Domicilio", options=sorted(office_options))
                
                ticket_id = st.text_input("Nro Ticket (ID)")
                familia = st.text_input("Familia / Especialidad")
                
                add_btn = st.form_submit_button("➕ Agregar a la Lista")
                
                if add_btn:
                    if not ticket_id:
                        st.warning("Por favor ingrese un número de ticket.")
                    else:
                        # Find coords for selected office
                        # If domicilio is used, match on 'domicilio', otherwise 'Nombre'
                        col_to_match = 'domicilio' if 'domicilio' in st.session_state.master_db.columns else 'Nombre'
                        office_data = st.session_state.master_db[st.session_state.master_db[col_to_match].astype(str) == str(selected_office)].iloc[0]
                        
                        # --- DATA ENRICHMENT ---
                        # Extract City (Provincia/Departamento) and District (Distrito)
                        # USER REQUEST: Use Department (DEPARTAMENTO) for main grouping
                        provincia = str(office_data.get('departamento', office_data.get('provincia', 'Desconocida'))).strip().upper()
                        distrito = str(office_data.get('distrito', 'Desconocido')).strip().upper()
                        
                        st.session_state.daily_tickets.append({
                            "Nombre": selected_office,
                            "Habla a": office_data.get('Habla a', ''),
                            "Ticket": ticket_id,
                            "Familia": familia,
                            "Latitud (y)": office_data['Latitud (y)'],
                            "Longitud (x)": office_data['Longitud (x)'],
                            "Provincia": provincia, # Used as City
                            "Distrito": distrito,
                            "Importe de la entrega": 1 
                        })
                        st.toast(f"Ticket {ticket_id} agregado!", icon="👍")
        
        # --- TAB IMPORT ---
        with tab_import:
            st.subheader("Carga Masiva")
            uploaded_tickets = st.file_uploader("Subir Excel (Columnas: Domicilio, Ticket, Familia)", type=["xlsx", "xls", "csv"])
            
            if uploaded_tickets:
                try:
                    if uploaded_tickets.name.endswith('.csv'):
                        df_upload = pd.read_csv(uploaded_tickets)
                    else:
                        df_upload = pd.read_excel(uploaded_tickets)
                    
                    st.write("Vista Previa:", df_upload.head(3))
                    
                    if st.button("Procesar Archivo"):
                        # Column Mapping Logic
                        # We need 'Domicilio' (to match Master DB), 'Ticket', 'Familia'
                        cols = df_upload.columns.str.lower()
                        
                        # Guess column names - Prioritize Domicilio/Direccion
                        col_oficina = next((c for c in df_upload.columns if 'domicilio' in c.lower() or 'direccion' in c.lower()), None)
                        if not col_oficina:
                             col_oficina = next((c for c in df_upload.columns if 'oficina' in c.lower() or 'nombre' in c.lower()), None)
                             
                        col_ticket = next((c for c in df_upload.columns if 'ticket' in c.lower() or 'numero' in c.lower()), None)
                        col_familia = next((c for c in df_upload.columns if 'familia' in c.lower()), None)
                        
                        if not col_oficina:
                            st.error("No se encontró columna para 'Domicilio', 'Direccion' o 'Oficina'.")
                        else:
                            success_count = 0
                            fail_count = 0
                            unmatched_rows = [] # To store failed inputs
                            
                            # --- OPTIMIZATION: BUILD LOOKUP DICTIONARY ---
                            # Pre-compute normalized map for O(1) access
                            if 'address_map' not in st.session_state:
                                master = st.session_state.master_db
                                addr_map = {}
                                
                                # Helper to normalize
                                def normalize_key(s):
                                    if pd.isna(s): return ""
                                    return str(s).strip().lower()
                                
                                for idx, row in master.iterrows():
                                    # Map Domicilio
                                    if 'domicilio' in master.columns:
                                        k = normalize_key(row['domicilio'])
                                        if k: addr_map[k] = row
                                    
                                    # Map Nombre
                                    k_nom = normalize_key(row['Nombre'])
                                    if k_nom: 
                                        if k_nom not in addr_map: # Prefer Domicilio if conflict? Or just add
                                            addr_map[k_nom] = row
                                            
                                    # Map Ubicación (just in case)
                                    if 'Ubicacion' in master.columns:
                                        k_ubi = normalize_key(row['Ubicacion'])
                                        if k_ubi and k_ubi not in addr_map:
                                             addr_map[k_ubi] = row
                                             
                                             
                                st.session_state.address_map = addr_map
                                
                                # Pre-compute normalized districts for suffix stripping
                                if 'districts_list' not in st.session_state:
                                    if 'distrito' in master.columns:
                                        # Sort by length desc to match longest first (e.g. "San Juan de Lurigancho" before "San Juan")
                                        dists = sorted([str(d).strip().lower() for d in master['distrito'].unique() if pd.notna(d)], key=len, reverse=True)
                                        st.session_state.districts_list = dists
                                    else:
                                        st.session_state.districts_list = []
                            
                            address_map = st.session_state.address_map
                            districts_list = st.session_state.districts_list
                            
                            # Process Uploaded Rows
                            # Show progress bar for large files
                            progress_text = "Procesando direcciones..."
                            my_bar = st.progress(0, text=progress_text)
                            total_rows = len(df_upload)
                            
                            processed_rows = 0
                            
                            for _, row in df_upload.iterrows():
                                processed_rows += 1
                                if processed_rows % 100 == 0:
                                    my_bar.progress(min(processed_rows / total_rows, 1.0), text=f"{progress_text} ({processed_rows}/{total_rows})")
                                
                                input_val = str(row[col_oficina]).strip().lower()
                                
                                # Direct Lookup O(1)
                                office_data = address_map.get(input_val)
                                
                                # Fallback: District Suffix Stripping
                                if office_data is None and districts_list:
                                    # Check if input ends with any known district
                                    for d in districts_list:
                                        if input_val.endswith(d):
                                            # Strip district and trailing spaces
                                            stripped_val = input_val[:-len(d)].strip()
                                            # Remove common separators if left hanging (e.g. "Av. Peru, ")
                                            stripped_val = stripped_val.rstrip(' ,.-')
                                            
                                            # Try finding the stripped value
                                            office_data = address_map.get(stripped_val)
                                            if office_data is not None:
                                                break # Found match!
                                                
                                match_found = office_data is not None
                                
                                if match_found:
                                    # Use matching name (preferred Domicilio if column exists)
                                    final_name = office_data['domicilio'] if 'domicilio' in office_data else office_data['Nombre']
                                    
                                    # --- DATA ENRICHMENT ---
                                    # USER REQUEST: Use Department (DEPARTAMENTO) for main grouping
                                    provincia = str(office_data.get('departamento', office_data.get('provincia', 'Desconocida'))).strip().upper()
                                    distrito = str(office_data.get('distrito', 'Desconocido')).strip().upper()
                                    
                                    st.session_state.daily_tickets.append({
                                        "Nombre": final_name,
                                        "Habla a": office_data.get('Habla a', ''),
                                        "Ticket": row[col_ticket] if col_ticket else "N/A",
                                        "Familia": row[col_familia] if col_familia else "General",
                                        "Latitud (y)": office_data['Latitud (y)'],
                                        "Longitud (x)": office_data['Longitud (x)'],
                                        "Provincia": provincia,
                                        "Distrito": distrito,
                                        "Importe de la entrega": 1
                                    })
                                    success_count += 1
                                else:
                                    fail_count += 1
                                    # Record failure
                                    row_copy = row.copy()
                                    row_copy['Razón'] = 'No encontrado en Base Maestra'
                                    row_copy['Input Normalizado'] = input_val
                                    unmatched_rows.append(row_copy)
                            
                            my_bar.empty()
                                    
                            st.success(f"Procesado: {success_count} tickets agregados.")
                            if fail_count > 0:
                                st.warning(f"⚠️ {fail_count} direcciones no encontradas. Descargue el reporte para corregirlas.")
                                
                                # Convert unmatched to DF and offer download
                                if unmatched_rows:
                                    df_unmatched = pd.DataFrame(unmatched_rows)
                                    csv_unmatched = df_unmatched.to_csv(index=False).encode('utf-8')
                                    st.download_button(
                                        label="📥 Descargar Direcciones No Encontradas (CSV)",
                                        data=csv_unmatched,
                                        file_name="direcciones_no_encontradas.csv",
                                        mime="text/csv"
                                    )
                                
                except Exception as e:
                    st.error(f"Error procesando: {e}")

    with col_table:
        st.subheader("📋 Lista de Pendientes")
        if st.session_state.daily_tickets:
            df_display = pd.DataFrame(st.session_state.daily_tickets)
            st.dataframe(style_dataframe(df_display[['Nombre', 'Ticket', 'Familia']]), use_container_width=True)
            
            if st.button("✅ Confirmar y Configurar Flota", type="primary"):
                st.session_state.stage = 'fleet_config'
                st.rerun()
        else:
            st.info("Agregue tickets para continuar.")


# --- STAGE 2: CONFIGURACION DE FLOTA ---
elif st.session_state.stage == 'fleet_config':
    st.header("2️⃣ Disponibilidad de Vehículos por Departamento")
    
    col_config, col_summary = st.columns(2)
    
    with col_config:
        st.info("Ingrese los recursos disponibles para hoy:")
        
        # USER REQUEST: ONLY WALKERS, PER CITY
        # 1. Detect Cities from Tickets
        df_tickets = pd.DataFrame(st.session_state.daily_tickets)
        if 'Provincia' in df_tickets.columns:
            unique_cities = sorted(df_tickets['Provincia'].unique())
        else:
            unique_cities = ["Desconocida"]
            
        walkers_per_city = {}
        total_walkers = 0
        
        st.write("**Configuración por Departamento:**")
        
        strategies_per_city = {}
        
        for city in unique_cities:
            with st.container():
                st.subheader(f"📍 {city}")
                c1, c2 = st.columns(2)
                # Walker Count
                count = c1.number_input(f"Caminantes en {city}", min_value=0, value=5, key=f"walkers_{city}")
                walkers_per_city[city] = count
                
                # Strategy Selection Per City
                strat = c2.radio(
                    f"Estrategia para {city}",
                    ["Global (Por Ciudad)", "Por Distrito"],
                    key=f"strat_{city}",
                    horizontal=True
                )
                strategies_per_city[city] = strat

                # District Selection if Strategy is "Por Distrito" (Moved here for better UX)
                # District Selection if Strategy is "Por Distrito" (Moved here for better UX)
                if strat == "Por Distrito":
                     # Get districts for this city
                     c_df = df_tickets[df_tickets['Provincia'] == city]
                     all_districts = sorted(c_df['Distrito'].unique())
                     
                     # SINGLE SELECT for "Por Distrito"
                     sel_dist = st.selectbox(
                         f"Distrito a procesar en {city}:",
                         all_districts,
                         key=f"sel_dist_{city}_cfg"
                     )
                     
                elif strat == "Global (Por Ciudad)":
                     c_df = df_tickets[df_tickets['Provincia'] == city]
                     all_districts = sorted(c_df['Distrito'].unique())
                     
                     # EXPANDER WITH CHECKBOX LIST
                     with st.expander(f"Seleccionar Distritos ({len(all_districts)})", expanded=False):
                         # Action Buttons
                         b1, b2 = st.columns(2)
                         if b1.button("✅ Marcar Todos", key=f"btn_all_{city}"):
                             for d in all_districts:
                                 st.session_state[f"chk_{city}_{d}"] = True
                             st.rerun()
                             
                         if b2.button("❌ Desmarcar Todos", key=f"btn_none_{city}"):
                             for d in all_districts:
                                 st.session_state[f"chk_{city}_{d}"] = False
                             st.rerun()
                         
                         st.divider()
                         
                         # Render Checkboxes
                         sel_dist = []
                         for d in all_districts:
                             # Default to True if new
                             key_chk = f"chk_{city}_{d}"
                             if key_chk not in st.session_state:
                                 st.session_state[key_chk] = True
                                 
                             is_checked = st.checkbox(d, key=key_chk)
                             if is_checked:
                                 sel_dist.append(d)
                                 
                     # SAVE SELECTION TO SESSION STATE FOR SOLVER
                     # The solver expects st.session_state[f"sel_dist_{city}_cfg"] to be a list
                     st.session_state[f"sel_dist_{city}_cfg"] = sel_dist
            st.divider()

        num_cars = 0 # Hidden as requested
        
        # Combined Capacity Logic
        # User requested max 50 per person
        max_capacity = st.number_input("Capacidad Max (Tickets por recurso)", min_value=1, value=50)
        
        col_adv_1, col_adv_2 = st.columns(2)
        service_time = col_adv_1.number_input("Tiempo de Servicio por Ticket (min)", min_value=1, value=15)
        # 50 stops * 15 min = 750 min = 12.5 hours. Needs >12h default.
        # User requested NO TIME RESTRICTION -> Set default to very high (100h)
        # User requested NO TIME RESTRICTION -> Set default to very high (100h)
        max_work_hours = col_adv_2.number_input("Jornada Maxima (horas)", min_value=1, value=100, help="Deje un valor alto (ej. 100) para no restringir por tiempo.")

        # Distance Constraint
        max_dist_km = st.number_input("Distancia Máx. por Caminante (km)", min_value=1, value=20, help="Límite de recorrido total por caminante.")

        tf_factor = 1.0
        
        col_act_1, col_act_2 = st.columns(2)
        if col_act_1.button("🔙 Volver"):
            st.session_state.stage = 'input_tickets'
            st.rerun()
            
        if col_act_2.button("🚀 Calcular Rutas", type="primary"):
            # Prepare Data & Run Solver Logic
            
            # Common params
            # User wants efficient routes, give solver more time (60s)
            solver_time_limit = 60
            forced_max_hours = max_work_hours # Respect the input which we increased default for
            
            all_solutions = []
            
            with st.spinner("Calculando rutas multi-ciudad (Optimizando)..."):
                try:
                    # Progress Bar Setup
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Estimate total steps for progress
                    # Global: 1 step per city
                    # District: 1 step per district per city
                    total_steps = 0
                    # Estimate total steps for progress
                    total_steps = 0
                    for c in unique_cities:
                        strat = strategies_per_city.get(c, "Global (Por Ciudad)")
                        if strat == "Global (Por Ciudad)":
                            total_steps += 1
                        else:
                            # Count districts
                            c_df = df_tickets[df_tickets['Provincia'] == c]
                            total_steps += len(c_df['Distrito'].unique())
                    
                    if total_steps == 0: total_steps = 1
                    current_step = 0
                    
                    def update_main_progress(step_idx, stage_desc=""):
                        val = min(1.0, step_idx / total_steps)
                        progress_bar.progress(val)
                        status_text.text(f"Procesando ({int(val*100)}%): {stage_desc}")

                    # ITERATE CITIES
                    # Use enumerate for manual step tracking if needed, 
                    # but we track current_step manually to handle nested loops better
                    
                    for city_idx, city in enumerate(unique_cities):
                        # Filter tickets for this city
                        city_tickets = df_tickets[df_tickets['Provincia'] == city].copy()
                        if city_tickets.empty: continue
                        
                        city_walkers = walkers_per_city.get(city, 1)
                        current_city_strategy = strategies_per_city.get(city, "Global (Por Ciudad)")
                        
                        if city_walkers == 0:
                            st.warning(f"⚠️ {city} omitido (0 caminantes asignados).")
                            # Try to advance progress bar logically
                            steps_for_this_city = 1
                            if current_city_strategy == "Por Distrito":
                                c_df_temp = df_tickets[df_tickets['Provincia'] == city]
                                steps_for_this_city = len(c_df_temp['Distrito'].unique())
                            current_step += steps_for_this_city
                            update_main_progress(current_step, f"Omitido {city}")
                            continue
                        
                        # LOGIC BRANCH: STRATEGY
                        if current_city_strategy == "Global (Por Ciudad)":
                            # --- CASE A: GLOBAL (Multi-District) ---
                            # Retrieve selection (List)
                            selected_districts = st.session_state.get(f"sel_dist_{city}_cfg", [])
                            if not selected_districts: 
                                # Default to all if missing
                                c_df = df_tickets[df_tickets['Provincia'] == city]
                                selected_districts = sorted(c_df['Distrito'].unique())
                            
                            # Filter tickets
                            city_tickets = city_tickets[city_tickets['Distrito'].isin(selected_districts)]
                            
                            if city_tickets.empty:
                                st.warning(f"No hay tickets en los distritos seleccionados para {city} (Global).")
                                continue
                                
                            # Group by Location
                            df_grouped = city_tickets.groupby(['Nombre', 'Latitud (y)', 'Longitud (x)', 'Habla a', 'Provincia', 'Distrito']).agg({
                                'Importe de la entrega': 'sum',
                                'Ticket': lambda x: ', '.join(x.astype(str)), 
                                'Familia': lambda x: ', '.join(x.unique())
                            }).reset_index()

                            # Depot Location (Department Capital)
                            depot_lat, depot_lon = DEPARTMENT_DEPOTS.get(city, (-16.398803, -71.536906))
                            if city not in DEPARTMENT_DEPOTS and city != "Desconocida":
                                if not city_tickets.empty:
                                    depot_lat = city_tickets['Latitud (y)'].mean()
                                    depot_lon = city_tickets['Longitud (x)'].mean()

                            depot_row = pd.DataFrame([{
                                'Nombre': f'DEPOT {city} (Plaza de Armas)', 
                                'Latitud (y)': depot_lat, 
                                'Longitud (x)': depot_lon, 
                                'Habla a': 'JLMarketing',
                                'Importe de la entrega': 0,
                                'Ticket': 'Inicio',
                                'Familia': 'Base',
                                'Provincia': city,
                                'Distrito': 'BASE'
                            }])

                            df_final = pd.concat([depot_row, df_grouped], ignore_index=True)
                            
                            def sub_callback(msg):
                                status_text.text(f"[{city}] {msg}")
                                
                            sol, rout, man, dat, df_cl = solve_vrp_data(
                                df_final, 0, city_walkers, max_capacity, traffic_factor=tf_factor,
                                service_time_per_ticket_mins=service_time, max_work_hours=forced_max_hours,
                                max_seconds=solver_time_limit,
                                max_distance_km=max_dist_km,
                                status_callback=sub_callback
                            )
                            
                            current_step += 1
                            update_main_progress(current_step, f"Finalizado {city}")
                            
                            if sol:
                                all_solutions.append((sol, rout, man, dat, df_cl, city, "Global"))

                        elif current_city_strategy == "Por Distrito":
                            # --- CASE B: PER DISTRICT (Single) ---
                            # Retrieve selection (Single String)
                            selected_district = st.session_state.get(f"sel_dist_{city}_cfg", None)
                            
                            if not selected_district:
                                st.warning(f"No se seleccionó ningún distrito para {city}.")
                                continue
                                
                            dist_tickets = city_tickets[city_tickets['Distrito'] == selected_district].copy()
                            if dist_tickets.empty:
                                st.warning(f"No hay tickets en {selected_district}.")
                                continue
                                
                            # Use ALL walkers for this Single District
                            assigned_walkers = city_walkers
                            
                            df_grouped = dist_tickets.groupby(['Nombre', 'Latitud (y)', 'Longitud (x)', 'Habla a', 'Provincia', 'Distrito']).agg({
                                'Importe de la entrega': 'sum',
                                'Ticket': lambda x: ', '.join(x.astype(str)), 
                                'Familia': lambda x: ', '.join(x.unique())
                            }).reset_index()
                            
                            # Depot: Mean of district (Start/End in district)
                            depot_lat = dist_tickets['Latitud (y)'].mean()
                            depot_lon = dist_tickets['Longitud (x)'].mean()

                            depot_row = pd.DataFrame([{
                                'Nombre': f'DEPOT {city}-{selected_district} (Calculado: Promedio de Tickets)', 
                                'Latitud (y)': depot_lat, 
                                'Longitud (x)': depot_lon, 
                                'Habla a': 'JLMarketing',
                                'Importe de la entrega': 0,
                                'Ticket': 'Inicio',
                                'Familia': 'Base',
                                'Provincia': city,
                                'Distrito': selected_district
                            }])
                            
                            df_final = pd.concat([depot_row, df_grouped], ignore_index=True)
                            
                            def sub_callback(msg):
                                status_text.text(f"[{city}-{selected_district}] {msg}")
                                
                            sol, rout, man, dat, df_cl = solve_vrp_data(
                                df_final, 0, assigned_walkers, max_capacity, traffic_factor=tf_factor,
                                service_time_per_ticket_mins=service_time, max_work_hours=forced_max_hours,
                                max_seconds=solver_time_limit,
                                max_distance_km=max_dist_km,
                                status_callback=sub_callback
                            )
                            
                            current_step += 1
                            update_main_progress(current_step, f"Finalizado {selected_district}")
                            
                            if sol:
                                all_solutions.append((sol, rout, man, dat, df_cl, city, selected_district))

                    if all_solutions:
                        st.session_state.optimization_result = all_solutions # Store List
                        st.session_state.stage = 'results'
                        st.rerun()
                    else:
                        st.error("No se pudo generar ninguna solución. Verifique los datos.")
                        
                except Exception as e:
                    st.error(f"Error calculando rutas: {e}")
                    import traceback
                    traceback.print_exc() 



    with col_summary:
        st.write(f"**Total Tickets:** {len(st.session_state.daily_tickets)}")
        st.write("**Oficinas a visitar:**")
        df_display = pd.DataFrame(st.session_state.daily_tickets)
        # Group by office name and count tickets
        office_counts = df_display.groupby('Nombre').size().reset_index(name='Tickets')
        st.dataframe(office_counts, use_container_width=True, hide_index=True)

# --- STAGE 3: RESULTADOS ---
elif st.session_state.stage == 'results':
    st.header("3️⃣ Rutas Optimizadas")
    
    if st.session_state.optimization_result:
        results_list = st.session_state.optimization_result
        if not isinstance(results_list, list):
            # Backward compatibility or fallback
            results_list = [(*results_list, "General", "General")] 
            
        # Tabs for each Result Group (City/District)
        tab_names = []
        for res in results_list:
            # Struct: (sol, rout, man, dat, df_cl, city, grouping_val)
            city_name = res[5]
            group_val = res[6]
            if group_val == "Global":
                tab_names.append(f"📍 {city_name}")
            else:
                tab_names.append(f"📍 {city_name} - {group_val}")
        
        if not tab_names:
            st.error("No hay resultados para mostrar.")
            if st.button("Volver"):
                st.session_state.stage = 'fleet_config'
                st.rerun()
            st.stop()
            
        tabs = st.tabs(tab_names)
        
        # Container for assignments to save later
        all_routes_data_for_save = {}
        
        for idx, tab in enumerate(tabs):
            with tab:
                solution, routing, manager, data, df_cleaned_res, r_city, r_group = results_list[idx]
                
                # --- METRICS & MAP ---
                max_route_distance = 0
                total_distance = 0
                total_load = 0
                
                # Extract Routes Logic (Copied/Adapted)
                routes = []
                for vehicle_id in range(data['num_vehicles']):
                    if not routing.IsVehicleUsed(solution, vehicle_id): continue
                    
                    index = routing.Start(vehicle_id)
                    route_dist = 0
                    route_load = 0
                    route_geometry = []
                    
                    while not routing.IsEnd(index):
                        node_index = manager.IndexToNode(index)
                        route_load += data['demands'][node_index]
                        
                        # Geometry
                        lat = df_cleaned_res.iloc[node_index]['Latitud (y)']
                        lon = df_cleaned_res.iloc[node_index]['Longitud (x)']
                        route_geometry.append((lat, lon))
                        
                        previous_index = index
                        index = solution.Value(routing.NextVar(index))
                        
                        step_dist = routing.GetArcCostForVehicle(previous_index, index, vehicle_id)
                        route_dist += step_dist
                        
                    # End Node
                    node_index = manager.IndexToNode(index)
                    lat = df_cleaned_res.iloc[node_index]['Latitud (y)']
                    lon = df_cleaned_res.iloc[node_index]['Longitud (x)']
                    route_geometry.append((lat, lon))
                    
                    if route_dist >= 0: # Only active routes
                        # Convert dist (meters appx)
                        dist_km = route_dist / 1000 
                        max_route_distance = max(max_route_distance, dist_km)
                        total_distance += dist_km
                        total_load += route_load
                        
                        # Global unique ID for saving (combine city index + vehicle ID)
                        # To ensure uniqueness across tabs if needed, though VID is per solver instance.
                        # We used vid directly before. It might clash if VID 0 exists in both Arequipa and Lima tabs.
                        # Resolution: Make key composite in session_state? "assign_{city}_{vid}"
                        # BUT render_route_details uses key f"assign_{vid}".
                        # We must update key in render_route_details? 
                        # Or just use VID? Since user inputs are stored by key, if key is same, inputs clash.
                        # FIX: We need unique key in render_route_details.
                        # Let's verify render_route_details key. It uses f"assign_{vid}".
                        # If we have 2 tabs with VID 0, they will share the input!
                        # We need to change render_route_details to accept a key prefix.
                        
                        routes.append({
                            "vehicle_id": vehicle_id,
                            "distance_km": dist_km,
                            "stops": len(route_geometry) - 2, # Exclude depot start/end
                            "load": route_load,
                            "geometry": route_geometry,
                            "type": "Caminante" 
                        })

                # --- DROPPED NODES CHECK ---
                # Count unique non-depot nodes visited
                visited_nodes = set()
                for vehicle_id in range(data['num_vehicles']):
                    if not routing.IsVehicleUsed(solution, vehicle_id): continue
                    index = routing.Start(vehicle_id)
                    while not routing.IsEnd(index):
                        node_index = manager.IndexToNode(index)
                        if node_index != 0: # Skip depot
                            visited_nodes.add(node_index)
                        index = solution.Value(routing.NextVar(index))
                
                total_tickets_in_group = len(df_cleaned_res) - 1
                dropped = total_tickets_in_group - len(visited_nodes)
                
                if dropped > 0:
                     st.error(f"⚠️ {dropped} tickets NO pudieron ser asignados (Falta de tiempo/recursos). Considere aumentar caminantes o tiempo límite.")
                else:
                     st.success("✅ Todos los tickets fueron asignados correctamente.")

                # Display Metrics
                c1, c2, c3 = st.columns(3)
                c1.metric("Distancia Total", f"{total_distance:.2f} km")
                c2.metric("Ruta + Larga", f"{max_route_distance:.2f} km")
                c3.metric("Tickets Atendidos", total_load)
                
                # Display Map (Folium)
                # We reuse the map logic
                center_lat = df_cleaned_res.iloc[0]['Latitud (y)']
                center_lon = df_cleaned_res.iloc[0]['Longitud (x)']
                m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
                
                colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue', 'darkpurple', 'white', 'pink', 'lightblue', 'lightgreen', 'gray', 'black', 'lightgray']
                
                for r in routes:
                    vid = r['vehicle_id']
                    color = colors[vid % len(colors)]
                    
                    folium.PolyLine(r['geometry'], color=color, weight=2.5, opacity=1).add_to(m)
                    
                    index = routing.Start(r['vehicle_id'])
                    step = 0
                    while not routing.IsEnd(index):
                        node_index = manager.IndexToNode(index)
                        row = df_cleaned_res.iloc[node_index]
                        
                        icon_color = color
                        icon_type = "info-sign"
                        if step == 0: icon_type = "home" 
                        
                        folium.Marker(
                            location=[row['Latitud (y)'], row['Longitud (x)']],
                            popup=f"{row['Nombre']} ({row['Habla a']}) - {row.get('Ticket', '')}",
                            icon=folium.Icon(color=icon_color, icon=icon_type)
                        ).add_to(m)
                        
                        index = solution.Value(routing.NextVar(index))
                        step += 1
                        
                st_folium(m, height=400, width="100%", key=f"map_{city_name}_{group_val}_{idx}")
                
                st.subheader("📋 Detalle de Itinerarios")
                
                # --- ITINERARIES ---
                for r in routes:
                    vid = r['vehicle_id']
                    
                    # Reconstruct DataFrame for this route
                    route_rows = []
                    index = routing.Start(vid)
                    accum_time = 0
                    
                    while not routing.IsEnd(index):
                        node_index = manager.IndexToNode(index)
                        if node_index != 0: 
                             row_data = df_cleaned_res.iloc[node_index].copy()
                             accum_time += 15 
                             row_data['AccumulatedDuration_Mins'] = accum_time
                             route_rows.append(row_data)
                        
                        index = solution.Value(routing.NextVar(index))
                        
                    if route_rows:
                        vehicle_route = pd.DataFrame(route_rows)
                        
                        # --- FIX KEY ERROR ---
                        # Map internal DB names to what render_route_details expects
                        if 'Nombre' in vehicle_route.columns:
                            vehicle_route['LocationName'] = vehicle_route['Nombre']
                        if 'Habla a' in vehicle_route.columns:
                            vehicle_route['Client'] = vehicle_route['Habla a']
                        
                        # Map Coordinates for Google Maps
                        if 'Latitud (y)' in vehicle_route.columns:
                             vehicle_route['Latitude'] = vehicle_route['Latitud (y)']
                        if 'Longitud (x)' in vehicle_route.columns:
                             vehicle_route['Longitude'] = vehicle_route['Longitud (x)']
                        
                        # Add Order In Route (Simple index-based)
                        vehicle_route['OrderInRoute'] = range(1, len(vehicle_route) + 1)

                        
                        # Use City+Group+VID as unique ID for saving
                        unique_suffix = f"_{r_city}_{r_group}"
                        unique_vid_key = f"{vid}{unique_suffix}"
                        
                        # Store for saving
                        all_routes_data_for_save[unique_vid_key] = {
                            "route_df_json": vehicle_route.to_json(date_format='iso', orient='records'),
                            "v_type": "Caminante",
                            "vid": unique_vid_key # Use unique string ID
                        }
                        
                        # Render using helper with specific city for this tab
                        render_route_details(vehicle_route, vid, "Caminante", is_admin=True, route_city=r_city, unique_key_suffix=unique_suffix)
        
        # --- SAVE BUTTON ---
        st.markdown("---")
        if st.button("💾 Guardar Asignaciones", type="primary"):
             final_assignments = {}
             # We need to loop through the generated keys.
             # unique_vid_key is e.g "0_AREQUIPA_Global"
             # render_route_details creates key: f"assign_{vid}{unique_key_suffix}"
             # which is f"assign_{vid}" + unique_suffix
             # which is f"assign_{vid}_{r_city}_{r_group}"
             # which is just f"assign_{unique_vid_key}"
             
             for unique_key, data in all_routes_data_for_save.items():
                 widget_key = f"assign_{unique_key}"
                 assigned_user = st.session_state.get(widget_key, "")
                 if assigned_user:
                     final_assignments[assigned_user] = data # Note: data['vid'] is unique string now
            
             if final_assignments:
                 save_assignments(final_assignments)
             else:
                 st.warning("No se seleccionó ningún usuario para asignar.")
             
        # ... (rest of export logic) ...

