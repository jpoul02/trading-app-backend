from datetime import datetime, timezone

import pandas as pd

FEATURE_KEYS = ["rsi", "macd_hist", "atr_pct", "price_vs_sma20", "price_vs_sma50", "hour_utc"]


def extract_entry_features(df: pd.DataFrame, index: int) -> dict:
    """Reads an indicator-enriched df (post add_indicators) at `index` and
    returns the feature snapshot used by the ML entry filter."""
    row = df.iloc[index]
    close = float(row["close"])
    atr = float(row["atr"]) if pd.notna(row["atr"]) else 0.0
    sma20 = float(row["sma20"]) if pd.notna(row["sma20"]) else close
    sma50 = float(row["sma50"]) if pd.notna(row["sma50"]) else close

    hour_utc = 0
    if "time" in df.columns and pd.notna(row["time"]):
        hour_utc = datetime.fromtimestamp(int(row["time"]), tz=timezone.utc).hour

    return {
        "rsi": float(row["rsi"]) if pd.notna(row["rsi"]) else 50.0,
        "macd_hist": float(row["macd_hist"]) if pd.notna(row["macd_hist"]) else 0.0,
        "atr_pct": (atr / close) if close else 0.0,
        "price_vs_sma20": ((close - sma20) / sma20) if sma20 else 0.0,
        "price_vs_sma50": ((close - sma50) / sma50) if sma50 else 0.0,
        "hour_utc": hour_utc,
    }


def features_to_vector(features: dict) -> list[float]:
    return [features[k] for k in FEATURE_KEYS]
