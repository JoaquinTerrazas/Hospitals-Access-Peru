import matplotlib.pyplot as plt
import seaborn as sns
import folium
from folium.plugins import MarkerCluster
import geopandas as gpd
import streamlit as st
import gc  # Garbage collector
import warnings

# Configurar estilo de gráficos y suprimir warnings
plt.style.use('default')
sns.set_palette("viridis")
warnings.filterwarnings('ignore', category=FutureWarning)

def create_static_maps(map_data):
    """Crear los 3 mapas estáticos y retornar las figuras"""
    if map_data is None:
        st.error("Error: map_data is None")
        return {}
        
    figures = {}
    
    try:
        # Mapa 1: Total de hospitales por distrito
        fig1, ax1 = plt.subplots(1, 1, figsize=(12, 8))
        map_data.plot(column='num_hospitales', ax=ax1, legend=True,
                     cmap='YlOrRd', legend_kwds={'label': 'Número de Hospitales', 'shrink': 0.6},
                     edgecolor='black', linewidth=0.1)
        ax1.set_title('Total de Hospitales Públicos por Distrito', fontsize=14)
        ax1.set_axis_off()
        plt.tight_layout()
        figures['map1_hospitales_distrito'] = fig1
        
        # Mapa 2: Distritos sin hospitales
        fig2, ax2 = plt.subplots(1, 1, figsize=(12, 8))
        map_data.plot(color='lightgray', ax=ax2, edgecolor='white', linewidth=0.1)
        map_data[map_data['num_hospitales'] == 0].plot(color='red', ax=ax2, edgecolor='black', linewidth=0.1)
        ax2.set_title('Distritos sin Hospitales Públicos', fontsize=14)
        ax2.set_axis_off()
        plt.tight_layout()
        figures['map2_distritos_sin_hospitales'] = fig2
        
        # Mapa 3: Top 10 distritos
        fig3, ax3 = plt.subplots(1, 1, figsize=(12, 8))
        top_10_distritos = map_data.nlargest(10, 'num_hospitales')
        map_data.plot(color='lightgray', ax=ax3, edgecolor='white', linewidth=0.1)
        top_10_distritos.plot(column='num_hospitales', ax=ax3, legend=True,
                             cmap='viridis', legend_kwds={'label': 'Número de Hospitales', 'shrink': 0.6},
                             edgecolor='black', linewidth=0.5)
        ax3.set_title('Top 10 Distritos con Más Hospitales', fontsize=14)
        ax3.set_axis_off()
        plt.tight_layout()
        figures['map3_top10_distritos'] = fig3
        
    except Exception as e:
        st.error(f"Error creating static maps: {e}")
        # Limpiar figuras parcialmente creadas
        for fig in figures.values():
            plt.close(fig)
        return {}
    
    return figures

def create_department_bar_chart(dept_stats):
    """Crear gráfico de barras por departamento y retornar la figura"""
    if dept_stats is None:
        st.error("Error: dept_stats is None")
        return None
        
    try:
        fig, ax = plt.subplots(figsize=(12, 8))
        # ARREGLO del warning de seaborn
        sns.barplot(data=dept_stats, y='DEPARTAMENTO', x='total_hospitals', 
                   ax=ax, hue='DEPARTAMENTO', palette='viridis', legend=False)
        ax.set_title('Número de Hospitales por Departamento', fontsize=14, fontweight='bold')
        ax.set_xlabel('Número de Hospitales')
        ax.set_ylabel('Departamento')
        
        # Añadir valores en las barras
        for i, v in enumerate(dept_stats['total_hospitals']):
            ax.text(v + 0.5, i, str(int(v)), va='center', fontsize=9)
        
        plt.tight_layout()
        return fig
        
    except Exception as e:
        st.error(f"Error creating bar chart: {e}")
        return None

def create_national_folium_map(map_data, dataset_cv):
    """Crear mapa Folium nacional con choropleth y markers"""
    if map_data is None or dataset_cv is None:
        st.error("Error: map_data or dataset_cv is None")
        return None
        
    try:
        m = folium.Map(location=[-9.1900, -75.0152], zoom_start=5)
        
        # Choropleth
        folium.Choropleth(
            geo_data=map_data.__geo_interface__,
            data=map_data,
            columns=['UBIGEO', 'num_hospitales'],
            key_on='feature.properties.UBIGEO',
            fill_color='YlOrRd',
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name='Hospitales por distrito'
        ).add_to(m)
        
        # Marker clusters - limitar cantidad para evitar timeout
        marker_cluster = MarkerCluster().add_to(m)
        
        # Solo mostrar una muestra si hay demasiados hospitales
        sample_size = min(len(dataset_cv), 1000)  # Máximo 1000 markers
        dataset_sample = dataset_cv.sample(n=sample_size) if len(dataset_cv) > sample_size else dataset_cv
        
        for _, hospital in dataset_sample.iterrows():
            folium.Marker(
                location=[hospital['LATITUD'], hospital['LONGITUD']],
                popup=hospital['NOMBRE'],
                icon=folium.Icon(color='blue', icon='plus-sign')
            ).add_to(marker_cluster)
        
        return m
        
    except Exception as e:
        st.error(f"Error creating national map: {e}")
        return None

