import pandas as pd
import geopandas as gpd
import chardet
import os
import numpy as np
from shapely.geometry import Point
import logging
import gc
import warnings

# Configurar logging y suprimir warnings
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)

# ==================== CONFIGURACIÓN DE RUTAS CORREGIDA ====================
# Obtener la ruta del directorio actual del script
current_dir = os.path.dirname(__file__)
data_dir = os.path.join(current_dir, "..", "data")

# Rutas relativas para Streamlit Cloud
RUTA_HOSPITALES = os.path.join(data_dir, "IPRESS.csv")
RUTA_SHAPEFILE = os.path.join(data_dir, "shape_file", "DISTRITOS.shp")
RUTA_CCPP = os.path.join(data_dir, "CCPP_0.zip")

def validate_file_paths():
    """Validar que los archivos requeridos existen"""
    files_status = {
        'IPRESS.csv': os.path.exists(RUTA_HOSPITALES),
        'DISTRITOS.shp': os.path.exists(RUTA_SHAPEFILE),
        'CCPP_0.zip': os.path.exists(RUTA_CCPP)
    }
    
    logger.info(f"File validation: {files_status}")
    
    if not files_status['IPRESS.csv']:
        logger.error(f"IPRESS.csv not found at: {RUTA_HOSPITALES}")
    if not files_status['DISTRITOS.shp']:
        logger.error(f"DISTRITOS.shp not found at: {RUTA_SHAPEFILE}")
    if not files_status['CCPP_0.zip']:
        logger.warning(f"CCPP_0.zip not found at: {RUTA_CCPP}")
    
    return files_status

def load_and_clean_hospitals():
    """Cargar y limpiar datos de hospitales con manejo robusto de errores"""
    try:
        if not os.path.exists(RUTA_HOSPITALES):
            logger.error(f"Hospital file not found: {RUTA_HOSPITALES}")
            return None
            
        # Detectar encoding de manera más robusta
        try:
            with open(RUTA_HOSPITALES, 'rb') as f:
                raw_data = f.read(10000)  # Leer solo una muestra
                det = chardet.detect(raw_data)
            charenc = det.get('encoding', 'utf-8')
            logger.info(f"Detected encoding: {charenc}")
        except Exception as e:
            logger.warning(f"Encoding detection failed, using utf-8: {e}")
            charenc = 'utf-8'
        
        # Intentar diferentes encodings si falla
        encodings_to_try = [charenc, 'utf-8', 'latin1', 'cp1252']
        df = None
        
        for encoding in encodings_to_try:
            try:
                df = pd.read_csv(RUTA_HOSPITALES, encoding=encoding)
                logger.info(f"Successfully loaded with encoding: {encoding}")
                break
            except Exception as e:
                logger.warning(f"Failed to load with {encoding}: {e}")
                continue
        
        if df is None:
            logger.error("Failed to load hospitals data with any encoding")
            return None
            
        logger.info(f"Original shape: {df.shape}")
        
        # Verificar columnas requeridas
        required_columns = ['Estado', 'CondiciÛn', 'NORTE', 'ESTE']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            logger.error(f"Missing required columns: {missing_columns}")
            logger.info(f"Available columns: {df.columns.tolist()}")
            return None
        
        # Aplicar filtros
        df_filtered = df[
            (df['Estado'] == 'ACTIVADO') & 
            (df['CondiciÛn'] == 'EN FUNCIONAMIENTO')
        ].copy()
        logger.info(f"After status filter: {df_filtered.shape}")
        
        # Limpiar coordenadas
        df_filtered = df_filtered.dropna(subset=['NORTE', 'ESTE'])
        
        # Filtrar coordenadas válidas (dentro de Perú aproximadamente)
        df_filtered = df_filtered[
            (df_filtered['NORTE'].between(-18.5, 0)) &  # Latitud Perú
            (df_filtered['ESTE'].between(-81.5, -68))   # Longitud Perú
        ]
        logger.info(f"After coordinate cleaning: {df_filtered.shape}")
        
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
        
        # Verificar que las columnas existen antes de seleccionar
        available_columns = [col for col in columnas_seleccionar.keys() if col in df_filtered.columns]
        df_final = df_filtered[available_columns].copy()
        
        # Renombrar solo columnas disponibles
        rename_dict = {col: columnas_seleccionar[col] for col in available_columns}
        df_final.rename(columns=rename_dict, inplace=True)
        
        # Asegurar tipos de datos correctos
        if 'UBIGEO' in df_final.columns:
            df_final['UBIGEO'] = pd.to_numeric(df_final['UBIGEO'], errors='coerce')
            df_final = df_final.dropna(subset=['UBIGEO'])
            df_final['UBIGEO'] = df_final['UBIGEO'].astype(int)
        
        logger.info(f"Final hospitals dataset shape: {df_final.shape}")
        return df_final
        
    except Exception as e:
        logger.error(f"Critical error loading hospitals data: {e}")
        return None

