from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

import backtest_engine

router = APIRouter()

WARMUP = 200


class BacktestRequest(BaseModel):
    symbol: str
    timeframe: str = "M15"
    date_from: str  # "YYYY-MM-DD"
    date_to: str
    strategy: str  # "trend" | "mean_reversion" | "both"
    risk_pct: float = 0.01
    starting_balance: float = 100000


def _run_one(symbol: str, timeframe: str, date_from: datetime, date_to: datetime,
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
    return result


@router.post("/run")
def run_backtest(req: BacktestRequest):
    date_from = datetime.fromisoformat(req.date_from)
    date_to = datetime.fromisoformat(req.date_to)

    if req.strategy == "both":
        return {
            "trend": _run_one(req.symbol, req.timeframe, date_from, date_to, "trend", req.risk_pct, req.starting_balance),
            "mean_reversion": _run_one(req.symbol, req.timeframe, date_from, date_to, "mean_reversion", req.risk_pct, req.starting_balance),
        }

    return _run_one(req.symbol, req.timeframe, date_from, date_to, req.strategy, req.risk_pct, req.starting_balance)
