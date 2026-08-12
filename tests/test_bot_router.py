import pytest
from fastapi.testclient import TestClient

import bot_db


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
    trades = resp.json()
    assert len(trades) == 1
    assert trades[0]["symbol"] == "EURUSD"


def test_get_and_update_config(client):
    resp = client.get("/api/bot/config")
    assert resp.status_code == 200
    assert resp.json()["risk_pct"] == 0.01

    resp = client.put("/api/bot/config", json={"risk_pct": 0.02, "symbols": ["EURUSD", "GBPUSD"]})
    assert resp.status_code == 200

    config = client.get("/api/bot/config").json()
    assert config["risk_pct"] == 0.02
    assert config["symbols"] == ["EURUSD", "GBPUSD"]
