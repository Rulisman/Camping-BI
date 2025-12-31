import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io

# Configuración de la página
st.set_page_config(page_title="Informe Platja Brava", layout="wide")
st.title("📊 Informe Consolidado: KPIs y Estacionalidad")
st.markdown("Sube el archivo Excel con las pestañas **2023, 2024 y 2025** para generar el reporte.")

# 1. CARGA DE ARCHIVO
uploaded_file = st.file_uploader("Sube tu archivo Excel (Platja Brava)", type=["xlsx"])

if uploaded_file is not None:
    try:
        # Cargar Excel con las tres pestañas dinámicamente
        # Usamos sheet_name=None primero para ver qué hay, o forzamos los años si estás seguro
        years_to_load = [2023, 2024, 2025]
        sheets = {year: pd.read_excel(uploaded_file, sheet_name=str(year)) for year in years_to_load}
        
        st.success("✅ Archivo cargado correctamente. Procesando datos...")

        # === Procesamiento de datos ===
        resultados = {}
        
        # Diccionario para forzar meses en español (los servidores suelen estar en inglés)
        mapa_meses = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
            7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }

        for year, df in sheets.items():
            # Limpieza básica de nombres de columnas (por si acaso)
            df.columns = [c.strip() for c in df.columns]
            
            # Asegurar formato fecha
            df["Fecha"] = pd.to_datetime(df["Fecha"])
            df["Mes"] = df["Fecha"].dt.month

            # KPI básicos
            # Aseguramos que sean numéricos para evitar errores
            df["Ocupacion"] = pd.to_numeric(df["Ocupacion"], errors='coerce')
            df["Precio"] = pd.to_numeric(df["Precio"], errors='coerce')
            
            ocupacion_media = df["Ocupacion"].mean()
            adr_medio = df["Precio"].mean()
            # Cálculo RevPAR diario promedio
            revpar = (df["Ocupacion"] / 100 * df["Precio"]).mean()

            # Agrupar por mes
            estacionalidad = df.groupby("Mes").agg({
                "Ocupacion": "mean",
                "Precio": "mean"
            }).sort_index()
            
            estacionalidad["RevPAR"] = estacionalidad["Ocupacion"]/100 * estacionalidad["Precio"]

            # Mapear nombres de meses
            estacionalidad.index = estacionalidad.index.map(mapa_meses)
            
            temporada_alta = estacionalidad[estacionalidad["Ocupacion"] > 80]
            temporada_baja = estacionalidad[estacionalidad["Ocupacion"] < 40]

            resultados[year] = {
                "Ocupacion Media (%)": round(ocupacion_media, 2),
                "ADR Medio": round(adr_medio, 2),
                "RevPAR": round(revpar, 2),
                "Estacionalidad": estacionalidad,
                "Temporada Alta": temporada_alta,
                "Temporada Baja": temporada_baja
            }

        # === Construir DataFrames consolidados ===
        
        # 1. KPIs Anuales
        # Extraemos solo los valores escalares para el resumen
        data_resumen = {
            year: {k: v for k, v in valores.items() 
                   if k not in ["Estacionalidad", "Temporada Alta", "Temporada Baja"]}
            for year, valores in resultados.items()
        }
        resumen_kpi = pd.DataFrame(data_resumen).T

        # 2. Comparativa Mes a Mes
        # Usamos los índices del primer año disponible
        meses_index = resultados[2023]["Estacionalidad"].index
        comparativa = pd.DataFrame(index=meses_index)

        for year, valores in resultados.items():
            # Aseguramos que alineamos por índice (Mes)
            estac = valores["Estacionalidad"]
            comparativa[f"Ocupacion_{year} (%)"] = estac["Ocupacion"]
            comparativa[f"ADR_{year} (€)"] = estac["Precio"]
            comparativa[f"RevPAR_{year} (€)"] = estac["RevPAR"]

        # 3. Marcar temporadas (basado en 2025 como pediste)
        comparativa["Temporada Alta (2025)"] = comparativa.index.isin(resultados[2025]["Temporada Alta"].index)
        comparativa["Temporada Baja (2025)"] = comparativa.index.isin(resultados[2025]["Temporada Baja"].index)

        # === VISUALIZACIÓN EN STREAMLIT ===
        
        st.subheader("1. Resumen de KPIs Anuales")
        st.dataframe(resumen_kpi.style.format("{:.2f}"))

        # Gráfico 1: KPIs Anuales (Matplotlib adaptado)
        st.write("#### Evolución Anual")
        fig, ax1 = plt.subplots(figsize=(10, 5))
        
        # Barras Ocupación
        ax1.bar(resumen_kpi.index.astype(str), resumen_kpi["Ocupacion Media (%)"], alpha=0.6, label="Ocupación (%)", color="#1f77b4")
        ax1.set_ylabel("Ocupación Media (%)")
        ax1.set_ylim(0, 100)
        
        # Línea ADR
        ax2 = ax1.twinx()
        ax2.plot(resumen_kpi.index.astype(str), resumen_kpi["ADR Medio"], color='orange', marker='o', linewidth=2, label="ADR Medio (€)")
        ax2.set_ylabel("ADR Medio (€)")

        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax2.legend(lines + lines2, labels + labels2, loc="upper center", bbox_to_anchor=(0.5, 1.15), ncol=2)
        
        st.pyplot(fig)

        st.divider()

        st.subheader("2. Comparativa Mes a Mes")
        
        # Pestañas para organizar los gráficos
        tab1, tab2, tab3 = st.tabs(["Ocupación", "ADR", "RevPAR"])
        
        with tab1:
            st.write("#### Evolución de la Ocupación (%)")
            cols_ocup = [c for c in comparativa.columns if "Ocupacion" in c]
            st.line_chart(comparativa[cols_ocup]) # Usamos gráfico nativo de Streamlit que es interactivo
        
        with tab2:
            st.write("#### Evolución del ADR (€)")
            cols_adr = [c for c in comparativa.columns if "ADR" in c]
            st.line_chart(comparativa[cols_adr])

        with tab3:
            st.write("#### Evolución del RevPAR (€)")
            cols_revpar = [c for c in comparativa.columns if "RevPAR" in c]
            st.line_chart(comparativa[cols_revpar])

        # === EXPORTACIÓN EXCEL ===
        st.divider()
        st.subheader("3. Exportar Informe")

        # Crear buffer en memoria
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            resumen_kpi.to_excel(writer, sheet_name="Informe", startrow=0)
            st.write("Generando Excel consolidado...")
            # Dejamos espacio entre tablas
            comparativa.to_excel(writer, sheet_name="Informe", startrow=len(resumen_kpi)+4)
        
        # Botón de descarga
        st.download_button(
            label="📥 Descargar Informe Completo (.xlsx)",
            data=buffer.getvalue(),
            file_name="Informe_Platja_Brava_Consolidado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except ValueError as e:
        st.error(f"Error: Asegúrate de que el Excel tenga las pestañas '2023', '2024' y '2025'. Detalle: {e}")
    except Exception as e:
        st.error(f"Ocurrió un error inesperado: {e}")

else:
    st.info("Esperando archivo... Por favor súbelo en el panel superior.")