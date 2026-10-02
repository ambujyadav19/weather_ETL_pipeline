import argparse
import sys
import time
from datetime import datetime, timezone

from config.logging_config import setup_logger
from src.extract import extract_all_weather
from src.load import check_db_connection, init_db_schema, load_weather_data
from src.transform import transform_all_weather
from src.validate import validate_weather_dataframe

logger = setup_logger("weather_etl.main")


def run_pipeline(batch_size: int = 500) -> bool:
    """
    Orchestrates the end-to-end Weather ETL Pipeline:
      1. Pre-flight DB health check & schema initialization
      2. Extract hourly weather data from Open-Meteo REST API
      3. Transform, clean, and enrich data using Pandas
      4. Validate data against schema and physical domain rules
      5. Load/Upsert verified records into PostgreSQL
    """
    pipeline_start = time.time()
    start_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    logger.info("=" * 60)
    logger.info(f"[START] WEATHER ETL PIPELINE RUN STARTED at {start_utc}")
    logger.info("=" * 60)

    try:
        # Step 0: Pre-flight Database Verification
        logger.info(">>> Stage 0: Checking PostgreSQL Database Connectivity...")
        if not check_db_connection():
            logger.error("Database pre-flight check failed! Aborting pipeline run.")
            return False

        logger.info(">>> Stage 0b: Ensuring Database Schema and Indexes Exist...")
        if not init_db_schema():
            logger.error("Failed to verify/initialize database schema! Aborting.")
            return False

        # Step 1: Extraction
        logger.info(">>> Stage 1: Ingesting Data from Open-Meteo API...")
        raw_city_data = extract_all_weather()
        if not raw_city_data:
            logger.error("Extraction returned 0 records. Pipeline aborted.")
            return False
        total_cities = len(raw_city_data)

        # Step 2: Transformation
        logger.info(">>> Stage 2: Transforming & Cleaning Data with Pandas...")
        df_transformed = transform_all_weather(raw_city_data)
        if df_transformed.empty:
            logger.error("Transformation resulted in empty DataFrame. Aborting.")
            return False
        total_transformed_rows = len(df_transformed)

        # Step 3: Validation
        logger.info(">>> Stage 3: Running Data Quality & Validation Gates...")
        df_valid, df_invalid = validate_weather_dataframe(df_transformed, strict_raise=False)
        valid_rows = len(df_valid)
        invalid_rows = len(df_invalid)

        if valid_rows == 0:
            logger.error("All records failed validation checks! Aborting load stage.")
            return False

        # Step 4: Loading
        logger.info(">>> Stage 4: Loading Verified Data into PostgreSQL...")
        loaded_rows = load_weather_data(df_valid, batch_size=batch_size)

        # Summary & Metrics
        duration = round(time.time() - pipeline_start, 2)
        end_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        logger.info("=" * 60)
        logger.info("[SUCCESS] PIPELINE EXECUTION COMPLETED SUCCESSFULLY!")
        logger.info("=" * 60)
        logger.info(f"Start Time       : {start_utc}")
        logger.info(f"Completion Time  : {end_utc}")
        logger.info(f"Elapsed Time     : {duration} seconds")
        logger.info(f"Cities Processed : {total_cities}")
        logger.info(f"Rows Transformed : {total_transformed_rows}")
        logger.info(f"Rows Validated   : {valid_rows} passed ({invalid_rows} quarantined)")
        logger.info(f"Rows Loaded      : {loaded_rows} records upserted")
        logger.info("=" * 60)

        return True

    except Exception as err:
        duration = round(time.time() - pipeline_start, 2)
        logger.critical(f"Pipeline crashed with an unhandled exception: {err}", exc_info=True)
        logger.info(f"Pipeline failed after {duration} seconds.")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Production Weather ETL Pipeline (Open-Meteo -> Pandas -> PostgreSQL)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch size for database loading (default: 500)",
    )
    args = parser.parse_args()

    success = run_pipeline(batch_size=args.batch_size)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
