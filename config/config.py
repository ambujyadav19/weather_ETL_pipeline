import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# --- Database Configurations ---
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "weather_db")

# SQLAlchemy connection string (supports full URL or individual components)
_raw_db_url = os.getenv("DATABASE_URL")
if _raw_db_url:
    if _raw_db_url.startswith("postgresql://"):
        DATABASE_URL = _raw_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    else:
        DATABASE_URL = _raw_db_url
else:
    DB_SSLMODE = os.getenv("DB_SSLMODE", "")
    ssl_param = f"?sslmode={DB_SSLMODE}" if DB_SSLMODE else ""
    DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}{ssl_param}"

# --- Logging Configuration ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- Open-Meteo API Configuration ---
OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"

# Hourly weather variables to extract
HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "weather_code",
]

# Monitored cities with geographic coordinates
DEFAULT_CITIES = [
    {"city_name": "London", "country": "United Kingdom", "latitude": 51.5074, "longitude": -0.1278},
    {"city_name": "New York", "country": "United States", "latitude": 40.7128, "longitude": -74.0060},
    {"city_name": "Tokyo", "country": "Japan", "latitude": 35.6762, "longitude": 139.6503},
    {"city_name": "Mumbai", "country": "India", "latitude": 19.0760, "longitude": 72.8777},
    {"city_name": "Berlin", "country": "Germany", "latitude": 52.5200, "longitude": 13.4050},
    {"city_name": "Sydney", "country": "Australia", "latitude": -33.8688, "longitude": 151.2093},
]
