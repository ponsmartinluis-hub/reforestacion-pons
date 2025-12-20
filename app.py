import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, HeatMap, Fullscreen, MiniMap
import xml.etree.ElementTree as ET
from io import BytesIO
import requests
import time

# ==============================================================================
# 1. CONFIGURACIÓN DEL SISTEMA Y ESTILOS
# ==============================================================================
st.set_page_config(
    page_title="SOLEX Forest Manager | Cerrito del Carmen",
    page_icon="🌵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONFIGURACIÓN DE ENLACES (GITHUB) ---
# Excel de Datos
URL_GITHUB_DEFAULT = "https://raw.githubusercontent.com/ponsmartinluis-hub/reforestacion-pons/main/plantacion.xlsx"
# Archivo KML de Polígonos (Asumimos este nombre, si cambia en tu repo, edítalo aquí)
URL_KML_DEFAULT = "https://raw.githubusercontent.com/ponsmartinluis-hub/reforestacion-pons/main/cerritodelcarmen.kml"

# Estilos CSS Avanzados para "Look & Feel" Corporativo
st.markdown("""
<style>
    /* Tipografía y Fondo General */
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Roboto', sans-serif;
        background-color: #f4f6f9;
        color: #2c3e50;
    }
    
    /* Encabezados y Títulos */
    h1 { color: #1b5e20; font-weight: 700; border-bottom: 3px solid #a5d6a7; padding-bottom: 10px; letter-spacing: -0.5px; }
    h2 { color: #2e7d32; margin-top: 25px; font-weight: 600; }
    h3 { color: #388e3c; font-weight: 500; }

    /* Tarjetas de Métricas (KPIs) - Efecto Glassmorphism sutil */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 20px;
        border-radius: 12px;
        border-left: 6px solid #2e7d32;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.1);
        border-left-color: #66bb6a;
    }

    /* Pestañas (Tabs) Personalizadas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #ffffff;
        padding: 10px 15px;
        border-radius: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.03);
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f1f8e9;
        border-radius: 8px;
        color: #33691e;
        font-weight: 600;
        border: 1px solid transparent;
    }
    .stTabs [aria-selected="true"] {
        background-color: #33691e !important;
        color: #ffffff !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
    }
    
    /* Botones Interactivos */
    .stButton>button {
        background-color: #2e7d32;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 500;
        transition: background-color 0.2s;
    }
    .stButton>button:hover {
        background-color: #1b5e20;
    }
    
    /* Ajustes para el Mapa */
    iframe {
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. FUNCIONES DE PROCESAMIENTO DE DATOS (ETL)
# ==============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_and_clean_data(source, is_url=False):
    """
    Carga datos desde URL o archivo local, limpia nombres de columnas,
    elimina duplicados y convierte tipos de datos.
    """
    try:
        if is_url:
            response = requests.get(source)
            response.raise_for_status()
            file_content = BytesIO(response.content)
            df = pd.read_excel(file_content)
        else:
            if source.name.endswith('.csv'):
                df = pd.read_csv(source)
            else:
                df = pd.read_excel(source)

        # 1. Normalización de Nombres de Columna
        # Elimina espacios, puntos, comas, dos puntos y convierte a título
        df.columns = df.columns.str.strip().str.replace(r'[,.:]', '', regex=True)
        
        # 2. Eliminación de Columnas Duplicadas
        df = df.loc[:, ~df.columns.duplicated()]

        # 3. Conversión de Tipos Numéricos
        numeric_cols = ['Coordenada_X', 'Coordenada_Y', 'Altura_cm', 'Diametro_cm', 'Costo', 'Edad_Meses']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 4. Estandarización de Texto
        if 'Estado_Salud' in df.columns:
            df['Estado_Salud'] = df['Estado_Salud'].astype(str).str.capitalize()

        return df
    except Exception as e:
        st.error(f"Error cargando datos principales: {str(e)}")
        return None

@st.cache_data(ttl=600, show_spinner=False)
def load_kml_content(source, is_url=False):
    """Descarga o lee el contenido KML en bytes"""
    try:
        if is_url:
            response = requests.get(source)
            if response.status_code == 200:
                return BytesIO(response.content)
            else:
                return None
        else:
            return source # Ya es un archivo subido
    except Exception:
        return None

def process_kml_polygons(kml_bytes_io):
    """
    Parsea archivos KML para extraer coordenadas de polígonos.
    Soporta BytesIO directo.
    """
    zonas = []
    if kml_bytes_io is None:
        return zonas
        
    try:
        # Reiniciar puntero si es necesario
        kml_bytes_io.seek(0)
        content = kml_bytes_io.read()
        # Decodificación segura
        try:
            xml_str = content.decode("utf-8")
        except UnicodeDecodeError:
            xml_str = content.decode("latin-1") # Fallback
            
        root = ET.fromstring(xml_str)
        # Namespaces comunes en Google Earth / GIS
        namespaces = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        # Búsqueda recursiva de Placemarks
        # Intentamos con namespace y sin él para máxima compatibilidad
        placemarks = root.findall('.//kml:Placemark', namespaces)
        if not placemarks:
            placemarks = root.findall('.//{http://www.opengis.net/kml/2.2}Placemark')
            
        for placemark in placemarks:
            # Obtener Nombre
            name_tag = placemark.find('.//kml:name', namespaces)
            if name_tag is None:
                name_tag = placemark.find('.//{http://www.opengis.net/kml/2.2}name')
            name = name_tag.text if name_tag is not None else "Polígono Sin Nombre"
            
            # Obtener Coordenadas
            coord_tag = placemark.find('.//kml:coordinates', namespaces)
            if coord_tag is None:
                coord_tag = placemark.find('.//{http://www.opengis.net/kml/2.2}coordinates')
                
            if coord_tag is not None and coord_tag.text:
                coords_str = coord_tag.text.strip().split()
                points = []
                for c in coords_str:
                    parts = c.split(',')
                    if len(parts) >= 2:
                        # KML estándar es (Lon, Lat) -> Folium requiere (Lat, Lon)
                        points.append([float(parts[1]), float(parts[0])])
                
                # Solo agregar si tiene puntos válidos
                if len(points) > 2:
                    zonas.append({'name': name, 'points': points})
                    
    except Exception as e:
        st.warning(f"Error procesando estructura KML: {e}")
    return zonas

def generate_report(df):
    """Genera un resumen textual para ejecutivos"""
    total = len(df)
    if total == 0: return "Sin datos."
    
    salud = df['Estado_Salud'].value_counts() if 'Estado_Salud' in df.columns else pd.Series()
    top_salud = salud.idxmax() if not salud.empty else "N/D"
    pct_salud = (salud.max() / total * 100) if not salud.empty else 0
    
    zonas = df['Poligono'].nunique() if 'Poligono' in df.columns else 0
    
    texto = f"""
    **INFORME EJECUTIVO - CERRITO DEL CARMEN**
    
    El proyecto cuenta actualmente con un inventario activo de **{total:,} especímenes**. 
    La operación de reforestación abarca **{zonas} zonas (polígonos)** diferenciadas geográficamente.
    
    **Diagnóstico Fitosanitario:**
    El estado de salud predominante en la plantación es **{top_salud}**, el cual representa el **{pct_salud:.1f}%** de la población total monitoreada.
    """
    return texto

# ==============================================================================
# 3. SIDEBAR Y FILTROS GLOBALES
# ==============================================================================

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3028/3028569.png", width=90) # Icono de Agave/Cactus
    st.title("Panel de Control")
    st.markdown("---")
    
    # 3.1 Selector de Fuente
    st.subheader("📡 Conexión de Datos")
    source_mode = st.radio("Modo de operación:", ["GitHub (Automático)", "Carga Manual"], index=0)
    
    # Lógica de Selección de Fuentes
    if source_mode == "GitHub (Automático)":
        data_source = URL_GITHUB_DEFAULT
        kml_source = URL_KML_DEFAULT
        is_url_flag = True
        st.success(f"🟢 Nube conectada")
        st.caption("Sincronizando Excel y KML desde repositorio oficial.")
    else:
        data_source = st.file_uploader("1. Subir Excel/CSV Plantación", type=['xlsx', 'csv'])
        kml_source = st.file_uploader("2. Subir Mapa Polígonos (KML)", type=['kml', 'xml'])
        is_url_flag = False

    st.markdown("---")
    st.info("v4.0.0 (Map Layers) | SOLEX Secure")

# ==============================================================================
# 4. LÓGICA PRINCIPAL (MAIN LOOP)
# ==============================================================================

# Carga de datos principales
if data_source:
    with st.spinner('Procesando datos del ecosistema...'):
        df_raw = load_and_clean_data(data_source, is_url=is_url_flag)
        
        # Carga de Polígonos (KML) en paralelo si existe fuente
        kml_data_obj = None
        if kml_source:
            kml_data_obj = load_kml_content(kml_source, is_url=is_url_flag)
else:
    df_raw = None

if df_raw is not None:
    # --- FILTROS DINÁMICOS EN SIDEBAR ---
    with st.sidebar:
        st.subheader("🔍 Filtros de Visualización")
        
        # Filtro Especie
        if 'Tipo' in df_raw.columns:
            all_species = sorted(df_raw['Tipo'].astype(str).unique())
            sel_species = st.multiselect("Filtrar Especie:", all_species, default=all_species)
        else:
            sel_species = []
            
        # Filtro Salud
        if 'Estado_Salud' in df_raw.columns:
            all_health = sorted(df_raw['Estado_Salud'].astype(str).unique())
            sel_health = st.multiselect("Filtrar Salud:", all_health, default=all_health)
        else:
            sel_health = []
            
        if st.button("Restablecer Filtros"):
            st.rerun()

    # APLICAR FILTROS
    df = df_raw.copy()
    if sel_species:
        df = df[df['Tipo'].astype(str).isin(sel_species)]
    if sel_health:
        df = df[df['Estado_Salud'].astype(str).isin(sel_health)]
    
    # --- ENCABEZADO Y KPIS ---
    st.title("🌵 Monitor de Reforestación: Cerrito del Carmen")
    st.markdown("**Sistema Integrado de Gestión Forestal y Financiera**")
    
    # Fila de Métricas
    k1, k2, k3, k4 = st.columns(4)
    
    total_trees = len(df)
    
    # KPI Salud
    if 'Estado_Salud' in df.columns:
        saludables = df['Estado_Salud'].astype(str).str.contains('Excelente|Bueno', case=False, na=False).sum()
        pct_salud = (saludables / total_trees * 100) if total_trees > 0 else 0
        delta_salud = "✅ Meta Cumplida" if pct_salud >= 90 else "⚠️ Atención Requerida"
        k2.metric("Índice de Salud", f"{pct_salud:.1f}%", delta_salud)
    else:
        k2.metric("Índice de Salud", "N/D")

    # KPI Altura
    if 'Altura_cm' in df.columns:
        avg_height = df['Altura_cm'].mean()
        k3.metric("Altura Promedio", f"{avg_height:.1f} cm")
    else:
        k3.metric("Altura Promedio", "N/D")

    # KPI Diversidad
    if 'Tipo' in df.columns:
        diversity = df['Tipo'].nunique()
        k4.metric("Variedad Especies", diversity)
    else:
        k4.metric("Especies", "0")
        
    k1.metric("Inventario Total", f"{total_trees:,}", "Plantas Activas")

    # --- PESTAÑAS DE CONTENIDO ---
    tab_dash, tab_map, tab_bio, tab_roi, tab_data = st.tabs([
        "📊 Dashboard Ejecutivo",
        "🗺️ Mapa Inteligente de Zonas",
        "📏 Biometría",
        "💰 Simulador Financiero",
        "📝 Editor de Datos"
    ])

    # === TAB 1: DASHBOARD EJECUTIVO ===
    with tab_dash:
        col_d1, col_d2 = st.columns([2, 1])
        
        with col_d1:
            st.subheader("Distribución Jerárquica de Inventario")
            if 'Poligono' in df.columns and 'Tipo' in df.columns:
                # Sunburst Chart (Interactiva y Jerárquica)
                path_cols = ['Poligono', 'Tipo']
                if 'Estado_Salud' in df.columns: path_cols.append('Estado_Salud')
                
                fig_sun = px.sunburst(
                    df, path=path_cols,
                    title="Exploración: Zona > Especie > Estado (Click para profundizar)",
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_sun.update_layout(height=500, margin=dict(t=30, l=0, r=0, b=0))
                st.plotly_chart(fig_sun, use_container_width=True)
            else:
                st.warning("Se requieren columnas 'Poligono' y 'Tipo' para visualizar la jerarquía.")

        with col_d2:
            st.subheader("Resumen Fitosanitario")
            if 'Estado_Salud' in df.columns:
                # Pie Chart corregido
                fig_pie = px.pie(
                    df, names='Estado_Salud', hole=0.5,
                    color_discrete_sequence=['#4caf50', '#cddc39', '#ff9800', '#f44336', '#9e9e9e']
                )
                fig_pie.update_layout(showlegend=False, height=300, title_text="Estado de Salud Global")
                # Anotación central
                fig_pie.add_annotation(text=f"{pct_salud:.0f}%", font_size=35, showarrow=False, font_color="#2e7d32")
                fig_pie.add_annotation(text="Sanos", y=-0.15, showarrow=False, font_size=14)
                st.plotly_chart(fig_pie, use_container_width=True)
                
                # Tabla resumen simple
                conteo_salud = df['Estado_Salud'].value_counts().reset_index()
                conteo_salud.columns = ['Estado', 'Total']
                st.dataframe(conteo_salud, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.info(generate_report(df))

    # === TAB 2: MAPA INTELIGENTE (POLÍGONOS + PUNTOS) ===
    with tab_map:
        st.subheader("Georreferenciación: Polígonos y Especímenes")
        
        col_m1, col_m2 = st.columns([3, 1])
        
        with col_m2:
            st.markdown("##### 🛠️ Capas del Mapa")
            show_polygons = st.checkbox("Mostrar Polígonos (Zonas)", value=True)
            show_heatmap = st.checkbox("Mapa de Calor (Densidad)", value=False)
            show_clusters = st.checkbox("Agrupar Marcadores (Clusters)", value=True)
            
            st.divider()
            st.markdown("**Simbología:**")
            st.markdown("🟢 **Excelente**")
            st.markdown("🟡 **Regular/Estrés**")
            st.markdown("🔴 **Crítico/Muerto**")
            
            if kml_data_obj is not None:
                st.success("✅ Archivo KML cargado correctamente.")
            else:
                st.warning("⚠️ No se encontró archivo KML de polígonos.")

        with col_m1:
            if 'Coordenada_X' in df.columns and 'Coordenada_Y' in df.columns:
                # Calcular centro del mapa
                lat_mean = df['Coordenada_X'].mean() if not df['Coordenada_X'].isna().all() else 21.23
                lon_mean = df['Coordenada_Y'].mean() if not df['Coordenada_Y'].isna().all() else -100.46
                
                # Inicializar mapa base
                m = folium.Map(location=[lat_mean, lon_mean], zoom_start=17, tiles="OpenStreetMap")
                Fullscreen().add_to(m)
                
                # 1. CAPA DE POLÍGONOS (ZONAS)
                if show_polygons and kml_data_obj is not None:
                    zonas_kml = process_kml_polygons(kml_data_obj)
                    
                    # Paleta de colores para diferenciar zonas
                    poly_colors = ['#1976D2', '#D81B60', '#FBC02D', '#388E3C', '#8E24AA', '#E64A19']
                    
                    for i, z in enumerate(zonas_kml):
                        color = poly_colors[i % len(poly_colors)]
                        folium.Polygon(
                            locations=z['points'],
                            popup=folium.Popup(f"<b>Zona:</b> {z['name']}", max_width=200),
                            tooltip=z['name'],
                            color=color,
                            weight=3,
                            fill=True,
                            fill_color=color,
                            fill_opacity=0.15
                        ).add_to(m)
                
                # Filtrar puntos válidos para marcadores
                df_geo = df.dropna(subset=['Coordenada_X', 'Coordenada_Y'])
                
                # 2. CAPA MAPA DE CALOR
                if show_heatmap and not df_geo.empty:
                    heat_data = [[row['Coordenada_X'], row['Coordenada_Y']] for index, row in df_geo.iterrows()]
                    HeatMap(heat_data, radius=18, blur=12).add_to(m)
                
                # 3. CAPA DE MARCADORES (ÁRBOLES)
                # Elegimos dónde añadir los marcadores (Cluster o Mapa directo)
                marker_layer = MarkerCluster().add_to(m) if show_clusters else m
                
                for _, row in df_geo.iterrows():
                    # Lógica de color según salud
                    status = str(row.get('Estado_Salud', '')).lower()
                    if 'crítico' in status or 'muerto' in status:
                        icon_color = 'red'
                        icon_icon = 'times-circle'
                    elif 'regular' in status or 'estrés' in status:
                        icon_color = 'orange'
                        icon_icon = 'exclamation-triangle'
                    else:
                        icon_color = 'green'
                        icon_icon = 'leaf'
                    
                    popup_html = f"""
                    <div style='font-family:sans-serif; width:150px;'>
                        <b>ID:</b> {row.get('ID_Especimen', 'N/A')}<br>
                        <b>Tipo:</b> {row.get('Tipo', 'Desc.')}<br>
                        <b>Salud:</b> {row.get('Estado_Salud', 'Desc.')}<br>
                        <b>Zona:</b> {row.get('Poligono', 'N/A')}
                    </div>
                    """
                    
                    folium.Marker(
                        location=[row['Coordenada_X'], row['Coordenada_Y']],
                        popup=folium.Popup(popup_html, max_width=200),
                        tooltip=f"{row.get('Tipo', 'Planta')}",
                        icon=folium.Icon(color=icon_color, icon=icon_icon, prefix='fa')
                    ).add_to(marker_layer)
                
                # Renderizar mapa
                st_folium(m, width="100%", height=600)
            else:
                st.warning("⚠️ No se detectaron columnas de coordenadas GPS válidas (Coordenada_X, Coordenada_Y).")

    # === TAB 3: BIOMETRÍA Y ESTADÍSTICAS ===
    with tab_bio:
        st.subheader("Análisis de Crecimiento y Desarrollo")
        
        if 'Altura_cm' in df.columns and 'Diametro_cm' in df.columns:
            col_b1, col_b2 = st.columns([2, 1])
            
            with col_b1:
                # --- VERIFICACIÓN SEGURA DE STATSMODELS ---
                trend_mode = None
                try:
                    import statsmodels
                    trend_mode = "ols"
                except ImportError:
                    trend_mode = None
                    if 'warned_stats' not in st.session_state:
                        st.toast("Librería 'statsmodels' no detectada. Línea de tendencia desactivada.", icon="ℹ️")
                        st.session_state['warned_stats'] = True

                # Scatter Plot
                st.markdown("#### Modelo de Crecimiento Alométrico")
                fig_scatter = px.scatter(
                    df, x='Diametro_cm', y='Altura_cm',
                    color='Tipo' if 'Tipo' in df.columns else None,
                    size='Altura_cm',
                    hover_data=df.columns,
                    trendline=trend_mode,
                    title="Correlación: Diámetro vs Altura"
                )
                st.plotly_chart(fig_scatter, use_container_width=True)
                
            with col_b2:
                st.markdown("#### Distribución de Alturas")
                # Box Plot
                fig_box = px.box(df, y="Altura_cm", x="Tipo" if 'Tipo' in df.columns else None, 
                                 points="all", title="Rango de Crecimiento por Especie")
                st.plotly_chart(fig_box, use_container_width=True)
            
            st.divider()
            
            # Histograma
            st.markdown("#### Frecuencia de Tamaños")
            fig_hist = px.histogram(df, x="Altura_cm", nbins=25, color="Tipo" if 'Tipo' in df.columns else None,
                                    title="Conteo de Árboles por Segmento de Altura")
            st.plotly_chart(fig_hist, use_container_width=True)
            
        else:
            st.info("Para activar el análisis biométrico, asegúrate de que el archivo contenga las columnas 'Altura_cm' y 'Diametro_cm'.")

    # === TAB 4: SIMULADOR FINANCIERO (ROI) ===
    with tab_roi:
        st.subheader("💰 Simulador Financiero de Proyecto")
        st.markdown("Proyección de rentabilidad para cultivos productivos (Ej. Maguey/Agave).")
        
        c_input, c_results = st.columns([1, 2])
        
        with c_input:
            with st.expander("🛠️ Variables Económicas", expanded=True):
                st.markdown("**Costos Operativos**")
                costo_unitario = st.number_input("Costo Inicial ($/planta)", value=60.0, step=5.0)
                manto_anual = st.number_input("Mantenimiento Anual ($/planta)", value=25.0, step=5.0)
                
                st.markdown("**Proyección de Venta**")
                precio_mercado = st.number_input("Precio Venta Final ($/unidad)", value=950.0, step=50.0)
                anios_cosecha = st.slider("Ciclo de Maduración (Años)", 4, 12, 7)
                riesgo_merma = st.slider("Margen de Riesgo/Merma (%)", 0, 40, 15) / 100
        
        with c_results:
            # Identificación de plantas productivas
            if 'Tipo' in df.columns:
                target_plants = df[df['Tipo'].str.contains("Maguey|Agave|Mezquite", case=False, na=False)]
                n_plantas = len(target_plants)
                if n_plantas > 0:
                    st.success(f"Simulación aplicada a **{n_plantas}** unidades productivas identificadas.")
                else:
                    st.warning("No se detectaron especies productivas (Agave, Maguey). Se usará el total del inventario.")
                    n_plantas = len(df)
            else:
                n_plantas = len(df)
            
            # Cálculo Financiero
            if n_plantas > 0:
                inversion_inicial = n_plantas * costo_unitario
                gasto_manto_total = n_plantas * manto_anual * anios_cosecha
                costo_total_proyecto = inversion_inicial + gasto_manto_total
                
                plantas_finales = n_plantas * (1 - riesgo_merma)
                ingreso_bruto = plantas_finales * precio_mercado
                
                utilidad_neta = ingreso_bruto - costo_total_proyecto
                roi_pct = (utilidad_neta / costo_total_proyecto) * 100 if costo_total_proyecto > 0 else 0
                
                # KPIs Financieros
                m1, m2, m3 = st.columns(3)
                m1.metric("Costo Total (OpEx + CapEx)", f"${costo_total_proyecto:,.0f}")
                m2.metric("Ventas Potenciales", f"${ingreso_bruto:,.0f}")
                m3.metric("Utilidad Neta", f"${utilidad_neta:,.0f}", delta=f"ROI: {roi_pct:.1f}%")
                
                # Gráfico Waterfall (Cascada)
                fig_water = go.Figure(go.Waterfall(
                    name = "Flujo", orientation = "v",
                    measure = ["relative", "relative", "total", "relative", "total"],
                    x = ["Inversión Inicial", "Mantenimiento Total", "Costo Acumulado", "Ingreso Venta", "Utilidad Final"],
                    textposition = "outside",
                    text = [f"-${inversion_inicial:,.0f}", f"-${gasto_manto_total:,.0f}", "", f"+${ingreso_bruto:,.0f}", ""],
                    y = [-inversion_inicial, -gasto_manto_total, 0, ingreso_bruto, 0],
                    connector = {"line":{"color":"rgb(63, 63, 63)"}},
                    decreasing = {"marker":{"color":"#ef5350"}},
                    increasing = {"marker":{"color":"#66bb6a"}},
                    totals = {"marker":{"color":"#42a5f5"}}
                ))
                fig_water.update_layout(title = "Análisis de Flujo de Efectivo", showlegend = False, height=400)
                st.plotly_chart(fig_water, use_container_width=True)
            else:
                st.error("Inventario insuficiente para generar proyección.")

    # === TAB 5: EDITOR DE DATOS ===
    with tab_data:
        st.subheader("📝 Gestión de Base de Datos")
        st.markdown("Edición en tiempo real para corrección de registros de campo.")
        
        # Editor Interactivo
        df_edited = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Estado_Salud": st.column_config.SelectboxColumn(
                    "Salud",
                    help="Categoría de estado fitosanitario",
                    width="medium",
                    options=["Excelente", "Bueno", "Regular", "Estrés Hídrico", "Plaga", "Crítico", "Muerto"],
                ),
                "Altura_cm": st.column_config.NumberColumn(
                    "Altura (cm)",
                    min_value=0,
                    max_value=1500,
                    step=1,
                    format="%d cm"
                ),
                "Diametro_cm": st.column_config.NumberColumn(
                    "Diámetro (cm)",
                    min_value=0,
                    max_value=500,
                    step=1
                )
            }
        )
        
        st.divider()
        
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.info(f"Visualizando {len(df_edited)} registros activos.")
        with col_dl2:
            # Botón de Descarga Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_edited.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Descargar Base de Datos Actualizada",
                data=output.getvalue(),
                file_name=f"Reforestacion_PONS_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

else:
    # Pantalla de Carga Inicial
    st.container()
    st.markdown("### ⏳ Estableciendo conexión con el servidor...")
    st.info("El sistema está sincronizando los datos desde GitHub. Por favor espera un momento.")
