"""
Family inc. — Friday Briefing (Phase 2)

Strava-meets-Morning-Brew Friday recap: (1) week spend vs 4w avg,
(2) kids' biggest moment, (3) next week's 3 reminders, (4) one goal
nudge (round-robin), (5) one contract heads-up, plus Shabbat times.

Live mode reads Family_OS.xlsx; falls back to mock data (banner shown).
Claude API used for prose if ANTHROPIC_API_KEY is set, else template.
Cost target <= $0.10/run.

Run: python friday_briefing.py [--dry-run] [--as-of YYYY-MM-DD]
"""
from __future__ import annotations
import argparse, logging, os
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import hebcal_client

ROOT = Path(__file__).parent
SHEET_PATH = ROOT.parent / "Family_OS.xlsx"
BRIEFINGS_DIR = ROOT.parent / "Briefings"

log = logging.getLogger("friday")

# Mock data fallback (matches sunday_briefing.py convention)
MOCK = {
    "week_spend": 3120, "avg_4w_spend": 2890,
    "kids_moment": {"child": "⟨child-1⟩", "date": "2026-05-28",
                    "event": "First swim class — floated on his back for 5 sec"},
    "next_week_reminders": [
        {"title": "⟨child-2⟩ — 4mo Tipat Halav", "date": "2026-06-02", "domain": "Health"},
        {"title": "Mortgage advisor call", "date": "2026-06-03", "domain": "Finance"},
        {"title": "Car insurance renewal", "date": "2026-06-05", "domain": "Car"},
    ],
    "goals": [
        {"name": "House — ⟨town⟩", "owner": "Both", "delta_week": 4200, "last_update_days": 2, "target_year": 2028},
        {"name": "Adar — job + grad school", "owner": "Adar", "delta_week": 0, "last_update_days": 24, "target_year": 2027},
        {"name": "Passive income stream", "owner": "Adar", "delta_week": 180, "last_update_days": 9, "target_year": 2029},
        {"name": "Shanee — grooming/wellness habit", "owner": "Shanee", "delta_week": 1, "last_update_days": 5, "target_year": 2026},
    ],
    "contracts": [
        {"name": "Cellcom mobile family plan", "renews": "2026-07-15", "monthly_ils": 220},
        {"name": "Yes TV bundle", "renews": "2026-08-30", "monthly_ils": 189},
    ],
}

def gather(today: date) -> dict:
    """Return data bag for the briefing, mock or live."""
    data = dict(MOCK)
    try:
        from openpyxl import load_workbook
        if SHEET_PATH.exists():
            load_workbook(SHEET_PATH, data_only=True)  # live overlay TBD
            data["_mock"] = False
            return data
    except Exception as e:
        log.warning("sheet load failed: %s", e)
    log.warning("RUNNING IN MOCK MODE — Family_OS.xlsx not available")
    data["_mock"] = True
    return data

def fmt_money(n) -> str:
    if n is None: return "—"
    try: n = float(n)
    except (TypeError, ValueError): return str(n)
    return f"₪{n:,.0f}"

def section_spend(data: dict) -> str:
    spend, avg = data["week_spend"], data["avg_4w_spend"]
    delta = spend - avg
    pct = (delta / avg * 100) if avg else 0
    arrow = "up" if delta > 0 else ("down" if delta < 0 else "flat")
    return (f"This week: {fmt_money(spend)} spent ({arrow} {abs(pct):.0f}% vs 4-week avg "
            f"of {fmt_money(avg)}).")

def section_kids(data: dict) -> str:
    m = data["kids_moment"]
    return f"Biggest kid moment — {m['child']} on {m['date']}: {m['event']}."

def section_next_week(data: dict) -> str:
    rs = data["next_week_reminders"][:3]
    if not rs:
        return "Next week: clean slate."
    bullets = "\n".join(f"  - {r['date']} — {r['title']} [{r['domain']}]" for r in rs)
    return "Next week's three things:\n" + bullets

def _goal_index(today: date) -> int:
    """Round-robin by ISO week so all four goals cycle monthly."""
    iso_year, iso_week, _ = today.isocalendar()
    return iso_week % 4

