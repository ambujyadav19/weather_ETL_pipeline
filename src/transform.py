from typing import Any, Dict, List, Optional
import pandas as pd

from config.logging_config import setup_logger

logger = setup_logger("weather_etl.transform")

# World Meteorological Organization (WMO) Weather Interpretation Codes
WMO_CODE_MAP = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

# Mapping raw API variable names to clean, unit-aware database column names
COLUMN_RENAME_MAP = {
    "time": "recorded_at",
    "temperature_2m": "temperature_celsius",
    "relative_humidity_2m": "humidity_pct",
    "precipitation": "precipitation_mm",
    "wind_speed_10m": "wind_speed_kmh",
    "weather_code": "weather_code",
}


def transform_city_weather(raw_city_item: Dict[str, Any]) -> pd.DataFrame:
    """
    Transforms raw JSON weather payload for a single city into a clean Pandas DataFrame.

    Args:
        raw_city_item: Dict containing city_name, country, coordinates, extracted_at,
                       and raw_data from Open-Meteo API.

    Returns:
        pd.DataFrame containing standardized and enriched hourly weather records.
    """
    city_name = raw_city_item.get("city_name", "Unknown")
    country = raw_city_item.get("country", "Unknown")
    latitude = raw_city_item.get("latitude")
    longitude = raw_city_item.get("longitude")
    extracted_at = raw_city_item.get("extracted_at")

    raw_data = raw_city_item.get("raw_data", {})
    hourly_data = raw_data.get("hourly", {})

    if not hourly_data or "time" not in hourly_data:
        logger.warning(f"No valid hourly data found to transform for {city_name}.")
        return pd.DataFrame()

    # Step 1: Flatten parallel arrays into a tabular DataFrame
    df = pd.DataFrame(hourly_data)

    # Step 2: Rename columns to standardized, unit-specific names
    df = df.rename(columns=COLUMN_RENAME_MAP)

    # Step 3: Add city metadata and audit columns
    df["city_name"] = city_name
    df["country"] = country
    df["latitude"] = float(latitude) if latitude is not None else None
    df["longitude"] = float(longitude) if longitude is not None else None
    df["extracted_at"] = pd.to_datetime(extracted_at, utc=True)

    # Step 4: Datetime parsing & timezone normalization (UTC)
    df["recorded_at"] = pd.to_datetime(df["recorded_at"], utc=True)

    # Step 5: Data type casting
    numeric_floats = ["temperature_celsius", "humidity_pct", "precipitation_mm", "wind_speed_kmh"]
    for col in numeric_floats:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    if "weather_code" in df.columns:
        df["weather_code"] = pd.to_numeric(df["weather_code"], errors="coerce").fillna(-1).astype("int32")

    # Step 6: Enrich with human-readable weather condition description
    df["weather_condition"] = df["weather_code"].map(
        lambda code: WMO_CODE_MAP.get(code, f"Unknown ({code})")
    )

    # Reorder columns logically
    desired_order = [
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
    existing_cols = [c for c in desired_order if c in df.columns]
    df = df[existing_cols]

    return df


def transform_all_weather(raw_records: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Transforms, cleans, and merges extracted weather records for all cities.

    Args:
        raw_records: List of raw city dictionaries extracted from the API.

    Returns:
        A unified, deduplicated Pandas DataFrame ready for validation and loading.
    """
    if not raw_records:
        logger.warning("Empty raw_records list received for transformation.")
        return pd.DataFrame()

    logger.info(f"Transforming weather data for {len(raw_records)} cities...")
    city_dfs: List[pd.DataFrame] = []

    for item in raw_records:
        city_df = transform_city_weather(item)
        if not city_df.empty:
            city_dfs.append(city_df)

    if not city_dfs:
        logger.warning("No city data could be transformed.")
        return pd.DataFrame()

    # Concatenate all city DataFrames
    combined_df = pd.concat(city_dfs, ignore_index=True)

    initial_count = len(combined_df)

    # Step 7: Deduplication based on composite primary key (city_name, recorded_at)
    combined_df = combined_df.drop_duplicates(subset=["city_name", "recorded_at"], keep="last")
    dedup_count = len(combined_df)
    duplicates_removed = initial_count - dedup_count

    if duplicates_removed > 0:
        logger.info(f"Removed {duplicates_removed} duplicate records during transformation.")

    # Sort deterministically
    combined_df = combined_df.sort_values(by=["city_name", "recorded_at"]).reset_index(drop=True)

    logger.info(
        f"Transformation complete: {dedup_count} total rows across {combined_df['city_name'].nunique()} cities."
    )

    return combined_df


if __name__ == "__main__":
    from src.extract import extract_all_weather

    print("Step 1: Extracting raw data from API...")
    raw_data = extract_all_weather()

    print("\nStep 2: Transforming raw data with Pandas...")
    clean_df = transform_all_weather(raw_data)

    print("\n--- Transformed DataFrame Info ---")
    print(clean_df.info())

    print("\n--- First 5 Records Sample ---")
    print(
        clean_df[["city_name", "recorded_at", "temperature_celsius", "humidity_pct", "weather_condition"]].head()
    )
