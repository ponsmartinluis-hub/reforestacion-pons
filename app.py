import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET
from io import BytesIO

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN VISUAL (ESTILO EJECUTIVO)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Monitor de Reforestación | SOLEX Secure",
    page_icon="🌲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Personalizado para apariencia profesional
st.markdown("""
<style>
    /* Fondo general limpio */
    .stApp {
        background-color: #f8f9fa;
    }
    /* Encabezados */
    h1, h2, h3 {
        color: #1e4620; /* Verde Bosque Oscuro */
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    /* Métricas (KPI Cards) */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #2e7d32; /* Borde verde */
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    /* Pestañas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #ffffff;
        border-radius: 4px;
        padding: 10px 20px;
        color: #4a4a4a;
    }
    .stTabs [aria-selected="true"] {
        background-color: #e8f5e9;
        color: #1b5e20;
        border-bottom: 2px solid #2e7d32;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. MOTOR DE DATOS (ROBUSTO)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data(uploaded_file):
    try:
        # Carga inteligente (CSV o Excel)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        # 1. LIMPIEZA DE NOMBRES DE COLUMNA
        # Quita espacios, puntos y comas extraños (ej: "Coordenada_X," -> "Coordenada_X")
        df.columns = df.columns.str.strip().str.replace('[,.:]', '', regex=True)
        
        # 2. ELIMINACIÓN DE DUPLICADOS (El error anterior)
        # Si el Excel tiene dos columnas "Altura_cm", borra la segunda.
        df = df.loc[:, ~df.columns.duplicated()]
        
        # 3. CONVERSIONES DE TIPOS
        # Numéricos
        cols_num = ['Coordenada_X', 'Coordenada_Y', 'Altura_cm', 'Diametro_cm', 'Costo', 'Inversion']
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Fechas
        if 'Fecha_Plantacion' in df.columns:
            df['Fecha_Plantacion'] = pd.to_datetime(df['Fecha_Plantacion'], errors='coerce')

        return df
    except Exception as e:
        st.error(f"Error crítico leyendo el archivo: {e}")
        return None

def leer_kml(archivo_kml):
    """Procesa archivos KML para dibujar polígonos en el mapa"""
    zonas = []
    try:
        string_data = archivo_kml.getvalue().decode("utf-8")
        root = ET.fromstring(string_data)
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        placemarks = root.findall('.//kml:Placemark', ns)
        if not placemarks: # Intento sin namespace
            placemarks = root.findall('.//{http://www.opengis.net/kml/2.2}Placemark')

        for pm in placemarks:
            nombre = pm.find('.//{http://www.opengis.net/kml/2.2}name')
            nombre_txt = nombre.text if nombre is not None else "Zona"
            coords = pm.find('.//{http://www.opengis.net/kml/2.2}coordinates')
            
            if coords is not None and coords.text:
                coords_raw = coords.text.strip().split()
                puntos = []
                for c in coords_raw:
                    val = c.split(',')
                    if len(val) >= 2:
                        puntos.append([float(val[1]), float(val[0])]) # Lat, Lon
                zonas.append({'nombre': nombre_txt, 'puntos': puntos})
    except Exception:
        pass # Fallo silencioso en KML para no detener la app
    return zonas

# -----------------------------------------------------------------------------
# 3. INTERFAZ PRINCIPAL
# -----------------------------------------------------------------------------

# Sidebar
with st.sidebar:
    st.title("📂 Panel de Control")
    st.markdown("---")
    uploaded_file = st.file_uploader("Cargar Datos (Excel/CSV)", type=['xlsx', 'csv'])
    uploaded_kml = st.file_uploader("Cargar Mapa (KML)", type=['kml', 'xml', 'txt'])
    
    st.markdown("---")
    st.info("💡 **Tip:** Asegúrate que tu Excel tenga columnas como 'Tipo', 'Poligono' y 'Estado_Salud'.")

# Main Content
st.title("🌲 Dashboard de Gestión Forestal")
st.markdown(f"**Cliente:** SOLEX Secure | **Proyecto:** Cerrito del Carmen")

if uploaded_file:
    df = load_data(uploaded_file)
    
    if df is not None:
        # --- FILA DE METRICAS (KPIs) ---
        # Se calculan dinámicamente según lo que haya en el Excel
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        total_arboles = len(df)
        
        # KPI 2: Salud
        if 'Estado_Salud' in df.columns:
            salud_ok = len(df[df['Estado_Salud'].astype(str).str.contains('Excelente|Bueno', case=False, na=False)])
            pct_salud = (salud_ok / total_arboles) * 100
            kpi2.metric("Tasa de Salud", f"{pct_salud:.1f}%", "Objetivo > 90%")
        else:
            kpi2.metric("Estado Salud", "N/D")

        # KPI 3: Especies
        if 'Tipo' in df.columns:
            num_especies = df['Tipo'].nunique()
            kpi3.metric("Variedad Especies", num_especies)
        else:
             kpi3.metric("Especies", "N/D")
             
        # KPI 1 y 4
        kpi1.metric("Total Especímenes", f"{total_arboles:,}")
        if 'Poligono' in df.columns:
            kpi4.metric("Zonas Activas", df['Poligono'].nunique())
        else:
            kpi4.metric("Zonas", "N/D")

        st.markdown("---")

        # --- PESTAÑAS DE CONTENIDO ---
        tab_dash, tab_bio, tab_map, tab_data = st.tabs([
            "📊 Resumen Ejecutivo", 
            "📏 Biometría & Crecimiento", 
            "🗺️ Mapa Geoespacial", 
            "📋 Base de Datos"
        ])

        # === 1. PESTAÑA RESUMEN ===
        with tab_dash:
            col_g1, col_g2 = st.columns([2, 1])
            
            with col_g1:
                st.subheader("Inventario por Especie y Zona")
                if 'Tipo' in df.columns and 'Poligono' in df.columns:
                    # Gráfico de barras apiladas profesional
                    fig_bar = px.histogram(df, x='Poligono', color='Tipo', 
                                           title="Distribución de Especies por Zona",
                                           barmode='group', text_auto=True,
                                           color_discrete_sequence=px.colors.qualitative.Prism)
                    fig_bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_bar, use_container_width=True)
                else:
                    st.warning("Faltan columnas 'Tipo' o 'Poligono' para este gráfico.")

            with col_g2:
                st.subheader("Estado Fitosanitario")
                if 'Estado_Salud' in df.columns:
                    # Gráfico de dona
                    fig_pie = px.donut(df, names='Estado_Salud', hole=0.4, 
                                       title="Salud General",
                                       color_discrete_sequence=['#4caf50', '#ffeb3b', '#f44336', '#9e9e9e'])
                    fig_pie.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.warning("Falta columna 'Estado_Salud'.")
            
            # Cronología (si hay fechas)
            if 'Fecha_Plantacion' in df.columns:
                st.subheader("Ritmo de Plantación")
                df_time = df.groupby('Fecha_Plantacion').size().reset_index(name='Cantidad')
                fig_line = px.line(df_time, x='Fecha_Plantacion', y='Cantidad', markers=True, 
                                   line_shape='spline', title="Histórico de Plantaciones")
                fig_line.update_traces(line_color='#2e7d32')
                st.plotly_chart(fig_line, use_container_width=True)

        # === 2. PESTAÑA BIOMETRÍA ===
        with tab_bio:
            st.subheader("Análisis de Desarrollo (Altura vs Diámetro)")
            col_b1, col_b2 = st.columns([3, 1])
            
            with col_b1:
                if 'Altura_cm' in df.columns and 'Diametro_cm' in df.columns:
                    # Scatter Plot Avanzado
                    fig_scatter = px.scatter(
                        df, x='Diametro_cm', y='Altura_cm',
                        color='Tipo' if 'Tipo' in df.columns else None,
                        size='Altura_cm', 
                        hover_data=df.columns,
                        title="Correlación de Crecimiento",
                        labels={'Diametro_cm': 'Diámetro (cm)', 'Altura_cm': 'Altura (cm)'}
                    )
                    st.plotly_chart(fig_scatter, use_container_width=True)
                else:
                    st.info("Esta sección requiere columnas numéricas 'Altura_cm' y 'Diametro_cm'.")

            with col_b2:
                st.markdown("#### Estadísticas Rápidas")
                if 'Altura_cm' in df.columns:
                    st.dataframe(df[['Altura_cm', 'Diametro_cm']].describe(), use_container_width=True)

        # === 3. PESTAÑA MAPA ===
        with tab_map:
            st.subheader("Georreferenciación")
            col_m1, col_m2 = st.columns([3, 1])
            
            with col_m1:
                if 'Coordenada_X' in df.columns and 'Coordenada_Y' in df.columns:
                    # Centro automático
                    lat_center = df['Coordenada_X'].mean() if not df['Coordenada_X'].isnull().all() else 21.23
                    lon_center = df['Coordenada_Y'].mean() if not df['Coordenada_Y'].isnull().all() else -100.46
                    
                    m = folium.Map(location=[lat_center, lon_center], zoom_start=18, tiles="OpenStreetMap")
                    
                    # 1. Dibujar Zonas (KML)
                    if uploaded_kml:
                        zonas = leer_kml(uploaded_kml)
                        colors = ['#1976D2', '#388E3C', '#FBC02D', '#D32F2F']
                        for i, z in enumerate(zonas):
                            folium.Polygon(
                                locations=z['puntos'],
                                color=colors[i % len(colors)],
                                fill=True, fill_opacity=0.1,
                                popup=z['nombre']
                            ).add_to(m)
                    
                    # 2. Dibujar Árboles
                    # Usamos dropna para evitar errores con filas vacías
                    df_map = df.dropna(subset=['Coordenada_X', 'Coordenada_Y'])
                    for _, row in df_map.iterrows():
                        # Lógica de color por salud
                        color = 'green'
                        estado = str(row.get('Estado_Salud', '')).lower()
                        if 'crítico' in estado or 'muerto' in estado: color = 'red'
                        elif 'regular' in estado: color = 'orange'
                        
                        folium.CircleMarker(
                            location=[row['Coordenada_X'], row['Coordenada_Y']],
                            radius=4,
                            color=color,
                            fill=True, fill_opacity=0.8,
                            tooltip=f"{row.get('Tipo','Arbol')} ({row.get('ID_Especimen','')})"
                        ).add_to(m)
                    
                    st_folium(m, width="100%", height=600)
                else:
                    st.warning("No se detectaron coordenadas GPS en el archivo.")

            with col_m2:
                st.markdown("**Leyenda de Mapa**")
                st.markdown("🟢 **Saludable:** Excelente/Bueno")
                st.markdown("🟠 **Alerta:** Regular/Estrés")
                st.markdown("🔴 **Crítico:** Plaga/Muerto")
                if uploaded_kml:
                    st.success("Capa de Polígonos KML activada.")

        # === 4. PESTAÑA DATOS ===
        with tab_data:
            st.subheader("Explorador de Datos")
            
            # Filtros dinámicos
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                if 'Tipo' in df.columns:
                    filtro_tipo = st.multiselect("Filtrar por Especie", df['Tipo'].unique())
            with col_f2:
                if 'Poligono' in df.columns:
                    filtro_zona = st.multiselect("Filtrar por Zona", df['Poligono'].unique())
            
            # Aplicar filtros
            df_view = df.copy()
            if 'Tipo' in df.columns and filtro_tipo:
                df_view = df_view[df_view['Tipo'].isin(filtro_tipo)]
            if 'Poligono' in df.columns and filtro_zona:
                df_view = df_view[df_view['Poligono'].isin(filtro_zona)]
            
            st.dataframe(df_view, use_container_width=True)
            
            # Descarga
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_view.to_excel(writer, index=False)
            st.download_button("💾 Descargar Datos Filtrados", data=output.getvalue(), file_name="Reporte_Reforestacion.xlsx")

else:
    # --- PANTALLA DE BIENVENIDA (ESTADO INICIAL) ---
    st.markdown("""
    <div style="text-align: center; padding: 50px; background-color: #f1f8e9; border-radius: 10px;">
        <h2 style="color: #2e7d32;">👋 Bienvenido al Sistema de Monitoreo</h2>
        <p>Por favor, carga tu archivo de datos en la barra lateral izquierda para generar el dashboard.</p>
        <p style="font-size: 0.9em; color: gray;">Formatos soportados: Excel (.xlsx), CSV (.csv) y Mapas (.kml)</p>
    </div>
    """, unsafe_allow_html=True)
