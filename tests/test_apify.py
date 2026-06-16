"""Tests for the Apify SECONDARY source (automation/lib/apify.py, D-040).

The network (`_run_actor`) is NEVER called here: `fetch_listings` takes a
`runner` override, exactly as `property_scrape` never drives the real browser.
Covers the two actor adapters (amit123 Yad2, swerve Madlan) against their
documented schemas, strict fail-loud on missing-id / corrupt numerics,
honest-empty on absent optionals, the token gate, actor-input synthesis (Yad2
from a url, Madlan requires params), the primary→secondary merge, the
backup-vs-gap-fill error policy, and the once/day cost gate — the last three via
property_scrape.run with a fake runner.
"""
from datetime import date

import pytest

from automation import property_scrape as P
from automation.lib import apify
from automation.lib import config as cfg

# Sample dataset items = the actors' DOCUMENTED output schemas (verify-live seam).
YAD2_ITEM = {
    "item_id": "abc123", "item_url": "https://www.yad2.co.il/item/abc123",
    "price": 1_850_000, "rooms": 4, "square_meter": 92,
    "location": "הרצליה, מרכז", "floor": 3,
}
YAD2_ITEM2 = {
    "item_id": "def456", "item_url": "https://www.yad2.co.il/item/def456",
    "price": 2_300_000, "rooms": 5, "square_meter": 120, "location": "רעננה",
}
MADLAN_ITEM = {
    "id": "m-555", "url": "https://www.madlan.co.il/listings/m-555",
    "price": 2_300_000, "rooms": 5, "areaSqm": 120,
    "address": "ויצמן 10", "neighbourhood": "מרכז", "cityHebrew": "כפר סבא",
}


class _FakeRunner:
    """Stands in for apify._run_actor: records the call and returns canned items."""
    def __init__(self, items):
        self.items = items
        self.calls = []

    def __call__(self, actor_id, payload, *, api_token, timeout_s):
        self.calls.append({"actor_id": actor_id, "payload": payload,
                           "api_token": api_token})
        return list(self.items)


# ---------------------------------------------------------------------------
# Adapters — dataset item -> Listing, strict
# ---------------------------------------------------------------------------
class TestAdapters:
    def test_yad2_maps_documented_fields(self):
        li = apify._adapt_yad2(YAD2_ITEM)
        assert li.listing_id == "yad2:abc123" and li.portal == "yad2"
        assert li.price_ils == 1_850_000 and li.rooms == 4.0 and li.size_sqm == 92
        assert li.location == "הרצליה, מרכז"
        assert li.url == "https://www.yad2.co.il/item/abc123"

    def test_madlan_maps_and_composes_location(self):
        li = apify._adapt_madlan(MADLAN_ITEM)
        assert li.listing_id == "madlan:m-555" and li.portal == "madlan"
        assert li.price_ils == 2_300_000 and li.rooms == 5.0 and li.size_sqm == 120
        assert li.location == "ויצמן 10, מרכז"      # first two parts only
        assert li.url.endswith("/m-555")

    def test_missing_id_raises(self):
        bad = {k: v for k, v in YAD2_ITEM.items() if k != "item_id"}
        with pytest.raises(apify.ApifyItemError):
            apify._adapt_yad2(bad)

    def test_corrupt_price_raises_not_invented(self):
        with pytest.raises(apify.ApifyItemError):
            apify._adapt_yad2({**YAD2_ITEM, "price": "חבילת פרימיום"})

    def test_bool_in_numeric_field_is_corrupt(self):
        with pytest.raises(apify.ApifyItemError):
            apify._adapt_yad2({**YAD2_ITEM, "price": True})

    def test_absent_optional_is_empty_not_error(self):
        li = apify._adapt_yad2({"item_id": "x", "item_url": "u", "price": 100})
        assert li.rooms is None and li.size_sqm is None and li.location == ""

    def test_numeric_string_with_commas_ok(self):
        li = apify._adapt_yad2({**YAD2_ITEM, "price": "1,850,000"})
        assert li.price_ils == 1_850_000

    def test_zero_is_honest_absent_not_fake_zero(self):
        li = apify._adapt_yad2({**YAD2_ITEM, "price": 0})
        assert li.price_ils is None          # 0 = price-on-request, not a real ₪0

    def test_negative_is_corrupt(self):
        with pytest.raises(apify.ApifyItemError):
            apify._adapt_yad2({**YAD2_ITEM, "square_meter": -5})


