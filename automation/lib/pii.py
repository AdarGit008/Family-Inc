"""Shared PII / secret detection patterns — one source of truth.

Two guards consume these:
  • tests/test_seed_safety.py — scans the committed Family_OS.xlsx cells.
  • tests/test_repo_pii_guard.py — scans every tracked text file in the repo.

The repo is "public-safe by construction" (CLAUDE.md): no real emails, phone
numbers, JIDs, Teudat-Zehut, account numbers, or real finance values may enter a
committed file. The two adult principals' first names Adar / Shanee are the one
accepted-public identifier (owner-routing tokens, Settings UserMap, git author),
so they are NOT matched here.

`scan()` returns the high-severity IDENTIFIER kinds (the set the binary seed is
guarded against). ILS amounts are intentionally NOT in `scan()` — the seed holds
synthetic finance values by design, so the seed guard must not flag them. The
tree guard applies `ILS_AMOUNT` separately, only outside its synthetic-by-design
allowlist.

This file is itself allowlisted by the tree guard (it necessarily carries the
pattern fragments), so this docstring may speak freely.
"""
import re

# Email-shaped token: an RFC-ish local part (kept tight so it does not swallow a
# leading quote / backtick / `SMTP_USER=` prefix / `…` placeholder), then a domain
# kept charset-agnostic (not ASCII-only) so a Unicode/Hebrew domain can't slip.
EMAIL_SHAPE = re.compile(r'([A-Za-z0-9._%+\-]+)@([^\s@]+\.[^\s@]+)')
PLACEHOLDER_DOMAIN = re.compile(r'^(?:example\.|test\.|placeholder|localhost)', re.I)
# Wrapping punctuation the domain capture may pick up ("…net", net), `net`).
_DOMAIN_STRIP = "\"'`()[]{}<>,;:!?*\\… \t"
# Domains that are email-SHAPED but never a personal address: JID domains (caught
# by the JID check, not double-flagged) and systemd unit templates
# (`family-fail-flag@%n.service` — the `%` specifier / .service/.timer suffix).
_JID_DOMAIN = {"s.whatsapp.net", "g.us", "lid"}
_UNIT_SUFFIX = ("service", "timer", "socket", "mount", "target")
# Role mailboxes are non-personal by construction (public no-reply senders a bill
# parser matches), so they are not the household PII this guard protects.
_ROLE_LOCALPART = re.compile(r'^(?:noreply|no-reply|donotreply|do-not-reply)$', re.I)

# Israeli mobile: +972 / 0 prefix, then 05X-XXX-XXXX with flexible spacing.
IL_MOBILE = re.compile(r'(?:\+?972[\-\s]?|0)5\d[\-\s]?\d{3}[\-\s]?\d{4}')

# A real WhatsApp JID — a numeric phone/group identifier before the suffix. The
# `\d{9,}` requirement is deliberate: it flags a real `972…@s.whatsapp.net` but
# NOT a redacted placeholder (`9725XXXX@…`) or a bare suffix reference in bridge
# code/docs that legitimately routes on `@s.whatsapp.net`.
JID = re.compile(r'\d{9,}@(?:s\.whatsapp\.net|g\.us|lid)\b')

# 12+ consecutive digits — IBAN / full account / card number.
LONG_ACCT = re.compile(r'(?<!\d)\d{12,}(?!\d)')

# Transaction-shaped ILS amount. Deliberately NARROW so it never fires on version
# strings (2.32), ratios (98/98), counts (390), or "₪0" doc mentions: it requires
# EITHER a thousands separator with agorot, OR an explicit currency token next to
# a decimal, OR the ₪ glyph beside a grouped/decimal number. Real Mizrahi values
# carry agorot or grouping, so this is the high-signal, low-false-positive shape.
#   matches:  1,847.32   ₪1,234.56   ₪50.00   1234.56 ILS   3,200.00 ש"ח
#   ignores:  2.32   98/98   390   ₪0   2/day   50_000   12,500 (no agorot)
_CUR = r'(?:₪|ILS|NIS|ש"ח|ש״ח|שח)'
ILS_AMOUNT = re.compile(
    r'(?:₪\s?\d{1,3}(?:,\d{3})+(?:\.\d{2})?)'        # ₪1,234 / ₪1,234.56
    r'|(?:₪\s?\d+\.\d{2})'                            # ₪50.00 / ₪1847.32
    r'|(?:(?<![\d.,])\d{1,3}(?:,\d{3})+\.\d{2})'      # 1,847.32 (grouped + agorot)
    r'|(?:(?<![\d.,])\d+\.\d{2}\s?' + _CUR + r')'     # 1234.56 ILS
)


def _is_real_personal_email(local: str, domain: str) -> bool:
    domain = domain.strip(_DOMAIN_STRIP)
    d = domain.lower()
    if PLACEHOLDER_DOMAIN.match(d):                 return False   # example./test./…
    if d in _JID_DOMAIN:                            return False   # a JID, not an email
    if "%" in domain:                               return False   # systemd specifier (%n)
    if d.rsplit(".", 1)[-1] in _UNIT_SUFFIX:        return False   # systemd unit name
    if _ROLE_LOCALPART.match(local):                return False   # noreply@… role mailbox
    return True


def has_real_email(s: str) -> bool:
    return any(_is_real_personal_email(m.group(1), m.group(2)) for m in EMAIL_SHAPE.finditer(s))


def has_real_teudat_zehut(s: str) -> bool:
    """A 9-digit Israeli ID that is not an all-same-digit placeholder (000000000)."""
    return any(len(set(m.group())) > 1 for m in re.finditer(r'(?<!\d)\d{9}(?!\d)', s))


def scan(s: str) -> list[str]:
    """High-severity IDENTIFIER kinds found in `s` (empty list if clean).

    Identifiers only — callers that also forbid finance values add `ILS_AMOUNT`
    themselves (the seed guard does not, since the seed is synthetic by design).
    """
    hits = []
    if has_real_email(s):          hits.append("real-email")
    if IL_MOBILE.search(s):        hits.append("IL-phone")
    if JID.search(s):              hits.append("JID")
    if LONG_ACCT.search(s):        hits.append("account-number")
    if has_real_teudat_zehut(s):   hits.append("teudat-zehut")
    return hits
