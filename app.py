import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime, timedelta
import os

# Configuración
st.set_page_config(page_title="📊 Shopify Analytics", layout="wide")

# Conexión a PostgreSQL
DB_URL = os.environ.get("DATABASE_URL")  # Railway env var
engine = create_engine(DB_URL)

# Fechas
today = datetime.today().date()
last_30 = today - timedelta(days=30)
previous_30 = last_30 - timedelta(days=30)

# Carga de datos
@st.cache_data(ttl=3600)
def load_data():
    query = f"""
        SELECT 
            order_id,
            shipping_country,
            fulfillment_created_at::date AS date,
            total,
            tipo_devolucion
        FROM shopify.raw_orders
        WHERE fulfillment_created_at::date >= '{previous_30}'
    """
    return pd.read_sql(query, engine)

df = load_data()

# Filtrado y resumen
df_last_30 = df[df["date"] >= last_30]
df_prev_30 = df[(df["date"] < last_30)]

def summarize(data):
    total_ventas = data["total"].sum()
    total_pedidos = data["order_id"].nunique()
    ticket_medio = total_ventas / total_pedidos if total_pedidos else 0
    devoluciones = data["tipo_devolucion"].notna().sum()
    return {
        "Pedidos": total_pedidos,
        "Ventas (€)": round(total_ventas, 2),
        "Ticket medio (€)": round(ticket_medio, 2),
        "Devoluciones": devoluciones
    }

st.title("📦 Shopify Pedidos - Últimos 30 días vs Anteriores")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Últimos 30 días")
    st.metric("Pedidos", summarize(df_last_30)["Pedidos"])
    st.metric("Ventas (€)", summarize(df_last_30)["Ventas (€)"])
    st.metric("Ticket medio", summarize(df_last_30)["Ticket medio (€)"])
    st.metric("Devoluciones", summarize(df_last_30)["Devoluciones"])

with col2:
    st.subheader("30 días anteriores")
    st.metric("Pedidos", summarize(df_prev_30)["Pedidos"])
    st.metric("Ventas (€)", summarize(df_prev_30)["Ventas (€)"])
    st.metric("Ticket medio", summarize(df_prev_30)["Ticket medio (€)"])
    st.metric("Devoluciones", summarize(df_prev_30)["Devoluciones"])

st.divider()
st.subheader("📈 Evolución por país")

df_grouped = df.groupby(["date", "shipping_country"]).agg({
    "order_id": "nunique",
    "total": "sum"
}).reset_index().rename(columns={
    "order_id": "pedidos",
    "total": "ventas"
})

selected_countries = st.multiselect(
    "Filtrar países", df_grouped["shipping_country"].unique().tolist(), default=None
)

if selected_countries:
    df_grouped = df_grouped[df_grouped["shipping_country"].isin(selected_countries)]

st.line_chart(df_grouped.pivot(index="date", columns="shipping_country", values="pedidos"))
