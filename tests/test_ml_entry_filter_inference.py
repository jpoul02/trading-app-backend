import time

import joblib
from sklearn.linear_model import LogisticRegression

import ml_entry_filter


def test_load_entry_filter_model_cached_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_entry_filter, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(ml_entry_filter, "_model_cache", {})

    assert ml_entry_filter.load_entry_filter_model_cached("trend") is None


def test_load_entry_filter_model_cached_caches_between_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_entry_filter, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(ml_entry_filter, "_model_cache", {})

    model = LogisticRegression().fit([[0], [1]], [0, 1])
    joblib.dump(model, tmp_path / "entry_filter_trend.joblib")

    loaded_1 = ml_entry_filter.load_entry_filter_model_cached("trend")
    loaded_2 = ml_entry_filter.load_entry_filter_model_cached("trend")

    assert loaded_1 is not None
    assert loaded_1 is loaded_2  # same cached object, no reload


def test_load_entry_filter_model_cached_reloads_when_file_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_entry_filter, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(ml_entry_filter, "_model_cache", {})

    path = tmp_path / "entry_filter_trend.joblib"
    joblib.dump(LogisticRegression().fit([[0], [1]], [0, 1]), path)
    loaded_1 = ml_entry_filter.load_entry_filter_model_cached("trend")

    time.sleep(0.05)
    joblib.dump(LogisticRegression().fit([[0], [1]], [1, 0]), path)
    loaded_2 = ml_entry_filter.load_entry_filter_model_cached("trend")

    assert loaded_2 is not loaded_1


def test_predict_win_probability_returns_value_in_unit_range():
    model = LogisticRegression().fit([[0, 0, 0, 0, 0, 0], [1, 1, 1, 1, 1, 1]], [0, 1])
    features = {"rsi": 1, "macd_hist": 1, "atr_pct": 1, "price_vs_sma20": 1, "price_vs_sma50": 1, "hour_utc": 1}

    prob = ml_entry_filter.predict_win_probability(model, features)

    assert 0.0 <= prob <= 1.0


def test_should_veto_entry_below_threshold():
    assert ml_entry_filter.should_veto_entry(0.3, 0.5) is True


def test_should_veto_entry_at_or_above_threshold():
    assert ml_entry_filter.should_veto_entry(0.5, 0.5) is False
    assert ml_entry_filter.should_veto_entry(0.7, 0.5) is False
