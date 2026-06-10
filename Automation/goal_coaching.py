"""
Family inc. — Goal coaching weekly retro

For each goal, emit ONE line:
  * if progress this week  -> celebration ("+X ILS, on track for 2028")
  * if no movement 3+ wks  -> single open question ("want to add a task?")
  * else                   -> steady-state acknowledgement

Designed to be embeddable from friday_briefing.py:
    from goal_coaching import retro_lines
    lines = retro_lines(today)

Falls back to mock Goals data if a CSV path is not supplied.

CSV columns expected:
  name, owner, target_year, delta_this_week, last_update_days, status

Output: Briefings/goal_retro_YYYY-MM-DD.md
"""
from __future__ import annotations
import argparse
import csv
import logging
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).parent
BRIEFINGS_DIR = ROOT.parent / "Briefings"

log = logging.getLogger("goals")

# ---------------------------------------------------------------------------
# Mock goals — mirrors kickoff doc
# ---------------------------------------------------------------------------
MOCK_GOALS = [
    {"name": "House — ⟨town⟩", "owner": "Both",   "target_year": 2028,
     "delta_this_week": 4200, "unit": "ILS", "last_update_days": 2, "status": "On track"},
    {"name": "Adar — job + grad school", "owner": "Adar",   "target_year": 2027,
     "delta_this_week": 0, "unit": "tasks", "last_update_days": 24, "status": "Stalled"},
    {"name": "Passive income stream",    "owner": "Adar",   "target_year": 2029,
     "delta_this_week": 180, "unit": "ILS/mo", "last_update_days": 9, "status": "On track"},
    {"name": "Shanee — grooming/wellness habit", "owner": "Shanee", "target_year": 2026,
     "delta_this_week": 1, "unit": "session(s)", "last_update_days": 5, "status": "Building habit"},
]

def fmt_money(n) -> str:
    try: n = float(n)
    except (TypeError, ValueError): return str(n)
    return f"₪{n:,.0f}"

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
def load_goals(path: Path | None) -> list[dict]:
    if not path or not path.exists():
        log.warning("RUNNING IN MOCK MODE — using built-in Goals list")
        return MOCK_GOALS
    out = []
    with path.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                r["target_year"] = int(r.get("target_year") or 0)
                r["delta_this_week"] = float(r.get("delta_this_week") or 0)
                r["last_update_days"] = int(r.get("last_update_days") or 0)
            except ValueError:
                continue
            r.setdefault("unit", "ILS")
            out.append(r)
    return out

# ---------------------------------------------------------------------------
# Line synth
# ---------------------------------------------------------------------------
def _delta_phrase(g: dict) -> str:
    d = g["delta_this_week"]
    unit = g.get("unit", "ILS")
    if unit == "ILS":
        return f"+{fmt_money(d)}"
    if unit == "ILS/mo":
        return f"+{fmt_money(d)}/mo"
    return f"+{int(d) if float(d).is_integer() else d} {unit}"

def line_for(g: dict) -> str:
    name = g["name"]
    if g["delta_this_week"] > 0:
        return f"{name}: {_delta_phrase(g)}, on track for {g['target_year']}."
    if g["last_update_days"] >= 21:
        return f"{name}: no movement in {g['last_update_days']} days — want to add a task?"
    return f"{name}: steady. Last touch {g['last_update_days']}d ago."

def retro_lines(today: date, goals_csv: Path | None = None) -> list[str]:
    """Public helper — friday_briefing.py imports this."""
    goals = load_goals(goals_csv)
    return [line_for(g) for g in goals]

# ---------------------------------------------------------------------------
# Render + write
# ---------------------------------------------------------------------------
def render(today: date, lines: list[str]) -> str:
    head = f"# Goal retro — {today.isoformat()}\n"
    body = "\n".join(f"- {l}" for l in lines) or "- (no goals tracked)"
    return head + body + "\n"

def run(today: date, goals_csv: Path | None = None) -> Path:
    lines = retro_lines(today, goals_csv)
    text = render(today, lines)
    BRIEFINGS_DIR.mkdir(exist_ok=True)
    out = BRIEFINGS_DIR / f"goal_retro_{today.isoformat()}.md"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"wrote {out}")
    return out

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--goals", help="path to Goals CSV")
    ap.add_argument("--as-of", help="YYYY-MM-DD")
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    run(today, Path(args.goals) if args.goals else None)

if __name__ == "__main__":
    main()
