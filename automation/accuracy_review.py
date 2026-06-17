"""
Family inc. — WhatsApp-classifier accuracy review surface (Phase F, D-048).

The hourly summarizer (whatsapp_summarizer.py) decides ROUTINE / DIGEST / ALERT
and records each decision + its outcome (critical, dispatched, action_owner) in
the WhatsApp_Inbox tab. Phase F is the weekly REVIEW of those decisions: it
surfaces the week's ALERT-tier classifications so a human can spot false
positives and tune. The bar, from the original WhatsApp design, is **fewer than
one ALERT-tier false positive per week** (config.ALERT_FP_TARGET_PER_WEEK).

What it does NOT do: invent a verdict. There is no automatic false-positive
detector — a false positive is a human judgment ("that ALERT shouldn't have
interrupted us"). This surface organizes the week's ALERTs for that judgment and
points at the tunable knob (the per-group keyword patterns in the group-config
seed). A machine-measured FP rate would need a human-mark channel (an additive
Inbox column or a dashboard control) — deferred, a PO call (D-048).

Why re-derive the rule: the Inbox schema (§6.2) stores the classification and
outcome but not WHICH rule fired. Rather than migrate the live tab, derive_rule
re-runs the summarizer's own hard_rule_alert against the persisted fields — the
hard rules are deterministic functions of (group, sender_role, time, text), so
this is faithful and can never drift from the classifier (single source of
truth). A persisted critical flag is authoritative; no hard rule matching means
the ALERT came from the LLM (or the deterministic fallback).

Delivery: the weekly briefing folds in a compact pulse (render_brief, via
weekly_briefing.section_classifier_accuracy) on the existing Sat-21:00 cadence —
no new timer. This script is the full operator surface (render_full), written to
Briefings/{date}_accuracy_review.md, run on demand:

  python3 automation/accuracy_review.py [--weeks N | --days N]
                                        [--as-of YYYY-MM-DD] [--dry-run]
                                        [--sheet path.xlsx] [--config groups.csv]
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/accuracy_review.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from automation import whatsapp_summarizer as was
from automation.lib import config as cfg
from automation.lib import sheet
from automation.lib.dates import to_date

log = logging.getLogger("accuracy")

# Rule labels for the two cases hard_rule_alert can't name on its own.
RULE_CRITICAL = "critical keyword"   # persisted critical flag — authoritative
RULE_LLM = "LLM / context"           # no hard rule fired → the model judged it ALERT

TAB = cfg.WA_INBOX_SHEET_TAB


# ---------------------------------------------------------------------------
# Cell helpers — both backends round-trip booleans differently (gspread RAW →
# the string "TRUE"/"FALSE"; openpyxl → Python bool), so normalize loosely.
# ---------------------------------------------------------------------------
def _truthy(v) -> bool:
    return v is True or str(v).strip().upper() in ("TRUE", "1", "YES")


def _clip(text: str, n: int = 100) -> str:
    t = re.sub(r"\s+", " ", str(text or "").strip())
    return (t[: n - 1] + "…") if len(t) > n else t


def _row_date(row: dict) -> Optional[date]:
    """The row's received_at as a date, or None when unparseable — NOT
    was._parse_dt, whose now() fallback would silently pull undatable rows into
    the window."""
    s = str(row.get("received_at", "") or "").strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "").split("+")[0]).date()
    except ValueError:
        return to_date(s)  # tolerant of DD/MM/YYYY etc.


# ---------------------------------------------------------------------------
# Read WhatsApp_Inbox rows as header-keyed dicts over the duck-typed workbook
# (sheet.workbook() handle OR a plain openpyxl Workbook — the weekly briefing
# passes the latter in tests). lib/sheet stays the only thing that opens a
# backend; this just reads through the public handle, like the briefing does.
# ---------------------------------------------------------------------------
def _tab_rows(wb, tab: str) -> list[dict]:
    if tab not in wb.sheetnames:
        return []
    ws = wb[tab]
    headers: list[str] = []
    for c in range(1, 65):  # headers are contiguous from col 1; stop at the first blank
        v = ws.cell(1, c).value
        if v is None or str(v).strip() == "":
            break
        headers.append(str(v).strip())
    if not headers:
        return []
    rows = []
    for r in range(2, ws.max_row + 1):
        d = {h: ws.cell(r, i + 1).value for i, h in enumerate(headers)}
        if any(v not in (None, "") for v in d.values()):  # skip fully-empty rows
            rows.append(d)
    return rows


# ---------------------------------------------------------------------------
# Rule re-derivation
# ---------------------------------------------------------------------------
def _row_to_msg(row: dict) -> dict:
    return {
        "group_name": row.get("group_name", "") or "",
        "text": row.get("text", "") or "",
        "sender_role": (row.get("sender_role") or "unknown"),
        "received_at": row.get("received_at", "") or "",
    }


def derive_rule(row: dict, group_config: dict) -> str:
    """Best-effort: why was this row an ALERT? A persisted critical flag is
    authoritative (only a critical keyword sets it). Otherwise re-run the
    summarizer's hard_rule_alert — a reason means a hard rule fired; None means
    the LLM/deterministic path made the call. group_type/keywords come from
    group_config; absent config degrades the keyword + daycare/vaad rules to
    'LLM / context' (the surface notes when config is missing)."""
    if _truthy(row.get("critical")):
        return RULE_CRITICAL
    reason, _ = was.hard_rule_alert(_row_to_msg(row), group_config)
    return reason or RULE_LLM


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
@dataclass
class Metrics:
    start: date
    end: date
    days: int
    total_in_window: int = 0
    by_class: dict = field(default_factory=dict)       # ROUTINE/DIGEST/ALERT counts
    alerts: list = field(default_factory=list)         # in-window ALERT rows (+ _rule/_time)
    criticals: int = 0
    dispatched: int = 0                                # alerts actually queued to phones
    floated: int = 0                                   # action_owner == none (needs-a-look)
    by_rule: dict = field(default_factory=dict)        # rule label -> [alert rows]
    by_group_type: dict = field(default_factory=dict)  # group_type -> alert count
    undated: int = 0                                   # excluded: unparseable received_at
    fp_target: int = cfg.ALERT_FP_TARGET_PER_WEEK
    config_loaded: bool = True


def collect(rows: list[dict], today: date, days: int, group_config: dict) -> Metrics:
    """Pure compute over Inbox dict-rows → Metrics for the trailing `days`
    window ending `today` (inclusive)."""
    start = today - timedelta(days=days - 1)
    m = Metrics(start=start, end=today, days=days,
                config_loaded=bool(group_config))
    for r in rows:
        d = _row_date(r)
        if d is None:
            m.undated += 1
            continue
        if not (start <= d <= today):
            continue
        m.total_in_window += 1
        klass = str(r.get("classification", "") or "").strip().upper()
        m.by_class[klass] = m.by_class.get(klass, 0) + 1
        if klass != "ALERT":
            continue
        r = dict(r)  # don't mutate the caller's row
        r["_rule"] = derive_rule(r, group_config)
        r["_time"] = f"{was._parse_dt(r.get('received_at', '')):%H:%M}"
        m.alerts.append(r)
        if _truthy(r.get("critical")):
            m.criticals += 1
        if _truthy(r.get("dispatched")):
            m.dispatched += 1
        if (r.get("action_owner") or "none") == "none":
            m.floated += 1
        gt = str(r.get("group_type", "") or "")
        m.by_group_type[gt] = m.by_group_type.get(gt, 0) + 1
        m.by_rule.setdefault(r["_rule"], []).append(r)
    return m


def _rules_sorted(by_rule: dict) -> list:
    return sorted(by_rule.items(), key=lambda kv: (-len(kv[1]), kv[0]))


# ---------------------------------------------------------------------------
# Render — brief (weekly briefing section) + full (standalone operator surface)
# ---------------------------------------------------------------------------
def render_brief(m: Metrics) -> str:
    """Compact pulse for the weekly briefing — tells the PO whether to look."""
    if m.total_in_window == 0:
        return f"_No group messages classified in the last {m.days} days._"
    a = m.by_class.get("ALERT", 0)
    lines = [
        f"**Last {m.days}d:** {m.total_in_window} messages classified — "
        f"{a} ALERT ({m.criticals} critical), {m.by_class.get('DIGEST', 0)} digest, "
        f"{m.by_class.get('ROUTINE', 0)} routine."
    ]
    if a:
        by_rule = ", ".join(f"{rule} ×{len(rs)}" for rule, rs in _rules_sorted(m.by_rule))
        lines.append(f"ALERTs by rule: {by_rule}.")
        if m.floated:
            lines.append(f"{m.floated} floated to “needs a look” (no recipient routed).")
    lines.append(
        f"_Target: <{m.fp_target} ALERT-tier false positive/week. "
        f"Run `accuracy_review.py` to scan each ALERT and narrow any over-firing "
        f"keyword pattern (group-config seed)._")
    return "\n".join(lines)


def render_full(m: Metrics) -> str:
    """The full operator surface — every ALERT, grouped by triggering rule, for
    the human false-positive judgment."""
    parts = [
        "# 🏠 Family inc. — Classifier accuracy review",
        f"_{m.end.isoformat()} · last {m.days} days "
        f"({m.start.isoformat()} → {m.end.isoformat()})_\n",
        "## Summary",
        f"- {m.total_in_window} messages classified"
        + (f"  (+{m.undated} undated, excluded)" if m.undated else ""),
        f"- ROUTINE {m.by_class.get('ROUTINE', 0)} · DIGEST {m.by_class.get('DIGEST', 0)}"
        f" · ALERT {m.by_class.get('ALERT', 0)}",
        f"- ALERT-tier: {m.criticals} critical · {m.dispatched} sent to phones · "
        f"{m.floated} floated to “needs a look”",
        f"- **Target: <{m.fp_target} ALERT-tier false positive per week.** A false "
        f"positive is an ALERT that shouldn't have interrupted — tally them by eye below.",
    ]
    if not m.config_loaded:
        parts.append("- ⚠ group-config seed not found — keyword/daycare/vaad rules "
                     "couldn't be re-derived (they show as “LLM / context”).")
    if not m.alerts:
        parts.append("\n## ALERTs\n\n_No ALERT-tier classifications in the window — "
                     "nothing to review._")
        return "\n".join(parts) + "\n"

    parts.append("\n## ALERTs by triggering rule")
    for rule, rs in _rules_sorted(m.by_rule):
        parts.append(f"\n### {rule} — {len(rs)}")
        for a in sorted(rs, key=lambda r: str(r.get("received_at", ""))):
            if _truthy(a.get("dispatched")):
                disp = "sent"
            elif (a.get("action_owner") or "none") == "none":
                disp = "needs-a-look"
            else:
                disp = "in-digest"
            grp = was.DIGEST_GROUP_LABEL.get(str(a.get("group_type", "")),
                                             a.get("group_type", "") or "?")
            summary = a.get("one_liner") or _clip(a.get("text", ""))
            parts.append(f"- [{disp}] **{grp}** · {a.get('sender_name', '?')} · "
                         f"{a.get('_time', '')} — {summary}")
    parts.append(
        "\n---\n_Narrow any pattern that over-fires in the group-config seed "
        "(alert_keywords / critical_keywords), or adjust the rule; log the change "
        "in DECISIONS. Measuring an exact FP rate needs a human-mark channel "
        "(deferred, D-048)._")
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def run(today: date, days: int, dry_run: bool = False,
        sheet_path: Optional[Path] = None,
        config_path: Optional[Path] = None) -> Optional[Path]:
    group_config = was.load_config(config_path or was.CONFIG_DEFAULT)
    live = True if sheet_path is not None else sheet.is_live()
    wb = sheet.workbook(sheet_path)  # live Sheet when configured, else seed/explicit
    rows = _tab_rows(wb, TAB)
    if not rows and not live:
        print("(no live Sheet backend — nothing to review)")
    m = collect(rows, today, days, group_config)
    print(f"accuracy review · {m.start} → {m.end} ({m.days}d): "
          f"{m.total_in_window} classified · {m.by_class.get('ALERT', 0)} ALERT "
          f"({m.criticals} critical, {m.floated} needs-a-look)")
    body = render_full(m)
    if dry_run:
        print("\n" + body)
        return None
    cfg.BRIEFINGS_DIR.mkdir(exist_ok=True)
    out = cfg.BRIEFINGS_DIR / f"{today.isoformat()}_accuracy_review.md"
    out.write_text(body, encoding="utf-8")
    print(f"wrote {out}")
    return out


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", help="YYYY-MM-DD; defaults to today")
    ap.add_argument("--weeks", type=int, help="review the last N weeks (×7 days)")
    ap.add_argument("--days", type=int, help="review the last N days "
                    f"(default {cfg.ACCURACY_REVIEW_DAYS})")
    ap.add_argument("--dry-run", action="store_true", help="print only, write nothing")
    ap.add_argument("--sheet", help="explicit xlsx path (tooling/tests)")
    ap.add_argument("--config", help="group-config CSV (rule re-derivation)")
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    days = (7 * args.weeks) if args.weeks else (args.days or cfg.ACCURACY_REVIEW_DAYS)
    run(today, days, dry_run=args.dry_run,
        sheet_path=Path(args.sheet) if args.sheet else None,
        config_path=Path(args.config) if args.config else None)


if __name__ == "__main__":
    main()
