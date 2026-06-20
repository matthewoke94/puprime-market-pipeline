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


def load_to_db(df: pd.DataFrame) -> dict:
    """
    Load transformed forex data into PostgreSQL with idempotent upserts.

    Args:
        df: Transformed DataFrame from transformer

    Returns:
        Dict with counts: {"attempted": int, "inserted": int, "skipped_duplicates": int}
    """
    result = {"attempted": 0, "inserted": 0, "skipped_duplicates": 0}

    if df is None or df.empty:
        logger.warning("Empty DataFrame. Nothing to load.")
        return result

    if not DATABASE_URL:
        logger.error("DATABASE_URL not found. Check your .env file.")
        return result

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
        result["attempted"] = len(records)

        # Count rows that already exist before inserting, so we can report
        # inserted vs skipped instead of just "did something".
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM forex_prices;")
            before_count = cur.fetchone()[0]

        query = """
            INSERT INTO forex_prices (
                symbol, datetime, open, high, low, close,
                daily_return, price_range, sma_7, sma_14, volatility
            ) VALUES %s
            ON CONFLICT (symbol, datetime) DO NOTHING;
        """

        with conn.cursor() as cur:
            execute_values(cur, query, records)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM forex_prices;")
            after_count = cur.fetchone()[0]

        conn.commit()
        conn.close()

        result["inserted"] = after_count - before_count
        result["skipped_duplicates"] = result["attempted"] - result["inserted"]

        logger.info(
            f"Load complete: {result['inserted']} new rows inserted, "
            f"{result['skipped_duplicates']} duplicates skipped "
            f"(of {result['attempted']} attempted)."
        )
        return result

    except Exception as e:
        logger.error(f"Database load failed: {e}")
        raise


if __name__ == "__main__":
    from extractor import fetch_forex_price
    from transformer import transform_forex_data

    raw_df = fetch_forex_price("EUR/USD", outputsize=30)
    transformed_df = transform_forex_data(raw_df)
    load_to_db(transformed_df)