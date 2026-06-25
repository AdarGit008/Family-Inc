"""Dashboard app.js syntax smoke (V3 lane — the cheapest JS guard).

The test suite is Python/pytest; the dashboard SPA (`dashboard/app.js`) has no JS
harness, so a syntax slip in an interactive edit would only surface as a blank
live dashboard. The V3 Today redesign rewrites `app.js` slice-by-slice (the file
crosses the ~2000-line JS-harness trigger mid-sequence, ENGINEERING §7), so pin
the floor cheaply now: the file must at least parse. Mirrors the `node --check`
guard the config-smoke already runs on the generated config.

This is syntax-only (no DOM, no execution) — it catches the unbalanced-brace /
stray-token class of regression that bit the most during the rewrite, without a
browser. Richer behaviour (computeCounts equivalence, STRINGS he+en parity)
stays on the DESIGN §9 manual smoke until a real JS harness lands.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_JS = ROOT / "dashboard" / "app.js"

requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="node not installed (app.js syntax check)")


@requires_node
def test_app_js_is_valid_js():
    r = subprocess.run(
        ["node", "--check", str(APP_JS)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f"dashboard/app.js is not valid JavaScript:\n{r.stderr}"
