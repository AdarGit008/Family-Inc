"""Dashboard pure-function unit tests (V3.8 — the cheap JS coverage).

The suite is Python/pytest and the dashboard is one no-build-step IIFE, so its JS
had only `node --check` (syntax) + the manual DESIGN §9 smoke. This adds real
behaviour coverage for the highest-risk, Lane-C-adjacent **pure** date logic —
`parseDate`, `fmtISO`, `flagFor`, `bumpDate` — with **no toolchain** (no npm, no
jsdom): it slices each function's source out of `app.js` by brace-matching, runs
it under plain `node`, and asserts. The function sources are self-contained (only
`Date`/`String`/`Math`/regex — no closure or DOM deps), so they run standalone.

The *interactive* JS (desk selection, batch write fan-out, bottom-sheet focus-trap,
love-note fetch) genuinely needs a DOM harness (jsdom) and is tracked as a deferred
"JS test harness" lane in `BACKLOG.md` — this file does not pretend to cover it.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_JS = (ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")

requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="node not installed (pure-fn JS tests)")

# All four target functions use only balanced braces (regex quantifiers like {2,4},
# template `${}`, and object literals all pair up), so a depth counter ends at 0 on
# the function's own closing brace — exact for these, and a bad slice fails loud at
# node parse time anyway.
_PURE_FNS = ("parseDate", "fmtISO", "flagFor", "bumpDate")


def _extract(name: str) -> str:
    m = re.search(r"\n  function " + re.escape(name) + r"\s*\(", APP_JS)
    assert m, f"function {name}() not found in app.js — did it move/rename?"
    open_at = APP_JS.index("{", m.start())
    depth = 0
    for j in range(open_at, len(APP_JS)):
        if APP_JS[j] == "{":
            depth += 1
        elif APP_JS[j] == "}":
            depth -= 1
            if depth == 0:
                return APP_JS[m.start():j + 1].strip()
    raise AssertionError(f"unbalanced braces extracting {name}()")


_ASSERTIONS = r"""
function assert(cond, msg) { if (!cond) { console.error('FAIL: ' + msg); process.exitCode = 1; } }

// fmtISO + parseDate round-trip (the Lane-C contract: a written ISO Due date reads
// back to the same calendar day).
const d = new Date(2026, 5, 25);            // 25 Jun 2026 (month is 0-indexed)
assert(fmtISO(d) === '2026-06-25', 'fmtISO emits ISO');
const back = parseDate('2026-06-25');
assert(back && back.getFullYear() === 2026 && back.getMonth() === 5 && back.getDate() === 25, 'parseDate reads ISO');

// The Lane-C trap: a he-IL DD/MM render must NOT be misparsed MM/DD by a bare Date.
const he = parseDate('25/06/2026');
assert(he && he.getMonth() === 5 && he.getDate() === 25, 'parseDate DD/MM is day-first');
const he2 = parseDate('25.06.2026');
assert(he2 && he2.getMonth() === 5 && he2.getDate() === 25, 'parseDate DD.MM is day-first');

// Impossible / empty inputs → null (never a silently-rolled-over Date).
assert(parseDate('31/02/2026') === null, 'parseDate rejects 31/02');
assert(parseDate('25/13/2026') === null, 'parseDate rejects month 13');
assert(parseDate('') === null && parseDate(null) === null && parseDate(undefined) === null, 'parseDate empty → null');

// flagFor thresholds (load-bearing for OVERDUE/FIRE clearing on snooze, the D4 fix).
assert(flagFor(-1, 'Pending') === 'OVERDUE', 'flagFor <0 OVERDUE');
assert(flagFor(0, 'Pending') === 'FIRE TODAY', 'flagFor 0 FIRE');
assert(flagFor(1, 'Pending') === 'FIRE TODAY', 'flagFor 1 FIRE');
assert(flagFor(2, 'Pending') === 'WEEK OUT', 'flagFor 2 WEEK');
assert(flagFor(7, 'Pending') === 'WEEK OUT', 'flagFor 7 WEEK');
assert(flagFor(8, 'Pending') === 'MONTH OUT', 'flagFor 8 MONTH');
assert(flagFor(30, 'Pending') === 'MONTH OUT', 'flagFor 30 MONTH');
assert(flagFor(31, 'Pending') === '', 'flagFor 31 none');
assert(flagFor(-5, 'Done') === '', 'Done carries no flag');
assert(flagFor(0, 'Skipped') === '', 'Skipped carries no flag');

// bumpDate (mirror of the engine's recurrence bump; month-end clamp).
const m1 = bumpDate(new Date(2026, 0, 15), 'Monthly');
assert(m1.getMonth() === 1 && m1.getDate() === 15, 'Monthly +1');
const m2 = bumpDate(new Date(2026, 0, 31), 'Monthly');
assert(m2.getMonth() === 1 && m2.getDate() === 28, 'Jan31 +1mo clamps to Feb28 (2026 non-leap)');
const w = bumpDate(new Date(2026, 5, 10), 'Weekly');
assert(w.getMonth() === 5 && w.getDate() === 17, 'Weekly +7');
const y = bumpDate(new Date(2026, 5, 10), 'Yearly');
assert(y.getFullYear() === 2027 && y.getMonth() === 5 && y.getDate() === 10, 'Yearly +12mo');
assert(bumpDate(new Date(2026, 5, 10), 'Custom') === null, 'Custom is unbumpable (null)');
assert(bumpDate(new Date(2026, 5, 10), 'One-off') === null, 'One-off is unbumpable (null)');
"""


@requires_node
def test_pure_functions_behaviour(tmp_path):
    src = "\n\n".join(_extract(n) for n in _PURE_FNS) + "\n" + _ASSERTIONS
    script = tmp_path / "pure.js"
    script.write_text(src)
    # Pin TZ to mirror production (Israel): parseDate's ISO branch is `new Date('YYYY-MM-DD')`
    # = UTC midnight, read back via LOCAL getters — west of UTC that rolls to the prior day
    # and the round-trip assert would falsely fail. The real users (and the box) run east of
    # UTC, so pinning here makes the test deterministic + faithful to the live environment.
    env = {**os.environ, "TZ": "Asia/Jerusalem"}
    r = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=30, env=env)
    assert r.returncode == 0, f"pure-function JS tests failed:\n{r.stdout}\n{r.stderr}"
