from fastapi import APIRouter
from datetime import datetime, timezone
import os

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None  # type: ignore
    MT5_AVAILABLE = False

from dotenv import load_dotenv
load_dotenv()

MT5_LOGIN  = os.getenv("MT5_LOGIN", "")
MT5_PASS   = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")

router = APIRouter()


def _connect() -> tuple[bool, str]:
    """Initialize MT5 and log in. Returns (ok, error_msg)."""
    if not MT5_AVAILABLE:
        return False, "Librería MetaTrader5 no instalada"
    if not mt5.initialize():
        return False, "MT5 no está ejecutándose — abrí la aplicación primero"
    if not mt5.login(int(MT5_LOGIN), password=MT5_PASS, server=MT5_SERVER):
        err = mt5.last_error()
        mt5.shutdown()
        return False, f"Login fallido: {err}"
    return True, ""


@router.get("/status")
def mt5_status():
    ok, err = _connect()
    if not ok:
        return {"connected": False, "error": err}
    info = mt5.account_info()
    mt5.shutdown()
    return {
        "connected": True,
        "login": info.login,
        "name": info.name,
        "balance": info.balance,
        "equity": info.equity,
        "profit": info.profit,
        "margin": info.margin,
        "margin_free": info.margin_free,
        "currency": info.currency,
        "leverage": info.leverage,
        "server": info.server,
    }


@router.get("/positions")
def mt5_positions():
    ok, err = _connect()
    if not ok:
        return {"connected": False, "error": err, "positions": []}
    positions = mt5.positions_get()
    mt5.shutdown()
    if positions is None:
        return {"connected": True, "positions": []}
    result = []
    for p in positions:
        result.append({
            "ticket": p.ticket,
            "symbol": p.symbol,
            "type": "BUY" if p.type == 0 else "SELL",
            "volume": p.volume,
            "open_price": p.price_open,
            "current_price": p.price_current,
            "sl": p.sl,
            "tp": p.tp,
            "profit": p.profit,
            "swap": p.swap,
            "open_time": datetime.fromtimestamp(p.time, tz=timezone.utc).isoformat(),
            "comment": p.comment,
        })
    return {"connected": True, "positions": result}


@router.get("/history")
def mt5_history():
    ok, err = _connect()
    if not ok:
        return {"connected": False, "error": err, "deals": []}
    from datetime import timedelta
    date_to   = datetime.now(tz=timezone.utc)
    date_from = date_to - timedelta(days=90)
    deals = mt5.history_deals_get(date_from, date_to)
    mt5.shutdown()
    if deals is None:
        return {"connected": True, "deals": []}
    closed = [d for d in deals if d.entry == 1]  # entry==1 → deal out (close)
    closed_sorted = sorted(closed, key=lambda d: d.time, reverse=True)[:20]
    result = []
    for d in closed_sorted:
        result.append({
            "ticket": d.ticket,
            "order": d.order,
            "symbol": d.symbol,
            "type": "BUY" if d.type == 0 else "SELL",
            "volume": d.volume,
            "price": d.price,
            "profit": d.profit,
            "swap": d.swap,
            "commission": d.commission,
            "time": datetime.fromtimestamp(d.time, tz=timezone.utc).isoformat(),
            "comment": d.comment,
        })
    return {"connected": True, "deals": result}


@router.get("/symbols")
def mt5_symbols():
    ok, err = _connect()
    if not ok:
        return {"connected": False, "error": err, "symbols": []}
    symbols = mt5.symbols_get()
    mt5.shutdown()
    if symbols is None:
        return {"connected": True, "symbols": []}
    result = []
    for s in symbols:
        if not s.visible:
            continue
        result.append({
            "name": s.name,
            "description": s.description,
            "currency_base": s.currency_base,
            "currency_profit": s.currency_profit,
            "digits": s.digits,
            "spread": s.spread,
            "category": s.path.split("\\")[0] if s.path else "",
        })
    return {"connected": True, "symbols": result}


@router.get("/price/{symbol}")
def mt5_price(symbol: str):
    ok, err = _connect()
    if not ok:
        return {"connected": False, "error": err}
    tick = mt5.symbol_info_tick(symbol.upper())
    if tick is None:
        mt5.shutdown()
        return {"connected": True, "error": f"Símbolo '{symbol}' no encontrado o sin cotización"}
    info = mt5.symbol_info(symbol.upper())
    mt5.shutdown()
    return {
        "connected": True,
        "symbol": symbol.upper(),
        "bid": tick.bid,
        "ask": tick.ask,
        "spread": round((tick.ask - tick.bid) * (10 ** (info.digits if info else 5)), 1),
        "digits": info.digits if info else 5,
        "time": datetime.fromtimestamp(tick.time, tz=timezone.utc).isoformat(),
    }
