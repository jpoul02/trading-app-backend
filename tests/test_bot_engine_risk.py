import bot_engine


def test_calc_sl_tp_for_buy():
    sl, tp = bot_engine.calc_sl_tp(entry_price=1.1000, atr=0.0010, direction="buy")
    assert round(sl, 5) == 1.0985  # 1.1000 - 1.5*0.0010
    assert round(tp, 5) == 1.1025  # 1.1000 + 2.5*0.0010


def test_calc_sl_tp_for_sell():
    sl, tp = bot_engine.calc_sl_tp(entry_price=1.1000, atr=0.0010, direction="sell")
    assert round(sl, 5) == 1.1015
    assert round(tp, 5) == 1.0975


def test_calc_position_size_rounds_to_volume_step():
    # risk = 1000 * 0.01 = 10; loss per lot = (sl_distance/tick_size)*tick_value
    # sl_distance=0.0015, tick_size=0.00001, tick_value=1.0 -> loss per lot = 150
    # raw volume = 10/150 = 0.0667 -> rounds down to nearest 0.01 step = 0.06
    volume = bot_engine.calc_position_size(
        balance=1000, risk_pct=0.01, sl_distance=0.0015,
        tick_value=1.0, tick_size=0.00001, volume_step=0.01, volume_min=0.01,
    )
    assert volume == 0.06


def test_calc_position_size_never_below_volume_min():
    volume = bot_engine.calc_position_size(
        balance=100, risk_pct=0.01, sl_distance=0.01,
        tick_value=1.0, tick_size=0.00001, volume_step=0.01, volume_min=0.01,
    )
    assert volume == 0.01


def test_check_kill_switch_sets_account_start_balance_on_first_call():
    state = {
        "account_start_balance": None, "day_start_balance": None,
        "day_start_date": None, "kill_switch_tripped": 0, "disabled_reason": None,
        "daily_loss_limit_pct": 0.03, "max_drawdown_pct": 0.10,
    }

    changes = bot_engine.check_kill_switch(state, balance=1000, equity=1000, today="2026-08-11")

    assert changes["account_start_balance"] == 1000
    assert changes["day_start_balance"] == 1000
    assert changes["day_start_date"] == "2026-08-11"
    assert "kill_switch_tripped" not in changes


def test_check_kill_switch_resets_day_start_on_new_day():
    state = {
        "account_start_balance": 1000, "day_start_balance": 950,
        "day_start_date": "2026-08-10", "kill_switch_tripped": 0, "disabled_reason": None,
        "daily_loss_limit_pct": 0.03, "max_drawdown_pct": 0.10,
    }

    changes = bot_engine.check_kill_switch(state, balance=980, equity=980, today="2026-08-11")

    assert changes["day_start_date"] == "2026-08-11"
    assert changes["day_start_balance"] == 980
    assert "account_start_balance" not in changes  # unchanged, not re-reported


def test_check_kill_switch_trips_on_daily_loss_limit():
    state = {
        "account_start_balance": 1000, "day_start_balance": 1000,
        "day_start_date": "2026-08-11", "kill_switch_tripped": 0, "disabled_reason": None,
        "daily_loss_limit_pct": 0.03, "max_drawdown_pct": 0.10,
    }

    changes = bot_engine.check_kill_switch(state, balance=965, equity=965, today="2026-08-11")

    assert changes["kill_switch_tripped"] == 1
    assert changes["disabled_reason"] == "daily_loss_limit"


def test_check_kill_switch_trips_on_max_drawdown():
    # Cumulative drawdown from account_start crosses 10%, but today's own move
    # (from day_start_balance) stays under the 3% daily limit — isolates the
    # max_drawdown branch from daily_loss_limit.
    state = {
        "account_start_balance": 1000, "day_start_balance": 915,
        "day_start_date": "2026-08-11", "kill_switch_tripped": 0, "disabled_reason": None,
        "daily_loss_limit_pct": 0.03, "max_drawdown_pct": 0.10,
    }

    changes = bot_engine.check_kill_switch(state, balance=900, equity=900, today="2026-08-11")

    assert changes["kill_switch_tripped"] == 1
    assert changes["disabled_reason"] == "max_drawdown"


def test_check_kill_switch_does_not_untrip_automatically():
    state = {
        "account_start_balance": 1000, "day_start_balance": 1000,
        "day_start_date": "2026-08-11", "kill_switch_tripped": 1, "disabled_reason": "daily_loss_limit",
        "daily_loss_limit_pct": 0.03, "max_drawdown_pct": 0.10,
    }

    changes = bot_engine.check_kill_switch(state, balance=999, equity=999, today="2026-08-11")

    assert "kill_switch_tripped" not in changes  # stays tripped; only reset-kill-switch endpoint clears it
