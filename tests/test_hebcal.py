"""Direct unit tests for automation/hebcal_client.chag_candles / _candle_items
(B2): the erev-chag candle-lighting accessor that daily_digest._hebcal_line
relies on. Hermetic — the month-calendar fetch is monkeypatched (no network);
these lock the parsing, eve-detection, and havdalah-bracketing logic that the
golden/dispatcher tests in test_render_golden.py only stub past."""

from datetime import date

import pytest
import requests

from automation import hebcal_client as hc

# A calendar-month payload as Hebcal returns it with c=on: a 'candles' item on
# each eve, a 'havdalah' item at each terminus, plus the 'holiday' rows
# chagim_in_range keeps (and _candle_items must ignore).
PAYLOAD = {"items": [
    {"category": "candles",  "date": "2026-06-10T19:10:00+03:00"},   # Wed erev-chag
    {"category": "havdalah", "date": "2026-06-11T20:15:00+03:00"},   # chag end
    {"category": "holiday",  "date": "2026-06-11", "yomtov": True, "title": "Chag"},
    {"category": "candles",  "date": "2026-06-12T19:26:00+03:00"},   # Fri Shabbat
    {"category": "havdalah", "date": "2026-06-13T20:37:00+03:00"},
]}


@pytest.fixture
def cached(monkeypatch):
    """Serve PAYLOAD from cache so _fetch_hebcal_month is never called (no net)."""
    monkeypatch.setattr(hc, "_cache_get", lambda key: PAYLOAD)
    monkeypatch.setattr(hc, "_fetch_hebcal_month",
                        lambda y, m: (_ for _ in ()).throw(AssertionError("network hit")))


def test_chag_candles_returns_eve_and_following_havdalah(cached):
    assert hc.chag_candles(date(2026, 6, 10)) == {
        "candle_lighting": "2026-06-10T19:10:00+03:00",
        "havdalah": "2026-06-11T20:15:00+03:00"}


def test_chag_candles_none_on_a_plain_day(cached):
    # No 'candles' item dated 2026-06-09 → not an eve → None, never a wrong line.
    assert hc.chag_candles(date(2026, 6, 9)) is None


def test_chag_candles_does_not_mistake_a_shabbat_in_window_for_an_eve(cached):
    # 2026-06-11 is a chag END; the next candles item (Fri 06-12 Shabbat) is in
    # the d..d+3 window but its date != d, so it is NOT returned here — the Friday
    # Shabbat line is shabbat_times()'s job, not chag_candles'.
    assert hc.chag_candles(date(2026, 6, 11)) is None


def test_chag_candles_none_when_no_havdalah_follows(monkeypatch):
    monkeypatch.setattr(hc, "_cache_get", lambda key:
                        {"items": [{"category": "candles",
                                    "date": "2026-06-10T19:10:00+03:00"}]})
    assert hc.chag_candles(date(2026, 6, 10)) is None


def test_chag_candles_degrades_quiet_on_fetch_failure(monkeypatch):
    monkeypatch.setattr(hc, "_cache_get", lambda key: None)

    def boom(y, m):
        raise requests.RequestException("boom")

    monkeypatch.setattr(hc, "_fetch_hebcal_month", boom)
    assert hc.chag_candles(date(2026, 6, 10)) is None
