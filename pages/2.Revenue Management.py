import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import re
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN ---
# Inventario (Capacidad total)
INVENTARIO_TOTAL = {
    'N-4': 30, 
    'N-6': 10,
    'ST2': 2,
    'ST4': 5,
    'ST5': 5
}

# Nombre de la hoja dentro de tu Google Sheet (pestaña inferior)
HOJA_DB = "Datos"  # Asegúrate de que coincida con tu Google Sheet

# --- FUNCIONES DE BASE DE DATOS (GOOGLE SHEETS) ---

def cargar_datos_gsheet():
    """Descarga toda la base de datos desde Google Sheets."""
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet=HOJA_DB)
        
        # --- CORRECCIÓN FECHAS EUROPEAS ---
        if not df.empty and 'fecha_estancia' in df.columns:
            # dayfirst=True le dice: "El primer número es el día, no el mes"
            # errors='coerce' le dice: "Si hay una fecha basura, no explotes, ponla vacía (NaT)"
            df['fecha_estancia'] = pd.to_datetime(df['fecha_estancia'], dayfirst=True, errors='coerce')
            df['fecha_snapshot'] = pd.to_datetime(df['fecha_snapshot'], dayfirst=True, errors='coerce')
            
            # Limpiamos filas que hayan quedado con fechas vacías por error
            df = df.dropna(subset=['fecha_estancia', 'fecha_snapshot'])
            
        return df
    except Exception as e:
        # Este print saldrá en la consola negra de Manage App si hay error
        print(f"Error detalle: {e}") 
        return pd.DataFrame()

def guardar_en_gsheet(df_nuevo, fecha_snapshot):
    """Añade los datos nuevos al Google Sheet, borrando duplicados de la misma fecha."""
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # 1. Leer lo que hay actualmente
    df_actual = conn.read(worksheet=HOJA_DB)
    
    # 2. Preparar los datos nuevos (Formato Largo)
    tipos = [c for c in INVENTARIO_TOTAL.keys() if c in df_nuevo.columns]
    df_long = df_nuevo.melt(id_vars=['fecha'], value_vars=tipos, var_name='tipo_alojamiento', value_name='cantidad')
    df_long.rename(columns={'fecha': 'fecha_estancia'}, inplace=True)
    df_long['fecha_snapshot'] = fecha_snapshot.strftime('%Y-%m-%d')
    
    # Asegurar tipos en el DF nuevo
    df_long['fecha_estancia'] = pd.to_datetime(df_long['fecha_estancia'])
    df_long['fecha_snapshot'] = pd.to_datetime(df_long['fecha_snapshot'])
    
    if not df_actual.empty:
        # Asegurar tipos en el DF actual para poder filtrar
        df_actual['fecha_snapshot'] = pd.to_datetime(df_actual['fecha_snapshot'])
        
        # 3. BORRAR si ya existía una carga de ESTA misma fecha (para evitar duplicados si le das 2 veces)
        snapshot_actual_str = fecha_snapshot.strftime('%Y-%m-%d')
        # Filtramos para quedarnos con TODO lo que NO sea de hoy
        df_limpio = df_actual[df_actual['fecha_snapshot'].dt.strftime('%Y-%m-%d') != snapshot_actual_str]
        
        # 4. Concatenar lo viejo limpio + lo nuevo
        df_final = pd.concat([df_limpio, df_long], ignore_index=True)
    else:
        df_final = df_long

    # 5. SUBIR (Update) al Google Sheet
    # Ordenamos un poco para que el Excel se vea bonito
    df_final = df_final.sort_values(by=['fecha_snapshot', 'fecha_estancia'])
    conn.update(worksheet=HOJA_DB, data=df_final)
    
    return len(df_long)

def obtener_ultimo_snapshot_gsheet(df_hist):
    """Busca el snapshot anterior en el DF descargado."""
    if df_hist.empty:
        return None, None
    
    # Buscamos la fecha máxima
    fecha_max = df_hist['fecha_snapshot'].max()
    
    # Filtramos los datos de esa fecha
    df_ultimo = df_hist[df_hist['fecha_snapshot'] == fecha_max].copy()
    
    return df_ultimo, fecha_max

def extraer_fecha_filename(filename):
    match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if match:
        return pd.to_datetime(match.group(1))
    return datetime.now()

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Revenue Manager Cloud", layout="wide")
st.title("⛺ Revenue Management System (Google Sheets Edition)")

