from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import bot_db

DB_PATH = bot_db.DB_PATH

router = APIRouter()

GATE_LOOKBACK_DAYS = 182
GATE_STARTING_BALANCE = 100000


def _split_symbols(csv: str) -> list[str]:
    return [s for s in csv.split(",") if s]


def _state_to_status(state: dict) -> dict:
    all_symbols = list(dict.fromkeys(
        _split_symbols(state["trend_symbols"])
        + _split_symbols(state["mean_reversion_symbols"])
        + _split_symbols(state["fast_symbols"])
    ))
    return {
        "running": bool(state["running"]),
        "kill_switch_tripped": bool(state["kill_switch_tripped"]),
        "disabled_reason": state["disabled_reason"],
        "day_start_balance": state["day_start_balance"],
        "account_start_balance": state["account_start_balance"],
        "current_balance": None,
        "current_equity": None,
        "current_profit": None,
        "symbols": all_symbols,
        "timeframe": state["timeframe"],
    }


@router.get("/status")
def get_status():
    bot_db.init_db(DB_PATH)
    status = _state_to_status(bot_db.get_state(DB_PATH))

    from routers import mt5 as mt5_router
    ok, _ = mt5_router._connect()
    if ok:
        account = mt5_router.mt5.account_info()
        if account is not None:
            status["current_balance"] = account.balance
            status["current_equity"] = account.equity
            status["current_profit"] = account.profit

    return status


@router.post("/start")
def start_bot():
    bot_db.init_db(DB_PATH)
    bot_db.update_state(DB_PATH, running=1)
    return {"running": True}


@router.post("/stop")
def stop_bot():
    bot_db.init_db(DB_PATH)
    bot_db.update_state(DB_PATH, running=0)
    return {"running": False}


@router.post("/reset-kill-switch")
def reset_kill_switch():
    bot_db.init_db(DB_PATH)
    bot_db.update_state(DB_PATH, kill_switch_tripped=0, disabled_reason=None)
    return {"kill_switch_tripped": False}


@router.get("/trades")
def get_trades(limit: int = 20, offset: int = 0):
    bot_db.init_db(DB_PATH)
    return {
        "trades": bot_db.list_trades(DB_PATH, limit=limit, offset=offset),
        "total": bot_db.count_trades(DB_PATH),
    }


@router.get("/config")
def get_config():
    bot_db.init_db(DB_PATH)
    state = bot_db.get_state(DB_PATH)
    return {
        "trend_symbols": _split_symbols(state["trend_symbols"]),
        "mean_reversion_symbols": _split_symbols(state["mean_reversion_symbols"]),
        "fast_symbols": _split_symbols(state["fast_symbols"]),
        "timeframe": state["timeframe"],
        "fast_timeframe": state["fast_timeframe"],
        "risk_pct": state["risk_pct"],
        "daily_loss_limit_pct": state["daily_loss_limit_pct"],
        "max_drawdown_pct": state["max_drawdown_pct"],
        "trend_enabled": bool(state["trend_enabled"]),
        "mean_reversion_enabled": bool(state["mean_reversion_enabled"]),
        "fast_enabled": bool(state["fast_enabled"]),
    }


class ConfigUpdate(BaseModel):
    trend_symbols: list[str] | None = None
    mean_reversion_symbols: list[str] | None = None
    fast_symbols: list[str] | None = None
    timeframe: str | None = None
    fast_timeframe: str | None = None
    risk_pct: float | None = None
    daily_loss_limit_pct: float | None = None
    max_drawdown_pct: float | None = None
    trend_enabled: bool | None = None
    mean_reversion_enabled: bool | None = None
    fast_enabled: bool | None = None


def check_mode_backtest_gate(mode: str, symbols: list[str], timeframe: str, risk_pct: float,
                              run_backtest_fn=None) -> dict:
    if not symbols:
        return {"passed": False, "failures": [
            {"symbol": None, "profit_factor": None, "error": "No hay símbolos configurados para este modo"}
        ]}

    if run_backtest_fn is None:
        from routers.backtest import run_single_backtest
        run_backtest_fn = run_single_backtest

    date_to = datetime.now(timezone.utc)
    date_from = date_to - timedelta(days=GATE_LOOKBACK_DAYS)

    failures = []
    for symbol in symbols:
        result = run_backtest_fn(symbol, timeframe, date_from, date_to, mode, risk_pct, GATE_STARTING_BALANCE)
        pf = result.get("profit_factor")
        if result.get("error") or pf is None or pf <= 1:
            failures.append({"symbol": symbol, "profit_factor": pf, "error": result.get("error")})

    return {"passed": len(failures) == 0, "failures": failures}


