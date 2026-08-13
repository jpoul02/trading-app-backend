from fastapi import APIRouter

import bot_db
import ml_entry_filter

router = APIRouter()

DB_PATH = bot_db.DB_PATH

TRAINABLE_MODES = (
    ("trend", "trend_symbols", "timeframe"),
    ("fast", "fast_symbols", "fast_timeframe"),
)


@router.post("/train")
def train():
    bot_db.init_db(DB_PATH)
    state = bot_db.get_state(DB_PATH)
    results = {}
    for mode, symbols_key, timeframe_key in TRAINABLE_MODES:
        symbols = [s for s in state[symbols_key].split(",") if s]
        results[mode] = ml_entry_filter.train_entry_filter_model(
            mode, symbols, state[timeframe_key], state["risk_pct"],
            min_confidence=state["ml_filter_min_confidence"],
            max_loss_pct=state["max_loss_pct"],
            trailing_trigger_pct=state["trailing_trigger_pct"],
            trailing_distance_atr=state["trailing_distance_atr"],
        )
    return results


@router.get("/models")
def get_models():
    bot_db.init_db(DB_PATH)
    return {
        "trend": bot_db.get_latest_ml_model(DB_PATH, mode="trend"),
        "fast": bot_db.get_latest_ml_model(DB_PATH, mode="fast"),
    }