tab1, tab2 = st.tabs(["📥 Importar & Analizar Pick Up", "📈 Booking Curve (Tendencia)"])

# ---------------------------------------------------------
# TAB 1: IMPORTADOR + PICK UP
# ---------------------------------------------------------
with tab1:
    st.markdown("### 1. Análisis de Pick Up")
    st.info("Los datos se guardan en tu **Google Sheet privado**. No se borrarán al reiniciar.")
    
    # Cargar base de datos actual al inicio
    df_hist_global = cargar_datos_gsheet()
    
    uploaded_file = st.file_uploader("Sube tu Excel actual", type=['xlsx'])
    
    if uploaded_file is not None:
        # A) PROCESAR
        fecha_sugerida = extraer_fecha_filename(uploaded_file.name)
        
        try:
            df_actual_wide = pd.read_excel(uploaded_file)
            if 'fecha' in df_actual_wide.columns:
                df_actual_wide['fecha'] = pd.to_datetime(df_actual_wide['fecha'])
                # Renombrar para evitar el error de Merge
                df_actual_wide_merge = df_actual_wide.rename(columns={'fecha': 'fecha_estancia'})
            else:
                st.error("Falta columna 'fecha'")
                st.stop()
        except Exception as e:
            st.error(f"Error archivo: {e}")
            st.stop()

        # Formato largo para comparar
        tipos_disponibles = [c for c in INVENTARIO_TOTAL.keys() if c in df_actual_wide.columns]
        df_actual = df_actual_wide_merge.melt(id_vars=['fecha_estancia'], value_vars=tipos_disponibles, var_name='tipo_alojamiento', value_name='cantidad')

        # B) BUSCAR EL ANTERIOR EN LA DB DESCARGADA
        df_anterior, fecha_anterior = obtener_ultimo_snapshot_gsheet(df_hist_global)
        
        st.divider()
        
        # C) COMPARATIVA
        if df_anterior is not None:
            st.subheader(f"📊 Informe de Pick Up")
            st.caption(f"Comparando con snapshot: **{fecha_anterior.date()}**")
            
            df_merge = pd.merge(
                df_actual, df_anterior, 
                on=['fecha_estancia', 'tipo_alojamiento'], 
                how='outer', suffixes=('_new', '_old')
            ).fillna(0)
            
            df_merge['pickup'] = df_merge['cantidad_new'] - df_merge['cantidad_old']
            
            total_pickup = int(df_merge['pickup'].sum())
            cols = st.columns(len(tipos_disponibles) + 1)
            cols[0].metric("Total Pick Up", f"{total_pickup}", delta=total_pickup)
            
            for i, tipo in enumerate(tipos_disponibles):
                pk = int(df_merge[df_merge['tipo_alojamiento'] == tipo]['pickup'].sum())
                if pk != 0:
                    cols[i+1].metric(tipo, pk, delta=pk)
            
            df_graph = df_merge[df_merge['pickup'] != 0]
            if not df_graph.empty:
                fig = px.bar(df_graph, x='fecha_estancia', y='pickup', color='tipo_alojamiento', title="Pick Up por día")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sin cambios respecto a la última carga.")
        else:
            st.warning("Primera carga: No hay historial previo en el Google Sheet.")

        # D) GUARDAR
        st.divider()
        fecha_final = st.date_input("Fecha snapshot:", value=fecha_sugerida.date())
        
        if st.button("☁️ GUARDAR EN GOOGLE SHEETS", type="primary"):
            with st.spinner("Conectando con Google..."):
                filas = guardar_en_gsheet(df_actual_wide, fecha_final)
            st.success(f"¡Guardado! Tu Google Sheet ahora tiene los datos del {fecha_final}.")
            st.cache_data.clear() # Limpiar caché para recargar datos frescos
            st.rerun()

