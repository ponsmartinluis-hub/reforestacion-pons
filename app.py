import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET
import os

# --- CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Gestión Cerrito del Carmen", layout="wide", page_icon="🌵")
st.markdown("""
    <style>
    .main {background-color: #f8f9fa;}
    h1, h2, h3 {color: #2c3e50;}
    .stMetric {background-color: #ffffff; border: 1px solid #e0e0e0; padding: 10px; border-radius: 8px;}
    </style>
    """, unsafe_allow_html=True)

st.title("🌵 Dashboard Estratégico: Martín Pons y Hermanos")

# --- VARIABLES POR DEFECTO ---
DEFAULT_EXCEL = "plantacion.xlsx"
DEFAULT_KML = "cerritodelcarmen.kml.txt"

# --- BARRA LATERAL (CONFIGURACIÓN) ---
with st.sidebar:
    st.header("⚙️ Centro de Carga")
    
    # 1. CARGA DE ARCHIVOS
    uploaded_file = st.file_uploader("Base de Datos (Excel/CSV)", type=["csv", "xlsx"])
    kml_file_upload = st.file_uploader("Mapa Digital (KML)", type=["kml", "xml", "txt"])
    
    st.divider()
    st.subheader("🔧 Mapeo de Columnas")
    st.info("Si cambias los nombres en el Excel, ajústalos aquí:")

# --- LÓGICA DE CARGA INICIAL ---
target_excel = uploaded_file if uploaded_file else (DEFAULT_EXCEL if os.path.exists(DEFAULT_EXCEL) else None)
target_kml = kml_file_upload if kml_file_upload else (DEFAULT_KML if os.path.exists(DEFAULT_KML) else None)

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

