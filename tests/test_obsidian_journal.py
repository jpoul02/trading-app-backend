import os
import obsidian_journal


def _trade(**overrides):
    base = {
        "symbol": "EURUSD",
        "mode": "trend",
        "action": "buy",
        "volume": 0.06,
        "price": 1.15369,
        "sl": 1.15219,
        "tp": 1.15594,
        "opened_at": "2026-08-11T14:32:00",
        "signal_reason": "RSI sobrevendido (25.6) + MACD positivo — posible rebote",
    }
    base.update(overrides)
    return base


def test_write_trade_opened_creates_file_with_frontmatter(tmp_path):
    path = obsidian_journal.write_trade_opened(_trade(), vault_path=str(tmp_path))

    assert os.path.exists(path)
    content = open(path, encoding="utf-8").read()
    assert "symbol: EURUSD" in content
    assert "mode: trend" in content
    assert "status: open" in content
    assert "RSI sobrevendido" in content


def test_write_trade_opened_filename_includes_symbol_and_timestamp(tmp_path):
    path = obsidian_journal.write_trade_opened(_trade(symbol="GBPUSD"), vault_path=str(tmp_path))
    filename = os.path.basename(path)
    assert filename.startswith("GBPUSD-20260811-143200")
    assert filename.endswith(".md")


def test_write_trade_opened_places_file_in_trades_subfolder(tmp_path):
    path = obsidian_journal.write_trade_opened(_trade(), vault_path=str(tmp_path))
    assert os.path.dirname(path) == os.path.join(str(tmp_path), "Trades")


def test_write_trade_closed_updates_status_and_adds_result(tmp_path):
    path = obsidian_journal.write_trade_opened(_trade(), vault_path=str(tmp_path))

    obsidian_journal.write_trade_closed(path, profit=12.5, closed_at="2026-08-11T15:10:00")

    content = open(path, encoding="utf-8").read()
    assert "status: closed" in content
    assert "status: open" not in content
    assert "profit: 12.5" in content
    assert "closed_at: 2026-08-11T15:10:00" in content
    assert "## Resultado" in content
    assert "+12.5" in content


def test_write_trade_closed_shows_negative_profit_without_plus_sign(tmp_path):
    path = obsidian_journal.write_trade_opened(_trade(), vault_path=str(tmp_path))

    obsidian_journal.write_trade_closed(path, profit=-8.2, closed_at="2026-08-11T15:10:00")

    content = open(path, encoding="utf-8").read()
    assert "-8.2" in content
    assert "+-8.2" not in content
