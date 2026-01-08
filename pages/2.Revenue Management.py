import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
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
    
    # Preparamos los datos: Pasamos de formato Ancho (Excel) a Largo (DB)
    tipos = [c for c in INVENTARIO_TOTAL.keys() if c in df.columns]
    
    df_long = df.melt(id_vars=['fecha'], value_vars=tipos, var_name='tipo_alojamiento', value_name='cantidad')
    df_long.rename(columns={'fecha': 'fecha_estancia'}, inplace=True)
    df_long['fecha_snapshot'] = fecha_snapshot.strftime('%Y-%m-%d')
    
    # Limpiamos datos viejos de ESA misma fecha de snapshot para no duplicar
    snapshot_str = fecha_snapshot.strftime('%Y-%m-%d')
    c = conn.cursor()
    c.execute("DELETE FROM reservas WHERE fecha_snapshot = ?", (snapshot_str,))
    conn.commit()
    
    # Guardamos lo nuevo
    df_long.to_sql('reservas', conn, if_exists='append', index=False)
    conn.close()
    return len(df_long)

def obtener_ultimo_snapshot_db():
    """Recupera los datos de la ÚLTIMA carga disponible en la DB para comparar."""
    if not os.path.exists(DB_PATH):
        return None, None
        
    conn = sqlite3.connect(DB_PATH)
    # 1. Buscamos cuál es la fecha más reciente registrada
    try:
        query_max_date = "SELECT MAX(fecha_snapshot) FROM reservas"
        fecha_max_str = pd.read_sql(query_max_date, conn).iloc[0,0]
        
        if not fecha_max_str:
            return None, None

        # 2. Descargamos los datos de esa fecha
        query_data = f"SELECT * FROM reservas WHERE fecha_snapshot = '{fecha_max_str}'"
        df_old = pd.read_sql(query_data, conn)
        df_old['fecha_estancia'] = pd.to_datetime(df_old['fecha_estancia'])
        
        conn.close()
        return df_old, pd.to_datetime(fecha_max_str)
    except:
        conn.close()
        return None, None

def cargar_datos_historicos_completos():
    """Lee todo el historial para la Tab 2."""
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM reservas", conn)
    conn.close()
    if not df.empty:
        df['fecha_estancia'] = pd.to_datetime(df['fecha_estancia'])
        df['fecha_snapshot'] = pd.to_datetime(df['fecha_snapshot'])
        df.rename(columns={'fecha_estancia': 'fecha'}, inplace=True)
    return df

def extraer_fecha_filename(filename):
    """Detecta la fecha en el nombre del archivo."""
    match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if match:
        return pd.to_datetime(match.group(1))
    return datetime.now()

# Inicializamos DB
init_db()

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Revenue Manager Pro", layout="wide")
st.title("⛺ Revenue Management System 3.0")

tab1, tab2 = st.tabs(["📥 Importar & Analizar Pick Up", "📈 Booking Curve (Tendencia)"])

