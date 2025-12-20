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

# Estilos CSS (Look Ejecutivo + Ajustes Móviles)
st.markdown("""
    <style>
    .main {background-color: #f4f6f9;}
    h1 {color: #1e3a8a;}
    /* Ajuste para que las métricas no se corten en móvil */
    [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
    }
    .stMetric {
        background-color: white; 
        padding: 10px; 
        border-radius: 8px; 
        border-left: 5px solid #1e3a8a;
        box-shadow: 1px 1px 3px rgba(0,0,0,0.1);
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
    with st.expander(titulo_seccion, expanded=False): # Colapsado por defecto en móvil para ahorrar espacio
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
        except Exception: st.warning("Combinación no válida para graficar.")

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
target_kml = kml_file_upload if kml_file_upload else (DEFAULT_KML if os.path.exists(DEFAULT_KML) else None)

if target_excel:
    try:
        if hasattr(target_excel, 'name') and target_excel.name.endswith('.csv'): df = pd.read_csv(target_excel)
        elif isinstance(target_excel, str) and target_excel.endswith('.csv'): df = pd.read_csv(target_excel)
        else: df = pd.read_excel(target_excel)
        df.columns = df.columns.str.strip().str.replace('[,.]', '', regex=True)
        if st.session_state.nuevos_registros:
            df = pd.concat([df, pd.DataFrame(st.session_state.nuevos_registros)], ignore_index=True)
        df_mapa = df.dropna(subset=['Coordenada_X', 'Coordenada_Y'])

        with st.sidebar:
            st.divider()
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer: df.to_excel(writer, index=False)
            st.download_button("💾 Bajar Excel", data=output.getvalue(), file_name="plantacion_v10.xlsx")

        # ==============================================================================
        # ESTRUCTURA PRINCIPAL
        # ==============================================================================
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "🗺️ Mapa", "💰 Finanzas", "📋 Datos"])

        # --- TAB 1: DASHBOARD (ARREGLADO PARA MÓVIL) ---
        with tab1:
            st.subheader("Resumen Ejecutivo")
            
            # SOLUCIÓN MÓVIL: Usamos 2 columnas en lugar de 4 para que no se aplasten
            col_kpi1, col_kpi2 = st.columns(2)
            with col_kpi1:
                st.metric("Plantas Totales", len(df))
                st.metric("En Riesgo", len(df[df['Estado_Salud']=='Crítico']), delta_color="inverse")
            with col_kpi2:
                st.metric("Magueyes", len(df[df['Tipo']=='Maguey']))
                st.metric("Zonas Activas", df['Poligono'].nunique())
            
            st.divider()
            st.markdown("#### 🛠️ Tu Análisis Dinámico")
            render_grafico_dinamico(df, "dash_main", "Diseña tu gráfica principal")

        # --- TAB 2: MAPA ---
        with tab2:
            st.info("Vista Satelital")
            m = folium.Map(location=[21.2374, -100.4639], zoom_start=18, tiles="OpenStreetMap")
            if target_kml:
                zonas = leer_kml(target_kml)
                colores = {'Martín Pons': '#3388ff', 'Leonor Pons Gutiérrez': '#ff33bb', 'Juan Manuel Pons': '#33ff57'}
                for z in zonas:
                    c = colores.get(z['nombre'], '#ff9933')
                    folium.Polygon(locations=z['puntos'], color=c, weight=2, fill=True, fill_opacity=0.1, popup=z['nombre']).add_to(m)
            for _, row in df_mapa.iterrows():
                color = 'red' if row['Estado_Salud'] == 'Crítico' else 'green'
                folium.CircleMarker([row['Coordenada_X'], row['Coordenada_Y']], radius=5, color=color, fill=True, popup=row['Tipo']).add_to(m)
            st_folium(m, width=1000, height=500)
            
            st.write("Estadísticas del Mapa:")
            render_grafico_dinamico(df_mapa, "map_stats")

        # --- TAB 3: FINANZAS ---
        with tab3:
            st.header("💰 Proyección Financiera")
            with st.expander("Configuración de Costos", expanded=True):
                c1, c2 = st.columns(2)
                inv_inicial = c1.number_input("Costo Plantación ($)", 50.0)
                mant_anual = c2.number_input("Mantenimiento Anual ($)", 20.0)
                anos = st.slider("Años a Cosecha", 5, 12, 7)
                precio_venta = st.number_input("Precio Venta ($/piña)", 800.0)
            
            num_plantas = len(df)
            costo_total = (inv_inicial + (mant_anual * anos)) * num_plantas
            ingreso_total = num_plantas * precio_venta
            utilidad = ingreso_total - costo_total
            
            st.divider()
            m1, m2 = st.columns(2)
            m1.metric("Inversión Total", f"${costo_total:,.0f}")
            m2.metric("Utilidad Neta", f"${utilidad:,.0f}", delta="Ganancia")
            
            datos_fin = pd.DataFrame({'Concepto': ['Inversión', 'Ventas', 'Utilidad'], 'Monto': [costo_total, ingreso_total, utilidad]})
            st.plotly_chart(px.bar(datos_fin, x='Concepto', y='Monto', color='Concepto', title="Balance"), use_container_width=True)

        # --- TAB 4: DATOS ---
        with tab4:
            st.subheader("Base de Datos")
            render_grafico_dinamico(df, "data_explore")
            st.dataframe(df, use_container_width=True)

    except Exception as e: st.error(f"Error: {e}")
else: st.info("Sube tu archivo.")