def load_and_process_shapefile():
    """Cargar y procesar shapefile de distritos con manejo robusto de errores"""
    try:
        if not os.path.exists(RUTA_SHAPEFILE):
            logger.error(f"Shapefile not found: {RUTA_SHAPEFILE}")
            return None
            
        # Intentar diferentes métodos de carga
        maps = None
        
        try:
            # Método estándar
            maps = gpd.read_file(RUTA_SHAPEFILE)
            logger.info("Shapefile loaded with standard method")
        except Exception as e1:
            logger.warning(f"Standard method failed: {e1}")
            try:
                # Método alternativo usando fiona directamente
                import fiona
                with fiona.open(RUTA_SHAPEFILE) as src:
                    maps = gpd.GeoDataFrame.from_features(src, crs=src.crs)
                logger.info("Shapefile loaded with fiona method")
            except Exception as e2:
                logger.error(f"All shapefile loading methods failed: {e1}, {e2}")
                return None
        
        if maps is None or len(maps) == 0:
            logger.error("Empty shapefile loaded")
            return None
        
        logger.info(f"Shapefile loaded with shape: {maps.shape}")
        
        # Verificar columnas requeridas
        if 'IDDIST' not in maps.columns and 'UBIGEO' not in maps.columns:
            logger.error(f"Required ID column not found. Available: {maps.columns.tolist()}")
            return None
        
        # Seleccionar y renombrar columnas
        if 'IDDIST' in maps.columns:
            maps = maps[['IDDIST', 'DISTRITO', 'geometry']].copy()
            maps.rename(columns={'IDDIST': 'UBIGEO'}, inplace=True)
        else:
            maps = maps[['UBIGEO', 'DISTRITO', 'geometry']].copy()
        
        # Convertir UBIGEO a entero
        maps['UBIGEO'] = pd.to_numeric(maps['UBIGEO'], errors='coerce')
        maps = maps.dropna(subset=['UBIGEO'])
        maps['UBIGEO'] = maps['UBIGEO'].astype(int)
        
        # Asegurar CRS correcto
        if maps.crs is None:
            maps.set_crs('EPSG:4326', inplace=True)
        else:
            maps = maps.to_crs(epsg=4326)
        
        # Verificar geometrías válidas
        valid_geom = maps.geometry.is_valid
        if not valid_geom.all():
            logger.warning(f"Found {(~valid_geom).sum()} invalid geometries, fixing...")
            maps.geometry = maps.geometry.buffer(0)
        
        logger.info(f"Processed shapefile shape: {maps.shape}")
        return maps
        
    except Exception as e:
        logger.error(f"Critical error loading shapefile: {e}")
        return None

