import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configuración de la página
st.set_page_config(page_title="Analítica de Reservas", layout="wide")

st.title("📊 Dashboard de Reservas e Ingresos")
st.write("Sube tus archivos Excel (.xls o .xlsx) para generar la comparativa automáticamente.")

# 1. Widget para subir archivos
archivos_subidos = st.file_uploader("Arrastra tus Excels aquí", type=['xls', 'xlsx'], accept_multiple_files=True)

if archivos_subidos:
    lista_dfs = []
    
    # Barra de progreso
    barra = st.progress(0)
    
    for i, archivo in enumerate(archivos_subidos):
        try:
            # En Streamlit leemos el objeto archivo directamente
            df = pd.read_excel(archivo)
            df.columns = df.columns.str.strip()
            
            if 'anio' in df.columns and 'mes' in df.columns and 'Total_Dep' in df.columns:
                df = df.dropna(subset=['anio', 'mes'])
                lista_dfs.append(df)
            else:
                st.warning(f"⚠️ {archivo.name} no tiene las columnas correctas.")
        except Exception as e:
            st.error(f"❌ Error en {archivo.name}: {e}")
        
        # Actualizar barra
        barra.progress((i + 1) / len(archivos_subidos))

    if lista_dfs:
        # 2. Procesamiento de datos
        df_total = pd.concat(lista_dfs, ignore_index=True)
        df_total['anio'] = df_total['anio'].astype(int)
        df_total['mes'] = df_total['mes'].astype(int)
        
        # Agrupar datos
        df_grouped = df_total.groupby(['anio', 'mes'])[['Reservas', 'Total_Dep']].sum().reset_index()
        
        # Mapa de meses
        mapa_meses = {1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun', 
                      7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'}
        df_grouped['nombre_mes'] = df_grouped['mes'].map(mapa_meses)

        anios = sorted(df_grouped['anio'].unique())

        # 3. Crear Gráfica Plotly
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            subplot_titles=("Evolución de RESERVAS", "Evolución de INGRESOS (€)")
        )

        for anio in anios:
            datos = df_grouped[df_grouped['anio'] == anio].sort_values('mes')
            
            # Reservas
            fig.add_trace(
                go.Scatter(
                    x=datos['nombre_mes'], y=datos['Reservas'],
                    name=f"{anio}", legendgroup=f"{anio}",
                    mode='lines+markers', marker=dict(size=8),
                    hovertemplate=f"<b>Año {anio}</b><br>Mes: %{{x}}<br>Reservas: %{{y}}<extra></extra>"
                ), row=1, col=1
            )

            # Ingresos
            fig.add_trace(
                go.Scatter(
                    x=datos['nombre_mes'], y=datos['Total_Dep'],
                    name=f"{anio}", legendgroup=f"{anio}", showlegend=False,
                    mode='lines+markers', line=dict(dash='dash'), marker=dict(symbol='square', size=8),
                    hovertemplate=f"<b>Año {anio}</b><br>Mes: %{{x}}<br>Ingresos: %{{y:,.2f}} €<extra></extra>"
                ), row=2, col=1
            )

        fig.update_layout(height=700, hovermode="x unified", template="plotly_white")
        fig.update_yaxes(title_text="Nº Reservas", row=1, col=1)
        fig.update_yaxes(title_text="Euros (€)", row=2, col=1)

        # 4. Mostrar en la web
        st.plotly_chart(fig, use_container_width=True)
        
        # Mostrar tabla de datos abajo (opcional)
        with st.expander("Ver datos brutos"):
            st.dataframe(df_grouped)

    else:
        st.error("No se pudieron procesar datos válidos.")
else:
    st.info("👆 Sube tus archivos Excel para comenzar.")