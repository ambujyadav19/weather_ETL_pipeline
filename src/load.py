from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
from sqlalchemy import MetaData, Table, create_engine, func, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from config.config import DATABASE_URL
from config.logging_config import setup_logger

logger = setup_logger("weather_etl.load")

# Global SQLAlchemy engine (connection pool)
_engine = None


def get_db_engine():
    """
    Returns a singleton SQLAlchemy engine with connection pooling.
    """
    global _engine
    if _engine is None:
        logger.info("Initializing SQLAlchemy database engine...")
        _engine = create_engine(
            DATABASE_URL,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Automatically detect disconnected connections
        )
    return _engine


def check_db_connection() -> bool:
    """
    Tests if PostgreSQL database is reachable.
    """
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection test successful.")
        return True
    except SQLAlchemyError as err:
        logger.error(f"Database connection failed: {err}")
        return False


def init_db_schema() -> bool:
    """
    Executes sql/create_tables.sql to ensure the database schema and indexes exist.
    """
    sql_path = Path(__file__).resolve().parent.parent / "sql" / "create_tables.sql"
    if not sql_path.exists():
        logger.error(f"DDL script not found at {sql_path}")
        return False

    try:
        engine = get_db_engine()
        with open(sql_path, "r", encoding="utf-8") as f:
            ddl_sql = f.read()

        with engine.begin() as conn:
            # Execute DDL statements
            for statement in ddl_sql.split(";"):
                clean_stmt = statement.strip()
                if clean_stmt:
                    conn.execute(text(clean_stmt))

        logger.info("Database schema initialized successfully.")
        return True
    except SQLAlchemyError as err:
        logger.error(f"Error initializing database schema: {err}")
        return False


def load_weather_data(df: pd.DataFrame, batch_size: int = 500) -> int:
    """
    Loads validated weather DataFrame into PostgreSQL using idempotent Upsert
    (ON CONFLICT (city_name, recorded_at) DO UPDATE).

    Args:
        df: Validated Pandas DataFrame.
        batch_size: Number of records to insert per batch.

    Returns:
        Number of records loaded/upserted.
    """
    if df is None or df.empty:
        logger.warning("No data provided to load.")
        return 0

    engine = get_db_engine()
    metadata = MetaData()
    metadata.reflect(bind=engine, only=["weather_metrics"])
    weather_table = metadata.tables.get("weather_metrics")

    if weather_table is None:
        logger.info("Table 'weather_metrics' not found. Creating from schema...")
        init_db_schema()
        metadata.clear()
        metadata.reflect(bind=engine, only=["weather_metrics"])
        weather_table = metadata.tables.get("weather_metrics")

    # Convert DataFrame records to list of dicts with Python native types
    records: List[Dict] = df.to_dict(orient="records")
    total_records = len(records)
    logger.info(f"Loading {total_records} records into 'weather_metrics' table (Upsert mode)...")

    loaded_count = 0

    try:
        with engine.begin() as conn:
            for i in range(0, total_records, batch_size):
                batch = records[i : i + batch_size]

                # PostgreSQL Upsert statement
                stmt = insert(weather_table).values(batch)
                upsert_stmt = stmt.on_conflict_do_update(
                    index_elements=["city_name", "recorded_at"],
                    set_={
                        "country": stmt.excluded.country,
                        "latitude": stmt.excluded.latitude,
                        "longitude": stmt.excluded.longitude,
                        "temperature_celsius": stmt.excluded.temperature_celsius,
                        "humidity_pct": stmt.excluded.humidity_pct,
                        "precipitation_mm": stmt.excluded.precipitation_mm,
                        "wind_speed_kmh": stmt.excluded.wind_speed_kmh,
                        "weather_code": stmt.excluded.weather_code,
                        "weather_condition": stmt.excluded.weather_condition,
                        "extracted_at": stmt.excluded.extracted_at,
                        "updated_at": func.now(),
                    },
                )

                conn.execute(upsert_stmt)
                loaded_count += len(batch)
                logger.info(f"Upserted batch {loaded_count}/{total_records} records.")

        logger.info(f"Successfully finished loading {loaded_count} records into PostgreSQL.")
        return loaded_count

    except SQLAlchemyError as err:
        logger.error(f"Failed to load data into database: {err}", exc_info=True)
        raise


if __name__ == "__main__":
    from src.extract import extract_all_weather
    from src.transform import transform_all_weather
    from src.validate import validate_weather_dataframe

    print("Step 1: Extracting...")
    raw = extract_all_weather()

    print("\nStep 2: Transforming...")
    df_clean = transform_all_weather(raw)

    print("\nStep 3: Validating...")
    df_valid, _ = validate_weather_dataframe(df_clean)

    print("\nStep 4: Loading into PostgreSQL...")
    init_db_schema()
    loaded = load_weather_data(df_valid)

    # Verify rows in PostgreSQL
    engine = get_db_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*), COUNT(DISTINCT city_name) FROM weather_metrics"))
        count, cities = result.fetchone()
        print(f"\n--- PostgreSQL Verification ---")
        print(f"Total rows in 'weather_metrics' table: {count}")
        print(f"Unique cities: {cities}")