class TestAdaptItems:
    def test_collects_item_errors_keeps_good(self):
        items = [YAD2_ITEM, {"item_url": "u"},                       # no id
                 {"item_id": "z", "item_url": "u2", "price": "junk"}]  # corrupt
        listings, errors = apify.adapt_items("yad2", items)
        assert [li.listing_id for li in listings] == ["yad2:abc123"]
        assert len(errors) == 2

    def test_non_dict_item_is_error(self):
        listings, errors = apify.adapt_items("yad2", [YAD2_ITEM, "oops"])
        assert len(listings) == 1 and len(errors) == 1


# ---------------------------------------------------------------------------
# Token gate
# ---------------------------------------------------------------------------
class TestTokenGate:
    def test_unconfigured_without_token(self):
        assert apify.is_configured(env={}) is False

    def test_configured_with_token(self):
        assert apify.is_configured(env={cfg.APIFY_TOKEN_ENV: "tok"}) is True


# ---------------------------------------------------------------------------
# fetch_listings — input synthesis + transport guards (no network)
# ---------------------------------------------------------------------------
class TestFetchListings:
    def test_no_token_fails_loud(self):
        with pytest.raises(apify.ApifyError):
            apify.fetch_listings("yad2", {"url": "U"}, api_token="",
                                 runner=_FakeRunner([]))

    def test_unknown_portal_fails_loud(self):
        with pytest.raises(apify.ApifyError):
            apify.fetch_listings("zillow", {"url": "U"}, api_token="t",
                                 runner=_FakeRunner([]))

    def test_yad2_synthesizes_start_urls(self):
        r = _FakeRunner([YAD2_ITEM])
        listings, errors = apify.fetch_listings(
            "yad2", {"url": "https://yad2/X"}, api_token="t", runner=r)
        assert r.calls[0]["actor_id"] == "amit123~yadscraper"
        assert r.calls[0]["payload"]["start_urls"] == [{"url": "https://yad2/X"}]
        assert r.calls[0]["payload"]["maxPagesPerSearch"] == cfg.PROPERTY_APIFY_MAX_PAGES
        assert len(listings) == 1 and errors == []

    def test_madlan_requires_params(self):
        with pytest.raises(apify.ApifyError):
            apify.fetch_listings("madlan", {"url": "U"}, api_token="t",
                                 runner=_FakeRunner([]))

    def test_madlan_with_params_builds_payload(self):
        r = _FakeRunner([MADLAN_ITEM])
        search = {"url": "U", "apify": {"city": "Kfar Saba", "dealType": "buy"}}
        listings, _ = apify.fetch_listings("madlan", search, api_token="t", runner=r)
        p = r.calls[0]["payload"]
        assert r.calls[0]["actor_id"] == "swerve~madlan-scraper"
        assert p["city"] == "Kfar Saba" and p["dealType"] == "buy"
        assert p["maxItems"] == cfg.PROPERTY_APIFY_MAX_ITEMS
        assert len(listings) == 1

    def test_yad2_override_merges_over_default_keeps_proxy(self):
        r = _FakeRunner([])
        apify.fetch_listings("yad2", {"url": "U", "apify": {"maxPagesPerSearch": 1}},
                             api_token="t", runner=r)
        p = r.calls[0]["payload"]
        assert p["maxPagesPerSearch"] == 1                  # override wins
        assert p["proxy"]["apifyProxyCountry"] == "IL"      # proxy NOT dropped (D-2)
        assert p["start_urls"] == [{"url": "U"}]            # url still synthesized


