import logging
import pandas as pd

logger = logging.getLogger(__name__)


def transform_forex_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform raw forex OHLCV data into enriched analytical dataset.

    Adds:
        - daily_return: percentage change in closing price
        - price_range: difference between high and low
        - sma_7: 7-day simple moving average
        - sma_14: 14-day simple moving average
        - volatility: rolling 7-day standard deviation of returns

    Args:
        df: Raw DataFrame from extractor

    Returns:
        Enriched DataFrame ready for loading
    """
    if df is None or df.empty:
        logger.warning("Empty DataFrame received. Skipping transformation.")
        return df

    df = df.sort_values("datetime").reset_index(drop=True)

    # Daily return (percentage change)
    df["daily_return"] = df["close"].pct_change() * 100

    # Price range (high - low)
    df["price_range"] = df["high"] - df["low"]

    # Simple moving averages
    df["sma_7"] = df["close"].rolling(window=7).mean()
    df["sma_14"] = df["close"].rolling(window=14).mean()

    # Volatility (7-day rolling std of returns)
    df["volatility"] = df["daily_return"].rolling(window=7).std()

    logger.info(f"Transformation complete. Shape: {df.shape}")
    return df


if __name__ == "__main__":
    from extractor import fetch_forex_price

    raw_df = fetch_forex_price("EUR/USD", outputsize=30)
    transformed_df = transform_forex_data(raw_df)
    print(transformed_df[["datetime", "close", "daily_return", "sma_7", "volatility"]])
