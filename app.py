import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET
import os
from datetime import datetime, timedelta

# --- CONFIGURACIÓN VISUAL (ESTILO SOLEX) ---
st.set_page_config(page_title="Gestión Cerrito del Carmen", layout="wide", page_icon="🌵")

# Estilos CSS para hacerlo más atractivo
st.markdown("""
    <style>
    .main {background-color: #f5f5f5;}
    h1 {color: #2c3e50;}
    .stMetric {background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);}
    </style>
    """, unsafe_allow_html=True)

st.title("🌵 Dashboard Estratégico: Martín Pons y Hermanos")
st.markdown("---")

# --- VARIABLES POR DEFECTO ---
DEFAULT_EXCEL = "plantacion.xlsx"
DEFAULT_KML = "cerritodelcarmen.kml.txt"

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Panel de Control")
    st.image("https://cdn-icons-png.flaticon.com/512/1598/1598196.png", width=100)
    st.info("Sistema de Gestión de Reforestación y Riesgos.")
    
    st.divider()
    st.subheader("📂 Actualizar Datos")
    uploaded_file = st.file_uploader("Base de Datos (Excel)", type=["csv", "xlsx"])
    kml_file_upload = st.file_uploader("Mapa Digital (KML)", type=["kml", "xml", "txt"])

# --- LÓGICA DE CARGA ---
target_excel = uploaded_file if uploaded_file else (DEFAULT_EXCEL if os.path.exists(DEFAULT_EXCEL) else None)
target_kml = kml_file_upload if kml_file_upload else (DEFAULT_KML if os.path.exists(DEFAULT_KML) else None)

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
    except Exception:
        pass
    return zonas

