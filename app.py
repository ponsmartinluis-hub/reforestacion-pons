import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET
import os
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA Y ESTILO ---
st.set_page_config(page_title="Cerrito del Carmen", layout="wide", page_icon="🌲")

# Estilos CSS para dar formato profesional a las secciones
st.markdown("""
    <style>
    .main {background-color: #f0f2f6;}
    h1 {color: #1e3a8a; text-align: center;}
    h3 {color: #2c3e50; border-bottom: 2px solid #4CAF50; padding-bottom: 5px;}
    .stMetric {background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);}
    div.stButton > button {width: 100%; border-radius: 8px;}
    </style>
    """, unsafe_allow_html=True)

# --- TÍTULO ACTUALIZADO ---
st.title("🌲 Dashboard de Reforestación Cerrito del Carmen : por Gemini y M Pons")
st.markdown("---")

# --- VARIABLES Y ESTADO ---
DEFAULT_EXCEL = "plantacion.xlsx"
DEFAULT_KML = "cerritodelcarmen.kml.txt"
if 'nuevos_registros' not in st.session_state: st.session_state.nuevos_registros = []

# --- FUNCIONES AUXILIARES ---
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

# --- BARRA LATERAL (OPERACIONES) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3594/3594412.png", width=80)
    st.header("Centro de Control")
    uploaded_file = st.file_uploader("📂 Cargar Datos (Excel)", type=["csv", "xlsx"])
    kml_file_upload = st.file_uploader("🗺️ Cargar Mapa (KML)", type=["kml", "xml", "txt"])
    
    st.divider()
    
    # MODULO DE REGISTRO RÁPIDO
    with st.expander("📝 Registrar Nueva Planta", expanded=False):
        with st.form("formulario_alta"):
            st.write("Datos de Campo")
            nuevo_id = st.text_input("ID (Ej. MAG-100)")
            nuevo_tipo = st.selectbox("Especie", ["Maguey", "Agave", "Mezquite", "Nopal", "Otro"])
            nuevo_poli = st.selectbox("Zona", ["Martín Pons", "Leonor Pons Gutiérrez", "Juan Manuel Pons", "Fracción Ruinas"])
            c1, c2 = st.columns(2)
            nueva_lat = c1.number_input("Latitud", value=21.23, format="%.5f")
            nueva_lon = c2.number_input("Longitud", value=-100.46, format="%.5f")
            nueva_salud = st.selectbox("Salud", ["Excelente", "Regular", "Crítico"])
            if st.form_submit_button("Guardar Registro"):
                st.session_state.nuevos_registros.append({
                    'ID_Especimen': nuevo_id, 'Tipo': nuevo_tipo, 'Poligono': nuevo_poli,
                    'Coordenada_X': nueva_lat, 'Coordenada_Y': nueva_lon, 'Estado_Salud': nueva_salud
                })
                st.success("Guardado en memoria")

# --- PROCESAMIENTO DE DATOS ---
target_excel = uploaded_file if uploaded_file else (DEFAULT_EXCEL if os.path.exists(DEFAULT_EXCEL) else None)
target_kml = kml_file_upload if kml_file_upload else (DEFAULT_KML if os.path.exists(DEFAULT_KML) else None)

