#!/usr/bin/env python3
"""Regenerate NEXT_SESSION_PROMPT.md — the paste-in opener for the next session.

Every session ends by running this, so the next session starts with current
state instead of archaeology. State is DERIVED from BACKLOG.md (open items) and
the git log (recent decisions — the D-NN log is retired; decisions now fold into
the canon and the dated rationale lives in commit messages). This script holds no
status of its own.

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


def _open_items(body: str) -> list[str]:
    """⬜/🔵 bullet lines in a section body, cleaned of marker + bold + length."""
    items: list[str] = []
    for ln in body.splitlines():
        s = ln.strip()
        for marker in ("- ⬜", "- 🔵"):
            if s.startswith(marker):
                text = s[len(marker):].strip().lstrip("*").strip()
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
    milestone, items = current_milestone(backlog)
    items_md = "\n".join(f"- {i}" for i in items) or "- (none)"
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

**Current focus: {milestone}**

Open items:

{items_md}

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
    print(f"OK → {OUT.name} (focus: {milestone}, {len(items)} open items)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
