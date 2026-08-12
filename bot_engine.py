import pandas as pd
import pandas_ta as ta


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
