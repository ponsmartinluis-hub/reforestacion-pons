import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET
import os

# CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Cerrito del Carmen", layout="wide")
st.title("🌵 Dashboard: Martín Pons y Hermanos")

# --- NOMBRES DE ARCHIVOS POR DEFECTO (EN GITHUB) ---
# Asegúrate de que en GitHub tus archivos se llamen EXACTAMENTE así:
DEFAULT_EXCEL = "plantacion.xlsx"
DEFAULT_KML = "cerritodelcarmen.kml.txt"

# --- BARRA LATERAL ---
st.sidebar.header("📂 Gestión de Archivos")
st.sidebar.info("La App carga datos automáticos. Si quieres actualizar, sube nuevos archivos abajo.")

uploaded_file = st.sidebar.file_uploader("Actualizar Excel", type=["csv", "xlsx"])
kml_file_upload = st.sidebar.file_uploader("Actualizar Mapa KML", type=["kml", "xml", "txt"])

# --- LÓGICA DE SELECCIÓN DE ARCHIVOS ---
# 1. Decidir qué Excel usar
target_excel = None
if uploaded_file is not None:
    target_excel = uploaded_file # El usuario subió uno nuevo
elif os.path.exists(DEFAULT_EXCEL):
    target_excel = DEFAULT_EXCEL # Usamos el guardado en GitHub

# 2. Decidir qué KML usar
target_kml = None
if kml_file_upload is not None:
    target_kml = kml_file_upload
elif os.path.exists(DEFAULT_KML):
    target_kml = DEFAULT_KML

# --- FUNCIÓN LEER KML ---
def leer_kml(archivo_kml):
    zonas = []
    try:
        tree = ET.parse(archivo_kml)
        root = tree.getroot()
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        for pm in root.findall('.//kml:Placemark', ns):
            nombre = pm.find('kml:name', ns)
            nombre_txt = nombre.text if nombre is not None else "Zona"
            polygon = pm.find('.//kml:Polygon//kml:coordinates', ns)
            if polygon is not None and polygon.text:
                coords_raw = polygon.text.strip().split()
                puntos = []
                for c in coords_raw:
                    partes = c.split(',')
                    if len(partes) >= 2:
                        puntos.append([float(partes[1]), float(partes[0])])
                zonas.append({'nombre': nombre_txt, 'puntos': puntos})
    except Exception as e:
        st.error(f"Error KML: {e}")
    return zonas

# --- EJECUCIÓN PRINCIPAL ---
if target_excel:
    # Carga de datos
    try:
        if hasattr(target_excel, 'name') and target_excel.name.endswith('.csv'):
             df = pd.read_csv(target_excel)
        elif isinstance(target_excel, str) and target_excel.endswith('.csv'):
             df = pd.read_csv(target_excel)
        else:
             df = pd.read_excel(target_excel)
             
        df.columns = df.columns.str.strip().str.replace('[,.]', '', regex=True)
        df_mapa = df.dropna(subset=['Coordenada_X', 'Coordenada_Y'])
        
        # Métricas
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Plantas", len(df))
        col2.metric("Magueyes", len(df[df['Tipo'] == 'Maguey']))
        col3.metric("Georreferenciadas 📍", len(df_mapa)) 
        col4.metric("Salud Crítica ⚠️", len(df[df['Estado_Salud'] == 'Crítico']))

        # Mapa
        st.subheader("Mapa del Terreno")
        m = folium.Map(location=[21.2374, -100.4639], zoom_start=18)

        # Dibujar KML si existe
        if target_kml:
            zonas = leer_kml(target_kml)
            colores = {'Martín Pons': '#3388ff', 'Leonor Pons Gutiérrez': '#ff33bb', 
                       'Juan Manuel Pons': '#33ff57', 'Fracción Ruinas': '#ff9933'}
            for z in zonas:
                c = colores.get(z['nombre'], 'gray')
                es_borde = 'completo' in z['nombre'].lower()
                folium.Polygon(locations=z['puntos'], color=c, weight=3 if es_borde else 1, 
                               fill=not es_borde, fill_opacity=0.2, popup=z['nombre']).add_to(m)

        # Dibujar Puntos
        for _, row in df_mapa.iterrows():
            c = 'green' if row['Estado_Salud'] == 'Excelente' else 'red'
            folium.CircleMarker([row['Coordenada_X'], row['Coordenada_Y']], radius=4, color=c, fill=True, popup=f"{row['Tipo']}").add_to(m)

        st_folium(m, width=1200, height=600)
        st.dataframe(df)

    except Exception as e:
        st.error(f"Error leyendo el archivo: {e}")
else:
    st.info("⚠️ No se encontraron datos. Por favor sube 'plantacion.xlsx' al GitHub o cárgalo aquí.")
