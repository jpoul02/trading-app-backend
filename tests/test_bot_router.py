import pytest
from fastapi.testclient import TestClient

import bot_db
import routers.bot as bot_router


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_bot.db")
    monkeypatch.setattr(bot_db, "DB_PATH", db_path)
    bot_db.init_db(db_path)

    import routers.bot as bot_router
    monkeypatch.setattr(bot_router, "DB_PATH", db_path)

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(bot_router.router, prefix="/api/bot")
    return TestClient(app)


def test_status_returns_default_state(client):
    resp = client.get("/api/bot/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["running"] is True
    assert body["kill_switch_tripped"] is False
    assert body["symbols"] == ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]


def test_stop_and_start(client):
    resp = client.post("/api/bot/stop")
    assert resp.status_code == 200
    assert client.get("/api/bot/status").json()["running"] is False

    resp = client.post("/api/bot/start")
    assert resp.status_code == 200
    assert client.get("/api/bot/status").json()["running"] is True


def test_reset_kill_switch(client):
    import routers.bot as bot_router
    bot_db.update_state(bot_router.DB_PATH, kill_switch_tripped=1, disabled_reason="daily_loss_limit")

    resp = client.post("/api/bot/reset-kill-switch")

    assert resp.status_code == 200
    status = client.get("/api/bot/status").json()
    assert status["kill_switch_tripped"] is False
    assert status["disabled_reason"] is None


def test_trades_list(client):
    import routers.bot as bot_router
    bot_db.log_trade(
        bot_router.DB_PATH, ticket=1, symbol="EURUSD", action="buy", volume=0.1,
        price=1.1, sl=1.09, tp=1.11, signal_reason="test", status="open",
    )

    resp = client.get("/api/bot/trades")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["trades"]) == 1
    assert body["trades"][0]["symbol"] == "EURUSD"


def test_trades_list_pagination(client):
    import routers.bot as bot_router
    for i in range(5):
        bot_db.log_trade(
            bot_router.DB_PATH, ticket=i, symbol="EURUSD", action="buy", volume=0.1,
            price=1.1, sl=1.09, tp=1.11, signal_reason="test", status="open",
        )

    resp = client.get("/api/bot/trades", params={"limit": 2, "offset": 2})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert len(body["trades"]) == 2
    assert body["trades"][0]["ticket"] == 2


def test_get_and_update_config(client):
    resp = client.get("/api/bot/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_pct"] == 0.01
    assert body["trend_symbols"] == ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
    assert body["fast_timeframe"] == "M5"
    assert body["fast_enabled"] is False

    resp = client.put("/api/bot/config", json={"risk_pct": 0.02, "trend_symbols": ["EURUSD", "GBPUSD"]})
    assert resp.status_code == 200

    config = client.get("/api/bot/config").json()
    assert config["risk_pct"] == 0.02
    assert config["trend_symbols"] == ["EURUSD", "GBPUSD"]


def test_check_mode_backtest_gate_passes_when_all_symbols_profitable():
    def fake_run(symbol, timeframe, date_from, date_to, strategy, risk_pct, starting_balance):
        return {"profit_factor": 1.3}

    gate = bot_router.check_mode_backtest_gate("trend", ["EURUSD", "GBPUSD"], "M15", 0.01, run_backtest_fn=fake_run)

    assert gate["passed"] is True
    assert gate["failures"] == []


def test_check_mode_backtest_gate_fails_when_one_symbol_unprofitable():
    def fake_run(symbol, timeframe, date_from, date_to, strategy, risk_pct, starting_balance):
        return {"profit_factor": 0.8 if symbol == "GBPUSD" else 1.3}

    gate = bot_router.check_mode_backtest_gate("trend", ["EURUSD", "GBPUSD"], "M15", 0.01, run_backtest_fn=fake_run)

    assert gate["passed"] is False
    assert gate["failures"] == [{"symbol": "GBPUSD", "profit_factor": 0.8, "error": None}]


def test_check_mode_backtest_gate_fails_closed_on_backtest_error():
    def fake_run(symbol, timeframe, date_from, date_to, strategy, risk_pct, starting_balance):
        return {"error": "No hay suficiente historial"}

    gate = bot_router.check_mode_backtest_gate("fast", ["EURUSD"], "M5", 0.01, run_backtest_fn=fake_run)

    assert gate["passed"] is False


def test_check_mode_backtest_gate_fails_closed_with_no_symbols():
    gate = bot_router.check_mode_backtest_gate("fast", [], "M5", 0.01, run_backtest_fn=lambda *a: {"profit_factor": 2.0})
    assert gate["passed"] is False


def test_update_config_rejects_enable_when_gate_fails(client, monkeypatch):
    monkeypatch.setattr(
        bot_router, "check_mode_backtest_gate",
        lambda mode, symbols, timeframe, risk_pct, run_backtest_fn=None: {
            "passed": False, "failures": [{"symbol": "EURUSD", "profit_factor": 0.7, "error": None}],
        },
    )

    resp = client.put("/api/bot/config", json={"fast_enabled": True})

    assert resp.status_code == 400
    assert resp.json()["detail"]["mode"] == "fast"
    config = client.get("/api/bot/config").json()
    assert config["fast_enabled"] is False  # rejected — not persisted


def test_update_config_accepts_enable_when_gate_passes(client, monkeypatch):
    monkeypatch.setattr(
        bot_router, "check_mode_backtest_gate",
        lambda mode, symbols, timeframe, risk_pct, run_backtest_fn=None: {"passed": True, "failures": []},
    )

    resp = client.put("/api/bot/config", json={"fast_enabled": True})

    assert resp.status_code == 200
    assert resp.json()["fast_enabled"] is True


def test_update_config_disable_does_not_trigger_gate(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        bot_router, "check_mode_backtest_gate",
        lambda *a, **kw: calls.append(1) or {"passed": True, "failures": []},
    )

    resp = client.put("/api/bot/config", json={"fast_enabled": False})

    assert resp.status_code == 200
    assert calls == []