def merge_hospitals_with_shapefile(hospitals_df, maps_gdf):
    """Merge de hospitales con shapefile por UBIGEO con validación"""
    try:
        if hospitals_df is None or maps_gdf is None:
            logger.error("Cannot merge: one of the dataframes is None")
            return None
        
        if 'UBIGEO' not in hospitals_df.columns or 'UBIGEO' not in maps_gdf.columns:
            logger.error("UBIGEO column missing for merge")
            return None
        
        logger.info(f"Merging hospitals ({len(hospitals_df)}) with maps ({len(maps_gdf)})")
        
        # Verificar tipos de UBIGEO
        hospitals_df['UBIGEO'] = hospitals_df['UBIGEO'].astype(int)
        maps_gdf['UBIGEO'] = maps_gdf['UBIGEO'].astype(int)
        
        dataset_cv = pd.merge(maps_gdf, hospitals_df, how="inner", on="UBIGEO")
        
        logger.info(f"Merge completed: {dataset_cv.shape[0]} registros")
        
        if len(dataset_cv) == 0:
            logger.warning("Merge resulted in empty dataset")
            return None
            
        return dataset_cv
        
    except Exception as e:
        logger.error(f"Error in merge: {e}")
        return None

def calculate_hospital_counts(dataset_cv, maps_gdf):
    """Calcular conteo de hospitales por distrito con validación"""
    try:
        if dataset_cv is None or maps_gdf is None:
            logger.error("Cannot calculate counts: datasets are None")
            return None
        
        hospital_count = dataset_cv.groupby('UBIGEO').size().reset_index(name='num_hospitales')
        map_data = maps_gdf.merge(hospital_count, on='UBIGEO', how='left')
        map_data['num_hospitales'] = map_data['num_hospitales'].fillna(0).astype(int)
        
        logger.info(f"Hospital counts calculated: {len(map_data)} districts")
        logger.info(f"Districts with hospitals: {(map_data['num_hospitales'] > 0).sum()}")
        logger.info(f"Districts without hospitals: {(map_data['num_hospitales'] == 0).sum()}")
        
        return map_data
        
    except Exception as e:
        logger.error(f"Error calculating hospital counts: {e}")
        return None

def calculate_department_stats(dataset_cv):
    """Calcular estadísticas por departamento con validación"""
    try:
        if dataset_cv is None:
            logger.error("Cannot calculate department stats: dataset is None")
            return None
        
        if 'DEPARTAMENTO' not in dataset_cv.columns:
            logger.error("DEPARTAMENTO column not found")
            return None
        
        dept_hospitals = dataset_cv.groupby('DEPARTAMENTO').size().reset_index(name='total_hospitals')
        dept_hospitals = dept_hospitals.sort_values('total_hospitals', ascending=False)
        
        logger.info(f"Department stats calculated: {len(dept_hospitals)} departments")
        
        return dept_hospitals
        
    except Exception as e:
        logger.error(f"Error calculating department stats: {e}")
        return None

