import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from datetime import date, timedelta

# Conexión a PostgreSQL
def get_connection():
    return psycopg2.connect(
        host=st.secrets["DBHOST"],
        database=st.secrets["DBNAME"],
        user=st.secrets["DBUSER"],
        password=st.secrets["DBPASSWORD"],
        port=st.secrets["DBPORT"]
    )

# Consulta con filtros dinámicos
def fetch_evolution(start_date, end_date, country):
    with get_connection() as conn:
        query = f"""
        SELECT 
            fulfillment_created_at::date AS fecha,
            shipping_country,
            COUNT(DISTINCT order_id) AS pedidos,
            SUM(total) AS ventas
        FROM shopify.raw_orders
        WHERE fulfillment_created_at BETWEEN %s AND %s
        {f"AND shipping_country = %s" if country != "Todos" else ""}
        GROUP BY 1, 2
        ORDER BY 1;
        """
        params = [start_date, end_date]
        if country != "Todos":
            params.append(country)
        return pd.read_sql(query, conn, params=params)

# Streamlit App
st.title("📈 Evolución de pedidos y ventas")

# Filtros
default_start = date.today() - timedelta(days=30)
default_end = date.today()

start_date = st.date_input("Desde", default_start)
end_date = st.date_input("Hasta", default_end)

# Obtener lista de países únicos
@st.cache_data
def get_country_list():
    with get_connection() as conn:
        df = pd.read_sql("SELECT DISTINCT shipping_country FROM shopify.raw_orders WHERE shipping_country IS NOT NULL", conn)
    return ["Todos"] + sorted(df["shipping_country"].dropna().tolist())

country = st.selectbox("Filtrar por país", get_country_list())

# Cargar y mostrar datos
df = fetch_evolution(start_date, end_date, country)

if not df.empty:
    fig = px.line(
        df, 
        x="fecha", 
        y=["pedidos", "ventas"], 
        markers=True,
        labels={"value": "Cantidad", "fecha": "Fecha", "variable": "Métrica"},
        title=f"Evolución diaria de pedidos y ventas - {country}"
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("No hay datos para el rango seleccionado.")
