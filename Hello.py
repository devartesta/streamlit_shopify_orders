# streamlit_app.py
import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta

# Conexión a PostgreSQL
def get_connection():
    return psycopg2.connect(
        host=st.secrets["DBHOST"],
        database=st.secrets["DBNAME"],
        user=st.secrets["DBUSER"],
        password=st.secrets["DBPASSWORD"],
        port=st.secrets["DBPORT"]
    )

# Consulta principal
def fetch_summary():
    with get_connection() as conn:
        query = """
        WITH base AS (
            SELECT 
                order_id,
                fecha_creacion::date AS fecha,
                total,
                quantity,
                tiene_devolucion
            FROM shopify.raw_orders
            GROUP BY 1, 2, 3, 4, 5
        ), rango AS (
            SELECT 
                *,
                CASE 
                    WHEN fecha >= current_date - INTERVAL '30 days' THEN 'últimos_30_días'
                    WHEN fecha >= current_date - INTERVAL '60 days' THEN 'anteriores_30_días'
                    ELSE NULL
                END AS periodo
            FROM base
        )
        SELECT
            periodo,
            COUNT(DISTINCT order_id) AS pedidos,
            SUM(total) AS ventas,
            SUM(quantity) AS unidades,
            ROUND(AVG(total), 2) AS ticket_medio,
            ROUND(100.0 * SUM(CASE WHEN tiene_devolucion THEN 1 ELSE 0 END) / COUNT(DISTINCT order_id), 1) AS porcentaje_devoluciones
        FROM rango
        WHERE periodo IS NOT NULL
        GROUP BY periodo
        ORDER BY periodo DESC;
        """
        return pd.read_sql(query, conn)

# Interfaz Streamlit
st.title("Resumen de Pedidos Shopify")
df = fetch_summary()

if not df.empty:
    col1, col2 = st.columns(2)
    col1.metric("Pedidos últimos 30 días", int(df.iloc[0]["pedidos"]), 
                delta=int(df.iloc[0]["pedidos"]) - int(df.iloc[1]["pedidos"]))
    col2.metric("Ventas (€)", round(df.iloc[0]["ventas"], 2), 
                delta=round(df.iloc[0]["ventas"] - df.iloc[1]["ventas"], 2))

    st.dataframe(df)
else:
    st.warning("No se encontraron datos para los últimos 60 días.")
