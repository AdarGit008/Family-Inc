"""Dashboard STRINGS he/en parity (V3 lane — the cheapest bilingual guard).

`t()` is fail-visible: a key present in one language but missing in the other
echoes the dotted key on screen (DESIGN §7 / the V3 build plan §5 flag this as
the largest bilingual hole). The JS suite is `node --check` syntax-only, so a
he-only / en-only key would only surface as a raw `timeline.cat.car` leaking into
the UI. This pins the floor hermetically (no node, no DOM): every key in
`STRINGS.he` must exist in `STRINGS.en` and vice-versa.

Parsing is deliberately shallow — keys are `'dotted.key':` at line start; values
(which never start a line) are ignored — so it can't be fooled by a colon or an
apostrophe inside a value.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_JS = ROOT / "dashboard" / "app.js"

# A STRINGS entry: leading whitespace, a single-quoted dotted key, then a colon.
KEY_RE = re.compile(r"^\s*'([\w.]+)'\s*:", re.MULTILINE)


def _string_keys():
    src = APP_JS.read_text(encoding="utf-8")
    strings_at = src.index("const STRINGS = {")
    he_at = src.index("he: {", strings_at)
    en_at = src.index("en: {", he_at)
    end_at = src.index("\n  };", en_at)          # closes the STRINGS object literal
    he_block = src[he_at:en_at]
    en_block = src[en_at:end_at]
    return set(KEY_RE.findall(he_block)), set(KEY_RE.findall(en_block))


def test_strings_he_en_parity():
    he, en = _string_keys()
    # Sanity: the extraction actually found the table (guards a refactor that
    # moves/renames STRINGS and would otherwise make this test vacuously pass).
    assert len(he) > 50, f"parsed only {len(he)} he keys — STRINGS shape changed?"
    missing_in_en = sorted(he - en)
    missing_in_he = sorted(en - he)
    assert not missing_in_en, f"keys in he but missing from en: {missing_in_en}"
    assert not missing_in_he, f"keys in en but missing from he: {missing_in_he}"
