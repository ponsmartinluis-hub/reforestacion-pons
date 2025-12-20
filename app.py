import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET
import os
from io import BytesIO

# --- CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Gestión Cerrito del Carmen", layout="wide", page_icon="🌵")
st.markdown("""
    <style>
    .main {background-color: #f4f6f9;}
    h1, h2, h3 {color: #1e3a8a;}
    .stButton>button {width: 100%; border-radius: 5px;}
    </style>
    """, unsafe_allow_html=True)

st.title("🌵 Dashboard de Operaciones: Martín Pons y Hermanos")

# --- VARIABLES POR DEFECTO ---
DEFAULT_EXCEL = "plantacion.xlsx"
DEFAULT_KML = "cerritodelcarmen.kml.txt"

# --- INICIALIZAR ESTADO (Memoria temporal para nuevos registros) ---
if 'nuevos_registros' not in st.session_state:
    st.session_state.nuevos_registros = []

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

# --- BARRA LATERAL: CARGA Y REGISTRO ---
with st.sidebar:
    st.header("📂 Archivos")
    uploaded_file = st.file_uploader("Cargar Base de Datos", type=["csv", "xlsx"])
    kml_file_upload = st.file_uploader("Cargar Mapa KML", type=["kml", "xml", "txt"])
    
    st.divider()
    
    # --- HERRAMIENTA DE CAPTURA DE DATOS ---
    st.header("📝 Registrar Nueva Planta")
    st.info("Agrega datos sin abrir el Excel.")
    
    with st.form("formulario_alta"):
        nuevo_id = st.text_input("ID / Nombre (Ej. MAG-050)")
        nuevo_tipo = st.selectbox("Tipo", ["Maguey", "Agave", "Mezquite", "Nopal", "Otro"])
        nuevo_poli = st.selectbox("Ubicación (Polígono)", ["Martín Pons", "Leonor Pons Gutiérrez", "Juan Manuel Pons", "Fracción Ruinas", "Otro"])
        
        c1, c2 = st.columns(2)
        nueva_lat = c1.number_input("Latitud (Y)", value=21.23, format="%.5f")
        nueva_lon = c2.number_input("Longitud (X)", value=-100.46, format="%.5f")
        
        nueva_salud = st.selectbox("Estado de Salud", ["Excelente", "Regular", "Crítico", "Muerto"])
        
        submitted = st.form_submit_button("➕ Agregar al Sistema")
        
        if submitted:
            # Guardamos en la memoria temporal
            nuevo_dato = {
                'ID_Especimen': nuevo_id,
                'Tipo': nuevo_tipo,
                'Poligono': nuevo_poli,
                'Coordenada_X': nueva_lat,
                'Coordenada_Y': nueva_lon,
                'Estado_Salud': nueva_salud
            }
            st.session_state.nuevos_registros.append(nuevo_dato)
            st.success("✅ ¡Registrado! (Recuerda descargar el Excel al final)")

# --- LÓGICA DE DATOS ---
target_excel = uploaded_file if uploaded_file else (DEFAULT_EXCEL if os.path.exists(DEFAULT_EXCEL) else None)
target_kml = kml_file_upload if kml_file_upload else (DEFAULT_KML if os.path.exists(DEFAULT_KML) else None)

if target_excel:
    try:
        # 1. Cargar archivo original
        if hasattr(target_excel, 'name') and target_excel.name.endswith('.csv'):
             df = pd.read_csv(target_excel)
        elif isinstance(target_excel, str) and target_excel.endswith('.csv'):
             df = pd.read_csv(target_excel)
        else:
             df = pd.read_excel(target_excel)
        
        # Limpieza estándar
        df.columns = df.columns.str.strip().str.replace('[,.]', '', regex=True)

        # 2. FUSIONAR con nuevos registros (si los hay)
        if st.session_state.nuevos_registros:
            df_nuevos = pd.DataFrame(st.session_state.nuevos_registros)
            df = pd.concat([df, df_nuevos], ignore_index=True)
            st.toast(f"Se han agregado {len(df_nuevos)} plantas nuevas en esta sesión.", icon="ℹ️")

        df_mapa = df.dropna(subset=['Coordenada_X', 'Coordenada_Y'])

        # --- BOTÓN DE DESCARGA (PARA GUARDAR CAMBIOS) ---
        with st.sidebar:
            st.divider()
            st.write("💾 **Guardar Cambios**")
            
            # Convertir DataFrame a Excel en memoria
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Plantacion')
            
            st.download_button(
                label="Descargar Excel Actualizado",
                data=output.getvalue(),
                file_name="plantacion_actualizada.xlsx",
                mime="application/vnd.ms-excel"
            )

        # --- PESTAÑAS DEL DASHBOARD ---
        tab1, tab2, tab3 = st.tabs(["📊 Análisis", "🗺️ Mapa", "💰 Negocio"])

        # TAB 1: ANÁLISIS (Tu versión favorita simplificada)
        with tab1:
            col_sel, col_graf = st.columns([1, 3])
            with col_sel:
                st.subheader("Filtros")
                opcion = st.selectbox("Analizar por:", ["Poligono", "Tipo", "Estado_Salud"])
            
            with col_graf:
                conteo = df[opcion].value_counts().reset_index()
                conteo.columns = ['Categoría', 'Cantidad']
                fig = px.bar(conteo, x='Categoría', y='Cantidad', color='Categoría', text='Cantidad', title=f"Total por {opcion}")
                st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("Base de Datos en Vivo")
            st.dataframe(df, use_container_width=True)

        # TAB 2: MAPA
        with tab2:
            st.metric("Georreferenciadas", len(df_mapa))
            m = folium.Map(location=[21.2374, -100.4639], zoom_start=18)

            if target_kml:
                zonas = leer_kml(target_kml)
                colores = {'Martín Pons': '#3388ff', 'Leonor Pons Gutiérrez': '#ff33bb', 'Juan Manuel Pons': '#33ff57'}
                for z in zonas:
                    c = colores.get(z['nombre'], '#ff9933')
                    folium.Polygon(locations=z['puntos'], color=c, weight=2, fill=True, fill_opacity=0.1, popup=z['nombre']).add_to(m)

            for _, row in df_mapa.iterrows():
                color = 'red' if row['Estado_Salud'] == 'Crítico' else 'green'
                folium.CircleMarker(
                    [row['Coordenada_X'], row['Coordenada_Y']], radius=5, color=color, fill=True, 
                    popup=f"{row['Tipo']} ({row['ID_Especimen']})"
                ).add_to(m)
            st_folium(m, width=1200, height=500)

        # TAB 3: NEGOCIO
        with tab3:
            st.info("Calculadora Rápida")
            c1, c2 = st.columns(2)
            precio = c1.number_input("Precio ($)", 800)
            st.metric("Valor Total Estimado", f"${len(df) * precio:,.2f}")

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Carga tu archivo Excel para comenzar.")
