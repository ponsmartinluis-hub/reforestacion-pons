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

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Panel de Control")
    st.info("Sube tus archivos para actualizar el tablero.")
    uploaded_file = st.file_uploader("Base de Datos (Excel)", type=["csv", "xlsx"])
    kml_file_upload = st.file_uploader("Mapa Digital (KML)", type=["kml", "xml", "txt"])

# --- CARGA INTELIGENTE ---
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

# --- PROGRAMA PRINCIPAL ---
if target_excel:
    try:
        # Lectura y Limpieza
        if hasattr(target_excel, 'name') and target_excel.name.endswith('.csv'):
             df = pd.read_csv(target_excel)
        elif isinstance(target_excel, str) and target_excel.endswith('.csv'):
             df = pd.read_csv(target_excel)
        else:
             df = pd.read_excel(target_excel)
        
        df.columns = df.columns.str.strip().str.replace('[,.]', '', regex=True)
        df_mapa = df.dropna(subset=['Coordenada_X', 'Coordenada_Y'])

        # --- PESTAÑAS ---
        tab1, tab2, tab3 = st.tabs(["📊 Análisis Detallado (Gráficas)", "🗺️ Mapa General", "💰 Plan de Negocio"])

        # ==============================================================================
        # TAB 1: ANÁLISIS DETALLADO (LO QUE PEDISTE)
        # ==============================================================================
        with tab1:
            st.subheader("🔍 Explorador de Datos por Columna")
            
            # 1. SELECTOR DE COLUMNA
            columnas_disponibles = [c for c in df.columns if c not in ['Coordenada_X', 'Coordenada_Y', 'ID_Especimen']]
            columna_seleccionada = st.selectbox("Selecciona qué columna quieres analizar:", columnas_disponibles, index=0)
            
            # 2. ANÁLISIS AUTOMÁTICO
            col_izq, col_der = st.columns([2, 1])
            
            with col_izq:
                # Si es TEXTO (Categorías: Tipo, Salud, Polígono)
                if df[columna_seleccionada].dtype == 'object':
                    st.markdown(f"### Distribución de: {columna_seleccionada}")
                    conteo = df[columna_seleccionada].value_counts().reset_index()
                    conteo.columns = ['Categoría', 'Total']
                    
                    # Gráfica de Barras con Totales
                    fig_bar = px.bar(conteo, x='Categoría', y='Total', text='Total', color='Categoría', 
                                     title=f"Totales por {columna_seleccionada}")
                    st.plotly_chart(fig_bar, use_container_width=True)
                    
                # Si es NÚMERO (Altura, Diámetro)
                else:
                    st.markdown(f"### Estadísticas de: {columna_seleccionada}")
                    fig_hist = px.histogram(df, x=columna_seleccionada, nbins=20, text_auto=True, 
                                            title=f"Distribución de {columna_seleccionada}")
                    st.plotly_chart(fig_hist, use_container_width=True)

            with col_der:
                # Gráfica de Pastel (Solo para texto) o Caja (para números)
                if df[columna_seleccionada].dtype == 'object':
                    fig_pie = px.pie(df, names=columna_seleccionada, title=f"% Porcentaje")
                    st.plotly_chart(fig_pie, use_container_width=True)
                    
                    # Tabla resumen pequeña
                    st.write("Resumen Numérico:")
                    st.dataframe(df[columna_seleccionada].value_counts(), use_container_width=True)
                else:
                    fig_box = px.box(df, y=columna_seleccionada, points="all", title="Rangos (Máx/Mín)")
                    st.plotly_chart(fig_box, use_container_width=True)
                    
                    st.metric("Promedio", f"{df[columna_seleccionada].mean():.2f}")
                    st.metric("Máximo", f"{df[columna_seleccionada].max():.2f}")

            # 3. VISUALIZADOR DE EXCEL (SIEMPRE VISIBLE ABAJO)
            st.divider()
            st.subheader(f"📋 Base de Datos Filtrada: {columna_seleccionada}")
            st.caption("Aquí puedes ver los datos crudos que generan las gráficas de arriba.")
            
            # Permitir filtrar la tabla visualmente
            filtro_valor = st.multiselect(f"Filtrar tabla por valores de '{columna_seleccionada}' (Opcional):", df[columna_seleccionada].unique())
            
            if filtro_valor:
                df_visible = df[df[columna_seleccionada].isin(filtro_valor)]
            else:
                df_visible = df
                
            st.dataframe(df_visible, use_container_width=True)


        # ==============================================================================
        # TAB 2: MAPA (SIMPLIFICADO)
        # ==============================================================================
        with tab2:
            st.metric("Total Georreferenciado", f"{len(df_mapa)} plantas")
            m = folium.Map(location=[21.2374, -100.4639], zoom_start=18)

            if target_kml:
                zonas = leer_kml(target_kml)
                colores = {'Martín Pons': '#3388ff', 'Leonor Pons Gutiérrez': '#ff33bb', 'Juan Manuel Pons': '#33ff57'}
                for z in zonas:
                    c = colores.get(z['nombre'], '#ff9933')
                    folium.Polygon(locations=z['puntos'], color=c, weight=2, fill=True, fill_opacity=0.1, popup=z['nombre']).add_to(m)

            for _, row in df_mapa.iterrows():
                color = 'green' if row['Estado_Salud'] == 'Excelente' else 'red'
                folium.CircleMarker(
                    [row['Coordenada_X'], row['Coordenada_Y']], radius=4, color=color, fill=True, fill_opacity=0.8,
                    popup=f"{row['Tipo']} ({row['ID_Especimen']})"
                ).add_to(m)
            
            st_folium(m, width=1200, height=500)

        # ==============================================================================
        # TAB 3: NEGOCIO (IGUAL QUE ANTES)
        # ==============================================================================
        with tab3:
            st.header("💰 Proyección Financiera")
            c1, c2 = st.columns(2)
            with c1:
                plantas = st.number_input("Total Plantas Maguey", value=len(df[df['Tipo']=='Maguey']))
                precio = st.number_input("Precio Venta Estimado ($)", value=800)
            with c2:
                venta_total = plantas * precio
                st.metric("Venta Potencial Total", f"${venta_total:,.2f}")
                st.progress(min(100, int(len(df)/10))) # Barra de progreso simulada

    except Exception as e:
        st.error(f"Error procesando el archivo: {e}")
else:
    st.info("👋 Carga tus datos para comenzar el análisis.")
