"""Tests for automation/property_scrape.py — the SPEC §12.1 property lane (M5).

The browser (fetch_html) is NEVER exercised here: parse_listings takes HTML
directly, so the suite needs no Playwright/Chromium. Covers card parse →
normalize, anti-bot fail-loud, genuine empty-result, the seen-set diff, persist
skip/roundtrip/Sheet-dedup, the Hebrew digest section, the saved-search config
loader, and the daily-digest fold-in.
"""
from datetime import date, datetime
from pathlib import Path

import pytest

from automation import property_scrape as P
from automation import templates as T
from automation.lib import config as cfg
from automation.lib import sheet

FIXTURES = Path(__file__).parent / "fixtures"


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Parse — embedded-JSON extraction + tolerant normalization
# ---------------------------------------------------------------------------
class TestParse:
    def test_parses_and_normalizes_cards(self):
        listings = P.parse_listings(_html("yad2_search.html"), "yad2")
        assert len(listings) == 3
        by_id = {li.listing_id: li for li in listings}

        a = by_id["yad2:abc123"]
        assert a.price_ils == 1_850_000 and a.rooms == 4 and a.size_sqm == 92
        assert "הרצליה" in a.location
        assert a.url == "https://www.yad2.co.il/item/abc123"

        # camelCase/Hebrew variants normalize the same way
        b = by_id["yad2:def456"]
        assert b.price_ils == 2_300_000 and b.rooms == 5 and b.size_sqm == 120
        assert b.url == "https://www.yad2.co.il/item/def456"   # relative → absolute

        # rooms parsed out of a Hebrew "3.5 חדרים" string
        assert by_id["yad2:ghi789"].rooms == 3.5

    def test_listing_id_namespaced_by_portal(self):
        listings = P.parse_listings(_html("yad2_search.html"), "yad2")
        assert all(li.listing_id.startswith("yad2:") for li in listings)

    def test_block_page_raises_blocked(self):
        with pytest.raises(P.BlockedError):
            P.parse_listings(_html("yad2_block.html"), "yad2")

    def test_empty_results_is_not_an_error(self):
        assert P.parse_listings(_html("yad2_empty.html"), "yad2") == []

    def test_promo_blocks_are_not_listings(self):
        """Embedded JSON is full of non-listing objects (promos, SEO, upsells).
        A non-numeric price or an id+title-only object must NOT become a row."""
        html = ('<script id="__NEXT_DATA__" type="application/json">'
                '{"items":['
                '{"id":"promo9","price":"חבילת פרימיום","title":"שדרגו עכשיו"},'
                '{"id":"seo1","title":"דירות למכירה בחיפה"},'
                '{"id":"real1","price":1750000,"rooms":4,"city":"חיפה","url":"/item/real1"}'
                ']}</script>')
        out = P.parse_listings(html, "yad2")
        assert [li.listing_id for li in out] == ["yad2:real1"]

    def test_detect_block_signatures(self):
        assert P.detect_block("<html>Just a moment...</html>")
        assert P.detect_block("<div>PerimeterX _px captcha</div>")
        assert not P.detect_block("<html>דירות למכירה בהרצליה</html>")


# ---------------------------------------------------------------------------
# Seen-set diff (the dedup key — SPEC §12.1)
# ---------------------------------------------------------------------------
class TestSeenDiff:
    def _listings(self):
        return [P.Listing("yad2:1", "yad2", 1_000_000, 3, 70, "א", ""),
                P.Listing("yad2:2", "yad2", 1_200_000, 4, 90, "ב", "")]

    def test_select_new_filters_seen_and_stamps(self):
        now = datetime(2026, 6, 16, 7, 10)
        new = P.select_new(self._listings(), seen={"yad2:1"}, now=now)
        assert [li.listing_id for li in new] == ["yad2:2"]
        assert new[0].first_seen == now.isoformat(timespec="seconds")

    def test_select_new_dedupes_within_batch(self):
        dup = self._listings() + [P.Listing("yad2:2", "yad2", 1_200_000, 4, 90, "ב", "")]
        new = P.select_new(dup, seen=set())
        assert [li.listing_id for li in new] == ["yad2:1", "yad2:2"]

    def test_seen_roundtrip(self, tmp_path):
        p = tmp_path / "seen.json"
        P.save_seen(p, {"yad2:1", "yad2:2"})
        assert P.load_seen(p) == {"yad2:1", "yad2:2"}

    def test_load_seen_missing_is_empty(self, tmp_path):
        assert P.load_seen(tmp_path / "nope.json") == set()


