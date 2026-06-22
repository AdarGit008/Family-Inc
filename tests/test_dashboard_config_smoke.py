"""Dashboard config.js smoke (ROADMAP §1, lane 1 — the config-smoke gate).

Pages generates dashboard/config.js from config.example.js on every dashboard/**
push (.github/workflows/pages.yml) via three `sed` substitutions. config.js is
gitignored and only exists at deploy time, so a template edit that silently
breaks the sed — or produces invalid JS — would only surface as a broken live
dashboard. This pins the contract three ways:
  • the three sed ANCHORS still exist in config.example.js (so a drifted template
    fails here, not at deploy — the "config.example.js still applies" check);
  • the generated output carries no placeholder and the full Finance tab names;
  • the generated output is valid JavaScript (node --check).

The generated config.js intentionally KEEPS the example.com USERS fallback —
pages.yml overrides only the two ids; live identity is Settings.UserMap (SPEC
§7.6) — so this does not assert example.com is absent.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "dashboard" / "config.example.js"

# The exact anchors pages.yml's sed depends on — keep in lockstep with that file.
_CLIENT_ANCHOR = "PASTE_YOUR_CLIENT_ID_HERE.apps.googleusercontent.com"
_SHEET_ANCHOR = "PASTE_YOUR_SHEET_ID_HERE"
_DEMO_ANCHOR = "DEMO_MODE: true"

_EXPECTED_TAB_KEYS = {
    "reminders", "calendarEvents", "people", "finance_acct", "finance_txns",
    "finance_bdgt", "goals", "health", "education", "car", "contracts", "settings",
}
_EXPECTED_FINANCE_TABS = ("Finance-Accounts", "Finance-Transactions", "Finance-Budget")

requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="node not installed (config.js syntax check)")


def _template() -> str:
    return TEMPLATE.read_text()


def _generate(client="dummy-client.apps.googleusercontent.com",
              sheet="dummySheetId1234567890") -> str:
    """Mirror pages.yml's three sed substitutions, in Python, with dummy secrets."""
    return (_template()
            .replace(_CLIENT_ANCHOR, client)
            .replace(_SHEET_ANCHOR, sheet)
            .replace(_DEMO_ANCHOR, "DEMO_MODE: false"))


def test_sed_anchors_present_in_template():
    t = _template()
    for anchor in (_CLIENT_ANCHOR, _SHEET_ANCHOR, _DEMO_ANCHOR):
        assert anchor in t, (
            f"pages.yml's sed anchor {anchor!r} is missing from config.example.js — "
            "Pages config generation would silently no-op. Keep the anchors in sync "
            "with .github/workflows/pages.yml.")


def test_generated_config_drops_placeholders_and_flips_demo():
    out = _generate()
    assert "PASTE_" not in out, "a PASTE_ placeholder survived generation"
    assert "DEMO_MODE: false" in out and "DEMO_MODE: true" not in out, \
        "DEMO_MODE was not flipped to false"


def test_generated_config_has_all_tabs():
    out = _generate()
    for key in _EXPECTED_TAB_KEYS:
        assert f"{key}:" in out, f"TABS is missing the {key!r} key"
    for full in _EXPECTED_FINANCE_TABS:
        assert full in out, f"config is missing the full finance tab name {full!r}"


@requires_node
def test_template_and_generated_config_are_valid_js(tmp_path):
    for label, source in (("config.example.js", _template()), ("generated config.js", _generate())):
        f = tmp_path / "config.js"
        f.write_text(source)
        r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, f"{label} is not valid JavaScript:\n{r.stderr}"
