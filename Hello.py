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
st.markdown("Explora los datos de pedidos y ventas con filtros personalizados.")

# Filtros en columnas para mejor presentación
col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

with col1:
    default_start = date.today() - timedelta(days=30)
    start_date = st.date_input("📅 Desde", default_start, key="start_date")

with col2:
    default_end = date.today()
    end_date = st.date_input("📅 Hasta", default_end, key="end_date")

with col3:
    country = st.selectbox("🌍 País", get_country_list(), key="country")

with col4:
    vista = st.selectbox("📊 Vista", ["Diaria", "Mensual"], key="vista")

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
                    ("background-color", "#2c3e50"),  # Fondo oscuro elegante
                    ("color", "white"),
                    ("font-weight", "bold"),
                    ("text-align", "center"),
                    ("border", "1px solid #34495e"),
                    ("padding", "12px"),
                    ("font-family", "Roboto, sans-serif"),
                    ("font-size", "16px"),
                    ("box-shadow", "0 2px 4px rgba(0,0,0,0.1)")
                ]
            },
            # Estilo para las filas
            {
                "selector": "td",
                "props": [
                    ("text-align", "center"),
                    ("border", "1px solid #ecf0f1"),
                    ("padding", "10px"),
                    ("font-family", "Roboto, sans-serif"),
                    ("font-size", "14px"),
                    ("color", "#2c3e50")
                ]
            },
            # Estilo para filas alternas
            {
                "selector": "tr:nth-child(even)",
                "props": [
                    ("background-color", "#f5f7fa")  # Fondo gris claro
                ]
            },
            # Estilo para filas al pasar el mouse
            {
                "selector": "tr:hover",
                "props": [
                    ("background-color", "#dfe6e9"),  # Resaltado al pasar el mouse
                    ("transition", "background-color 0.3s ease")
                ]
            },
            # Estilo para la tabla completa
            {
                "selector": "",
                "props": [
                    ("border-collapse", "collapse"),
                    ("box-shadow", "0 4px 8px rgba(0,0,0,0.1)"),
                    ("border-radius", "8px"),
                    ("overflow", "hidden")
                ]
            }
        ]).set_caption(f"Datos de pedidos y ventas - {country} ({vista})").set_properties(**{
            "background-color": "white",
            "border": "1px solid #ecf0f1"
        }).hide(axis="index")  # Ocultar el índice

    # Mostrar tabla
    st.markdown("### 📋 Tabla de Datos")
    st.write(style_dataframe(df_display), unsafe_allow_html=True)

    # Resumen estadístico con tarjetas más elaboradas
    st.markdown("### 📊 Resumen Estadístico")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="Total Pedidos",
            value=f"{int(df['pedidos'].sum()):,}",
            delta=f"{int(df['pedidos'].mean()):,} (promedio diario)",
            delta_color="normal"
        )
    with col2:
        st.metric(
            label="Total Ventas",
            value=f"€{df['ventas'].sum():,.2f}",
            delta=f"€{df['ventas'].mean():,.2f} (promedio diario)",
            delta_color="normal"
        )
    with col3:
        st.metric(
            label="Día con Más Pedidos",
            value=f"{int(df['pedidos'].max()):,}",
            delta=f"{df['fecha'][df['pedidos'].idxmax()].strftime('%Y-%m-%d')}",
            delta_color="off"
        )
    with col4:
        st.metric(
            label="Día con Más Ventas",
            value=f"€{df['ventas'].max():,.2f}",
            delta=f"{df['fecha'][df['ventas'].idxmax()].strftime('%Y-%m-%d')}",
            delta_color="off"
        )

    # Opción para descargar los datos
    st.markdown("### 💾 Descargar Datos")
    csv = df_display.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Descargar como CSV",
        data=csv,
        file_name=f"pedidos_ventas_{country}_{vista.lower()}_{start_date}_a_{end_date}.csv",
        mime="text/csv",
        help="Descarga los datos en formato CSV"
    )