# ---------------------------------------------------------------------------
# Persist — lib/sheet append (D-016), skip-loud without a backend, Sheet dedup
# ---------------------------------------------------------------------------
class TestPersist:
    def _new(self):
        return [P.Listing("yad2:1", "yad2", 1_000_000, 3, 70, "הרצליה",
                          "https://www.yad2.co.il/item/1",
                          first_seen="2026-06-16T07:10:00")]

    def test_skips_loudly_without_backend(self, capsys):
        assert P.persist_new(self._new(), sheet_path=None, live_override=False) is False
        assert "NOT appended" in capsys.readouterr().out

    def test_roundtrip_and_sheet_dedup(self, tmp_path):
        from openpyxl import Workbook
        p = tmp_path / "s.xlsx"
        wb = Workbook(); wb.active.title = "README"; wb.save(p)

        assert P.persist_new(self._new(), sheet_path=p)
        assert sheet.read_column(cfg.PROPERTY_LISTINGS_TAB, "listing_id", p) == ["yad2:1"]

        # re-persisting the same id appends nothing (Sheet-side dedup guard, so
        # a lost seen.json can't double-write a listing)
        P.persist_new(self._new(), sheet_path=p)
        assert sheet.read_column(cfg.PROPERTY_LISTINGS_TAB, "listing_id", p) == ["yad2:1"]

    def test_row_shape_matches_columns(self):
        row = self._new()[0].to_row()
        assert list(row.keys()) == sheet.PROPERTY_LISTINGS_COLUMNS
        assert row["status"] == "new" and row["portal"] == "yad2"


# ---------------------------------------------------------------------------
# Digest section — "🏠 דירות חדשות" (DESIGN §6 copy, [Shanee review])
# ---------------------------------------------------------------------------
class TestDigestSection:
    def test_section_head_and_line(self):
        s = P.build_digest_section(
            [P.Listing("yad2:1", "yad2", 1_850_000, 4, 92, "הרצליה", "")])
        assert s.startswith(T.PROPERTY_SECTION_HEAD)
        assert "₪1,850,000" in s and "הרצליה" in s
        assert "4 חד׳" in s and "92 מ״ר" in s and "(yad2)" in s

    def test_empty_is_blank(self):
        assert P.build_digest_section([]) == ""

    def test_cheapest_first(self):
        many = [P.Listing(f"yad2:{i}", "yad2", price, 3, 60, f"loc{i}", "")
                for i, price in enumerate([3_000_000, 1_000_000, 2_000_000], start=1)]
        body = P.build_digest_section(many).splitlines()[1:]
        assert "loc2" in body[0]   # 1,000,000 — cheapest first

    def test_overflow_links_to_dashboard(self):
        many = [P.Listing(f"yad2:{i}", "yad2", 100_000 * i, 3, 60, f"loc{i}", "")
                for i in range(1, 11)]
        lines = P.build_digest_section(many, max_items=3).splitlines()
        assert len(lines) == 1 + 3 + 1            # head + 3 items + overflow line
        assert lines[-1].startswith("+7")         # DIGEST_MORE_IN_DASHBOARD, n=7

    def test_missing_facets_degrade_gracefully(self):
        s = P.build_digest_section(
            [P.Listing("yad2:9", "yad2", None, None, None, "", "")])
        assert T.PROPERTY_SECTION_HEAD in s and "₪?" in s   # no crash, no "None"
        assert "None" not in s


# ---------------------------------------------------------------------------
# Saved-search config loader
# ---------------------------------------------------------------------------
class TestLoadSearches:
    def test_reads_and_filters(self, tmp_path):
        p = tmp_path / "s.json"
        p.write_text('{"searches":['
                     '{"portal":"yad2","url":"http://x"},'
                     '{"portal":"bogus","url":"http://y"},'
                     '{"portal":"madlan","url":""}]}', encoding="utf-8")
        out = P.load_searches(p)
        assert [s["portal"] for s in out] == ["yad2"]   # bad portal + empty url dropped

    def test_missing_returns_empty(self, tmp_path):
        assert P.load_searches(tmp_path / "nope.json") == []


