import pandas as pd
import bot_engine


def _strong_buy_df():
    rows = [
        {"close": 1.0990, "rsi": 50.0, "macd_hist": 0.0, "atr": 0.0010},
        {"close": 1.0995, "rsi": 50.0, "macd_hist": 0.0, "atr": 0.0010},
        {"close": 1.1000, "rsi": 25.0, "macd_hist": 0.0005, "atr": 0.0010},
    ]
    return pd.DataFrame(rows)


def _wait_df():
    rows = [
        {"close": 1.0990, "rsi": 50.0, "macd_hist": 0.0, "atr": 0.0010},
        {"close": 1.1000, "rsi": 50.0, "macd_hist": 0.0, "atr": 0.0010},
    ]
    return pd.DataFrame(rows)


def _state(running=1, tripped=0, reason=None, risk_pct=0.01):
    return {"running": running, "kill_switch_tripped": tripped, "disabled_reason": reason, "risk_pct": risk_pct}


def _symbol_meta():
    return {"tick_value": 1.0, "tick_size": 0.00001, "volume_step": 0.01, "volume_min": 0.01}


def test_no_action_when_bot_not_running():
    called = []
    result = bot_engine.process_symbol_tick(
        "EURUSD", _strong_buy_df(), _state(running=0), [], 1000, _symbol_meta(),
        place_order_fn=lambda **kw: called.append(kw),
    )
    assert result["action"] == "none"
    assert result["reason"] == "bot_stopped"
    assert called == []


def test_no_action_when_kill_switch_tripped():
    result = bot_engine.process_symbol_tick(
        "EURUSD", _strong_buy_df(), _state(tripped=1, reason="daily_loss_limit"), [], 1000, _symbol_meta(),
        place_order_fn=lambda **kw: {"success": True},
    )
    assert result["action"] == "none"
    assert result["reason"] == "daily_loss_limit"


def test_no_action_when_position_already_open():
    result = bot_engine.process_symbol_tick(
        "EURUSD", _strong_buy_df(), _state(), [{"ticket": 1}], 1000, _symbol_meta(),
        place_order_fn=lambda **kw: {"success": True},
    )
    assert result["action"] == "none"
    assert result["reason"] == "position_already_open"


def test_no_action_when_signal_not_strong():
    result = bot_engine.process_symbol_tick(
        "EURUSD", _wait_df(), _state(), [], 1000, _symbol_meta(),
        place_order_fn=lambda **kw: {"success": True},
    )
    assert result["action"] == "none"
    assert result["reason"] == "no_strong_signal"


def test_opens_buy_position_on_strong_buy_signal():
    captured = {}

    def fake_place_order(**kw):
        captured.update(kw)
        return {"success": True, "order": 999, "volume": kw["volume"], "price": 1.1000, "comment": "ok"}

    result = bot_engine.process_symbol_tick(
        "EURUSD", _strong_buy_df(), _state(), [], 1000, _symbol_meta(),
        place_order_fn=fake_place_order,
    )

    assert result["action"] == "opened"
    assert result["ticket"] == 999
    assert captured["symbol"] == "EURUSD"
    assert captured["action"] == "buy"
    assert captured["volume"] > 0
    assert captured["sl"] < 1.1000 < captured["tp"]


def test_opened_result_reports_actual_filled_volume_not_requested():
    # place_order can scale the requested volume down (margin guard) — the
    # reported/logged volume must reflect what actually got filled, not what
    # was asked for, or the trades table shows a size that never existed.
    def fake_place_order(**kw):
        return {"success": True, "order": 999, "volume": 5.0, "price": 1.1000, "comment": "ok"}

    result = bot_engine.process_symbol_tick(
        "EURUSD", _strong_buy_df(), _state(), [], 1000, _symbol_meta(),
        place_order_fn=fake_place_order,
    )

    assert result["volume"] == 5.0


def test_reports_rejected_when_place_order_fails():
    result = bot_engine.process_symbol_tick(
        "EURUSD", _strong_buy_df(), _state(), [], 1000, _symbol_meta(),
        place_order_fn=lambda **kw: {"success": False, "error": "Error 10019: no money"},
    )
    assert result["action"] == "rejected"
    assert "no money" in result["reason"]
