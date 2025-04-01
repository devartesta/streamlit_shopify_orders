import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go
from datetime import date, timedelta

# 🔌 Conexión a PostgreSQL
def get_connection():
    return psycopg2.connect(
        host=st.secrets["DBHOST"],
        database=st.secrets["DBNAME"],
        user=st.secrets["DBUSER"],
        password=st.secrets["DBPASSWORD"],
        port=st.secrets["DBPORT"]
    )

# 🌍 Lista de países
@st.cache_data
def get_country_list():
    with get_connection() as conn:
        df = pd.read_sql(
            "SELECT DISTINCT shipping_country FROM shopify.raw_orders WHERE shipping_country IS NOT NULL",
            conn
        )
    return ["Todos"] + sorted(df["shipping_country"].dropna().tolist())

# 📊 Consulta con vista diaria o mensual
def fetch_evolution(start_date, end_date, country, vista):
    with get_connection() as conn:
        date_trunc = "day" if vista == "Diaria" else "month"
        query = f"""
        WITH pedidos_agrupados AS (
            SELECT
                order_id,
                DATE_TRUNC('{date_trunc}', fulfillment_created_at)::date AS fecha,
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
        FROM pedidos_agrupados
        GROUP BY fecha, shipping_country
        ORDER BY fecha;
        """
        params = [start_date, end_date]
        if country != 'Todos':
            params.append(country)
        return pd.read_sql(query, conn, params=params)

# 🖥️ Interfaz
st.title("📦 Evolución de pedidos y ventas")

# Filtros
default_start = date.today() - timedelta(days=30)
default_end = date.today()

start_date = st.date_input("📅 Desde", default_start)
end_date = st.date_input("📅 Hasta", default_end)
country = st.selectbox("🌍 País", get_country_list())
vista = st.radio("📊 Vista", ["Diaria", "Mensual"], horizontal=True)

# Cargar datos
try:
    df = fetch_evolution(start_date, end_date, country, vista)
except Exception as e:
    st.error(f"❌ Error al consultar la base de datos: {e}")
    st.stop()

# Mostrar gráfico + tabla
if df.empty:
    st.warning("⚠️ No hay datos para el rango seleccionado.")
else:
    fig = go.Figure()

    # Eje 1: pedidos
    fig.add_trace(go.Scatter(
        x=df["fecha"],
        y=df["pedidos"],
        mode="lines+markers",
        name="Pedidos",
        yaxis="y1"
    ))

    # Eje 2: ventas
    fig.add_trace(go.Scatter(
        x=df["fecha"],
        y=df["ventas"],
        mode="lines+markers",
        name="Ventas (€)",
        yaxis="y2"
    ))

    fig.update_layout(
        title=f"Evolución {vista.lower()} de pedidos y ventas - {country}",
        xaxis=dict(title="Fecha"),
        yaxis=dict(title="Pedidos", side="left"),
        yaxis2=dict(title="Ventas (€)", overlaying="y", side="right"),
        legend=dict(x=0.01, y=0.99),
        margin=dict(l=40, r=40, t=60, b=40),
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)

    # Vista previa
    st.subheader("📄 Vista previa de los datos")
    st.dataframe(df)