# --- PROCESAMIENTO INTELIGENTE ---
if target_excel:
    try:
        # A) LEER EL ARCHIVO ORIGINAL (SIN TOCAR)
        if hasattr(target_excel, 'name') and target_excel.name.endswith('.csv'):
             df_raw = pd.read_csv(target_excel)
        elif isinstance(target_excel, str) and target_excel.endswith('.csv'):
             df_raw = pd.read_csv(target_excel)
        else:
             df_raw = pd.read_excel(target_excel)
        
        # Limpieza básica de nombres (quitar espacios extra)
        df_raw.columns = df_raw.columns.str.strip()

        # B) SELECTORES DE MAPEO (EN LA BARRA LATERAL)
        # Esto permite al usuario decirnos qué columna es cuál
        with st.sidebar:
            # Función para intentar adivinar la columna correcta
            def encontrar_col(opciones, busqueda):
                for col in opciones:
                    if busqueda.lower() in col.lower():
                        return col
                return opciones[0] # Si no encuentra, devuelve la primera

            col_lat = st.selectbox("Columna Latitud (Y)", df_raw.columns, index=df_raw.columns.get_loc(encontrar_col(df_raw.columns, "Coordenada_X")))
            col_lon = st.selectbox("Columna Longitud (X)", df_raw.columns, index=df_raw.columns.get_loc(encontrar_col(df_raw.columns, "Coordenada_Y")))
            col_tipo = st.selectbox("Columna Tipo Planta", df_raw.columns, index=df_raw.columns.get_loc(encontrar_col(df_raw.columns, "Tipo")))
            col_salud = st.selectbox("Columna Salud", df_raw.columns, index=df_raw.columns.get_loc(encontrar_col(df_raw.columns, "Salud")))
            col_id = st.selectbox("Columna ID / Nombre", df_raw.columns, index=df_raw.columns.get_loc(encontrar_col(df_raw.columns, "ID")))

        # C) CREAR DATAFRAME ESTANDARIZADO (RENOMBRAR INTERNAMENTE)
        df = df_raw.copy()
        df.rename(columns={
            col_lat: 'Coordenada_X', # Nota: Usaste X para Lat en tu excel, mantenemos tu lógica
            col_lon: 'Coordenada_Y',
            col_tipo: 'Tipo',
            col_salud: 'Estado_Salud',
            col_id: 'ID_Especimen'
        }, inplace=True)

        df_mapa = df.dropna(subset=['Coordenada_X', 'Coordenada_Y'])

        # --- PESTAÑAS DEL DASHBOARD ---
        tab1, tab2, tab3 = st.tabs(["📊 Análisis Flexible", "🗺️ Mapa Geo-Estratégico", "💰 Negocio"])

        # TAB 1: ANÁLISIS
        with tab1:
            st.subheader("🔍 Analizador de Datos")
            columnas_excluidas = ['Coordenada_X', 'Coordenada_Y', 'ID_Especimen', 'Tipo', 'Estado_Salud']
            # Permitimos analizar las columnas ORIGINALES que sobraron
            cols_extra = [c for c in df.columns if c not in columnas_excluidas]
            
            if cols_extra:
                col_elegida = st.selectbox("Analizar Variable Extra:", cols_extra)
                
                c1, c2 = st.columns([2,1])
                with c1:
                    if df[col_elegida].dtype == 'object':
                        conteo = df[col_elegida].value_counts().reset_index()
                        conteo.columns = ['Dato', 'Total']
                        st.plotly_chart(px.bar(conteo, x='Dato', y='Total', color='Dato', title=f"Totales por {col_elegida}"), use_container_width=True)
                    else:
                        st.plotly_chart(px.histogram(df, x=col_elegida, title=f"Distribución de {col_elegida}"), use_container_width=True)
                with c2:
                    st.write("Datos filtrados:")
                    st.dataframe(df[[col_elegida, 'ID_Especimen']].head(10), use_container_width=True)
            else:
                st.info("Tu Excel solo tiene las columnas básicas. Agrega más columnas (ej. Altura, Dueño) para ver análisis aquí.")
            
            st.divider()
            st.caption("Vista completa de la Base de Datos:")
            st.dataframe(df)

        # TAB 2: MAPA
        with tab2:
            st.metric("Puntos Activos", len(df_mapa))
            m = folium.Map(location=[21.2374, -100.4639], zoom_start=18)

            if target_kml:
                zonas = leer_kml(target_kml)
                colores = {'Martín Pons': '#3388ff', 'Leonor Pons Gutiérrez': '#ff33bb', 'Juan Manuel Pons': '#33ff57'}
                for z in zonas:
                    c = colores.get(z['nombre'], '#ff9933')
                    folium.Polygon(locations=z['puntos'], color=c, weight=2, fill=True, fill_opacity=0.1, popup=z['nombre']).add_to(m)

            for _, row in df_mapa.iterrows():
                # Lógica de color segura
                color = 'green'
                if str(row['Estado_Salud']).lower() in ['crítico', 'critico', 'malo']: color = 'red'
                elif str(row['Estado_Salud']).lower() in ['regular', 'medio']: color = 'orange'
                
                folium.CircleMarker(
                    [row['Coordenada_X'], row['Coordenada_Y']], radius=5, color=color, fill=True, fill_opacity=0.8,
                    popup=f"ID: {row['ID_Especimen']}\n{row['Tipo']}"
                ).add_to(m)
            
            st_folium(m, width=1200, height=500)

        # TAB 3: NEGOCIO
        with tab3:
            st.header("Proyección Financiera")
            st.info("Calculadora de ROI basada en inventario actual.")
            plantas_activas = len(df)
            precio = st.slider("Precio por Piña ($)", 500, 1500, 800)
            st.metric("Valor del Inventario", f"${plantas_activas * precio:,.2f}")

    except Exception as e:
        st.error(f"Error de lectura: {e}")
        st.warning("Consejo: Revisa que hayas seleccionado las columnas correctas en la barra lateral.")
else:
    st.info("Sube un archivo para empezar.")
