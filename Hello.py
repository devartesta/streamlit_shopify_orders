import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go
from datetime import date, timedelta
from calendar import monthrange

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
        date_trunc = "day" if vista == "Diaria" else "week" if vista == "Semanal" else "month"
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

# Panel abatible para los filtros
with st.sidebar:
    st.header("🔍 Filtros")
    
    default_start = date.today() - timedelta(days=30)
    start_date = st.date_input("📅 Desde", default_start, key="start_date")
    
    default_end = date.today()
    end_date = st.date_input("📅 Hasta", default_end, key="end_date")
    
    country = st.selectbox("🌍 País", get_country_list(), key="country")
    
    vista = st.radio("📊 Vista", ["Diaria", "Semanal", "Mensual"], horizontal=True, key="vista")

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

    # Calcular promedio de pedidos diario
    def calculate_daily_average(row, vista):
            if vista == "Diaria":
                # Para vista diaria, el promedio es el mismo número de pedidos (1 día)
                return row["pedidos"]
            elif vista == "Semanal":
                # Para vista semanal, dividimos entre 7 días
                # Nota: Esto asume que cada semana tiene 7 días, lo cual puede no ser exacto si la semana está incompleta
                return row["pedidos"] / 7
            else:
                # Para vista mensual, dividimos entre el número de días del mes
                # Convertimos el Timestamp a datetime para evitar problemas
                fecha = pd.Timestamp(row["fecha"]).to_pydatetime()
                year = fecha.year
                month = fecha.month
                days_in_month = monthrange(year, month)[1]
                return row["pedidos"] / days_in_month

    df["promedio_pedidos_diario"] = df.apply(lambda row: calculate_daily_average(row, vista), axis=1)
    st.dataframe(df)

    # KPIs antes de la tabla
    st.markdown("### 📊 Resumen Estadístico")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown("**Total Pedidos**")
    st.markdown(f"<h2 style='color: #1f77b4;'>{int(df['pedidos'].sum()):,}</h2>", unsafe_allow_html=True)

with col2:
    st.markdown("**Total Ventas**")
    st.markdown(f"<h2 style='color: #ff7f0e;'>€{df['ventas'].sum():,.2f}</h2>", unsafe_allow_html=True)

with col3:
    st.markdown("**Promedio Diario de Pedidos**")
    st.markdown(f"<h2 style='color: #2ca02c;'>{promedio_diario_pedidos:,.1f}</h2>", unsafe_allow_html=True)

with col4:
    st.markdown("**Promedio Diario de Ventas**")
    st.markdown(f"<h2 style='color: #d62728;'>€{promedio_diario_ventas:,.2f}</h2>", unsafe_allow_html=True)
    # Minigráfico para promedio diario de ventas
    df["promedio_ventas_diario"] = df.apply(lambda row: row["ventas"] / 1 if vista == "Diaria" else row["ventas"] / 7 if vista == "Semanal" else row["ventas"] / monthrange(pd.Timestamp(row["fecha"]).year, pd.Timestamp(row["fecha"]).month)[1], axis=1)

