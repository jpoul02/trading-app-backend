import bot_db


def _run_fields(**overrides):
    base = {
        "symbol": "EURUSD",
        "timeframe": "M15",
        "strategy": "mean_reversion",
        "date_from": "2025-06-01",
        "date_to": "2026-08-01",
        "risk_pct": 0.01,
        "starting_balance": 100000,
        "total_trades": 418,
        "win_rate_pct": 31.1,
        "total_profit": -12742.87,
        "max_drawdown_pct": 26.58,
        "profit_factor": 0.9508,
        "full_result_json": '{"trades": [], "equity_curve": []}',
    }
    base.update(overrides)
    return base


def test_save_and_list_backtest_runs(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)

    run_id = bot_db.save_backtest_run(db_path, **_run_fields())

    runs = bot_db.list_backtest_runs(db_path)
    assert len(runs) == 1
    assert runs[0]["id"] == run_id
    assert runs[0]["symbol"] == "EURUSD"
    assert runs[0]["strategy"] == "mean_reversion"
    assert runs[0]["total_profit"] == -12742.87
    assert runs[0]["profit_factor"] == 0.9508


def test_list_backtest_runs_excludes_full_result_json(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)
    bot_db.save_backtest_run(db_path, **_run_fields())

    runs = bot_db.list_backtest_runs(db_path)

    assert "full_result_json" not in runs[0]


def test_list_backtest_runs_most_recent_first(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)
    id1 = bot_db.save_backtest_run(db_path, **_run_fields(symbol="EURUSD"))
    id2 = bot_db.save_backtest_run(db_path, **_run_fields(symbol="GBPUSD"))

    runs = bot_db.list_backtest_runs(db_path)

    assert runs[0]["id"] == id2
    assert runs[1]["id"] == id1


def test_get_backtest_run_includes_full_result_json(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)
    run_id = bot_db.save_backtest_run(db_path, **_run_fields())

    run = bot_db.get_backtest_run(db_path, run_id)

    assert run["id"] == run_id
    assert run["full_result_json"] == '{"trades": [], "equity_curve": []}'


def test_get_backtest_run_returns_none_when_missing(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)

    assert bot_db.get_backtest_run(db_path, 999) is None
