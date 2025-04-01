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
        query = """
        SELECT DISTINCT shipping_country 
        FROM shopify.raw_orders 
        WHERE shipping_country IS NOT NULL
        """
        df = pd.read_sql(query, conn)
    return ["Todos"] + sorted(df["shipping_country"].dropna().tolist())

# 📊 Consulta de datos
def fetch_evolution(start_date, end_date, country, vista):
    with get_connection() as conn:
        date_trunc = "day" if vista == "Diaria" else "month"
        query = f"""
        SELECT 
            DATE_TRUNC('{date_trunc}', fulfillment_created_at) AS fecha,
            shipping_country,
            COUNT(DISTINCT order_id) AS pedidos,
            SUM(total) AS ventas
        FROM shopify.raw_orders
        WHERE fulfillment_created_at BETWEEN %s AND %s
        {f"AND shipping_country = %s" if country != "Todos" else ""}
        GROUP BY DATE_TRUNC('{date_trunc}', fulfillment_created_at), shipping_country
        ORDER BY fecha
        """
        params = [start_date, end_date]
        if country != "Todos":
            params.append(country)
        df = pd.read_sql(query, conn, params=params)
    return df

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

# Procesar datos
if df.empty:
    st.warning("⚠️ No hay datos para el rango seleccionado.")
else:
    # Convertir fechas y valores numéricos
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    df["pedidos"] = pd.to_numeric(df["pedidos"], errors="coerce").fillna(0)
    df["ventas"] = pd.to_numeric(df["ventas"], errors="coerce").fillna(0)

    # Agrupar si es "Todos" los países
    if country == "Todos":
        df = df.groupby("fecha").agg({"pedidos": "sum", "ventas": "sum"}).reset_index()
    else:
        df = df[["fecha", "shipping_country", "pedidos", "ventas"]]

    # Depuración: Mostrar datos antes de graficar
    st.subheader("Datos antes de graficar:")
    st.dataframe(df)

    # Crear gráfico
    fig = go.Figure()

    # Añadir línea de pedidos (eje izquierdo)
    fig.add_trace(go.Scatter(
        x=df["fecha"],
        y=df["pedidos"],
        name="Pedidos",
        mode="lines+markers",
        line=dict(color="blue"),
        marker=dict(size=8)
    ))

    # Añadir línea de ventas (eje derecho)
    fig.add_trace(go.Scatter(
        x=df["fecha"],
        y=df["ventas"],
        name="Ventas (€)",
        mode="lines+markers",
        line=dict(color="orange"),
        marker=dict(size=8),
        yaxis="y2"
    ))

    # Configurar el layout del gráfico
    fig.update_layout(
        title=f"Evolución {vista.lower()} de pedidos y ventas - {country}",
        xaxis=dict(
            title="Fecha",
            type="date",
            tickformat="%Y-%m-%d" if vista == "Diaria" else "%Y-%m"
        ),
        yaxis=dict(
            title="Pedidos",
            side="left",
            color="blue",
            range=[0, df["pedidos"].max() * 1.2]  # Margen adicional para visibilidad
        ),
        yaxis2=dict(
            title="Ventas (€)",
            side="right",
            overlaying="y",
            color="orange",
            range=[0, df["ventas"].max() * 1.2]  # Margen adicional para visibilidad
        ),
        legend=dict(x=0.01, y=0.99),
        hovermode="x unified",
        template="plotly_white",
        margin=dict(l=50, r=50, t=60, b=40)
    )

    # Mostrar gráfico
    st.plotly_chart(fig, use_container_width=True)

    # Mostrar tabla de datos
    st.subheader("Vista previa de los datos")
    st.dataframe(df.style.format({
        "fecha": "{:%Y-%m-%d}",
        "pedidos": "{:.0f}",
        "ventas": "€{:.2f}"
    }))