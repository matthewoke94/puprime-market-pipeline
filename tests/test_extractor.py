import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src", "pipeline"))

from extractor import fetch_forex_price, validate_response, validate_dataframe


def make_mock_response(values):
    """Build a fake requests.Response-like object."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"values": values}
    return mock_resp


def make_valid_values(n=5):
    return [
        {
            "datetime": f"2026-06-{10+i:02d}",
            "open": "1.1000",
            "high": "1.1100",
            "low": "1.0900",
            "close": "1.1050",
        }
        for i in range(n)
    ]


def test_validate_response_rejects_error_status():
    bad = {"status": "error", "message": "invalid api key"}
    assert validate_response(bad, "EUR/USD") is False


def test_validate_response_rejects_missing_values():
    bad = {"status": "ok"}
    assert validate_response(bad, "EUR/USD") is False


def test_validate_response_accepts_good_payload():
    good = {"status": "ok", "values": make_valid_values(3)}
    assert validate_response(good, "EUR/USD") is True


def test_validate_dataframe_rejects_negative_prices():
    df = pd.DataFrame({
        "datetime": pd.to_datetime(["2026-06-10"]),
        "open": [-1.1], "high": [1.2], "low": [1.0], "close": [1.1],
    })
    assert validate_dataframe(df, "EUR/USD") is False


def test_validate_dataframe_rejects_high_below_low():
    df = pd.DataFrame({
        "datetime": pd.to_datetime(["2026-06-10"]),
        "open": [1.1], "high": [1.0], "low": [1.2], "close": [1.1],
    })
    assert validate_dataframe(df, "EUR/USD") is False


def test_validate_dataframe_accepts_clean_data():
    df = pd.DataFrame({
        "datetime": pd.to_datetime(["2026-06-10", "2026-06-11"]),
        "open": [1.1, 1.2], "high": [1.2, 1.3], "low": [1.0, 1.1], "close": [1.15, 1.25],
    })
    assert validate_dataframe(df, "EUR/USD") is True


@patch("extractor.requests.get")
def test_fetch_forex_price_success(mock_get):
    mock_get.return_value = make_mock_response(make_valid_values(10))
    with patch("extractor.API_KEY", "fake-key-for-test"):
        df = fetch_forex_price("EUR/USD", outputsize=10)
    assert df is not None
    assert len(df) == 10
    assert "symbol" in df.columns


@patch("extractor.requests.get")
def test_fetch_forex_price_retries_on_connection_error(mock_get):
    import requests
    mock_get.side_effect = [
        requests.exceptions.ConnectionError("network down"),
        make_mock_response(make_valid_values(5)),
    ]
    with patch("extractor.API_KEY", "fake-key-for-test"), \
         patch("extractor.RETRY_BACKOFF_SECONDS", 0):
        df = fetch_forex_price("EUR/USD", outputsize=5)
    assert df is not None
    assert mock_get.call_count == 2


@patch("extractor.requests.get")
def test_fetch_forex_price_returns_none_after_all_retries_fail(mock_get):
    import requests
    mock_get.side_effect = requests.exceptions.ConnectionError("network down")
    with patch("extractor.API_KEY", "fake-key-for-test"), \
         patch("extractor.RETRY_BACKOFF_SECONDS", 0):
        df = fetch_forex_price("EUR/USD", outputsize=5)
    assert df is None
    assert mock_get.call_count == 3


def test_fetch_forex_price_no_api_key():
    with patch("extractor.API_KEY", None):
        df = fetch_forex_price("EUR/USD")
    assert df is None