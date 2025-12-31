import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Forecasting 2026", layout="wide")

st.title("🏨 Revenue Manager AI - Estrategia 2026")
st.markdown("""
Esta herramienta lee **todas las pestañas** de tu Excel histórico (2022, 2023, 2024, 2025...) 
y genera una estrategia de precios optimizada para la temporada 2026.
""")

# --- BARRA LATERAL (CONFIGURACIÓN) ---
with st.sidebar:
    st.header("⚙️ Parámetros Revenue")
    st.write("Ajusta la sensibilidad del algoritmo:")
    
    umbral_alto = st.slider("Umbral Ocupación Alta (%)", 80, 99, 90, help="Si supera este %, subirá precio agresivamente.")
    umbral_bajo = st.slider("Umbral Ocupación Baja (%)", 10, 60, 50, help="Si baja de este %, bajará precio para estimular.")
    
    st.info("El algoritmo detectará automáticamente todas las hojas del Excel.")

# --- FUNCIONES DE LÓGICA ---

def normalizar_datos(df):
    """Limpia nombres de columnas y datos."""
    # Estandarizar columnas a minúsculas
    mapa = {
        'fecha': 'Fecha', 'date': 'Fecha', 
        'precio': 'Precio', 'adr': 'Precio', 
        'ocupacion': 'Ocupacion', 'occ': 'Ocupacion', '% ocupacion': 'Ocupacion'
    }
    df.columns = [c.strip().lower() for c in df.columns]
    
    # Renombrar columnas encontradas
    cols_renombradas = {}
    for col in df.columns:
        for k, v in mapa.items():
            if k in col:
                cols_renombradas[col] = v
                break
    df = df.rename(columns=cols_renombradas)
    
    # Validar si tiene las columnas necesarias
    if not {'Fecha', 'Precio', 'Ocupacion'}.issubset(df.columns):
        return None

    # Limpiar simbolos € y %
    for col in ['Precio', 'Ocupacion']:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.replace('€','').str.replace('%','').str.replace(',','.').str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Convertir fecha
    df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Fecha']) # Eliminar fechas invalidas
    
    return df

def leer_excel_completo(file):
    """
    Lee TODAS las hojas de un archivo Excel y las combina.
    """
    dataframes_validos = []
    
    try:
        xls = pd.ExcelFile(file)
        # Iteramos sobre CADA hoja detectada en el archivo
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(file, sheet_name=sheet_name)
            
            # Intentamos normalizar
            df_limpio = normalizar_datos(df)
            
            if df_limpio is not None and not df_limpio.empty:
                # Agregamos una columna para saber de qué año vino (opcional, para depurar)
                df_limpio['Origen'] = sheet_name
                dataframes_validos.append(df_limpio)
                st.sidebar.success(f"✅ Leída hoja: {sheet_name} ({len(df_limpio)} filas)")
            else:
                st.sidebar.warning(f"⚠️ Hoja '{sheet_name}' ignorada (no tiene columnas Fecha/Precio/Ocupacion).")
                
    except Exception as e:
        st.error(f"Error procesando el Excel: {e}")
        return None
        
    if dataframes_validos:
        return pd.concat(dataframes_validos, ignore_index=True)
    else:
        return None

def aplicar_yield_management(precio_base, ocupacion):
    """Aplica las reglas definidas en el sidebar."""
    ocupacion_decimal = ocupacion / 100 if ocupacion > 1 else ocupacion
    
    # Usamos los sliders del sidebar
    if ocupacion_decimal >= (umbral_alto / 100):
        return precio_base * 1.15, "🔥 Subida Agresiva (+15%)"
    elif 0.75 <= ocupacion_decimal < (umbral_alto / 100):
        return precio_base * 1.08, "📈 Subida Moderada (+8%)"
    elif (umbral_bajo / 100) <= ocupacion_decimal < 0.75:
        return precio_base * 1.03, "🛡️ Ajuste IPC (+3%)"
    else:
        return precio_base * 0.95, "🔻 Bajada Estímulo (-5%)"

# --- INTERFAZ PRINCIPAL ---

uploaded_file = st.file_uploader(
    "Sube tu archivo Excel con múltiples pestañas (2022, 2023, 2024...)", 
    type=['xlsx']
)

