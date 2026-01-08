import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import re
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN ---
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT_DIR, 'camping_revenue.db')

# Inventario (Capacidad total)
INVENTARIO_TOTAL = {
    'N-4': 30, 
    'N-6': 10,
    'ST2': 2,
    'ST4': 5,
    'ST5': 5
}

# --- GESTIÓN DE BASE DE DATOS (SQLITE) ---

def init_db():
    """Crea la tabla si no existe."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Creamos una tabla que guarde: fecha de estancia, tipo, cantidad y CUÁNDO tomamos el dato (snapshot)
    c.execute('''
        CREATE TABLE IF NOT EXISTS reservas (
            fecha_estancia TEXT,
            tipo_alojamiento TEXT,
            cantidad INTEGER,
            fecha_snapshot TEXT,
            PRIMARY KEY (fecha_estancia, tipo_alojamiento, fecha_snapshot)
        )
    ''')
    conn.commit()
    conn.close()

def guardar_en_db(df, fecha_snapshot):
    """Guarda el dataframe en la base de datos SQL."""
    conn = sqlite3.connect(DB_PATH)
    
    # Preparamos los datos para que tengan el formato correcto
    # Asumimos que el DF tiene columnas: fecha, N-4, N-6... (Formato ancho)
    # Lo pasamos a formato largo (fecha_estancia, tipo, cantidad)
    tipos = [c for c in INVENTARIO_TOTAL.keys() if c in df.columns]
    
    df_long = df.melt(id_vars=['fecha'], value_vars=tipos, var_name='tipo_alojamiento', value_name='cantidad')
    df_long.rename(columns={'fecha': 'fecha_estancia'}, inplace=True)
    
    # Añadimos la columna de la fecha de subida/snapshot
    df_long['fecha_snapshot'] = fecha_snapshot.strftime('%Y-%m-%d')
    
    # Limpiamos datos viejos de ESA misma fecha de snapshot para no duplicar si re-subes
    snapshot_str = fecha_snapshot.strftime('%Y-%m-%d')
    c = conn.cursor()
    c.execute("DELETE FROM reservas WHERE fecha_snapshot = ?", (snapshot_str,))
    conn.commit()
    
    # Guardamos lo nuevo
    df_long.to_sql('reservas', conn, if_exists='append', index=False)
    conn.close()
    return len(df_long)

def cargar_datos_db():
    """Lee todo el historial desde la base de datos."""
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM reservas"
    df = pd.read_sql(query, conn)
    conn.close()
    
    if not df.empty:
        # Convertimos textos a fechas reales de pandas
        df['fecha_estancia'] = pd.to_datetime(df['fecha_estancia'])
        df['fecha_snapshot'] = pd.to_datetime(df['fecha_snapshot'])
        # Renombramos para compatibilidad con tu lógica anterior
        df.rename(columns={'fecha_estancia': 'fecha'}, inplace=True)
    
    return df

def extraer_fecha_filename(filename):
    """Detecta la fecha en el nombre del archivo."""
    match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if match:
        return pd.to_datetime(match.group(1))
    return datetime.now()

# Inicializamos la DB al arrancar
init_db()

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Revenue Manager Camping PRO", layout="wide")
st.title("⛺ Revenue Management System (Database Edition)")

tab1, tab2 = st.tabs(["📥 Importador de Datos", "📈 Booking Curve (Evolución)"])

# ---------------------------------------------------------
# TAB 1: IMPORTADOR INTELIGENTE
# ---------------------------------------------------------
with tab1:
    st.markdown("### 1. Carga de Archivos al Sistema")
    st.info("Sube tus Excels aquí. El sistema detectará la fecha del nombre del archivo y la guardará en la base de datos.")
    
    uploaded_file = st.file_uploader("Sube un archivo (o varios uno a uno)", type=['xlsx'])
    
    if uploaded_file is not None:
        # 1. Detectar fecha sugerida
        fecha_sugerida = extraer_fecha_filename(uploaded_file.name)
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"Archivo: **{uploaded_file.name}**")
            # Leemos el excel
            try:
                df_upload = pd.read_excel(uploaded_file)
                if 'fecha' in df_upload.columns:
                    df_upload['fecha'] = pd.to_datetime(df_upload['fecha'])
                    st.success(f"✅ Leído correctamente: {len(df_upload)} días.")
                else:
                    st.error("❌ El excel no tiene columna 'fecha'.")
                    st.stop()
            except Exception as e:
                st.error(f"Error: {e}")
                st.stop()
                
        with col2:
            st.write("### 📅 ¿De qué fecha son estos datos?")
            # Permitimos al usuario CORREGIR la fecha si el nombre estaba mal
            fecha_final = st.date_input(
                "Fecha de captura (Snapshot):", 
                value=fecha_sugerida.date()
            )
            
            if st.button("💾 GUARDAR EN BASE DE DATOS", type="primary"):
                rows = guardar_en_db(df_upload, fecha_final)
                st.balloons()
                st.success(f"¡Guardado! Se han insertado {rows} registros con fecha de snapshot {fecha_final}.")
                st.markdown("**Ya puedes subir el siguiente archivo o ir a la pestaña de gráficas.**")

# ---------------------------------------------------------
# TAB 2: EVOLUCIÓN (BOOKING CURVE)
# ---------------------------------------------------------
with tab2:
    st.header("⏳ Análisis de Curvas de Llenado")
    
    if st.button("🔄 Actualizar Gráficas desde DB"):
        st.session_state['refresh'] = True

    # Cargamos desde SQL
    df_hist = cargar_datos_db()
    
    if not df_hist.empty:
        # PIVOTAMOS: La DB está en formato largo, la pasamos a ancho para facilitar algunos cálculos si fuera necesario,
        # pero para Plotly el formato largo es mejor.
        
        # --- AUDITORÍA DE FECHAS EN DB ---
        snapshots_disponibles = sorted(df_hist['fecha_snapshot'].unique())
        snapshots_str = [pd.to_datetime(d).strftime('%Y-%m-%d') for d in snapshots_disponibles]
        
        with st.expander("🕵️ Ver fechas disponibles en la Base de Datos", expanded=False):
            st.write(snapshots_str)
            if len(snapshots_disponibles) < 2:
                st.warning("⚠️ Solo tienes 1 fecha cargada en la base de datos. Sube más archivos de fechas distintas en la Tab 1.")

        # --- FILTROS ---
        c1, c2 = st.columns(2)
        with c1:
            tipo = st.selectbox("Alojamiento:", list(INVENTARIO_TOTAL.keys()))
        with c2:
            fechas_estancia = st.date_input("Rango de Estancia:", [])
            
        if len(fechas_estancia) == 2:
            start, end = pd.to_datetime(fechas_estancia[0]), pd.to_datetime(fechas_estancia[1])
            
            # Filtramos por tipo y fechas de estancia
            mask = (df_hist['tipo_alojamiento'] == tipo) & \
                   (df_hist['fecha'] >= start) & \
                   (df_hist['fecha'] <= end)
            
            df_filtered = df_hist[mask].copy()
            
            if not df_filtered.empty:
                # AGRUPAMOS POR SNAPSHOT
                curva = df_filtered.groupby('fecha_snapshot')['cantidad'].sum().reset_index()
                curva.sort_values('fecha_snapshot', inplace=True)
                
                # GRÁFICA
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=curva['fecha_snapshot'], 
                    y=curva['cantidad'],
                    mode='lines+markers+text',
                    text=curva['cantidad'],
                    textposition="top center",
                    name=tipo,
                    line=dict(color='firebrick', width=3)
                ))
                
                fig.update_layout(
                    title=f"Curva de Llenado: {tipo} (Estancias {start.date()} a {end.date()})",
                    xaxis_title="Fecha de Toma de Datos",
                    yaxis_title="Noches Vendidas Acumuladas",
                    template="plotly_white"
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No hay datos para esas fechas.")
    else:
        st.info("La base de datos está vacía. Ve a la Tab 1 e importa tus archivos Excel históricos.")