def load_and_process_ccpp():
    """Cargar y procesar centros poblados (opcional)"""
    try:
        if not os.path.exists(RUTA_CCPP):
            logger.warning(f"CCPP file not found: {RUTA_CCPP}")
            return None
            
        # Intentar múltiples métodos de carga
        ccpp = None
        
        try:
            # Método ZIP
            ccpp = gpd.read_file(f"zip://{RUTA_CCPP}")
            logger.info("CCPP loaded with zip method")
        except Exception as e1:
            logger.warning(f"Zip method failed: {e1}")
            try:
                # Método directo
                ccpp = gpd.read_file(RUTA_CCPP)
                logger.info("CCPP loaded with direct method")
            except Exception as e2:
                logger.warning(f"All CCPP loading methods failed: {e1}, {e2}")
                return None
        
        if ccpp is None or len(ccpp) == 0:
            logger.warning("Empty CCPP dataset")
            return None
        
        logger.info(f"CCPP original shape: {ccpp.shape}")
        logger.info(f"CCPP columns: {ccpp.columns.tolist()}")
        
        # Mapear columnas dinámicamente
        column_mapping = {}
        for col in ccpp.columns:
            col_upper = col.upper()
            if any(keyword in col_upper for keyword in ['POBLAD', 'NOMBCCPP', 'CENTRO']):
                column_mapping[col] = 'NOMBCCPP'
            elif any(keyword in col_upper for keyword in ['DEP', 'DEPARTAMENTO']):
                column_mapping[col] = 'NOMBDEP'
            elif any(keyword in col_upper for keyword in ['PROV', 'PROVINCIA']):
                column_mapping[col] = 'NOMBPROV'
            elif any(keyword in col_upper for keyword in ['DIST', 'DISTRITO']):
                column_mapping[col] = 'NOMBDIST'
            elif any(keyword in col_upper for keyword in ['ID', 'CODIGO', 'COD']):
                column_mapping[col] = 'IDCCPP'
        
        # Renombrar columnas disponibles
        available_mapping = {k: v for k, v in column_mapping.items() if k in ccpp.columns}
        if available_mapping:
            ccpp.rename(columns=available_mapping, inplace=True)
        
        # Limpiar geometrías
        ccpp = ccpp[ccpp.geometry.is_valid]
        
        # Convertir CRS
        if ccpp.crs is None:
            ccpp.set_crs('EPSG:4326', inplace=True)
        else:
            ccpp = ccpp.to_crs('EPSG:4326')
        
        # Remover duplicados si hay columna ID
        if 'IDCCPP' in ccpp.columns:
            ccpp = ccpp.drop_duplicates(subset=['IDCCPP'])
        
        logger.info(f"CCPP processed shape: {ccpp.shape}")
        return ccpp
        
    except Exception as e:
        logger.warning(f"Error loading CCPP (non-critical): {e}")
        return None

def analyze_proximity(ccpp_gdf, hospitals_gdf, department_name):
    """Analizar proximidad para un departamento específico (opcional)"""
    try:
        if ccpp_gdf is None:
            logger.info(f"CCPP data not available for {department_name}")
            return None, None, None
            
        if 'NOMBDEP' not in ccpp_gdf.columns:
            logger.warning(f"NOMBDEP column not found in CCPP for {department_name}")
            return None, None, None
            
        # Filtrar por departamento
        department_ccpp = ccpp_gdf[
            ccpp_gdf['NOMBDEP'].str.upper() == department_name.upper()
        ].copy()
        
        if len(department_ccpp) == 0:
            logger.info(f"No CCPP data found for department: {department_name}")
            return None, None, None
        
        logger.info(f"Processing {len(department_ccpp)} centers for {department_name}")
        
        # Crear buffers de 10km usando proyección métrica
        def create_buffer_safe(gdf):
            try:
                # Usar proyección UTM apropiada para Perú
                gdf_metric = gdf.to_crs('EPSG:32718')  # UTM 18S
                gdf_metric['buffer_10km'] = gdf_metric.geometry.buffer(10000)
                gdf['buffer_10km'] = gdf_metric['buffer_10km'].to_crs('EPSG:4326')
                return gdf
            except Exception as e:
                logger.error(f"Error creating buffer: {e}")
                return gdf
        
        department_ccpp = create_buffer_safe(department_ccpp)
        
        if 'buffer_10km' not in department_ccpp.columns:
            logger.error(f"Failed to create buffers for {department_name}")
            return None, None, None
        
        # Contar hospitales en buffers
        def count_hospitals_safe(row, hospitals_gdf):
            try:
                return len(hospitals_gdf[hospitals_gdf.geometry.within(row['buffer_10km'])])
            except Exception:
                return 0
        
        department_ccpp['hospitals_in_10km'] = department_ccpp.apply(
            count_hospitals_safe, args=(hospitals_gdf,), axis=1
        )
        
        # Encontrar centros extremos
        if len(department_ccpp) > 0:
            min_idx = department_ccpp['hospitals_in_10km'].idxmin()
            max_idx = department_ccpp['hospitals_in_10km'].idxmax()
            
            most_isolated = department_ccpp.loc[min_idx]
            most_concentrated = department_ccpp.loc[max_idx]
            
            logger.info(f"{department_name} - Most isolated: {most_isolated['hospitals_in_10km']} hospitals")
            logger.info(f"{department_name} - Most concentrated: {most_concentrated['hospitals_in_10km']} hospitals")
            
            return most_isolated, most_concentrated, department_ccpp
        else:
            return None, None, None
            
    except Exception as e:
        logger.error(f"Error in proximity analysis for {department_name}: {e}")
        return None, None, None

