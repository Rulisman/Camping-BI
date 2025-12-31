import streamlit as st
import pandas as pd
import plotly.graph_objects as go # Importamos Plotly
import os
import glob
from datetime import datetime

# --- CONFIGURACIÓN ---
# Rutas para que funcione dentro de la carpeta 'pages'
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA_HISTORIAL = os.path.join(ROOT_DIR, 'historial')

if not os.path.exists(CARPETA_HISTORIAL):
    os.makedirs(CARPETA_HISTORIAL)

# Ajusta tu inventario aquí (Capacidad total por tipo)
INVENTARIO_TOTAL = {
    'N-4': 20, 
    'N-6': 10,
    'ST2': 15,
    'ST4': 10,
    'ST5': 10
}

# --- INICIO DE LA PÁGINA ---
st.title("📊 Análisis de Revenue y Pick Up")
st.markdown("Sube el Excel generado por SQL para comparar con la semana anterior.")

# 1. SUBIDA DE ARCHIVO
uploaded_file = st.file_uploader("Sube tu archivo Excel (actual.xlsx)", type=['xlsx'])

if uploaded_file is not None:
    # Cargar datos actuales
    try:
        df_actual = pd.read_excel(uploaded_file)
        if 'fecha' in df_actual.columns:
            df_actual['fecha'] = pd.to_datetime(df_actual['fecha'])
        else:
            st.error("El archivo no tiene columna 'fecha'.")
            st.stop()
    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")
        st.stop()

    st.success(f"Archivo cargado: {len(df_actual)} días analizados.")

    # 2. BUSCAR HISTORIAL
    archivos_pasados = glob.glob(os.path.join(CARPETA_HISTORIAL, "*.xlsx"))
    df_pasado = None

    if archivos_pasados:
        ultimo_archivo = max(archivos_pasados, key=os.path.getctime)
        st.info(f"🔄 Comparando con historial: {os.path.basename(ultimo_archivo)}")
        df_pasado = pd.read_excel(ultimo_archivo)
        df_pasado['fecha'] = pd.to_datetime(df_pasado['fecha'])
    else:
        st.warning("⚠️ No hay historial previo. Se tomará este archivo como base.")

    # 3. CÁLCULOS
    tipos_alojamiento = [col for col in INVENTARIO_TOTAL.keys() if col in df_actual.columns]

    # A) Ocupación %
    df_ocupacion = df_actual.copy()
    for tipo in tipos_alojamiento:
        capacidad = INVENTARIO_TOTAL.get(tipo, 1)
        df_ocupacion[f'%_{tipo}'] = (df_ocupacion[tipo] / capacidad) * 100

    # B) Pick Up
    df_merge = None
    pickup_resumen = {}
    
    if df_pasado is not None:
        df_merge = pd.merge(df_actual, df_pasado, on='fecha', suffixes=('_act', '_ant'), how='left')
        df_merge = df_merge.fillna(0)
        
        for tipo in tipos_alojamiento:
            col_pickup = f'PickUp_{tipo}'
            df_merge[col_pickup] = df_merge[f'{tipo}_act'] - df_merge[f'{tipo}_ant']
            total = df_merge[col_pickup].sum()
            if total != 0:
                pickup_resumen[tipo] = int(total)

    # --- MOSTRAR METRICAS (KPIs) ---
    st.subheader("Resumen de Pick Up Semanal")
    if pickup_resumen:
        cols = st.columns(len(pickup_resumen))
        for i, (tipo, valor) in enumerate(pickup_resumen.items()):
            cols[i].metric(label=f"Pick Up {tipo}", value=f"{valor} noches", delta=str(valor))
    else:
        st.info("No hay cambios de reservas respecto a la última carga.")

    # 4. GRÁFICAS CON PLOTLY
    st.subheader("📈 Gráficas de Evolución")
    
    # --- GRÁFICA 1: Porcentaje de Ocupación ---
    fig_occ = go.Figure()

    for tipo in tipos_alojamiento:
        fig_occ.add_trace(go.Scatter(
            x=df_ocupacion['fecha'],
            y=df_ocupacion[f'%_{tipo}'],
            mode='lines+markers',
            name=tipo,
            hovertemplate='%{y:.1f}%<extra></extra>' # Formato bonito al pasar el ratón
        ))

    fig_occ.update_layout(
        title="Porcentaje de Ocupación por Fecha",
        yaxis_title="% Ocupado",
        yaxis_range=[0, 105], # Fija el eje Y hasta 100% (con margen)
        hovermode="x unified", # Muestra todas las series al pasar el ratón por una fecha
        template="plotly_white"
    )
    
    st.plotly_chart(fig_occ, use_container_width=True)

    # --- GRÁFICA 2: Pick Up (Si existe) ---
    if df_merge is not None:
        fig_pickup = go.Figure()
        hay_datos_pickup = False

        for tipo in tipos_alojamiento:
            # Solo añadimos al gráfico si hay movimiento
            if df_merge[f'PickUp_{tipo}'].sum() != 0:
                fig_pickup.add_trace(go.Bar(
                    x=df_merge['fecha'],
                    y=df_merge[f'PickUp_{tipo}'],
                    name=tipo
                ))
                hay_datos_pickup = True
        
        if hay_datos_pickup:
            fig_pickup.update_layout(
                title="Pick Up (Nuevas Reservas vs Semana Anterior)",
                yaxis_title="Noches Variación",
                barmode='group', # Barras agrupadas (pon 'relative' si prefieres apiladas)
                template="plotly_white"
            )
            # Añadir línea cero
            fig_pickup.add_hline(y=0, line_width=1, line_color="black")
            
            st.plotly_chart(fig_pickup, use_container_width=True)
        else:
            st.info("No hay variaciones visuales que mostrar.")
            
    else:
        st.write("Carga un segundo archivo la próxima semana para ver la gráfica de Pick Up.")

    # 5. GUARDAR EN HISTORIAL
    st.divider()
    st.write("### 💾 Guardar datos")
    st.write("Si los datos son correctos, guárdalos en el historial para la comparación de la semana que viene.")
    
    if st.button("Confirmar y Guardar en Historial"):
        fecha_hoy = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nombre_archivo = f"backup_{fecha_hoy}.xlsx"
        ruta_destino = os.path.join(CARPETA_HISTORIAL, nombre_archivo)
        
        with open(ruta_destino, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"✅ Archivo guardado correctamente en '{CARPETA_HISTORIAL}' como: {nombre_archivo}")