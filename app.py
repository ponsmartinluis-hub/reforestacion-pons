import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET
import os
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Suite Cerrito del Carmen", layout="wide", page_icon="🌲")

# --- ESTILOS CSS CORREGIDOS (ALTO CONTRASTE) ---
st.markdown("""
    <style>
    .main {background-color: #f4f6f9;}
    h1 {color: #1e3a8a;}
    
    /* 1. FORZAR COLOR DE TARJETAS Y TEXTO */
    .stMetric {
        background-color: #ffffff !important; /* Fondo blanco obligatorio */
        padding: 15px !important;
        border-radius: 10px !important;
        border-left: 6px solid #1e3a8a !important;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1) !important;
    }
    
    /* 2. FORZAR COLOR DE LOS NÚMEROS (VALORES) A NEGRO */
    [data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        color: #000000 !important; /* Negro puro */
        font-weight: bold !important;
    }

    /* 3. FORZAR COLOR DE LOS TÍTULOS (ETIQUETAS) A GRIS OSCURO */
    [data-testid="stMetricLabel"] {
        color: #444444 !important; /* Gris oscuro */
        font-size: 1rem !important;
    }

    /* 4. ARREGLAR FLECHITAS DE DELTA (VERDE/ROJO) */
    [data-testid="stMetricDelta"] {
        font-weight: bold !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🌲 Dashboard Cerrito del Carmen: Gemini & M Pons")

# --- VARIABLES Y ESTADO ---
DEFAULT_EXCEL = "plantacion.xlsx"
DEFAULT_KML = "cerritodelcarmen.kml.txt"
if 'nuevos_registros' not in st.session_state: st.session_state.nuevos_registros = []

# --- FUNCIÓN GRÁFICA ---
def render_grafico_dinamico(df_in, key_suffix, titulo_seccion="📊 Análisis a Medida"):
    with st.expander(titulo_seccion, expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        cols = list(df_in.columns)
        eje_x = c1.selectbox("Eje X", cols, index=0, key=f"x_{key_suffix}")
        eje_y = c2.selectbox("Eje Y", ["Conteo (Automático)"] + cols, key=f"y_{key_suffix}")
        color_g = c3.selectbox("Color", ["Ninguno"] + cols, index=min(len(cols)-1, 2), key=f"c_{key_suffix}")
        tipo_g = c4.selectbox("Tipo", ["Barras", "Pastel", "Línea", "Dispersión", "Caja"], key=f"t_{key_suffix}")
        
        try:
            if eje_y == "Conteo (Automático)":
                df_count = df_in[eje_x].value_counts().reset_index()
                df_count.columns = [eje_x, 'Cantidad']
                if tipo_g == "Pastel": fig = px.pie(df_in, names=eje_x, title=f"Distribución de {eje_x}")
                else: fig = px.bar(df_count, x=eje_x, y='Cantidad', text='Cantidad', title=f"Total por {eje_x}")
            else:
                color_arg = color_g if color_g != "Ninguno" else None
                if tipo_g == "Barras": fig = px.bar(df_in, x=eje_x, y=eje_y, color=color_arg)
                elif tipo_g == "Línea": fig = px.line(df_in, x=eje_x, y=eje_y, color=color_arg)
                elif tipo_g == "Dispersión": fig = px.scatter(df_in, x=eje_x, y=eje_y, color=color_arg)
                elif tipo_g == "Caja": fig = px.box(df_in, x=eje_x, y=eje_y, color=color_arg)
                else: fig = px.bar(df_in, x=eje_x, y=eje_y)
            st.plotly_chart(fig, use_container_width=True)
        except Exception: st.warning("Combinación no válida.")

# --- FUNCIÓN KML ---
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
    except Exception: pass
    return zonas

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🎛️ Operaciones")
    uploaded_file = st.file_uploader("Datos (Excel)", type=["csv", "xlsx"])
    kml_file_upload = st.file_uploader("Mapa (KML)", type=["kml", "xml", "txt"])
    
    with st.expander("➕ Registro Rápido"):
        with st.form("alta"):
            nid = st.text_input("ID")
            ntipo = st.selectbox("Tipo", ["Maguey", "Agave", "Mezquite", "Nopal"])
            npol = st.selectbox("Zona", ["Martín Pons", "Leonor Pons", "Juan Manuel Pons", "Ruinas"])
            c1, c2 = st.columns(2)
            nlat = c1.number_input("Lat", 21.23, format="%.4f")
            nlon = c2.number_input("Lon", -100.46, format="%.4f")
            nsalud = st.selectbox("Salud", ["Excelente", "Regular", "Crítico"])
            if st.form_submit_button("Guardar"):
                st.session_state.nuevos_registros.append({
                    'ID_Especimen': nid, 'Tipo': ntipo, 'Poligono': npol,
                    'Coordenada_X': nlat, 'Coordenada_Y': nlon, 'Estado_Salud': nsalud
                })
                st.success("Guardado")

# --- CARGA ---
target_excel = uploaded_file if uploaded_file else (DEFAULT_EXCEL if os.path.exists(DEFAULT_EXCEL) else None)
target
