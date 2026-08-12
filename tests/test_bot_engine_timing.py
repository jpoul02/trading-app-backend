from datetime import datetime, timezone
import bot_engine


def test_sleep_seconds_for_m15_mid_interval():
    now = datetime(2026, 8, 11, 10, 7, 0, tzinfo=timezone.utc)
    seconds = bot_engine.next_candle_sleep_seconds("M15", now=now)
    assert seconds == 8 * 60  # next boundary at 10:15


def test_sleep_seconds_for_h1_near_boundary():
    now = datetime(2026, 8, 11, 10, 59, 30, tzinfo=timezone.utc)
    seconds = bot_engine.next_candle_sleep_seconds("H1", now=now)
    assert seconds == 30


def test_sleep_seconds_minimum_is_five_seconds():
    now = datetime(2026, 8, 11, 10, 15, 0, tzinfo=timezone.utc)
    seconds = bot_engine.next_candle_sleep_seconds("M15", now=now)
    assert seconds >= 5  # never busy-loop at exactly the boundary