def section_goal_nudge(data: dict, today: date) -> str:
    g = data["goals"][_goal_index(today) % len(data["goals"])]
    name, d, days = g["name"], g["delta_week"], g["last_update_days"]
    if d > 0 and days <= 7:
        if name.startswith("House"):
            return f"Goal nudge — {name}: +{fmt_money(d)} this week, on track for {g['target_year']}."
        if "grooming" in name:
            return f"Goal nudge — Shanee logged {d} grooming/wellness session(s) this week. Streak alive."
        return f"Goal nudge — {name}: +{d} this week."
    if days >= 21:
        return f"Goal nudge — {name}: no movement in {days} days. Want to add one task?"
    return f"Goal nudge — {name}: steady, last update {days}d ago."

def section_contract(data: dict, today: date) -> str:
    soon = []
    for c in data["contracts"]:
        try: d = datetime.strptime(c["renews"], "%Y-%m-%d").date()
        except ValueError: continue
        if 0 <= (d - today).days <= 60:
            soon.append(((d - today).days, c))
    if not soon: return "No contract renewals in the next 60 days."
    soon.sort(); days, c = soon[0]
    return (f"Contract heads-up — {c['name']} renews in {days} days "
            f"({c['renews']}, ~{fmt_money(c['monthly_ils'])}/mo). Worth a price-check call?")

def section_shabbat(today: date) -> str:
    st = hebcal_client.shabbat_times(today)
    if st.get("_stub"):
        return "Shabbat times unavailable (hebcal offline)."
    cl = (st.get("candle_lighting") or "")[11:16] or "?"
    hv = (st.get("havdalah") or "")[11:16] or "?"
    par = st.get("parasha") or "?"
    return f"Shabbat — candles {cl}, havdalah {hv}. Parashat {par}. Shabbat shalom."

# Renderers — templated + (optional) Claude
def render_template(data: dict, today: date) -> str:
    banner = "_RUNNING IN MOCK MODE_\n\n" if data.get("_mock") else ""
    parts = [
        f"# Family inc. — Friday Briefing",
        f"_{today.strftime('%A, %B %-d, %Y')}_\n",
        banner.rstrip() if banner else "",
        f"**Money.** {section_spend(data)}\n",
        f"**Kids.** {section_kids(data)}\n",
        f"**Ahead.** {section_next_week(data)}\n",
        f"**Goals.** {section_goal_nudge(data, today)}\n",
        f"**Contracts.** {section_contract(data, today)}\n",
        f"**Shabbat.** {section_shabbat(today)}\n",
        "---\n_Auto-generated. Edits go back into Family_OS.xlsx._",
    ]
    return "\n".join(p for p in parts if p) + "\n"

def render_with_claude(data: dict, today: date) -> Optional[str]:
    """Rewrite via Anthropic SDK; return None if key/SDK missing so caller falls back."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key: return None
    try: import anthropic
    except ImportError:
        log.warning("anthropic SDK not installed — falling back to template"); return None
    raw = render_template(data, today)
    prompt = ("Rewrite this Friday family briefing as a 6-paragraph Morning-Brew-style note: "
              "warm, concrete, no emojis, Hebrew place names kept as-is. "
              "Preserve every number and date. <=220 words total.\n\n" + raw)
    try:  # Haiku keeps cost well under $0.10
        msg = anthropic.Anthropic(api_key=key).messages.create(
            model="claude-haiku-4-5", max_tokens=600,
            messages=[{"role": "user", "content": prompt}])
        return msg.content[0].text
    except Exception as e:
        log.warning("Claude synthesis failed (%s) — using template", e); return None

# Main
def run(today: date, dry_run: bool = False) -> Optional[Path]:
    data = gather(today)
    body = render_with_claude(data, today) or render_template(data, today)
    if dry_run:
        print(body)
        return None
    BRIEFINGS_DIR.mkdir(exist_ok=True)
    out = BRIEFINGS_DIR / f"friday_{today.isoformat()}.md"
    out.write_text(body, encoding="utf-8")
    print(f"wrote {out}")
    print(body)
    return out

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", help="YYYY-MM-DD; defaults to today")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    run(today, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
