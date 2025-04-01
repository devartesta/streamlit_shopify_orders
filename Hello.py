import streamlit as st
import pandas as pd
import psycopg2
from datetime import date, timedelta

# Configuración de la página
st.set_page_config(page_title="📦 Análisis de Pedidos y Ventas", layout="wide")

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
st.title("📦 Análisis de Pedidos y Ventas")

# Filtros en columnas para mejor presentación
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    default_start = date.today() - timedelta(days=30)
    start_date = st.date_input("📅 Desde", default_start, key="start_date")

with col2:
    default_end = date.today()
    end_date = st.date_input("📅 Hasta", default_end, key="end_date")

with col3:
    country = st.selectbox("🌍 País", get_country_list(), key="country")

# Filtro de vista (diaria o mensual)
vista = st.radio("📊 Vista", ["Diaria", "Mensual"], horizontal=True, key="vista")

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

    # Formatear datos para la tabla
    df_display = df.copy()
    df_display["fecha"] = df_display["fecha"].apply(lambda x: x.strftime("%Y-%m-%d"))
    df_display["pedidos"] = df_display["pedidos"].astype(int)
    df_display["ventas"] = df_display["ventas"].apply(lambda x: f"€{x:,.2f}")

    # Renombrar columnas para la tabla
    df_display = df_display.rename(columns={
        "fecha": "Fecha",
        "shipping_country": "País",
        "pedidos": "Pedidos",
        "ventas": "Ventas"
    })

    # Estilo personalizado para la tabla
    def style_dataframe(df):
        return df.style.set_table_styles([
            # Estilo para el encabezado
            {
                "selector": "th",
                "props": [
                    ("background-color", "#1f77b4"),
                    ("color", "white"),
                    ("font-weight", "bold"),
                    ("text-align", "center"),
                    ("border", "1px solid #ddd"),
                    ("padding", "8px")
                ]
            },
            # Estilo para las filas
            {
                "selector": "td",
                "props": [
                    ("text-align", "center"),
                    ("border", "1px solid #ddd"),
                    ("padding", "8px")
                ]
            },
            # Estilo para filas alternas
            {
                "selector": "tr:nth-child(even)",
                "props": [
                    ("background-color", "#f2f2f2")
                ]
            },
            # Estilo para filas al pasar el mouse
            {
                "selector": "tr:hover",
                "props": [
                    ("background-color", "#e6f3ff")
                ]
            }
        ]).set_properties(**{
            "font-family": "Arial, sans-serif",
            "font-size": "14px"
        }).hide(axis="index")  # Ocultar el índice

    # Mostrar tabla
    st.subheader(f"Datos de pedidos y ventas - {country} ({vista})")
    st.write(style_dataframe(df_display))

    # Resumen estadístico
    st.subheader("📊 Resumen")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Pedidos", df["pedidos"].sum())
    with col2:
        st.metric("Total Ventas", f"€{df['ventas'].sum():,.2f}")
    with col3:
        st.metric("Promedio Diario", f"€{df['ventas'].mean():,.2f}")