# ---------------------------------------------------------
# TAB 1: IMPORTADOR + PICK UP (FUNCIONALIDAD RECUPERADA)
# ---------------------------------------------------------
with tab1:
    st.markdown("### 1. Análisis de Pick Up (Subida de Archivos)")
    st.info("Sube el archivo de HOY. El sistema lo comparará automáticamente con el ÚLTIMO archivo guardado en la base de datos.")
    
    uploaded_file = st.file_uploader("Sube tu Excel actual", type=['xlsx'])
    
    if uploaded_file is not None:
        # A) PROCESAR ARCHIVO ACTUAL
        fecha_sugerida = extraer_fecha_filename(uploaded_file.name)
        
        try:
            df_actual_wide = pd.read_excel(uploaded_file)
            if 'fecha' in df_actual_wide.columns:
                df_actual_wide['fecha'] = pd.to_datetime(df_actual_wide['fecha'])
            else:
                st.error("El archivo no tiene columna 'fecha'.")
                st.stop()
        except Exception as e:
            st.error(f"Error leyendo archivo: {e}")
            st.stop()

        # Transformamos el actual a formato largo para poder comparar fácil
        tipos_disponibles = [c for c in INVENTARIO_TOTAL.keys() if c in df_actual_wide.columns]
        df_actual = df_actual_wide.melt(id_vars=['fecha'], value_vars=tipos_disponibles, var_name='tipo_alojamiento', value_name='cantidad')

        # B) BUSCAR EL ANTERIOR EN LA DB
        df_anterior, fecha_anterior = obtener_ultimo_snapshot_db()
        
        st.divider()
        
        # C) COMPARATIVA (PICK UP)
        if df_anterior is not None:
            st.subheader(f"📊 Informe de Pick Up")
            st.caption(f"Comparando archivo actual (**{fecha_sugerida.date()}**) vs Base de Datos (**{fecha_anterior.date()}**)")
            
            # Hacemos Merge: Actual vs Anterior
            df_merge = pd.merge(
                df_actual, 
                df_anterior, 
                on=['fecha_estancia', 'tipo_alojamiento'], # Nota: en df_actual la llamamos 'fecha' pero al melt hay que alinear
                left_on=['fecha', 'tipo_alojamiento'],
                right_on=['fecha_estancia', 'tipo_alojamiento'],
                how='outer', 
                suffixes=('_new', '_old')
            ).fillna(0)
            
            # Calculamos diferencia (Pick Up)
            df_merge['pickup'] = df_merge['cantidad_new'] - df_merge['cantidad_old']
            
            # Usamos la fecha correcta (coalesce)
            df_merge['fecha_final'] = df_merge['fecha'].combine_first(df_merge['fecha_estancia'])
            
            # 1. KPIs Generales
            total_pickup = int(df_merge['pickup'].sum())
            cols = st.columns(len(tipos_disponibles) + 1)
            
            cols[0].metric("Total Pick Up Global", f"{total_pickup}", delta=total_pickup)
            
            for i, tipo in enumerate(tipos_disponibles):
                pickup_tipo = int(df_merge[df_merge['tipo_alojamiento'] == tipo]['pickup'].sum())
                if pickup_tipo != 0:
                    cols[i+1].metric(f"{tipo}", f"{pickup_tipo}", delta=pickup_tipo)
            
            # 2. Gráfica de Barras por Fecha (Donde se ven las variaciones)
            df_graph = df_merge[df_merge['pickup'] != 0].copy()
            
            if not df_graph.empty:
                fig_pickup = px.bar(
                    df_graph, 
                    x='fecha_final', 
                    y='pickup', 
                    color='tipo_alojamiento',
                    title="Detalle de Movimientos (Nuevas Reservas vs Cancelaciones)",
                    text_auto=True,
                    labels={'fecha_final': 'Fecha de Estancia', 'pickup': 'Variación Noches'}
                )
                fig_pickup.update_layout(xaxis_title="Fecha de Estancia")
                st.plotly_chart(fig_pickup, use_container_width=True)
            else:
                st.info("📉 No ha habido movimientos de reservas respecto a la última carga.")

        else:
            st.warning("⚠️ Es la primera vez que subes datos. No hay historial previo para calcular Pick Up todavía.")

        # D) BOTÓN DE GUARDAR (Al final, tras ver el análisis)
        st.divider()
        col_save, col_info = st.columns([1, 2])
        
        with col_save:
            st.write("### ¿Datos correctos?")
            fecha_final = st.date_input("Confirma la fecha de estos datos:", value=fecha_sugerida.date())
            
            if st.button("💾 GUARDAR EN HISTORIAL", type="primary"):
                rows = guardar_en_db(df_actual_wide, fecha_final)
                st.success(f"¡Guardado! Base de datos actualizada con {rows} registros del día {fecha_final}.")
                st.balloons()
                # Forzar recarga para que si vas a la Tab 2 ya salga
                st.session_state['refresh'] = True 

# ---------------------------------------------------------
# TAB 2: EVOLUCIÓN (BOOKING CURVE) - IGUAL QUE ANTES
# ---------------------------------------------------------
with tab2:
    st.header("⏳ Análisis de Curvas de Llenado")
    
    if st.button("🔄 Actualizar Gráficas"):
        pass # Streamlit recarga al pulsar
        
    df_hist = cargar_datos_historicos_completos()
    
    if not df_hist.empty:
        # Filtros
        c1, c2 = st.columns(2)
        with c1:
            tipo = st.selectbox("Alojamiento:", list(INVENTARIO_TOTAL.keys()))
        with c2:
            fechas_estancia = st.date_input("Rango de Estancia:", [])
            
        if len(fechas_estancia) == 2:
            start, end = pd.to_datetime(fechas_estancia[0]), pd.to_datetime(fechas_estancia[1])
            
            # Filtro fecha estancia + tipo
            mask = (df_hist['tipo_alojamiento'] == tipo) & \
                   (df_hist['fecha'] >= start) & \
                   (df_hist['fecha'] <= end)
            
            df_filtered = df_hist[mask].copy()
            
            if not df_filtered.empty:
                # 1. CURVA (Suma agrupada por snapshot)
                curva = df_filtered.groupby('fecha_snapshot')['cantidad'].sum().reset_index()
                curva.sort_values('fecha_snapshot', inplace=True)
                
                # 2. KPI ACTUAL (Último snapshot)
                ultimo_snapshot = df_filtered['fecha_snapshot'].max()
                total_actual = curva[curva['fecha_snapshot'] == ultimo_snapshot]['cantidad'].values[0]
                
                # Visualización
                st.metric(f"Total Noches Reservadas ({tipo})", int(total_actual))
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=curva['fecha_snapshot'], 
                    y=curva['cantidad'],
                    mode='lines+markers+text',
                    text=curva['cantidad'],
                    textposition="top left",
                    name=tipo,
                    line=dict(color='royalblue', width=3)
                ))
                
                fig.update_layout(
                    title=f"Curva de Evolución: {tipo}",
                    xaxis_title="Fecha de Lectura",
                    yaxis_title="Noches Acumuladas",
                    template="plotly_white"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No hay datos para ese rango.")
    else:
        st.info("Sube archivos en la Pestaña 1 para ver el historial.")
