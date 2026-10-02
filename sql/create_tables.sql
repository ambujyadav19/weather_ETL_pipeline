-- ====================================================================
-- Table: weather_metrics
-- Description: Stores hourly meteorological metrics for monitored cities
-- Composite Primary Key: (city_name, recorded_at) ensures idempotency
-- ====================================================================

CREATE TABLE IF NOT EXISTS weather_metrics (
    city_name VARCHAR(100) NOT NULL,
    country VARCHAR(100) NOT NULL,
    latitude NUMERIC(6, 4) NOT NULL,
    longitude NUMERIC(7, 4) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    temperature_celsius NUMERIC(5, 2),
    humidity_pct NUMERIC(5, 2),
    precipitation_mm NUMERIC(6, 2),
    wind_speed_kmh NUMERIC(6, 2),
    weather_code INT,
    weather_condition VARCHAR(100),
    extracted_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_weather_metrics PRIMARY KEY (city_name, recorded_at)
);

-- Indexes for high-performance analytical queries
CREATE INDEX IF NOT EXISTS idx_weather_metrics_city_name 
    ON weather_metrics (city_name);

CREATE INDEX IF NOT EXISTS idx_weather_metrics_recorded_at 
    ON weather_metrics (recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_weather_metrics_city_recorded 
    ON weather_metrics (city_name, recorded_at DESC);
