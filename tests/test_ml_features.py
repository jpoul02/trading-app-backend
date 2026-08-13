import pandas as pd

import ml_features


def _df():
    return pd.DataFrame([
        {"time": 1735689600, "close": 1.1050, "rsi": 28.0, "macd_hist": 0.0004,
         "atr": 0.0011, "sma20": 1.1000, "sma50": 1.0950},
    ])


def test_extract_entry_features_reads_expected_columns():
    features = ml_features.extract_entry_features(_df(), 0)

    assert features["rsi"] == 28.0
    assert features["macd_hist"] == 0.0004
    assert round(features["atr_pct"], 6) == round(0.0011 / 1.1050, 6)
    assert round(features["price_vs_sma20"], 6) == round((1.1050 - 1.1000) / 1.1000, 6)
    assert round(features["price_vs_sma50"], 6) == round((1.1050 - 1.0950) / 1.0950, 6)
    assert features["hour_utc"] == 0  # 1735689600 == 2025-01-01T00:00:00Z


def test_extract_entry_features_defaults_when_indicators_missing():
    df = pd.DataFrame([{"time": 1735689600, "close": 1.1050, "rsi": float("nan"),
                         "macd_hist": float("nan"), "atr": float("nan"),
                         "sma20": float("nan"), "sma50": float("nan")}])

    features = ml_features.extract_entry_features(df, 0)

    assert features["rsi"] == 50.0
    assert features["macd_hist"] == 0.0
    assert features["atr_pct"] == 0.0
    assert features["price_vs_sma20"] == 0.0
    assert features["price_vs_sma50"] == 0.0


def test_features_to_vector_preserves_key_order():
    features = {"rsi": 1, "macd_hist": 2, "atr_pct": 3, "price_vs_sma20": 4, "price_vs_sma50": 5, "hour_utc": 6}

    assert ml_features.features_to_vector(features) == [1, 2, 3, 4, 5, 6]
