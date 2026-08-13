import bot_engine


class _FakeObsidian:
    def __init__(self):
        self.opened_calls = []

    def write_trade_opened(self, trade):
        self.opened_calls.append(trade)
        return "Trades/fake.md"


def test_build_symbol_meta_extracts_expected_fields():
    class _Info:
        trade_tick_value = 1.0
        trade_tick_size = 0.00001
        volume_step = 0.01
        volume_min = 0.01

    meta = bot_engine._build_symbol_meta(_Info())

    assert meta == {"tick_value": 1.0, "tick_size": 0.00001, "volume_step": 0.01, "volume_min": 0.01}


def test_record_trade_result_logs_opened_trade():
    logged = []
    fake_obsidian = _FakeObsidian()
    result = {
        "action": "opened", "ticket": 111, "direction": "buy", "volume": 0.05,
        "price": 1.1000, "sl": 1.0950, "tp": 1.1100, "signal_reason": "test",
    }

    bot_engine._record_trade_result(
        "fast", "EURUSD", result, fake_obsidian,
        log_trade_fn=lambda **kw: logged.append(kw),
    )

    assert len(logged) == 1
    assert logged[0]["mode"] == "fast"
    assert logged[0]["status"] == "open"
    assert logged[0]["obsidian_path"] == "Trades/fake.md"
    assert len(fake_obsidian.opened_calls) == 1


def test_record_trade_result_logs_rejected_trade():
    logged = []
    result = {"action": "rejected", "reason": "no money"}

    bot_engine._record_trade_result(
        "trend", "EURUSD", result, _FakeObsidian(),
        log_trade_fn=lambda **kw: logged.append(kw),
    )

    assert len(logged) == 1
    assert logged[0]["status"] == "rejected"
    assert logged[0]["signal_reason"] == "no money"


def test_record_trade_result_does_nothing_when_no_action():
    logged = []
    result = {"action": "none", "reason": "no_strong_signal"}

    bot_engine._record_trade_result("trend", "EURUSD", result, _FakeObsidian(), log_trade_fn=lambda **kw: logged.append(kw))

    assert logged == []