# --- EJECUCIÓN PRINCIPAL ---
if target_excel:
    # Cargar Data
    try:
        if hasattr(target_excel, 'name') and target_excel.name.endswith('.csv'):
             df = pd.read_csv(target_excel)
        elif isinstance(target_excel, str) and target_excel.endswith('.csv'):
             df = pd.read_csv(target_excel)
        else:
             df = pd.read_excel(target_excel)
        
        df.columns = df.columns.str.strip().str.replace('[,.]', '', regex=True)
        df_mapa = df.dropna(subset=['Coordenada_X', 'Coordenada_Y'])

        # --- ESTRUCTURA DE PESTAÑAS (TABS) ---
        tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Mapa & Operaciones", "📊 Laboratorio de Datos", "📅 Cronograma", "💰 Plan de Negocio"])

        # ---------------------------------------------------------
        # TAB 1: EL MAPA CLÁSICO (MEJORADO)
        # ---------------------------------------------------------
        with tab1:
            # KPIs Principales
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Inventario Total", len(df), delta="Plantas")
            c2.metric("Magueyes", len(df[df['Tipo'] == 'Maguey']), delta="Producción")
            c3.metric("Cobertura GPS", f"{len(df_mapa)}/{len(df)}", delta_color="off")
            salud_critica = len(df[df['Estado_Salud'] == 'Crítico'])
            c4.metric("Atención Requerida", salud_critica, delta="- Riesgo", delta_color="inverse")

            st.subheader("📍 Georreferenciación de Predios")
            m = folium.Map(location=[21.2374, -100.4639], zoom_start=18, tiles="OpenStreetMap")

            # Capa KML
            if target_kml:
                zonas = leer_kml(target_kml)
                colores = {'Martín Pons': '#3388ff', 'Leonor Pons Gutiérrez': '#ff33bb', 'Juan Manuel Pons': '#33ff57'}
                for z in zonas:
                    c = colores.get(z['nombre'], '#ff9933')
                    folium.Polygon(locations=z['puntos'], color=c, weight=2, fill=True, fill_opacity=0.1, popup=z['nombre']).add_to(m)

            # Capa Puntos
            for _, row in df_mapa.iterrows():
                color = 'green' if row['Estado_Salud'] == 'Excelente' else ('orange' if row['Estado_Salud'] == 'Regular' else 'red')
                folium.CircleMarker(
                    [row['Coordenada_X'], row['Coordenada_Y']], radius=4, color=color, fill=True, fill_opacity=0.8,
                    popup=f"<b>{row['Tipo']}</b><br>ID: {row['ID_Especimen']}<br>Salud: {row['Estado_Salud']}"
                ).add_to(m)
            
            st_folium(m, width=1200, height=500)

        # ---------------------------------------------------------
        # TAB 2: LABORATORIO DE DATOS (TÚ CREAS LAS GRÁFICAS)
        # ---------------------------------------------------------
        with tab2:
            st.subheader("🛠️ Generador de Gráficas Personalizadas")
            col_x, col_y, col_color = st.columns(3)
            
            # Selectores dinámicos
            ejex = col_x.selectbox("Eje X (Horizontal)", df.columns)
            ejey = col_y.selectbox("Eje Y (Vertical)", df.columns)
            categoria = col_color.selectbox("Agrupar por color", df.columns, index=1)
            
            tipo_grafica = st.radio("Tipo de Gráfica", ["Barras", "Dispersión (Puntos)", "Caja (Boxplot)"], horizontal=True)

            if tipo_grafica == "Barras":
                fig = px.bar(df, x=ejex, y=ejey, color=categoria, title=f"Análisis: {ejex} vs {ejey}")
            elif tipo_grafica == "Dispersión (Puntos)":
                fig = px.scatter(df, x=ejex, y=ejey, color=categoria, size_max=15, title=f"Correlación: {ejex} vs {ejey}")
            else:
                fig = px.box(df, x=ejex, y=ejey, color=categoria, title=f"Distribución: {ejex} vs {ejey}")
            
            st.plotly_chart(fig, use_container_width=True)

        # ---------------------------------------------------------
        # TAB 3: CRONOGRAMA DE TRABAJO (GANTT)
        # ---------------------------------------------------------
        with tab3:
            st.subheader("📅 Calendario Operativo 2024-2025")
            st.caption("Planificación visual de actividades de mantenimiento.")
            
            # Simulación de datos de cronograma (Idealmente esto vendría de otro Excel)
            data_cronograma = [
                dict(Actividad="Riego Temporada Seca", Inicio="2025-01-10", Fin="2025-05-15", Responsable="Equipo A"),
                dict(Actividad="Poda Formativa", Inicio="2025-03-01", Fin="2025-03-20", Responsable="Equipo B"),
                dict(Actividad="Fertilización Orgánica", Inicio="2025-06-01", Fin="2025-06-10", Responsable="Equipo A"),
                dict(Actividad="Monitoreo de Plagas", Inicio="2025-02-01", Fin="2025-12-30", Responsable="Martín P."),
                dict(Actividad="Cosecha Estimada (Lote 1)", Inicio="2028-09-01", Fin="2028-12-01", Responsable="Todos"),
            ]
            df_gantt = pd.DataFrame(data_cronograma)
            
            fig_gantt = px.timeline(df_gantt, x_start="Inicio", x_end="Fin", y="Actividad", color="Responsable", title="Cronograma de Actividades")
            fig_gantt.update_yaxes(autorange="reversed") # Tareas en orden descendente
            st.plotly_chart(fig_gantt, use_container_width=True)

        # ---------------------------------------------------------
        # TAB 4: PLAN DE NEGOCIO (SIMULADOR)
        # ---------------------------------------------------------
        with tab4:
            st.subheader("💰 Simulador de Rentabilidad (Maguey/Agave)")
            
            col_inversion, col_retorno = st.columns(2)
            
            with col_inversion:
                st.markdown("#### 1. Costos de Inversión")
                costo_planta = st.number_input("Costo por planta ($)", value=50.0)
                costo_mantenimiento = st.number_input("Mantenimiento anual por planta ($)", value=20.0)
                anos_madurez = st.slider("Años para cosecha", 5, 10, 7)
                
                total_plantas = len(df[df['Tipo'] == 'Maguey'])
                inversion_total = (costo_planta * total_plantas) + (costo_mantenimiento * total_plantas * anos_madurez)
                st.error(f"Inversión Estimada Total: ${inversion_total:,.2f}")

            with col_retorno:
                st.markdown("#### 2. Proyección de Ventas")
                precio_piña = st.number_input("Precio venta por piña/planta ($)", value=800.0)
                merma = st.slider("Porcentaje de Merma (Riesgo)", 0, 50, 10) / 100
                
                plantas_finales = total_plantas * (1 - merma)
                ventas_totales = plantas_finales * precio_piña
                st.success(f"Ventas Estimadas: ${ventas_totales:,.2f}")
            
            st.divider()
            utilidad = ventas_totales - inversion_total
            roi = (utilidad / inversion_total) * 100 if inversion_total > 0 else 0
            
            c_res1, c_res2 = st.columns(2)
            c_res1.metric("Utilidad Proyectada", f"${utilidad:,.2f}")
            c_res2.metric("Retorno de Inversión (ROI)", f"{roi:.1f}%")
            
            if roi > 0:
                st.balloons()

    except Exception as e:
        st.error(f"Ocurrió un error al procesar los datos: {e}")
else:
    st.info("👋 Bienvenido al Sistema SOLEX-Agro. Por favor carga los datos para iniciar.")
