from datetime import datetime, timedelta, timezone
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression

import backtest_engine
import bot_db
import ml_features

MODEL_DIR = Path(__file__).parent / "ml_models"
GATE_LOOKBACK_DAYS = 730  # 2 years, matches the existing backtest convention


def _profit_factor(trades: list[dict]) -> float | None:
    gross_profit = sum(t["profit"] for t in trades if t["profit"] > 0)
    gross_loss = abs(sum(t["profit"] for t in trades if t["profit"] <= 0))
    if gross_loss <= 0:
        return None
    return round(gross_profit / gross_loss, 4)


def train_entry_filter_model(mode: str, symbols: list[str], timeframe: str,
                              risk_pct: float, min_confidence: float,
                              starting_balance: float = 100000,
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
    date_from = date_to - timedelta(days=GATE_LOOKBACK_DAYS)

    all_trades = []
    for symbol in symbols:
        df = fetch_candles_fn(symbol, timeframe, date_from, date_to)
        if df is None or len(df) <= 200:
            continue
        symbol_meta = symbol_info_fn(symbol)
        if symbol_meta is None:
            continue
        result = simulate_fn(df, mode, risk_pct, symbol_meta, starting_balance, warmup=200)
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
    passed = filtered_pf is not None and unfiltered_pf is not None and filtered_pf > unfiltered_pf

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
