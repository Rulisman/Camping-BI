import pandas as pd
import os
import glob
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# NOTA: En Codespaces no usamos 'google.colab' ni 'tkinter'.
# El script buscará archivos directamente en la carpeta donde se ejecuta.

def buscar_archivos_locales():
    """
    Busca automáticamente archivos .xlsx y .csv en la carpeta actual.
    """
    print("--- PASO 1: BUSCANDO ARCHIVOS ---")
    
    # Busca todos los Excel y CSV en la carpeta actual
    archivos_excel = glob.glob("*.xlsx")
    archivos_csv = glob.glob("*.csv")
    
    todos_los_archivos = archivos_excel + archivos_csv
    
    # Filtramos para no leernos a nosotros mismos (el archivo de salida)
    archivos_validos = [f for f in todos_los_archivos if "Estrategia_Precios" not in f]
    
    if not archivos_validos:
        print("❌ No encontré archivos de datos.")
        print("ℹ️  Instrucción: Arrastra tus archivos .csv o .xlsx a la barra lateral izquierda de este editor.")
        return []
    
    print(f"✅ Archivos detectados: {archivos_validos}")
    return archivos_validos

def leer_archivo_robusto(ruta):
    """
    Intenta leer el archivo probando diferentes formatos.
    """
    ext = os.path.splitext(ruta)[1].lower()
    try:
        if ext == '.xlsx':
            return pd.read_excel(ruta)
        elif ext == '.csv':
            try:
                # Intento 1: CSV estándar
                return pd.read_csv(ruta)
            except:
                pass
            # Intento 2: Formato Español
            return pd.read_csv(ruta, sep=';', decimal=',')
    except Exception as e:
        print(f"Error leyendo {ruta}: {e}")
        return None

def normalizar_columnas(df):
    """
    Estandariza los nombres de las columnas (Fecha, Precio, Ocupacion).
    """
    mapa = {
        'fecha': 'Fecha', 'date': 'Fecha', 
        'precio': 'Precio', 'adr': 'Precio', 'pvn': 'Precio',
        'ocupacion': 'Ocupacion', 'occ': 'Ocupacion', '% ocupacion': 'Ocupacion'
    }
    
    df.columns = [c.strip().lower() for c in df.columns]
    
    nuevo_mapa = {}
    for col in df.columns:
        for clave, valor in mapa.items():
            if clave in col:
                nuevo_mapa[col] = valor
                break
    
    if nuevo_mapa:
        df = df.rename(columns=nuevo_mapa)
    return df

def cargar_datos(archivos):
    lista_dfs = []
    print(f"\nProcesando {len(archivos)} archivos...")
    
    for archivo in archivos:
        df = leer_archivo_robusto(archivo)
        if df is not None:
            df = normalizar_columnas(df)
            
            if {'Fecha', 'Precio', 'Ocupacion'}.issubset(df.columns):
                # Limpieza de simbolos € y %
                for col in ['Precio', 'Ocupacion']:
                    if df[col].dtype == object:
                        df[col] = df[col].astype(str).str.replace('€', '').str.replace('%', '').str.replace(',', '.')
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                
                lista_dfs.append(df)
            else:
                print(f"⚠️ Saltando {archivo}: No tiene columnas Fecha/Precio/Ocupacion")
    
    if not lista_dfs: return None
    
    df_total = pd.concat(lista_dfs, ignore_index=True)
    df_total['Fecha'] = pd.to_datetime(df_total['Fecha'], dayfirst=True)
    
    # Corrección de porcentaje > 1.5
    df_total['Ocupacion'] = df_total['Ocupacion'].fillna(0)
    if df_total['Ocupacion'].max() > 1.5:
        print("ℹ️  Normalizando ocupación (dividiendo por 100)...")
        df_total['Ocupacion'] = df_total['Ocupacion'] / 100
        
    return df_total

def logica_revenue_manager(precio_base, ocupacion_historica):
    nuevo_precio = precio_base
    accion = "Mantener"
    
    if ocupacion_historica >= 0.90:
        nuevo_precio = precio_base * 1.15 
        accion = "Subida Agresiva (+15%)"
    elif 0.75 <= ocupacion_historica < 0.90:
        nuevo_precio = precio_base * 1.08
        accion = "Subida Moderada (+8%)"
    elif 0.50 <= ocupacion_historica < 0.75:
        nuevo_precio = precio_base * 1.03
        accion = "Ajuste IPC (+3%)"
    elif ocupacion_historica < 0.50:
        nuevo_precio = precio_base * 0.95
        accion = "Bajada Estimulo (-5%)"
        
    return round(nuevo_precio, 2), accion

def generar_proyeccion_2026(df_historico):
    print("\n--- PASO 2: CALCULANDO ESTRATEGIA 2026 ---")
    df_historico['MesDia'] = df_historico['Fecha'].dt.strftime('%m-%d')
    
    stats = df_historico.groupby('MesDia').agg({'Precio': 'mean', 'Ocupacion': 'mean'}).reset_index()
    
    inicio = datetime(2026, 5, 15)
    fin = datetime(2026, 9, 13)
    dias = (fin - inicio).days + 1
    
    proyeccion = []
    
    for i in range(dias):
        fecha = inicio + timedelta(days=i)
        mes_dia = fecha.strftime('%m-%d')
        dato = stats[stats['MesDia'] == mes_dia]
        
        if not dato.empty:
            adr, occ = dato.iloc[0]['Precio'], dato.iloc[0]['Ocupacion']
            precio, accion = logica_revenue_manager(adr, occ)
            
            proyeccion.append({
                'Fecha': fecha,
                'Fecha Texto': fecha.strftime('%Y-%m-%d'),
                'Día': fecha.strftime('%A'),
                'ADR Histórico': round(adr, 2),
                'Ocupación %': round(occ * 100, 1),
                'Precio Recomendado': precio,
                'Estrategia': accion
            })
            
    return pd.DataFrame(proyeccion)

def finalizar_proceso(df):
    nombre_salida = 'PlatjaBrava_Estrategia_2026.xlsx'
    
    # Generar Gráfico y guardarlo como imagen (Codespaces no muestra ventanas)
    plt.figure(figsize=(12, 6))
    plt.plot(df['Fecha'], df['ADR Histórico'], label='Histórico', linestyle='--', alpha=0.7)
    plt.plot(df['Fecha'], df['Precio Recomendado'], label='Proyección 2026', linewidth=2.5)
    plt.title('Estrategia de Precios 2026')
    plt.legend()
    plt.savefig('Grafico_Estrategia.png') # Guardamos imagen en vez de mostrarla
    print("\n✅ Gráfico guardado como 'Grafico_Estrategia.png'")
    
    # Guardar Excel
    df.drop(columns=['Fecha']).to_excel(nombre_salida, index=False)
    print(f"✅ Excel generado: {nombre_salida}")
    print("👉 Busca estos archivos en la barra lateral izquierda para descargarlos.")

# --- EJECUCIÓN ---
if __name__ == "__main__":
    archivos = buscar_archivos_locales()
    if archivos:
        df = cargar_datos(archivos)
        if df is not None:
            final = generar_proyeccion_2026(df)
            finalizar_proceso(final)