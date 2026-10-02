from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import text
import streamlit as st

from config.config import DATABASE_URL
from src.load import get_db_engine

# --- Page Configuration ---
st.set_page_config(
    page_title="Global Weather Telemetry Dashboard",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom Styling ---
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #6c757d;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 16px;
        border-left: 4px solid #007bff;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=300)
def load_weather_data() -> pd.DataFrame:
    """
    Loads latest weather metrics from PostgreSQL with a 5-minute cache.
    """
    engine = get_db_engine()
    query = """
        SELECT 
            city_name,
            country,
            latitude,
            longitude,
            recorded_at,
            temperature_celsius,
            humidity_pct,
            precipitation_mm,
            wind_speed_kmh,
            weather_code,
            weather_condition,
            extracted_at,
            updated_at
        FROM weather_metrics
        ORDER BY recorded_at ASC;
    """
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(text(query), conn)
            df["recorded_at"] = pd.to_datetime(df["recorded_at"])
            df["extracted_at"] = pd.to_datetime(df["extracted_at"])
            return df
    except Exception as e:
        st.error(f"Failed to connect to database: {e}")
        return pd.DataFrame()


# --- Load Data ---
df = load_weather_data()

# --- Sidebar Controls ---
st.sidebar.title("⚙️ Dashboard Controls")

if df.empty:
    st.warning("⚠️ No data found in PostgreSQL database! Please make sure your pipeline has executed.")
    st.stop()

# Refresh button
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

all_cities = sorted(df["city_name"].unique().tolist())
selected_cities = st.sidebar.multiselect(
    "Select Cities to Display",
    options=all_cities,
    default=all_cities,
)

if not selected_cities:
    st.sidebar.warning("Please select at least one city.")
    st.stop()

filtered_df = df[df["city_name"].isin(selected_cities)].copy()

# Sidebar Metadata
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Database**: Connected")
st.sidebar.markdown(f"**Total Records**: `{len(df):,}` rows")
last_sync = df["extracted_at"].max()
st.sidebar.markdown(f"**Last ETL Sync**: `{last_sync.strftime('%Y-%m-%d %H:%M UTC')}`")

# --- Title Header ---
st.markdown('<div class="main-header">🌤️ Global Weather Analytics Dashboard</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Live meteorological forecasts ingested via Open-Meteo REST API → Pandas Cleaning → PostgreSQL</div>',
    unsafe_allow_html=True,
)

# --- KPI Cards Row ---
col1, col2, col3, col4 = st.columns(4)

# Current snapshot (first available timestamp for each city)
current_df = filtered_df.sort_values("recorded_at").groupby("city_name").first().reset_index()

hottest_row = current_df.loc[current_df["temperature_celsius"].idxmax()]
coldest_row = current_df.loc[current_df["temperature_celsius"].idxmin()]
rainiest_row = filtered_df.groupby("city_name")["precipitation_mm"].sum().idxmax()
total_rain_val = filtered_df.groupby("city_name")["precipitation_mm"].sum().max()

with col1:
    st.metric(
        label="🔥 Hottest City Right Now",
        value=f"{hottest_row['temperature_celsius']} °C",
        delta=f"{hottest_row['city_name']} ({hottest_row['weather_condition']})",
        delta_color="off",
    )

with col2:
    st.metric(
        label="❄️ Coldest City Right Now",
        value=f"{coldest_row['temperature_celsius']} °C",
        delta=f"{coldest_row['city_name']} ({coldest_row['weather_condition']})",
        delta_color="off",
    )

with col3:
    st.metric(
        label="🌧️ Highest 7-Day Rainfall",
        value=f"{total_rain_val:.1f} mm",
        delta=f"{rainiest_row}",
        delta_color="off",
    )

with col4:
    avg_wind = filtered_df["wind_speed_kmh"].mean()
    st.metric(
        label="💨 Average Wind Speed",
        value=f"{avg_wind:.1f} km/h",
        delta=f"{len(selected_cities)} cities monitored",
        delta_color="off",
    )

st.markdown("---")

# --- Tabbed Visualizations ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Temperature Forecast",
    "🌧️ Rainfall & Precipitation",
    "💨 Wind & Conditions",
    "📋 Raw Data Explorer",
])

# Tab 1: Temperature Trends
with tab1:
    st.subheader("7-Day Hourly Temperature Trend (°C)")
    fig_temp = px.line(
        filtered_df,
        x="recorded_at",
        y="temperature_celsius",
        color="city_name",
        labels={"recorded_at": "Forecast Time (UTC)", "temperature_celsius": "Temperature (°C)", "city_name": "City"},
        template="plotly_white",
    )
    fig_temp.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig_temp, use_container_width=True)

# Tab 2: Rainfall
with tab2:
    st.subheader("Hourly Precipitation Forecast (mm)")
    fig_rain = px.bar(
        filtered_df,
        x="recorded_at",
        y="precipitation_mm",
        color="city_name",
        barmode="group",
        labels={"recorded_at": "Forecast Time (UTC)", "precipitation_mm": "Precipitation (mm)", "city_name": "City"},
        template="plotly_white",
    )
    fig_rain.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig_rain, use_container_width=True)

# Tab 3: Wind & Atmospheric Conditions
with tab3:
    col_w1, col_w2 = st.columns(2)
    with col_w1:
        st.subheader("Average Wind Speed by City (km/h)")
        wind_summary = filtered_df.groupby("city_name")["wind_speed_kmh"].agg(["mean", "max"]).reset_index()
        fig_wind = px.bar(
            wind_summary,
            x="city_name",
            y=["mean", "max"],
            barmode="group",
            labels={"value": "Wind Speed (km/h)", "city_name": "City", "variable": "Metric"},
            template="plotly_white",
            color_discrete_map={"mean": "#0d6efd", "max": "#dc3545"},
        )
        st.plotly_chart(fig_wind, use_container_width=True)

    with col_w2:
        st.subheader("Weather Conditions Distribution")
        cond_counts = filtered_df["weather_condition"].value_counts().reset_index()
        cond_counts.columns = ["Weather Condition", "Hours Count"]
        fig_pie = px.pie(
            cond_counts,
            names="Weather Condition",
            values="Hours Count",
            hole=0.4,
            template="plotly_white",
        )
        st.plotly_chart(fig_pie, use_container_width=True)

# Tab 4: Raw Data Explorer
with tab4:
    st.subheader("Filterable Data View")
    st.dataframe(
        filtered_df[[
            "city_name", "country", "recorded_at", "temperature_celsius", 
            "humidity_pct", "precipitation_mm", "wind_speed_kmh", "weather_condition"
        ]],
        use_container_width=True,
        hide_index=True,
    )
    
    # Download CSV
    csv_data = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Data as CSV",
        data=csv_data,
        file_name="weather_metrics_export.csv",
        mime="text/csv",
    )
