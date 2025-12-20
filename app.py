import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, HeatMap
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

# URL por defecto (GitHub Raw)
URL_GITHUB_DEFAULT = "https://raw.githubusercontent.com/ponsmartinluis-hub/reforestacion-pons/main/plantacion.xlsx"

# Estilos CSS Avanzados para "Look & Feel" Corporativo
st.markdown("""
<style>
    /* Tipografía y Fondo */
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Roboto', sans-serif;
        background-color: #f4f6f9;
        color: #2c3e50;
    }
    
    /* Encabezados */
    h1 { color: #1b5e20; font-weight: 700; border-bottom: 2px solid #a5d6a7; padding-bottom: 10px; }
    h2 { color: #2e7d32; margin-top: 20px; }
    h3 { color: #388e3c; }

    /* Tarjetas de Métricas (KPIs) */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 20px;
        border-radius: 10px;
        border-left: 6px solid #2e7d32;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: transform 0.2s;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
    }

    /* Pestañas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: #ffffff;
        padding: 10px;
        border-radius: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f1f8e9;
        border-radius: 5px;
        color: #33691e;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #33691e !important;
        color: #ffffff !important;
    }
    
    /* Botones */
    .stButton>button {
        background-color: #2e7d32;
        color: white;
        border-radius: 5px;
        border: none;
    }
    .stButton>button:hover {
        background-color: #1b5e20;
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
        
        # 4. Estandarización de Texto (Opcional pero recomendado)
        if 'Estado_Salud' in df.columns:
            df['Estado_Salud'] = df['Estado_Salud'].astype(str).str.capitalize()

        return df
    except Exception as e:
        st.error(f"Error en el motor de datos: {str(e)}")
        return None

def process_kml_polygons(kml_file):
    """Parsea archivos KML para extraer coordenadas de polígonos"""
    zonas = []
    try:
        content = kml_file.getvalue().decode("utf-8")
        root = ET.fromstring(content)
        # Namespaces comunes
        namespaces = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        # Búsqueda recursiva de Placemarks
        for placemark in root.findall('.//kml:Placemark', namespaces) or root.findall('.//{http://www.opengis.net/kml/2.2}Placemark'):
            name_tag = placemark.find('.//kml:name', namespaces) or placemark.find('.//{http://www.opengis.net/kml/2.2}name')
            name = name_tag.text if name_tag is not None else "Zona Sin Nombre"
            
            coord_tag = placemark.find('.//kml:coordinates', namespaces) or placemark.find('.//{http://www.opengis.net/kml/2.2}coordinates')
            if coord_tag is not None and coord_tag.text:
                coords_str = coord_tag.text.strip().split()
                points = []
                for c in coords_str:
                    parts = c.split(',')
                    if len(parts) >= 2:
                        # KML es (Lon, Lat) -> Folium quiere (Lat, Lon)
                        points.append([float(parts[1]), float(parts[0])])
                zonas.append({'name': name, 'points': points})
    except Exception as e:
        st.warning(f"No se pudo procesar el mapa KML: {e}")
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
    
    El proyecto cuenta actualmente con un inventario de **{total:,} especímenes**. 
    La operación abarca **{zonas} polígonos** distintos.
    
    **Estado Fitosanitario:**
    El estado predominante es **{top_salud}**, representando el **{pct_salud:.1f}%** de la población.
    """
    return texto

# ==============================================================================
# 3. SIDEBAR Y FILTROS GLOBALES
# ==============================================================================

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3028/3028569.png", width=100) # Icono de Agave/Cactus
    st.title("Panel de Control")
    st.markdown("---")
    
    # 3.1 Selector de Fuente
    st.subheader("📡 Origen de Datos")
    source_mode = st.radio("Modo de conexión:", ["GitHub (Automático)", "Carga Manual"], index=0)
    
    if source_mode == "GitHub (Automático)":
        data_source = URL_GITHUB_DEFAULT
        is_url_flag = True
        st.caption(f"Conectado a: `.../plantacion.xlsx`")
    else:
        data_source = st.file_uploader("Sube tu Excel/CSV", type=['xlsx', 'csv'])
        is_url_flag = False

    st.markdown("---")
    
    # 3.2 Carga de Mapa Base
    st.subheader("🗺️ Capas Geográficas")
    uploaded_kml = st.file_uploader("Archivo KML (Polígonos)", type=['kml', 'xml'])
    
    st.markdown("---")
    st.info("v3.0.0 | SOLEX Secure © 2025")

# ==============================================================================
# 4. LÓGICA PRINCIPAL (MAIN LOOP)
# ==============================================================================

# Carga de datos
if data_source:
    with st.spinner('Sincronizando con base de datos...'):
        df_raw = load_and_clean_data(data_source, is_url=is_url_flag)
else:
    df_raw = None

if df_raw is not None:
    # --- FILTROS DINÁMICOS EN SIDEBAR (Ahora que tenemos datos) ---
    with st.sidebar:
        st.subheader("🔍 Filtros Avanzados")
        
        # Filtro Especie
        if 'Tipo' in df_raw.columns:
            all_species = sorted(df_raw['Tipo'].astype(str).unique())
            sel_species = st.multiselect("Especies:", all_species, default=all_species)
        else:
            sel_species = []
            
        # Filtro Salud
        if 'Estado_Salud' in df_raw.columns:
            all_health = sorted(df_raw['Estado_Salud'].astype(str).unique())
            sel_health = st.multiselect("Salud:", all_health, default=all_health)
        else:
            sel_health = []

    # APLICAR FILTROS
    df = df_raw.copy()
    if sel_species:
        df = df[df['Tipo'].astype(str).isin(sel_species)]
    if sel_health:
        df = df[df['Estado_Salud'].astype(str).isin(sel_health)]
    
    # --- ENCABEZADO Y KPIS ---
    st.title("🌵 Monitor de Reforestación: Cerrito del Carmen")
    st.markdown("**Dashboard Operativo y Financiero**")
    
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
        "🗺️ Mapa Inteligente",
        "📏 Biometría",
        "💰 Simulador Financiero",
        "📝 Editor de Datos"
    ])

    # === TAB 1: DASHBOARD EJECUTIVO ===
    with tab_dash:
        col_d1, col_d2 = st.columns([2, 1])
        
        with col_d1:
            st.subheader("Distribución de Inventario")
            if 'Poligono' in df.columns and 'Tipo' in df.columns:
                # Sunburst Chart (Interactiva y Jerárquica)
                path_cols = ['Poligono', 'Tipo']
                if 'Estado_Salud' in df.columns: path_cols.append('Estado_Salud')
                
                fig_sun = px.sunburst(
                    df, path=path_cols,
                    title="Jerarquía: Zona > Especie > Estado",
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_sun.update_layout(height=500, margin=dict(t=30, l=0, r=0, b=0))
                st.plotly_chart(fig_sun, use_container_width=True)
            else:
                st.warning("Se requieren columnas 'Poligono' y 'Tipo' para visualizar la jerarquía.")

        with col_d2:
            st.subheader("Resumen Fitosanitario")
            if 'Estado_Salud' in df.columns:
                # Donut Chart con anotación central
                fig_don = px.donut(
                    df, names='Estado_Salud', hole=0.6,
                    color_discrete_sequence=['#4caf50', '#cddc39', '#ff9800', '#f44336', '#9e9e9e']
                )
                fig_don.update_layout(showlegend=False, height=300)
                fig_don.add_annotation(text=f"{pct_salud:.0f}%", font_size=40, showarrow=False, textangle=0)
                fig_don.add_annotation(text="Sanos", y=-0.2, showarrow=False)
                st.plotly_chart(fig_don, use_container_width=True)
                
                # Barras simples
                conteo_salud = df['Estado_Salud'].value_counts().reset_index()
                conteo_salud.columns = ['Estado', 'Cant']
                st.dataframe(conteo_salud, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown(generate_report(df))

    # === TAB 2: MAPA INTELIGENTE ===
    with tab_map:
        st.subheader("Georreferenciación Avanzada")
        
        col_m1, col_m2 = st.columns([3, 1])
        
        with col_m2:
            st.markdown("##### Configuración de Capas")
            show_heatmap = st.checkbox("Ver Mapa de Calor (Densidad)", value=False)
            show_clusters = st.checkbox("Agrupar Marcadores (Clusters)", value=True)
            st.info("💡 Usa Clusters si el mapa se pone lento.")
            
            st.divider()
            st.markdown("**Leyenda:**")
            st.markdown("🟢 **Excelente**")
            st.markdown("🟡 **Regular**")
            st.markdown("🔴 **Crítico/Muerto**")

        with col_m1:
            if 'Coordenada_X' in df.columns and 'Coordenada_Y' in df.columns:
                # Calcular centro
                lat_mean = df['Coordenada_X'].mean() if not df['Coordenada_X'].isna().all() else 21.23
                lon_mean = df['Coordenada_Y'].mean() if not df['Coordenada_Y'].isna().all() else -100.46
                
                m = folium.Map(location=[lat_mean, lon_mean], zoom_start=18, tiles="OpenStreetMap")
                
                # 1. Capa Polígonos (KML)
                if uploaded_kml:
                    zonas_kml = process_kml_polygons(uploaded_kml)
                    colors = ['#1e88e5', '#d81b60', '#fbc02d', '#43a047']
                    for i, z in enumerate(zonas_kml):
                        folium.Polygon(
                            locations=z['points'],
                            popup=z['name'],
                            color=colors[i % len(colors)],
                            fill=True, fill_opacity=0.1
                        ).add_to(m)
                
                # Filtrar puntos válidos
                df_geo = df.dropna(subset=['Coordenada_X', 'Coordenada_Y'])
                
                # 2. Capa Mapa de Calor
                if show_heatmap and not df_geo.empty:
                    heat_data = [[row['Coordenada_X'], row['Coordenada_Y']] for index, row in df_geo.iterrows()]
                    HeatMap(heat_data, radius=15).add_to(m)
                
                # 3. Capa Marcadores
                marker_layer = MarkerCluster().add_to(m) if show_clusters else m
                
                for _, row in df_geo.iterrows():
                    # Color logic
                    status = str(row.get('Estado_Salud', '')).lower()
                    if 'crítico' in status or 'muerto' in status:
                        icon_color = 'red'
                        icon_icon = 'times'
                    elif 'regular' in status or 'estrés' in status:
                        icon_color = 'orange'
                        icon_icon = 'exclamation'
                    else:
                        icon_color = 'green'
                        icon_icon = 'tree'
                    
                    folium.Marker(
                        location=[row['Coordenada_X'], row['Coordenada_Y']],
                        popup=f"<b>{row.get('ID_Especimen', 'ID?')}</b><br>{row.get('Tipo', '')}<br>{row.get('Estado_Salud','')}",
                        icon=folium.Icon(color=icon_color, icon=icon_icon, prefix='fa')
                    ).add_to(marker_layer)
                
                st_folium(m, width="100%", height=600)
            else:
                st.warning("⚠️ No se detectaron columnas de coordenadas GPS (Coordenada_X, Coordenada_Y).")

    # === TAB 3: BIOMETRÍA Y ESTADÍSTICAS ===
    with tab_bio:
        st.subheader("Análisis de Crecimiento")
        
        if 'Altura_cm' in df.columns and 'Diametro_cm' in df.columns:
            col_b1, col_b2 = st.columns([2, 1])
            
            with col_b1:
                # Scatter Plot con Tendencia
                st.markdown("#### Correlación Altura vs Diámetro")
                fig_scatter = px.scatter(
                    df, x='Diametro_cm', y='Altura_cm',
                    color='Tipo' if 'Tipo' in df.columns else None,
                    size='Altura_cm',
                    hover_data=df.columns,
                    trendline="ols", # Línea de tendencia automática
                    title="Modelo de Crecimiento Alométrico"
                )
                st.plotly_chart(fig_scatter, use_container_width=True)
                
            with col_b2:
                st.markdown("#### Distribución (Box Plot)")
                # Box Plot para ver outliers
                fig_box = px.box(df, y="Altura_cm", x="Tipo" if 'Tipo' in df.columns else None, 
                                 points="all", title="Dispersión de Alturas")
                st.plotly_chart(fig_box, use_container_width=True)
                
            st.divider()
            
            # Histograma
            st.markdown("#### Histograma de Frecuencias")
            fig_hist = px.histogram(df, x="Altura_cm", nbins=20, color="Tipo" if 'Tipo' in df.columns else None,
                                    title="¿Cuántos árboles hay por rango de altura?")
            st.plotly_chart(fig_hist, use_container_width=True)
            
        else:
            st.info("Esta sección requiere columnas numéricas 'Altura_cm' y 'Diametro_cm' para activarse.")

    # === TAB 4: SIMULADOR FINANCIERO (ROI) ===
    with tab_roi:
        st.subheader("💰 Proyección de Retorno de Inversión")
        st.markdown("Modelo financiero simplificado para cultivo de **Maguey/Agave**.")
        
        c_input, c_results = st.columns([1, 2])
        
        with c_input:
            with st.expander("🛠️ Parámetros del Modelo", expanded=True):
                st.markdown("**Costos**")
                costo_unitario = st.number_input("Costo Plantación ($/planta)", value=60.0, step=5.0)
                manto_anual = st.number_input("Mantenimiento Anual ($/planta)", value=25.0, step=5.0)
                
                st.markdown("**Ventas**")
                precio_mercado = st.number_input("Precio Venta Piña ($)", value=950.0, step=50.0)
                anios_cosecha = st.slider("Ciclo de Maduración (Años)", 4, 12, 7)
                riesgo_merma = st.slider("Factor Riesgo/Merma (%)", 0, 40, 15) / 100
        
        with c_results:
            # Lógica de cálculo
            if 'Tipo' in df.columns:
                target_plants = df[df['Tipo'].str.contains("Maguey|Agave|Mezquite", case=False, na=False)]
                n_plantas = len(target_plants)
                st.success(f"Cálculo basado en **{n_plantas}** unidades productivas (Agave/Mezquite) detectadas.")
            else:
                n_plantas = len(df)
                st.warning(f"Calculando sobre el total de **{n_plantas}** registros (Sin filtrar especie).")
            
            # Matemáticas Financieras
            if n_plantas > 0:
                inversion_inicial = n_plantas * costo_unitario
                gasto_manto_total = n_plantas * manto_anual * anios_cosecha
                costo_total_proyecto = inversion_inicial + gasto_manto_total
                
                plantas_finales = n_plantas * (1 - riesgo_merma)
                ingreso_bruto = plantas_finales * precio_mercado
                
                utilidad_neta = ingreso_bruto - costo_total_proyecto
                roi_pct = (utilidad_neta / costo_total_proyecto) * 100
                
                # Visualización de Resultados
                m1, m2, m3 = st.columns(3)
                m1.metric("Costo Total Proyecto", f"${costo_total_proyecto:,.0f}")
                m2.metric("Ventas Proyectadas", f"${ingreso_bruto:,.0f}")
                m3.metric("Utilidad Neta", f"${utilidad_neta:,.0f}", delta=f"ROI: {roi_pct:.1f}%")
                
                # Gráfico Waterfall
                fig_water = go.Figure(go.Waterfall(
                    name = "Flujo", orientation = "v",
                    measure = ["relative", "relative", "total", "relative", "total"],
                    x = ["Inv. Inicial", "Mantenimiento", "Costo Total", "Venta Cosecha", "Resultado"],
                    textposition = "outside",
                    text = [f"-{inversion_inicial/1000:.1f}k", f"-{gasto_manto_total/1000:.1f}k", "", f"+{ingreso_bruto/1000:.1f}k", ""],
                    y = [-inversion_inicial, -gasto_manto_total, 0, ingreso_bruto, 0],
                    connector = {"line":{"color":"rgb(63, 63, 63)"}},
                ))
                fig_water.update_layout(title = "Cascada de Flujo de Efectivo", showlegend = False)
                st.plotly_chart(fig_water, use_container_width=True)
            else:
                st.error("No hay plantas suficientes para calcular.")

    # === TAB 5: EDITOR DE DATOS ===
    with tab_data:
        st.subheader("📝 Gestión de Base de Datos")
        st.markdown("Aquí puedes editar datos erróneos temporalmente y descargar la versión corregida.")
        
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
                    max_value=1000,
                    step=1,
                    format="%d cm"
                )
            }
        )
        
        st.divider()
        
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.info(f"Mostrando {len(df_edited)} registros.")
        with col_dl2:
            # Botón de Descarga
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_edited.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Descargar Excel Actualizado",
                data=output.getvalue(),
                file_name=f"Reforestacion_PONS_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

else:
    # Pantalla de Carga Inicial / Error
    st.container()
    st.markdown("### ⏳ Esperando conexión de datos...")
    st.info("Si esto tarda mucho, verifica que la URL de GitHub sea pública o sube el archivo manualmente en la barra lateral.")