def load_all_data():
    """Cargar y procesar todos los datos con manejo robusto de errores"""
    try:
        logger.info("Starting data loading process...")
        
        # Validar archivos
        file_status = validate_file_paths()
        if not file_status['IPRESS.csv'] or not file_status['DISTRITOS.shp']:
            logger.error("Critical files missing")
            return None
        
        # Cargar datos de hospitales
        logger.info("Loading hospital data...")
        hospitals = load_and_clean_hospitals()
        if hospitals is None:
            logger.error("Failed to load hospital data")
            return None
        
        # Cargar shapefile
        logger.info("Loading shapefile...")
        maps = load_and_process_shapefile()
        if maps is None:
            logger.error("Failed to load shapefile")
            return None
        
        # Merge datos
        logger.info("Merging data...")
        dataset_cv = merge_hospitals_with_shapefile(hospitals, maps)
        if dataset_cv is None:
            logger.error("Failed to merge data")
            return None
        
        # Calcular conteos
        logger.info("Calculating hospital counts...")
        map_data = calculate_hospital_counts(dataset_cv, maps)
        if map_data is None:
            logger.error("Failed to calculate hospital counts")
            return None
        
        # Estadísticas departamentales
        logger.info("Calculating department stats...")
        dept_stats = calculate_department_stats(dataset_cv)
        if dept_stats is None:
            logger.error("Failed to calculate department stats")
            return None
        
        # Cargar CCPP (opcional)
        logger.info("Loading population centers...")
        ccpp = load_and_process_ccpp()
        
        # Crear GeoDataFrame de hospitales
        logger.info("Creating hospital GeoDataFrame...")
        try:
            gdf_hospitales = gpd.GeoDataFrame(
                dataset_cv, 
                geometry=gpd.points_from_xy(dataset_cv.LONGITUD, dataset_cv.LATITUD),
                crs="EPSG:4326"
            )
        except Exception as e:
            logger.error(f"Error creating hospital GeoDataFrame: {e}")
            return None
        
        # Análisis de proximidad (opcional)
        lima_analysis = (None, None, None)
        loreto_analysis = (None, None, None)
        
        if ccpp is not None:
            logger.info("Analyzing proximity for Lima...")
            lima_analysis = analyze_proximity(ccpp, gdf_hospitales, "LIMA")
            
            logger.info("Analyzing proximity for Loreto...")
            loreto_analysis = analyze_proximity(ccpp, gdf_hospitales, "LORETO")
        else:
            logger.info("Skipping proximity analysis due to missing CCPP data")
        
        # Limpiar memoria
        gc.collect()
        
        result = {
            'hospitals': hospitals,
            'maps': maps,
            'dataset_cv': dataset_cv,
            'map_data': map_data,
            'dept_stats': dept_stats,
            'gdf_hospitales': gdf_hospitales,
            'lima_analysis': lima_analysis,
            'loreto_analysis': loreto_analysis
        }
        
        logger.info("Data loading completed successfully!")
        logger.info(f"Final dataset sizes:")
        logger.info(f"  - Hospitals: {len(hospitals)}")
        logger.info(f"  - Districts: {len(maps)}")
        logger.info(f"  - Merged data: {len(dataset_cv)}")
        logger.info(f"  - Departments: {len(dept_stats)}")
        
        return result
        
    except Exception as e:
        logger.error(f"Critical error in load_all_data: {e}")
        return None