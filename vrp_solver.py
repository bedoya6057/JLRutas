
import pandas as pd
import numpy as np
import math
import folium
import os
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from datetime import datetime

# --- CONFIGURATION ---
# --- CONFIGURATION ---
# Default to local file if present, otherwise expecting file upload or param
INPUT_FILE = "Base Arequipa .xlsx" 
OUTPUT_MAP = "mapa_rutas_peru.html"
OUTPUT_EXCEL = "solucion_rutas.xlsx"

def haversine(lat1, lon1, lat2, lon2):
    """Calculates the great circle distance in km between two points."""
    R = 6371  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def create_distance_matrix(locations):
    """
    Creates a distance matrix (meters) from locations using Vectorized Haversine.
    Much faster for large datasets (O(N^2) vectorized).
    """
    n = len(locations)
    print(f"Calculating distance matrix for {n} locations...")
    
    # Extract coordinates
    lats = locations['Latitud (y)'].values
    lons = locations['Longitud (x)'].values
    
    # Convert to radians
    # np.radians is not available if we didn't import numpy fully as np? 
    # We did import numpy as np in line 3.
    lats_rad = np.radians(lats)
    lons_rad = np.radians(lons)
    
    # Simple broadcasting (N, 1) vs (1, N)
    dlat = lats_rad[:, np.newaxis] - lats_rad
    dlon = lons_rad[:, np.newaxis] - lons_rad
    
    a = np.sin(dlat / 2)**2 + np.cos(lats_rad[:, np.newaxis]) * np.cos(lats_rad) * np.sin(dlon / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    
    # Radius of Earth in meters
    R = 6371000 
    dist_matrix_m = R * c
    
    # Convert to int (meters) and list of lists for OR-Tools
    # Force diagonal to 0 just in case
    np.fill_diagonal(dist_matrix_m, 0)
    
    return dist_matrix_m.astype(int).tolist()

def solve_vrp_data(df_loc, num_cars, num_walkers, vehicle_capacity, start_node_index=0, max_seconds=30, traffic_factor=1.0, 
                   service_time_per_ticket_mins=15, max_work_hours=12, status_callback=None, max_distance_km=0):
    """
    Solves VRP for Mixed Fleet (Cars + Walkers).
    """
    num_locations = len(df_loc)
    num_vehicles = num_cars + num_walkers
    print(f"Solving for {num_locations} locations. Cars: {num_cars}, Walkers: {num_walkers}")

    # CLEANING: Ensure coordinates are numeric
    for col in ['Latitud (y)', 'Longitud (x)']:
        if col in df_loc.columns:
            df_loc[col] = pd.to_numeric(df_loc[col], errors='coerce')
            
    # Remove NaN coordinates just in case
    df_loc = df_loc.dropna(subset=['Latitud (y)', 'Longitud (x)'])
    # Re-index to ensure continuity
    df_loc = df_loc.reset_index(drop=True)
    num_locations = len(df_loc) 

    # Build Vehicle Config
    vehicle_capacities = [vehicle_capacity] * num_vehicles
    starts = [start_node_index] * num_vehicles
    ends = [start_node_index] * num_vehicles
    
    # Define Vehicle Types: 0 = Car, 1 = Walker
    vehicle_types = ['Auto'] * num_cars + ['Walker'] * num_walkers
    
    # SETUP DATA MODEL
    data = {}
    
    if status_callback: status_callback("Generando matriz de distancias...")
    
    # 1. DISTANCE MATRIX (Meters)
    data['distance_matrix'] = create_distance_matrix(df_loc)
    
    # Demands
    if 'Importe de la entrega' in df_loc.columns:
        demands = df_loc['Importe de la entrega'].fillna(0).astype(int).tolist()
    elif 'Tickets' in df_loc.columns:
        demands = df_loc['Tickets'].fillna(0).astype(int).tolist()
    else:
        demands = [0] * num_locations 
        
    data['demands'] = demands
    data['vehicle_capacities'] = vehicle_capacities
    data['num_vehicles'] = num_vehicles
    data['starts'] = starts
    data['ends'] = ends
    data['vehicle_types'] = vehicle_types # Store for later formatting
    
    # OR-TOOLS SETUP
    manager = pywrapcp.RoutingIndexManager(len(data['distance_matrix']),
                                           data['num_vehicles'],
                                           data['starts'],
                                           data['ends'])
    
    if status_callback: status_callback("Configurando vehículos y restricciones...")
    routing = pywrapcp.RoutingModel(manager)
    
    # --- DEFINE SPEEDS ---
    # Car Speed (m/s)
    speed_car_kmh = 30 / traffic_factor
    speed_car_ms = speed_car_kmh * (1000 / 3600)
    
    # Walker Speed (m/s)
    speed_walker_kmh = 5.0
    speed_walker_ms = speed_walker_kmh * (1000 / 3600)
    
    service_time_seconds = service_time_per_ticket_mins * 60

    # --- CALLBACKS ---
    def car_time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        # Service time
        service = data['demands'][from_node] * service_time_seconds
        # Travel time
        dist = data['distance_matrix'][from_node][to_node]
        travel = int(dist / speed_car_ms)
        return travel + service

    def walker_time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        # Service time
        service = data['demands'][from_node] * service_time_seconds
        # Travel time
        dist = data['distance_matrix'][from_node][to_node]
        travel = int(dist / speed_walker_ms)
        return travel + service

    car_evaluator_index = routing.RegisterTransitCallback(car_time_callback)
    walker_evaluator_index = routing.RegisterTransitCallback(walker_time_callback)
    
    # Assign Callbacks to Vehicles
    for i in range(num_vehicles):
        if vehicle_types[i] == 'Auto':
            routing.SetArcCostEvaluatorOfVehicle(car_evaluator_index, i)
        else:
            routing.SetArcCostEvaluatorOfVehicle(walker_evaluator_index, i)

    # --- DIMENSIONS ---
    
    # Capacity
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return data['demands'][from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  
        data['vehicle_capacities'],
        True,
        'Capacity')
    
    # Time Dimension
    # We need a generic callback for the dimension if we want to retrieve values, 
    # BUT AddDimensionWithVehicleTransits allows per-vehicle transit!
    
    # Create vector of evaluator indices for all vehicles
    transit_evaluator_indices = []
    for i in range(num_vehicles):
        if vehicle_types[i] == 'Auto':
            transit_evaluator_indices.append(car_evaluator_index)
        else:
            transit_evaluator_indices.append(walker_evaluator_index)

    max_time_seconds = max_work_hours * 3600
    
    # Use AddDimensionWithVehicleTransits to correctly track time per vehicle type
    routing.AddDimensionWithVehicleTransits(
        transit_evaluator_indices,
        max_time_seconds, # Slack
        max_time_seconds, # Horizon
        False, # Start at zero? No, accumulate
        'Time')
    
    # Global Span Cost
    time_dimension = routing.GetDimensionOrDie('Time')
    # User requested NO TIME RESTRICTION and to use MULTIPLE walkers. 
    # High coeff here minimizes max time, which is good for balancing, 
    # BUT if constraints are loose, it might just pick 1 walker if it's cheaper by distance.
    # Let's reduce this or keep it. Actually, minimizing Max Time encourages parallelism.
    # But if efficient to do 1 long route vs 2 short, distance might win.
    # Let's set a small coefficient for GlobalSpan to encourage balance but not dominate.
    time_dimension.SetGlobalSpanCostCoefficient(10)

    # --- DISTANCE DIMENSION (MAX DISTANCE PER WALKER) ---
    if max_distance_km > 0:
        max_dist_meters = int(max_distance_km * 1000)
        
        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return data['distance_matrix'][from_node][to_node]
            
        dist_callback_index = routing.RegisterTransitCallback(distance_callback)
        
        routing.AddDimension(
            dist_callback_index,
            0, # Slack (0 for distance normally)
            max_dist_meters, # Capacity (Max Dist per vehicle)
            True, # Start cumul to zero
            'Distance'
        )
        dist_dimension = routing.GetDimensionOrDie('Distance')
        # Maybe add span cost if we want balanced distances?
        # dist_dimension.SetGlobalSpanCostCoefficient(100)

    # --- ALLOW DROPPING NODES ---
    # To prevent "No Solution" when constraints are too tight
    penalty = 1000000 # High penalty so it tries to visit all
    for node in range(1, len(df_loc)): # 1 to end (0 is depot)
        routing.AddDisjunction([manager.NodeToIndex(node)], penalty)

    # SOLVE
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
        
    # Adaptive Search Strategy based on Size
    if num_locations > 1000:
        print("Large dataset detected (>1000). Using GREEDY_DESCENT for speed.")
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GREEDY_DESCENT)
    else:
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    search_parameters.time_limit.seconds = max_seconds
    
    if status_callback: status_callback("Buscando solución óptima...")
    solution = routing.SolveWithParameters(search_parameters)
    return solution, routing, manager, data, df_loc