# ---------------------------------------------------------------------------
# Merge — primary wins, fills gaps, adds new (property_scrape.merge_listings)
# ---------------------------------------------------------------------------
class TestMerge:
    def test_primary_wins_fills_gaps_adds_new(self):
        primary = [P.Listing("yad2:1", "yad2", 100, 4, None, "", "u1")]
        secondary = [
            P.Listing("yad2:1", "yad2", 999, 9, 80, "Loc", "u1b"),  # dup id
            P.Listing("yad2:2", "yad2", 200, 3, 70, "L2", "u2"),    # new
        ]
        merged = P.merge_listings(primary, secondary)
        by_id = {li.listing_id: li for li in merged}
        m1 = by_id["yad2:1"]
        assert m1.price_ils == 100 and m1.rooms == 4 and m1.url == "u1"  # primary won
        assert m1.size_sqm == 80 and m1.location == "Loc"               # gaps filled
        assert "yad2:2" in by_id and len(merged) == 2                   # new added

    def test_missing_fields_detection(self):
        full = P.Listing("yad2:1", "yad2", 100, 4, 80, "L", "u")
        gappy = P.Listing("yad2:1", "yad2", 100, 4, None, "L", "u")
        assert P._missing_fields(full) is False
        assert P._missing_fields(gappy) is True


# ---------------------------------------------------------------------------
# Integration via property_scrape.run — fake runner, simulated blocked primary
# ---------------------------------------------------------------------------
def _blocked(*a, **k):
    raise P.BlockedError("simulated anti-bot block")


def _searches_file(tmp_path, entries):
    import json
    p = tmp_path / "property_searches.json"
    p.write_text(json.dumps({"searches": entries}), encoding="utf-8")
    return p


def _xlsx(tmp_path):
    from openpyxl import Workbook
    p = tmp_path / "sheet.xlsx"
    wb = Workbook(); wb.active.title = "README"; wb.save(p)
    return p


