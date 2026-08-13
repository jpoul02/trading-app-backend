import pandas as pd
import bot_engine


def _df(rsi, macd_hist=0.0, close=1.1000, atr=0.0010):
    rows = [
        {"close": 1.0990, "rsi": 50.0, "macd_hist": 0.0, "atr": atr},
        {"close": 1.0995, "rsi": 50.0, "macd_hist": 0.0, "atr": atr},
        {"close": close, "rsi": rsi, "macd_hist": macd_hist, "atr": atr},
    ]
    return pd.DataFrame(rows)


def _state(running=1, tripped=0, reason=None, risk_pct=0.01, magic=424001):
    return {"running": running, "kill_switch_tripped": tripped, "disabled_reason": reason, "risk_pct": risk_pct, "magic": magic}


def _symbol_meta():
    return {"tick_value": 1.0, "tick_size": 0.00001, "volume_step": 0.01, "volume_min": 0.01}


def test_opens_buy_on_weak_bullish_trend_signal():
    # rsi=40 -> "TENDENCIA ALCISTA" in compute_signal, not a FUERTE signal —
    # trend mode ignores this, fast mode must still open.
    df = _df(rsi=40.0)
    captured = {}

    def fake_place_order(**kw):
        captured.update(kw)
        return {"success": True, "order": 777, "volume": kw["volume"], "price": 1.1000, "comment": "ok"}

    result = bot_engine.process_symbol_tick_fast(
        "EURUSD", df, _state(), [], 1000, _symbol_meta(), place_order_fn=fake_place_order,
    )

    assert result["action"] == "opened"
    assert captured["action"] == "buy"
    assert captured["magic"] == 424003  # trend magic + 2


def test_opens_sell_on_weak_bearish_trend_signal():
    df = _df(rsi=60.0)  # -> "TENDENCIA BAJISTA"
    captured = {}

    def fake_place_order(**kw):
        captured.update(kw)
        return {"success": True, "order": 778, "volume": kw["volume"], "price": 1.1000, "comment": "ok"}

    result = bot_engine.process_symbol_tick_fast(
        "EURUSD", df, _state(), [], 1000, _symbol_meta(), place_order_fn=fake_place_order,
    )

    assert result["action"] == "opened"
    assert captured["action"] == "sell"


def test_no_action_when_signal_is_wait():
    df = _df(rsi=50.0)  # -> "ESPERAR"
    result = bot_engine.process_symbol_tick_fast(
        "EURUSD", df, _state(), [], 1000, _symbol_meta(),
        place_order_fn=lambda **kw: {"success": True},
    )
    assert result["action"] == "none"
    assert result["reason"] == "no_strong_signal"


def test_still_opens_on_strong_fuerte_signal():
    df = _df(rsi=25.0, macd_hist=0.0005)  # -> "COMPRAR FUERTE"
    result = bot_engine.process_symbol_tick_fast(
        "EURUSD", df, _state(), [], 1000, _symbol_meta(),
        place_order_fn=lambda **kw: {"success": True, "order": 1, "volume": kw["volume"], "price": 1.1},
    )
    assert result["action"] == "opened"


def test_no_action_when_bot_stopped():
    df = _df(rsi=40.0)
    called = []
    result = bot_engine.process_symbol_tick_fast(
        "EURUSD", df, _state(running=0), [], 1000, _symbol_meta(),
        place_order_fn=lambda **kw: called.append(kw),
    )
    assert result["action"] == "none"
    assert result["reason"] == "bot_stopped"
    assert called == []


def test_no_action_when_position_already_open():
    df = _df(rsi=40.0)
    result = bot_engine.process_symbol_tick_fast(
        "EURUSD", df, _state(), [{"ticket": 1}], 1000, _symbol_meta(),
        place_order_fn=lambda **kw: {"success": True},
    )
    assert result["action"] == "none"
    assert result["reason"] == "position_already_open"
