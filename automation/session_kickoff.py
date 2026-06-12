#!/usr/bin/env python3
"""Regenerate NEXT_SESSION_PROMPT.md — the paste-in opener for the next session.

Pattern ported from the Porto project (D-023): every session ends by running this,
so the next session starts with current state instead of archaeology. State is
DERIVED from BACKLOG.md and DECISIONS.md — this script holds no status of its own.

Usage:  python3 automation/session_kickoff.py   (from repo root; stdlib only)
"""

import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "NEXT_SESSION_PROMPT.md"
N_DECISIONS = 5


def current_milestone(backlog: str) -> tuple[str, list[str]]:
    """First '### M…' section that still contains an unchecked ⬜ item."""
    sections = re.split(r"^### ", backlog, flags=re.M)[1:]
    for sec in sections:
        header, _, body = sec.partition("\n")
        items = [ln.strip()[2:].strip() for ln in body.splitlines()
                 if ln.strip().startswith("- ⬜")]
        if items:
            return header.strip(), items
    return "(no open milestone found — check BACKLOG.md)", []


def recent_decisions(decisions: str, n: int = N_DECISIONS) -> list[str]:
    rows = []
    for ln in decisions.splitlines():
        m = re.match(r"\|\s*(D-\d+)\s*\|\s*([\d-]+)\s*\|\s*(.+?)\s*\|", ln)
        if m:
            summary = re.sub(r"\*\*", "", m.group(3))
            summary = summary[:140] + "…" if len(summary) > 140 else summary
            rows.append(f"{m.group(1)} ({m.group(2)}): {summary}")
        if len(rows) == n:
            break
    return rows


def main() -> int:
    backlog = (ROOT / "BACKLOG.md").read_text(encoding="utf-8")
    decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    milestone, items = current_milestone(backlog)
    items_md = "\n".join(f"- {i}" for i in items) or "- (none)"
    decisions_md = "\n".join(f"- {d}" for d in recent_decisions(decisions))
    today = dt.date.today().isoformat()

    OUT.write_text(f"""# Next session — Family Inc

*Generated {today} by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current milestone only.

**Current milestone: {milestone}**

Open items:

{items_md}

Recent decisions (full log in `DECISIONS.md`):

{decisions_md}

Session contract: don't open lanes outside this milestone without a PO call
logged in `DECISIONS.md` · constants → config, utilities → `automation/lib/`,
message copy → templates · session end: tests green if code moved, `BACKLOG.md`
flipped, directional calls logged with the next D-number, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
""", encoding="utf-8")
    print(f"OK → {OUT.name} (milestone: {milestone}, {len(items)} open items)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
