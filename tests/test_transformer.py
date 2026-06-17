import pandas as pd
import pytest
from src.pipeline.transformer import transform_forex_data


def make_sample_df() -> pd.DataFrame:
    """Create a sample forex DataFrame for testing."""
    data = {
        "datetime": pd.date_range(start="2026-01-01", periods=20, freq="D"),
        "open": [1.10 + i * 0.001 for i in range(20)],
        "high": [1.11 + i * 0.001 for i in range(20)],
        "low": [1.09 + i * 0.001 for i in range(20)],
        "close": [1.105 + i * 0.001 for i in range(20)],
        "symbol": ["EUR/USD"] * 20,
    }
    return pd.DataFrame(data)


def test_transform_returns_dataframe():
    """Transformed result should be a DataFrame."""
    df = make_sample_df()
    result = transform_forex_data(df)
    assert isinstance(result, pd.DataFrame)


def test_transform_adds_expected_columns():
    """Transformer should add daily_return, sma_7, sma_14, volatility columns."""
    df = make_sample_df()
    result = transform_forex_data(df)
    expected_columns = ["daily_return", "price_range", "sma_7", "sma_14", "volatility"]
    for col in expected_columns:
        assert col in result.columns, f"Missing column: {col}"


def test_transform_empty_dataframe():
    """Transformer should handle empty DataFrame gracefully."""
    empty_df = pd.DataFrame()
    result = transform_forex_data(empty_df)
    assert result.empty


def test_price_range_calculation():
    """price_range should equal high minus low."""
    df = make_sample_df()
    result = transform_forex_data(df)
    expected = result["high"] - result["low"]
    pd.testing.assert_series_equal(
        result["price_range"].round(6),
        expected.round(6),
        check_names=False
    )