if target_excel:
    try:
        # Carga
        if hasattr(target_excel, 'name') and target_excel.name.endswith('.csv'): df = pd.read_csv(target_excel)
        elif isinstance(target_excel, str) and target_excel.endswith('.csv'): df = pd.read_csv(target_excel)
        else: df = pd.read_excel(target_excel)
        
        df.columns = df.columns.str.strip().str.replace('[,.]', '', regex=True)
        
        # Fusión con nuevos registros
        if st.session_state.nuevos_registros:
            df = pd.concat([df, pd.DataFrame(st.session_state.nuevos_registros)], ignore_index=True)
            st.toast(f"Plantas nuevas en sesión: {len(st.session_state.nuevos_registros)}", icon="🌱")

        df_mapa = df.dropna(subset=['Coordenada_X', 'Coordenada_Y'])

        # --- BOTÓN DE DESCARGA ---
        with st.sidebar:
            st.divider()
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False)
            st.download_button("💾 Descargar Excel Actualizado", data=output.getvalue(), file_name="plantacion_v8.xlsx")

        # ==============================================================================
        # PESTAÑAS DEL DASHBOARD
        # ==============================================================================
        tab1, tab2, tab3 = st.tabs(["📊 Resumen Ejecutivo", "🗺️ Mapa Satelital", "📋 Base de Datos"])

        # --- TAB 1: DASHBOARD INICIAL (RENOVADO) ---
        with tab1:
            # SECCIÓN 1: KPIs PRINCIPALES
            st.markdown("### 1. Balance General")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Total Inventario", f"{len(df)}", delta="Plantas")
            k2.metric("Magueyes", f"{len(df[df['Tipo']=='Maguey'])}", delta=f"{len(df[df['Tipo']=='Maguey'])/len(df):.0%} del total")
            k3.metric("Cobertura GPS", f"{len(df_mapa)}", delta="Geolocalizadas")
            # Valor estimado rápido (suponiendo $800 por planta promedio)
            valor_estimado = len(df) * 800
            k4.metric("Valor Est. Inventario", f"${valor_estimado:,.0f}", delta="MXN")

            st.divider()

            # SECCIÓN 2: DESGLOSE DETALLADO (DOS COLUMNAS)
            col_left, col_right = st.columns([1, 1])

            with col_left:
                st.markdown("### 2. Inventario por Especie y Zona")
                # Tabla resumen dinámica
                resumen_tipo = df.groupby(['Tipo', 'Poligono']).size().reset_index(name='Cantidad')
                fig_sun = px.sunburst(resumen_tipo, path=['Tipo', 'Poligono'], values='Cantidad', 
                                      color='Tipo', title="Distribución Jerárquica")
                st.plotly_chart(fig_sun, use_container_width=True)

            with col_right:
                st.markdown("### 3. Auditoría de Salud")
                # Gráfica de anillo
                fig_don = px.pie(df, names='Estado_Salud', title="Estado Fitosanitario", hole=0.4,
                                 color_discrete_map={'Excelente':'green', 'Regular':'orange', 'Crítico':'red', 'Muerto':'black'})
                st.plotly_chart(fig_don, use_container_width=True)
            
            # SECCIÓN 3: ALERTAS PRIORITARIAS
            st.markdown("### ⚠️ Alertas: Atención Inmediata (Estado Crítico)")
            criticos = df[df['Estado_Salud'].isin(['Crítico', 'Malo', 'Muerto'])]
            if not criticos.empty:
                st.warning(f"Se detectaron {len(criticos)} especímenes en riesgo.")
                st.dataframe(criticos[['ID_Especimen', 'Tipo', 'Poligono', 'Estado_Salud', 'Notas'] if 'Notas' in df.columns else ['ID_Especimen', 'Tipo', 'Poligono', 'Estado_Salud']], use_container_width=True)
            else:
                st.success("✅ ¡Excelente! No hay plantas en estado crítico reportadas.")

        # --- TAB 2: MAPA ---
        with tab2:
            st.markdown(f"**Visualizando {len(df_mapa)} puntos en el terreno**")
            m = folium.Map(location=[21.2374, -100.4639], zoom_start=18, tiles="OpenStreetMap") # Ojo: tiles="OpenStreetMap" carga rápido

            if target_kml:
                zonas = leer_kml(target_kml)
                colores = {'Martín Pons': '#3388ff', 'Leonor Pons Gutiérrez': '#ff33bb', 'Juan Manuel Pons': '#33ff57'}
                for z in zonas:
                    c = colores.get(z['nombre'], '#ff9933')
                    folium.Polygon(locations=z['puntos'], color=c, weight=2, fill=True, fill_opacity=0.1, popup=z['nombre']).add_to(m)

            for _, row in df_mapa.iterrows():
                color = 'green' if row['Estado_Salud'] == 'Excelente' else ('red' if row['Estado_Salud'] == 'Crítico' else 'orange')
                folium.CircleMarker(
                    [row['Coordenada_X'], row['Coordenada_Y']], radius=5, color=color, fill=True, fill_opacity=0.8,
                    popup=f"<b>{row['Tipo']}</b><br>{row['ID_Especimen']}"
                ).add_to(m)
            st_folium(m, width=1200, height=600)

        # --- TAB 3: BASE DE DATOS ---
        with tab3:
            st.markdown("### Base de Datos Completa")
            with st.expander("🔍 Filtros Avanzados"):
                f_tipo = st.multiselect("Filtrar por Tipo", df['Tipo'].unique())
                f_zona = st.multiselect("Filtrar por Zona", df['Poligono'].unique())
            
            df_show = df.copy()
            if f_tipo: df_show = df_show[df_show['Tipo'].isin(f_tipo)]
            if f_zona: df_show = df_show[df_show['Poligono'].isin(f_zona)]
            
            st.dataframe(df_show, use_container_width=True)

    except Exception as e:
        st.error(f"Error cargando datos: {e}")
else:
    st.info("👋 Esperando archivo de datos...")
