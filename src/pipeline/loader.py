import logging
import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")


def create_table(conn) -> None:
    """Create forex_prices table if it doesn't exist."""
    query = """
        CREATE TABLE IF NOT EXISTS forex_prices (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(10) NOT NULL,
            datetime TIMESTAMP NOT NULL,
            open NUMERIC(10, 5),
            high NUMERIC(10, 5),
            low NUMERIC(10, 5),
            close NUMERIC(10, 5),
            daily_return NUMERIC(10, 6),
            price_range NUMERIC(10, 6),
            sma_7 NUMERIC(10, 5),
            sma_14 NUMERIC(10, 5),
            volatility NUMERIC(10, 6),
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(symbol, datetime)
        );
    """
    with conn.cursor() as cur:
        cur.execute(query)
    conn.commit()
    logger.info("Table forex_prices ready.")


def load_to_db(df: pd.DataFrame) -> None:
    """
    Load transformed forex data into PostgreSQL.

    Args:
        df: Transformed DataFrame from transformer
    """
    if df is None or df.empty:
        logger.warning("Empty DataFrame. Nothing to load.")
        return

    if not DATABASE_URL:
        logger.error("DATABASE_URL not found. Check your .env file.")
        return

    try:
        conn = psycopg2.connect(DATABASE_URL)
        create_table(conn)

        records = [
            (
                row.symbol,
                row.datetime,
                row.open,
                row.high,
                row.low,
                row.close,
                row.daily_return if pd.notna(row.daily_return) else None,
                row.price_range,
                row.sma_7 if pd.notna(row.sma_7) else None,
                row.sma_14 if pd.notna(row.sma_14) else None,
                row.volatility if pd.notna(row.volatility) else None,
            )
            for row in df.itertuples()
        ]

        query = """
            INSERT INTO forex_prices (
                symbol, datetime, open, high, low, close,
                daily_return, price_range, sma_7, sma_14, volatility
            ) VALUES %s
            ON CONFLICT (symbol, datetime) DO NOTHING;
        """

        with conn.cursor() as cur:
            execute_values(cur, query, records)

        conn.commit()
        conn.close()
        logger.info(f"Successfully loaded {len(records)} records into database.")

    except Exception as e:
        logger.error(f"Database load failed: {e}")
        raise


if __name__ == "__main__":
    from extractor import fetch_forex_price
    from transformer import transform_forex_data

    raw_df = fetch_forex_price("EUR/USD", outputsize=30)
    transformed_df = transform_forex_data(raw_df)
    load_to_db(transformed_df)