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

# --- FUNCIONES AUXILIARES (PÉGALO AL PRINCIPIO DEL SCRIPT) ---
def extraer_fecha_filename(filename):
    """
    Versión mejorada: Busca cualquier fecha tipo YYYY-MM-DD en el nombre.
    """
    basename = os.path.basename(filename)
    
    # 1. Buscamos el patrón AAAA-MM-DD (Ej: 2025-12-31)
    # Esto encontrará la fecha aunque el archivo se llame "datos_2025-12-31.xlsx" o solo "2025-12-31.xlsx"
    match_iso = re.search(r'(\d{4}-\d{2}-\d{2})', basename)
    
    if match_iso:
        return pd.to_datetime(match_iso.group(1))
    
    # 2. Si falla lo anterior, usamos la fecha del sistema (pero te avisamos en la consola)
    fecha_sistema = datetime.fromtimestamp(os.path.getctime(filename))
    print(f"⚠️ AVISO: No se detectó fecha en el nombre de '{basename}'. Usando fecha sistema: {fecha_sistema}")
    return pd.to_datetime(fecha_sistema.date())

def cargar_todo_historial():
    """Carga todos los excels de la carpeta historial."""
    # Forzamos la búsqueda de cualquier Excel
    archivos = glob.glob(os.path.join(CARPETA_HISTORIAL, "*.xlsx"))
    lista_dfs = []
    
    # Ordenamos archivos para procesarlos en orden
    archivos.sort()

    print(f"📂 Archivos encontrados en historial: {len(archivos)}")
    
    for f in archivos:
        try:
            temp = pd.read_excel(f)
            # Validamos que tenga la columna fecha (estancia)
            if 'fecha' in temp.columns:
                temp['fecha'] = pd.to_datetime(temp['fecha'])
                
                # AQUÍ ESTÁ LA CLAVE: Usamos la nueva función de extracción
                fecha_detectada = extraer_fecha_filename(f)
                temp['fecha_snapshot'] = fecha_detectada
                
                lista_dfs.append(temp)
                print(f"   ✅ Cargado: {os.path.basename(f)} -> Fecha asignada: {fecha_detectada.date()}")
            else:
                print(f"   ❌ Omitido {os.path.basename(f)}: No tiene columna 'fecha'")

        except Exception as e:
            print(f"   ❌ Error cargando {f}: {e}")
            
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
# TAB 2: EVOLUCIÓN HISTÓRICA (BOOKING CURVE) - FINAL
# ---------------------------------------------------------
with tab2:
    st.header("⏳ Booking Curve (Ritmo de Llenado)")
    st.markdown("Selecciona un rango de estancia futura (ej. Semana Santa) y mira cómo se ha ido llenando día tras día.")

    # 1. BOTÓN DE CARGA Y AUDITORÍA
    if st.button("🔄 Recargar Base de Datos Histórica"):
        # Llamamos a la función global que debe tener la lógica regex actualizada
        df_full = cargar_todo_historial() 
        st.session_state['df_full'] = df_full
        
        # --- BLOQUE DE AUDITORÍA (Visualización de fechas detectadas) ---
        if not df_full.empty and 'fecha_snapshot' in df_full.columns:
            fechas_detectadas = df_full['fecha_snapshot'].unique()
            # Las ordenamos y convertimos a texto para leerlas fácil
            fechas_legibles = sorted([pd.to_datetime(f).strftime('%Y-%m-%d') for f in fechas_detectadas])
            
            st.success(f"✅ Base de datos actualizada. Se han procesado {len(fechas_detectadas)} archivos.")
            
            with st.expander("🕵️ Ver fechas de historial detectadas (Auditoría)", expanded=True):
                st.write("El sistema ha encontrado datos de estos días (Eje X de tu gráfica):")
                st.write(fechas_legibles)
                
                if len(fechas_detectadas) < 2:
                    st.warning("⚠️ ¡Atención! Solo veo 1 fecha única. Recuerda renombrar tus archivos viejos a '2025-12-31.xlsx' para que aparezca la evolución.")
        else:
            st.error("❌ No se han encontrado datos o ha fallado la carga.")

    # 2. VISUALIZACIÓN Y FILTROS
    if 'df_full' in st.session_state and not st.session_state['df_full'].empty:
        df_hist = st.session_state['df_full']
        
        # --- FILTROS ---
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            # Elegimos qué alojamiento analizar
            tipo_analisis = st.selectbox("Tipo de Alojamiento:", list(INVENTARIO_TOTAL.keys()))
        
        with col_f2:
            # Elegimos el rango de fechas DE ESTANCIA (ej. Agosto)
            st.write("Rango de fechas de Estancia a analizar:")
            rango_fechas = st.date_input("Selecciona inicio y fin:", [])

    # --- LÓGICA DE LA CURVA CORREGIDA ---
        if len(rango_fechas) == 2:
            start_date, end_date = pd.to_datetime(rango_fechas[0]), pd.to_datetime(rango_fechas[1])
            
            # 1. Filtramos por FECHA DE ESTANCIA (Cuándo viene el cliente)
            mask_estancia = (df_hist['fecha'] >= start_date) & (df_hist['fecha'] <= end_date)
            df_target = df_hist[mask_estancia].copy()

            if not df_target.empty:
                
                # --- A) CÁLCULO PARA LA GRÁFICA (EVOLUCIÓN) ---
                # Agrupamos por 'fecha_snapshot' para que sume los totales INDEPENDIENTES de cada día de carga
                curva_evolucion = df_target.groupby('fecha_snapshot')[tipo_analisis].sum().reset_index()
                curva_evolucion = curva_evolucion.sort_values('fecha_snapshot')
                
                # --- B) CÁLCULO PARA EL DATO ACTUAL (KPI REAL) ---
                # Para saber cuántas reservas hay HOY, solo miramos el último snapshot disponible
                ultimo_snapshot = df_target['fecha_snapshot'].max()
                df_ultimo_dia = df_target[df_target['fecha_snapshot'] == ultimo_snapshot]
                total_real_actual = int(df_ultimo_dia[tipo_analisis].sum())

                # Calculamos KPIs adicionales
                dias_rango = (end_date - start_date).days + 1
                capacidad_total_rango = INVENTARIO_TOTAL.get(tipo_analisis, 1) * dias_rango
                
                # % de Ocupación actual real
                ocupacion_real_pct = (total_real_actual / capacidad_total_rango) * 100

                # --- VISUALIZACIÓN ---
                st.subheader(f"Analizando: {tipo_analisis}")
                
                # MOSTRAR EL DATO CORRECTO (NO EL ACUMULADO)
                col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
                col_kpi1.metric("Noches Reservadas (OTB)", f"{total_real_actual}", help="Datos tomados del último archivo cargado")
                col_kpi2.metric("Capacidad Total Periodo", f"{capacidad_total_rango}")
                col_kpi3.metric("% Ocupación", f"{ocupacion_real_pct:.1f}%")

                st.caption(f"Evolución de reservas para estancias entre {start_date.date()} y {end_date.date()}")

                # Gráfica
                fig_curve = go.Figure()

                fig_curve.add_trace(go.Scatter(
                    x=curva_evolucion['fecha_snapshot'],
                    y=curva_evolucion[tipo_analisis], # Aquí Plotly ya usa el dato agrupado correctamente
                    mode='lines+markers+text',
                    name='Noches Vendidas',
                    text=curva_evolucion[tipo_analisis],
                    textposition="top center",
                    line=dict(color='royalblue', width=3)
                ))

                fig_curve.update_layout(
                    xaxis_title="Fecha de Toma de Datos (Snapshot)",
                    yaxis_title="Noches Vendidas (Acumulado a esa fecha)",
                    template="plotly_white",
                    hovermode="x unified"
                )

                st.plotly_chart(fig_curve, use_container_width=True)
                
            else:
                st.warning("No se encontraron reservas en el historial para ese rango de fechas de estancia.")
        
        else:
            st.info("👆 Selecciona una fecha de inicio y fin en el calendario para generar la curva.")

    else:
        st.info("Pulsa 'Recargar Base de Datos' para comenzar el análisis.")