# ---------------------------------------------------------------------------
# Run — mock mode (no config, no browser), dry-run vs write, re-run dedup
# ---------------------------------------------------------------------------
class TestRun:
    def test_mock_dry_run_writes_nothing(self, tmp_runtime, capsys):
        res = P.run(dry_run=True, today=date(2026, 6, 16),
                    state_path=tmp_runtime / "seen.json",
                    briefings_dir=tmp_runtime / "Briefings")
        assert res.is_mock and len(res.new_listings) == 3
        assert "RUNNING IN MOCK MODE" in capsys.readouterr().out
        assert res.digest_path is None
        assert not (tmp_runtime / "seen.json").exists()

    def test_mock_run_persists_writes_digest_then_dedups(self, tmp_runtime):
        from openpyxl import Workbook
        bd = tmp_runtime / "Briefings"
        state = tmp_runtime / "seen.json"
        sp = tmp_runtime / "sheet.xlsx"
        wb = Workbook(); wb.active.title = "README"; wb.save(sp)

        res = P.run(dry_run=False, today=date(2026, 6, 16),
                    state_path=state, briefings_dir=bd, sheet_path=sp)
        f = bd / "property_listings_2026-06-16.md"
        assert res.digest_path == f and f.exists()
        assert T.PROPERTY_SECTION_HEAD in f.read_text(encoding="utf-8")
        assert sheet.read_column(cfg.PROPERTY_LISTINGS_TAB, "listing_id", sp) == \
            ["yad2:mock-1", "yad2:mock-2", "madlan:mock-3"]
        assert state.exists()   # seen-set advanced because rows were persisted

        # second run: ids now in seen.json → nothing new, no digest file
        res2 = P.run(dry_run=False, today=date(2026, 6, 16),
                     state_path=state, briefings_dir=bd, sheet_path=sp)
        assert res2.new_listings == [] and res2.digest_path is None

    def test_no_backend_does_not_advance_seen(self, tmp_runtime):
        """Anti-poison guard (review SHOULD-FIX #3): a non-dry run with no live
        backend skips the Sheet write, so the seen-set must NOT advance — else a
        later live run would treat the listings as already-seen and lose them."""
        bd = tmp_runtime / "Briefings"
        state = tmp_runtime / "seen.json"
        P.run(dry_run=False, today=date(2026, 6, 16),
              state_path=state, briefings_dir=bd, sheet_path=None)
        assert not state.exists()
        # so a later run still surfaces them as new (nothing was silently lost)
        res2 = P.run(dry_run=False, today=date(2026, 6, 16),
                     state_path=state, briefings_dir=bd, sheet_path=None)
        assert len(res2.new_listings) == 3

    def test_mock_with_live_sheet_fails_loud_writes_nothing(self, tmp_runtime, monkeypatch):
        """D-038: MOCK mode + a live Sheet configured (the appliance with
        property_searches.json missing) must fail loud and write NOTHING — never
        append the mock sample rows to the live Property-Listings tab."""
        from automation.lib import sheet
        monkeypatch.setattr(sheet, "is_live", lambda: True)
        state = tmp_runtime / "seen.json"
        bd = tmp_runtime / "Briefings"
        with pytest.raises(P.ScrapeError):
            P.run(dry_run=False, today=date(2026, 6, 16),
                  state_path=state, briefings_dir=bd, sheet_path=None)
        assert not state.exists()                       # seen-set NOT advanced
        assert not (bd.exists() and any(bd.glob("property_listings_*.md")))

    def test_html_fixture_path_with_error_raises(self, tmp_runtime):
        # a blocked page surfaces as a loud ScrapeError (systemd OnFailure)
        with pytest.raises(P.BlockedError):
            P.run(dry_run=True, today=date(2026, 6, 16),
                  html=_html("yad2_block.html"), portal="yad2",
                  state_path=tmp_runtime / "seen.json",
                  briefings_dir=tmp_runtime / "Briefings")


# ---------------------------------------------------------------------------
# Daily-digest fold-in — the section rides the 07:30 message (SPEC §12.1)
# ---------------------------------------------------------------------------
class TestDigestFoldIn:
    def test_assemble_includes_property_section(self, tmp_runtime, make_sheet):
        from automation import daily_digest

        bd = tmp_runtime / "Briefings"
        bd.mkdir(parents=True, exist_ok=True)
        (bd / "property_listings_2026-06-16.md").write_text(
            T.PROPERTY_SECTION_HEAD + "\nהרצליה — ₪1,850,000 (yad2)\n",
            encoding="utf-8")

        asm = daily_digest.assemble(
            date(2026, 6, 16), sheet_path=make_sheet([]),
            briefings_dir=bd, shabbat_times=None)
        assert T.PROPERTY_SECTION_HEAD in asm.messages["adar"]
