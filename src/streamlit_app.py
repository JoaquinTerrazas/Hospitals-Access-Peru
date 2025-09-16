import streamlit as st

# CONFIGURACIÓN DE PÁGINA DEBE SER LO PRIMERO
st.set_page_config(
    page_title="Hospital Access Peru Analysis",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ahora las importaciones restantes
import pandas as pd
import matplotlib.pyplot as plt
import folium
import tempfile
import os
import sys
import gc
import logging
import time
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== CORRECCIÓN DE IMPORTACIONES ====================
# Agregar la carpeta src al path para importaciones correctas
current_dir = os.path.dirname(__file__)
sys.path.insert(0, current_dir)

# Importar módulos después de configurar el path
try:
    from estimation import load_all_data
    from plot import generate_all_visualizations, cleanup_matplotlib_figures
except ImportError as e:
    st.error(f"Error importing modules: {e}")
    st.stop()

def show_folium_map(folium_map, width=700, height=500):
    """Mostrar mapa Folium de manera estable usando archivos temporales"""
    if folium_map is None:
        st.warning("Mapa no disponible")
        return
    
    temp_file = None
    try:
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8') as f:
            folium_map.save(f.name)
            temp_file = f.name
        
        # Leer y mostrar el HTML
        with open(temp_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Mostrar como componente
        st.components.v1.html(html_content, width=width, height=height, scrolling=True)
        
    except Exception as e:
        st.error(f"Error mostrando mapa: {e}")
        logger.error(f"Error in show_folium_map: {e}")
    finally:
        # Limpiar archivo temporal
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except Exception:
                pass

def display_health_check():
    """Mostrar indicadores de salud de la aplicación"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.sidebar.markdown(f"**Última actualización:** {current_time}")
    
    # Verificar memoria
    try:
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        st.sidebar.metric("Memoria (MB)", f"{memory_mb:.1f}")
    except:
        pass

# Título principal
st.title("🏥 Análisis de Acceso a Hospitales en Perú")
st.markdown("---")

# Health check
display_health_check()

# Cargar datos (solo cache para datos, no para visualizaciones)
@st.cache_data(show_spinner="Cargando datos...", ttl=3600)  # Cache por 1 hora
def load_cached_data():
    """Cargar datos con manejo robusto de errores"""
    try:
        logger.info("Loading data...")
        data = load_all_data()
        if data is None:
            logger.error("load_all_data returned None")
            return None
        
        logger.info(f"Data loaded successfully. Dataset shape: {data.get('dataset_cv', pd.DataFrame()).shape}")
        return data
    except Exception as e:
        logger.error(f"Error in load_cached_data: {e}")
        st.error(f"Error loading data: {e}")
        return None

def generate_visualizations_safe(data_dict, vis_type="all"):
    """Generar visualizaciones de manera segura con control de memoria"""
    try:
        if vis_type == "static":
            # Solo mapas estáticos y gráficos
            from plot import create_static_maps, create_department_bar_chart
            return {
                'static_maps': create_static_maps(data_dict['map_data']),
                'bar_chart': create_department_bar_chart(data_dict['dept_stats']),
            }
        elif vis_type == "dynamic":
            # Solo mapas dinámicos
            from plot import create_national_folium_map, create_proximity_maps
            return {
                'national_map': create_national_folium_map(data_dict['map_data'], data_dict['dataset_cv']),
                'proximity_maps': create_proximity_maps(
                    data_dict['lima_analysis'], 
                    data_dict['loreto_analysis'], 
                    data_dict['gdf_hospitales']
                )
            }
        else:
            # Todas las visualizaciones
            return generate_all_visualizations(data_dict)
            
    except Exception as e:
        logger.error(f"Error generating visualizations: {e}")
        st.error(f"Error generating visualizations: {e}")
        return None

# Cargar datos
with st.spinner("Inicializando aplicación..."):
    data_dict = load_cached_data()

# Verificar que los datos se cargaron correctamente
if data_dict is None or data_dict.get('dataset_cv') is None:
    st.error("❌ Error al cargar los datos. Por favor verifica las rutas de los archivos.")
    st.info("Verifica que los archivos estén en las rutas correctas:")
    st.code("""
    data/
    ├── IPRESS.csv
    ├── CCPP_0.zip  
    └── shape_file/
        └── DISTRITOS.shp
    """)
    st.stop()

st.success("✅ Datos cargados correctamente")

# Crear pestañas
tab1, tab2, tab3 = st.tabs([
    "🗂️ Data Description", 
    "🗺️ Static Maps & Department Analysis", 
    "🌍 Dynamic Maps"
])

with tab1:
    st.header("Descripción de Datos y Metodología")
    
    # Unit of analysis
    st.subheader("Unidad de Análisis")
    st.write("Hospitales públicos operativos en Perú según datos oficiales del MINSA")
    
    # Data sources
    st.subheader("Fuentes de Datos")
    st.write("- **MINSA – IPRESS**: Subconjunto operacional de establecimientos de salud")
    st.write("- **Centros Poblados**: Datos geográficos de localidades")
    st.write("- **Shapefiles**: Límites distritales del Perú")
    
    # Filtering rules
    st.subheader("Reglas de Filtrado")
    st.write("✅ **Estado operativo**: Estado = 'ACTIVADO'")
    st.write("✅ **Condición funcional**: Condición = 'EN FUNCIONAMIENTO'")
    st.write("✅ **Coordenadas válidas**: Latitud y longitud no nulas")
    st.write("✅ **Georreferenciación**: Merge válido con shapefile por UBIGEO")
    
    # Métricas clave
    st.subheader("Métricas Clave")
    
    try:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_hospitals = len(data_dict['dataset_cv'])
            st.metric("Total Hospitales", total_hospitals)
        
        with col2:
            total_departments = data_dict['dept_stats']['DEPARTAMENTO'].nunique()
            st.metric("Departamentos", total_departments)
        
        with col3:
            total_districts = data_dict['map_data']['UBIGEO'].nunique()
            st.metric("Distritos", total_districts)
        
        with col4:
            zero_hospitals = (data_dict['map_data']['num_hospitales'] == 0).sum()
            st.metric("Distritos sin Hospitales", zero_hospitals)
    except Exception as e:
        st.error(f"Error displaying metrics: {e}")
        logger.error(f"Error in metrics display: {e}")
    
    # Mostrar sample de datos
    st.subheader("Muestra de Datos de Hospitales")
    try:
        sample_data = data_dict['dataset_cv'][['NOMBRE', 'DEPARTAMENTO', 'LATITUD', 'LONGITUD']].head(10)
        st.dataframe(sample_data, use_container_width=True)
    except Exception as e:
        st.error(f"Error displaying data sample: {e}")
        logger.error(f"Error in data sample display: {e}")

with tab2:
    st.header("Mapas Estáticos y Análisis Departamental")
    
    # Limpiar visualizaciones previas si existen
    if hasattr(st.session_state, 'tab2_visualizations'):
        cleanup_matplotlib_figures(st.session_state.tab2_visualizations)
        del st.session_state.tab2_visualizations
        gc.collect()
    
    # Generar solo visualizaciones estáticas
    with st.spinner("Generando mapas estáticos..."):
        try:
            static_visualizations = generate_visualizations_safe(data_dict, vis_type="static")
            st.session_state.tab2_visualizations = static_visualizations
        except Exception as e:
            st.error(f"Error generando visualizaciones estáticas: {e}")
            logger.error(f"Error in static visualizations: {e}")
            static_visualizations = None
    
    visualizations = st.session_state.get('tab2_visualizations')
    
    # Mapas estáticos
    st.subheader("Mapas de Distribución de Hospitales")
    
    if visualizations and visualizations.get('static_maps'):
        try:
            col1, col2 = st.columns(2)
            
            with col1:
                if 'map1_hospitales_distrito' in visualizations['static_maps']:
                    st.pyplot(visualizations['static_maps']['map1_hospitales_distrito'], 
                             use_container_width=True)
                    st.caption("Mapa 1: Hospitales por Distrito")
                else:
                    st.warning("Mapa 1 no disponible")
            
            with col2:
                if 'map2_distritos_sin_hospitales' in visualizations['static_maps']:
                    st.pyplot(visualizations['static_maps']['map2_distritos_sin_hospitales'], 
                             use_container_width=True)
                    st.caption("Mapa 2: Distritos sin Hospitales")
                else:
                    st.warning("Mapa 2 no disponible")
            
            if 'map3_top10_distritos' in visualizations['static_maps']:
                st.pyplot(visualizations['static_maps']['map3_top10_distritos'], 
                         use_container_width=True)
                st.caption("Mapa 3: Top 10 Distritos con Más Hospitales")
            else:
                st.warning("Mapa 3 no disponible")
                
        except Exception as e:
            st.error(f"Error displaying static maps: {e}")
            logger.error(f"Error displaying static maps: {e}")
    else:
        st.error("Error generando mapas estáticos")
    
    # Análisis departamental
    st.subheader("Análisis por Departamento")
    
    try:
        # Tabla resumen
        st.write("**Tabla Resumen - Hospitales por Departamento**")
        st.dataframe(data_dict['dept_stats'].sort_values('total_hospitals', ascending=False),
                    use_container_width=True)
        
        # Gráfico de barras
        st.write("**Gráfico de Barras - Distribución por Departamento**")
        if visualizations and visualizations.get('bar_chart'):
            st.pyplot(visualizations['bar_chart'], use_container_width=True)
        else:
            st.error("Error generando gráfico de barras")
        
        # Estadísticas departamentales
        st.subheader("Estadísticas Clave")
        highest_dept = data_dict['dept_stats'].iloc[0]
        lowest_dept = data_dict['dept_stats'].iloc[-1]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.info(f"**Departamento con más hospitales**: {highest_dept['DEPARTAMENTO']} ({highest_dept['total_hospitals']} hospitales)")
        
        with col2:
            st.warning(f"**Departamento con menos hospitales**: {lowest_dept['DEPARTAMENTO']} ({lowest_dept['total_hospitals']} hospitales)")
            
    except Exception as e:
        st.error(f"Error in department analysis: {e}")
        logger.error(f"Error in department analysis: {e}")

with tab3:
    st.header("Mapas Interactivos Dinámicos")
    
    # Limpiar visualizaciones previas si existen
    if hasattr(st.session_state, 'tab3_visualizations'):
        del st.session_state.tab3_visualizations
        gc.collect()
    
    # Generar solo visualizaciones dinámicas
    with st.spinner("Generando mapas interactivos..."):
        try:
            dynamic_visualizations = generate_visualizations_safe(data_dict, vis_type="dynamic")
            st.session_state.tab3_visualizations = dynamic_visualizations
        except Exception as e:
            st.error(f"Error generando visualizaciones dinámicas: {e}")
            logger.error(f"Error in dynamic visualizations: {e}")
            dynamic_visualizations = None

    visualizations = st.session_state.get('tab3_visualizations')
    
    # Mapa nacional
    st.subheader("Mapa Nacional - Hospitales por Distrito")
    
    if visualizations and visualizations.get('national_map'):
        show_folium_map(visualizations['national_map'], width=700, height=500)
    else:
        st.error("Error generando mapa nacional")
    
    # Mapas de proximidad
    st.subheader("Análisis de Proximidad - Lima y Loreto")
    
    st.write("""
    **Leyenda:**
    - 🔴 Círculo Rojo: Centro poblado con menor densidad hospitalaria (aislado)
    - 🟢 Círculo Verde: Centro poblado con mayor densidad hospitalaria (concentrado)
    - 🟢 Marcadores Verdes: Hospitales dentro del radio de 10km
    """)
    
    try:
        # Lima
        st.write("### 🏙️ Lima - Concentración Urbana y Accesibilidad")
        if visualizations and visualizations.get('proximity_maps'):
            col1, col2 = st.columns(2)
            
            with col1:
                if 'lima_aislado' in visualizations['proximity_maps'] and visualizations['proximity_maps']['lima_aislado']:
                    show_folium_map(visualizations['proximity_maps']['lima_aislado'], width=350, height=400)
                    st.caption("Lima: Centro más aislado (menos hospitales en 10km)")
                else:
                    st.warning("Mapa de Lima aislado no disponible")
            
            with col2:
                if 'lima_concentrado' in visualizations['proximity_maps'] and visualizations['proximity_maps']['lima_concentrado']:
                    show_folium_map(visualizations['proximity_maps']['lima_concentrado'], width=350, height=400)
                    st.caption("Lima: Centro más concentrado (más hospitales en 10km)")
                else:
                    st.warning("Mapa de Lima concentrado no disponible")
        else:
            st.error("Error generando mapas de proximidad para Lima")
        
        # Loreto
        st.write("### 🌳 Loreto - Dispersión Geográfica y Desafíos Amazónicos")
        if visualizations and visualizations.get('proximity_maps'):
            col1, col2 = st.columns(2)
            
            with col1:
                if 'loreto_aislado' in visualizations['proximity_maps'] and visualizations['proximity_maps']['loreto_aislado']:
                    show_folium_map(visualizations['proximity_maps']['loreto_aislado'], width=350, height=400)
                    st.caption("Loreto: Centro más aislado (menos hospitales en 10km)")
                else:
                    st.warning("Mapa de Loreto aislado no disponible")
            
            with col2:
                if 'loreto_concentrado' in visualizations['proximity_maps'] and visualizations['proximity_maps']['loreto_concentrado']:
                    show_folium_map(visualizations['proximity_maps']['loreto_concentrado'], width=350, height=400)
                    st.caption("Loreto: Centro más concentrado (más hospitales en 10km)")
                else:
                    st.warning("Mapa de Loreto concentrado no disponible")
        
        # Análisis breve
        st.subheader("Análisis Comparativo")
        st.write("""
        **Lima**: Muestra patrones de concentración urbana con mejor accesibilidad a servicios de salud 
        en áreas metropolitanas, típico de entornos urbanos densos.
        
        **Loreto**: Evidencia los desafíos de dispersión geográfica característicos de la Amazonía, 
        con mayores distancias entre centros de salud y poblaciones, reflejando la necesidad de 
        estrategias de salud móvil o itinerante.
        """)
        
    except Exception as e:
        st.error(f"Error in proximity maps: {e}")
        logger.error(f"Error in proximity maps: {e}")

# Footer
st.markdown("---")
st.caption("© 2024 - Análisis de Acceso a Hospitales en Perú | Datos: MINSA - IPRESS")

# Cleanup al final
try:
    gc.collect()
except:
    pass