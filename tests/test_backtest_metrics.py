import backtest_engine


def test_no_trades_returns_empty_metrics():
    result = backtest_engine.compute_backtest_metrics([], starting_balance=100000)

    assert result["total_trades"] == 0
    assert result["win_rate_pct"] == 0.0
    assert result["total_profit"] == 0.0
    assert result["profit_factor"] is None
    assert result["max_drawdown_pct"] == 0.0
    assert len(result["equity_curve"]) == 1


def test_mixed_wins_and_losses():
    trades = [
        {"profit": 100.0, "closed_at": 1},
        {"profit": -50.0, "closed_at": 2},
        {"profit": 200.0, "closed_at": 3},
    ]

    result = backtest_engine.compute_backtest_metrics(trades, starting_balance=1000)

    assert result["total_trades"] == 3
    assert result["wins"] == 2
    assert result["losses"] == 1
    assert round(result["win_rate_pct"], 2) == 66.67
    assert result["total_profit"] == 250.0
    assert result["avg_win"] == 150.0
    assert result["avg_loss"] == -50.0
    assert result["profit_factor"] == 6.0  # 300 gross profit / 50 gross loss


def test_drawdown_tracks_peak_to_trough():
    # balance: 1000 -> 1100 (peak) -> 1050 (dd = 50/1100 = 4.545...%) -> 1250 (new peak)
    trades = [
        {"profit": 100.0, "closed_at": 1},
        {"profit": -50.0, "closed_at": 2},
        {"profit": 200.0, "closed_at": 3},
    ]

    result = backtest_engine.compute_backtest_metrics(trades, starting_balance=1000)

    assert result["max_drawdown_pct"] == 4.55


def test_profit_factor_none_when_no_losses():
    trades = [{"profit": 100.0, "closed_at": 1}]

    result = backtest_engine.compute_backtest_metrics(trades, starting_balance=1000)

    assert result["profit_factor"] is None


def test_equity_curve_has_one_point_per_trade_plus_start():
    trades = [{"profit": 10.0, "closed_at": 1}, {"profit": -5.0, "closed_at": 2}]

    result = backtest_engine.compute_backtest_metrics(trades, starting_balance=1000)

    assert len(result["equity_curve"]) == 3
    assert result["equity_curve"][0]["balance"] == 1000
    assert result["equity_curve"][1]["balance"] == 1010
    assert result["equity_curve"][2]["balance"] == 1005
