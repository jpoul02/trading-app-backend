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
