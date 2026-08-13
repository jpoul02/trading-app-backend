import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import bot_db
import routers.ml as ml_router


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_ml_router.db")
    monkeypatch.setattr(bot_db, "DB_PATH", db_path)
    monkeypatch.setattr(ml_router, "DB_PATH", db_path)
    bot_db.init_db(db_path)

    app = FastAPI()
    app.include_router(ml_router.router, prefix="/api/ml")
    return TestClient(app), db_path


def test_train_calls_pipeline_for_trend_and_fast(client, monkeypatch):
    test_client, _ = client
    calls = []

    def fake_train(mode, symbols, timeframe, risk_pct, min_confidence):
        calls.append(mode)
        return {"trained": True, "n_trades": 100, "profit_factor_filtered": 1.4, "profit_factor_unfiltered": 1.1}

    monkeypatch.setattr(ml_router.ml_entry_filter, "train_entry_filter_model", fake_train)

    resp = test_client.post("/api/ml/train")

    assert resp.status_code == 200
    assert set(calls) == {"trend", "fast"}
    assert resp.json()["trend"]["trained"] is True


def test_get_models_returns_none_when_never_trained(client):
    test_client, _ = client

    resp = test_client.get("/api/ml/models")

    assert resp.status_code == 200
    assert resp.json() == {"trend": None, "fast": None}


def test_get_models_returns_latest_saved_run(client):
    test_client, db_path = client
    bot_db.save_ml_model_run(
        db_path, mode="trend", n_trades=50,
        profit_factor_filtered=1.3, profit_factor_unfiltered=1.0, enabled=1,
    )

    resp = test_client.get("/api/ml/models")

    assert resp.json()["trend"]["n_trades"] == 50
    assert resp.json()["fast"] is None
