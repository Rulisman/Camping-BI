import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Forecasting 2026", layout="wide")

st.title("🏨 Revenue Manager AI - Estrategia 2026 (Ponderada)")
st.markdown("""
Esta herramienta genera precios para la temporada 2026. 
**Mejora Inteligente:** Aplica mayor peso a los años recientes (2025/2024) para que la proyección sea más realista.
""")

# --- BARRA LATERAL (CONFIGURACIÓN) ---
with st.sidebar:
    st.header("⚙️ Configuración Algoritmo")
    
    # Opción para elegir el tipo de cálculo
    metodo_calculo = st.radio(
        "Método de Proyección:",
        ["Media Ponderada (Recomendado)", "Media Simple"],
        help="La Ponderada da más importancia a los últimos años. La Simple trata todos los años igual."
    )
    
    st.divider()
    st.write("📈 **Sensibilidad de Precios:**")
    umbral_alto = st.slider("Umbral Ocupación Alta (%)", 80, 99, 90)
    umbral_bajo = st.slider("Umbral Ocupación Baja (%)", 10, 60, 50)
    
    st.info("Sube tu archivo Excel con todas las pestañas históricas.")

# --- FUNCIONES ---

def normalizar_datos(df):
    """Limpia columnas y formatos."""
    mapa = {
        'fecha': 'Fecha', 'date': 'Fecha', 
        'precio': 'Precio', 'adr': 'Precio', 
        'ocupacion': 'Ocupacion', 'occ': 'Ocupacion', '% ocupacion': 'Ocupacion'
    }
    df.columns = [c.strip().lower() for c in df.columns]
    cols_renombradas = {}
    for col in df.columns:
        for k, v in mapa.items():
            if k in col:
                cols_renombradas[col] = v
                break
    df = df.rename(columns=cols_renombradas)
    
    if not {'Fecha', 'Precio', 'Ocupacion'}.issubset(df.columns):
        return None

    # Limpiar numéricos y fechas
    for col in ['Precio', 'Ocupacion']:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.replace('€','').str.replace('%','').str.replace(',','.').str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Fecha'])
    
    # Extraer el año para poder ponderar después
    df['Year'] = df['Fecha'].dt.year
    return df

def leer_excel_completo(file):
    validos = []
    try:
        xls = pd.ExcelFile(file)
        for sheet in xls.sheet_names:
            df = pd.read_excel(file, sheet_name=sheet)
            df_limpio = normalizar_datos(df)
            if df_limpio is not None and not df_limpio.empty:
                validos.append(df_limpio)
                # Mensaje discreto en sidebar
                st.sidebar.success(f"✅ Leído: {sheet} (Año detectado: {df_limpio['Year'].mode()[0]})")
    except Exception as e:
        st.error(f"Error: {e}")
        return None
    return pd.concat(validos, ignore_index=True) if validos else None

def calcular_estadisticas_ponderadas(df_total):
    """
    Calcula la media ponderada dando más peso a los años recientes.
    """
    df_total['MesDia'] = df_total['Fecha'].dt.strftime('%m-%d')
    
    # 1. Identificar años y asignar pesos
    years = sorted(df_total['Year'].unique())
    # Fórmula de peso: Posición en la lista (1, 2, 3...)
    # El año más antiguo tendrá peso 1, el más nuevo tendrá peso N
    weights = {year: i + 1 for i, year in enumerate(years)}
    
    # Mostrar los pesos usados al usuario
    if metodo_calculo == "Media Ponderada (Recomendado)":
        with st.expander("ℹ️ Ver Pesos aplicados por año"):
            st.write("Cuanto mayor es el peso, más influye en el precio 2026:")
            st.write(weights)
        
        # Aplicar pesos al dataframe
        df_total['Peso'] = df_total['Year'].map(weights)
    else:
        # Si es media simple, todos pesan 1
        df_total['Peso'] = 1

    # 2. Calcular valores ponderados (Precio * Peso)
    df_total['Precio_Ponderado'] = df_total['Precio'] * df_total['Peso']
    df_total['Ocupacion_Ponderada'] = df_total['Ocupacion'] * df_total['Peso']

    # 3. Agrupar por día del año y hacer la media ponderada
    # Fórmula: Suma(Valor * Peso) / Suma(Pesos)
    stats = df_total.groupby('MesDia').agg({
        'Precio_Ponderado': 'sum',
        'Ocupacion_Ponderada': 'sum',
        'Peso': 'sum'
    }).reset_index()

    stats['Precio_Medio'] = stats['Precio_Ponderado'] / stats['Peso']
    stats['Ocupacion_Media'] = stats['Ocupacion_Ponderada'] / stats['Peso']
    
    return stats