#    # Formatear datos para la tabla
#    df_display = df.copy()
#    df_display["fecha"] = df_display["fecha"].apply(lambda x: x.strftime("%Y-%m-%d"))
#    df_display["pedidos"] = df_display["pedidos"].astype(int)
#    df_display["ventas"] = df_display["ventas"].apply(lambda x: f"€{x:,.2f}")
#    df_display["promedio_pedidos_diario"] = df_display["promedio_pedidos_diario"].apply(lambda x: f"{x:,.2f}")
#
#    # Renombrar columnas para la tabla
#    df_display = df_display.rename(columns={
#        "fecha": "Fecha",
#        "shipping_country": "País",
#        "pedidos": "Pedidos",
#        "ventas": "Ventas",
#        "promedio_pedidos_diario": "Promedio Pedidos Diario"
#    })
#
#    # Estilo personalizado para la tabla (inspirado en la captura)
#    def style_dataframe(df):
#        return df.style.set_table_styles([
#            # Estilo para el encabezado
#            {
#                "selector": "th",
#                "props": [
#                    ("background-color", "#1a2526"),  # Fondo oscuro como en la captura
#                    ("color", "white"),
#                    ("font-weight", "bold"),
#                    ("text-align", "center"),
#                    ("border", "1px solid #34495e"),
#                    ("padding", "12px"),
#                    ("font-family", "Arial, sans-serif"),
#                    ("font-size", "14px"),
#                    ("text-transform", "uppercase")
#                ]
#            },
#            # Estilo para las filas
#            {
#                "selector": "td",
#                "props": [
#                    ("text-align", "center"),
#                    ("border", "1px solid #34495e"),
#                    ("padding", "10px"),
#                    ("font-family", "Arial, sans-serif"),
#                    ("font-size", "14px"),
#                    ("color", "white"),
#                    ("background-color", "#2a3b3c")  # Fondo oscuro para las celdas
#                ]
#            },
#            # Estilo para filas al pasar el mouse
#            {
#                "selector": "tr:hover",
#                "props": [
#                    ("background-color", "#3e5c5e"),  # Resaltado al pasar el mouse
#                    ("transition", "background-color 0.3s ease")
#                ]
#            },
#            # Estilo para la tabla completa
#            {
#                "selector": "",
#                "props": [
#                    ("border-collapse", "collapse"),
#                    ("width", "100%"),  # Ocupar todo el ancho
#                    ("background-color", "#2a3b3c")
#                ]
#            }
#        ]).set_caption(f"Datos de pedidos y ventas - {country} ({vista})").set_properties(**{
#            "border": "1px solid #34495e"
#        }).hide(axis="index")  # Ocultar el índice
#
#    # Mostrar tabla
#    st.markdown("### 📋 Tabla de Datos")
#    st.write(style_dataframe(df_display), unsafe_allow_html=True)
#
#    # Gráficos debajo de la tabla
#    st.markdown("### 📈 Análisis Visual")
#
#    # Gráfico 1: Evolución de pedidos
#    st.markdown("#### Evolución de Pedidos")
#    fig1 = go.Figure()
#    fig1.add_trace(go.Scatter(
#        x=df["fecha"],
#        y=df["pedidos"],
#        mode="lines+markers",
#        name="Pedidos",
#        line=dict(color="#1f77b4"),
#        marker=dict(size=8)
#    ))
#    fig1.update_layout(
#        xaxis=dict(
#            title="Fecha",
#            type="date",
#            tickformat="%Y-%m-%d" if vista == "Diaria" else "%Y-%m-%d" if vista == "Semanal" else "%Y-%m"
#        ),
#        yaxis=dict(title="Pedidos"),
#        template="plotly_dark",
#        margin=dict(l=50, r=50, t=30, b=30)
#    )
#    st.plotly_chart(fig1, use_container_width=True)
#
#    # Gráfico 2: Evolución de ventas
#    st.markdown("#### Evolución de Ventas")
#    fig2 = go.Figure()
#    fig2.add_trace(go.Scatter(
#        x=df["fecha"],
#        y=df["ventas"],
#        mode="lines+markers",
#        name="Ventas (€)",
#        line=dict(color="#ff7f0e"),
#        marker=dict(size=8)
#    ))
#    fig2.update_layout(
#        xaxis=dict(
#            title="Fecha",
#            type="date",
#            tickformat="%Y-%m-%d" if vista == "Diaria" else "%Y-%m-%d" if vista == "Semanal" else "%Y-%m"
#        ),
#        yaxis=dict(title="Ventas (€)"),
#        template="plotly_dark",
#        margin=dict(l=50, r=50, t=30, b=30)
#    )
#    st.plotly_chart(fig2, use_container_width=True)
#
#    # Gráfico 3: Evolución del promedio de pedidos diario
#    st.markdown("#### Evolución del Promedio de Pedidos Diario")
#    fig3 = go.Figure()
#    fig3.add_trace(go.Scatter(
#        x=df["fecha"],
#        y=df["promedio_pedidos_diario"],
#        mode="lines+markers",
#        name="Promedio Pedidos Diario",
#        line=dict(color="#2ca02c"),
#        marker=dict(size=8)
#    ))
#    fig3.update_layout(
#        xaxis=dict(
#            title="Fecha",
#            type="date",
#            tickformat="%Y-%m-%d" if vista == "Diaria" else "%Y-%m-%d" if vista == "Semanal" else "%Y-%m"
#        ),
#        yaxis=dict(title="Promedio Pedidos Diario"),
#        template="plotly_dark",
#        margin=dict(l=50, r=50, t=30, b=30)
#    )
#    st.plotly_chart(fig3, use_container_width=True)
#
#    # Opción para descargar los datos
#    st.markdown("### 💾 Descargar Datos")
#    csv = df_display.to_csv(index=False).encode('utf-8')
#    st.download_button(
#        label="Descargar como CSV",
#        data=csv,
#        file_name=f"pedidos_ventas_{country}_{vista.lower()}_{start_date}_a_{end_date}.csv",
#        mime="text/csv",
#        help="Descarga los datos en formato CSV"
#    )