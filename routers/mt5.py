from fastapi import APIRouter
from datetime import datetime, timezone, timedelta
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

# Paths to try in order; None = let MT5 find the terminal itself
_MT5_PATHS = [
    None,
    r"C:\Program Files\MetaTrader 5\terminal64.exe",
    r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe",
]

_initialized = False

router = APIRouter()


# ─── Connection helpers ────────────────────────────────────────────────────────

def _ensure_initialized() -> tuple[bool, str]:
    """
    Keep a persistent MT5 session — initialize once, never shutdown between
    requests. Re-initialize automatically if the terminal connection drops.
    """
    global _initialized
    if not MT5_AVAILABLE:
        return False, "Librería MetaTrader5 no instalada"

    # Already initialized — verify the terminal is still alive
    if _initialized:
        if mt5.terminal_info() is not None:
            return True, ""
        # Connection dropped (e.g. MT5 was restarted); reset and retry below
        _initialized = False

    for path in _MT5_PATHS:
        kwargs = {"path": path} if path else {}
        if mt5.initialize(**kwargs):
            _initialized = True
            return True, ""

    return False, f"mt5.initialize() falló: {mt5.last_error()} — abrí MT5 primero"


def _connect() -> tuple[bool, str]:
    """Ensure MT5 is initialized and logged in. No shutdown after calls."""
    ok, err = _ensure_initialized()
    if not ok:
        return False, err

    # If already logged in (account_info returns data), skip re-login
    if mt5.account_info() is not None:
        return True, ""

    if not mt5.login(int(MT5_LOGIN), password=MT5_PASS, server=MT5_SERVER):
        return False, f"Login fallido: {mt5.last_error()}"

    return True, ""


# ─── Debug endpoint ───────────────────────────────────────────────────────────

@router.get("/debug")
def mt5_debug():
    """Diagnostic endpoint — returns every MT5 state detail for troubleshooting."""
    if not MT5_AVAILABLE:
        return {"mt5_available": False, "error": "Librería MetaTrader5 no instalada"}

    out: dict = {"mt5_available": True}

    # Library version (works before initialize)
    try:
        out["version"] = str(mt5.version())
    except Exception as exc:
        out["version"] = f"error: {exc}"

    # Try initialize without path
    init_ok = mt5.initialize()
    out["initialize_no_path"] = init_ok
    out["last_error_after_init"] = str(mt5.last_error())

    if not init_ok:
        # Retry with explicit paths
        for path in _MT5_PATHS[1:]:
            result = mt5.initialize(path=path)
            out[f"initialize_{path}"] = result
            out["last_error_after_init"] = str(mt5.last_error())
            if result:
                init_ok = True
                break

    if init_ok:
        global _initialized
        _initialized = True

        ti = mt5.terminal_info()
        out["terminal_info"] = dict(ti._asdict()) if ti else None

        login_ok = mt5.login(int(MT5_LOGIN), password=MT5_PASS, server=MT5_SERVER)
        out["login_result"] = login_ok
        out["last_error_after_login"] = str(mt5.last_error())

        if login_ok:
            ai = mt5.account_info()
            out["account_info"] = {
                "login": ai.login,
                "name": ai.name,
                "balance": ai.balance,
                "server": ai.server,
                "currency": ai.currency,
            } if ai else None

    return out


# ─── API endpoints ────────────────────────────────────────────────────────────

@router.get("/status")
def mt5_status():
    ok, err = _connect()
    if not ok:
        return {"connected": False, "error": err}
    info = mt5.account_info()
    if info is None:
        return {"connected": False, "error": "account_info() returned None after login"}
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
    date_to   = datetime.now(tz=timezone.utc)
    date_from = date_to - timedelta(days=90)
    deals = mt5.history_deals_get(date_from, date_to)
    if deals is None:
        return {"connected": True, "deals": []}
    closed = [d for d in deals if d.entry == 1]
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
    sym = symbol.upper()
    tick = mt5.symbol_info_tick(sym)
    if tick is None:
        return {"connected": True, "error": f"Símbolo '{sym}' no encontrado o sin cotización"}
    info = mt5.symbol_info(sym)
    digits = info.digits if info else 5
    return {
        "connected": True,
        "symbol": sym,
        "bid": tick.bid,
        "ask": tick.ask,
        "spread": round((tick.ask - tick.bid) * (10 ** digits), 1),
        "digits": digits,
        "time": datetime.fromtimestamp(tick.time, tz=timezone.utc).isoformat(),
    }
