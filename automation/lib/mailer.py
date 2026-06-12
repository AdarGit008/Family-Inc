"""
Family inc. — SMTP email fallback (SPEC §10.2, delivery layer 2). The ONLY
smtplib import in the repo.

When the bridge heartbeat is stale past config.EMAIL_FALLBACK_AFTER_HOURS the
daily digest sends the identical rendered content here instead of queueing
rows the bridge can't deliver. No watcher process — the sender itself
degrades (SPEC §10.2).

NOT an outbox bypass (CLAUDE.md guardrail): the content arriving here already
passed outbox policy — assembly consumed the deferred queue, and the digest is
briefing-kind (budget-exempt). This substitutes the *transport* for one
already-policied message. Logged in DECISIONS.md D-027.

Config: SMTP_HOST/SMTP_PORT (defaults in lib/config.py), SMTP_USER/SMTP_PASS
(env-only, /etc/family-inc/env), FAMILY_INC_EMAIL_TO (comma-separated; unset
→ Settings.UserMap emails — degrades to env so the fallback path has no hard
Sheet dependency when infra is already sick).
"""
from __future__ import annotations

import logging
import os
import smtplib
from datetime import date
from email.message import EmailMessage

from automation.lib import config

log = logging.getLogger("mailer")


def fallback_recipients() -> list[str]:
    """FAMILY_INC_EMAIL_TO env first; else Settings.UserMap emails (best
    effort — the Sheet may be part of what's broken)."""
    raw = os.environ.get(config.EMAIL_TO_ENV, "")
    addrs = [a.strip() for a in raw.split(",") if a.strip()]
    if addrs:
        return addrs
    try:
        from automation.lib import sheet
        return sorted(sheet.read_settings().usermap.keys())
    except Exception as e:  # noqa: BLE001 — last-resort path; log + empty
        log.warning("no %s and Settings unreadable (%s)", config.EMAIL_TO_ENV, e)
        return []


def send_digest(messages: dict[str, str], stale_hours: float | None,
                today: date) -> bool:
    """Email the rendered digest to both adults. True = handed to the SMTP
    server. Never raises: any failure logs loudly and returns False so the
    caller can queue to the bridge outbox instead (delivery on reconnect)."""
    from automation import templates as T  # message copy stays reviewable there

    host = os.environ.get("SMTP_HOST", config.SMTP_DEFAULT_HOST)
    port = int(os.environ.get("SMTP_PORT", config.SMTP_DEFAULT_PORT))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    if not (user and password):
        log.error("email fallback: SMTP_USER/SMTP_PASS missing in /etc/family-inc/env")
        return False
    to = fallback_recipients()
    if not to:
        log.error("email fallback: no recipients — set %s", config.EMAIL_TO_ENV)
        return False

    hours = "?" if stale_hours is None else f"{stale_hours:.0f}"
    note = T.EMAIL_FALLBACK_NOTE.format(hours=hours)
    sections = [note, ""]
    for rcpt in sorted(messages):
        sections += [T.EMAIL_SECTION_HEAD.format(recipient=rcpt), messages[rcpt].rstrip(), ""]

    msg = EmailMessage()
    msg["Subject"] = T.EMAIL_FALLBACK_SUBJECT.format(date=today.strftime("%-d/%-m"))
    msg["From"] = user
    msg["To"] = ", ".join(to)
    msg.set_content("\n".join(sections))

    try:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls()
            s.login(user, password)
            s.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        log.error("email fallback failed (%s:%s): %s", host, port, e)
        return False
    log.info("email fallback delivered to %s", ", ".join(to))
    return True