@router.put("/config")
def update_config(body: ConfigUpdate):
    bot_db.init_db(DB_PATH)
    state = bot_db.get_state(DB_PATH)
    risk_pct = body.risk_pct if body.risk_pct is not None else state["risk_pct"]

    trend_enabled_after = body.trend_enabled if body.trend_enabled is not None else bool(state["trend_enabled"])
    touches_trend = (
        body.trend_enabled is True or body.trend_symbols is not None
        or body.timeframe is not None or body.risk_pct is not None
    )
    if trend_enabled_after and touches_trend:
        symbols = body.trend_symbols if body.trend_symbols is not None else _split_symbols(state["trend_symbols"])
        timeframe = body.timeframe if body.timeframe is not None else state["timeframe"]
        gate = check_mode_backtest_gate("trend", symbols, timeframe, risk_pct)
        if not gate["passed"]:
            raise HTTPException(status_code=400, detail={"mode": "trend", "failures": gate["failures"]})

    mr_enabled_after = (
        body.mean_reversion_enabled if body.mean_reversion_enabled is not None
        else bool(state["mean_reversion_enabled"])
    )
    touches_mr = (
        body.mean_reversion_enabled is True or body.mean_reversion_symbols is not None
        or body.timeframe is not None or body.risk_pct is not None
    )
    if mr_enabled_after and touches_mr:
        symbols = (
            body.mean_reversion_symbols if body.mean_reversion_symbols is not None
            else _split_symbols(state["mean_reversion_symbols"])
        )
        timeframe = body.timeframe if body.timeframe is not None else state["timeframe"]
        gate = check_mode_backtest_gate("mean_reversion", symbols, timeframe, risk_pct)
        if not gate["passed"]:
            raise HTTPException(status_code=400, detail={"mode": "mean_reversion", "failures": gate["failures"]})

    fast_enabled_after = body.fast_enabled if body.fast_enabled is not None else bool(state["fast_enabled"])
    touches_fast = (
        body.fast_enabled is True or body.fast_symbols is not None
        or body.fast_timeframe is not None or body.risk_pct is not None
    )
    if fast_enabled_after and touches_fast:
        symbols = body.fast_symbols if body.fast_symbols is not None else _split_symbols(state["fast_symbols"])
        timeframe = body.fast_timeframe if body.fast_timeframe is not None else state["fast_timeframe"]
        gate = check_mode_backtest_gate("fast", symbols, timeframe, risk_pct)
        if not gate["passed"]:
            raise HTTPException(status_code=400, detail={"mode": "fast", "failures": gate["failures"]})

    fields = {}
    if body.trend_symbols is not None:
        fields["trend_symbols"] = ",".join(s.strip().upper() for s in body.trend_symbols)
    if body.mean_reversion_symbols is not None:
        fields["mean_reversion_symbols"] = ",".join(s.strip().upper() for s in body.mean_reversion_symbols)
    if body.fast_symbols is not None:
        fields["fast_symbols"] = ",".join(s.strip().upper() for s in body.fast_symbols)
    if body.timeframe is not None:
        fields["timeframe"] = body.timeframe.upper()
    if body.fast_timeframe is not None:
        fields["fast_timeframe"] = body.fast_timeframe.upper()
    if body.risk_pct is not None:
        fields["risk_pct"] = body.risk_pct
    if body.daily_loss_limit_pct is not None:
        fields["daily_loss_limit_pct"] = body.daily_loss_limit_pct
    if body.max_drawdown_pct is not None:
        fields["max_drawdown_pct"] = body.max_drawdown_pct
    if body.trend_enabled is not None:
        fields["trend_enabled"] = int(body.trend_enabled)
    if body.mean_reversion_enabled is not None:
        fields["mean_reversion_enabled"] = int(body.mean_reversion_enabled)
    if body.fast_enabled is not None:
        fields["fast_enabled"] = int(body.fast_enabled)
    bot_db.update_state(DB_PATH, **fields)
    return get_config()
