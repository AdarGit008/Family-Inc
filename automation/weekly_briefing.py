"""
Family inc. — Weekly Briefing (SPEC.md §7.2: Sat 21:00, D-011)

Renamed from sunday_briefing.py in M1 — it runs Saturday evening. Generates
the cross-domain weekly briefing from the master workbook (lib/sheet.py — the
live Google Sheet when configured) and writes
Briefings/{date}_weekly_briefing.md; with --send it also queues through
lib/outbox.py (kind=briefing: budget-exempt, quiet-hours held; SPEC §7.2,
id=brief-weekly-{date}).

Sections (in order): week ahead · reminders firing this week · overdue ·
money · goals · data hygiene (which also surfaces schema-drift flags and
engine review flags — ENGINEERING §8 self-reporting: humans never read logs
unless the briefing says to).

The SPEC §7.2 LLM-written five-scene narrative (DESIGN.md §6) with this
deterministic template as its fallback is still an open lane — what follows
IS the fallback path.

Run modes:
  python3 automation/weekly_briefing.py             # today's date, writes file
  python3 automation/weekly_briefing.py --dry-run   # print only
  python3 automation/weekly_briefing.py --send      # also queue to the outbox (M3)
  python3 automation/weekly_briefing.py --as-of 2026-05-31
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/weekly_briefing.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from automation import templates as T
from automation.lib import config, outbox, sheet
from automation.lib.dates import fmt_date, to_date
from automation.lib.money import fmt_money, pct


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------
def section_week_ahead(wb, today: date, end: date) -> str:
    ws = wb["Calendar-Events"]
    rows = []
    for r in range(2, ws.max_row + 1):
        d = to_date(ws.cell(r, 1).value)
        if not d or d < today or d > end:
            continue
        title = ws.cell(r, 4).value
        if not title:
            continue
        rows.append({
            "date": d,
            "start": ws.cell(r, 2).value,
            "end": ws.cell(r, 3).value,
            "title": title,
            "owner": ws.cell(r, 5).value or "",
            "location": ws.cell(r, 7).value or "",
        })
    rows.sort(key=lambda x: (x["date"], x["start"] or ""))
    if not rows:
        return "_Quiet week ahead — no events scheduled._"
    by_day = {}
    for r in rows:
        by_day.setdefault(r["date"], []).append(r)
    lines = []
    for d in sorted(by_day):
        marker = " **(today)**" if d == today else ""
        lines.append(f"\n**{fmt_date(d)}**{marker}")
        for r in by_day[d]:
            time = ""
            if r["start"]:
                time = f"{r['start']}"
            if r["start"] and r["end"]:
                time += f"–{r['end']}"
            if not time:
                time = "all day"
            who = f" · {r['owner']}" if r["owner"] else ""
            loc = f" · {r['location']}" if r["location"] else ""
            lines.append(f"- {time} — {r['title']}{who}{loc}")
    return "\n".join(lines).lstrip()


def section_reminders_week(wb, today: date, end: date) -> tuple[str, str]:
    """Returns (upcoming_section, overdue_section)."""
    ws = wb["Reminders"]
    upcoming, overdue = [], []
    for r in range(2, ws.max_row + 1):
        title = ws.cell(r, 1).value
        if not title or str(title).startswith("["):
            continue
        status = ws.cell(r, 7).value or "Pending"
        if status in {"Done", "Skipped"}:
            continue
        due = to_date(ws.cell(r, 4).value)
        if not due:
            continue
        owner = ws.cell(r, 3).value or ""
        domain = ws.cell(r, 2).value or ""
        days = (due - today).days
        if days < 0:
            overdue.append((due, days, title, owner, domain))
        elif days <= config.WEEK_AHEAD_DAYS:
            upcoming.append((due, days, title, owner, domain))
    upcoming.sort(key=lambda x: x[0])
    overdue.sort(key=lambda x: x[0])

    def render(rows, kind: str) -> str:
        if not rows:
            return f"_No {kind} items._"
        lines = []
        for due, days, title, owner, domain in rows:
            if days < 0:
                tag = f"🔴 overdue {-days}d"
            elif days == 0:
                tag = "🟠 today"
            elif days <= 1:
                tag = "🟠 tomorrow"
            elif days <= 7:
                tag = f"🟡 in {days}d"
            else:
                tag = f"in {days}d"
            who = f" · {owner}" if owner else ""
            dom = f" [{domain}]" if domain else ""
            lines.append(f"- {tag} — {title}{who}{dom}  ({due.isoformat()})")
        return "\n".join(lines)

    return render(upcoming, "upcoming"), render(overdue, "overdue")


def section_money(wb, today: date) -> str:
    """Read Finance-Bdgt (as-built tab name; SPEC §6.4 calls it Finance-Budget
    — flagged 2026-06-12, code follows the actual Sheet until the POs rename)."""
    ws = wb["Finance-Bdgt"]
    rows = []
    for r in range(2, ws.max_row + 1):
        cat = ws.cell(r, 1).value
        if not cat or cat == "TOTAL":
            continue
        target = ws.cell(r, 2).value
        actual = ws.cell(r, 3).value
        if target in (None, 0):
            continue
        rows.append({
            "cat": cat,
            "target": float(target),
            "actual": float(actual or 0),
        })
    # Show top 3 over-budget and totals
    over = sorted([r for r in rows if r["actual"] > r["target"]],
                  key=lambda r: r["actual"] - r["target"], reverse=True)[:3]
    total_target = sum(r["target"] for r in rows)
    total_actual = sum(r["actual"] for r in rows)
    p = pct(total_actual, total_target)
    lines = [f"**Month-to-date:** {fmt_money(total_actual)} of {fmt_money(total_target)} target  ({(p or 0)*100:.0f}%)"]
    if over:
        lines.append("\n**Over-budget categories:**")
        for r in over:
            o = r["actual"] - r["target"]
            lines.append(f"- {r['cat']}: {fmt_money(r['actual'])} / {fmt_money(r['target'])}  (+{fmt_money(o)})")
    else:
        lines.append("\nNo categories over budget this month.")
    return "\n".join(lines)


def section_goals(wb, today: date) -> str:
    ws = wb["Goals"]
    rows = []
    for r in range(2, ws.max_row + 1):
        goal = ws.cell(r, 1).value
        if not goal:
            continue
        target = to_date(ws.cell(r, 4).value)
        milestone = ws.cell(r, 5).value or ""
        pct_done = ws.cell(r, 6).value
        last_update = to_date(ws.cell(r, 7).value)
        status = ws.cell(r, 8).value or "Not started"
        owner = ws.cell(r, 2).value or ""
        rows.append({
            "goal": goal, "owner": owner, "target": target, "milestone": milestone,
            "pct": pct_done, "last_update": last_update, "status": status
        })
    if not rows:
        return "_No goals tracked yet._"
    lines = []
    for r in rows:
        flags = []
        if r["target"] and (r["target"] - today).days <= config.GOAL_MILESTONE_FLAG_DAYS \
                and (r["target"] - today).days >= 0:
            flags.append(f"⏰ milestone in {(r['target']-today).days}d")
        if r["last_update"] and (today - r["last_update"]).days > config.STALE_GOAL_UPDATE_DAYS:
            flags.append(f"⚠️ no update in {(today - r['last_update']).days}d")
        pct_str = f"{int(r['pct'])}%" if isinstance(r["pct"], (int, float)) else "—"
        flag_str = ("  " + " · ".join(flags)) if flags else ""
        line = f"- **{r['goal']}** ({r['owner']}, {r['status']}, {pct_str})"
        if r["milestone"]:
            line += f"\n  next: {r['milestone']}"
        line += flag_str
        lines.append(line)
    return "\n".join(lines)


def _system_flags() -> list[str]:
    """Fail-loud surfacing (ENGINEERING §8): schema drift aborts engine runs
    silently from the humans' perspective — the briefing is where they hear
    about it. Engine review flags (Feb-29 clamps, Custom recurrence) ride
    along until someone clears the file."""
    issues = []
    drift = sheet.schema_drift_flag()
    if drift:
        issues.append("- ⚠ **schema drift**: Reminders header no longer matches "
                      f"SPEC §6.1 — engine runs are aborting ({'; '.join(drift.get('problems', []))})")
    if config.ENGINE_FLAGS.exists():
        flags = [json.loads(ln) for ln in
                 config.ENGINE_FLAGS.read_text(encoding="utf-8").splitlines() if ln.strip()]
        for f in flags[-5:]:
            issues.append(f"- ⚠ engine flag: {f.get('reason', '?')} — row {f.get('row', '?')} "
                          f"`{f.get('title', '')}`")
        if len(flags) > 5:
            issues.append(f"- (+{len(flags) - 5} older engine flags in logs/engine_flags.jsonl)")
    return issues


def section_hygiene(wb, today: date) -> str:
    issues = _system_flags()
    # Reminders missing due date
    r_ws = wb["Reminders"]
    missing = 0
    for row in range(2, r_ws.max_row + 1):
        if r_ws.cell(row, 1).value and not r_ws.cell(row, 4).value:
            missing += 1
    if missing:
        issues.append(f"- {missing} reminder(s) missing a Due Date")
    # Stale Last Imported on accounts
    fa_ws = wb["Finance-Accts"]
    for row in range(2, fa_ws.max_row + 1):
        if fa_ws.cell(row, 1).value and not fa_ws.cell(row, 1).value.startswith("["):
            last_imp = to_date(fa_ws.cell(row, 7).value)
            if not last_imp:
                issues.append(f"- Account `{fa_ws.cell(row, 1).value}` has no Last Imported date")
            elif (today - last_imp).days > 35:
                issues.append(f"- Account `{fa_ws.cell(row, 1).value}` not imported in {(today-last_imp).days}d")
    # Placeholder rows still in People/Health/etc.
    p_ws = wb["People"]
    placeholders = sum(1 for r in range(2, p_ws.max_row + 1)
                       if p_ws.cell(r, 1).value and str(p_ws.cell(r, 1).value).startswith("["))
    if placeholders:
        issues.append(f"- {placeholders} People row(s) still using placeholder names")
    if not issues:
        return "_All clean._"
    return "\n".join(issues)


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def render_briefing(wb, today: date) -> str:
    end = today + timedelta(days=config.WEEK_AHEAD_DAYS)
    parts = []
    parts.append(T.WEEKLY_TITLE)
    parts.append(f"_{today.strftime('%A, %B %-d, %Y')}_  ·  week of {today.isoformat()} → {end.isoformat()}\n")

    parts.append("## Week ahead")
    parts.append(section_week_ahead(wb, today, end))

    upcoming, overdue = section_reminders_week(wb, today, end)
    parts.append("\n## Reminders firing this week")
    parts.append(upcoming)
    parts.append("\n## Overdue")
    parts.append(overdue)

    parts.append("\n## Money")
    parts.append(section_money(wb, today))

    parts.append("\n## Goals")
    parts.append(section_goals(wb, today))

    parts.append("\n## Data hygiene")
    parts.append(section_hygiene(wb, today))

    parts.append(T.WEEKLY_FOOTER)
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run(today: date, dry_run: bool = False, send: bool = False,
        sheet_path: Path | None = None) -> Path | None:
    wb = sheet.workbook(sheet_path)  # live Sheet when configured (D-016)
    body = render_briefing(wb, today)
    if dry_run:
        print(body)
        return None
    config.BRIEFINGS_DIR.mkdir(exist_ok=True)
    out = config.BRIEFINGS_DIR / f"{today.isoformat()}_weekly_briefing.md"
    out.write_text(body, encoding="utf-8")
    print(f"wrote {out}")
    if send:
        res = outbox.queue("both", body, "briefing", source="weekly_briefing",
                           msg_id=f"brief-weekly-{today.isoformat()}")
        print(f"queued briefing → both: {len(res.queued)} row(s)"
              + (f", duplicate {res.duplicates}" if res.duplicates else ""))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", help="YYYY-MM-DD; defaults to today")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--send", action="store_true",
                    help="queue to the bridge outbox (M3 timers use this)")
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    run(today, dry_run=args.dry_run, send=args.send)


if __name__ == "__main__":
    main()
