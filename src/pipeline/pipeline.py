import logging
import sys
from extractor import fetch_forex_price
from transformer import transform_forex_data
from loader import load_to_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SYMBOLS = ["EUR/USD", "GBP/USD", "USD/JPY"]


def run_pipeline(symbol: str, outputsize: int = 30) -> bool:
    """
    Run full ETL pipeline for a given forex symbol.

    Args:
        symbol: Currency pair e.g. 'EUR/USD'
        outputsize: Number of data points to fetch

    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Starting pipeline for {symbol}")

    # Extract
    raw_df = fetch_forex_price(symbol, outputsize=outputsize)
    if raw_df is None:
        logger.error(f"Extraction failed for {symbol}")
        return False

    # Transform
    transformed_df = transform_forex_data(raw_df)
    if transformed_df is None or transformed_df.empty:
        logger.error(f"Transformation failed for {symbol}")
        return False

    # Load
    load_to_db(transformed_df)
    logger.info(f"Pipeline complete for {symbol}")
    return True


if __name__ == "__main__":
    success_count = 0

    for symbol in SYMBOLS:
        success = run_pipeline(symbol)
        if success:
            success_count += 1

    logger.info(
        f"Pipeline finished. {success_count}/{len(SYMBOLS)} symbols processed."
    )

    if success_count == 0:
        sys.exit(1)