def create_proximity_map(centroid_row, hospitals_gdf, region_name, isolation_type):
    """Crear mapa de proximidad individual"""
    if centroid_row is None:
        st.warning(f"No data available for {region_name} {isolation_type}")
        return None
        
    try:
        m = folium.Map(
            location=[centroid_row.geometry.y, centroid_row.geometry.x], 
            zoom_start=12
        )
        
        # Centro poblado
        folium.Marker(
            location=[centroid_row.geometry.y, centroid_row.geometry.x],
            popup=f"{centroid_row['NOMBCCPP']} - {centroid_row['hospitals_in_10km']} hospitales",
            icon=folium.Icon(color='red' if isolation_type == 'isolation' else 'blue')
        ).add_to(m)
        
        # Buffer 10km
        folium.Circle(
            location=[centroid_row.geometry.y, centroid_row.geometry.x],
            radius=10000,
            color='red' if isolation_type == 'isolation' else 'green',
            fill=True,
            fillOpacity=0.2,
            popup=f"{centroid_row['NOMBCCPP']} - {centroid_row['hospitals_in_10km']} hospitales"
        ).add_to(m)
        
        # Hospitales dentro del buffer
        buffer_hospitals = hospitals_gdf[hospitals_gdf.geometry.within(centroid_row['buffer_10km'])]
        for _, hospital in buffer_hospitals.iterrows():
            folium.Marker(
                location=[hospital.geometry.y, hospital.geometry.x],
                popup=hospital['NOMBRE'],
                icon=folium.Icon(color='green', icon='plus-sign')
            ).add_to(m)
        
        return m
        
    except Exception as e:
        st.error(f"Error creating proximity map for {region_name}: {e}")
        return None

def create_proximity_maps(lima_analysis, loreto_analysis, gdf_hospitales):
    """Crear mapas de proximidad para Lima y Loreto"""
    if gdf_hospitales is None:
        st.error("Error: gdf_hospitales is None")
        return {}
        
    maps = {}
    
    try:
        # Mapa Lima - Aislamiento
        if lima_analysis[0] is not None:
            maps['lima_aislado'] = create_proximity_map(lima_analysis[0], gdf_hospitales, "Lima", "isolation")
        
        # Mapa Lima - Concentración
        if lima_analysis[1] is not None:
            maps['lima_concentrado'] = create_proximity_map(lima_analysis[1], gdf_hospitales, "Lima", "concentration")
        
        # Mapa Loreto - Aislamiento
        if loreto_analysis[0] is not None:
            maps['loreto_aislado'] = create_proximity_map(loreto_analysis[0], gdf_hospitales, "Loreto", "isolation")
        
        # Mapa Loreto - Concentración
        if loreto_analysis[1] is not None:
            maps['loreto_concentrado'] = create_proximity_map(loreto_analysis[1], gdf_hospitales, "Loreto", "concentration")
            
    except Exception as e:
        st.error(f"Error creating proximity maps: {e}")
    
    return maps

def generate_all_visualizations(data_dict):
    """Generar todas las visualizaciones y retornar diccionario con objetos"""
    if data_dict is None:
        st.error("Error: data_dict is None")
        return None
        
    try:
        st.info("Generando visualizaciones...")
        
        # Mapas estáticos
        static_maps = create_static_maps(data_dict['map_data'])
        
        # Gráfico de barras departamental
        bar_chart = create_department_bar_chart(data_dict['dept_stats'])
        
        # Mapas Folium
        national_map = create_national_folium_map(data_dict['map_data'], data_dict['dataset_cv'])
        proximity_maps = create_proximity_maps(
            data_dict['lima_analysis'], 
            data_dict['loreto_analysis'], 
            data_dict['gdf_hospitales']
        )
        
        # Limpiar memoria
        gc.collect()
        
        return {
            'static_maps': static_maps,
            'bar_chart': bar_chart,
            'national_map': national_map,
            'proximity_maps': proximity_maps
        }
        
    except Exception as e:
        st.error(f"Error generating visualizations: {e}")
        return None

def cleanup_matplotlib_figures(figures_dict):
    """Limpiar figuras de matplotlib para liberar memoria"""
    if figures_dict and 'static_maps' in figures_dict:
        for fig in figures_dict['static_maps'].values():
            plt.close(fig)
    
    if figures_dict and 'bar_chart' in figures_dict:
        plt.close(figures_dict['bar_chart'])
    
    gc.collect()