from datetime import datetime
from typing import List, Tuple
import pandas as pd
from pydantic import BaseModel, Field, ValidationError

from config.logging_config import setup_logger

logger = setup_logger("weather_etl.validate")


class WeatherRecordModel(BaseModel):
    """
    Pydantic schema definition representing a single validated weather metric record.
    Used for strict schema enforcement and type checking.
    """
    city_name: str = Field(..., min_length=1)
    country: str = Field(..., min_length=1)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    recorded_at: datetime
    temperature_celsius: float = Field(..., ge=-90.0, le=60.0)
    humidity_pct: float = Field(..., ge=0.0, le=100.0)
    precipitation_mm: float = Field(..., ge=0.0)
    wind_speed_kmh: float = Field(..., ge=0.0)
    weather_code: int
    weather_condition: str
    extracted_at: datetime


class DataValidationError(Exception):
    """Custom exception raised when pipeline data validation fails completely."""
    pass


def validate_weather_dataframe(
    df: pd.DataFrame,
    strict_raise: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Validates the transformed weather DataFrame against business and physical rules:
      1. Non-empty DataFrame
      2. Required columns present
      3. Non-null primary key fields (city_name, recorded_at)
      4. Physical sanity range limits (temperature, humidity, wind, precipitation)
      5. Primary key uniqueness

    Args:
        df: Input transformed Pandas DataFrame.
        strict_raise: If True and 0 valid rows remain, raises DataValidationError.

    Returns:
        Tuple of (valid_df, invalid_df).
    """
    if df is None or df.empty:
        err_msg = "Validation failed: Input DataFrame is empty or None."
        logger.error(err_msg)
        if strict_raise:
            raise DataValidationError(err_msg)
        return pd.DataFrame(), pd.DataFrame()

    total_rows = len(df)
    logger.info(f"Starting data validation on {total_rows} records...")

    # Required columns check
    required_columns = [
        "city_name",
        "country",
        "latitude",
        "longitude",
        "recorded_at",
        "temperature_celsius",
        "humidity_pct",
        "precipitation_mm",
        "wind_speed_kmh",
        "weather_code",
        "weather_condition",
        "extracted_at",
    ]
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        err_msg = f"Validation failed: Missing required columns: {missing_cols}"
        logger.error(err_msg)
        raise DataValidationError(err_msg)

    # Rule 1: Non-null primary key components
    pk_null_mask = df["city_name"].isna() | df["recorded_at"].isna()

    # Rule 2: Physical boundaries range checks
    temp_valid = df["temperature_celsius"].between(-90.0, 60.0)
    humidity_valid = df["humidity_pct"].between(0.0, 100.0)
    precip_valid = df["precipitation_mm"] >= 0.0
    wind_valid = df["wind_speed_kmh"] >= 0.0
    lat_valid = df["latitude"].between(-90.0, 90.0)
    lon_valid = df["longitude"].between(-180.0, 180.0)

    # Combined validity mask
    is_valid_mask = (
        ~pk_null_mask
        & temp_valid
        & humidity_valid
        & precip_valid
        & wind_valid
        & lat_valid
        & lon_valid
    )

    valid_df = df[is_valid_mask].copy()
    invalid_df = df[~is_valid_mask].copy()

    # Rule 3: Composite uniqueness check on valid data
    duplicate_mask = valid_df.duplicated(subset=["city_name", "recorded_at"], keep="first")
    if duplicate_mask.any():
        dup_count = duplicate_mask.sum()
        logger.warning(f"Found {dup_count} duplicate (city_name, recorded_at) records. Keeping first occurrence.")
        valid_df = valid_df[~duplicate_mask]

    passed_count = len(valid_df)
    failed_count = len(invalid_df)

    logger.info(
        f"Validation summary: {passed_count}/{total_rows} records passed ({failed_count} quarantined/invalid)."
    )

    if failed_count > 0:
        logger.warning(f"Quarantined {failed_count} records due to validation failures.")

    if passed_count == 0 and strict_raise:
        err_msg = "Validation failed: 0 valid records remained after checks."
        logger.error(err_msg)
        raise DataValidationError(err_msg)

    return valid_df, invalid_df


def sample_pydantic_check(df: pd.DataFrame, sample_size: int = 5) -> bool:
    """
    Performs a deep Pydantic validation on a sample of records to verify
    type adherence and Pydantic model contract.
    """
    sample_records = df.head(sample_size).to_dict(orient="records")
    for idx, rec in enumerate(sample_records):
        try:
            WeatherRecordModel(**rec)
        except ValidationError as e:
            logger.error(f"Pydantic sample validation error on record {idx}: {e}")
            return False
    logger.info(f"Pydantic schema model check passed on {len(sample_records)} sample records.")
    return True


if __name__ == "__main__":
    from src.extract import extract_all_weather
    from src.transform import transform_all_weather

    print("Step 1: Extracting...")
    raw = extract_all_weather()

    print("\nStep 2: Transforming...")
    df_clean = transform_all_weather(raw)

    print("\nStep 3: Validating...")
    df_valid, df_invalid = validate_weather_dataframe(df_clean)

    sample_pydantic_check(df_valid)

    print(f"\n--- Validation Results ---")
    print(f"Valid records: {len(df_valid)}")
    print(f"Invalid records: {len(df_invalid)}")
    print(f"Cities covered: {df_valid['city_name'].unique().tolist()}")
