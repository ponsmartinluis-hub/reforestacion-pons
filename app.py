import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET

# CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Cerrito del Carmen - Gestión", layout="wide")
st.title("🌵 Dashboard de Reforestación: Martín Pons y Hermanos")

# --- BARRA LATERAL (CARGA DE ARCHIVOS) ---
st.sidebar.header("📂 Carga de Archivos")
uploaded_file = st.sidebar.file_uploader("1. Base de Datos (Excel/CSV)", type=["csv", "xlsx"])
kml_file = st.sidebar.file_uploader("2. Mapa de Divisiones (.kml)", type=["kml", "xml", "txt"])

# --- FUNCIÓN PARA LEER KML ---
def leer_kml(archivo_kml):
    zonas = []
    try:
        # Leemos el archivo
        tree = ET.parse(archivo_kml)
        root = tree.getroot()
        # Espacio de nombres de KML (necesario para encontrar las etiquetas)
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        # Buscamos todos los 'Placemark' (lugares marcados)
        for pm in root.findall('.//kml:Placemark', ns):
            nombre = pm.find('kml:name', ns)
            nombre_txt = nombre.text if nombre is not None else "Zona Desconocida"
            
            # Buscamos las coordenadas del polígono
            polygon = pm.find('.//kml:Polygon//kml:coordinates', ns)
            if polygon is not None and polygon.text:
                # Convertimos el texto "lon,lat,alt" a una lista de [lat, lon]
                coords_raw = polygon.text.strip().split()
                puntos = []
                for c in coords_raw:
                    partes = c.split(',')
                    if len(partes) >= 2:
                        # KML usa (Lon, Lat), Folium usa (Lat, Lon) -> Invertimos
                        puntos.append([float(partes[1]), float(partes[0])])
                
                zonas.append({'nombre': nombre_txt, 'puntos': puntos})
    except Exception as e:
        st.error(f"Error leyendo el KML: {e}")
    return zonas

# --- LÓGICA PRINCIPAL ---
if uploaded_file:
    # A) CARGA DE PLANTAS
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    
    # Limpieza
    df.columns = df.columns.str.strip().str.replace('[,.]', '', regex=True)
    df_mapa = df.dropna(subset=['Coordenada_X', 'Coordenada_Y'])

    # B) MÉTRICAS
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Especímenes", len(df))
    col2.metric("Magueyes", len(df[df['Tipo'] == 'Maguey']))
    col3.metric("Con Ubicación 📍", len(df_mapa)) 
    col4.metric("Salud Crítica ⚠️", len(df[df['Estado_Salud'] == 'Crítico']))

    # C) MAPA
    st.subheader("Ubicación y Divisiones del Terreno")
    m = folium.Map(location=[21.2374, -100.4639], zoom_start=18)

    # 1. DIBUJAR DIVISIONES DEL KML (SI SE SUBIÓ)
    if kml_file:
        zonas_kml = leer_kml(kml_file)
        
        # Colores para cada hermano/zona
        colores = {
            'Martín Pons': '#3388ff',       # Azul
            'Leonor Pons Gutiérrez': '#ff33bb', # Rosa
            'Juan Manuel Pons': '#33ff57',  # Verde
            'Fracción Ruinas': '#ff9933',   # Naranja
            'Fracción Agrícola': '#9933ff', # Morado
            'Cerrito del Carmen completo': 'gray' # Borde general
        }

        for zona in zonas_kml:
            color_zona = colores.get(zona['nombre'], 'gray')
            # Si es el borde completo, solo dibujamos línea, si es terreno, rellenamos
            es_borde = 'completo' in zona['nombre'].lower()
            
            folium.Polygon(
                locations=zona['puntos'],
                color=color_zona,
                weight=3 if es_borde else 1,
                fill=not es_borde,
                fill_opacity=0.2 if not es_borde else 0,
                popup=f"Propiedad: {zona['nombre']}",
                tooltip=zona['nombre']
            ).add_to(m)
        
        st.success(f"✅ Se cargaron {len(zonas_kml)} zonas del archivo KML.")

    # 2. DIBUJAR PLANTAS (PUNTOS)
    if not df_mapa.empty:
        for idx, row in df_mapa.iterrows():
            color_punto = 'green' if row['Estado_Salud'] == 'Excelente' else 'red'
            folium.CircleMarker(
                location=[row['Coordenada_X'], row['Coordenada_Y']],
                radius=4,
                color=color_punto,
                fill=True,
                fill_opacity=1,
                popup=f"{row['Tipo']} ({row['ID_Especimen']})"
            ).add_to(m)
    
    st_folium(m, width=1200, height=600)

    # D) TABLA
    st.subheader("Base de Datos Maestra")
    st.dataframe(df)

else:
    st.info("👋 Por favor, sube tu base de datos Excel en la barra lateral para comenzar.")