# ---------------------------------------------------------
# TAB 2: EVOLUCIÓN Y OCUPACIÓN REAL
# ---------------------------------------------------------
with tab2:
    st.header("⏳ Análisis de Tendencias y Ocupación")
    
    if st.button("🔄 Refrescar Datos"):
        st.cache_data.clear()
        st.rerun()
        
    # Usamos la variable cargada al inicio
    df_hist = df_hist_global
    
    if not df_hist.empty:
        # Filtros Superiores
        c1, c2 = st.columns(2)
        with c1:
            tipo = st.selectbox("Alojamiento:", list(INVENTARIO_TOTAL.keys()))
        with c2:
            fechas = st.date_input("Rango Estancia:", [])
            
        if len(fechas) == 2:
            start, end = pd.to_datetime(fechas[0]), pd.to_datetime(fechas[1])
            
            # Filtramos datos para ese tipo y rango de fechas
            mask = (df_hist['tipo_alojamiento'] == tipo) & (df_hist['fecha_estancia'] >= start) & (df_hist['fecha_estancia'] <= end)
            df_filt = df_hist[mask].copy()
            
            if not df_filt.empty:
                # --- PREPARACIÓN DE DATOS ---
                
                # 1. Datos para la CURVA (Evolución histórica)
                curva = df_filt.groupby('fecha_snapshot')['cantidad'].sum().reset_index().sort_values('fecha_snapshot')
                
                # 2. Datos para la OCUPACIÓN REAL (Foto actual del último día cargado)
                ultimo_snap = curva['fecha_snapshot'].max()
                df_actual_dia = df_filt[df_filt['fecha_snapshot'] == ultimo_snap].copy()
                
                # --- CÁLCULOS DE KPI (Occupancy %) ---
                capacidad_diaria = INVENTARIO_TOTAL.get(tipo, 1) # Capacidad de ese tipo (ej: 30 parcelas)
                total_noches_vendidas = curva[curva['fecha_snapshot'] == ultimo_snap]['cantidad'].values[0]
                
                # Capacidad total del periodo seleccionado (Días del rango * Unidades)
                dias_rango = (end - start).days + 1
                capacidad_total_periodo = capacidad_diaria * dias_rango
                
                # % Ocupación Media del periodo
                ocupacion_media = (total_noches_vendidas / capacidad_total_periodo) * 100
                
                # --- VISUALIZACIÓN DE KPIs ---
                col1, col2, col3 = st.columns(3)
                col1.metric(f"Total Noches Vendidas", f"{int(total_noches_vendidas)}")
                col2.metric("Capacidad Total Periodo", f"{capacidad_total_periodo} noches disp.")
                col3.metric("🔥 Ocupación Media", f"{ocupacion_media:.1f}%")
                
                st.divider()

                # --- GRÁFICA 1: BOOKING CURVE (PACE) ---
                st.subheader(f"📈 Curva de Llenado (Pace) - {tipo}")
                fig_curve = go.Figure()
                fig_curve.add_trace(go.Scatter(
                    x=curva['fecha_snapshot'], 
                    y=curva['cantidad'], 
                    mode='lines+markers', 
                    name='Noches Acumuladas',
                    line=dict(color='royalblue', width=3)
                ))
                fig_curve.update_layout(
                    xaxis_title="Fecha de Lectura", 
                    yaxis_title="Noches Vendidas",
                    template="plotly_white",
                    height=350
                )
                st.plotly_chart(fig_curve, use_container_width=True)

                # --- GRÁFICA 2: OCUPACIÓN DIARIA (REAL POR DÍA) ---
                st.divider()
                st.subheader(f"📅 Calendario de Ocupación Real (On The Books)")
                st.caption(f"Radiografía día a día según los datos más recientes ({ultimo_snap.date()})")
                
                # Agrupamos por día de estancia para ver ocupación diaria
                ocup_diaria = df_actual_dia.groupby('fecha_estancia')['cantidad'].sum().reset_index()
                
                # Calculamos % diario
                ocup_diaria['% Ocupacion'] = (ocup_diaria['cantidad'] / capacidad_diaria) * 100
                
                # Gráfica de Barras
                fig_bar = px.bar(
                    ocup_diaria,
                    x='fecha_estancia',
                    y='% Ocupacion',
                    title=f"Ocupación por Día - {tipo}",
                    labels={'fecha_estancia': 'Fecha Estancia', '% Ocupacion': '% Ocupación'},
                    text_auto='.0f', # Muestra el % sin decimales en la barra
                    color='% Ocupacion', # Pinta más oscuro si está más lleno
                    color_continuous_scale='Blues'
                )
                
                # Línea roja marcando el 100%
                fig_bar.add_hline(y=100, line_dash="dot", line_color="red", annotation_text="Completo (100%)")
                
                fig_bar.update_layout(
                    yaxis_range=[0, 110], # Dejamos aire arriba
                    template="plotly_white"
                )
                
                st.plotly_chart(fig_bar, use_container_width=True)

            else:
                st.warning("No hay datos para ese rango.")
    else:
        st.info("El Google Sheet está vacío.")
