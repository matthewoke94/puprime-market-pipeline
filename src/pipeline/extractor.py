import os
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


def fetch_forex_price(
    symbol: str,
    interval: str = "1day",
    outputsize: int = 30
) -> Optional[pd.DataFrame]:
    """
    Fetch historical forex price data from Twelve Data API.

    Args:
        symbol: Currency pair e.g. 'EUR/USD'
        interval: Time interval e.g. '1day', '1h'
        outputsize: Number of data points to return

    Returns:
        DataFrame with OHLCV data or None if request fails
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

    try:
        logger.info(f"Fetching {symbol} data from Twelve Data...")
        response = requests.get(
            f"{BASE_URL}/time_series",
            params=params,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if "values" not in data:
            logger.error(f"Unexpected response: {data}")
            return None

        df = pd.DataFrame(data["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        df[["open", "high", "low", "close"]] = df[
            ["open", "high", "low", "close"]
        ].astype(float)
        df["symbol"] = symbol

        logger.info(f"Successfully fetched {len(df)} records for {symbol}")
        return df

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return None


if __name__ == "__main__":
    df = fetch_forex_price("EUR/USD")
    if df is not None:
        print(df.head())