"""Repo-wide PII / secret guard (ROADMAP §1, lane 1 — the CI leak guard).

test_seed_safety.py guards the binary seed's CELLS; this guards every tracked
TEXT file, so a real email / phone / JID / Teudat-Zehut / account number / ILS
transaction value pasted into code, docs, or config fails before it can merge.
Same patterns (automation/lib/pii) as the seed guard — one source of truth.

Scoped + allowlisted (PO call, 2026-06-22): files that hold synthetic money by
design (the test fixtures, seeds, the dashboard DEMO blob, the binary seed) are
exempt from the ILS-amount check; the identifier checks apply everywhere a real
value could leak. A flagged synthetic value is a one-line allowlist addition; a
flagged real value is the leak this guard exists to stop.

It rides the normal pytest suite, so deploy/deploy.sh runs it on the box too —
no deploy.sh change. Like the seed guard, it fails loud rather than pass
vacuously if it cannot enumerate or scan the tree.

Known limits (the threat is an ACCIDENTAL paste, not a motivated evader): the
scan is line-by-line, so a value deliberately split across lines is not caught;
and the ILS-amount check is skipped on .md prose (identifiers are still scanned
there), so a real amount typed into a markdown note relies on human review. Both
are accepted under the scoped model — accidental pastes land whole and on one
line, in code/data, where the guard does scan.
"""
import subprocess
from pathlib import Path

from automation.lib import pii

ROOT = Path(__file__).resolve().parent.parent

# Synthetic-by-design (or non-text) — exempt from the whole scan.
#   tests/, seeds/   — synthetic fixtures + the committed rules CSV.
#   reviews/         — dated external-model review transcripts: illustrative
#                      currency-format examples (₪4,280.00), redacted JID
#                      placeholders, and public brand addresses, by construction.
#   Archive/         — superseded canon + design docs (read-only history), same.
# These are prose artifacts, not the live surface, and their synthetic ILS amounts
# are shape-identical to real values — only path-scoping can exempt them. The live
# surface (automation/, dashboard/, deploy/, canon docs, config) stays scanned.
_ALLOW_PREFIXES = ("tests/", "seeds/", "reviews/", "Archive/")
_ALLOW_FILES = {
    "dashboard/mock_data.json",                 # the DEMO_MODE blob — synthetic finance
    "automation/lib/pii.py",                     # the pattern definitions themselves
    "automation/lib/money.py",                   # the ILS formatter — its docstring shows ₪ examples
    "uv.lock",                                   # dependency hashes — long digit runs
    "automation/bridge/package-lock.json",
    "automation/finance/package-lock.json",
}
_BINARY_EXT = {".xlsx", ".png", ".ico", ".jpg", ".jpeg", ".gif", ".pdf",
               ".woff", ".woff2", ".ttf"}


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return [p for p in out.stdout.splitlines() if p]


def _allowlisted(rel: str) -> bool:
    return (rel in _ALLOW_FILES
            or rel.startswith(_ALLOW_PREFIXES)
            or Path(rel).suffix.lower() in _BINARY_EXT)


def _is_binary(p: Path) -> bool:
    try:
        return b"\x00" in p.read_bytes()[:4096]
    except OSError:
        return True


def test_no_pii_in_tracked_files():
    files = _tracked_files()
    # A guard that enumerates nothing is false safety (mirrors the seed guard).
    assert len(files) > 50, (
        f"git ls-files returned only {len(files)} paths — the guard would scan "
        "almost nothing. Run from the repo checkout.")

    scanned, leaks = 0, []
    for rel in files:
        if _allowlisted(rel):
            continue
        p = ROOT / rel
        if _is_binary(p):
            continue
        scanned += 1
        # Identifiers (email/phone/JID/ID/account) are NEVER legitimately in prose,
        # so they are scanned everywhere. ILS amounts ARE — every design doc shows
        # example money — and a real value is shape-identical, so the amount check
        # skips Markdown prose and rides only code/data/config, where a real bank
        # dump would actually leak.
        check_amounts = p.suffix.lower() != ".md"
        for lineno, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
            kinds = pii.scan(line)
            if check_amounts and pii.ILS_AMOUNT.search(line):
                kinds.append("ILS-amount")
            for kind in kinds:
                leaks.append(f"{rel}:{lineno}: {kind}")

    assert scanned > 30, (
        f"only {scanned} text files scanned — the allowlist/binary filter is too "
        "broad; the guard is near-vacuous.")
    assert not leaks, (
        "Tracked files carry real PII — the repo is public-safe by construction "
        "(CLAUDE.md). Scrub the value to a placeholder, move it to the Sheet / "
        "/etc/family-inc/, or — if it is synthetic-by-design — add its path to the "
        "allowlist in this test. Offending lines:\n  " + "\n  ".join(sorted(set(leaks))))
