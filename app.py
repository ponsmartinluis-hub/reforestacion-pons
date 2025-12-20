import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, HeatMap, Fullscreen, MiniMap, MeasureControl
import xml.etree.ElementTree as ET
from io import BytesIO
import requests
import time
from datetime import datetime

# ==============================================================================
# 1. CONFIGURACIÓN INICIAL Y DE PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="SOLEX Forest Manager | Cerrito del Carmen",
    page_icon="🌵",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://www.solexsecure.com',
        'Report a bug': "mailto:support@solex.com",
        'About': "# Dashboard de Reforestación v6.0. Desarrollado para SOLEX Secure."
    }
)

# --- VARIABLES DE ENTORNO Y CONSTANTES ---
# AQUÍ ESTÁ EL ARREGLO: Apuntamos al archivo .txt que subiste
URL_GITHUB_EXCEL = "https://raw.githubusercontent.com/ponsmartinluis-hub/reforestacion-pons/main/plantacion.xlsx"
URL_GITHUB_KML = "https://raw.githubusercontent.com/ponsmartinluis-hub/reforestacion-pons/main/cerritodelcarmen.kml.txt"

# ==============================================================================
# 2. ESTILOS CSS AVANZADOS (CORPORATIVO & PREMIUM)
# ==============================================================================
st.markdown("""
<style>
    /* Importación de fuentes */
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&family=Montserrat:wght@600&display=swap');
    
    /* Reset y Estilos Globales */
    html, body, [class*="css"]  {
        font-family: 'Roboto', sans-serif;
        background-color: #f8f9fa;
        color: #1e293b;
    }
    
    /* Encabezados */
    h1 {
        font-family: 'Montserrat', sans-serif;
        color: #1b5e20;
        font-weight: 700;
        border-bottom: 3px solid #4caf50;
        padding-bottom: 15px;
        margin-bottom: 25px;
        letter-spacing: -0.5px;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }
    h2 {
        color: #2e7d32;
        font-weight: 600;
        margin-top: 30px;
        border-left: 5px solid #81c784;
        padding-left: 10px;
    }
    h3 {
        color: #388e3c;
        font-weight: 500;
    }

    /* Tarjetas de Métricas (KPIs) con Efecto Glassmorphism */
    div[data-testid="metric-container"] {
        background: rgba(255, 255, 255, 0.95);
        border: 1px solid #e2e8f0;
        padding: 20px;
        border-radius: 15px;
        border-top: 5px solid #2e7d32;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        transition: all 0.3s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 20px rgba(0, 0, 0, 0.1);
        border-top-color: #66bb6a;
    }
    div[data-testid="metric-container"] label {
        color: #64748b;
        font-size: 0.9rem;
    }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
        color: #0f172a;
        font-weight: 700;
    }

    /* Personalización de Pestañas (Tabs) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: #ffffff;
        padding: 10px 15px;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f1f8e9;
        border-radius: 8px;
        color: #33691e;
        font-weight: 600;
        border: 1px solid transparent;
        transition: all 0.2s;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #dcedc8;
        color: #1b5e20;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2e7d32 !important;
        color: #ffffff !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.15);
    }
    
    /* Botones Personalizados */
    .stButton>button {
        background: linear-gradient(135deg, #2e7d32 0%, #1b5e20 100%);
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.6rem 1.2rem;
        font-weight: 500;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: transform 0.1s;
    }
    .stButton>button:hover {
        transform: scale(1.02);
        box-shadow: 0 6px 8px rgba(0,0,0,0.15);
    }
    
    /* Ajustes para Mapas y Dataframes */
    iframe {
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border: 1px solid #e0e0e0;
    }
    [data-testid="stDataFrame"] {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* Alertas y Mensajes */
    .stAlert {
        border-radius: 8px;
        border-left: 5px solid rgba(0,0,0,0.2);
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 3. LÓGICA DE NEGOCIO Y PROCESAMIENTO DE DATOS (ETL)
# ==============================================================================

def safe_float_convert(value):
    """Intenta convertir a float de forma segura, retornando None si falla."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

@st.cache_data(ttl=300, show_spinner=False)
def load_data_engine(source, is_url=False):
    """
    Motor principal de carga de datos.
    Soporta Excel (.xlsx) y CSV (.csv).
    Realiza limpieza profunda de nombres de columnas y tipos de datos.
    """
    df = None
    try:
        if is_url:
            # Petición HTTP con timeout para evitar bloqueos
            response = requests.get(source, timeout=10)
            response.raise_for_status()
            file_content = BytesIO(response.content)
            df = pd.read_excel(file_content)
        else:
            # Carga local
            if source.name.endswith('.csv'):
                df = pd.read_csv(source)
            else:
                df = pd.read_excel(source)

        if df is not None:
            # 1. Limpieza de Cabeceras (Trim, Remove special chars)
            df.columns = df.columns.str.strip().str.replace(r'[,.:]', '', regex=True)
            
            # 2. Eliminación de Duplicados (Columnas repetidas por error en Excel)
            df = df.loc[:, ~df.columns.duplicated()]

            # 3. Conversión de Tipos (Casteo explícito)
            numeric_cols = ['Coordenada_X', 'Coordenada_Y', 'Altura_cm', 'Diametro_cm', 'Costo', 'Edad_Meses']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 4. Formateo de Textos
            if 'Estado_Salud' in df.columns:
                df['Estado_Salud'] = df['Estado_Salud'].astype(str).str.strip().str.capitalize()
            
            if 'Tipo' in df.columns:
                 df['Tipo'] = df['Tipo'].astype(str).str.strip()

            # 5. Validación de Coordenadas (Limpieza de ceros o nulos)
            if 'Coordenada_X' in df.columns:
                df = df[df['Coordenada_X'].notna()]
                
            return df

    except Exception as e:
        st.error(f"Error crítico en el motor de datos: {str(e)}")
        return None

@st.cache_data(ttl=600, show_spinner=False)
def load_kml_raw_content(url):
    """Descarga el contenido KML crudo desde GitHub."""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return BytesIO(response.content)
        else:
            st.sidebar.error(f"Error HTTP {response.status_code} al descargar mapa.")
            return None
    except Exception as e:
        st.sidebar.error(f"Error de conexión KML: {e}")
        return None

def parse_kml_zones(kml_bytes):
    """
    Parser robusto para KML.
    Maneja XML namespaces y busca coordenadas anidadas profundamente.
    """
    zonas = []
    if kml_bytes is None:
        return zonas
    
    try:
        kml_bytes.seek(0)
        content = kml_bytes.read()
        
        # Intentar decodificar con utf-8, fallback a latin-1
        try:
            xml_string = content.decode('utf-8')
        except UnicodeDecodeError:
            xml_string = content.decode('latin-1')
            
        root = ET.fromstring(xml_string)
        
        # Definir namespaces comunes (Google Earth usa kml 2.2)
        namespaces = {
            'k': 'http://www.opengis.net/kml/2.2',
            'gx': 'http://www.google.com/kml/ext/2.2'
        }
        
        # Búsqueda agnóstica de Placemarks (con y sin namespace)
        placemarks = root.findall('.//k:Placemark', namespaces)
        if not placemarks:
            placemarks = root.findall('.//Placemark') # Intento sin namespace explícito
            
        for pm in placemarks:
            # 1. Extraer Nombre
            name_node = pm.find('.//k:name', namespaces)
            if name_node is None: name_node = pm.find('.//name')
            
            zone_name = name_node.text if name_node is not None else "Zona Desconocida"
            
            # 2. Extraer Polígono (Coordinates)
            coords_node = pm.find('.//k:coordinates', namespaces)
            if coords_node is None: coords_node = pm.find('.//coordinates')
            
            if coords_node is not None and coords_node.text:
                raw_coords = coords_node.text.strip().split()
                points = []
                for c in raw_coords:
                    parts = c.split(',')
                    if len(parts) >= 2:
                        # IMPORTANTE: KML usa (Lon, Lat), Folium necesita (Lat, Lon)
                        lon = float(parts[0])
                        lat = float(parts[1])
                        points.append([lat, lon])
                
                # Validar que sea un polígono (mínimo 3 puntos)
                if len(points) > 2:
                    zonas.append({'name': zone_name, 'points': points})
                    
    except ET.ParseError as e:
        st.sidebar.warning(f"Error parseando XML del KML: {e}")
    except Exception as e:
        st.sidebar.warning(f"Error procesando zonas KML: {e}")
        
    return zonas

def generate_text_report(df):
    """Genera un reporte narrativo basado en los datos actuales."""
    if df is None or df.empty: return "No hay datos disponibles para generar el reporte."
    
    total = len(df)
    zonas = df['Poligono'].nunique() if 'Poligono' in df.columns else 0
    especies = df['Tipo'].nunique() if 'Tipo' in df.columns else 0
    
    # Salud
    salud_txt = "datos no disponibles"
    if 'Estado_Salud' in df.columns:
        salud_counts = df['Estado_Salud'].value_counts()
        top_salud = salud_counts.idxmax()
        pct_top = (salud_counts.max() / total) * 100
        salud_txt = f"El estado predominante es **{top_salud}** ({pct_top:.1f}%)."

    report = f"""
    **RESUMEN EJECUTIVO AUTOMATIZADO**
    
    A fecha de **{datetime.now().strftime('%d/%m/%Y')}**, el proyecto "Cerrito del Carmen" gestiona un inventario biológico de **{total:,.0f} especímenes**.
    La reforestación se distribuye a lo largo de **{zonas} zonas geográficas** (polígonos), integrando una biodiversidad de **{especies} especies distintas**.
    
    **Análisis Fitosanitario:**
    {salud_txt}
    """
    return report

# ==============================================================================
# 4. BARRA LATERAL (SIDEBAR) Y CONTROLES
# ==============================================================================

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3028/3028569.png", width=90) # Cactus Icon
    st.title("SOLEX Control")
    st.markdown("---")
    
    # --- SECCIÓN DE CONEXIÓN ---
    st.header("📡 Conectividad")
    conn_mode = st.radio(
        "Fuente de Datos:", 
        ["Nube GitHub (Auto)", "Carga Manual"], 
        index=0,
        help="Usa 'Nube' para sincronizar con el repositorio oficial."
    )
    
    data_source = None
    kml_source = None
    is_url_flag = False
    
    if conn_mode == "Nube GitHub (Auto)":
        data_source = URL_GITHUB_EXCEL
        # Intentamos cargar el KML automáticamente desde la URL corregida
        kml_content_bytes = load_kml_raw_content(URL_GITHUB_KML)
        is_url_flag = True
        st.success("🟢 Sistema Online")
        st.caption("Sincronizando con repositorio...")
    else:
        st.info("Modo Local Activado")
        data_source = st.file_uploader("1. Excel de Datos (.xlsx)", type=['xlsx', 'csv'])
        kml_uploaded = st.file_uploader("2. Mapa de Zonas (.kml)", type=['kml', 'xml', 'txt'])
        if kml_uploaded:
            kml_content_bytes = kml_uploaded # Ya es BytesIO
        else:
            kml_content_bytes = None
        is_url_flag = False

    st.markdown("---")
    
    # --- SECCIÓN DE FILTROS ---
    st.header("🔍 Segmentación")
    st.caption("Los filtros afectan a todos los gráficos.")
    
    # Placeholders para filtros dinámicos
    filter_container = st.container()

    st.markdown("---")
    st.markdown("### ℹ️ Acerca de")
    st.caption("**Versión:** 6.0.2 LTS")
    st.caption("**Cliente:** SOLEX Secure")
    st.caption("**Dev:** Pons & Gemini")

# ==============================================================================
# 5. CARGA Y PROCESAMIENTO PRINCIPAL
# ==============================================================================

if data_source:
    with st.spinner("Procesando ecosistema de datos..."):
        # Carga de Datos Tabulares
        df_raw = load_data_engine(data_source, is_url=is_url_flag)
        
        # Procesamiento de Mapa (Polígonos)
        map_zones = []
        if kml_content_bytes:
            map_zones = parse_kml_zones(kml_content_bytes)
else:
    df_raw = None

# ==============================================================================
# 6. DASHBOARD INTERACTIVO
# ==============================================================================

if df_raw is not None:
    
    # --- RENDERIZADO DE FILTROS DINÁMICOS ---
    with filter_container:
        # Filtro de Especies
        if 'Tipo' in df_raw.columns:
            available_species = sorted(df_raw['Tipo'].astype(str).unique())
            selected_species = st.multiselect("Especies:", available_species, default=available_species)
        else:
            selected_species = []
            
        # Filtro de Polígonos
        if 'Poligono' in df_raw.columns:
            available_zones = sorted(df_raw['Poligono'].astype(str).unique())
            selected_zones = st.multiselect("Zonas:", available_zones, default=available_zones)
        else:
            selected_zones = []

    # --- APLICACIÓN DE FILTROS AL DATAFRAME ---
    df = df_raw.copy()
    if selected_species and 'Tipo' in df.columns:
        df = df[df['Tipo'].isin(selected_species)]
    if selected_zones and 'Poligono' in df.columns:
        df = df[df['Poligono'].isin(selected_zones)]

    # --- CABECERA PRINCIPAL ---
    st.title("🌵 Monitor de Reforestación: Cerrito del Carmen")
    st.markdown("**Plataforma Integral de Gestión Biológica y Financiera**")

    # --- INDICADORES CLAVE (KPIs) ---
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    
    total_trees = len(df)
    
    # Cálculo seguro de Salud
    salud_pct = 0
    if 'Estado_Salud' in df.columns:
        good_health = df['Estado_Salud'].str.contains('Excelente|Bueno', case=False, na=False).sum()
        salud_pct = (good_health / total_trees * 100) if total_trees > 0 else 0
        
    # Cálculo seguro de Altura
    avg_height = 0
    if 'Altura_cm' in df.columns:
        avg_height = df['Altura_cm'].mean()

    col_kpi1.metric("Inventario Total", f"{total_trees:,.0f}", delta="Especímenes")
    col_kpi2.metric("Índice de Supervivencia", f"{salud_pct:.1f}%", delta="Meta > 90%", delta_color="normal")
    col_kpi3.metric("Altura Promedio", f"{avg_height:.1f} cm", delta="Crecimiento")
    col_kpi4.metric("Zonas Activas", f"{len(map_zones)} Polígonos" if map_zones else "Sin Mapa")

    # --- ESTRUCTURA DE PESTAÑAS (TABS) ---
    tab_dash, tab_map, tab_bio, tab_roi, tab_data = st.tabs([
        "📊 Dashboard Ejecutivo", 
        "🗺️ Mapa Inteligente", 
        "📏 Biometría", 
        "💰 Finanzas (ROI)", 
        "📝 Base de Datos"
    ])

    # --------------------------------------------------------------------------
    # TAB 1: DASHBOARD EJECUTIVO
    # --------------------------------------------------------------------------
    with tab_dash:
        col_d1, col_d2 = st.columns([2, 1])
        
        with col_d1:
            st.subheader("Distribución Jerárquica del Ecosistema")
            if 'Poligono' in df.columns and 'Tipo' in df.columns:
                path_cols = ['Poligono', 'Tipo']
                if 'Estado_Salud' in df.columns: path_cols.append('Estado_Salud')
                
                fig_sun = px.sunburst(
                    df, 
                    path=path_cols,
                    title="Niveles: Zona > Especie > Estado (Interactivo)",
                    color_discrete_sequence=px.colors.qualitative.Prism,
                    height=500
                )
                st.plotly_chart(fig_sun, use_container_width=True)
            else:
                st.info("Faltan columnas 'Poligono' o 'Tipo' para generar el gráfico jerárquico.")

        with col_d2:
            st.subheader("Estado Fitosanitario Global")
            if 'Estado_Salud' in df.columns:
                fig_pie = px.pie(
                    df, 
                    names='Estado_Salud', 
                    hole=0.5,
                    title="Proporción de Salud",
                    color_discrete_sequence=px.colors.sequential.Greens_r
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(showlegend=False)
                st.plotly_chart(fig_pie, use_container_width=True)
                
                # Tabla Resumen
                st.markdown("##### Detalle Numérico")
                summary_table = df['Estado_Salud'].value_counts().reset_index()
                summary_table.columns = ['Estado', 'Cantidad']
                st.dataframe(summary_table, use_container_width=True, hide_index=True)
        
        st.divider()
        st.info(generate_text_report(df))

    # --------------------------------------------------------------------------
    # TAB 2: MAPA INTELIGENTE (POLÍGONOS + PUNTOS)
    # --------------------------------------------------------------------------
    with tab_map:
        st.subheader("Georreferenciación de Zonas y Especímenes")
        
        c_map_controls, c_map_view = st.columns([1, 4])
        
        with c_map_controls:
            st.markdown("### Capas")
            show_polys = st.toggle("Mostrar Zonas (Polígonos)", value=True)
            show_heat = st.toggle("Mapa de Calor", value=False)
            show_clusters = st.toggle("Agrupar Puntos (Clusters)", value=True)
            
            st.markdown("### Leyenda")
            st.markdown("🟢 **Excelente**")
            st.markdown("🟡 **Regular/Estrés**")
            st.markdown("🔴 **Crítico/Muerto**")
            
            if map_zones:
                st.success(f"✅ {len(map_zones)} zonas cargadas del KML.")
            else:
                st.warning("⚠️ No se detectaron zonas en el KML.")

        with c_map_view:
            if 'Coordenada_X' in df.columns and 'Coordenada_Y' in df.columns:
                # Centro dinámico del mapa
                lat_center = df['Coordenada_X'].mean() if not df.empty else 21.23
                lon_center = df['Coordenada_Y'].mean() if not df.empty else -100.46
                
                m = folium.Map(location=[lat_center, lon_center], zoom_start=17, tiles="OpenStreetMap")
                
                # Plugins de Folium
                Fullscreen().add_to(m)
                MeasureControl(position='topright').add_to(m)
                MiniMap(toggle_display=True).add_to(m)
                
                # 1. CAPA DE POLÍGONOS (ZONAS KML)
                if show_polys and map_zones:
                    colors_poly = ['#3388ff', '#ff33bb', '#33ff57', '#ff9933', '#6600cc']
                    for i, zone in enumerate(map_zones):
                        c = colors_poly[i % len(colors_poly)]
                        folium.Polygon(
                            locations=zone['points'],
                            tooltip=zone['name'],
                            popup=f"<b>Zona:</b> {zone['name']}",
                            color=c,
                            fill=True,
                            fill_opacity=0.15,
                            weight=2
                        ).add_to(m)

                # 2. CAPA DE MAPA DE CALOR
                df_geo = df.dropna(subset=['Coordenada_X', 'Coordenada_Y'])
                if show_heat and not df_geo.empty:
                    heat_data = [[row['Coordenada_X'], row['Coordenada_Y']] for idx, row in df_geo.iterrows()]
                    HeatMap(heat_data, radius=15, blur=10).add_to(m)

                # 3. CAPA DE PUNTOS (CLUSTER O INDIVIDUAL)
                marker_group = MarkerCluster().add_to(m) if show_clusters else m
                
                for _, row in df_geo.iterrows():
                    # Lógica de Color
                    status = str(row.get('Estado_Salud', '')).lower()
                    if 'crítico' in status or 'muerto' in status:
                        icon_color = 'red'
                        icon_icon = 'times'
                    elif 'regular' in status or 'estrés' in status:
                        icon_color = 'orange'
                        icon_icon = 'exclamation'
                    else:
                        icon_color = 'green'
                        icon_icon = 'leaf'
                        
                    html_popup = f"""
                    <div style='font-family:sans-serif; min-width:120px'>
                        <h5 style='margin:0'>{row.get('ID_Especimen','ID')}</h5>
                        <hr style='margin:5px 0'>
                        <b>Tipo:</b> {row.get('Tipo','-')}<br>
                        <b>Salud:</b> {row.get('Estado_Salud','-')}<br>
                        <b>Zona:</b> {row.get('Poligono','-')}
                    </div>
                    """
                    
                    folium.Marker(
                        location=[row['Coordenada_X'], row['Coordenada_Y']],
                        popup=folium.Popup(html_popup, max_width=200),
                        tooltip=f"{row.get('Tipo')}",
                        icon=folium.Icon(color=icon_color, icon=icon_icon, prefix='fa')
                    ).add_to(marker_group)

                st_folium(m, width="100%", height=650)
            else:
                st.error("No se encontraron columnas de coordenadas (Coordenada_X, Coordenada_Y) en el Excel.")

    # --------------------------------------------------------------------------
    # TAB 3: BIOMETRÍA AVANZADA
    # --------------------------------------------------------------------------
    with tab_bio:
        st.subheader("Análisis Biométrico de Crecimiento")
        
        if 'Altura_cm' in df.columns and 'Diametro_cm' in df.columns:
            col_b1, col_b2 = st.columns([3, 1])
            
            with col_b1:
                # --- VERIFICACIÓN DE LIBRERÍA DE TENDENCIAS ---
                trend_mode = None
                try:
                    import statsmodels
                    trend_mode = "ols"
                except ImportError:
                    trend_mode = None
                    # Notificación discreta
                    if 'stats_warn' not in st.session_state:
                        st.toast("Librería 'statsmodels' no instalada. Tendencias desactivadas.", icon="ℹ️")
                        st.session_state['stats_warn'] = True
                
                fig_scatter = px.scatter(
                    df, 
                    x='Diametro_cm', 
                    y='Altura_cm',
                    color='Tipo' if 'Tipo' in df.columns else None,
                    size='Altura_cm',
                    hover_data=df.columns,
                    trendline=trend_mode,
                    title="Relación Alométrica: Diámetro vs Altura",
                    labels={'Diametro_cm': 'Diámetro de Tallo (cm)', 'Altura_cm': 'Altura Total (cm)'}
                )
                st.plotly_chart(fig_scatter, use_container_width=True)
            
            with col_b2:
                st.markdown("#### Estadísticas Rápidas")
                desc = df[['Altura_cm', 'Diametro_cm']].describe()
                st.dataframe(desc, use_container_width=True)
                
            st.divider()
            
            # Histograma de Distribución
            fig_hist = px.histogram(
                df, 
                x='Altura_cm', 
                color='Tipo' if 'Tipo' in df.columns else None,
                nbins=30,
                title="Distribución de Tamaños en la Plantación",
                marginal="box", # Muestra boxplot arriba
                opacity=0.7
            )
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.warning("Se requieren columnas numéricas 'Altura_cm' y 'Diametro_cm' para este análisis.")

    # --------------------------------------------------------------------------
    # TAB 4: SIMULADOR FINANCIERO (ROI)
    # --------------------------------------------------------------------------
    with tab_roi:
        st.subheader("💰 Proyección Financiera de Negocio")
        st.markdown("Simulador para especies productivas (Ej. Agave/Maguey) basado en el inventario actual.")
        
        col_input, col_graph = st.columns([1, 2])
        
        with col_input:
            with st.expander("⚙️ Parámetros del Modelo", expanded=True):
                st.markdown("**Costos (Output)**")
                cost_plant = st.number_input("Costo Plantación ($/u)", 60.0, step=5.0)
                cost_maint = st.number_input("Mantenimiento Anual ($/u)", 25.0, step=5.0)
                
                st.markdown("**Ingresos (Input)**")
                price_sale = st.number_input("Precio Venta ($/u)", 950.0, step=50.0)
                years = st.slider("Años a Cosecha", 4, 12, 7)
                risk_pct = st.slider("Riesgo/Merma (%)", 0, 50, 15) / 100
        
        with col_graph:
            # Identificar plantas productivas
            if 'Tipo' in df.columns:
                # Busca palabras clave
                mask_prod = df['Tipo'].str.contains("Maguey|Agave|Mezquite", case=False, na=False)
                df_prod = df[mask_prod]
                n_plants = len(df_prod)
                
                if n_plants > 0:
                    st.success(f"Modelo aplicado a **{n_plants}** unidades productivas.")
                else:
                    st.warning("No se detectaron especies productivas. Usando total del inventario.")
                    n_plants = total_trees
            else:
                n_plants = total_trees
            
            if n_plants > 0:
                # Cálculos
                capex = n_plants * cost_plant
                opex = n_plants * cost_maint * years
                total_cost = capex + opex
                
                final_plants = n_plants * (1 - risk_pct)
                revenue = final_plants * price_sale
                
                profit = revenue - total_cost
                roi = (profit / total_cost) * 100 if total_cost > 0 else 0
                
                # Métricas Financieras
                m1, m2, m3 = st.columns(3)
                m1.metric("Costo Total", f"${total_cost:,.0f}", help="Inversión + Mantenimiento")
                m2.metric("Venta Proyectada", f"${revenue:,.0f}", help="Ingreso Bruto")
                m3.metric("Utilidad Neta", f"${profit:,.0f}", delta=f"ROI: {roi:.1f}%")
                
                # Gráfico Waterfall (Cascada)
                fig_water = go.Figure(go.Waterfall(
                    orientation = "v",
                    measure = ["relative", "relative", "total", "relative", "total"],
                    x = ["Inversión Inicial", "Mantenimiento", "Costo Acumulado", "Venta Cosecha", "Ganancia Final"],
                    textposition = "outside",
                    text = [f"-{capex/1000:.0f}k", f"-{opex/1000:.0f}k", "", f"+{revenue/1000:.0f}k", f"{profit/1000:.0f}k"],
                    y = [-capex, -opex, 0, revenue, 0],
                    connector = {"line":{"color":"rgb(63, 63, 63)"}},
                    decreasing = {"marker":{"color":"#ef5350"}},
                    increasing = {"marker":{"color":"#66bb6a"}},
                    totals = {"marker":{"color":"#42a5f5"}}
                ))
                fig_water.update_layout(title="Flujo de Caja del Proyecto", height=450)
                st.plotly_chart(fig_water, use_container_width=True)

    # --------------------------------------------------------------------------
    # TAB 5: EDITOR DE DATOS Y DESCARGA
    # --------------------------------------------------------------------------
    with tab_data:
        st.subheader("📝 Gestión de Base de Datos")
        st.markdown("Edición en tiempo real para correcciones rápidas. Los cambios son temporales en esta sesión.")
        
        # Editor Interactivo
        df_editor = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Estado_Salud": st.column_config.SelectboxColumn(
                    "Salud",
                    options=["Excelente", "Bueno", "Regular", "Estrés Hídrico", "Plaga", "Crítico", "Muerto"],
                    required=True
                ),
                "Altura_cm": st.column_config.NumberColumn(
                    "Altura",
                    min_value=0,
                    max_value=2000,
                    format="%.0f cm"
                ),
                "Coordenada_X": st.column_config.NumberColumn("Latitud", format="%.6f"),
                "Coordenada_Y": st.column_config.NumberColumn("Longitud", format="%.6f"),
            },
            height=500
        )
        
        st.divider()
        
        col_down1, col_down2 = st.columns([3, 1])
        with col_down1:
            st.caption(f"Mostrando {len(df_editor)} registros. Usa el botón de descarga para guardar cambios.")
        
        with col_down2:
            # Generador de Excel
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_editor.to_excel(writer, index=False, sheet_name='Plantacion_Editada')
            
            st.download_button(
                label="📥 Descargar Excel",
                data=buffer.getvalue(),
                file_name=f"Plantacion_Cerrito_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

else:
    # Pantalla de Carga Inicial
    st.markdown("""
    <div style='text-align: center; margin-top: 50px;'>
        <h2>⏳ Estableciendo Conexión Segura...</h2>
        <p>Sincronizando con SOLEX GitHub Repository</p>
        <p style='color:gray; font-size:0.8em'>Si esto demora, verifica tu conexión a internet.</p>
    </div>
    """, unsafe_allow_html=True)
