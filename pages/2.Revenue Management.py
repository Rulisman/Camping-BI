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
            
# --- 5. GESTIÓN DE GUARDADO Y DESHACER ---
        st.divider()
        st.subheader("💾 Guardar datos en Historial")
        st.write("Guarda los datos actuales para que sirvan de comparación mañana.")

        # Contenedor para mensajes de estado
        status_container = st.empty()

        col_save, col_undo = st.columns([1, 1])

        with col_save:
            # Botón de Guardar
            if st.button("Confirmar y Guardar", type="primary"):
                fecha_hoy = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                nombre_archivo = f"backup_{fecha_hoy}.xlsx"
                ruta_destino = os.path.join(CARPETA_HISTORIAL, nombre_archivo)
                
                try:
                    uploaded_file.seek(0) # Rebobinamos el archivo por si acaso
                    with open(ruta_destino, "wb") as f:
                        f.write(uploaded_file.read())
                    
                    # Guardamos en la memoria de la sesión qué archivo acabamos de crear
                    st.session_state['ultimo_guardado'] = nombre_archivo
                    st.session_state['ruta_ultimo_guardado'] = ruta_destino
                    
                    status_container.success(f"✅ Archivo guardado: {nombre_archivo}")
                    
                    # Recargamos la app para que actualice las gráficas con el nuevo dato si se desea
                    # o simplemente para actualizar el estado del botón
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

        with col_undo:
            # Lógica para Deshacer (Solo aparece si acabamos de guardar algo)
            if 'ultimo_guardado' in st.session_state and os.path.exists(st.session_state['ruta_ultimo_guardado']):
                archivo_a_borrar = st.session_state['ultimo_guardado']
                
                st.warning(f"Último guardado: {archivo_a_borrar}")
                
                if st.button(f"🗑️ Deshacer (Borrar {archivo_a_borrar})"):
                    try:
                        os.remove(st.session_state['ruta_ultimo_guardado'])
                        
                        # Limpiamos el estado
                        del st.session_state['ultimo_guardado']
                        del st.session_state['ruta_ultimo_guardado']
                        
                        status_container.info(f"↩️ Se ha eliminado {archivo_a_borrar}. El historial ha vuelto a su estado anterior.")
                        
                        # Forzamos recarga para que desaparezca del historial visual
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"No se pudo borrar el archivo: {e}")
            
            elif 'ultimo_guardado' in st.session_state:
                # Si el archivo ya no existe (lo borraste manual), limpiamos el estado
                del st.session_state['ultimo_guardado']
                st.rerun()

# ---------------------------------------------------------
# TAB 2: EVOLUCIÓN HISTÓRICA (BOOKING CURVE) CORREGIDA
# ---------------------------------------------------------
with tab2:
    st.header("⏳ Booking Curve (Ritmo de Llenado)")
    st.markdown("Selecciona un rango de estancia futura (ej. Semana Santa) y mira cómo se ha ido llenando día tras día.")

    # Botón para refrescar la base de datos de archivos
    if st.button("🔄 Recargar Base de Datos Histórica"):
        df_full = cargar_todo_historial() # Asegúrate de tener definida esta función arriba
        st.session_state['df_full'] = df_full
        st.success(f"Base de datos actualizada. Se han encontrado {df_full['fecha_snapshot'].nunique()} archivos/snapshots diferentes.")

    # Verificamos si hay datos cargados
    if 'df_full' in st.session_state and not st.session_state['df_full'].empty:
        df_hist = st.session_state['df_full']
        
        # --- DEBUG (Opcional, para que veas si está leyendo bien las fechas) ---
        with st.expander("Ver fechas de archivos detectadas (Snapshots)"):
            fechas_detectadas = df_hist['fecha_snapshot'].unique()
            fechas_detectadas_str = [pd.to_datetime(f).strftime('%Y-%m-%d') for f in fechas_detectadas]
            st.write("El sistema tiene datos de los siguientes días de carga:", fechas_detectadas_str)
            if len(fechas_detectadas) < 2:
                st.warning("⚠️ ¡Atención! Solo hay 1 fecha de snapshot. Necesitas guardar archivos en días diferentes para ver una curva.")

        # --- FILTROS ---
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            # Elegimos qué alojamiento analizar
            tipo_analisis = st.selectbox("Tipo de Alojamiento:", list(INVENTARIO_TOTAL.keys()))
        
        with col_f2:
            # Elegimos el rango de fechas DE ESTANCIA (ej. Agosto)
            st.write("Rango de fechas de Estancia a analizar:")
            rango_fechas = st.date_input("Selecciona inicio y fin:", [])

        # --- LÓGICA DE LA CURVA ---
        if len(rango_fechas) == 2:
            start_date, end_date = pd.to_datetime(rango_fechas[0]), pd.to_datetime(rango_fechas[1])
            
            # 1. Filtramos: Nos quedamos solo con las filas que corresponden a la estancia seleccionada
            mask_estancia = (df_hist['fecha'] >= start_date) & (df_hist['fecha'] <= end_date)
            df_target = df_hist[mask_estancia].copy()

            if not df_target.empty:
                # 2. AGRUPAMOS POR SNAPSHOT (La clave del éxito)
                # Sumamos las habitaciones vendidas para ese rango de estancia, agrupadas por la fecha en que se tomó el dato.
                # Esto responde: "¿Cuántas reservas para Agosto teníamos el día 1? ¿Y el día 2? ¿Y el día 3?"
                
                curva_evolucion = df_target.groupby('fecha_snapshot')[tipo_analisis].sum().reset_index()
                
                # Ordenamos cronológicamente por fecha de snapshot para que la línea vaya de izquierda a derecha
                curva_evolucion = curva_evolucion.sort_values('fecha_snapshot')

                # 3. Calculamos KPIs adicionales (Ocupación %)
                dias_rango = (end_date - start_date).days + 1
                capacidad_total_rango = INVENTARIO_TOTAL.get(tipo_analisis, 1) * dias_rango
                
                curva_evolucion['% Ocupacion'] = (curva_evolucion[tipo_analisis] / capacidad_total_rango) * 100

                # --- VISUALIZACIÓN ---
                st.subheader(f"Evolución de ventas para: {tipo_analisis}")
                st.caption(f"Estancias entre {start_date.date()} y {end_date.date()}")

                fig_curve = go.Figure()

                # Línea de Ocupación
                fig_curve.add_trace(go.Scatter(
                    x=curva_evolucion['fecha_snapshot'],
                    y=curva_evolucion[tipo_analisis],
                    mode='lines+markers+text',
                    name='Noches Vendidas',
                    text=curva_evolucion[tipo_analisis],
                    textposition="top center",
                    line=dict(color='firebrick', width=3)
                ))

                fig_curve.update_layout(
                    xaxis_title="Fecha de Lectura (¿Cuándo miramos el dato?)",
                    yaxis_title="Total Noches Vendidas (OTB)",
                    template="plotly_white",
                    hovermode="x unified"
                )

                st.plotly_chart(fig_curve, use_container_width=True)
                
                # Tabla de datos crudos
                with st.expander("Ver datos de la tabla"):
                    st.dataframe(curva_evolucion)
            
            else:
                st.warning("No se encontraron reservas en el historial para ese rango de fechas de estancia.")
        
        else:
            st.info("👆 Selecciona una fecha de inicio y fin en el calendario para generar la curva.")

    else:
        st.info("Pulsa 'Recargar Base de Datos' para comenzar el análisis.")
