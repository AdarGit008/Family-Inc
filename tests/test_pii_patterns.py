"""Detection-contract for automation/lib/pii — the shared patterns behind both
the seed guard and the repo-wide guard. Pins what MUST be caught and (just as
important) the real false-positive shapes found in the live tree on 2026-06-22,
so a future pattern tweak can't silently blind the guard or start failing CI on
benign systemd units / version strings / ₪0 mentions.
"""
import pytest

from automation.lib import pii

# (text, expected kind in pii.scan) — a real value that MUST be flagged.
_MUST_FLAG_IDENTIFIERS = [
    ("contact adar008@gmail.com please", "real-email"),
    ("call 050-123-4567 today", "IL-phone"),
    ("+972 50-123-4567", "IL-phone"),
    ("route 972501234567@s.whatsapp.net", "JID"),       # real numeric JID
    ("acct 1234567890123 debited", "account-number"),    # 13 digits
    ("teudat 318273645 on file", "teudat-zehut"),        # 9 mixed digits
]

# Strings that must produce NO identifier hit (the live-tree false positives).
_MUST_NOT_FLAG_IDENTIFIERS = [
    "fallback you@example.com only",                     # placeholder domain
    "{ match: 'noreply@iec.co.il' }",                    # public role mailbox
    '"adar": "9725XXXXXXXX@s.whatsapp.net"',             # redacted JID placeholder
    "jid.endsWith('@g.us')",                             # bare JID suffix in code
    "OnFailure=family-fail-flag@%n.service",             # systemd unit template
    "SMTP_USER=…@gmail.com",                             # env-var doc placeholder
    "id 000000000 placeholder",                          # all-same-digit Teudat-Zehut
    "ratio 98/98 idempotent",                            # not an account number
]

# ILS amounts that MUST be flagged (transaction-shaped).
_MUST_FLAG_AMOUNTS = ["₪1,234.56", "1,847.32", "₪50.00", "1234.56 ILS", "₪2,450,000", '3,200.00 ש"ח']

# Money-ish text that must NOT be flagged as an ILS amount.
_MUST_NOT_FLAG_AMOUNTS = [
    "~₪0/mo",                # bare zero
    "requests>=2.32",        # version string
    "max age 1.4h",          # not money
    "390/390 green",         # ratio
    "budget 12,500 rooms",   # grouped but no agorot / currency
    "alert budget 2/day",    # ratio
]


@pytest.mark.parametrize("text,kind", _MUST_FLAG_IDENTIFIERS)
def test_identifiers_are_flagged(text, kind):
    assert kind in pii.scan(text), f"{text!r} should flag {kind}"


@pytest.mark.parametrize("text", _MUST_NOT_FLAG_IDENTIFIERS)
def test_benign_identifiers_are_not_flagged(text):
    assert pii.scan(text) == [], f"{text!r} should be clean, got {pii.scan(text)}"


@pytest.mark.parametrize("text", _MUST_FLAG_AMOUNTS)
def test_amounts_are_flagged(text):
    assert pii.ILS_AMOUNT.search(text), f"{text!r} should flag as an ILS amount"


@pytest.mark.parametrize("text", _MUST_NOT_FLAG_AMOUNTS)
def test_benign_amounts_are_not_flagged(text):
    assert not pii.ILS_AMOUNT.search(text), f"{text!r} should NOT flag as an ILS amount"
