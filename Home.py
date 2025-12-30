import streamlit as st

# 1. Configuración de la página (Título, icono y diseño ancho)
st.set_page_config(
    page_title="Camping BI",
    page_icon="⛺",
    layout="wide"
)

# 2. Encabezado y Título Principal
st.title("⛺ Business Intelligence para Camping")
st.markdown("---")

# 3. Mensaje de bienvenida y descripción
st.markdown("""
### ¡Bienvenido a tu panel de control!

Esta aplicación centraliza todas las herramientas de análisis para la gestión del camping.
Utiliza el **menú de la izquierda** para navegar entre las diferentes herramientas disponibles.

#### Módulos disponibles actualmente:
* **📊 Dashboard Principal:** Tu script de análisis actual.
* **📈 Futuros Módulos:** Espacio reservado para nuevas herramientas.
""")

# 4. (Opcional) Puedes poner una imagen bonita o métricas rápidas aquí
col1, col2 = st.columns(2)

with col1:
    st.info("💡 **Tip:** Puedes ocultar el menú de navegación haciendo clic en la 'X' arriba a la izquierda.")

with col2:
    st.success("✅ **Estado del sistema:** Todos los scripts están operativos.")