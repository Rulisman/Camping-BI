import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import glob
import re
from datetime import datetime

# --- CONFIGURACIÓN ---
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA_HISTORIAL = os.path.join(ROOT_DIR, 'historial')

if not os.path.exists(CARPETA_HISTORIAL):
    os.makedirs(CARPETA_HISTORIAL)

# Capacidad total por tipo
INVENTARIO_TOTAL = {
    'N-4': 30, 
    'N-6': 10,
    'ST2': 2,
    'ST4': 5,
    'ST5': 5
}

# --- FUNCIONES AUXILIARES ---

def extraer_fecha_filename(filename):
    """
    Intenta extraer la fecha del nombre del archivo formato 'backup_YYYY-MM-DD_HH-MM-SS.xlsx'
    """
    basename = os.path.basename(filename)
    match = re.search(r'backup_(\d{4}-\d{2}-\d{2})', basename)
    if match:
        return pd.to_datetime(match.group(1))
    # Si el archivo no tiene el formato esperado, usamos la fecha de creación del sistema
    return pd.to_datetime(datetime.fromtimestamp(os.path.getctime(filename)).strftime('%Y-%m-%d'))

def cargar_todo_historial():
    """Carga todos los excels de la carpeta historial en un único DataFrame."""
    archivos = glob.glob(os.path.join(CARPETA_HISTORIAL, "*.xlsx"))
    lista_dfs = []
    
    for f in archivos:
        try:
            temp = pd.read_excel(f)
            # Normalizamos fecha
            if 'fecha' in temp.columns:
                temp['fecha'] = pd.to_datetime(temp['fecha'])
                # Añadimos la fecha de captura (Snapshot Date)
                temp['fecha_snapshot'] = extraer_fecha_filename(f)
                lista_dfs.append(temp)
        except Exception as e:
            print(f"Error cargando {f}: {e}")
            
    if lista_dfs:
        return pd.concat(lista_dfs, ignore_index=True)
    return pd.DataFrame()

# --- INICIO DE LA PÁGINA ---
st.set_page_config(page_title="Revenue Manager Camping", layout="wide")
st.title("⛺ Revenue Management & Booking Curve")

# PESTAÑAS
tab1, tab2 = st.tabs(["📥 Análisis de Carga (Pick Up)", "📈 Evolución Histórica (Curvas)"])

# ---------------------------------------------------------
# TAB 1: ANÁLISIS DE PICK UP (Lo que tenías, mejorado)
# ---------------------------------------------------------
with tab1:
    st.markdown("### Comparativa: Carga Actual vs Último Historial")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        uploaded_file = st.file_uploader("Sube tu Excel actual", type=['xlsx'], key="upload_tab1")

    df_actual = None
    if uploaded_file is not None:
        df_actual = pd.read_excel(uploaded_file)
        df_actual['fecha'] = pd.to_datetime(df_actual['fecha'])
        
        # Guardar en sesión para usarlo en otras partes si fuera necesario
        st.session_state['df_actual'] = df_actual 
        
        # Buscar el último historial para comparar
        archivos_pasados = glob.glob(os.path.join(CARPETA_HISTORIAL, "*.xlsx"))
        df_pasado = None
        
        if archivos_pasados:
            ultimo_archivo = max(archivos_pasados, key=os.path.getctime)
            st.info(f"Comparando contra: **{os.path.basename(ultimo_archivo)}**")
            df_pasado = pd.read_excel(ultimo_archivo)
            df_pasado['fecha'] = pd.to_datetime(df_pasado['fecha'])
        else:
            st.warning("No hay historial previo para calcular Pick Up.")

        # --- CÁLCULO DE PICK UP DETALLADO ---
        if df_pasado is not None:
            # Hacemos merge
            df_merge = pd.merge(df_actual, df_pasado, on='fecha', suffixes=('_act', '_ant'), how='outer').fillna(0)
            
            # Selector de tipos
            tipos_disponibles = [k for k in INVENTARIO_TOTAL.keys() if k in df_actual.columns]
            tipos_sel = st.multiselect("Filtrar por tipo:", tipos_disponibles, default=tipos_disponibles)
            
            # KPI General
            st.subheader("Resumen General")
            kpi_cols = st.columns(len(tipos_sel))
            
            # Guardamos los datos de pickup para graficar
            df_pickup_graph = df_merge[['fecha']].copy()
            
            for idx, tipo in enumerate(tipos_sel):
                col_act = f'{tipo}_act'
                col_ant = f'{tipo}_ant'
                
                # Calculamos diferencia por día
                diff = df_merge[col_act] - df_merge[col_ant]
                df_pickup_graph[tipo] = diff
                
                total_pickup = int(diff.sum())
                kpi_cols[idx].metric(f"Total Pick Up {tipo}", f"{total_pickup}", delta=total_pickup)

            # --- GRÁFICA DE PICK UP POR FECHA (GRANULARIDAD) ---
            st.divider()
            st.subheader("📅 Detalle de Pick Up por Fecha de Estancia")
            st.markdown("¿Para qué fechas hemos ganado o perdido reservas?")
            
            # Transformamos a formato largo para Plotly
            df_long_pickup = df_pickup_graph.melt(id_vars='fecha', value_vars=tipos_sel, var_name='Tipo', value_name='Variacion')
            # Filtramos los ceros para limpiar la gráfica
            df_long_pickup = df_long_pickup[df_long_pickup['Variacion'] != 0]

            if not df_long_pickup.empty:
                fig_pu = px.bar(
                    df_long_pickup, 
                    x='fecha', 
                    y='Variacion', 
                    color='Tipo', 
                    title="Pick Up por Día (Positivo = Nuevas Reservas, Negativo = Cancelaciones)",
                    text_auto=True
                )
                fig_pu.update_layout(xaxis_title="Fecha de Estancia", yaxis_title="Noches Variación")
                st.plotly_chart(fig_pu, use_container_width=True)
            else:
                st.info("No hay variaciones entre los dos archivos para los tipos seleccionados.")

        # --- BOTÓN DE GUARDAR ---
        st.divider()
        if st.button("💾 Confirmar y Guardar en Historial"):
            fecha_hoy = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            nombre_archivo = f"backup_{fecha_hoy}.xlsx"
            ruta_destino = os.path.join(CARPETA_HISTORIAL, nombre_archivo)
            uploaded_file.seek(0)
            with open(ruta_destino, "wb") as f:
                f.write(uploaded_file.read())
            st.success(f"Guardado: {nombre_archivo}")

