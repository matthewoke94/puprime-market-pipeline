import os
import time
import logging
from typing import Optional
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("TWELVE_DATA_API_KEY")
BASE_URL = "https://api.twelvedata.com"

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2


def validate_response(data: dict, symbol: str) -> bool:
    """
    Validate the raw API response before any parsing happens.

    Checks for API error payloads, missing keys, and empty result sets.

    Args:
        data: Parsed JSON response from Twelve Data
        symbol: Symbol requested, used for error messages

    Returns:
        True if the response looks usable, False otherwise
    """
    if not isinstance(data, dict):
        logger.error(f"[{symbol}] Response is not a JSON object: {type(data)}")
        return False

    if data.get("status") == "error":
        logger.error(f"[{symbol}] API returned an error: {data.get('message')}")
        return False

    if "values" not in data or not data["values"]:
        logger.error(f"[{symbol}] No 'values' field in response: {data}")
        return False

    return True


def validate_dataframe(df: pd.DataFrame, symbol: str) -> bool:
    """
    Data quality checks on the parsed DataFrame before it's allowed downstream.

    Flags issues that would silently corrupt analytics: negative or zero
    prices, high < low inversions, and missing timestamps.

    Args:
        df: Parsed OHLCV DataFrame
        symbol: Symbol being validated, used for error messages

    Returns:
        True if the data passes quality checks, False otherwise
    """
    if df.empty:
        logger.error(f"[{symbol}] DataFrame is empty after parsing.")
        return False

    required_cols = {"datetime", "open", "high", "low", "close"}
    missing = required_cols - set(df.columns)
    if missing:
        logger.error(f"[{symbol}] Missing required columns: {missing}")
        return False

    if df["datetime"].isna().any():
        logger.error(f"[{symbol}] Found null timestamps in response.")
        return False

    price_cols = ["open", "high", "low", "close"]
    if (df[price_cols] <= 0).any().any():
        logger.error(f"[{symbol}] Found zero or negative price values.")
        return False

    if (df["high"] < df["low"]).any():
        logger.error(f"[{symbol}] Found rows where high < low — data integrity issue.")
        return False

    return True


def fetch_forex_price(
    symbol: str,
    interval: str = "1day",
    outputsize: int = 30
) -> Optional[pd.DataFrame]:
    """
    Fetch historical forex price data from Twelve Data API, with retries
    on transient failures and validation before returning.

    Args:
        symbol: Currency pair e.g. 'EUR/USD'
        interval: Time interval e.g. '1day', '1h'
        outputsize: Number of data points to return

    Returns:
        Validated DataFrame with OHLCV data, or None if extraction failed
        after all retries or validation checks did not pass
    """
    if not API_KEY:
        logger.error("API key not found. Check your .env file.")
        return None

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": API_KEY,
    }

    last_exception: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"[{symbol}] Fetching data (attempt {attempt}/{MAX_RETRIES})...")
            response = requests.get(
                f"{BASE_URL}/time_series",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if not validate_response(data, symbol):
                return None  # API-level error, retrying won't help

            df = pd.DataFrame(data["values"])
            df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
            df[["open", "high", "low", "close"]] = df[
                ["open", "high", "low", "close"]
            ].astype(float)
            df["symbol"] = symbol

            if not validate_dataframe(df, symbol):
                return None  # Bad data, retrying won't fix it

            logger.info(f"[{symbol}] Successfully fetched and validated {len(df)} records.")
            return df

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_exception = e
            logger.warning(
                f"[{symbol}] Network issue on attempt {attempt}/{MAX_RETRIES}: {e}"
            )
            if attempt < MAX_RETRIES:
                sleep_time = RETRY_BACKOFF_SECONDS * attempt
                logger.info(f"[{symbol}] Retrying in {sleep_time}s...")
                time.sleep(sleep_time)

        except requests.exceptions.RequestException as e:
            logger.error(f"[{symbol}] Non-retryable request error: {e}")
            return None

    logger.error(f"[{symbol}] All {MAX_RETRIES} attempts failed. Last error: {last_exception}")
    return None


if __name__ == "__main__":
    df = fetch_forex_price("EUR/USD")
    if df is not None:
        print(df.head())