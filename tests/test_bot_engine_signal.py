import pandas as pd
import bot_engine


def _df_with_last_row(rsi, macd_hist, close=1.1000, atr=0.0012):
    # compute_signal only reads the last row — pad a few earlier rows so
    # iloc[-1] behaves like it would on a real multi-row indicator frame.
    rows = [
        {"close": 1.0990, "rsi": 50.0, "macd_hist": 0.0, "atr": atr},
        {"close": 1.0995, "rsi": 50.0, "macd_hist": 0.0, "atr": atr},
        {"close": close, "rsi": rsi, "macd_hist": macd_hist, "atr": atr},
    ]
    return pd.DataFrame(rows)


def test_strong_buy_signal_when_oversold_and_macd_positive():
    df = _df_with_last_row(rsi=25.0, macd_hist=0.0005)
    result = bot_engine.compute_signal(df)
    assert result["signal"] == "COMPRAR FUERTE"
    assert "sobrevendido" in result["signal_reason"]


def test_bullish_trend_signal_when_rsi_favorable():
    df = _df_with_last_row(rsi=40.0, macd_hist=0.0)
    result = bot_engine.compute_signal(df)
    assert result["signal"] == "TENDENCIA ALCISTA"


def test_strong_sell_signal_when_overbought_and_macd_negative():
    df = _df_with_last_row(rsi=75.0, macd_hist=-0.0005)
    result = bot_engine.compute_signal(df)
    assert result["signal"] == "VENDER FUERTE"
    assert "sobrecomprado" in result["signal_reason"]


def test_bearish_trend_signal_when_rsi_cautious():
    df = _df_with_last_row(rsi=60.0, macd_hist=0.0)
    result = bot_engine.compute_signal(df)
    assert result["signal"] == "TENDENCIA BAJISTA"


def test_wait_signal_when_rsi_neutral():
    df = _df_with_last_row(rsi=50.0, macd_hist=0.0)
    result = bot_engine.compute_signal(df)
    assert result["signal"] == "ESPERAR"


def test_signal_uses_nan_safe_defaults():
    df = _df_with_last_row(rsi=float("nan"), macd_hist=float("nan"))
    result = bot_engine.compute_signal(df)
    assert result["last_rsi"] == 50.0
    assert result["last_macd_hist"] == 0.0
    assert result["signal"] == "ESPERAR"


def test_add_indicators_adds_expected_columns():
    rates = [
        {"time": 1000 + i * 60, "open": 1.10 + i * 0.0001, "high": 1.1005 + i * 0.0001,
         "low": 1.0995 + i * 0.0001, "close": 1.10 + i * 0.0001, "tick_volume": 100}
        for i in range(60)
    ]
    df = pd.DataFrame(rates)
    result = bot_engine.add_indicators(df)
    for col in ["sma20", "sma50", "rsi", "macd", "macd_signal", "macd_hist",
                "bb_upper", "bb_mid", "bb_lower", "atr"]:
        assert col in result.columns


def test_add_indicators_adds_stochastic_columns():
    rates = [
        {"time": 1000 + i * 60, "open": 1.10 + i * 0.0001, "high": 1.1005 + i * 0.0001,
         "low": 1.0995 + i * 0.0001, "close": 1.10 + i * 0.0001, "tick_volume": 100}
        for i in range(60)
    ]
    df = pd.DataFrame(rates)
    result = bot_engine.add_indicators(df)
    assert "stoch_k" in result.columns
    assert "stoch_d" in result.columns
