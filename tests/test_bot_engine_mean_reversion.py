import pandas as pd
import bot_engine


def _df_with_last_row(close, rsi, stoch_k, bb_lower=1.0980, bb_upper=1.1020, bb_mid=1.1000, atr=0.0010):
    rows = [
        {"close": 1.0995, "rsi": 50.0, "stoch_k": 50.0, "bb_lower": bb_lower, "bb_upper": bb_upper, "bb_mid": bb_mid, "atr": atr},
        {"close": 1.0998, "rsi": 50.0, "stoch_k": 50.0, "bb_lower": bb_lower, "bb_upper": bb_upper, "bb_mid": bb_mid, "atr": atr},
        {"close": close, "rsi": rsi, "stoch_k": stoch_k, "bb_lower": bb_lower, "bb_upper": bb_upper, "bb_mid": bb_mid, "atr": atr},
    ]
    return pd.DataFrame(rows)


def test_strong_buy_when_touches_lower_band_oversold():
    df = _df_with_last_row(close=1.0975, rsi=25.0, stoch_k=15.0)
    result = bot_engine.compute_mean_reversion_signal(df)
    assert result["signal"] == "COMPRAR FUERTE"
    assert result["bb_mid"] == 1.1000


def test_strong_sell_when_touches_upper_band_overbought():
    df = _df_with_last_row(close=1.1025, rsi=75.0, stoch_k=85.0)
    result = bot_engine.compute_mean_reversion_signal(df)
    assert result["signal"] == "VENDER FUERTE"


def test_no_signal_when_only_price_touches_band():
    # Band touched but RSI/stoch not confirming — no signal, unlike trend mode there's no intermediate state
    df = _df_with_last_row(close=1.0975, rsi=50.0, stoch_k=50.0)
    result = bot_engine.compute_mean_reversion_signal(df)
    assert result["signal"] == "ESPERAR"


def test_no_signal_when_price_inside_bands():
    df = _df_with_last_row(close=1.1000, rsi=20.0, stoch_k=10.0)
    result = bot_engine.compute_mean_reversion_signal(df)
    assert result["signal"] == "ESPERAR"


def _state(running=1, tripped=0, reason=None, risk_pct=0.01, magic=424001):
    return {"running": running, "kill_switch_tripped": tripped, "disabled_reason": reason, "risk_pct": risk_pct, "magic": magic}


def _symbol_meta():
    return {"tick_value": 1.0, "tick_size": 0.00001, "volume_step": 0.01, "volume_min": 0.01}


def test_orchestration_opens_buy_with_tp_at_bb_mid():
    df = _df_with_last_row(close=1.0975, rsi=25.0, stoch_k=15.0, bb_mid=1.1000)
    captured = {}

    def fake_place_order(**kw):
        captured.update(kw)
        return {"success": True, "order": 555, "volume": kw["volume"], "price": 1.0975, "comment": "ok"}

    result = bot_engine.process_symbol_tick_mean_reversion(
        "EURUSD", df, _state(), [], 1000, _symbol_meta(), place_order_fn=fake_place_order,
    )

    assert result["action"] == "opened"
    assert captured["magic"] == 424002  # trend magic + 1
    assert captured["tp"] == 1.1000
    assert captured["sl"] < 1.0975


def test_opened_result_reports_actual_filled_volume_not_requested():
    df = _df_with_last_row(close=1.0975, rsi=25.0, stoch_k=15.0, bb_mid=1.1000)

    def fake_place_order(**kw):
        return {"success": True, "order": 555, "volume": 3.0, "price": 1.0975, "comment": "ok"}

    result = bot_engine.process_symbol_tick_mean_reversion(
        "EURUSD", df, _state(), [], 1000, _symbol_meta(), place_order_fn=fake_place_order,
    )

    assert result["volume"] == 3.0


def test_orchestration_no_action_when_position_already_open():
    df = _df_with_last_row(close=1.0975, rsi=25.0, stoch_k=15.0)
    result = bot_engine.process_symbol_tick_mean_reversion(
        "EURUSD", df, _state(), [{"ticket": 1}], 1000, _symbol_meta(),
        place_order_fn=lambda **kw: {"success": True},
    )
    assert result["action"] == "none"
    assert result["reason"] == "position_already_open"


def test_orchestration_no_action_when_bot_stopped():
    df = _df_with_last_row(close=1.0975, rsi=25.0, stoch_k=15.0)
    called = []
    result = bot_engine.process_symbol_tick_mean_reversion(
        "EURUSD", df, _state(running=0), [], 1000, _symbol_meta(),
        place_order_fn=lambda **kw: called.append(kw),
    )
    assert result["action"] == "none"
    assert result["reason"] == "bot_stopped"
    assert called == []
