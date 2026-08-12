from fastapi import APIRouter
from pydantic import BaseModel

import bot_db

DB_PATH = bot_db.DB_PATH

router = APIRouter()


def _state_to_status(state: dict) -> dict:
    return {
        "running": bool(state["running"]),
        "kill_switch_tripped": bool(state["kill_switch_tripped"]),
        "disabled_reason": state["disabled_reason"],
        "day_start_balance": state["day_start_balance"],
        "account_start_balance": state["account_start_balance"],
        "current_balance": None,
        "current_equity": None,
        "current_profit": None,
        "symbols": [s for s in state["symbols"].split(",") if s],
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
        "symbols": [s for s in state["symbols"].split(",") if s],
        "timeframe": state["timeframe"],
        "risk_pct": state["risk_pct"],
        "daily_loss_limit_pct": state["daily_loss_limit_pct"],
        "max_drawdown_pct": state["max_drawdown_pct"],
        "trend_enabled": bool(state["trend_enabled"]),
        "mean_reversion_enabled": bool(state["mean_reversion_enabled"]),
    }


class ConfigUpdate(BaseModel):
    symbols: list[str] | None = None
    timeframe: str | None = None
    risk_pct: float | None = None
    daily_loss_limit_pct: float | None = None
    max_drawdown_pct: float | None = None
    trend_enabled: bool | None = None
    mean_reversion_enabled: bool | None = None


@router.put("/config")
def update_config(body: ConfigUpdate):
    bot_db.init_db(DB_PATH)
    fields = {}
    if body.symbols is not None:
        fields["symbols"] = ",".join(s.strip().upper() for s in body.symbols)
    if body.timeframe is not None:
        fields["timeframe"] = body.timeframe.upper()
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
    bot_db.update_state(DB_PATH, **fields)
    return get_config()
