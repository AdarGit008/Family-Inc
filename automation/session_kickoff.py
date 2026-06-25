#!/usr/bin/env python3
"""Regenerate NEXT_SESSION_PROMPT.md — the paste-in opener for the next session.

Every session ends by running this, so the next session starts with current
state instead of archaeology. State is DERIVED from BACKLOG.md (open items) and
the git log (recent decisions — the D-NN log is retired; decisions now fold into
the canon and the dated rationale lives in commit messages). This script holds no
status of its own.

The focus headline is chosen, in order: (1) an explicit `**Focus:** …` pin the PO
sets in BACKLOG (deterministic — it beats any heuristic when the active lane isn't
the one a section is *titled* after); (2) else the in-progress (🔵) lanes across
ALL sections; (3) else the first section with an open item. This is the fix for
the old "focus = whatever section is literally titled 'In progress'" trap, which
hid an actively-built lane filed elsewhere.

Usage:  python3 automation/session_kickoff.py   (from repo root; stdlib only)
"""

import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "NEXT_SESSION_PROMPT.md"
N_COMMITS = 6


def _open_items(body: str, markers: tuple[str, ...] = ("⬜", "🔵")) -> list[str]:
    """Bullet lines in a section body whose marker emoji is in `markers`, cleaned of
    the bullet/bold wrapper + length. Tolerates BOTH `- 🔵 **x**` and the bold-wrapped
    `- **🔵 x**` forms (the v3 lane uses the latter)."""
    items: list[str] = []
    for ln in body.splitlines():
        s = ln.strip()
        if not s.startswith("- "):
            continue
        rest = s[2:].lstrip().lstrip("*").lstrip()  # past "- " and any leading **
        for emoji in markers:
            if rest.startswith(emoji):
                text = rest[len(emoji):].strip().lstrip("*").strip()
                text = re.sub(r"\*\*", "", text)
                if len(text) > 200:  # word-boundary clip — never mid-word; keep the lead clause
                    text = text[:200].rsplit(" ", 1)[0].rstrip(" ;,—-") + " …"
                items.append(text)
                break
    return items


def current_milestone(backlog: str) -> tuple[str, list[str]]:
    """The '## In progress' section's open items; else the first '## ' section
    that still has any open item. (BACKLOG.md uses level-2 section headers.)"""
    sections = re.split(r"^## ", backlog, flags=re.M)[1:]
    # Prefer the explicit in-progress section.
    for sec in sections:
        header, _, body = sec.partition("\n")
        if header.strip().lower().startswith("in progress"):
            items = _open_items(body)
            if items:
                return header.strip(), items
    # Fallback: first section with any open item.
    for sec in sections:
        header, _, body = sec.partition("\n")
        items = _open_items(body)
        if items:
            return header.strip(), items
    return "(no open milestone found — check BACKLOG.md)", []


# An explicit, PO-set focus line in BACKLOG (e.g. `**▶ Focus:** v3 — V3.2 …`).
# Boring + deterministic — it beats any heuristic when the active lane isn't the
# one a section is *titled* after. Optional leading arrow glyph; tolerant of spacing.
PIN_RE = re.compile(r"^\s*\*\*\s*(?:▶|►|➤)?\s*Focus:\s*\*\*\s*(.+?)\s*$", re.M)


def in_progress_lanes(backlog: str) -> list[str]:
    """Every 🔵 (in-progress) bullet across ALL sections — the lanes actually in
    flight (the legend's 🔵), not just whatever section is titled 'In progress'."""
    lanes: list[str] = []
    for sec in re.split(r"^## ", backlog, flags=re.M)[1:]:
        _, _, body = sec.partition("\n")
        lanes.extend(_open_items(body, markers=("🔵",)))
    return lanes


def focus(backlog: str) -> tuple[str, list[str]]:
    """(headline, active-lane list). Precedence:
      1. an explicit `**Focus:** …` pin in BACKLOG — PO-controlled, deterministic;
      2. else the in-progress (🔵) lanes across every section, document order;
      3. else the first section that still has an open item (legacy heuristic)."""
    lanes = in_progress_lanes(backlog)
    pin = PIN_RE.search(backlog)
    if pin:
        return pin.group(1).strip(), lanes
    if lanes:
        return lanes[0], lanes
    return current_milestone(backlog)


def recent_decisions(n: int = N_COMMITS) -> list[str]:
    """Recent commit subjects (dated) — the decision record now lives in git
    history. Best-effort: returns [] if git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "log", "-n", str(n), "--pretty=format:%cs %s"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0:
            return []
        return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    except (OSError, subprocess.SubprocessError):
        return []


def main() -> int:
    backlog = (ROOT / "BACKLOG.md").read_text(encoding="utf-8")
    headline, lanes = focus(backlog)
    lanes_md = "\n".join(f"- {ln}" for ln in lanes) or "- (none)"
    commits = recent_decisions()
    commits_md = "\n".join(f"- {c}" for c in commits) or "- (git log unavailable)"
    today = dt.date.today().isoformat()

    OUT.write_text(f"""# Next session — Family Inc

*Generated {today} by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current focus only.

**Current focus: {headline}**

*(The focus headline is set by a `**Focus:** …` pin in `BACKLOG.md` → `## Now`; absent a pin it's the freshest 🔵 lane.)*

Active lanes (🔵 in progress — work the focus above first; don't open the others without a PO call):

{lanes_md}

Recent commits (the dated decision record — decisions fold into the canon, not a separate log):

{commits_md}

Session contract: don't open lanes outside the current focus without a PO call ·
constants → config, utilities → `automation/lib/`, message copy → templates ·
a directional call = edit the relevant canon doc to the new present-tense state
(short inline *why* if non-obvious) with the dated rationale in the commit message ·
session end: tests green if code moved, `BACKLOG.md` flipped, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
""", encoding="utf-8")
    print(f"OK → {OUT.name} (focus: {headline[:80]}, {len(lanes)} active lanes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
