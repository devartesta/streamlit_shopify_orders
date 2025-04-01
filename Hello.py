import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from datetime import date, timedelta

# 🔌 Conexión a PostgreSQL usando secretos de Streamlit Cloud o .streamlit/secrets.toml
def get_connection():
    return psycopg2.connect(
        host=st.secrets["DBHOST"],
        database=st.secrets["DBNAME"],
        user=st.secrets["DBUSER"],
        password=st.secrets["DBPASSWORD"],
        port=st.secrets["DBPORT"]
    )

# 🌍 Lista de países únicos
@st.cache_data
def get_country_list():
    with get_connection() as conn:
        df = pd.read_sql(
            "SELECT DISTINCT shipping_country FROM shopify.raw_orders WHERE shipping_country IS NOT NULL",
            conn
        )
    return ["Todos"] + sorted(df["shipping_country"].dropna().tolist())

# 📈 Consulta de evolución diaria de pedidos y ventas
def fetch_evolution(start_date, end_date, country):
    with get_connection() as conn:
        query = f"""
        WITH pedidos_dia AS (
            SELECT
                order_id,
                fulfillment_created_at::date AS fecha,
                shipping_country,
                MAX(total) AS total
            FROM shopify.raw_orders
            WHERE fulfillment_created_at BETWEEN %s AND %s
            {f"AND shipping_country = %s" if country != 'Todos' else ""}
            GROUP BY order_id, fecha, shipping_country
        )
        SELECT
            fecha,
            shipping_country,
            COUNT(order_id) AS pedidos,
            SUM(total) AS ventas
        FROM pedidos_dia
        GROUP BY fecha, shipping_country
        ORDER BY fecha;
        """
        params = [start_date, end_date]
        if country != 'Todos':
            params.append(country)
        return pd.read_sql(query, conn, params=params)

# 🚀 App Streamlit
st.title("📦 Evolución de pedidos y ventas")

# Filtros
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
    # Transformar para gráfico multivariable
    df_long = df.melt(
        id_vars=["fecha"],
        value_vars=["pedidos", "ventas"],
        var_name="Métrica",
        value_name="Cantidad"
    )

    # Gráfico con Plotly
    fig = px.line(
        df_long,
        x="fecha",
        y="Cantidad",
        color="Métrica",
        markers=True,
        labels={"Cantidad": "Cantidad", "fecha": "Fecha", "Métrica": "Métrica"},
        title=f"Evolución diaria de pedidos y ventas - {country}"
    )
    st.plotly_chart(fig, use_container_width=True)

    # Vista previa de datos
    st.subheader("📄 Vista previa de los datos")
    st.dataframe(df)
