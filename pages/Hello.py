import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from datetime import date, timedelta

# Conexión a PostgreSQL
def get_connection():
    return psycopg2.connect(
        host=st.secrets["DB_HOST"],
        database=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        port=st.secrets["DB_PORT"]
    )

# Obtener lista de países disponibles
@st.cache_data
def get_country_list():
    with get_connection() as conn:
        df = pd.read_sql(
            "SELECT DISTINCT shipping_country FROM shopify.raw_orders WHERE shipping_country IS NOT NULL",
            conn
        )
    return ["Todos"] + sorted(df["shipping_country"].dropna().tolist())

# Consulta de evolución por fecha y país
def fetch_evolution(start_date, end_date, country):
    with get_connection() as conn:
        query = f"""
        SELECT 
            fulfillment_created_at::date AS fecha,
            shipping_country,
            COUNT(DISTINCT order_id) AS pedidos,
            SUM(DISTINCT total) AS ventas
        FROM shopify.raw_orders
        WHERE fulfillment_created_at BETWEEN %s AND %s
        {f"AND shipping_country = %s" if country != 'Todos' else ""}
        GROUP BY 1, 2
        ORDER BY 1;
        """
        params = [start_date, end_date]
        if country != 'Todos':
            params.append(country)
        return pd.read_sql(query, conn, params=params)

# Streamlit App
st.title("📦 Evolución de pedidos y ventas")

# Filtros de usuario
default_start = date.today() - timedelta(days=30)
default_end = date.today()

start_date = st.date_input("📅 Desde", default_start)
end_date = st.date_input("📅 Hasta", default_end)

country = st.selectbox("🌍 País", get_country_list())

# Cargar datos
try:
    df = fetch_evolution(start_date, end_date, country)
except Exception as e:
    st.error(f"❌ Error al consultar la base de datos: {e}")
    st.stop()

# Mostrar resultados
if df.empty:
    st.warning("⚠️ No hay datos para el rango seleccionado.")
else:
    fig = px.line(
        df, 
        x="fecha", 
        y=["pedidos", "ventas"],
        markers=True,
        labels={"value": "Cantidad", "fecha": "Fecha", "variable": "Métrica"},
        title=f"Evolución diaria de pedidos y ventas - {country}"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📄 Vista previa de datos")
    st.dataframe(df)
