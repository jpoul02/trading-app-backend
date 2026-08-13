from datetime import datetime, timedelta, timezone
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression

import backtest_engine
import bot_db
import ml_features

MODEL_DIR = Path(__file__).parent / "ml_models"
GATE_LOOKBACK_DAYS = 730  # 2 years — default for higher timeframes

# Only M1/M5 are known to run into a broker/terminal history limit (confirmed:
# this demo server has no 2-year M5 history for EURUSD) — M15 and up already
# train fine on the full 2-year default, so they aren't shortened "just in case".
LOOKBACK_DAYS_BY_TIMEFRAME = {
    "M1": 30,
    "M5": 90,
}


def _lookback_days(timeframe: str) -> int:
    return LOOKBACK_DAYS_BY_TIMEFRAME.get(timeframe.upper(), GATE_LOOKBACK_DAYS)


def _profit_factor(trades: list[dict]) -> float | None:
    gross_profit = float(sum(t["profit"] for t in trades if t["profit"] > 0))
    gross_loss = abs(float(sum(t["profit"] for t in trades if t["profit"] <= 0)))
    if gross_loss <= 0:
        return None
    return round(gross_profit / gross_loss, 4)


def train_entry_filter_model(mode: str, symbols: list[str], timeframe: str,
                              risk_pct: float, min_confidence: float,
                              starting_balance: float = 100000,
                              max_loss_pct: float = 0, trailing_trigger_pct: float = 0,
                              trailing_distance_atr: float = 0,
                              fetch_candles_fn=None, symbol_info_fn=None,
                              simulate_fn=None, save_run_fn=None) -> dict:
    if not symbols:
        return {"trained": False, "error": "No hay símbolos configurados para este modo"}

    if fetch_candles_fn is None:
        fetch_candles_fn = backtest_engine.fetch_historical_candles
    if simulate_fn is None:
        simulate_fn = backtest_engine.simulate_strategy
    if save_run_fn is None:
        save_run_fn = bot_db.save_ml_model_run
    if symbol_info_fn is None:
        def symbol_info_fn(symbol):
            from routers import mt5 as mt5_router
            info = mt5_router.mt5.symbol_info(symbol.upper())
            if info is None:
                return None
            return {
                "tick_value": info.trade_tick_value, "tick_size": info.trade_tick_size,
                "volume_step": info.volume_step, "volume_min": info.volume_min,
            }

    date_to = datetime.now(timezone.utc)
    date_from = date_to - timedelta(days=_lookback_days(timeframe))

    all_trades = []
    for symbol in symbols:
        df = fetch_candles_fn(symbol, timeframe, date_from, date_to)
        if df is None or len(df) <= 200:
            continue
        symbol_meta = symbol_info_fn(symbol)
        if symbol_meta is None:
            continue
        result = simulate_fn(
            df, mode, risk_pct, symbol_meta, starting_balance, warmup=200,
            max_loss_pct=max_loss_pct, trailing_trigger_pct=trailing_trigger_pct,
            trailing_distance_atr=trailing_distance_atr,
        )
        all_trades.extend(t for t in result["trades"] if t.get("features"))

    if len(all_trades) < 30:
        return {"trained": False, "error": f"Muy pocos trades ({len(all_trades)}) para entrenar — mínimo 30", "n_trades": len(all_trades)}

    all_trades.sort(key=lambda t: t["opened_at"])
    split_idx = int(len(all_trades) * 0.8)
    train_trades = all_trades[:split_idx]
    test_trades = all_trades[split_idx:]

    if len(test_trades) < 5:
        return {"trained": False, "error": "Muy pocos trades en el tramo de test", "n_trades": len(all_trades)}

    y_train = [1 if t["profit"] > 0 else 0 for t in train_trades]
    if len(set(y_train)) < 2:
        return {"trained": False, "error": "Todos los trades de entrenamiento tienen el mismo resultado — no se puede entrenar", "n_trades": len(all_trades)}

    X_train = [ml_features.features_to_vector(t["features"]) for t in train_trades]
    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)

    X_test = [ml_features.features_to_vector(t["features"]) for t in test_trades]
    probs = model.predict_proba(X_test)[:, 1]

    unfiltered_pf = _profit_factor(test_trades)
    filtered_trades = [t for t, p in zip(test_trades, probs) if p >= min_confidence]
    filtered_pf = _profit_factor(filtered_trades)

    # Both sides must be a defined ratio (a None profit factor means zero losses in
    # that slice — nothing to divide by) so "no baseline losses" can never look like
    # an automatic pass for the filtered model.
    passed = bool(filtered_pf is not None and unfiltered_pf is not None and filtered_pf > unfiltered_pf)

    if passed:
        MODEL_DIR.mkdir(exist_ok=True)
        joblib.dump(model, MODEL_DIR / f"entry_filter_{mode}.joblib")

    save_run_fn(
        mode=mode, n_trades=len(all_trades), profit_factor_filtered=filtered_pf,
        profit_factor_unfiltered=unfiltered_pf, enabled=1 if passed else 0,
    )

    return {
        "trained": passed, "n_trades": len(all_trades),
        "profit_factor_filtered": filtered_pf, "profit_factor_unfiltered": unfiltered_pf,
    }


_model_cache: dict[str, tuple[float, object]] = {}


def load_entry_filter_model_cached(mode: str):
    path = MODEL_DIR / f"entry_filter_{mode}.joblib"
    if not path.exists():
        _model_cache.pop(mode, None)
        return None
    mtime = path.stat().st_mtime
    cached = _model_cache.get(mode)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    model = joblib.load(path)
    _model_cache[mode] = (mtime, model)
    return model


def predict_win_probability(model, features: dict) -> float:
    vector = [ml_features.features_to_vector(features)]
    return float(model.predict_proba(vector)[0][1])


def should_veto_entry(win_probability: float, min_confidence: float) -> bool:
    return win_probability < min_confidence
