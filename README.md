# 🌤️ Weather ETL Pipeline

An end-to-end, production-grade Data Engineering ETL (Extract, Transform, Load) pipeline built with **Python**, **Pandas**, and **PostgreSQL**, containerized using **Docker Compose**.

Ingests real-time meteorological forecasts from the open [Open-Meteo REST API](https://open-meteo.com/), standardizes and cleans the data, runs multi-stage data quality checks, and performs **idempotent upserts** into PostgreSQL.

---

## 🏛️ Architecture Overview

```text
┌───────────────────────┐
│   Open-Meteo API      │  (Public Meteorological REST API)
└───────────┬───────────┘
            │ HTTP GET (with exponential backoff & retry)
            ▼
┌───────────────────────┐
│   src/extract.py      │  Ingests 168-hr forecasts for global cities
└───────────┬───────────┘
            │ Raw JSON Payloads
            ▼
┌───────────────────────┐
│   src/transform.py    │  Flattens JSON, standardizes units, UTC timestamps,
└───────────┬───────────┘  maps WMO weather conditions, deduplicates
            │ Clean Pandas DataFrame
            ▼
┌───────────────────────┐
│   src/validate.py     │  Data Quality Gate (Null checks, domain bounds, Pydantic)
└───────────┬───────────┘
            │ Verified Records
            ▼
┌───────────────────────┐
│   src/load.py         │  Idempotent Upsert (ON CONFLICT DO UPDATE)
└───────────┬───────────┘
            │ Batch Inserts via SQLAlchemy connection pool
            ▼
┌───────────────────────┐
│   PostgreSQL (Docker) │  Tables with B-Tree indexes for fast analytical queries
└───────────────────────┘
```

---

## 📁 Repository Structure

```text
weather_etl_pipeline/
├── config/
│   ├── config.py             # Database credentials, API endpoints, monitored cities
│   └── logging_config.py     # Centralized logging (console + logs/pipeline.log)
├── src/
│   ├── extract.py            # API ingestion with urllib3 Retry & timeouts
│   ├── transform.py          # Pandas normalization & WMO weather mapping
│   ├── validate.py           # Vectorized range checks & Pydantic schema validation
│   └── load.py               # SQLAlchemy PostgreSQL loader with upsert logic
├── sql/
│   └── create_tables.sql     # DDL table schema, composite primary keys, and indexes
├── logs/
│   └── pipeline.log          # Persistent timestamped audit logs
├── docker-compose.yml        # PostgreSQL 16 + pgAdmin container services
├── requirements.txt          # Python dependencies
├── main.py                   # Master pipeline orchestrator & CLI
└── .env                      # Environment variables & DB connection secrets
```

---

## 🚀 Quickstart Guide

### 1. Start Database Services (Docker)
Ensure Docker Desktop is running, then execute:
```powershell
docker compose up -d
```
This automatically starts:
* **PostgreSQL 16** on `localhost:5432`
* **pgAdmin 4 (GUI)** on `http://localhost:8080` (Login: `admin@example.com` / `admin`)

### 2. Activate Python Virtual Environment
```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Run the Full ETL Pipeline
```powershell
python main.py
```

---

## 🔍 Sample Analytical SQL Queries

Once the pipeline runs, connect to your PostgreSQL instance and try these queries:

### 1. Current Weather Across Monitored Cities
```sql
SELECT 
    city_name,
    country,
    recorded_at,
    temperature_celsius,
    humidity_pct,
    weather_condition
FROM weather_metrics
WHERE recorded_at = (SELECT MIN(recorded_at) FROM weather_metrics)
ORDER BY temperature_celsius DESC;
```

### 2. 7-Day Average & Extremes by City
```sql
SELECT 
    city_name,
    ROUND(AVG(temperature_celsius), 2) AS avg_temp_c,
    MIN(temperature_celsius) AS min_temp_c,
    MAX(temperature_celsius) AS max_temp_c,
    ROUND(SUM(precipitation_mm), 2) AS total_rain_mm,
    ROUND(MAX(wind_speed_kmh), 2) AS max_wind_kmh
FROM weather_metrics
GROUP BY city_name
ORDER BY avg_temp_c DESC;
```

### 3. Rainiest Periods
```sql
SELECT 
    city_name,
    recorded_at,
    precipitation_mm,
    weather_condition
FROM weather_metrics
WHERE precipitation_mm > 0
ORDER BY precipitation_mm DESC
LIMIT 10;
```

---

## ⚙️ Key Engineering Features

1. **Idempotency**: Running `python main.py` multiple times updates existing records without creating duplicates or throwing primary key constraint violations.
2. **Resilience**: The extraction layer uses exponential backoff retries (`HTTPAdapter`) to handle intermittent rate limits (HTTP 429) or network hiccups.
3. **Quality Gates**: Invalid physical measurements (e.g. temperatures $>60^\circ\text{C}$, negative humidity, or null primary keys) are trapped before database ingestion.
4. **Audit Trail**: Every execution is logged with start time, completion time, elapsed seconds, row counts, and error tracebacks in `logs/pipeline.log`.

---

## ☁️ Cloud Deployment (Automated Daily Runs)

This pipeline includes a pre-configured **GitHub Actions Workflow** (`.github/workflows/daily_etl.yml`) that automatically executes every day at **06:00 UTC** and writes to a free cloud PostgreSQL instance (e.g., [Neon.tech](https://neon.tech) or [Supabase](https://supabase.com)).

### Deployment Steps:
1. **Create Free Cloud Database**: Sign up at [Neon.tech](https://neon.tech) and copy your PostgreSQL connection string.
2. **Push to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "feat: initial weather ETL pipeline"
   git branch -M main
   git remote add origin https://github.com/<YOUR_USER>/weather-etl-pipeline.git
   git push -u origin main
   ```
3. **Configure GitHub Secrets**:
   * Navigate to `Repository Settings` -> `Secrets and variables` -> `Actions`.
   * Add a repository secret named `DATABASE_URL` with your cloud PostgreSQL connection string.
4. **Trigger Manually or Wait for Cron**: Go to the **Actions** tab on GitHub, select **Daily Weather ETL Pipeline**, and click **Run workflow**!
