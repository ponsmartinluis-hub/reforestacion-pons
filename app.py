import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET
from io import BytesIO

# --- 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS MÓVILES ---
st.set_page_config(page_title="Monitor Cerrito del Carmen", layout="wide", page_icon="🌲")

# CSS para asegurar visibilidad en celulares (Fondo Blanco / Texto Oscuro)
st.markdown("""
    <style>
    /* Forzar fondo blanco y texto oscuro para evitar problemas de Modo Oscuro en cel */
    [data-testid="stAppViewContainer"] {
        background-color: #ffffff;
    }
    [data-testid="stHeader"] {
        background-color: rgba(255, 255, 255, 0.95);
    }
    /* Texto general en gris muy oscuro */
    h1, h2, h3, h4, h5, h6, p, li, span, div, label {
        color: #0f172a !important; 
    }
    /* Excepción: Textos dentro de métricas y botones */
    div[data-testid="stMetricValue"] {
        color: #1e3a8a !important; /* Azul Corporativo */
    }
    div[data-testid="stMetricLabel"] {
        color: #475569 !important; /* Gris medio */
    }
    /* Ajuste para las pestañas */
    button[data-baseweb="tab"] {
        color: #0f172a !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🌲 Dashboard Cerrito del Carmen")
st.markdown("**SOLEX Secure - Proyecto de Reforestación**")

# --- 2. FUNCIONES DE CARGA Y LIMPIEZA ---
@st.cache_data
def load_data(uploaded_file):
    try:
        # Detectar si es CSV o Excel
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        # LIMPIEZA CRÍTICA DE COLUMNAS (Basado en tu archivo real)
        # Elimina comas y puntos al final de los nombres (ej: "Coordenada_X," -> "Coordenada_X")
        df.columns = df.columns.str.strip().str.replace('[,.:]', '', regex=True)
        
        # Asegurar tipos de datos numéricos para coordenadas y medidas
        cols_num = ['Coordenada_X', 'Coordenada_Y', 'Altura_cm', 'Diametro_cm']
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        return df
    except Exception as e:
        st.error(f"Error procesando archivo: {e}")
        return None

def leer_kml(archivo_kml):
    """Lee el archivo KML de zonas"""
    zonas = []
    try:
        string_data = archivo_kml.getvalue().decode("utf-8")
        root = ET.fromstring(string_data)
        # Namespace usual de KML
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        # Buscar Placemarks (si no tiene namespace, intenta búsqueda genérica)
        placemarks = root.findall('.//kml:Placemark', ns)
        if not placemarks: 
            placemarks = root.findall('.//{http://www.opengis.net/kml/2.2}Placemark')

        for pm in placemarks:
            nombre = pm.find('.//{http://www.opengis.net/kml/2.2}name')
            nombre_txt = nombre.text if nombre is not None else "Zona Desconocida"
            
            coords = pm.find('.//{http://www.opengis.net/kml/2.2}coordinates')
            if coords is not None and coords.text:
                coords_raw = coords.text.strip().split()
                puntos = []
                for c in coords_raw:
                    val = c.split(',')
                    if len(val) >= 2:
                        # KML suele ser Lon, Lat -> Folium quiere Lat, Lon
                        puntos.append([float(val[1]), float(val[0])])
                zonas.append({'nombre': nombre_txt, 'puntos': puntos})
    except Exception as e:
        st.warning(f"No se pudo procesar estructura KML completa: {e}")
    return zonas

# --- 3. BARRA LATERAL ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1598/1598196.png", width=80)
    st.header("Carga de Datos")
    
    file_excel = st.file_uploader("📂 Subir Excel/CSV Plantación", type=["xlsx", "csv"])
    file_kml = st.file_uploader("🗺️ Subir Mapa (KML)", type=["kml", "txt", "xml"])
    
    st.divider()
    st.info("Sistema optimizado para visualización móvil.")

# --- 4. LÓGICA PRINCIPAL ---
if file_excel:
    df = load_data(file_excel)
    
    if df is not None:
        # --- PESTAÑAS ---
        tab1, tab2, tab3 = st.tabs(["📊 Resumen Ejecutivo", "🗺️ Mapa Georreferenciado", "📈 Análisis Detallado"])
        
        # === TAB 1: RESUMEN ===
        with tab1:
            st.subheader("Estado Actual de la Plantación")
            
            # KPIS
            col1, col2, col3, col4 = st.columns(4)
            total = len(df)
            saludables = len(df[df['Estado_Salud'].astype(str).str.contains('Excelente|Bueno', case=False, na=False)])
            magueyes = len(df[df['Tipo'].astype(str).str.upper() == 'MAGUEY'])
            
            col1.metric("Total Especímenes", total)
            col2.metric("Salud Excelente", saludables, delta=f"{saludables/total*100:.1f}%")
            col3.metric("Magueyes", magueyes)
            
            # Altura Promedio (si existe la columna)
            if 'Altura_cm' in df.columns:
                avg_alt = df['Altura_cm'].mean()
                col4.metric("Altura Promedio", f"{avg_alt:.1f} cm")
            else:
                col4.metric("Zonas", df['Poligono'].nunique())

            st.divider()

            # GRÁFICOS RESUMEN
            c_chart1, c_chart2 = st.columns(2)
            
            with c_chart1:
                # Conteo por Polígono (Basado en tu columna 'Poligono')
                if 'Poligono' in df.columns:
                    conteo_zona = df['Poligono'].value_counts().reset_index()
                    conteo_zona.columns = ['Zona', 'Cantidad']
                    fig_bar = px.bar(conteo_zona, x='Zona', y='Cantidad', color='Zona', 
                                     title="Distribución por Polígono", text='Cantidad')
                    st.plotly_chart(fig_bar, use_container_width=True)
            
            with c_chart2:
                # Estado de Salud
                if 'Estado_Salud' in df.columns:
                    fig_pie = px.pie(df, names='Estado_Salud', title="Estado de Salud General",
                                     color_discrete_sequence=px.colors.sequential.Teal)
                    st.plotly_chart(fig_pie, use_container_width=True)

        # === TAB 2: MAPA ===
        with tab2:
            st.subheader("Ubicación de Especímenes")
            
            # Validar coordenadas
            if 'Coordenada_X' in df.columns and 'Coordenada_Y' in df.columns:
                # Centro del mapa (Usando el primer punto válido o el promedio)
                lat_center = df['Coordenada_X'].mean()
                lon_center = df['Coordenada_Y'].mean()
                
                m = folium.Map(location=[lat_center, lon_center], zoom_start=17, tiles="OpenStreetMap")
                
                # Capa KML (Polígonos)
                if file_kml:
                    zonas = leer_kml(file_kml)
                    colores_zonas = ['#3388ff', '#ff33bb', '#33ff57', '#ff9933']
                    for i, z in enumerate(zonas):
                        color = colores_zonas[i % len(colores_zonas)]
                        folium.Polygon(
                            locations=z['puntos'], 
                            color=color, fill=True, fill_opacity=0.2, 
                            popup=f"Zona: {z['nombre']}"
                        ).add_to(m)

                # Capa Puntos (Árboles)
                for _, row in df.iterrows():
                    # Validar que no sean NaN
                    if pd.notnull(row['Coordenada_X']) and pd.notnull(row['Coordenada_Y']):
                        # Color por salud
                        color_pt = 'green'
                        estado = str(row.get('Estado_Salud', '')).lower()
                        if 'crítico' in estado or 'muerto' in estado: color_pt = 'red'
                        elif 'regular' in estado: color_pt = 'orange'
                        
                        tooltip_txt = f"{row.get('ID_Especimen', 'ID?')} - {row.get('Tipo', '')}"
                        
                        folium.CircleMarker(
                            location=[row['Coordenada_X'], row['Coordenada_Y']], # Tu CSV tiene X=Lat, Y=Lon
                            radius=4,
                            color=color_pt,
                            fill=True,
                            fill_opacity=0.8,
                            tooltip=tooltip_txt
                        ).add_to(m)
                
                st_folium(m, width="100%", height=500)
                
                st.caption("Verde: Excelente/Bueno | Naranja: Regular | Rojo: Crítico")
            else:
                st.warning("No se encontraron columnas de coordenadas válidas (Coordenada_X, Coordenada_Y).")

        # === TAB 3: ANÁLISIS ===
        with tab3:
            st.subheader("Análisis de Crecimiento y Especies")
            
            # Scatter Plot: Altura vs Diametro (Si existen las columnas del nuevo Excel)
            if 'Altura_cm' in df.columns and 'Diametro_cm' in df.columns:
                st.markdown("##### Correlación: Altura vs Diámetro")
                # Filtramos nulos para que la gráfica no falle
                df_clean = df.dropna(subset=['Altura_cm', 'Diametro_cm'])
                
                if not df_clean.empty:
                    fig_scatter = px.scatter(
                        df_clean, 
                        x='Diametro_cm', 
                        y='Altura_cm', 
                        color='Tipo', 
                        size='Altura_cm',
                        hover_data=['ID_Especimen', 'Poligono'],
                        title="Relación de Crecimiento (Tamaño = Altura)"
                    )
                    st.plotly_chart(fig_scatter, use_container_width=True)
                else:
                    st.info("Faltan datos de altura/diámetro para generar la gráfica.")
            
            st.markdown("##### Base de Datos Bruta")
            st.dataframe(df, use_container_width=True)

            # Botón de descarga corregido
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False)
            st.download_button("💾 Descargar Excel Procesado", data=output.getvalue(), file_name="Cerrito_Data_Procesada.xlsx")

else:
    # Pantalla de bienvenida si no hay archivo
    st.info("👋 Hola Pons. Por favor sube el archivo 'plantacion.xlsx' en la barra lateral para iniciar.")
