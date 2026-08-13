import bot_db


def _run_fields(**overrides):
    base = {
        "mode": "trend",
        "n_trades": 340,
        "profit_factor_filtered": 1.42,
        "profit_factor_unfiltered": 1.08,
        "enabled": 1,
    }
    base.update(overrides)
    return base


def test_save_and_get_latest_ml_model(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)

    run_id = bot_db.save_ml_model_run(db_path, **_run_fields())

    model = bot_db.get_latest_ml_model(db_path, mode="trend")
    assert model["id"] == run_id
    assert model["n_trades"] == 340
    assert model["profit_factor_filtered"] == 1.42
    assert model["enabled"] == 1
    assert model["trained_at"] is not None


def test_get_latest_ml_model_returns_none_when_no_runs(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)

    assert bot_db.get_latest_ml_model(db_path, mode="trend") is None


def test_get_latest_ml_model_returns_most_recent(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)
    bot_db.save_ml_model_run(db_path, **_run_fields(n_trades=100))
    second_id = bot_db.save_ml_model_run(db_path, **_run_fields(n_trades=200))

    model = bot_db.get_latest_ml_model(db_path, mode="trend")

    assert model["id"] == second_id
    assert model["n_trades"] == 200


def test_get_latest_ml_model_scoped_by_mode(tmp_path):
    db_path = str(tmp_path / "test.db")
    bot_db.init_db(db_path)
    bot_db.save_ml_model_run(db_path, **_run_fields(mode="trend"))

    assert bot_db.get_latest_ml_model(db_path, mode="fast") is None
