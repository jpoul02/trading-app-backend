from fastapi import APIRouter
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
import os

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None  # type: ignore
    MT5_AVAILABLE = False

from dotenv import load_dotenv

try:
    import pandas as pd
    import pandas_ta as ta  # type: ignore
    PANDAS_TA_AVAILABLE = True
except ImportError:
    pd = None  # type: ignore
    ta = None  # type: ignore
    PANDAS_TA_AVAILABLE = False

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


TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1 if MT5_AVAILABLE else None,
    "M5": mt5.TIMEFRAME_M5 if MT5_AVAILABLE else None,
    "M15": mt5.TIMEFRAME_M15 if MT5_AVAILABLE else None,
    "M30": mt5.TIMEFRAME_M30 if MT5_AVAILABLE else None,
    "H1": mt5.TIMEFRAME_H1 if MT5_AVAILABLE else None,
    "H4": mt5.TIMEFRAME_H4 if MT5_AVAILABLE else None,
    "D1": mt5.TIMEFRAME_D1 if MT5_AVAILABLE else None,
}


@router.get("/candles/{symbol}")
async def get_candles(symbol: str, timeframe: str = "H1", count: int = 100):
    ok, err = _ensure_initialized()
    if not ok:
        return {"error": err}
    tf = TIMEFRAME_MAP.get(timeframe.upper())
    if tf is None:
        return {"error": f"Timeframe inválido: {timeframe}"}
    count = min(count, 500)
    rates = mt5.copy_rates_from_pos(symbol.upper(), tf, 0, count)
    if rates is None:
        return {"error": f"No se pudieron obtener velas para {symbol}: {mt5.last_error()}"}
    return [
        {
            "time": int(r["time"]),
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": int(r["tick_volume"]),
        }
        for r in rates
    ]


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


class OrderRequest(BaseModel):
    symbol: str
    action: str  # "buy" o "sell"
    volume: float
    sl: float = 0.0
    tp: float = 0.0
    comment: str = "Trading App"


@router.post("/order")
async def send_order(req: OrderRequest):
    ok, err = _connect()
    if not ok:
        return {"success": False, "error": err}

    symbol = req.symbol.upper()
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return {"success": False, "error": f"Símbolo {symbol} no encontrado"}

    if not symbol_info.visible:
        mt5.symbol_select(symbol, True)

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"success": False, "error": "No se pudo obtener el precio actual"}

    order_type = mt5.ORDER_TYPE_BUY if req.action.lower() == "buy" else mt5.ORDER_TYPE_SELL
    price = tick.ask if req.action.lower() == "buy" else tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": req.volume,
        "type": order_type,
        "price": price,
        "sl": req.sl if req.sl > 0 else 0.0,
        "tp": req.tp if req.tp > 0 else 0.0,
        "deviation": 20,
        "magic": 234000,
        "comment": req.comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        return {"success": False, "error": str(mt5.last_error())}

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return {"success": False, "error": f"Error {result.retcode}: {result.comment}"}

    return {
        "success": True,
        "order": result.order,
        "volume": result.volume,
        "price": result.price,
        "comment": result.comment,
    }


@router.post("/close/{ticket}")
async def close_position(ticket: int):
    ok, err = _connect()
    if not ok:
        return {"success": False, "error": err}

    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        return {"success": False, "error": f"Posición #{ticket} no encontrada"}

    pos = positions[0]
    close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY

    tick = mt5.symbol_info_tick(pos.symbol)
    if tick is None:
        return {"success": False, "error": "No se pudo obtener precio actual"}

    price = tick.bid if pos.type == 0 else tick.ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": pos.symbol,
        "volume": pos.volume,
        "type": close_type,
        "position": ticket,
        "price": price,
        "deviation": 20,
        "magic": 234000,
        "comment": "Close by Trading App",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        return {"success": False, "error": str(mt5.last_error())}

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return {"success": False, "error": f"Error {result.retcode}: {result.comment}"}

    return {
        "success": True,
        "order": result.order,
        "volume": result.volume,
        "price": result.price,
        "comment": result.comment,
    }


@router.get("/indicators/{symbol}")
async def get_indicators(symbol: str, timeframe: str = "H1", count: int = 200):
    if not PANDAS_TA_AVAILABLE:
        return {"error": "pandas-ta no instalado en este servidor"}
    ok, err = _ensure_initialized()
    if not ok:
        return {"error": err}
    tf = TIMEFRAME_MAP.get(timeframe.upper())
    if tf is None:
        return {"error": f"Timeframe inválido: {timeframe}"}
    count = min(count, 500)
    rates = mt5.copy_rates_from_pos(symbol.upper(), tf, 0, count)
    if rates is None:
        return {"error": f"No se pudieron obtener datos: {mt5.last_error()}"}

    df = pd.DataFrame(rates)
    df["sma20"] = ta.sma(df["close"], length=20)
    df["sma50"] = ta.sma(df["close"], length=50)
    df["rsi"]   = ta.rsi(df["close"], length=14)
    macd_df     = ta.macd(df["close"])
    df["macd"]        = macd_df["MACD_12_26_9"]
    df["macd_signal"] = macd_df["MACDs_12_26_9"]
    df["macd_hist"]   = macd_df["MACDh_12_26_9"]
    bb_df        = ta.bbands(df["close"], length=20)
    df["bb_upper"] = bb_df["BBU_20_2.0"]
    df["bb_lower"] = bb_df["BBL_20_2.0"]
    df["bb_mid"]   = bb_df["BBM_20_2.0"]

    last = df.iloc[-1]
    rsi_val       = float(last["rsi"])       if pd.notna(last["rsi"])       else 50.0
    macd_hist_val = float(last["macd_hist"]) if pd.notna(last["macd_hist"]) else 0.0

    if rsi_val < 30 and macd_hist_val > 0:
        signal        = "COMPRAR"
        signal_reason = f"RSI sobrevendido ({rsi_val:.1f}) + MACD positivo"
    elif rsi_val > 70 and macd_hist_val < 0:
        signal        = "VENDER"
        signal_reason = f"RSI sobrecomprado ({rsi_val:.1f}) + MACD negativo"
    else:
        signal        = "ESPERAR"
        signal_reason = f"RSI neutral ({rsi_val:.1f})"

    def _f(val, decimals: int = 5):
        return round(float(val), decimals) if pd.notna(val) else None

    return {
        "signal":        signal,
        "signal_reason": signal_reason,
        "last_rsi":      round(rsi_val, 2),
        "last_macd":     _f(last["macd"]),
        "last_close":    float(last["close"]),
        "candles": [
            {
                "time":        int(row["time"]),
                "sma20":       _f(row["sma20"]),
                "sma50":       _f(row["sma50"]),
                "rsi":         _f(row["rsi"], 2),
                "macd":        _f(row["macd"]),
                "macd_signal": _f(row["macd_signal"]),
                "macd_hist":   _f(row["macd_hist"]),
                "bb_upper":    _f(row["bb_upper"]),
                "bb_lower":    _f(row["bb_lower"]),
            }
            for _, row in df.iterrows()
        ],
    }