def format_solution(data, manager, routing, solution, df_loc):
    """Formats solution into standard structure for display/export"""
    total_duration = 0
    total_load = 0
    
    results = [] 
    route_maps_data = [] # For plotting

    for vehicle_id in range(data['num_vehicles']):
        index = routing.Start(vehicle_id)
        route_duration = 0
        route_load = 0
        route_nodes = []
        route_coords = []
        
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_load += data['demands'][node_index]
            
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            
            # Cost is roughly seconds now
            duration = routing.GetArcCostForVehicle(previous_index, index, vehicle_id)
            route_duration += duration
            
            # Data collection
            # Skip the start node (Depot) in the Excel report to avoid "repeating offices"
            # and to avoid listing vehicles that don't leave the depot.
            # We check previous_index because index has already been updated to NextVar
            if previous_index != routing.Start(vehicle_id):
                loc_name = df_loc.iloc[node_index]['Nombre'] if 'Nombre' in df_loc.columns else f"Loc {node_index}"
                client_name = df_loc.iloc[node_index]['Habla a'] if 'Habla a' in df_loc.columns else ""
                lat = df_loc.iloc[node_index]['Latitud (y)']
                lon = df_loc.iloc[node_index]['Longitud (x)']
                
                # Identify Vehicle Type
                v_type = data['vehicle_types'][vehicle_id]
                
                results.append({
                    'VehicleID': vehicle_id,
                    'VehicleType': v_type,
                    'NodeID': node_index,
                    'LocationName': loc_name,
                    'Client': client_name,
                    'Latitude': lat,
                    'Longitude': lon,
                    'Load': route_load,
                    'OrderInRoute': len(route_nodes), # adjusted index since we skip start
                    'AccumulatedDuration_Mins': int(route_duration / 60)
                })

            route_nodes.append(node_index)
            route_coords.append((df_loc.iloc[node_index]['Latitud (y)'], df_loc.iloc[node_index]['Longitud (x)']))
            
        # Return to depot (visual)
        node_index = manager.IndexToNode(index) 
        lat = df_loc.iloc[node_index]['Latitud (y)']
        lon = df_loc.iloc[node_index]['Longitud (x)']
        route_coords.append((lat, lon))
        
        total_duration += route_duration
        total_load += route_load
        
        route_maps_data.append({
            'vehicle_id': vehicle_id,
            'vehicle_type': data['vehicle_types'][vehicle_id],
            'coords': route_coords,
            'load': route_load,
            'duration_s': route_duration
        })
        
    return results, route_maps_data, total_duration, total_load

