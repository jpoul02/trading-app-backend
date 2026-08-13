import json
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

import backtest_engine
import bot_db

router = APIRouter()

WARMUP = 200


class BacktestRequest(BaseModel):
    symbol: str
    timeframe: str = "M15"
    date_from: str  # "YYYY-MM-DD"
    date_to: str
    strategy: str  # "trend" | "mean_reversion" | "fast" | "both"
    risk_pct: float = 0.01
    starting_balance: float = 100000


def run_single_backtest(symbol: str, timeframe: str, date_from: datetime, date_to: datetime,
                        strategy: str, risk_pct: float, starting_balance: float):
    from routers import mt5 as mt5_router

    df = backtest_engine.fetch_historical_candles(symbol, timeframe, date_from, date_to)
    if df is None or len(df) <= WARMUP:
        return {"error": f"No hay suficiente historial para {symbol} {timeframe} en ese rango"}

    info = mt5_router.mt5.symbol_info(symbol.upper())
    if info is None:
        return {"error": f"Símbolo {symbol} no encontrado"}
    symbol_meta = {
        "tick_value": info.trade_tick_value, "tick_size": info.trade_tick_size,
        "volume_step": info.volume_step, "volume_min": info.volume_min,
    }

    result = backtest_engine.simulate_strategy(
        df, strategy, risk_pct, symbol_meta, starting_balance, warmup=WARMUP,
    )
    result["symbol"] = symbol.upper()
    result["timeframe"] = timeframe.upper()
    result["strategy"] = strategy

    bot_db.init_db()
    run_id = bot_db.save_backtest_run(
        symbol=result["symbol"], timeframe=result["timeframe"], strategy=strategy,
        date_from=date_from.date().isoformat(), date_to=date_to.date().isoformat(),
        risk_pct=risk_pct, starting_balance=starting_balance,
        total_trades=result["total_trades"], win_rate_pct=result["win_rate_pct"],
        total_profit=result["total_profit"], max_drawdown_pct=result["max_drawdown_pct"],
        profit_factor=result["profit_factor"], full_result_json=json.dumps(result),
    )
    result["run_id"] = run_id
    return result


@router.post("/run")
def run_backtest(req: BacktestRequest):
    date_from = datetime.fromisoformat(req.date_from)
    date_to = datetime.fromisoformat(req.date_to)

    if req.strategy == "both":
        return {
            "trend": run_single_backtest(req.symbol, req.timeframe, date_from, date_to, "trend", req.risk_pct, req.starting_balance),
            "mean_reversion": run_single_backtest(req.symbol, req.timeframe, date_from, date_to, "mean_reversion", req.risk_pct, req.starting_balance),
            "fast": run_single_backtest(req.symbol, req.timeframe, date_from, date_to, "fast", req.risk_pct, req.starting_balance),
        }

    return run_single_backtest(req.symbol, req.timeframe, date_from, date_to, req.strategy, req.risk_pct, req.starting_balance)


@router.get("/history")
def get_history(limit: int = 50):
    bot_db.init_db()
    return bot_db.list_backtest_runs(limit=limit)


@router.get("/history/{run_id}")
def get_history_run(run_id: int):
    bot_db.init_db()
    run = bot_db.get_backtest_run(run_id=run_id)
    if run is None:
        return {"error": "Backtest no encontrado"}
    run["full_result"] = json.loads(run.pop("full_result_json"))
    return run
