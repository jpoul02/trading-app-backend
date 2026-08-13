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


def manage_open_position(pos: dict, atr: float, max_loss_pct: float = 0,
                          trailing_trigger_pct: float = 0, trailing_distance_atr: float = 0) -> dict:
    """Decide whether an open position should be hard-closed or trailed.

    pos: {"type": "buy"|"sell", "open_price": float, "current_price": float,
          "sl": float | None, "tp": float}
    Hard stop takes priority over trailing — a big adverse move closes the
    position outright instead of waiting for the (wider) ATR-based SL.
    trailing_trigger_pct: fraction (0-1) of the entry→TP distance the price
    must cover before trailing kicks in (e.g. 0.30 = 30% of the way to TP).
    """
    direction = pos["type"]
    entry = pos["open_price"]
    current = pos["current_price"]
    tp = pos.get("tp")

    adverse_pct = (entry - current) / entry if direction == "buy" else (current - entry) / entry
    if max_loss_pct and adverse_pct >= max_loss_pct:
        return {"action": "close", "reason": "max_loss_pct"}

    if not atr or not trailing_trigger_pct or not tp:
        return {"action": "none"}

    tp_distance = (tp - entry) if direction == "buy" else (entry - tp)
    if tp_distance <= 0:
        return {"action": "none"}

    progress_pct = (current - entry) / tp_distance if direction == "buy" else (entry - current) / tp_distance
    if progress_pct < trailing_trigger_pct:
        return {"action": "none"}

    sl = pos.get("sl")
    if direction == "buy":
        new_sl = current - trailing_distance_atr * atr
        if sl is not None and new_sl <= sl:
            return {"action": "none"}
    else:
        new_sl = current + trailing_distance_atr * atr
        if sl is not None and new_sl >= sl:
            return {"action": "none"}

    return {"action": "modify_sl", "sl": new_sl, "tp": tp}


def should_log_ml_veto(last_logged: dict, key: tuple, now_ts: float, cooldown_seconds: float = 3600) -> bool:
    last = last_logged.get(key)
    return last is None or (now_ts - last) >= cooldown_seconds


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

    ml_confidence = None
    if state.get("ml_filter_trend_enabled"):
        import ml_entry_filter
        import ml_features
        model = ml_entry_filter.load_entry_filter_model_cached("trend")
        if model is not None:
            features = ml_features.extract_entry_features(candles_df, len(candles_df) - 1)
            win_prob = ml_entry_filter.predict_win_probability(model, features)
            min_confidence = state.get("ml_filter_min_confidence", 0.5)
            if ml_entry_filter.should_veto_entry(win_prob, min_confidence):
                return {
                    "action": "rejected", "symbol": symbol,
                    "reason": f"Vetado por ML (confianza {win_prob:.0%})",
                }
            ml_confidence = round(win_prob, 4)

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
            "volume": result.get("volume", volume),
            "price": result.get("price", entry_price),
            "sl": result.get("sl", sl),
            "tp": result.get("tp", tp),
            "signal_reason": signal_info["signal_reason"],
            "ml_confidence": ml_confidence,
        }

    return {"action": "rejected", "symbol": symbol, "reason": result.get("error", "unknown error")}


