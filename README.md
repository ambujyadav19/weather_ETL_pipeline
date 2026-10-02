# 🌤️ Global Weather Telemetry ETL Pipeline & Analytics Dashboard

[![Daily Weather ETL Pipeline](https://github.com/ambujyadav19/weather-ETL-pipeline/actions/workflows/daily_etl.yml/badge.svg)](https://github.com/ambujyadav19/weather-ETL-pipeline/actions/workflows/daily_etl.yml)
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://weatheretlpipelinebyambuj.streamlit.app/)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-FF4B4B?logo=streamlit&logoColor=white)

An end-to-end, automated Data Engineering pipeline and real-time analytics web dashboard. Ingests 7-day meteorological forecasts from the open [Open-Meteo REST API](https://open-meteo.com/), transforms and standardizes telemetry using **Pandas**, enforces data quality via **Pydantic**, performs **idempotent upserts** into **PostgreSQL**, and visualizes actionable metrics with **Streamlit** & **Plotly**.

Automated to execute daily via **GitHub Actions** and stored in serverless cloud PostgreSQL (**Neon.tech**).

---

## 🌐 Live Interactive Web Dashboard

👉 **[Click Here to Open the Live Dashboard](https://weatheretlpipelinebyambuj.streamlit.app/)**  
*(Explore temperature trends, rain volume forecasts, wind speeds, and download exported CSV datasets directly in your browser).*

---

## 🏛️ End-to-End Architecture

```text
┌─────────────────────────────────┐
│       Open-Meteo REST API       │  (Public Meteorological Telemetry)
└────────────────┬────────────────┘
                 │ HTTP GET (with exponential backoff & retry)
                 ▼
┌─────────────────────────────────┐
│     Extraction (extract.py)     │  168-hr forecast per city, timeouts & error handling
└────────────────┬────────────────┘
                 │ Raw JSON Payloads
                 ▼
┌─────────────────────────────────┐
│   Transformation (transform.py) │  Flattens nested JSON, converts to UTC, standardizes
└────────────────┬────────────────┘  column units, maps WMO weather conditions
                 │ Clean Pandas DataFrame
                 ▼
┌─────────────────────────────────┐
│     Validation (validate.py)    │  Quality Gate: non-null PKs, physical bounds, Pydantic
└────────────────┬────────────────┘
                 │ Verified Records (100% Quality)
                 ▼
┌─────────────────────────────────┐
│      Loading (load.py)          │  Idempotent Upsert (ON CONFLICT DO UPDATE)
└───────────────┬─────────────────┘
                │
        ┌───────┴────────────────────────┐
        ▼                                ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│   Local PostgreSQL       │    │   Cloud PostgreSQL       │
│   (Docker Compose)       │    │   (Neon Serverless DB)   │
└───────────────┬──────────┘    └───────────────┬──────────┘
                │                               │
                ▼                               ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│   pgAdmin 4 (Port 8080)  │    │   Streamlit Web App      │
│   Local Web Database GUI │    │   (Live Cloud Dashboard) │
└──────────────────────────┘    └──────────────────────────┘
```

---

## 📁 Repository Structure

```text
weather_etl_pipeline/
├── .github/
│   └── workflows/
│       └── daily_etl.yml     # Cloud Cron: automated daily pipeline run at 06:00 UTC
├── config/
│   ├── config.py             # Database settings, API endpoints, monitored cities
│   └── logging_config.py     # Centralized logging (console + logs/pipeline.log)
├── src/
│   ├── extract.py            # API ingestion with urllib3 Retry & timeouts
│   ├── transform.py          # Pandas normalization & WMO weather mapping
│   ├── validate.py           # Vectorized range checks & Pydantic schema validation
│   └── load.py               # SQLAlchemy PostgreSQL loader with upsert logic
├── sql/
│   └── create_tables.sql     # DDL table schema, composite primary keys, and indexes
├── logs/
│   └── pipeline.log          # Persistent audit logs
├── docker-compose.yml        # PostgreSQL 16 + pgAdmin container services
├── requirements.txt          # Python dependencies
├── main.py                   # Master pipeline orchestrator & CLI
├── app.py                    # Streamlit interactive analytics dashboard
└── .env                      # Local environment secrets & DB credentials
```

---

## 🚀 Quickstart Guide

### 1. Start Local Database (Docker)
Ensure Docker Desktop is running:
```powershell
docker compose up -d
```
* **PostgreSQL 16**: `localhost:5432`
* **pgAdmin 4 GUI**: `http://localhost:8080` (Login: `admin@example.com` / `admin`)

### 2. Activate Virtual Environment & Install Dependencies
```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Run the Full ETL Pipeline
```powershell
python main.py
```

### 4. Launch the Local Analytics Dashboard
```powershell
streamlit run app.py
```
View the dashboard locally at **`http://localhost:8501`**.

---

## ⚙️ Key Engineering Features

* **Idempotent Upsert**: Built with `ON CONFLICT (city_name, recorded_at) DO UPDATE`. Multiple pipeline executions safely update existing forecast hours without duplicate rows or primary key violations.
* **Network Fault Tolerance**: Extraction uses an `HTTPAdapter` with exponential backoff (retrying 429, 500, 502, 503, 504 errors) and strict timeouts to prevent process hangs.
* **Multi-Stage Validation**: Protects downstream systems using Pandas boundary masks (temperature between -90°C and 60°C, non-negative wind/rain) and Pydantic schema contracts.
* **Cloud Automation**: Zero-cost daily execution via **GitHub Actions** writing to a serverless **Neon PostgreSQL** database.
* **Auditability**: Every run logs start time, completion time, elapsed seconds, row counts, and tracebacks to `logs/pipeline.log`.

---

## 🔍 Analytical SQL Queries & Business Use Cases

Connect to PostgreSQL (via pgAdmin or SQL Editor) and test these real-world queries:

### 1. Logistics Alert: High-Risk Delivery Windows
*Identifies hours with severe precipitation or high winds that disrupt supply chain operations:*
```sql
SELECT 
    city_name,
    recorded_at,
    precipitation_mm,
    wind_speed_kmh,
    weather_condition,
    CASE 
        WHEN wind_speed_kmh >= 35 OR precipitation_mm >= 3.0 THEN 'HIGH DISRUPTION RISK'
        WHEN wind_speed_kmh >= 25 OR precipitation_mm >= 1.0 THEN 'MODERATE DELAY EXPECTED'
        ELSE 'NORMAL OPERATIONS'
    END AS operational_status
FROM weather_metrics
WHERE wind_speed_kmh >= 25 OR precipitation_mm >= 1.0
ORDER BY recorded_at ASC;
```

### 2. Renewable Energy: Solar & Wind Generation Potential
*Calculates optimal wind turbine generation hours (12–50 km/h) and prime solar hours per city:*
```sql
SELECT 
    city_name,
    COUNT(*) FILTER (WHERE weather_condition = 'Clear sky') AS prime_solar_hours,
    COUNT(*) FILTER (WHERE weather_condition LIKE '%Overcast%') AS low_solar_hours,
    COUNT(*) FILTER (WHERE wind_speed_kmh BETWEEN 12.0 AND 50.0) AS optimal_wind_hours,
    ROUND(AVG(wind_speed_kmh), 1) AS avg_wind_speed_kmh
FROM weather_metrics
GROUP BY city_name
ORDER BY optimal_wind_hours DESC;
```

### 3. Smart HVAC & Grid Strain: 7-Day Diurnal Swing
*Measures day/night temperature swings to forecast peak building heating/cooling energy demand:*
```sql
SELECT 
    city_name,
    DATE(recorded_at) AS forecast_date,
    MIN(temperature_celsius) AS night_low,
    MAX(temperature_celsius) AS day_high,
    ROUND(MAX(temperature_celsius) - MIN(temperature_celsius), 1) AS diurnal_temp_swing
FROM weather_metrics
GROUP BY city_name, DATE(recorded_at)
ORDER BY city_name, forecast_date;
```
