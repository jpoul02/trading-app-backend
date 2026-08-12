import bot_db


def test_init_db_creates_default_state(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)

    state = bot_db.get_state(db_path)

    assert state["running"] == 1
    assert state["kill_switch_tripped"] == 0
    assert state["disabled_reason"] is None
    assert state["symbols"] == "EURUSD,GBPUSD,USDJPY,USDCHF"
    assert state["timeframe"] == "M15"
    assert state["risk_pct"] == 0.01
    assert state["daily_loss_limit_pct"] == 0.03
    assert state["max_drawdown_pct"] == 0.10
    assert state["magic"] == 424001


def test_init_db_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)
    bot_db.update_state(db_path, running=0)

    bot_db.init_db(db_path)  # calling init again must not reset existing state
    state = bot_db.get_state(db_path)

    assert state["running"] == 0


def test_update_state_changes_only_given_fields(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)

    bot_db.update_state(db_path, kill_switch_tripped=1, disabled_reason="daily_loss_limit")
    state = bot_db.get_state(db_path)

    assert state["kill_switch_tripped"] == 1
    assert state["disabled_reason"] == "daily_loss_limit"
    assert state["running"] == 1  # untouched field keeps its value


def test_log_trade_and_list_trades(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)

    trade_id = bot_db.log_trade(
        db_path,
        ticket=123,
        symbol="EURUSD",
        action="buy",
        volume=0.1,
        price=1.1000,
        sl=1.0950,
        tp=1.1100,
        signal_reason="RSI sobrevendido",
        status="open",
    )

    trades = bot_db.list_trades(db_path)

    assert len(trades) == 1
    assert trades[0]["id"] == trade_id
    assert trades[0]["symbol"] == "EURUSD"
    assert trades[0]["status"] == "open"
    assert trades[0]["profit"] is None
    assert trades[0]["closed_at"] is None


def test_update_trade_closes_it(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)
    trade_id = bot_db.log_trade(
        db_path, ticket=123, symbol="EURUSD", action="buy", volume=0.1,
        price=1.1000, sl=1.0950, tp=1.1100, signal_reason="x", status="open",
    )

    bot_db.update_trade(db_path, trade_id, status="closed", profit=12.5, closed_at="2026-08-11T10:00:00")

    trades = bot_db.list_trades(db_path)
    assert trades[0]["status"] == "closed"
    assert trades[0]["profit"] == 12.5
    assert trades[0]["closed_at"] == "2026-08-11T10:00:00"


def test_list_trades_respects_limit_and_order(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)
    for i in range(5):
        bot_db.log_trade(
            db_path, ticket=i, symbol="EURUSD", action="buy", volume=0.1,
            price=1.1, sl=1.09, tp=1.11, signal_reason="x", status="open",
        )

    trades = bot_db.list_trades(db_path, limit=2)

    assert len(trades) == 2
    assert trades[0]["ticket"] == 4  # most recent first
    assert trades[1]["ticket"] == 3


def test_list_trades_respects_offset(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)
    for i in range(5):
        bot_db.log_trade(
            db_path, ticket=i, symbol="EURUSD", action="buy", volume=0.1,
            price=1.1, sl=1.09, tp=1.11, signal_reason="x", status="open",
        )

    page2 = bot_db.list_trades(db_path, limit=2, offset=2)

    assert len(page2) == 2
    assert page2[0]["ticket"] == 2
    assert page2[1]["ticket"] == 1


def test_count_trades(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)
    assert bot_db.count_trades(db_path) == 0
    for i in range(3):
        bot_db.log_trade(
            db_path, ticket=i, symbol="EURUSD", action="buy", volume=0.1,
            price=1.1, sl=1.09, tp=1.11, signal_reason="x", status="open",
        )
    assert bot_db.count_trades(db_path) == 3


def test_init_db_migration_adds_mode_and_obsidian_path_to_existing_table(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)  # first run — creates table without assuming new columns exist twice
    bot_db.init_db(db_path)  # second run on an already-migrated table must not error

    trade_id = bot_db.log_trade(
        db_path, ticket=1, symbol="EURUSD", action="buy", volume=0.1,
        price=1.1, sl=1.09, tp=1.11, signal_reason="x", status="open",
        mode="trend", obsidian_path="Trades/EURUSD-1.md",
    )
    trades = bot_db.list_trades(db_path)
    assert trades[0]["id"] == trade_id
    assert trades[0]["mode"] == "trend"
    assert trades[0]["obsidian_path"] == "Trades/EURUSD-1.md"


def test_get_open_trades_returns_only_open_status(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)
    open_id = bot_db.log_trade(
        db_path, ticket=1, symbol="EURUSD", action="buy", volume=0.1,
        price=1.1, sl=1.09, tp=1.11, signal_reason="x", status="open", mode="trend",
    )
    bot_db.log_trade(
        db_path, ticket=2, symbol="GBPUSD", action="sell", volume=0.1,
        price=1.2, sl=1.21, tp=1.19, signal_reason="x", status="closed", mode="trend",
    )

    open_trades = bot_db.get_open_trades(db_path)

    assert len(open_trades) == 1
    assert open_trades[0]["id"] == open_id
