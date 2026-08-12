import asyncio
import traceback
from datetime import datetime, timezone

import pandas as pd
import pandas_ta as ta

import bot_db

TIMEFRAME_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Adds sma20/sma50/rsi/macd/macd_signal/macd_hist/bb_upper/bb_mid/bb_lower/atr in place."""
    df["sma20"] = ta.sma(df["close"], length=20)
    df["sma50"] = ta.sma(df["close"], length=50)
    df["rsi"] = ta.rsi(df["close"], length=14)

    macd_df = ta.macd(df["close"])
    if macd_df is not None and not macd_df.empty:
        macd_col = next((c for c in macd_df.columns if c.startswith("MACD_") and not c.startswith("MACDs_") and not c.startswith("MACDh_")), None)
        signal_col = next((c for c in macd_df.columns if c.startswith("MACDs_")), None)
        hist_col = next((c for c in macd_df.columns if c.startswith("MACDh_")), None)
        df["macd"] = macd_df[macd_col] if macd_col else None
        df["macd_signal"] = macd_df[signal_col] if signal_col else None
        df["macd_hist"] = macd_df[hist_col] if hist_col else None
    else:
        df["macd"] = df["macd_signal"] = df["macd_hist"] = None

    bb_df = ta.bbands(df["close"], length=20)
    if bb_df is not None and not bb_df.empty:
        upper_col = next((c for c in bb_df.columns if c.startswith("BBU_")), None)
        mid_col = next((c for c in bb_df.columns if c.startswith("BBM_")), None)
        lower_col = next((c for c in bb_df.columns if c.startswith("BBL_")), None)
        df["bb_upper"] = bb_df[upper_col] if upper_col else None
        df["bb_mid"] = bb_df[mid_col] if mid_col else None
        df["bb_lower"] = bb_df[lower_col] if lower_col else None
    else:
        df["bb_upper"] = df["bb_mid"] = df["bb_lower"] = None

    if {"high", "low"}.issubset(df.columns):
        df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)
    else:
        df["atr"] = None

    stoch_df = ta.stoch(df["high"], df["low"], df["close"], k=5, d=3, smooth_k=3) if {"high", "low"}.issubset(df.columns) else None
    if stoch_df is not None and not stoch_df.empty:
        k_col = next((c for c in stoch_df.columns if c.startswith("STOCHk_")), None)
        d_col = next((c for c in stoch_df.columns if c.startswith("STOCHd_")), None)
        df["stoch_k"] = stoch_df[k_col] if k_col else None
        df["stoch_d"] = stoch_df[d_col] if d_col else None
    else:
        df["stoch_k"] = df["stoch_d"] = None

    return df


def compute_signal(df: pd.DataFrame) -> dict:
    """Reads the last row of an indicator-enriched df and returns a trade signal."""
    last = df.iloc[-1]
    rsi_val = float(last["rsi"]) if pd.notna(last["rsi"]) else 50.0
    macd_hist_val = float(last["macd_hist"]) if pd.notna(last["macd_hist"]) else 0.0
    atr_val = float(last["atr"]) if "atr" in df.columns and pd.notna(last["atr"]) else 0.0

    if rsi_val < 30 and macd_hist_val > 0:
        signal = "COMPRAR FUERTE"
        signal_reason = f"RSI sobrevendido ({rsi_val:.1f}) + MACD positivo — posible rebote"
    elif rsi_val < 45:
        signal = "TENDENCIA ALCISTA"
        signal_reason = f"RSI ({rsi_val:.1f}) en zona favorable, momentum positivo"
    elif rsi_val > 70 and macd_hist_val < 0:
        signal = "VENDER FUERTE"
        signal_reason = f"RSI sobrecomprado ({rsi_val:.1f}) + MACD negativo — posible caída"
    elif rsi_val > 55:
        signal = "TENDENCIA BAJISTA"
        signal_reason = f"RSI ({rsi_val:.1f}) en zona de precaución"
    else:
        signal = "ESPERAR"
        signal_reason = f"RSI neutral ({rsi_val:.1f}) — no hay señal clara"

    return {
        "signal": signal,
        "signal_reason": signal_reason,
        "last_rsi": round(rsi_val, 2),
        "last_macd_hist": macd_hist_val,
        "last_close": float(last["close"]),
        "atr": atr_val,
    }


def calc_sl_tp(entry_price: float, atr: float, direction: str,
                sl_mult: float = 1.5, tp_mult: float = 2.5) -> tuple[float, float]:
    if direction == "buy":
        sl = entry_price - sl_mult * atr
        tp = entry_price + tp_mult * atr
    else:
        sl = entry_price + sl_mult * atr
        tp = entry_price - tp_mult * atr
    return sl, tp


def calc_position_size(balance: float, risk_pct: float, sl_distance: float,
                        tick_value: float, tick_size: float,
                        volume_step: float, volume_min: float) -> float:
    risk_amount = balance * risk_pct
    loss_per_lot = (sl_distance / tick_size) * tick_value
    if loss_per_lot <= 0:
        return volume_min
    raw_volume = risk_amount / loss_per_lot
    steps = int(raw_volume / volume_step)
    volume = round(steps * volume_step, 8)
    return max(volume, volume_min)


def check_kill_switch(state: dict, balance: float, equity: float, today: str) -> dict:
    changes: dict = {}

    account_start_balance = state.get("account_start_balance")
    if account_start_balance is None:
        account_start_balance = balance
        changes["account_start_balance"] = balance

    day_start_balance = state.get("day_start_balance")
    if state.get("day_start_date") != today:
        day_start_balance = balance
        changes["day_start_balance"] = balance
        changes["day_start_date"] = today

    if state.get("kill_switch_tripped"):
        return changes  # already tripped — only manual reset clears it

    daily_loss_pct = 0.0
    if day_start_balance:
        daily_loss_pct = (day_start_balance - equity) / day_start_balance

    drawdown_pct = 0.0
    if account_start_balance:
        drawdown_pct = (account_start_balance - equity) / account_start_balance

    if daily_loss_pct >= state["daily_loss_limit_pct"]:
        changes["kill_switch_tripped"] = 1
        changes["disabled_reason"] = "daily_loss_limit"
    elif drawdown_pct >= state["max_drawdown_pct"]:
        changes["kill_switch_tripped"] = 1
        changes["disabled_reason"] = "max_drawdown"

    return changes


def process_symbol_tick(symbol: str, candles_df: pd.DataFrame, state: dict,
                         open_positions: list, balance: float, symbol_meta: dict,
                         place_order_fn) -> dict:
    if not state["running"]:
        return {"action": "none", "reason": "bot_stopped"}

    if state["kill_switch_tripped"]:
        return {"action": "none", "reason": state.get("disabled_reason") or "kill_switch"}

    if open_positions:
        return {"action": "none", "reason": "position_already_open"}

    signal_info = compute_signal(candles_df)
    if signal_info["signal"] not in ("COMPRAR FUERTE", "VENDER FUERTE"):
        return {"action": "none", "reason": "no_strong_signal", "signal": signal_info["signal"]}

    direction = "buy" if signal_info["signal"] == "COMPRAR FUERTE" else "sell"
    entry_price = signal_info["last_close"]
    atr = signal_info["atr"] or entry_price * 0.001  # fallback if ATR unavailable
    sl, tp = calc_sl_tp(entry_price, atr, direction)
    sl_distance = abs(entry_price - sl)

    volume = calc_position_size(
        balance=balance,
        risk_pct=state["risk_pct"],
        sl_distance=sl_distance,
        tick_value=symbol_meta["tick_value"],
        tick_size=symbol_meta["tick_size"],
        volume_step=symbol_meta["volume_step"],
        volume_min=symbol_meta["volume_min"],
    )

    result = place_order_fn(symbol=symbol, action=direction, volume=volume, sl=sl, tp=tp,
                             comment=signal_info["signal"], magic=state.get("magic", 424001))

    if result.get("success"):
        return {
            "action": "opened",
            "ticket": result.get("order"),
            "symbol": symbol,
            "direction": direction,
            "volume": volume,
            "price": result.get("price", entry_price),
            "sl": sl,
            "tp": tp,
            "signal_reason": signal_info["signal_reason"],
        }

    return {"action": "rejected", "symbol": symbol, "reason": result.get("error", "unknown error")}


def compute_mean_reversion_signal(df: pd.DataFrame) -> dict:
    """Reads the last row of an indicator-enriched df and returns a mean-reversion signal."""
    last = df.iloc[-1]
    close = float(last["close"])
    rsi_val = float(last["rsi"]) if pd.notna(last["rsi"]) else 50.0
    stoch_k = float(last["stoch_k"]) if pd.notna(last["stoch_k"]) else 50.0
    bb_lower = float(last["bb_lower"]) if pd.notna(last["bb_lower"]) else close
    bb_upper = float(last["bb_upper"]) if pd.notna(last["bb_upper"]) else close
    bb_mid = float(last["bb_mid"]) if pd.notna(last["bb_mid"]) else close
    atr_val = float(last["atr"]) if "atr" in df.columns and pd.notna(last["atr"]) else 0.0

    if close <= bb_lower and rsi_val < 30 and stoch_k < 20:
        signal = "COMPRAR FUERTE"
        signal_reason = f"Precio tocó banda inferior + RSI ({rsi_val:.1f}) y Stochastic ({stoch_k:.1f}) sobrevendidos — reversión a la media"
    elif close >= bb_upper and rsi_val > 70 and stoch_k > 80:
        signal = "VENDER FUERTE"
        signal_reason = f"Precio tocó banda superior + RSI ({rsi_val:.1f}) y Stochastic ({stoch_k:.1f}) sobrecomprados — reversión a la media"
    else:
        signal = "ESPERAR"
        signal_reason = "Sin confirmación de reversión a la media"

    return {
        "signal": signal,
        "signal_reason": signal_reason,
        "last_close": close,
        "atr": atr_val,
        "bb_mid": bb_mid,
    }


def process_symbol_tick_mean_reversion(symbol: str, candles_df: pd.DataFrame, state: dict,
                                        open_positions: list, balance: float, symbol_meta: dict,
                                        place_order_fn) -> dict:
    if not state["running"]:
        return {"action": "none", "reason": "bot_stopped"}

    if state["kill_switch_tripped"]:
        return {"action": "none", "reason": state.get("disabled_reason") or "kill_switch"}

    if open_positions:
        return {"action": "none", "reason": "position_already_open"}

    signal_info = compute_mean_reversion_signal(candles_df)
    if signal_info["signal"] not in ("COMPRAR FUERTE", "VENDER FUERTE"):
        return {"action": "none", "reason": "no_strong_signal", "signal": signal_info["signal"]}

    direction = "buy" if signal_info["signal"] == "COMPRAR FUERTE" else "sell"
    entry_price = signal_info["last_close"]
    atr = signal_info["atr"] or entry_price * 0.001
    sl, _ = calc_sl_tp(entry_price, atr, direction)
    tp = signal_info["bb_mid"]

    # Guard against inverted geometry (bb_mid on the wrong side of entry)
    if (direction == "buy" and tp <= entry_price) or (direction == "sell" and tp >= entry_price):
        return {"action": "none", "reason": "invalid_tp_geometry"}

    sl_distance = abs(entry_price - sl)
    volume = calc_position_size(
        balance=balance,
        risk_pct=state["risk_pct"],
        sl_distance=sl_distance,
        tick_value=symbol_meta["tick_value"],
        tick_size=symbol_meta["tick_size"],
        volume_step=symbol_meta["volume_step"],
        volume_min=symbol_meta["volume_min"],
    )

    mr_magic = state.get("magic", 424001) + 1
    result = place_order_fn(symbol=symbol, action=direction, volume=volume, sl=sl, tp=tp,
                             comment=signal_info["signal"], magic=mr_magic)

    if result.get("success"):
        return {
            "action": "opened",
            "ticket": result.get("order"),
            "symbol": symbol,
            "direction": direction,
            "volume": volume,
            "price": result.get("price", entry_price),
            "sl": sl,
            "tp": tp,
            "signal_reason": signal_info["signal_reason"],
        }

    return {"action": "rejected", "symbol": symbol, "reason": result.get("error", "unknown error")}


def find_closed_trades(open_trades: list, live_tickets: set) -> list:
    return [t for t in open_trades if t.get("ticket") is not None and t["ticket"] not in live_tickets]


def next_candle_sleep_seconds(timeframe: str, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    minutes = TIMEFRAME_MINUTES.get(timeframe.upper(), 15)
    interval_seconds = minutes * 60
    elapsed_today = (now.hour * 3600 + now.minute * 60 + now.second) % interval_seconds
    remaining = interval_seconds - elapsed_today
    return max(remaining, 5)


async def run_bot_loop():
    from routers import mt5 as mt5_router

    bot_db.init_db()
    last_candle_time: dict[str, int] = {}

    while True:
        try:
            state = bot_db.get_state()
            ok, _ = mt5_router._ensure_initialized()
            if ok:
                account = mt5_router.mt5.account_info()
                if account is not None:
                    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    changes = check_kill_switch(state, account.balance, account.equity, today)
                    if changes:
                        bot_db.update_state(**changes)
                        state.update(changes)

                    for symbol in state["symbols"].split(","):
                        symbol = symbol.strip().upper()
                        if not symbol:
                            continue

                        tf = mt5_router.TIMEFRAME_MAP.get(state["timeframe"].upper())
                        rates = mt5_router.mt5.copy_rates_from_pos(symbol, tf, 0, 200)
                        if rates is None or len(rates) == 0:
                            continue

                        latest_time = int(rates[-1]["time"])
                        if last_candle_time.get(symbol) == latest_time:
                            continue  # same candle already processed
                        last_candle_time[symbol] = latest_time

                        df = pd.DataFrame(rates)
                        df = add_indicators(df)

                        positions = mt5_router.mt5.positions_get(symbol=symbol) or []
                        bot_positions = [p for p in positions if p.magic == state["magic"]]

                        info = mt5_router.mt5.symbol_info(symbol)
                        if info is None:
                            continue
                        symbol_meta = {
                            "tick_value": info.trade_tick_value,
                            "tick_size": info.trade_tick_size,
                            "volume_step": info.volume_step,
                            "volume_min": info.volume_min,
                        }

                        def _place_order(**kw):
                            return mt5_router.place_order(**kw)

                        result = process_symbol_tick(
                            symbol, df, state, bot_positions, account.balance,
                            symbol_meta, _place_order,
                        )

                        if result["action"] == "opened":
                            bot_db.log_trade(
                                ticket=result["ticket"], symbol=symbol, action=result["direction"],
                                volume=result["volume"], price=result["price"], sl=result["sl"],
                                tp=result["tp"], signal_reason=result["signal_reason"], status="open",
                            )
                        elif result["action"] == "rejected":
                            bot_db.log_trade(
                                ticket=None, symbol=symbol, action="unknown", volume=0,
                                price=0, sl=0, tp=0, signal_reason=result["reason"], status="rejected",
                            )

            sleep_for = min(
                next_candle_sleep_seconds(state.get("timeframe", "M15")) if ok else 30,
                60,
            )
        except Exception:
            traceback.print_exc()
            sleep_for = 30

        await asyncio.sleep(sleep_for)
