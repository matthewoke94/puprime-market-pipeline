# Forex Market Data Pipeline

## Business problem

Forex brokers need reliable, automated market data to power dashboards, risk systems, and client-facing platforms. Pulling prices manually doesn't scale, and a pipeline that silently fails or duplicates data is worse than no pipeline at all — downstream analytics and risk decisions depend on it being correct.

## Solution

A fault-tolerant ETL pipeline that pulls live forex prices, validates the response before trusting it, enriches it with trading indicators, and loads it into PostgreSQL using idempotent upserts — so the pipeline can be re-run safely at any frequency without corrupting data.

## Outcome

The pipeline successfully ingests live forex market data for multiple currency pairs, validates every response, enriches each record with trading indicators, and stores the results in PostgreSQL using idempotent upserts. Built-in retry logic, data quality validation, and duplicate prevention ensure the pipeline remains reliable, fault-tolerant, and safe to rerun without compromising data integrity. Each execution reports detailed loading metrics, providing clear visibility into pipeline performance and operational health.

---

## Architecture
## Data source

[Twelve Data](https://twelvedata.com) — real-time and historical OHLCV (Open, High, Low, Close) data for forex pairs. Free tier, authenticated via API key, accessed through the `/time_series` REST endpoint.

## ETL process, step by step

**1. Extraction (`extractor.py`)**
- Requests the last 30 daily candles for a given symbol
- Retries up to 3 times with increasing backoff (2s, 4s) on network timeouts or connection errors — a single dropped request doesn't fail the whole run
- Non-retryable errors (e.g. bad API key, malformed request) fail fast instead of wasting retries

**2. Validation**
Two layers, both must pass before data moves downstream:
- **Response validation** — rejects API error payloads, missing `values` field, or empty result sets
- **Data quality validation** — rejects rows with null timestamps, zero/negative prices, or `high < low` (a data integrity red flag that would otherwise corrupt every downstream calculation silently)

**3. Cleaning**
- `datetime` parsed with `errors="coerce"` so malformed dates become detectable `NaT` values rather than crashing the pipeline
- Price columns cast to `float` explicitly rather than trusting API string types

**4. Transformation (`transformer.py`)**
| Column | Meaning |
|---|---|
| `daily_return` | % change in closing price vs previous day |
| `price_range` | `high - low` |
| `sma_7` / `sma_14` | 7-day / 14-day simple moving average of close |
| `volatility` | 7-day rolling standard deviation of daily returns |

**5. Loading (`loader.py`)**
- Upserts via `ON CONFLICT (symbol, datetime) DO NOTHING`
- Counts rows before and after the insert to report exactly how many were new vs duplicate — not just "success"

**6. Orchestration (`pipeline.py`)**
- Runs extract → transform → load independently per symbol
- A failure on one symbol doesn't block the others
- Logs a final summary: `X/Y symbols processed successfully`

## Database schema

```sql
CREATE TABLE forex_prices (
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
```
`UNIQUE(symbol, datetime)` is what makes loads idempotent at the database level — not just application logic.

## Reliability features

| Feature | Implementation |
|---|---|
| Retry with backoff | Up to 3 attempts on network errors, 2s/4s delay |
| Response validation | Rejects malformed/error API payloads before parsing |
| Data quality checks | Rejects negative prices, high<low rows, null timestamps |
| Duplicate prevention | DB-level unique constraint + upsert logic |
| Observability | Every load reports inserted vs skipped counts |
| Structured logging | Timestamped, per-symbol log lines at every stage |

## Orchestration and scheduling

Currently runs on-demand via `python src/pipeline/pipeline.py`. Because loads are idempotent, it's safe to schedule at any frequency without risk of duplicate data — the natural next step would be a daily cron job or GitHub Actions workflow, or Airflow if orchestrating alongside other pipelines (see [Project 2](https://github.com/matthewoke94/puprime-trading-analytics) for the analytics layer this would feed).

## Tech stack

- **Language:** Python 3.12
- **Database:** PostgreSQL (Neon cloud)
- **Libraries:** pandas, psycopg2, requests, python-dotenv
- **Testing:** pytest
- **Version Control:** Git/GitHub

## Project structure
## Setup

```bash
pip install -r requirements.txt
```
Create `.env`:
Run:
```bash
python src/pipeline/pipeline.py
```

## Sample output
## Known gaps / next steps

Being transparent about what's not yet built, rather than overstating scope:
- No automated scheduler wired up yet (cron/Airflow) — pipeline runs on manual trigger
- Retry logic covers network failures only, not rate-limit (HTTP 429) backoff specifically
- No alerting on repeated pipeline failures (would be a natural extension)

## Business Value

This project demonstrates the foundation of a modern data engineering pipeline. By delivering clean, validated, and deduplicated market data into a centralized PostgreSQL database, it enables downstream analytics, trading dashboards, reporting, and risk monitoring systems to operate on trusted data.

The pipeline is designed to integrate seamlessly with the **[PuPrime Trading Analytics Dashboard](https://github.com/matthewoke94/puprime-trading-analytics)** for business intelligence and can be extended to support the **[PuPrime Anomaly Detection System](https://github.com/matthewoke94/puprime-anomaly-detection)** for automated trading surveillance and risk monitoring.

Its modular architecture also makes it straightforward to evolve into a production-grade platform using orchestration tools such as Apache Airflow, real-time streaming with Apache Kafka, or cloud-based data services as business requirements grow.


## Author

Matthew James

Data Engineer | Python | SQL | ETL | Data Pipelines