# ---------------------------------------------------------
# TAB 2: EVOLUCIÓN HISTÓRICA (BOOKING CURVES)
# ---------------------------------------------------------
with tab2:
    st.header("⏳ Curvas de Llenado (Pace)")
    st.markdown("Analiza cómo ha evolucionado la ocupación a lo largo del tiempo.")
    
    if st.button("🔄 Cargar/Actualizar Base de Datos Histórica"):
        df_full = cargar_todo_historial()
        st.session_state['df_full'] = df_full
        st.success(f"Cargados {len(df_full)} registros históricos.")
    
    if 'df_full' in st.session_state and not st.session_state['df_full'].empty:
        df_hist = st.session_state['df_full']
        
        # Filtros
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            tipo_analisis = st.selectbox("Selecciona Alojamiento:", list(INVENTARIO_TOTAL.keys()))
        with col_f2:
            # Filtramos fechas futuras o pasadas
            rango_fechas = st.date_input("Rango de fechas de estancia a analizar:", [])
        
        if len(rango_fechas) == 2:
            start_date, end_date = pd.to_datetime(rango_fechas[0]), pd.to_datetime(rango_fechas[1])
            
            # Filtramos el dataframe por el rango de fechas de ESTANCIA
            mask = (df_hist['fecha'] >= start_date) & (df_hist['fecha'] <= end_date)
            df_filtered = df_hist[mask].copy()

            if not df_filtered.empty:
                # Agrupamos por fecha de snapshot para ver cuántas reservas teníamos en cada momento
                # Sumamos la columna del tipo seleccionado
                evolucion = df_filtered.groupby('fecha_snapshot')[tipo_analisis].sum().reset_index()
                
                # Calculamos % ocupación sobre la capacidad total del rango seleccionado
                dias_rango = (end_date - start_date).days + 1
                capacidad_total_periodo = INVENTARIO_TOTAL[tipo_analisis] * dias_rango
                
                evolucion['Ocupacion %'] = (evolucion[tipo_analisis] / capacidad_total_periodo) * 100
                
                # Gráfica de línea
                fig_hist = go.Figure()
                fig_hist.add_trace(go.Scatter(
                    x=evolucion['fecha_snapshot'],
                    y=evolucion['Ocupacion %'],
                    mode='lines+markers',
                    name=f'Ocupación {tipo_analisis}'
                ))
                
                fig_hist.update_layout(
                    title=f"Evolución de ventas para estancias entre {start_date.date()} y {end_date.date()}",
                    xaxis_title="Fecha de Lectura (Cuándo miramos)",
                    yaxis_title="% Ocupación Acumulada"
                )
                st.plotly_chart(fig_hist, use_container_width=True)
                
                st.write("Datos de la gráfica:", evolucion)
                
            else:
                st.warning("No hay datos en el historial para ese rango de fechas.")
        else:
            st.info("Selecciona un rango de fechas (Inicio y Fin) para ver la curva.")
    else:
        st.info("Pulsa el botón de cargar historial para analizar las tendencias.")
