import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from estimation import load_all_data
from plot import generate_all_visualizations
import folium
from streamlit_folium import st_folium
import tempfile
import base64
import os

def show_folium_map(folium_map, width=700, height=500):
    """Mostrar mapa Folium de manera estable usando archivos temporales"""
    if folium_map is None:
        st.warning("Mapa no disponible")
        return
    
    try:
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as f:
            folium_map.save(f.name)
            html_file = f.name
        
        # Leer y mostrar el HTML
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Mostrar como componente
        st.components.v1.html(html_content, width=width, height=height, scrolling=True)
        
        # Limpiar archivo temporal
        os.unlink(html_file)
        
    except Exception as e:
        st.error(f"Error mostrando mapa: {e}")


# Configuración de la página
st.set_page_config(
    page_title="Hospital Access Peru Analysis",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título principal
st.title("🏥 Análisis de Acceso a Hospitales en Perú")
st.markdown("---")

# Cargar datos (solo cache para datos, no para visualizaciones)
@st.cache_data(show_spinner="Cargando datos...", hash_funcs={folium.Map: lambda _: None})
def load_cached_data():
    return load_all_data()

# Función para generar visualizaciones sin cache (porque Folium no es serializable)
def generate_visualizations_no_cache(data_dict):
    """Generar visualizaciones sin cache para evitar problemas de serialización"""
    return generate_all_visualizations(data_dict)

# Cargar datos
data_dict = load_cached_data()

# Verificar que los datos se cargaron correctamente
if data_dict is None or data_dict['dataset_cv'] is None:
    st.error("Error al cargar los datos. Por favor verifica las rutas de los archivos.")
    st.stop()

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
    
    # Mostrar sample de datos
    st.subheader("Muestra de Datos de Hospitales")
    st.dataframe(data_dict['dataset_cv'][['NOMBRE', 'DEPARTAMENTO', 'LATITUD', 'LONGITUD']].head(10))

with tab2:
    st.header("Mapas Estáticos y Análisis Departamental")
    
    # Solo generar visualizaciones cuando se accede a esta pestaña
    if 'tab2_visualizations' not in st.session_state:
        with st.spinner("Generando mapas estáticos..."):
            st.session_state.tab2_visualizations = generate_visualizations_no_cache(data_dict)
    
    visualizations = st.session_state.tab2_visualizations
    
    # Mapas estáticos
    st.subheader("Mapas de Distribución de Hospitales")
    
    if visualizations and visualizations['static_maps']:
        col1, col2 = st.columns(2)
        
        with col1:
            st.pyplot(visualizations['static_maps']['map1_hospitales_distrito'])
            st.caption("Mapa 1: Hospitales por Distrito")
        
        with col2:
            st.pyplot(visualizations['static_maps']['map2_distritos_sin_hospitales'])
            st.caption("Mapa 2: Distritos sin Hospitales")
        
        st.pyplot(visualizations['static_maps']['map3_top10_distritos'])
        st.caption("Mapa 3: Top 10 Distritos con Más Hospitales")
    else:
        st.error("Error generando mapas estáticos")
    
    # Análisis departamental
    st.subheader("Análisis por Departamento")
    
    # Tabla resumen
    st.write("**Tabla Resumen - Hospitales por Departamento**")
    st.dataframe(data_dict['dept_stats'].sort_values('total_hospitals', ascending=False))
    
    # Gráfico de barras
    st.write("**Gráfico de Barras - Distribución por Departamento**")
    if visualizations and visualizations['bar_chart']:
        st.pyplot(visualizations['bar_chart'])
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

with tab3:
    st.header("Mapas Interactivos Dinámicos")
    
    # Solo generar visualizaciones cuando se accede a esta pestaña
    if 'tab3_visualizations' not in st.session_state:
        # Usar un placeholder para el spinner
        spinner_placeholder = st.empty()
        with spinner_placeholder:
            with st.spinner("Generando mapas interactivos..."):
                tab3_visualizations = generate_visualizations_no_cache(data_dict)
                st.session_state.tab3_visualizations = tab3_visualizations
        
        # Limpiar el spinner después de terminar
        spinner_placeholder.empty()

    visualizations = st.session_state.tab3_visualizations
    # Mapa nacional
    st.subheader("Mapa Nacional - Hospitales por Distrito")
    
    if visualizations and visualizations['national_map']:
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
    
    # Lima
    st.write("### 🏙️ Lima - Concentración Urbana y Accesibilidad")
    if visualizations and visualizations['proximity_maps']:
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
        st.error("Error generando mapas de proximidad")
    
    # Loreto
    st.write("### 🌳 Loreto - Dispersión Geográfica y Desafíos Amazónicos")
    if visualizations and visualizations['proximity_maps']:
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

# Footer
st.markdown("---")
st.caption("© 2024 - Análisis de Acceso a Hospitales en Perú | Datos: MINSA - IPRESS")
