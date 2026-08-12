from bot_engine import (
    add_indicators, calc_position_size, calc_sl_tp,
    compute_mean_reversion_signal, compute_signal,
)


def simulate_strategy(candles_df, strategy: str, risk_pct: float, symbol_meta: dict,
                       starting_balance: float, warmup: int = 200, signal_fn=None) -> dict:
    if signal_fn is None:
        base_fn = compute_signal if strategy == "trend" else compute_mean_reversion_signal

        def signal_fn(window):
            return base_fn(add_indicators(window.copy()))

    balance = starting_balance
    trades: list = []
    position = None

    n = len(candles_df)
    i = warmup
    while i < n:
        row = candles_df.iloc[i]

        if position is None:
            window = candles_df.iloc[: i + 1]
            info = signal_fn(window)
            if info["signal"] in ("COMPRAR FUERTE", "VENDER FUERTE"):
                direction = "buy" if info["signal"] == "COMPRAR FUERTE" else "sell"
                entry = info["last_close"]
                atr = info["atr"] or entry * 0.001
                sl, tp = calc_sl_tp(entry, atr, direction)
                if strategy == "mean_reversion":
                    tp = info["bb_mid"]
                    if (direction == "buy" and tp <= entry) or (direction == "sell" and tp >= entry):
                        i += 1
                        continue
                sl_distance = abs(entry - sl)
                volume = calc_position_size(
                    balance=balance, risk_pct=risk_pct, sl_distance=sl_distance,
                    tick_value=symbol_meta["tick_value"], tick_size=symbol_meta["tick_size"],
                    volume_step=symbol_meta["volume_step"], volume_min=symbol_meta["volume_min"],
                )
                position = {
                    "direction": direction, "entry": entry, "sl": sl, "tp": tp,
                    "volume": volume, "opened_at": int(row["time"]),
                }
        else:
            if position["direction"] == "buy":
                hit_sl = row["low"] <= position["sl"]
                hit_tp = row["high"] >= position["tp"]
            else:
                hit_sl = row["high"] >= position["sl"]
                hit_tp = row["low"] <= position["tp"]

            close_price = None
            if hit_sl:
                close_price = position["sl"]  # SL takes priority if both hit in the same candle
            elif hit_tp:
                close_price = position["tp"]

            if close_price is not None:
                price_diff = (
                    close_price - position["entry"] if position["direction"] == "buy"
                    else position["entry"] - close_price
                )
                profit = (price_diff / symbol_meta["tick_size"]) * symbol_meta["tick_value"] * position["volume"]
                balance += profit
                trades.append({
                    "direction": position["direction"], "entry": position["entry"],
                    "exit": close_price, "sl": position["sl"], "tp": position["tp"],
                    "volume": position["volume"], "profit": round(profit, 2),
                    "opened_at": position["opened_at"], "closed_at": int(row["time"]),
                })
                position = None

        i += 1

    return compute_backtest_metrics(trades, starting_balance)


def compute_backtest_metrics(trades: list, starting_balance: float) -> dict:
    balance = starting_balance
    peak = starting_balance
    max_dd = 0.0
    equity_curve = [{"time": None, "balance": round(balance, 2)}]
    wins, losses = [], []

    for t in trades:
        balance += t["profit"]
        equity_curve.append({"time": t["closed_at"], "balance": round(balance, 2)})
        peak = max(peak, balance)
        if peak > 0:
            max_dd = max(max_dd, (peak - balance) / peak)
        (wins if t["profit"] > 0 else losses).append(t)

    total_trades = len(trades)
    win_rate_pct = round(len(wins) / total_trades * 100, 2) if total_trades else 0.0
    total_profit = round(balance - starting_balance, 2)
    avg_win = round(sum(t["profit"] for t in wins) / len(wins), 2) if wins else 0.0
    avg_loss = round(sum(t["profit"] for t in losses) / len(losses), 2) if losses else 0.0
    gross_profit = sum(t["profit"] for t in wins)
    gross_loss = abs(sum(t["profit"] for t in losses))
    profit_factor = round(gross_profit / gross_loss, 4) if gross_loss > 0 else None

    return {
        "total_trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": win_rate_pct,
        "total_profit": total_profit,
        "max_drawdown_pct": round(max_dd * 100, 2),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "equity_curve": equity_curve,
        "trades": trades,
    }
