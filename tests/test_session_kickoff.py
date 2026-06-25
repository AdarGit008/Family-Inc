"""Focus-selection for the next-session prompt generator.

Guards the fix for the old trap where the focus headline was whatever section was
literally titled '## In progress', which hid an actively-built lane filed under
another header (e.g. the v3 dashboard lane under '## v1.1 candidates').
"""

from automation.session_kickoff import (
    PIN_RE,
    current_milestone,
    focus,
    in_progress_lanes,
)

BACKLOG_WITH_PIN = """# Backlog

## Now

**▶ Focus:** v3 redesign — V3.2 scaffold + pill.
<!-- ^ steers the headline -->

Some prose.

## In progress — M6 finance ingestion

- 🔵 **M6.3 — consumer wiring.** acceptance-gated stuff.
- ⬜ **Parallel (Shanee).** budget migration.

## v1.1 candidates

- **🔵 v3 Today redesign (building).** bold-wrapped marker, like real BACKLOG.
"""

BACKLOG_NO_PIN = """# Backlog

## In progress — M6 finance ingestion

- 🔵 **M6.3 — consumer wiring.** stuff.

## v1.1 candidates

- 🔵 **v3 Today redesign (building).** the dashboard lane.
- ⬜ **something queued.**
"""

BACKLOG_FALLBACK = """# Backlog

## In progress — M6 finance ingestion

- ⬜ **M6.x todo only.** no in-progress here.

## Other

- ⬜ **also todo.**
"""


def test_pin_wins_over_section_heuristic():
    headline, lanes = focus(BACKLOG_WITH_PIN)
    assert headline == "v3 redesign — V3.2 scaffold + pill."
    # the active-lane list still surfaces every 🔵 lane across sections, for context
    assert any("M6.3" in ln for ln in lanes)
    assert any("v3 Today redesign" in ln for ln in lanes)


def test_in_progress_lanes_span_all_sections():
    # both the 'In progress' section AND the v1.1-candidates lane, not one section
    lanes = in_progress_lanes(BACKLOG_WITH_PIN)
    assert len(lanes) == 2
    assert any("v3 Today redesign" in ln for ln in lanes)


def test_no_pin_leads_with_first_blue_lane():
    headline, lanes = focus(BACKLOG_NO_PIN)
    assert "M6.3" in headline  # first 🔵 in document order
    assert len(lanes) == 2  # the ⬜ queued item is not an active lane


def test_fallback_to_section_when_no_pin_no_blue():
    headline, lanes = focus(BACKLOG_FALLBACK)
    assert headline.lower().startswith("in progress")  # legacy section heuristic
    assert lanes  # surfaces the section's ⬜ items


def test_pin_regex_tolerates_arrow_and_spacing():
    assert PIN_RE.search("**Focus:** plain").group(1) == "plain"
    assert PIN_RE.search("** ▶ Focus: ** arrowed").group(1) == "arrowed"
    assert PIN_RE.search("no focus pin here") is None
    # a real-world pin line with trailing markdown is captured whole
    assert PIN_RE.search(
        "**▶ Focus:** v3 — V3.2 scaffold (V3.1 landed)."
    ).group(1) == "v3 — V3.2 scaffold (V3.1 landed)."
