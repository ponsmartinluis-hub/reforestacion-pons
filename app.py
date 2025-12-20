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

# Estilos CSS (Look Ejecutivo)
st.markdown("""
    <style>
    .main {background-color: #f4f6f9;}
    h1 {color: #1e3a8a;}
    .stMetric {background-color: white; padding: 10px; border-radius: 8px; border-left: 5px solid #1e3a8a;}
    </style>
    """, unsafe_allow_html=True)

st.title("🌲 Dashboard de Reforestación Cerrito del Carmen : por Gemini y M Pons")

# --- VARIABLES Y ESTADO ---
DEFAULT_EXCEL = "plantacion.xlsx"
DEFAULT_KML = "cerritodelcarmen.kml.txt"
if 'nuevos_registros' not in st.session_state: st.session_state.nuevos_registros = []

# --- FUNCIÓN: GENERADOR DE GRÁFICAS (REUTILIZABLE) ---
def render_grafico_dinamico(df_in, key_suffix, titulo_seccion="📊 Análisis a Medida"):
    """Crea un widget de gráficas que se puede poner en cualquier pestaña"""
    with st.expander(titulo_seccion, expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        cols = list(df_in.columns)
        
        # Selectores únicos para cada sección (usando key_suffix)
        eje_x = c1.selectbox("Eje X", cols, index=0, key=f"x_{key_suffix}")
        eje_y = c2.selectbox("Eje Y (Opcional)", ["Conteo (Automático)"] + cols, key=f"y_{key_suffix}")
        color_g = c3.selectbox("Agrupar por Color", ["Ninguno"] + cols, index=min(len(cols)-1, 2), key=f"c_{key_suffix}")
        tipo_g = c4.selectbox("Tipo de Gráfico", ["Barras", "Pastel", "Línea", "Dispersión", "Caja"], key=f"t_{key_suffix}")
        
        # Lógica de Graficado
        try:
            if eje_y == "Conteo (Automático)":
                # Graficar conteos
                df_count = df_in[eje_x].value_counts().reset_index()
                df_count.columns = [eje_x, 'Cantidad']
                if tipo_g == "Pastel":
                    fig = px.pie(df_in, names=eje_x, title=f"Distribución de {eje_x}")
                else:
                    color_arg = color_g if color_g != "Ninguno" else None # No se puede agrupar conteos simples fácilmente por color extra, simplificamos
                    fig = px.bar(df_count, x=eje_x, y='Cantidad', text='Cantidad', title=f"Total por {eje_x}")
            else:
                # Graficar Columna vs Columna
                color_arg = color_g if color_g != "Ninguno" else None
                if tipo_g == "Barras": fig = px.bar(df_in, x=eje_x, y=eje_y, color=color_arg)
                elif tipo_g == "Línea": fig = px.line(df_in, x=eje_x, y=eje_y, color=color_arg)
                elif tipo_g == "Dispersión": fig = px.scatter(df_in, x=eje_x, y=eje_y, color=color_arg)
                elif tipo_g == "Caja": fig = px.box(df_in, x=eje_x, y=eje_y, color=color_arg)
                else: fig = px.bar(df_in, x=eje_x, y=eje_y) # Fallback
            
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.warning(f"No se pudo generar el gráfico con esa combinación: {e}")

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

# --- CARGA DE DATOS ---
target_excel = uploaded_file if uploaded_file else (DEFAULT_EXCEL if os.path.exists(DEFAULT_EXCEL) else None)
target_kml = kml_file_upload if kml_file_upload else (DEFAULT_KML if os.path.exists(DEFAULT_KML) else None)

if target_excel:
    try:
        # Lectura
        if hasattr(target_excel, 'name') and target_excel.name.endswith('.csv'): df = pd.read_csv(target_excel)
        elif isinstance(target_excel, str) and target_excel.endswith('.csv'): df = pd.read_csv(target_excel)
        else: df = pd.read_excel(target_excel)
        
        df.columns = df.columns.str.strip().str.replace('[,.]', '', regex=True)
        if st.session_state.nuevos_registros:
            df = pd.concat([df, pd.DataFrame(st.session_state.nuevos_registros)], ignore_index=True)
        
        df_mapa = df.dropna(subset=['Coordenada_X', 'Coordenada_Y'])

        # Botón Descarga
        with st.sidebar:
            st.divider()
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False)
            st.download_button("💾 Bajar Excel", data=output.getvalue(), file_name="plantacion_v9.xlsx")

        # ==============================================================================
        # ESTRUCTURA PRINCIPAL (4 PESTAÑAS)
        # ==============================================================================
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard General", "🗺️ Mapa Exclusivo", "💰 Finanzas (ROI)", "📋 Base de Datos"])

        # --- TAB 1: DASHBOARD ---
        with tab1:
            st.subheader("Resumen Ejecutivo")
            # KPIs Fijos (Siempre útiles)
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Plantas Totales", len(df))
            k2.metric("Magueyes", len(df[df['Tipo']=='Maguey']))
            k3.metric("En Riesgo", len(df[df['Estado_Salud']=='Crítico']), delta_color="inverse")
            k4.metric("Zonas Activas", df['Poligono'].nunique())
            
            st.divider()
            # ¡AQUÍ ESTÁ TU GRÁFICA PERSONALIZABLE 1!
            st.markdown("#### 🛠️ Tu Análisis Dinámico")
            render_grafico_dinamico(df, "dash_main", "Diseña tu gráfica principal")

        # --- TAB 2: MAPA ---
        with tab2:
            col_map, col_stats = st.columns([3, 1])
            with col_map:
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
                st_folium(m, width=1000, height=600)
            
            with col_stats:
                st.info("Estadísticas Geográficas")
                # ¡AQUÍ ESTÁ TU GRÁFICA PERSONALIZABLE 2!
                st.write("Analiza la distribución del mapa:")
                render_grafico_dinamico(df_mapa, "map_stats", "Graficar Mapa")

        # --- TAB 3: FINANZAS (REGRESO) ---
        with tab3:
            st.header("💰 Proyección Financiera y ROI")
            st.markdown("Simulador de negocio para Maguey/Agave.")
            
            # 1. Inputs Financieros
            with st.expander("1. Configuración de Costos y Precios", expanded=True):
                c1, c2, c3 = st.columns(3)
                inv_inicial = c1.number_input("Costo Plantación ($/planta)", 50.0, step=5.0)
                mant_anual = c2.number_input("Mantenimiento Anual ($/planta)", 20.0, step=5.0)
                anos = c3.slider("Años a Cosecha", 5, 12, 7)
                
                c4, c5 = st.columns(2)
                precio_venta = c4.number_input("Precio Venta Final ($/piña)", 800.0, step=50.0)
                merma = c5.slider("% Riesgo / Merma", 0, 30, 10) / 100

            # 2. Cálculos
            num_plantas = len(df[df['Tipo'].isin(['Maguey', 'Agave'])])
            if num_plantas == 0: num_plantas = len(df) # Fallback si no hay tipo definido
            
            costo_total = (inv_inicial + (mant_anual * anos)) * num_plantas
            plantas_finales = num_plantas * (1 - merma)
            ingreso_total = plantas_finales * precio_venta
            utilidad = ingreso_total - costo_total
            roi = (utilidad / costo_total) * 100 if costo_total > 0 else 0
            
            # 3. Resultados Visuales
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("Inversión Total Estimada", f"${costo_total:,.2f}", delta="Costo")
            m2.metric("Venta Proyectada", f"${ingreso_total:,.2f}", delta="Ingreso")
            m3.metric("Utilidad Neta", f"${utilidad:,.2f}", delta=f"ROI: {roi:.1f}%")
            
            # 4. Gráfica Financiera
            st.markdown("#### 📈 Proyección de Flujo de Efectivo")
            # Creamos datos simulados para la gráfica financiera
            datos_fin = pd.DataFrame({
                'Concepto': ['Inversión', 'Ventas', 'Utilidad'],
                'Monto': [costo_total, ingreso_total, utilidad],
                'Tipo': ['Salida', 'Entrada', 'Resultado']
            })
            # ¡AQUÍ ESTÁ TU GRÁFICA PERSONALIZABLE 3! (Pre-cargada con finanzas)
            fig_fin = px.bar(datos_fin, x='Concepto', y='Monto', color='Tipo', text='Monto', title="Balance Financiero")
            st.plotly_chart(fig_fin, use_container_width=True)
            
            st.write("¿Quieres analizar otra variable financiera?")
            render_grafico_dinamico(df, "fin_stats", "Crear gráfica extra")

        # --- TAB 4: BASE DE DATOS ---
        with tab4:
            st.subheader("Base de Datos Maestra")
            # ¡AQUÍ ESTÁ TU GRÁFICA PERSONALIZABLE 4!
            render_grafico_dinamico(df, "data_explore", "Analizar Base de Datos")
            st.divider()
            st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.error(f"Error cargando: {e}")
else:
    st.info("Sube tu archivo para comenzar.")