def generate_folium_map(df_loc, route_maps_data):
    """Generates Folium map object"""
    center_lat = df_loc.iloc[0]['Latitud (y)']
    center_lon = df_loc.iloc[0]['Longitud (x)']
    m = folium.Map(location=[center_lat, center_lon], zoom_start=6)
    
    colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'lightred', 'beige', 
              'darkblue', 'darkgreen', 'cadetblue', 'darkpurple', 'pink', 'gray', 'black']
    
    # Plot routes
    for r_data in route_maps_data:
        vid = r_data['vehicle_id']
        coords = r_data['coords']
        color = colors[vid % len(colors)]
        
        folium.PolyLine(coords, color=color, weight=3, opacity=0.8).add_to(m)
        
        # Plot markers (except last one which is return to depot, redundant for markers)
        # Actually loop through coordinates to place markers
        for i, (lat, lon) in enumerate(coords[:-1]): 
            # We don't have the node name easily here without re-querying df_loc or passing it down
            # Simplification: Just put a dot
            folium.CircleMarker(
                location=[lat, lon],
                radius=3,
                color=color,
                fill=True,
                fill_color=color,
                popup=f"V{vid}"
            ).add_to(m)

    return m

def solve_vrp_file():
    """Legacy function to run from file as before"""
    print(f"Reading file: {INPUT_FILE}")
    try:
        # Try reading standard sheet name, fallback to 'Hoja1' (common in new files)
        try:
            df_loc = pd.read_excel(INPUT_FILE, sheet_name='1 ubicaciones')
        except:
             print("Sheet '1 ubicaciones' not found. Trying 'Hoja1'...")
             df_loc = pd.read_excel(INPUT_FILE, sheet_name='Hoja1')
        
        df_loc.columns = df_loc.columns.str.strip()
        
        # COLUMN MAPPING (If using Base Arequipa format)
        if 'Lat' in df_loc.columns:
            df_loc.rename(columns={'Lat': 'Latitud (y)', 'Long': 'Longitud (x)', 'gerencia': 'Habla a'}, inplace=True)
        
        # --- LIMPIEZA DE DATOS ---
        print(f"Filas originales: {len(df_loc)}")
        
        # 1. Convertir a numérico forzando errores a NaN
        for col in ['Latitud (y)', 'Longitud (x)']:
            if col in df_loc.columns:
                df_loc[col] = pd.to_numeric(df_loc[col], errors='coerce')
        
        # 2. Eliminar filas con NaN en coordenadas
        valid_rows = df_loc.dropna(subset=['Latitud (y)', 'Longitud (x)'])
        dropped = len(df_loc) - len(valid_rows)
        if dropped > 0:
            print(f"Advertencia: Se eliminaron {dropped} filas con coordenadas inválidas (texto o vacío).")
        df_loc = valid_rows.copy()
        
        # 3. Filtrar coordenadas fuera de rango (Perú aprox: Lat -20 a 0, Lon -82 a -68)
        # Esto ayuda a filtrar errores como -120 o -700
        mask_peru = (
            (df_loc['Latitud (y)'] > -20) & (df_loc['Latitud (y)'] < 0) &
            (df_loc['Longitud (x)'] > -85) & (df_loc['Longitud (x)'] < -65)
        )
        out_of_bounds = df_loc[~mask_peru]
        if not out_of_bounds.empty:
            print(f"Advertencia: Se eliminaron {len(out_of_bounds)} filas con coordenadas fuera de Perú:")
            # print(out_of_bounds[['Nombre', 'Latitud (y)', 'Longitud (x)']].head())
            df_loc = df_loc[mask_peru].copy()

        print(f"Filas válidas para optimizar: {len(df_loc)}")
        # -------------------------
        
            # --- NUEVO REQUERIMIENTO: FIJAR DEPOT EN CENTRO DE AREQUIPA ---
        # Coordenadas: -16.398803, -71.536906
        depot_row = pd.DataFrame([{
            'Nombre': 'Centro de Arequipa',
            'Habla a': 'SODEXO', 
            'Latitud (y)': -16.398803,
            'Longitud (x)': -71.536906,
            'Importe de la entrega': 0,
            'Tickets': 0
        }])
        
        # Concatenar al inicio
        df_loc = pd.concat([depot_row, df_loc], ignore_index=True)
        print("Depot fijado en: Centro de Arequipa (-16.398803, -71.536906)")
        # -------------------------------------------------------------
        
        # vehicles config from file... simplified usage for now or reimplement full read
        # For backward compatibility, I'll attempt to minimally reconstruct the vehicle logic
        # OR just use the new generic solver with defaults if that suffices?
        # The user's original request implies moving AWAY from the hardcoded file, but keeping the CLI working is nice.
        
        # Let's read the vehicles sheet to get count/cap
        # Let's read the vehicles sheet to get count/cap
        try:
            df_veh = pd.read_excel(INPUT_FILE, sheet_name='3.Vehículos')
            df_veh.columns = df_veh.columns.str.strip()
            
            # Simple extraction of total vehicles and max capacity for the generic solver
            total_vehicles = 0
            max_cap = 0
            for _, row in df_veh.iterrows():
                count = int(row.get('Numero de vehiculos', 1))
                cap = int(row.get('Capacidad', 100))
                total_vehicles += count
                max_cap = max(max_cap, cap)
                
            if total_vehicles == 0: total_vehicles = 5
            if max_cap == 0: max_cap = 100
            
        except Exception as e:
            print(f"Warning: Could not read '3.Vehículos' sheet ({e}). Using defaults.")
            total_vehicles = 5
            max_cap = 100
            
        # Legacy mode assumes only cars for simplicity or defaults
        solution, routing, manager, data, df_loc_solved = solve_vrp_data(df_loc, total_vehicles, 0, max_cap)
        
        if solution:
            results, route_data, dist, load = format_solution(data, manager, routing, solution, df_loc_solved)
            
            print(f"Total Distance: {dist}m")
            print(f"Total Load: {load}")
            
            # Save excel
            pd.DataFrame(results).to_excel(OUTPUT_EXCEL, index=False)
            print(f"Saved {OUTPUT_EXCEL}")
            
            # Save map
            m = generate_folium_map(df_loc, route_data)
            m.save(OUTPUT_MAP)
            print(f"Saved {OUTPUT_MAP}")
        else:
            print("No solution found.")
            
    except Exception as e:
        print(f"Error executing legacy mode: {e}")

if __name__ == '__main__':
    solve_vrp_file()
