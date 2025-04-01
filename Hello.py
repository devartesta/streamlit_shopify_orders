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
        SELECT
            DATE_TRUNC('{date_trunc}', fulfillment_created_at)::date AS fecha,
            shipping_country,
            COUNT(DISTINCT order_id) AS pedidos,
            SUM(total) AS ventas
        FROM shopify.raw_orders
        WHERE fulfillment_created_at BETWEEN %s AND %s
        {f"AND shipping_country = %s" if country != 'Todos' else ""}
        GROUP BY DATE_TRUNC('{date_trunc}', fulfillment_created_at), shipping_country
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
    # Preparar datos
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["pedidos"] = pd.to_numeric(df["pedidos"], errors="coerce").fillna(0)
    df["ventas"] = pd.to_numeric(df["ventas"], errors="coerce").fillna(0)

    # Si es "Todos" los países, agrupamos
    if country == "Todos":
        df = df.groupby("fecha").agg({"pedidos": "sum", "ventas": "sum"}).reset_index()

    # Crear gráfico
    fig = go.Figure()

    # Línea de pedidos (eje izquierdo)
    fig.add_trace(go.Scatter(
        x=df["fecha"],
        y=df["pedidos"],
        mode="lines+markers",
        name="Pedidos",
        line=dict(color="#1f77b4"),
        marker=dict(size=8),
        yaxis="y1"
    ))

    # Línea de ventas (eje derecho)
    fig.add_trace(go.Scatter(
        x=df["fecha"],
        y=df["ventas"],
        mode="lines+markers",
        name="Ventas (€)",
        line=dict(color="#ff7f0e"),
        marker=dict(size=8),
        yaxis="y2"
    ))

    # Configuración del layout
    fig.update_layout(
        title=f"Evolución {vista.lower()} de pedidos y ventas - {country}",
        xaxis=dict(
            title="Fecha",
            tickformat="%Y-%m-%d" if vista == "Diaria" else "%Y-%m"
        ),
        yaxis=dict(
            title="Pedidos",
            side="left",
            color="#1f77b4",
            range=[0, df["pedidos"].max() * 1.1]  # Ajustar rango para pedidos
        ),
        yaxis2=dict(
            title="Ventas (€)",
            overlaying="y",
            side="right",
            color="#ff7f0e",
            range=[0, df["ventas"].max() * 1.1]  # Ajustar rango para ventas
        ),
        legend=dict(x=0.01, y=0.99),
        margin=dict(l=50, r=50, t=60, b=40),
        hovermode="x unified",
        template="plotly_white"
    )

    st.plotly_chart(fig, use_container_width=True)

    # Vista previa de datos
    st.subheader("📄 Vista previa de los datos")
    st.dataframe(df.style.format({
        "fecha": "{:%Y-%m-%d}",
        "pedidos": "{:.0f}",
        "ventas": "€{:.2f}"
    }))