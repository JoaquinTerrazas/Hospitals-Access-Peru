import pandas as pd
import geopandas as gpd
import chardet
import os
import numpy as np
from shapely.geometry import Point

# ==================== CONFIGURACIÓN DE RUTAS ====================
# Obtener la ruta del directorio actual del script
current_dir = os.path.dirname(__file__)
data_dir = os.path.join(current_dir, "..", "data")

# Rutas relativas para Streamlit Cloud
RUTA_HOSPITALES = os.path.join(data_dir, "IPRESS.csv")
RUTA_SHAPEFILE = os.path.join(data_dir, "shape_file", "DISTRITOS.shp")
RUTA_CCPP = os.path.join(data_dir, "CCPP_0.zip")


def load_and_clean_hospitals():
    """Cargar y limpiar datos de hospitales - Filtros: ACTIVADO + EN FUNCIONAMIENTO + coordenadas válidas"""
    try:
        # Detectar encoding
        with open(RUTA_HOSPITALES, 'rb') as f:
            det = chardet.detect(f.read())
        charenc = det['encoding']
        
        df = pd.read_csv(RUTA_HOSPITALES, encoding=charenc)
        print(f"Forma original: {df.shape}")
        
        # Aplicar filtros
        df_filtered = df[(df['Estado'] == 'ACTIVADO') & 
                        (df['CondiciÛn'] == 'EN FUNCIONAMIENTO')].copy()
        print(f"Después de filtro Estado=ACTIVADO y Condición=EN FUNCIONAMIENTO: {df_filtered.shape}")
        
        df_filtered = df_filtered.dropna(subset=['NORTE', 'ESTE'])
        print(f"Después de eliminar NaN en NORTE y ESTE: {df_filtered.shape}")
        
        # Renombrar columnas
        columnas_seleccionar = {
            'CÛdigo ⁄nico': 'CODIGO_IPRESS',
            'Nombre del establecimiento': 'NOMBRE', 
            'UBIGEO': 'UBIGEO',
            'NORTE': 'LONGITUD',
            'ESTE': 'LATITUD',
            'Departamento': 'DEPARTAMENTO',
            'Estado': 'ESTADO'
        }
        
        df_final = df_filtered[list(columnas_seleccionar.keys())].copy()
        df_final.rename(columns=columnas_seleccionar, inplace=True)
        
        return df_final
        
    except Exception as e:
        print(f"Error loading hospitals data: {e}")
        return None

def load_and_process_shapefile():
    """Cargar y procesar shapefile de distritos"""
    try:
        maps = gpd.read_file(RUTA_SHAPEFILE)
        maps = maps[['IDDIST', 'DISTRITO', 'geometry']]
        maps = maps.rename(columns={'IDDIST': 'UBIGEO'})
        maps['UBIGEO'] = maps['UBIGEO'].astype(str).astype(int)
        maps = maps.to_crs(epsg=4326)
        return maps
    except Exception as e:
        print(f"Error loading shapefile: {e}")
        return None

def merge_hospitals_with_shapefile(hospitals_df, maps_gdf):
    """Merge de hospitales con shapefile por UBIGEO"""
    try:
        dataset_cv = pd.merge(maps_gdf, hospitals_df, how="inner", on="UBIGEO")
        print(f"Merge completado: {dataset_cv.shape[0]} registros")
        return dataset_cv
    except Exception as e:
        print(f"Error in merge: {e}")
        return None

def calculate_hospital_counts(dataset_cv, maps_gdf):
    """Calcular conteo de hospitales por distrito"""
    try:
        hospital_count = dataset_cv.groupby('UBIGEO').size().reset_index(name='num_hospitales')
        map_data = maps_gdf.merge(hospital_count, on='UBIGEO', how='left')
        map_data['num_hospitales'] = map_data['num_hospitales'].fillna(0)
        return map_data
    except Exception as e:
        print(f"Error calculating hospital counts: {e}")
        return None

def calculate_department_stats(dataset_cv):
    """Calcular estadísticas por departamento"""
    try:
        dept_hospitals = dataset_cv.groupby('DEPARTAMENTO').size().reset_index(name='total_hospitals')
        dept_hospitals = dept_hospitals.sort_values('total_hospitals', ascending=False)
        return dept_hospitals
    except Exception as e:
        print(f"Error calculating department stats: {e}")
        return None

