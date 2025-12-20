import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET
from io import BytesIO
import requests

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN EJECUTIVA Y ESTILOS
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Dashboard Reforestación | SOLEX",
    page_icon="🌵",  # ¡El Cactus solicitado!
    layout="wide",
    initial_sidebar_state="collapsed"
)


https://github.com/ponsmartinluis-hub/reforestacion-pons/blob/main/plantacion.xlsx
 

# Estilos CSS Profesionales (Mobile Friendly)
st.markdown("""
<style>
    /* Fondo limpio y textos oscuros para legibilidad */
    .stApp { background-color: #f8f9fa; }
    h1, h2, h3, h4 { color: #1b4f25; font-family: 'Helvetica Neue', sans-serif; }
    
    /* Métricas con estilo de tarjeta */
    div[data-testid="metric-container"] {
        background-color: white;
        border-radius: 8px;
        padding: 15px;
        border-left: 5px solid #2e7d32;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Pestañas estilo botón */
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 1.1rem;
        font-weight: 600;
    }
    
    /* Ajuste para móviles: Texto siempre oscuro */
    p, span, div { color: #2c3e50; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. MOTOR DE DATOS HÍBRIDO (GITHUB + UPLOAD)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=600) # Guarda en caché por 10 min
def load_data(source, is_url=False):
    try:
        if is_url:
            # Carga desde GitHub
            response = requests.get(source)
            response.raise_for_status()
            file_content = BytesIO(response.content)
            df = pd.read_excel(file_content)
        else:
            # Carga manual
            if source.name.endswith('.csv'):
                df = pd.read_csv(source)
            else:
                df = pd.read_excel(source)

        # --- LIMPIEZA AUTOMÁTICA (CRÍTICO) ---
        # 1. Nombres: Quita comas, puntos y espacios
        df.columns = df.columns.str.strip().str.replace('[,.:]', '', regex=True)
        
        # 2. Duplicados: Si hay dos columnas 'Altura_cm', borra la segunda
        df = df.loc[:, ~df.columns.duplicated()]
        
        # 3. Conversiones Numéricas
        cols_num = ['Coordenada_X', 'Coordenada_Y', 'Altura_cm', 'Diametro_cm']
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df
    except Exception as e:
        return None

def leer_kml(archivo_kml):
    """Procesador de mapas KML"""
    zonas = []
    try:
        string_data = archivo_kml.getvalue().decode("utf-8")
        root = ET.fromstring(string_data)
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        placemarks = root.findall('.//kml:Placemark', ns)
        if not placemarks: placemarks = root.findall('.//{http://www.opengis.net/kml/2.2}Placemark')

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
                        puntos.append([float(val[1]), float(val[0])])
                zonas.append({'nombre': nombre_txt, 'puntos': puntos})
    except: pass
    return zonas

# -----------------------------------------------------------------------------
# 3. INTERFAZ Y LÓGICA
# -----------------------------------------------------------------------------
st.title("🌵 Monitor Cerrito del Carmen")
st.caption("Dashboard Ejecutivo | Datos en Tiempo Real")

# --- CONTROL DE DATOS (SIDEBAR) ---
with st.sidebar:
    st.header("Fuente de Datos")
    
    # 1. Opción de GitHub
    use_github = st.checkbox("Usar GitHub (Automático)", value=True)
    github_url = st.text_input("URL GitHub Raw", value=URL_GITHUB_DEFAULT)
    
    # 2. Opción Manual
    uploaded_file = st.file_uploader("O subir archivo manual (Sobreescribe)", type=['xlsx', 'csv'])
    
    st.markdown("---")
    uploaded_kml = st.file_uploader("Cargar Mapa KML", type=['kml', 'xml'])
    
    if st.button("🔄 Recargar Datos"):
        st.cache_data.clear()
        st.rerun()

# --- LÓGICA DE CARGA ---
df = None
source_label = ""

if uploaded_file:
    df = load_data(uploaded_file, is_url=False)
    source_label = "Archivo Manual"
elif use_github and github_url:
    df = load_data(github_url, is_url=True)
    source_label = "Nube GitHub"

# --- DASHBOARD ---
if df is not None:
    st.success(f"✅ Datos cargados exitosamente desde: **{source_label}** ({len(df)} registros)")

    # TABS PRINCIPALES
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Dashboard Ejecutivo", 
        "🗺️ Mapa Geoespacial", 
        "💰 Proyección ROI", 
        "📂 Base de Datos"
    ])

    # === TAB 1: DASHBOARD ORGULLO ===
    with tab1:
        # KPIs Superiores
        k1, k2, k3, k4 = st.columns(4)
        total = len(df)
        
        # Cálculos defensivos (por si faltan columnas)
        salud_ok = len(df[df['Estado_Salud'].str.contains('Excelente|Bueno', case=False, na=False)]) if 'Estado_Salud' in df.columns else 0
        tipo_top = df['Tipo'].mode()[0] if 'Tipo' in df.columns else "N/A"
        zona_top = df['Poligono'].mode()[0] if 'Poligono' in df.columns else "N/A"

        k1.metric("Total Plantado", f"{total:,}", delta="Inventario")
        k2.metric("Tasa Supervivencia", f"{(salud_ok/total)*100:.1f}%" if total>0 else "0%", delta="Meta > 90%")
        k3.metric("Especie Dominante", tipo_top)
        k4.metric("Zona Más Densa", zona_top)

        st.divider()

        # GRÁFICOS PREMIUM
        col_g1, col_g2 = st.columns([2, 1])
        
        with col_g1:
            st.subheader("Distribución Jerárquica")
            if 'Poligono' in df.columns and 'Tipo' in df.columns:
                # GRÁFICO SUNBURST (Muy vistoso)
                # Muestra Zona -> Tipo -> Salud en anillos concéntricos
                cols_path = ['Poligono', 'Tipo']
                if 'Estado_Salud' in df.columns: cols_path.append('Estado_Salud')
                
                fig_sun = px.sunburst(
                    df, path=cols_path, 
                    title="Radiografía del Proyecto (Click para profundizar)",
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_sun.update_layout(height=500)
                st.plotly_chart(fig_sun, use_container_width=True)
            else:
                st.info("Faltan columnas Poligono/Tipo para el gráfico jerárquico.")

        with col_g2:
            st.subheader("Salud General")
            if 'Estado_Salud' in df.columns:
                fig_pie = px.donut(df, names='Estado_Salud', hole=0.5, 
                                   color_discrete_sequence=['#66bb6a', '#ffee58', '#ef5350', '#bdbdbd'])
                fig_pie.update_layout(showlegend=False, height=400)
                # Añadir anotación central
                fig_pie.add_annotation(text=f"{salud_ok}", showarrow=False, font_size=40, font_color="#1b4f25")
                fig_pie.add_annotation(text="Sanos", showarrow=False, y=-0.15, font_size=15)
                st.plotly_chart(fig_pie, use_container_width=True)

        # GRÁFICO DE BARRAS DE ESPECIES
        if 'Tipo' in df.columns:
            conteo_tipos = df['Tipo'].value_counts().reset_index()
            conteo_tipos.columns = ['Especie', 'Cantidad']
            fig_bar = px.bar(conteo_tipos, x='Especie', y='Cantidad', text='Cantidad',
                             color='Cantidad', color_continuous_scale='Greens',
                             title="Inventario por Especie")
            st.plotly_chart(fig_bar, use_container_width=True)

    # === TAB 2: MAPA ===
    with tab2:
        c_map, c_ctrl = st.columns([3, 1])
        with c_ctrl:
            st.markdown("### Filtros de Mapa")
            if 'Tipo' in df.columns:
                filtro_tipo_mapa = st.multiselect("Especie", df['Tipo'].unique(), default=df['Tipo'].unique())
            else:
                filtro_tipo_mapa = []
            
            st.info("🟢 Verde: Saludable\n🟠 Naranja: Regular\n🔴 Rojo: Crítico")

        with c_map:
            if 'Coordenada_X' in df.columns:
                # Centrado automático
                lat = df['Coordenada_X'].mean() if not df['Coordenada_X'].isnull().all() else 21.23
                lon = df['Coordenada_Y'].mean() if not df['Coordenada_Y'].isnull().all() else -100.46
                
                m = folium.Map(location=[lat, lon], zoom_start=18, tiles="OpenStreetMap")
                
                # Capa KML
                if uploaded_kml:
                    zonas = leer_kml(uploaded_kml)
                    colors = ['#4285F4', '#EA4335', '#FBBC05', '#34A853']
                    for i, z in enumerate(zonas):
                        folium.Polygon(z['puntos'], color=colors[i%4], fill=True, fill_opacity=0.1, popup=z['nombre']).add_to(m)
                
                # Capa Puntos
                df_map = df[df['Tipo'].isin(filtro_tipo_mapa)] if filtro_tipo_mapa else df
                df_map = df_map.dropna(subset=['Coordenada_X'])
                
                for _, row in df_map.iterrows():
                    color = '#2e7d32' # Verde Maguey
                    estado = str(row.get('Estado_Salud','')).lower()
                    if 'crítico' in estado or 'muerto' in estado: color = '#c62828'
                    elif 'regular' in estado: color = '#f9a825'
                    
                    folium.CircleMarker(
                        [row['Coordenada_X'], row['Coordenada_Y']],
                        radius=5, color=color, fill=True, fill_opacity=0.8,
                        tooltip=f"{row.get('Tipo','')} | {row.get('Poligono','')}"
                    ).add_to(m)
                
                st_folium(m, width="100%", height=600)

    # === TAB 3: ROI (FINANZAS) ===
    with tab3:
        st.subheader("💰 Simulador de Retorno de Inversión")
        
        col_in, col_res = st.columns([1, 2])
        
        with col_in:
            with st.expander("Parámetros del Modelo", expanded=True):
                costo_inicial = st.number_input("Costo por Planta ($)", 50.0)
                mant_anual = st.number_input("Mantenimiento Anual ($)", 15.0)
                anos = st.slider("Años a Cosecha", 3, 15, 7)
                precio_venta = st.number_input("Precio Venta ($/Piña)", 900.0)
                riesgo = st.slider("Riesgo de Merma (%)", 0, 50, 10) / 100
        
        with col_res:
            # Cálculos en tiempo real
            if 'Tipo' in df.columns:
                # Asumimos que todo lo que dice "Maguey" o "Agave" cuenta
                n_plantas = len(df[df['Tipo'].str.contains("Maguey|Agave|Mezquite", case=False, na=False)])
            else:
                n_plantas = len(df)
            
            st.info(f"Calculando sobre **{n_plantas}** unidades productivas detectadas.")
            
            inversion_total = (costo_inicial + (mant_anual * anos)) * n_plantas
            plantas_finales = n_plantas * (1 - riesgo)
            ventas_totales = plantas_finales * precio_venta
            utilidad = ventas_totales - inversion_total
            roi = (utilidad / inversion_total) * 100 if inversion_total > 0 else 0
            
            # Gráfico de Cascada (Waterfall) para Finanzas
            fig_fin = px.bar(
                x=['Inversión Total', 'Ingresos Brutos', 'Utilidad Neta'],
                y=[inversion_total, ventas_totales, utilidad],
                color=['Gastos', 'Ingresos', 'Ganancia'],
                color_discrete_map={'Gastos':'#ef5350', 'Ingresos':'#42a5f5', 'Ganancia':'#66bb6a'},
                text_auto='.2s',
                title=f"Proyección Financiera a {anos} años"
            )
            st.plotly_chart(fig_fin, use_container_width=True)
            
            m1, m2 = st.columns(2)
            m1.metric("ROI Estimado", f"{roi:.1f}%", delta="Rentabilidad")
            m2.metric("Utilidad Neta", f"${utilidad:,.0f}", delta="Cash Flow")

    # === TAB 4: DATOS ===
    with tab4:
        st.subheader("Base de Datos Maestra")
        st.dataframe(df, use_container_width=True)

else:
    st.warning("⚠️ No se pudieron cargar datos.")
    st.markdown(f"Verifica la URL de GitHub en la configuración o sube el archivo manual. \n\n URL actual intentada: `{github_url}`")