class TestRunIntegration:
    def test_primary_blocked_uses_apify_backup(self, tmp_path, monkeypatch):
        monkeypatch.setattr(P, "fetch_html", _blocked)
        sfile = _searches_file(tmp_path, [{"portal": "yad2", "url": "U", "label": "t"}])
        r = _FakeRunner([YAD2_ITEM, YAD2_ITEM2])
        stamp = tmp_path / "apify_last_run.json"
        res = P.run(today=date(2026, 6, 16), searches_path=sfile,
                    state_path=tmp_path / "seen.json",
                    briefings_dir=tmp_path / "Briefings", sheet_path=_xlsx(tmp_path),
                    apify_enabled=True, apify_token="t", apify_runner=r,
                    apify_stamp_path=stamp)
        assert res.used_apify and res.errors == []
        assert {li.listing_id for li in res.new_listings} == {"yad2:abc123", "yad2:def456"}
        assert res.digest_path and res.digest_path.exists()
        assert stamp.exists()                       # once/day gate stamped on write
        assert len(r.calls) == 1

    def test_primary_blocked_no_apify_fails_loud(self, tmp_path, monkeypatch):
        monkeypatch.setattr(P, "fetch_html", _blocked)
        sfile = _searches_file(tmp_path, [{"portal": "yad2", "url": "U"}])
        with pytest.raises(P.ScrapeError):
            P.run(today=date(2026, 6, 16), searches_path=sfile,
                  state_path=tmp_path / "seen.json",
                  briefings_dir=tmp_path / "Briefings", sheet_path=_xlsx(tmp_path),
                  apify_enabled=False)

    def test_once_per_day_skips_second_run_no_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(P, "fetch_html", _blocked)
        sfile = _searches_file(tmp_path, [{"portal": "yad2", "url": "U"}])
        r = _FakeRunner([YAD2_ITEM])
        stamp = tmp_path / "apify_last_run.json"
        sp = _xlsx(tmp_path)
        common = dict(today=date(2026, 6, 16), searches_path=sfile,
                      state_path=tmp_path / "seen.json",
                      briefings_dir=tmp_path / "Briefings", sheet_path=sp,
                      apify_enabled=True, apify_token="t", apify_runner=r,
                      apify_stamp_path=stamp)
        P.run(**common)                              # morning: calls apify, stamps
        res2 = P.run(**common)                       # evening: gate closed
        assert len(r.calls) == 1                     # not charged twice
        assert res2.errors == [] and res2.used_apify is False  # no fail-flag

    def test_gapfill_fills_missing_field(self, tmp_path, monkeypatch):
        # primary returns a listing missing size_sqm → gap-fill from Apify
        monkeypatch.setattr(P, "fetch_html", lambda *a, **k: "html")
        monkeypatch.setattr(P, "parse_listings",
                            lambda html, portal: [P.Listing(
                                "yad2:abc123", "yad2", 1_850_000, 4, None,
                                "הרצליה, מרכז", "u")])
        sfile = _searches_file(tmp_path, [{"portal": "yad2", "url": "U"}])
        r = _FakeRunner([YAD2_ITEM])                 # has square_meter 92
        res = P.run(today=date(2026, 6, 16), searches_path=sfile,
                    state_path=tmp_path / "seen.json",
                    briefings_dir=tmp_path / "Briefings", sheet_path=_xlsx(tmp_path),
                    apify_enabled=True, apify_token="t", apify_runner=r,
                    apify_stamp_path=tmp_path / "stamp.json")
        assert res.used_apify and len(r.calls) == 1
        assert res.all_listings[0].size_sqm == 92    # blank filled, primary kept
        assert res.all_listings[0].price_ils == 1_850_000

    def test_gapfill_does_not_consume_backup_budget(self, tmp_path, monkeypatch):
        # CRITICAL (review): a morning GAP-FILL must NOT spend the once/day budget
        # and silently suppress a later BACKUP when the primary goes dark.
        sfile = _searches_file(tmp_path, [{"portal": "yad2", "url": "U"}])
        stamp = tmp_path / "stamp.json"
        sp = _xlsx(tmp_path)
        common = dict(today=date(2026, 6, 16), searches_path=sfile,
                      state_path=tmp_path / "seen.json",
                      briefings_dir=tmp_path / "Briefings", sheet_path=sp,
                      apify_enabled=True, apify_token="t", apify_stamp_path=stamp)

        # morning: primary OK but gappy → gap-fill fires (stamps gapfill only)
        monkeypatch.setattr(P, "fetch_html", lambda *a, **k: "html")
        monkeypatch.setattr(P, "parse_listings", lambda html, portal: [
            P.Listing("yad2:1", "yad2", 100, 4, None, "loc", "u")])
        r_gap = _FakeRunner([{"item_id": "1", "item_url": "u", "price": 100,
                              "rooms": 4, "square_meter": 80, "location": "loc"}])
        res1 = P.run(apify_runner=r_gap, **common)
        assert res1.used_apify and len(r_gap.calls) == 1   # gap-fill happened

        # evening: primary now BLOCKED → backup must STILL fire (budget intact)
        monkeypatch.setattr(P, "fetch_html", _blocked)
        r_bak = _FakeRunner([YAD2_ITEM, YAD2_ITEM2])
        res2 = P.run(apify_runner=r_bak, **common)
        assert res2.used_apify and len(r_bak.calls) == 1   # backup NOT suppressed
        assert res2.errors == []
        assert {li.listing_id for li in res2.new_listings} == {"yad2:abc123", "yad2:def456"}

    def test_both_sources_down_fails_loud(self, tmp_path, monkeypatch):
        # primary blocked AND Apify backup raises → the run must fail loud
        monkeypatch.setattr(P, "fetch_html", _blocked)

        def _boom(*a, **k):
            raise apify.ApifyError("apify down")

        sfile = _searches_file(tmp_path, [{"portal": "yad2", "url": "U"}])
        with pytest.raises(P.ScrapeError):
            P.run(today=date(2026, 6, 16), searches_path=sfile,
                  state_path=tmp_path / "seen.json",
                  briefings_dir=tmp_path / "Briefings", sheet_path=_xlsx(tmp_path),
                  apify_enabled=True, apify_token="t", apify_runner=_boom,
                  apify_stamp_path=tmp_path / "stamp.json")

    def test_gapfill_failure_is_best_effort_not_loud(self, tmp_path, monkeypatch):
        # primary OK but a field is missing → gap-fill wanted; Apify fails → the
        # primary data STANDS, the run succeeds (no fail-flag), nothing invented.
        monkeypatch.setattr(P, "fetch_html", lambda *a, **k: "html")
        monkeypatch.setattr(P, "parse_listings",
                            lambda html, portal: [P.Listing(
                                "yad2:1", "yad2", 100, 4, None, "loc", "u")])

        def _boom(*a, **k):
            raise apify.ApifyError("apify down")

        sfile = _searches_file(tmp_path, [{"portal": "yad2", "url": "U"}])
        res = P.run(today=date(2026, 6, 16), searches_path=sfile,
                    state_path=tmp_path / "seen.json",
                    briefings_dir=tmp_path / "Briefings", sheet_path=_xlsx(tmp_path),
                    apify_enabled=True, apify_token="t", apify_runner=_boom,
                    apify_stamp_path=tmp_path / "stamp.json")
        assert res.errors == []                       # best-effort, no fail-flag
        assert res.all_listings[0].size_sqm is None   # primary stands, not invented

    def test_backup_item_errors_best_effort_when_usable(self, tmp_path, monkeypatch):
        # D-042: a backup returning SOME usable listings plus a junk row (no id)
        # skips the junk and succeeds — a few dirty rows are not a run failure.
        monkeypatch.setattr(P, "fetch_html", _blocked)
        sfile = _searches_file(tmp_path, [{"portal": "yad2", "url": "U"}])
        r = _FakeRunner([YAD2_ITEM, {"item_url": "u-no-id"}])   # 1 good, 1 junk
        res = P.run(today=date(2026, 6, 16), searches_path=sfile,
                    state_path=tmp_path / "seen.json",
                    briefings_dir=tmp_path / "Briefings", sheet_path=_xlsx(tmp_path),
                    apify_enabled=True, apify_token="t", apify_runner=r,
                    apify_stamp_path=tmp_path / "stamp.json")
        assert res.errors == []                        # junk warned, not fatal
        assert {li.listing_id for li in res.new_listings} == {"yad2:abc123"}

    def test_gapfill_item_errors_best_effort(self, tmp_path, monkeypatch):
        # D-042: a gap-fill whose actor returns a junk row alongside a usable one
        # never fails the run; the primary stands and the good row enriches it.
        monkeypatch.setattr(P, "fetch_html", lambda *a, **k: "html")
        monkeypatch.setattr(P, "parse_listings",
                            lambda html, portal: [P.Listing(
                                "yad2:abc123", "yad2", 1_850_000, 4, None,
                                "loc", "u")])
        sfile = _searches_file(tmp_path, [{"portal": "yad2", "url": "U"}])
        r = _FakeRunner([YAD2_ITEM, {"item_url": "u-no-id"}])   # good enriches, junk skipped
        res = P.run(today=date(2026, 6, 16), searches_path=sfile,
                    state_path=tmp_path / "seen.json",
                    briefings_dir=tmp_path / "Briefings", sheet_path=_xlsx(tmp_path),
                    apify_enabled=True, apify_token="t", apify_runner=r,
                    apify_stamp_path=tmp_path / "stamp.json")
        assert res.errors == []
        assert res.all_listings[0].size_sqm == 92      # enriched from the good row

    def test_apify_all_items_bad_fails_loud(self, tmp_path, monkeypatch):
        # D-042: items returned but ZERO usable (every row id-less) = broken
        # adapter / schema drift → still fail loud (the one case that survives).
        monkeypatch.setattr(P, "fetch_html", _blocked)
        sfile = _searches_file(tmp_path, [{"portal": "yad2", "url": "U"}])
        r = _FakeRunner([{"item_url": "u1"}, {"item_url": "u2"}])   # all id-less
        with pytest.raises(P.ScrapeError):
            P.run(today=date(2026, 6, 16), searches_path=sfile,
                  state_path=tmp_path / "seen.json",
                  briefings_dir=tmp_path / "Briefings", sheet_path=_xlsx(tmp_path),
                  apify_enabled=True, apify_token="t", apify_runner=r,
                  apify_stamp_path=tmp_path / "stamp.json")


class TestSearchConfigCarriesApify:
    def test_apify_block_preserved_through_loader(self, tmp_path):
        import json
        p = tmp_path / "property_searches.json"
        p.write_text(json.dumps({"searches": [
            {"portal": "madlan", "url": "U",
             "apify": {"city": "Kfar Saba", "dealType": "buy"}}]}), encoding="utf-8")
        out = P.load_searches(p)
        assert out[0]["apify"] == {"city": "Kfar Saba", "dealType": "buy"}