if uploaded_file:
    st.write("---")
    
    # 1. Leemos todo el contenido del Excel
    df_total = leer_excel_completo(uploaded_file)
    
    if df_total is not None:
        
        # 2. Corregir porcentaje globalmente si es necesario
        df_total['Ocupacion'] = df_total['Ocupacion'].fillna(0)
        # Si detectamos valores tipo 85, 90... los pasamos a 0.85, 0.90
        if df_total['Ocupacion'].max() > 1.5:
            df_total['Ocupacion'] = df_total['Ocupacion'] / 100

        # Mostramos resumen de datos ingeridos
        st.write(f"📊 **Datos Históricos Ingeridos:** {len(df_total)} días analizados.")
        st.dataframe(df_total.head())

        # 3. CÁLCULOS DE PROYECCIÓN
        # Agrupamos por Mes-Día para sacar el comportamiento histórico promedio
        df_total['MesDia'] = df_total['Fecha'].dt.strftime('%m-%d')
        
        # Calculamos la media de Precio y Ocupación para cada día del año (usando datos de 2022, 23, 24, 25)
        stats = df_total.groupby('MesDia')[['Precio', 'Ocupacion']].mean().reset_index()
        
        # 4. Generar calendario 2026
        inicio = datetime(2026, 5, 15)
        fin = datetime(2026, 9, 13)
        dias = (fin - inicio).days + 1
        
        proyeccion = []
        for i in range(dias):
            fecha = inicio + timedelta(days=i)
            mes_dia = fecha.strftime('%m-%d')
            
            # Buscamos si tenemos historia para este día (ej: 15 de Mayo)
            row = stats[stats['MesDia'] == mes_dia]
            
            if not row.empty:
                adr_hist = row.iloc[0]['Precio']
                occ_hist = row.iloc[0]['Ocupacion']
                
                # APLICAMOS LA IA DE REVENUE
                nuevo_precio, estrategia = aplicar_yield_management(adr_hist, occ_hist)
                
                proyeccion.append({
                    'Fecha': fecha,
                    'Día': fecha.strftime('%A'),
                    'ADR Histórico Promedio': round(adr_hist, 2),
                    'Ocupación Histórica Promedio (%)': round(occ_hist * 100, 1),
                    'Precio Recomendado 2026': round(nuevo_precio, 2),
                    'Estrategia': estrategia
                })
        
        if proyeccion:
            df_final = pd.DataFrame(proyeccion)
            
            # --- RESULTADOS ---
            col1, col2, col3 = st.columns(3)
            col1.metric("Días Proyectados 2026", len(df_final))
            col2.metric("ADR Medio Proyectado", f"{df_final['Precio Recomendado 2026'].mean():.2f}€")
            
            dif_precio = df_final['Precio Recomendado 2026'].mean() - df_final['ADR Histórico Promedio'].mean()
            col3.metric("Incremento vs Histórico", f"{dif_precio:.2f}€", delta_color="normal")
            
            # --- GRÁFICO ---
            st.subheader("📈 Estrategia de Precios 2026 (Basada en 4 años históricos)")
            
            chart_data = df_final[['Fecha', 'ADR Histórico Promedio', 'Precio Recomendado 2026']].set_index('Fecha')
            st.line_chart(chart_data, color=["#A9A9A9", "#00FF00"]) # Gris vs Verde
            
            # --- TABLA Y DESCARGA ---
            st.subheader("📋 Detalle Diario")
            st.dataframe(df_final.style.format({
                'ADR Histórico Promedio': '{:.2f}€',
                'Ocupación Histórica Promedio (%)': '{:.1f}%',
                'Precio Recomendado 2026': '{:.2f}€'
            }))
            
            # Botón Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Estrategia 2026')
            
            st.download_button(
                label="📥 Descargar Excel con Estrategia 2026",
                data=buffer.getvalue(),
                file_name="Estrategia_Precios_2026_Full.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        else:
            st.warning("No se encontraron coincidencias de fechas (Mayo-Septiembre) en tus datos históricos.")
    else:
        st.error("No se pudieron leer datos válidos del Excel. Revisa el formato de las columnas.")
