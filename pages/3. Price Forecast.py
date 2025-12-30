import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Forecasting 2026", layout="wide")

st.title("🏨 Revenue Manager AI - Estrategia 2026")
st.markdown("""
Esta herramienta analiza tu histórico (2023, 2024, 2025) y genera una estrategia de precios 
para la temporada 2026 (15 de Mayo - 13 de Septiembre).
""")

# --- BARRA LATERAL (CONFIGURACIÓN) ---
with st.sidebar:
    st.header("⚙️ Parámetros Revenue")
    st.write("Ajusta la sensibilidad del algoritmo:")
    
    umbral_alto = st.slider("Umbral Ocupación Alta (%)", 80, 99, 90, help="Si supera este %, subirá precio agresivamente.")
    umbral_bajo = st.slider("Umbral Ocupación Baja (%)", 10, 60, 50, help="Si baja de este %, bajará precio para estimular.")
    
    st.info("Sube tus archivos .csv o .xlsx en el panel principal.")

# --- FUNCIONES DE LÓGICA ---

def leer_archivo_robusto(file):
    """Lee Excel o CSV intentando detectar el formato español."""
    try:
        if file.name.endswith('.xlsx'):
            return pd.read_excel(file)
        elif file.name.endswith('.csv'):
            # Truco: leemos los primeros bytes para ver si usa ; o ,
            content = file.getvalue().decode('utf-8', errors='ignore')
            sep = ';' if ';' in content.splitlines()[0] else ','
            dec = ',' if sep == ';' else '.'
            
            # Volvemos al inicio del archivo para leerlo bien
            file.seek(0)
            return pd.read_csv(file, sep=sep, decimal=dec)
    except Exception as e:
        st.error(f"Error leyendo {file.name}: {e}")
        return None

def normalizar_datos(df):
    """Limpia nombres de columnas y datos."""
    # Estandarizar columnas
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
    
    # Validar
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

uploaded_files = st.file_uploader(
    "Arrastra aquí tus archivos históricos (2023, 2024, 2025...)", 
    type=['xlsx', 'csv'], 
    accept_multiple_files=True
)

if uploaded_files:
    all_data = []
    st.write("---")
    progreso = st.progress(0)
    
    for i, file in enumerate(uploaded_files):
        df = leer_archivo_robusto(file)
        if df is not None:
            df = normalizar_datos(df)
            if df is not None:
                all_data.append(df)
        progreso.progress((i + 1) / len(uploaded_files))
    
    if all_data:
        df_total = pd.concat(all_data, ignore_index=True)
        
        # Corregir porcentaje globalmente si es necesario
        df_total['Ocupacion'] = df_total['Ocupacion'].fillna(0)
        if df_total['Ocupacion'].max() > 1.5:
            df_total['Ocupacion'] = df_total['Ocupacion'] / 100

        # --- CÁLCULOS ---
        df_total['MesDia'] = df_total['Fecha'].dt.strftime('%m-%d')
        stats = df_total.groupby('MesDia')[['Precio', 'Ocupacion']].mean().reset_index()
        
        # Generar fechas 2026
        inicio = datetime(2026, 5, 15)
        fin = datetime(2026, 9, 13)
        dias = (fin - inicio).days + 1
        
        proyeccion = []
        for i in range(dias):
            fecha = inicio + timedelta(days=i)
            mes_dia = fecha.strftime('%m-%d')
            row = stats[stats['MesDia'] == mes_dia]
            
            if not row.empty:
                adr_hist = row.iloc[0]['Precio']
                occ_hist = row.iloc[0]['Ocupacion']
                nuevo_precio, estrategia = aplicar_yield_management(adr_hist, occ_hist)
                
                proyeccion.append({
                    'Fecha': fecha,
                    'Día': fecha.strftime('%A'), # Nombre del día
                    'ADR Histórico': round(adr_hist, 2),
                    'Ocupación Histórica (%)': round(occ_hist * 100, 1),
                    'Precio Recomendado 2026': round(nuevo_precio, 2),
                    'Estrategia': estrategia
                })
        
        if proyeccion:
            df_final = pd.DataFrame(proyeccion)
            
            # --- RESULTADOS ---
            col1, col2, col3 = st.columns(3)
            col1.metric("Días Proyectados", len(df_final))
            col2.metric("ADR Medio 2026", f"{df_final['Precio Recomendado 2026'].mean():.2f}€")
            dif_precio = df_final['Precio Recomendado 2026'].mean() - df_final['ADR Histórico'].mean()
            col3.metric("Incremento Medio", f"{dif_precio:.2f}€", delta_color="normal")
            
            # --- GRÁFICO ---
            st.subheader("📊 Evolución de Precios: Histórico vs 2026")
            
            chart_data = df_final[['Fecha', 'ADR Histórico', 'Precio Recomendado 2026']].set_index('Fecha')
            st.line_chart(chart_data, color=["#A9A9A9", "#00FF00"]) # Gris para histórico, Verde para nuevo
            
            # --- TABLA Y DESCARGA ---
            st.subheader("📋 Detalle Diario")
            st.dataframe(df_final.style.format({
                'ADR Histórico': '{:.2f}€',
                'Ocupación Histórica (%)': '{:.1f}%',
                'Precio Recomendado 2026': '{:.2f}€'
            }))
            
            # Botón Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Estrategia 2026')
            
            st.download_button(
                label="📥 Descargar Excel con Estrategia",
                data=buffer.getvalue(),
                file_name="Estrategia_Precios_2026.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        else:
            st.warning("Las fechas de tus archivos no coinciden con la temporada Mayo-Septiembre.")
    else:
        st.error("No se pudieron leer los datos. Revisa que los archivos tengan columnas Fecha, Precio y Ocupación.")