def aplicar_yield_management(precio_base, ocupacion):
    ocupacion_decimal = ocupacion / 100 if ocupacion > 1 else ocupacion
    if ocupacion_decimal >= (umbral_alto / 100):
        return precio_base * 1.15, "🔥 Subida Agresiva"
    elif 0.75 <= ocupacion_decimal < (umbral_alto / 100):
        return precio_base * 1.08, "📈 Subida Moderada"
    elif (umbral_bajo / 100) <= ocupacion_decimal < 0.75:
        return precio_base * 1.03, "🛡️ Ajuste IPC"
    else:
        return precio_base * 0.95, "🔻 Bajada Estímulo"

# --- INTERFAZ ---

uploaded_file = st.file_uploader("Sube tu Excel Histórico", type=['xlsx'])

if uploaded_file:
    st.divider()
    df_total = leer_excel_completo(uploaded_file)
    
    if df_total is not None:
        # Corrección % ocupación
        df_total['Ocupacion'] = df_total['Ocupacion'].fillna(0)
        if df_total['Ocupacion'].max() > 1.5:
            df_total['Ocupacion'] = df_total['Ocupacion'] / 100

        # --- CÁLCULO INTELIGENTE ---
        stats = calcular_estadisticas_ponderadas(df_total)
        
        # Generar 2026
        inicio = datetime(2026, 5, 15)
        fin = datetime(2026, 9, 13)
        dias = (fin - inicio).days + 1
        
        proyeccion = []
        for i in range(dias):
            fecha = inicio + timedelta(days=i)
            mes_dia = fecha.strftime('%m-%d')
            row = stats[stats['MesDia'] == mes_dia]
            
            if not row.empty:
                adr = row.iloc[0]['Precio_Medio']
                occ = row.iloc[0]['Ocupacion_Media']
                precio_rec, estrategia = aplicar_yield_management(adr, occ)
                
                proyeccion.append({
                    'Fecha': fecha,
                    'Día': fecha.strftime('%A'),
                    'ADR Histórico (Base)': round(adr, 2),
                    'Ocupación Histórica (%)': round(occ * 100, 1),
                    'Precio 2026': round(precio_rec, 2),
                    'Estrategia': estrategia
                })
        
        if proyeccion:
            df_final = pd.DataFrame(proyeccion)
            
            # Métricas
            c1, c2, c3 = st.columns(3)
            c1.metric("Días Proyectados", len(df_final))
            c2.metric("ADR Medio 2026", f"{df_final['Precio 2026'].mean():.2f}€")
            delta = df_final['Precio 2026'].mean() - df_final['ADR Histórico (Base)'].mean()
            c3.metric("Variación vs Base", f"{delta:.2f}€", delta_color="normal")
            
            # Gráfico
            st.subheader(f"Comparativa: Histórico ({metodo_calculo}) vs Estrategia 2026")
            chart_data = df_final[['Fecha', 'ADR Histórico (Base)', 'Precio 2026']].set_index('Fecha')
            st.line_chart(chart_data, color=["#A9A9A9", "#00FF00"])
            
            # Descarga
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Precios 2026')
            
            st.download_button("📥 Descargar Estrategia (.xlsx)", buffer, "Precios_2026_Smart.xlsx")
        else:
            st.warning("No hay datos coincidentes de fechas.")
