import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.config import DEFAULT_CITIES, HOURLY_VARIABLES, OPEN_METEO_BASE_URL
from config.logging_config import setup_logger

logger = setup_logger("weather_etl.extract")


def get_http_session(
    retries: int = 3,
    backoff_factor: float = 1.0,
    status_forcelist: tuple = (429, 500, 502, 503, 504),
) -> requests.Session:
    """
    Creates a requests.Session configured with exponential backoff retries.
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def extract_city_weather(
    city_info: Dict[str, Any],
    session: Optional[requests.Session] = None,
    timeout: int = 10,
) -> Optional[Dict[str, Any]]:
    """
    Fetches hourly weather data for a single city from Open-Meteo API.

    Args:
        city_info: Dictionary containing city_name, country, latitude, longitude.
        session: Reusable requests.Session object (optional).
        timeout: Request timeout in seconds.

    Returns:
        Dictionary containing city metadata, extracted_at timestamp, and raw JSON payload,
        or None if extraction fails.
    """
    city_name = city_info.get("city_name", "Unknown")
    lat = city_info.get("latitude")
    lon = city_info.get("longitude")

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(HOURLY_VARIABLES),
        "timezone": "UTC",
    }

    http = session or get_http_session()

    try:
        start_time = time.time()
        logger.info(f"Extracting weather data for {city_name} ({lat}, {lon})...")

        response = http.get(OPEN_METEO_BASE_URL, params=params, timeout=timeout)
        duration = round(time.time() - start_time, 2)

        # Check HTTP status code
        response.raise_for_status()

        data = response.json()

        # Sanity check on response structure
        if "hourly" not in data or "time" not in data["hourly"]:
            logger.error(f"Malformed response for {city_name}: missing 'hourly.time'")
            return None

        num_hours = len(data["hourly"]["time"])
        logger.info(
            f"Successfully extracted {num_hours} hourly records for {city_name} in {duration}s"
        )

        return {
            "city_name": city_name,
            "country": city_info.get("country", "Unknown"),
            "latitude": lat,
            "longitude": lon,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "raw_data": data,
        }

    except requests.exceptions.Timeout:
        logger.error(f"Timeout ({timeout}s) exceeded while requesting data for {city_name}")
        return None
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred for {city_name}: {http_err} (Status: {response.status_code})")
        return None
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Network error while extracting data for {city_name}: {req_err}")
        return None
    except Exception as err:
        logger.error(f"Unexpected error extracting data for {city_name}: {err}", exc_info=True)
        return None


def extract_all_weather(cities: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    Extracts weather data for all configured target cities.

    Args:
        cities: List of city dictionaries. Defaults to DEFAULT_CITIES from config.

    Returns:
        List of successfully extracted city data dictionaries.
    """
    target_cities = cities or DEFAULT_CITIES
    results: List[Dict[str, Any]] = []

    logger.info(f"Starting weather extraction batch for {len(target_cities)} cities...")
    session = get_http_session()

    try:
        for city in target_cities:
            extracted = extract_city_weather(city_info=city, session=session)
            if extracted:
                results.append(extracted)
    finally:
        session.close()

    success_count = len(results)
    total_count = len(target_cities)
    logger.info(f"Extraction complete: {success_count}/{total_count} cities extracted successfully.")

    return results


if __name__ == "__main__":
    # Test script directly
    extracted_data = extract_all_weather()
    print(f"\n--- Extracted Summary ---")
    print(f"Total cities extracted: {len(extracted_data)}")
    for item in extracted_data:
        hours = len(item["raw_data"]["hourly"]["time"])
        print(f" - {item['city_name']} ({item['country']}): {hours} hourly data points")
