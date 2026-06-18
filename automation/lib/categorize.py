"""
Family inc. — finance categorization (SPEC §12.2 / §8.6, M6.4; D-050/051).

Two stages, both degrade-quiet (§3.6):

  1. On-box rules engine — seeds/14_Finance_Category_Rules.csv maps a keyword
     (case-insensitive SUBSTRING, Hebrew or English) to a category. Applied to
     EVERY transaction; first match wins (rows are ordered specific→general).
     Most transactions are tagged here and never leave the box.

  2. DeepSeek gap-fill (lib/llm) — ONLY the rules-miss remainder, and ONLY each
     transaction's DESCRIPTION + AMOUNT (never the account, balance, Txn-ID,
     identifier, or the whole ledger — §8.6). The model must answer with a
     category from the rules file's own vocabulary or "UNKNOWN"; anything else
     leaves the transaction blank.

Cat-Source: "rules" | "llm" | "" (blank = uncategorized — the budget SUMIFS
just won't bucket it, and a human can fill it later). Nothing here raises into
the ingest: a missing rules file, a missing key, an LLM error, or an off-vocab
answer all collapse to "leave it blank".
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from automation.lib import config

log = logging.getLogger("finance.categorize")

# Per-prompt cap so a pathological import can't balloon a single LLM request.
# It is a CHUNK size, not a ceiling: `_gapfill` loops over all rules-misses in
# batches of this size, so every miss is categorized before the write. (A miss
# left blank would be appended with its real Txn-ID, then excluded from dedup
# forever — never re-presented to the LLM — so a one-shot 80-cap was permanent
# data loss on the first 45-day backlog. B5, audit 2026-06-18.)
GAPFILL_MAX_BATCH = 80


# ---------------------------------------------------------------------------
# Rules (stage 1) — pure, on-box
# ---------------------------------------------------------------------------
def load_rules(path: Optional[Path] = None) -> list[tuple[str, str]]:
    """Parse the rules CSV → [(pattern_casefolded, category)], file order kept.
    Comment (#) / blank / header lines are skipped; a missing file → [] (the
    rules engine no-ops, degrade quiet). Patterns are casefolded once here so
    matching is a plain case-insensitive substring test."""
    path = Path(path or config.FINANCE_CATEGORY_RULES)
    if not path.exists():
        log.warning("no finance category rules at %s — rules engine no-ops", path)
        return []
    rules: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.casefold().startswith("pattern,"):
            continue
        pat, _, cat = s.partition(",")
        pat, cat = pat.strip(), cat.strip()
        if pat and cat:
            rules.append((pat.casefold(), cat))
    return rules


def vocabulary(rules: list[tuple[str, str]]) -> list[str]:
    """Distinct categories in file order — the ONLY labels gap-fill may use."""
    seen: set[str] = set()
    out: list[str] = []
    for _, cat in rules:
        if cat not in seen:
            seen.add(cat)
            out.append(cat)
    return out


def apply_rules(description: str, rules: list[tuple[str, str]]) -> Optional[str]:
    """First category whose keyword is a substring of the description, else None."""
    d = (description or "").casefold()
    if not d:
        return None
    for pat, cat in rules:
        if pat in d:
            return cat
    return None


# ---------------------------------------------------------------------------
# Orchestration — rules first, then the bounded gap-fill
# ---------------------------------------------------------------------------
def categorize_transactions(txns: list[dict], *, allow_llm: bool = True,
                            rules_path: Optional[Path] = None) -> None:
    """Populate Category + Cat-Source on each txn dict IN PLACE (Finance-
    Transactions shape). Rules run on every still-blank txn; then, when
    `allow_llm` and a provider key is configured, the LLM gap-fills the
    rules-miss remainder. A txn that already carries a Category is left as-is."""
    if not txns:
        return
    rules = load_rules(rules_path)
    misses: list[dict] = []
    for t in txns:
        if str(t.get("Category", "") or "").strip():   # already categorized
            continue
        cat = apply_rules(t.get("Description", ""), rules)
        if cat:
            t["Category"], t["Cat-Source"] = cat, "rules"
        else:
            misses.append(t)
    if allow_llm and misses:
        _gapfill(misses, vocabulary(rules))


def _gapfill(misses: list[dict], vocab: list[str]) -> None:
    """DeepSeek (or the configured fallback) over the rules-miss remainder, in
    chunks of GAPFILL_MAX_BATCH so the WHOLE remainder is categorized before the
    write — a large first import (the 45-day backlog) is fully covered, not
    truncated at the per-prompt cap. No vocab / no key → no-op. lib/llm is
    imported lazily so a keyless box pays nothing and the import never hinges on
    the LLM module."""
    if not vocab:
        return
    from automation.lib import llm
    if not llm.available():
        return
    for start in range(0, len(misses), GAPFILL_MAX_BATCH):
        _gapfill_batch(misses[start:start + GAPFILL_MAX_BATCH], vocab, llm)


def _gapfill_batch(batch: list[dict], vocab: list[str], llm) -> None:
    """One LLM request over <= GAPFILL_MAX_BATCH rules-misses. A failed/empty
    reply leaves THIS chunk blank (degrade quiet, §3.6) without aborting the
    other chunks — those rows can still be filled by a human or a later run."""
    # Privacy seam: each line carries a within-batch INDEX (not the Txn-ID), the
    # amount, and the description — nothing else from the row ever leaves the box.
    lines = []
    for i, t in enumerate(batch):
        amt = t.get("Amount (ILS)", "")
        desc = str(t.get("Description", "") or "").replace("\n", " ").strip()
        lines.append(f"{i}\t{amt}\t{desc}")
    system = (
        "You categorize Israeli household bank and credit-card transactions. "
        "For each line choose EXACTLY ONE category from this list:\n"
        f"{', '.join(vocab)}\n"
        'If none clearly fits, use "UNKNOWN". Decide from the description and '
        "amount only. Reply with a JSON object of the form "
        '{"results":[{"i":<index>,"category":"<one listed category or UNKNOWN>"}]}.'
    )
    prompt = "index\tamount\tdescription\n" + "\n".join(lines)
    # Size the reply budget to the chunk. A full GAPFILL_MAX_BATCH reply of
    # {"i":N,"category":"…"} items runs ~1.5k tokens — a fixed 600 truncates the
    # JSON array mid-stream, and a truncated object recovers NOTHING, so the
    # WHOLE chunk would land blank with real Txn-IDs and never be re-presented
    # (the very B5 data-loss this loop closes). ~24 tok/row + floor.
    raw = llm.complete(prompt, task="categorize", system=system,
                       max_tokens=max(256, len(batch) * 24),
                       source="finance.categorize", json_mode=True)
    if not raw:
        return
    for i, cat in _parse_gapfill(raw, vocab, len(batch)).items():
        batch[i]["Category"], batch[i]["Cat-Source"] = cat, "llm"


def _parse_gapfill(raw: str, vocab: list[str], n: int) -> dict[int, str]:
    """Tolerant parse: the first JSON object in the reply (DeepSeek json_mode is
    clean; the Anthropic fallback may wrap prose). Keep only in-range indices
    mapped to an in-vocab category (case-insensitive); drop UNKNOWN / off-vocab."""
    obj = _first_json_object(raw)
    if not isinstance(obj, dict):
        return {}
    canon = {c.casefold(): c for c in vocab}
    out: dict[int, str] = {}
    for item in obj.get("results") or []:
        if not isinstance(item, dict):
            continue
        try:
            i = int(item["i"])
        except (KeyError, TypeError, ValueError):
            continue
        cat = canon.get(str(item.get("category", "")).strip().casefold())
        if cat is not None and 0 <= i < n:
            out[i] = cat
    return out


def _first_json_object(raw: str):
    try:
        return json.loads(raw)
    except ValueError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except ValueError:
            return None
