import streamlit as st
import pandas as pd
import plotly.graph_objects as go # Librería Plotly para gráficos avanzados
import io

# Configuración de la página
st.set_page_config(page_title="Informe Platja Brava", layout="wide")
st.title("📊 Informe Consolidado: KPIs y Estacionalidad")
st.markdown("Sube el archivo Excel con las pestañas **2023, 2024 y 2025**.")

# 1. CARGA DE ARCHIVO
uploaded_file = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])

if uploaded_file is not None:
    try:
        years_to_load = [2022, 2023, 2024, 2025]
        # Leemos todas las pestañas
        sheets = {year: pd.read_excel(uploaded_file, sheet_name=str(year)) for year in years_to_load}
        
        st.success("✅ Datos cargados. Generando informe interactivo...")

        # === Procesamiento de datos ===
        resultados = {}
        
        mapa_meses = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
            7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }

        for year, df in sheets.items():
            df.columns = [c.strip() for c in df.columns]
            df["Fecha"] = pd.to_datetime(df["Fecha"])
            df["Mes"] = df["Fecha"].dt.month

            # Limpieza numérica
            df["Ocupacion"] = pd.to_numeric(df["Ocupacion"], errors='coerce')
            df["Precio"] = pd.to_numeric(df["Precio"], errors='coerce')
            
            # Cálculo KPIs
            ocupacion_media = df["Ocupacion"].mean()
            adr_medio = df["Precio"].mean()
            revpar = (df["Ocupacion"] / 100 * df["Precio"]).mean()

            # Estacionalidad
            estacionalidad = df.groupby("Mes").agg({
                "Ocupacion": "mean",
                "Precio": "mean"
            }).sort_index()
            
            estacionalidad["RevPAR"] = estacionalidad["Ocupacion"]/100 * estacionalidad["Precio"]
            estacionalidad.index = estacionalidad.index.map(mapa_meses)
            
            resultados[year] = {
                "Ocupacion Media (%)": round(ocupacion_media, 2),
                "ADR Medio": round(adr_medio, 2),
                "RevPAR": round(revpar, 2),
                "Estacionalidad": estacionalidad
            }

        # === Construir DataFrames ===
        # 1. KPIs Anuales
        data_resumen = {
            year: {k: v for k, v in valores.items() if k != "Estacionalidad"}
            for year, valores in resultados.items()
        }
        resumen_kpi = pd.DataFrame(data_resumen).T

        # 2. Comparativa Mes a Mes
        meses_index = resultados[2023]["Estacionalidad"].index
        comparativa = pd.DataFrame(index=meses_index)
        for year, valores in resultados.items():
            estac = valores["Estacionalidad"]
            comparativa[f"Ocupacion_{year} (%)"] = estac["Ocupacion"]
            comparativa[f"ADR_{year} (€)"] = estac["Precio"]
            comparativa[f"RevPAR_{year} (€)"] = estac["RevPAR"]

        # === VISUALIZACIÓN CON PLOTLY ===
        
        st.subheader("1. Evolución Anual (KPIs)")
        
        # --- GRÁFICO 1: Ocupación (Barras) vs ADR (Línea) ---
        fig = go.Figure()

        # Eje Y Primario (Izquierda) - Ocupación
        fig.add_trace(go.Bar(
            x=resumen_kpi.index.astype(str),
            y=resumen_kpi["Ocupacion Media (%)"],
            name="Ocupación (%)",
            marker_color='#1f77b4',
            opacity=0.6,
            yaxis='y1'
        ))

        # Eje Y Secundario (Derecha) - ADR
        fig.add_trace(go.Scatter(
            x=resumen_kpi.index.astype(str),
            y=resumen_kpi["ADR Medio"],
            name="ADR Medio (€)",
            marker_color='#ff7f0e',
            mode='lines+markers',
            line=dict(width=3),
            yaxis='y2'
        ))

        # Configuración del Layout (Doble Eje)
        fig.update_layout(
            title="Comparativa Anual: Ocupación vs Precio",
            yaxis=dict(title="Ocupación (%)", side="left", range=[0, 100]),
            yaxis2=dict(title="Precio Medio (€)", side="right", overlaying="y", showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(fig, use_container_width=True)
        
        # Mostrar tabla de datos anuales
        st.dataframe(resumen_kpi.style.format("{:.2f}"))

        st.divider()

        # --- GRÁFICOS MENSUALES (Comparativa) ---
        st.subheader("2. Comparativa Mensual")
        
        tab1, tab2, tab3 = st.tabs(["📊 Ocupación", "💰 ADR", "📈 RevPAR"])
        
        # Función auxiliar para gráficos de líneas mensuales
        def plot_mensual(metric_name, unit):
            fig_m = go.Figure()
            cols = [c for c in comparativa.columns if metric_name in c]
            colors = ['#cccccc', '#888888', '#00CC96'] # 2023 gris claro, 2024 gris oscuro, 2025 verde
            
            for i, col in enumerate(cols):
                year_label = col.split("_")[1].split(" ")[0] # Extraer año del nombre
                fig_m.add_trace(go.Scatter(
                    x=comparativa.index,
                    y=comparativa[col],
                    name=year_label,
                    mode='lines+markers',
                    line=dict(width=3 if '2025' in col else 1, color=colors[i] if i<3 else None)
                ))
            
            fig_m.update_layout(
                title=f"Evolución Mensual - {metric_name}",
                yaxis_title=unit,
                hovermode="x unified"
            )
            return fig_m

        with tab1:
            st.plotly_chart(plot_mensual("Ocupacion", "%"), use_container_width=True)
        
        with tab2:
            st.plotly_chart(plot_mensual("ADR", "€"), use_container_width=True)

        with tab3:
            st.plotly_chart(plot_mensual("RevPAR", "€"), use_container_width=True)

        # === EXPORTACIÓN ===
        st.divider()
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            resumen_kpi.to_excel(writer, sheet_name="Informe", startrow=0)
            comparativa.to_excel(writer, sheet_name="Informe", startrow=len(resumen_kpi)+4)
        
        st.download_button(
            label="📥 Descargar Informe Completo (.xlsx)",
            data=buffer.getvalue(),
            file_name="Informe_Platja_Brava_Consolidado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"Error procesando el archivo: {e}")

else:
    st.info("Sube tu archivo Excel para ver los gráficos interactivos.")
