import pandas as pd

import bot_engine
import ml_entry_filter


def _df(rsi=25.0, macd_hist=0.0005, close=1.1000, atr=0.0010):
    rows = [
        {"time": 0, "close": 1.0990, "rsi": 50.0, "macd_hist": 0.0, "atr": atr, "sma20": 1.0, "sma50": 1.0},
        {"time": 1, "close": 1.0995, "rsi": 50.0, "macd_hist": 0.0, "atr": atr, "sma20": 1.0, "sma50": 1.0},
        {"time": 2, "close": close, "rsi": rsi, "macd_hist": macd_hist, "atr": atr, "sma20": 1.0, "sma50": 1.0},
    ]
    return pd.DataFrame(rows)


def _state(**overrides):
    base = {
        "running": 1, "kill_switch_tripped": 0, "disabled_reason": None, "risk_pct": 0.01,
        "magic": 424001, "ml_filter_trend_enabled": 0, "ml_filter_fast_enabled": 0,
        "ml_filter_min_confidence": 0.5,
    }
    base.update(overrides)
    return base


def _symbol_meta():
    return {"tick_value": 1.0, "tick_size": 0.00001, "volume_step": 0.01, "volume_min": 0.01}


class _FakeModel:
    def __init__(self, win_prob):
        self.win_prob = win_prob

    def predict_proba(self, X):
        return [[1 - self.win_prob, self.win_prob] for _ in X]


def test_ml_filter_vetoes_entry_below_confidence_trend(monkeypatch):
    monkeypatch.setattr(ml_entry_filter, "load_entry_filter_model_cached", lambda mode: _FakeModel(0.2))
    df = _df(rsi=25.0, macd_hist=0.0005)  # -> COMPRAR FUERTE

    result = bot_engine.process_symbol_tick(
        "EURUSD", df, _state(ml_filter_trend_enabled=1), [], 1000, _symbol_meta(),
        place_order_fn=lambda **kw: {"success": True},
    )

    assert result["action"] == "rejected"
    assert "20%" in result["reason"]


def test_ml_filter_allows_entry_above_confidence_trend(monkeypatch):
    monkeypatch.setattr(ml_entry_filter, "load_entry_filter_model_cached", lambda mode: _FakeModel(0.8))
    df = _df(rsi=25.0, macd_hist=0.0005)

    result = bot_engine.process_symbol_tick(
        "EURUSD", df, _state(ml_filter_trend_enabled=1), [], 1000, _symbol_meta(),
        place_order_fn=lambda **kw: {"success": True, "order": 1, "volume": kw["volume"], "price": 1.1},
    )

    assert result["action"] == "opened"


def test_ml_filter_disabled_by_default_does_not_block_trend(monkeypatch):
    monkeypatch.setattr(ml_entry_filter, "load_entry_filter_model_cached", lambda mode: _FakeModel(0.0))
    df = _df(rsi=25.0, macd_hist=0.0005)

    result = bot_engine.process_symbol_tick(
        "EURUSD", df, _state(ml_filter_trend_enabled=0), [], 1000, _symbol_meta(),
        place_order_fn=lambda **kw: {"success": True, "order": 1, "volume": kw["volume"], "price": 1.1},
    )

    assert result["action"] == "opened"  # filter off — even a 0.0 confidence model doesn't block


def test_ml_filter_enabled_but_no_model_does_not_block_trend(monkeypatch):
    monkeypatch.setattr(ml_entry_filter, "load_entry_filter_model_cached", lambda mode: None)
    df = _df(rsi=25.0, macd_hist=0.0005)

    result = bot_engine.process_symbol_tick(
        "EURUSD", df, _state(ml_filter_trend_enabled=1), [], 1000, _symbol_meta(),
        place_order_fn=lambda **kw: {"success": True, "order": 1, "volume": kw["volume"], "price": 1.1},
    )

    assert result["action"] == "opened"


def test_ml_filter_vetoes_entry_below_confidence_fast(monkeypatch):
    monkeypatch.setattr(ml_entry_filter, "load_entry_filter_model_cached", lambda mode: _FakeModel(0.1))
    df = _df(rsi=40.0)  # -> TENDENCIA ALCISTA (fast-only entry signal)

    result = bot_engine.process_symbol_tick_fast(
        "EURUSD", df, _state(ml_filter_fast_enabled=1), [], 1000, _symbol_meta(),
        place_order_fn=lambda **kw: {"success": True},
    )

    assert result["action"] == "rejected"
    assert "10%" in result["reason"]
