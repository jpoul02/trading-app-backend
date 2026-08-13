import json

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

import ml_entry_filter


def _fake_trade(profit, opened_at, win_shape):
    features = (
        {"rsi": 20.0, "macd_hist": 0.002, "atr_pct": 0.001, "price_vs_sma20": 0.002, "price_vs_sma50": 0.002, "hour_utc": 10}
        if win_shape else
        {"rsi": 80.0, "macd_hist": -0.002, "atr_pct": 0.001, "price_vs_sma20": -0.002, "price_vs_sma50": -0.002, "hour_utc": 10}
    )
    return {
        "direction": "buy", "entry": 1.1, "exit": 1.1, "sl": 1.09, "tp": 1.11,
        "volume": 0.1, "profit": profit, "opened_at": opened_at, "closed_at": opened_at + 1,
        "features": features,
    }


def _fake_candles(n=300):
    return pd.DataFrame([{"time": i, "open": 1.1, "high": 1.1, "low": 1.1, "close": 1.1} for i in range(n)])


def _fake_symbol_meta(symbol):
    return {"tick_value": 1.0, "tick_size": 0.00001, "volume_step": 0.01, "volume_min": 0.01}


def test_train_rejects_when_no_symbols():
    result = ml_entry_filter.train_entry_filter_model("trend", [], "M15", 0.01, min_confidence=0.5)

    assert result["trained"] is False
    assert "error" in result


def test_train_rejects_when_too_few_trades():
    def fake_simulate(df, mode, risk_pct, symbol_meta, starting_balance, warmup, **kwargs):
        return {"trades": [_fake_trade(10.0, i, True) for i in range(5)]}

    result = ml_entry_filter.train_entry_filter_model(
        "trend", ["EURUSD"], "M15", 0.01, min_confidence=0.5,
        fetch_candles_fn=lambda *a: _fake_candles(),
        symbol_info_fn=_fake_symbol_meta,
        simulate_fn=fake_simulate, save_run_fn=lambda **kw: None,
    )

    assert result["trained"] is False
    assert "Muy pocos trades" in result["error"]


def test_train_rejects_when_all_train_labels_are_the_same():
    def fake_simulate(df, mode, risk_pct, symbol_meta, starting_balance, warmup, **kwargs):
        return {"trades": [_fake_trade(10.0, i, True) for i in range(40)]}  # all wins

    result = ml_entry_filter.train_entry_filter_model(
        "trend", ["EURUSD"], "M15", 0.01, min_confidence=0.5,
        fetch_candles_fn=lambda *a: _fake_candles(),
        symbol_info_fn=_fake_symbol_meta,
        simulate_fn=fake_simulate, save_run_fn=lambda **kw: None,
    )

    assert result["trained"] is False
    assert "mismo resultado" in result["error"]


def test_train_saves_model_when_filter_improves_profit_factor(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_entry_filter, "MODEL_DIR", tmp_path)

    # 40 trades, chronological 80/20 split -> train = i 0..31, test = i 32..39.
    # Win-shaped features (i % 2 == 0) mostly profit +20; loss-shaped features
    # (i % 2 == 1) always -10. i == 38 is win-shaped but still lost a little
    # (-5) so the *filtered* test slice keeps at least one loss — profit_factor
    # needs a nonzero denominator, so an all-wins filtered slice would be
    # undefined (None), not "better than the baseline".
    trades = []
    for i in range(40):
        win_shape = i % 2 == 0
        if i == 38:
            profit = -5.0
        else:
            profit = 20.0 if win_shape else -10.0
        trades.append(_fake_trade(profit, i, win_shape))

    def fake_simulate(df, mode, risk_pct, symbol_meta, starting_balance, warmup, **kwargs):
        return {"trades": trades}

    saved = {}

    def fake_save(**kw):
        saved.update(kw)

    result = ml_entry_filter.train_entry_filter_model(
        "trend", ["EURUSD"], "M15", 0.01, min_confidence=0.5,
        fetch_candles_fn=lambda *a: _fake_candles(),
        symbol_info_fn=_fake_symbol_meta,
        simulate_fn=fake_simulate, save_run_fn=fake_save,
    )

    assert result["trained"] is True
    assert (tmp_path / "entry_filter_trend.joblib").exists()
    assert saved["enabled"] == 1
    assert saved["mode"] == "trend"


def test_train_result_is_json_serializable_with_numpy_sourced_profits(tmp_path, monkeypatch):
    # Regression test: real backtest trades carry profit as numpy.float64 (pandas/MT5
    # arithmetic), not plain Python float. round()/comparisons on numpy.float64 stay
    # numpy-typed, and numpy.bool_ isn't JSON serializable — FastAPI's jsonable_encoder
    # crashed on this in production (POST /api/ml/train) even though every other test
    # here uses plain-float fixtures that never exercise the numpy path.
    monkeypatch.setattr(ml_entry_filter, "MODEL_DIR", tmp_path)

    trades = [
        _fake_trade(np.float64(20.0) if i % 2 == 0 else np.float64(-10.0), i, i % 2 == 0)
        for i in range(40)
    ]
    trades[38]["profit"] = np.float64(-5.0)

    def fake_simulate(df, mode, risk_pct, symbol_meta, starting_balance, warmup, **kwargs):
        return {"trades": trades}

    result = ml_entry_filter.train_entry_filter_model(
        "trend", ["EURUSD"], "M15", 0.01, min_confidence=0.5,
        fetch_candles_fn=lambda *a: _fake_candles(),
        symbol_info_fn=_fake_symbol_meta,
        simulate_fn=fake_simulate, save_run_fn=lambda **kw: None,
    )

    assert result["trained"] is True  # `is True` — fails if this is numpy.bool_, not bool
    assert type(result["trained"]) is bool
    assert type(result["profit_factor_filtered"]) is float
    assert type(result["profit_factor_unfiltered"]) is float
    json.dumps(result)  # raises TypeError if anything is still numpy-typed


def test_train_skips_symbols_with_insufficient_history():
    def fake_simulate(df, mode, risk_pct, symbol_meta, starting_balance, warmup, **kwargs):
        return {"trades": [_fake_trade(10.0, i, i % 2 == 0) for i in range(40)]}

    result = ml_entry_filter.train_entry_filter_model(
        "trend", ["EURUSD", "GBPUSD"], "M15", 0.01, min_confidence=0.5,
        fetch_candles_fn=lambda symbol, *a: _fake_candles() if symbol == "EURUSD" else None,
        symbol_info_fn=_fake_symbol_meta,
        simulate_fn=fake_simulate, save_run_fn=lambda **kw: None,
    )

    # GBPUSD contributed nothing (None candles) — only EURUSD's 40 trades count.
    assert result["n_trades"] == 40