def process_symbol_tick_fast(symbol: str, candles_df: pd.DataFrame, state: dict,
                              open_positions: list, balance: float, symbol_meta: dict,
                              place_order_fn) -> dict:
    if not state["running"]:
        return {"action": "none", "reason": "bot_stopped"}

    if state["kill_switch_tripped"]:
        return {"action": "none", "reason": state.get("disabled_reason") or "kill_switch"}

    if open_positions:
        return {"action": "none", "reason": "position_already_open"}

    signal_info = compute_signal(candles_df)
    buy_signals = ("COMPRAR FUERTE", "TENDENCIA ALCISTA")
    sell_signals = ("VENDER FUERTE", "TENDENCIA BAJISTA")
    if signal_info["signal"] not in buy_signals + sell_signals:
        return {"action": "none", "reason": "no_strong_signal", "signal": signal_info["signal"]}

    ml_confidence = None
    if state.get("ml_filter_fast_enabled"):
        import ml_entry_filter
        import ml_features
        model = ml_entry_filter.load_entry_filter_model_cached("fast")
        if model is not None:
            features = ml_features.extract_entry_features(candles_df, len(candles_df) - 1)
            win_prob = ml_entry_filter.predict_win_probability(model, features)
            min_confidence = state.get("ml_filter_min_confidence", 0.5)
            if ml_entry_filter.should_veto_entry(win_prob, min_confidence):
                return {
                    "action": "rejected", "symbol": symbol,
                    "reason": f"Vetado por ML (confianza {win_prob:.0%})",
                }
            ml_confidence = round(win_prob, 4)

    direction = "buy" if signal_info["signal"] in buy_signals else "sell"
    entry_price = signal_info["last_close"]
    atr = signal_info["atr"] or entry_price * 0.001
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

    fast_magic = state.get("magic", 424001) + 2
    result = place_order_fn(symbol=symbol, action=direction, volume=volume, sl=sl, tp=tp,
                             comment=signal_info["signal"], magic=fast_magic)

    if result.get("success"):
        return {
            "action": "opened",
            "ticket": result.get("order"),
            "symbol": symbol,
            "direction": direction,
            "volume": result.get("volume", volume),
            "price": result.get("price", entry_price),
            "sl": result.get("sl", sl),
            "tp": result.get("tp", tp),
            "signal_reason": signal_info["signal_reason"],
            "ml_confidence": ml_confidence,
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
            "volume": result.get("volume", volume),
            "price": result.get("price", entry_price),
            "sl": result.get("sl", sl),
            "tp": result.get("tp", tp),
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


def _build_symbol_meta(info) -> dict:
    return {
        "tick_value": info.trade_tick_value,
        "tick_size": info.trade_tick_size,
        "volume_step": info.volume_step,
        "volume_min": info.volume_min,
    }


def _parse_symbols(csv: str) -> set[str]:
    return {s.strip().upper() for s in csv.split(",") if s.strip()}


def _record_trade_result(mode: str, symbol: str, result: dict, obsidian_journal, log_trade_fn=None) -> None:
    if log_trade_fn is None:
        log_trade_fn = bot_db.log_trade

    if result["action"] == "opened":
        opened_at = datetime.now(timezone.utc).isoformat()
        obsidian_path = None
        try:
            obsidian_path = obsidian_journal.write_trade_opened({
                "symbol": symbol, "mode": mode, "action": result["direction"],
                "volume": result["volume"], "price": result["price"],
                "sl": result["sl"], "tp": result["tp"],
                "opened_at": opened_at, "signal_reason": result["signal_reason"],
            })
        except Exception:
            traceback.print_exc()
        log_trade_fn(
            ticket=result["ticket"], symbol=symbol, action=result["direction"],
            volume=result["volume"], price=result["price"], sl=result["sl"],
            tp=result["tp"], signal_reason=result["signal_reason"], status="open",
            mode=mode, obsidian_path=obsidian_path, opened_at=opened_at,
            ml_confidence=result.get("ml_confidence"),
        )
    elif result["action"] == "rejected":
        log_trade_fn(
            ticket=None, symbol=symbol, action="unknown", volume=0,
            price=0, sl=0, tp=0, signal_reason=result["reason"], status="rejected",
            mode=mode,
        )


async def run_bot_loop():
    from routers import mt5 as mt5_router
    import obsidian_journal

    bot_db.init_db()
    last_candle_time: dict[str, int] = {}
    last_candle_time_fast: dict[str, int] = {}
    last_ml_veto_logged: dict[tuple[str, str], float] = {}

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

                    # ── Close detection ─────────────────────────────────────
                    live_positions = mt5_router.mt5.positions_get() or []
                    open_trades = bot_db.get_open_trades()
                    if open_trades:
                        live_tickets = {p.ticket for p in live_positions}
                        for trade in find_closed_trades(open_trades, live_tickets):
                            deals = mt5_router.mt5.history_deals_get(position=trade["ticket"]) or []
                            close_deal = next((d for d in deals if d.entry == 1), None)
                            if close_deal is None:
                                continue
                            closed_at = datetime.fromtimestamp(close_deal.time, tz=timezone.utc).isoformat()
                            bot_db.update_trade(bot_db.DB_PATH, trade["id"], status="closed",
                                                 profit=close_deal.profit, closed_at=closed_at,
                                                 close_price=close_deal.price)
                            if trade.get("obsidian_path"):
                                try:
                                    obsidian_journal.write_trade_closed(trade["obsidian_path"], close_deal.profit, closed_at)
                                except Exception:
                                    traceback.print_exc()

                    # ── Position management: hard stop + ATR trailing SL ────
                    # Runs every tick (not gated on new-candle) so a fast adverse
                    # move gets caught before waiting for the wider ATR-based SL.
                    own_magics = {state["magic"], state["magic"] + 1, state["magic"] + 2}
                    obsidian_path_by_ticket = {
                        t["ticket"]: t["obsidian_path"] for t in open_trades if t.get("ticket") is not None
                    }
                    for pos in live_positions:
                        if pos.magic not in own_magics:
                            continue
                        tf_key = "fast_timeframe" if pos.magic == state["magic"] + 2 else "timeframe"
                        tf = mt5_router.TIMEFRAME_MAP.get(state[tf_key].upper())
                        rates = mt5_router.mt5.copy_rates_from_pos(pos.symbol, tf, 0, 20)
                        if rates is None or len(rates) == 0:
                            continue
                        atr_series = ta.atr(pd.Series(rates["high"]), pd.Series(rates["low"]), pd.Series(rates["close"]), length=14)
                        atr = float(atr_series.iloc[-1]) if atr_series is not None and pd.notna(atr_series.iloc[-1]) else 0.0

                        decision = manage_open_position(
                            {
                                "type": "buy" if pos.type == 0 else "sell",
                                "open_price": pos.price_open,
                                "current_price": pos.price_current,
                                "sl": pos.sl or None,
                                "tp": pos.tp,
                            },
                            atr,
                            max_loss_pct=state.get("max_loss_pct", 0),
                            trailing_trigger_pct=state.get("trailing_trigger_pct", 0),
                            trailing_distance_atr=state.get("trailing_distance_atr", 0),
                        )
                        if decision["action"] == "close":
                            mt5_router.close_position_by_ticket(pos.ticket)
                        elif decision["action"] == "modify_sl":
                            result = mt5_router.modify_position_sltp(pos.ticket, decision["sl"], decision["tp"])
                            path = obsidian_path_by_ticket.get(pos.ticket)
                            if result.get("success") and path:
                                try:
                                    obsidian_journal.write_trade_sl_adjusted(
                                        path, old_sl=pos.sl, new_sl=decision["sl"],
                                        current_price=pos.price_current,
                                        adjusted_at=datetime.now(timezone.utc).isoformat(),
                                    )
                                except Exception:
                                    traceback.print_exc()

                    # ── Signal evaluation: trend + mean reversion (shared timeframe) ──
                    trend_symbols = _parse_symbols(state["trend_symbols"])
                    mr_symbols = _parse_symbols(state["mean_reversion_symbols"])
                    for symbol in sorted(trend_symbols | mr_symbols):
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
                        trend_magic = state["magic"]
                        mr_magic = state["magic"] + 1
                        trend_positions = [p for p in positions if p.magic == trend_magic]
                        mr_positions = [p for p in positions if p.magic == mr_magic]

                        info = mt5_router.mt5.symbol_info(symbol)
                        if info is None:
                            continue
                        symbol_meta = _build_symbol_meta(info)

                        def _place_order(**kw):
                            return mt5_router.place_order(**kw)

                        for mode, positions_for_mode, process_fn, enabled_key, mode_symbols in (
                            ("trend", trend_positions, process_symbol_tick, "trend_enabled", trend_symbols),
                            ("mean_reversion", mr_positions, process_symbol_tick_mean_reversion, "mean_reversion_enabled", mr_symbols),
                        ):
                            if not state.get(enabled_key, 1) or symbol not in mode_symbols:
                                continue

                            result = process_fn(symbol, df, state, positions_for_mode,
                                                 state.get("trading_capital") or account.balance,
                                                 symbol_meta, _place_order)
                            if result["action"] == "rejected" and result.get("reason", "").startswith("Vetado por ML"):
                                veto_key = (mode, symbol)
                                now_ts = datetime.now(timezone.utc).timestamp()
                                if not should_log_ml_veto(last_ml_veto_logged, veto_key, now_ts):
                                    continue
                                last_ml_veto_logged[veto_key] = now_ts
                            _record_trade_result(mode, symbol, result, obsidian_journal)

                    # ── Signal evaluation: fast (independent timeframe) ─────────────
                    fast_symbols = _parse_symbols(state["fast_symbols"])
                    if state.get("fast_enabled") and fast_symbols:
                        for symbol in sorted(fast_symbols):
                            tf = mt5_router.TIMEFRAME_MAP.get(state["fast_timeframe"].upper())
                            rates = mt5_router.mt5.copy_rates_from_pos(symbol, tf, 0, 200)
                            if rates is None or len(rates) == 0:
                                continue

                            latest_time = int(rates[-1]["time"])
                            if last_candle_time_fast.get(symbol) == latest_time:
                                continue
                            last_candle_time_fast[symbol] = latest_time

                            df = pd.DataFrame(rates)
                            df = add_indicators(df)

                            positions = mt5_router.mt5.positions_get(symbol=symbol) or []
                            fast_magic = state["magic"] + 2
                            fast_positions = [p for p in positions if p.magic == fast_magic]

                            info = mt5_router.mt5.symbol_info(symbol)
                            if info is None:
                                continue
                            symbol_meta = _build_symbol_meta(info)

                            def _place_order(**kw):
                                return mt5_router.place_order(**kw)

                            result = process_symbol_tick_fast(symbol, df, state, fast_positions,
                                                                state.get("trading_capital") or account.balance,
                                                                symbol_meta, _place_order)
                            if result["action"] == "rejected" and result.get("reason", "").startswith("Vetado por ML"):
                                veto_key = ("fast", symbol)
                                now_ts = datetime.now(timezone.utc).timestamp()
                                if not should_log_ml_veto(last_ml_veto_logged, veto_key, now_ts):
                                    continue
                                last_ml_veto_logged[veto_key] = now_ts
                            _record_trade_result("fast", symbol, result, obsidian_journal)

            sleep_for = min(
                next_candle_sleep_seconds(state.get("timeframe", "M15")) if ok else 30,
                60,
            )
        except Exception:
            traceback.print_exc()
            sleep_for = 30

        await asyncio.sleep(sleep_for)