def load_and_process_ccpp():
    """Cargar y procesar centros poblados"""
    try:
        if not os.path.exists(RUTA_CCPP):
            print(f"Warning: CCPP file not found at {RUTA_CCPP}")
            return None
            
        # Leer archivo ZIP correctamente para Streamlit Cloud
        ccpp = gpd.read_file(f"zip://{RUTA_CCPP}")
        
        # Verificar columnas disponibles
        print("Columnas CCPP disponibles:", ccpp.columns.tolist())
        
        # Mapear columnas disponibles
        column_mapping = {}
        for col in ccpp.columns:
            if 'POBLAD' in col or 'poblad' in col:
                column_mapping[col] = 'NOMBCCPP'
            elif col == 'DEP' or 'departamento' in col.lower():
                column_mapping[col] = 'NOMBDEP'
            elif col == 'PROV' or 'provincia' in col.lower():
                column_mapping[col] = 'NOMBPROV'
            elif col == 'DIST' or 'distrito' in col.lower():
                column_mapping[col] = 'NOMBDIST'
            elif 'DIGO' in col or 'codigo' in col.lower():
                column_mapping[col] = 'IDCCPP'
        
        # Verificar duplicados solo si la columna de código existe
        codigo_col = next((col for col in ccpp.columns if col in column_mapping and column_mapping[col] == 'IDCCPP'), None)
        if codigo_col:
            ccpp = ccpp.drop_duplicates(subset=[codigo_col])
        
        ccpp = ccpp[ccpp.is_valid]
        
        # Renombrar columnas disponibles
        available_cols = [col for col in ccpp.columns if col in column_mapping]
        if available_cols:
            ccpp = ccpp.rename(columns={col: column_mapping[col] for col in available_cols})
        
        return ccpp
        
    except Exception as e:
        print(f"Error loading CCPP: {e}")
        return None

def analyze_proximity(ccpp_gdf, hospitals_gdf, department_name):
    """Analizar proximidad para un departamento específico"""
    try:
        # Filtrar por departamento
        department_ccpp = ccpp_gdf[ccpp_gdf['NOMBDEP'] == department_name.upper()].copy()
        department_ccpp = department_ccpp.to_crs(epsg=4326)
        
        # Crear buffers de 10km
        def create_10km_buffer_simple(gdf):
            gdf_metric = gdf.to_crs(epsg=32718)
            gdf_metric['buffer_10km'] = gdf_metric.geometry.buffer(10000)
            gdf['buffer_10km'] = gdf_metric['buffer_10km'].to_crs(epsg=4326)
            return gdf
        
        department_ccpp = create_10km_buffer_simple(department_ccpp)
        
        # Contar hospitales en buffers
        def count_hospitals_in_buffer(row, hospitals_gdf):
            return len(hospitals_gdf[hospitals_gdf.geometry.within(row['buffer_10km'])])
        
        department_ccpp['hospitals_in_10km'] = department_ccpp.apply(
            count_hospitals_in_buffer, args=(hospitals_gdf,), axis=1
        )
        
        # Encontrar centros extremos
        if len(department_ccpp) > 0:
            most_isolated = department_ccpp.loc[department_ccpp['hospitals_in_10km'].idxmin()]
            most_concentrated = department_ccpp.loc[department_ccpp['hospitals_in_10km'].idxmax()]
            return most_isolated, most_concentrated, department_ccpp
        else:
            return None, None, None
            
    except Exception as e:
        print(f"Error in proximity analysis for {department_name}: {e}")
        return None, None, None

# Función principal para cargar todos los datos
def load_all_data():
    """Cargar y procesar todos los datos"""
    print("Loading hospital data...")
    hospitals = load_and_clean_hospitals()
    if hospitals is None:
        return None
    
    print("Loading shapefile...")
    maps = load_and_process_shapefile()
    if maps is None:
        return None
    
    print("Merging data...")
    dataset_cv = merge_hospitals_with_shapefile(hospitals, maps)
    if dataset_cv is None:
        return None
    
    print("Calculating hospital counts...")
    map_data = calculate_hospital_counts(dataset_cv, maps)
    if map_data is None:
        return None
    
    print("Calculating department stats...")
    dept_stats = calculate_department_stats(dataset_cv)
    if dept_stats is None:
        return None
    
    print("Loading population centers...")
    ccpp = load_and_process_ccpp()
    
    # Crear GeoDataFrame de hospitales para análisis espacial
    gdf_hospitales = gpd.GeoDataFrame(
        dataset_cv, 
        geometry=gpd.points_from_xy(dataset_cv.LONGITUD, dataset_cv.LATITUD),
        crs="EPSG:4326"
    )
    
    print("Analyzing proximity for Lima...")
    lima_isolated, lima_concentrated, lima_ccpp = analyze_proximity(ccpp, gdf_hospitales, "LIMA") if ccpp is not None else (None, None, None)
    
    print("Analyzing proximity for Loreto...")
    loreto_isolated, loreto_concentrated, loreto_ccpp = analyze_proximity(ccpp, gdf_hospitales, "LORETO") if ccpp is not None else (None, None, None)
    
    return {
        'hospitals': hospitals,
        'maps': maps,
        'dataset_cv': dataset_cv,
        'map_data': map_data,
        'dept_stats': dept_stats,
        'gdf_hospitales': gdf_hospitales,
        'lima_analysis': (lima_isolated, lima_concentrated, lima_ccpp),
        'loreto_analysis': (loreto_isolated, loreto_concentrated, loreto_ccpp)
    }