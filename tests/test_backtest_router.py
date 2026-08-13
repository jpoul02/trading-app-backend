import routers.backtest as backtest_router


def test_run_backtest_both_calls_trend_mean_reversion_and_fast(monkeypatch):
    calls = []

    def fake_run_single_backtest(symbol, timeframe, date_from, date_to, strategy, risk_pct, starting_balance):
        calls.append(strategy)
        return {"strategy": strategy}

    monkeypatch.setattr(backtest_router, "run_single_backtest", fake_run_single_backtest)

    req = backtest_router.BacktestRequest(
        symbol="EURUSD", timeframe="M15", date_from="2025-06-01", date_to="2026-08-01",
        strategy="both",
    )
    result = backtest_router.run_backtest(req)

    assert calls == ["trend", "mean_reversion", "fast"]
    assert set(result.keys()) == {"trend", "mean_reversion", "fast"}


def test_run_backtest_single_strategy_calls_once(monkeypatch):
    calls = []

    def fake_run_single_backtest(symbol, timeframe, date_from, date_to, strategy, risk_pct, starting_balance):
        calls.append(strategy)
        return {"strategy": strategy}

    monkeypatch.setattr(backtest_router, "run_single_backtest", fake_run_single_backtest)

    req = backtest_router.BacktestRequest(
        symbol="EURUSD", timeframe="M5", date_from="2025-06-01", date_to="2026-08-01",
        strategy="fast",
    )
    result = backtest_router.run_backtest(req)

    assert calls == ["fast"]
    assert result == {"strategy": "fast"}
