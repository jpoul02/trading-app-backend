import bot_engine


def test_find_closed_trades_returns_tickets_no_longer_live():
    open_trades = [
        {"id": 1, "ticket": 100, "symbol": "EURUSD"},
        {"id": 2, "ticket": 200, "symbol": "GBPUSD"},
        {"id": 3, "ticket": 300, "symbol": "USDJPY"},
    ]
    live_tickets = {100, 300}

    closed = bot_engine.find_closed_trades(open_trades, live_tickets)

    assert len(closed) == 1
    assert closed[0]["ticket"] == 200


def test_find_closed_trades_ignores_rows_without_ticket():
    open_trades = [{"id": 1, "ticket": None, "symbol": "EURUSD"}]
    closed = bot_engine.find_closed_trades(open_trades, live_tickets=set())
    assert closed == []


def test_find_closed_trades_empty_when_all_still_live():
    open_trades = [{"id": 1, "ticket": 100, "symbol": "EURUSD"}]
    closed = bot_engine.find_closed_trades(open_trades, live_tickets={100})
    assert closed == []
