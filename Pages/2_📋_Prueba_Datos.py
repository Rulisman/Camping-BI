import streamlit as st
import pandas as pd
import numpy as np

st.title("📋 Análisis de Prueba")
st.write("Esta es una segunda página independiente.")

# Un gráfico de ejemplo simple
chart_data = pd.DataFrame(np.random.randn(20, 3), columns=["A", "B", "C"])
st.line_chart(chart_data)