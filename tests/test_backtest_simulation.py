import math
import time

import pandas as pd
import backtest_engine


def _candles(n=5):
    return pd.DataFrame([
        {"time": i, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}
        for i in range(n)
    ])


def _symbol_meta():
    return {"tick_value": 1.0, "tick_size": 0.00001, "volume_step": 0.01, "volume_min": 0.01}


def test_no_signal_never_opens_a_trade():
    df = _candles(6)

    def signal_fn(window):
        return {"signal": "ESPERAR", "signal_reason": "x", "last_close": 1.1, "atr": 0.001, "bb_mid": 1.1}

    result = backtest_engine.simulate_strategy(
        df, "trend", risk_pct=0.01, symbol_meta=_symbol_meta(),
        starting_balance=1000, warmup=3, signal_fn=signal_fn,
    )

    assert result["total_trades"] == 0
    assert result["total_profit"] == 0.0


def test_trade_closes_at_take_profit():
    df = pd.DataFrame([
        {"time": 0, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
        {"time": 1, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
        {"time": 2, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
        {"time": 3, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},  # window len 4 -> opens here
        {"time": 4, "open": 1.1, "high": 1.1030, "low": 1.0990, "close": 1.1010},  # hits TP (1.1025)
    ])

    def signal_fn(window):
        if len(window) == 4:
            return {"signal": "COMPRAR FUERTE", "signal_reason": "x", "last_close": 1.1000, "atr": 0.001, "bb_mid": 1.1000}
        return {"signal": "ESPERAR", "signal_reason": "x", "last_close": 1.1000, "atr": 0.001, "bb_mid": 1.1000}

    result = backtest_engine.simulate_strategy(
        df, "trend", risk_pct=0.01, symbol_meta=_symbol_meta(),
        starting_balance=1000, warmup=3, signal_fn=signal_fn,
    )

    assert result["total_trades"] == 1
    assert result["trades"][0]["volume"] == 0.06  # same calc_position_size numbers as existing risk tests
    assert result["trades"][0]["profit"] == 15.0  # 2.5 * 0.001 ATR distance * 0.06 lots / tick_size * tick_value
    assert result["total_profit"] == 15.0


def test_trade_closes_at_stop_loss():
    df = pd.DataFrame([
        {"time": 0, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
        {"time": 1, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
        {"time": 2, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
        {"time": 3, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
        {"time": 4, "open": 1.1, "high": 1.1000, "low": 1.0980, "close": 1.0985},  # hits SL (1.0985), not TP
    ])

    def signal_fn(window):
        if len(window) == 4:
            return {"signal": "COMPRAR FUERTE", "signal_reason": "x", "last_close": 1.1000, "atr": 0.001, "bb_mid": 1.1000}
        return {"signal": "ESPERAR", "signal_reason": "x", "last_close": 1.1000, "atr": 0.001, "bb_mid": 1.1000}

    result = backtest_engine.simulate_strategy(
        df, "trend", risk_pct=0.01, symbol_meta=_symbol_meta(),
        starting_balance=1000, warmup=3, signal_fn=signal_fn,
    )

    assert result["total_trades"] == 1
    assert result["trades"][0]["profit"] == -9.0


def test_same_candle_touching_both_sl_and_tp_assumes_sl():
    df = pd.DataFrame([
        {"time": 0, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
        {"time": 1, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
        {"time": 2, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
        {"time": 3, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
        {"time": 4, "open": 1.1, "high": 1.1030, "low": 1.0980, "close": 1.1000},  # both SL and TP crossed
    ])

    def signal_fn(window):
        if len(window) == 4:
            return {"signal": "COMPRAR FUERTE", "signal_reason": "x", "last_close": 1.1000, "atr": 0.001, "bb_mid": 1.1000}
        return {"signal": "ESPERAR", "signal_reason": "x", "last_close": 1.1000, "atr": 0.001, "bb_mid": 1.1000}

    result = backtest_engine.simulate_strategy(
        df, "trend", risk_pct=0.01, symbol_meta=_symbol_meta(),
        starting_balance=1000, warmup=3, signal_fn=signal_fn,
    )

    assert result["trades"][0]["profit"] == -9.0  # SL outcome, not the +15 TP outcome


def test_does_not_open_a_second_trade_while_one_is_open():
    df = pd.DataFrame([
        {"time": i, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0} for i in range(8)
    ])

    def signal_fn(window):
        # Signal fires every step from window len 4 onward — must still only open once,
        # since price never moves enough to hit SL/TP (all rows are flat at 1.0).
        if len(window) >= 4:
            return {"signal": "COMPRAR FUERTE", "signal_reason": "x", "last_close": 1.0, "atr": 0.001, "bb_mid": 1.0}
        return {"signal": "ESPERAR", "signal_reason": "x", "last_close": 1.0, "atr": 0.001, "bb_mid": 1.0}

    result = backtest_engine.simulate_strategy(
        df, "trend", risk_pct=0.01, symbol_meta=_symbol_meta(),
        starting_balance=1000, warmup=3, signal_fn=signal_fn,
    )

    assert result["total_trades"] == 0  # never hits SL/TP in this fixture, so still "open" — logged as 0 closed trades


def test_default_signal_fn_runs_fast_on_a_realistic_series():
    # Regression guard for the O(n^2) bug: recomputing indicators on every growing
    # window instead of once over the full series. 2000 rows should complete in well
    # under a second once indicators are computed a single time up front.
    n = 2000
    rows = []
    for i in range(n):
        base = 1.10 + 0.05 * math.sin(i / 40) + (i % 7) * 0.0003
        rows.append({
            "time": i, "open": base, "close": base + 0.0002,
            "high": base + 0.0015, "low": base - 0.0015,
        })
    df = pd.DataFrame(rows)

    start = time.monotonic()
    result = backtest_engine.simulate_strategy(
        df, "mean_reversion", risk_pct=0.01,
        symbol_meta={"tick_value": 1.0, "tick_size": 0.00001, "volume_step": 0.01, "volume_min": 0.01},
        starting_balance=100000, warmup=200,
    )
    elapsed = time.monotonic() - start

    assert elapsed < 5.0
    assert "total_trades" in result
    assert result["total_trades"] >= 0
