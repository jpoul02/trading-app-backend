import bot_engine


def test_hard_stop_closes_on_adverse_move_even_before_atr_sl():
    pos = {"type": "buy", "open_price": 100.0, "current_price": 98.9, "sl": 90.0, "tp": 110.0}
    decision = bot_engine.manage_open_position(pos, atr=1.0, max_loss_pct=0.01, trailing_trigger_pct=0.1, trailing_distance_atr=1.0)
    assert decision == {"action": "close", "reason": "max_loss_pct"}


def test_no_trailing_when_progress_toward_tp_under_threshold():
    # entry=100, tp=110 -> only 5% of the way there, trigger is 30%.
    pos = {"type": "buy", "open_price": 100.0, "current_price": 100.5, "sl": 90.0, "tp": 110.0}
    decision = bot_engine.manage_open_position(pos, atr=1.0, max_loss_pct=0, trailing_trigger_pct=0.30, trailing_distance_atr=1.0)
    assert decision["action"] == "none"


def test_trailing_moves_sl_up_once_progress_to_tp_exceeds_trigger_buy():
    # entry=100, tp=110 -> current=102 is 20% of the way, above the 10% trigger.
    pos = {"type": "buy", "open_price": 100.0, "current_price": 102.0, "sl": 98.0, "tp": 110.0}
    decision = bot_engine.manage_open_position(pos, atr=1.0, max_loss_pct=0, trailing_trigger_pct=0.10, trailing_distance_atr=1.0)
    assert decision == {"action": "modify_sl", "sl": 101.0, "tp": 110.0}


def test_trailing_moves_sl_down_once_progress_to_tp_exceeds_trigger_sell():
    # entry=100, tp=90 -> current=98 is 20% of the way, above the 10% trigger.
    pos = {"type": "sell", "open_price": 100.0, "current_price": 98.0, "sl": 102.0, "tp": 90.0}
    decision = bot_engine.manage_open_position(pos, atr=1.0, max_loss_pct=0, trailing_trigger_pct=0.10, trailing_distance_atr=1.0)
    assert decision == {"action": "modify_sl", "sl": 99.0, "tp": 90.0}


def test_trailing_never_loosens_the_stop():
    # New computed SL (100.0) would be worse than the already-trailed SL (101.5).
    pos = {"type": "buy", "open_price": 100.0, "current_price": 101.0, "sl": 101.5, "tp": 110.0}
    decision = bot_engine.manage_open_position(pos, atr=1.0, max_loss_pct=0, trailing_trigger_pct=0.05, trailing_distance_atr=1.0)
    assert decision["action"] == "none"


def test_no_action_when_trailing_disabled():
    pos = {"type": "buy", "open_price": 100.0, "current_price": 105.0, "sl": 98.0, "tp": 110.0}
    decision = bot_engine.manage_open_position(pos, atr=1.0, max_loss_pct=0, trailing_trigger_pct=0, trailing_distance_atr=1.0)
    assert decision["action"] == "none"


def test_no_trailing_without_a_tp():
    pos = {"type": "buy", "open_price": 100.0, "current_price": 105.0, "sl": 98.0, "tp": None}
    decision = bot_engine.manage_open_position(pos, atr=1.0, max_loss_pct=0, trailing_trigger_pct=0.10, trailing_distance_atr=1.0)
    assert decision["action"] == "none"
