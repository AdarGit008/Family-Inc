"""Dashboard a11y — WCAG AA contrast assertion (V3.8).

The V3 retone deliberately darkened `--muted` (#5F6878) and `--amber` (#8A5E12)
to clear AA and paired `--on-accent` per theme; V3.8 gave `--blue` a dark value
so calendar times stay legible on dark tiles. This pins those engineered values
so a future retone can't silently regress them below AA (4.5:1 for normal text) —
"assert them, don't re-pick them" (`V3_BUILD_PLAN.md` §V3.8). Hermetic: it parses
`styles.css` and computes the WCAG contrast ratio in pure Python (no browser).

Scope note: the semantic hues `--green`/`--red` are asserted only where they sit
on white tiles (flags/text on `.row`); on the near-`--bg` status-pill washes they
read ~3.9–4.4 (large-ish pill text + a redundant glyph + label carry the meaning,
DESIGN §8) — a known, accepted nuance, not pinned here.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "dashboard" / "styles.css").read_text(encoding="utf-8")

_HEX = re.compile(r"--([\w-]+):\s*(#[0-9A-Fa-f]{6})\b")
AA = 4.5


def _tokens(marker: str) -> dict:
    """The #rrggbb tokens declared in the brace block opened by `marker`.

    The theme blocks have no nested braces, so a scan to the next `}` is exact.
    """
    start = CSS.index(marker)
    end = CSS.index("}", start)
    return dict(_HEX.findall(CSS[start:end]))


def _lin(c8: int) -> float:
    c = c8 / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _lum(hexv: str) -> float:
    r, g, b = (int(hexv[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _contrast(fg: str, bg: str) -> float:
    hi, lo = sorted((_lum(fg), _lum(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


LIGHT = _tokens(":root {")
DARK = _tokens(':root[data-theme="dark"] {')


def test_token_blocks_parsed():
    # Guard a refactor that renames/moves the token blocks (else everything below
    # would pass vacuously on an empty dict).
    need = {"bg", "tile", "muted", "amber", "accent", "on-accent", "blue", "green", "red"}
    assert need <= set(LIGHT), f"light token block changed shape: {sorted(LIGHT)}"
    assert need <= set(DARK), f"dark token block changed shape: {sorted(DARK)}"


def test_muted_clears_aa_both_surfaces_light():
    for bg in ("bg", "tile"):
        r = _contrast(LIGHT["muted"], LIGHT[bg])
        assert r >= AA, f"--muted {LIGHT['muted']} on --{bg} {LIGHT[bg]} = {r:.2f} < AA"


def test_muted_clears_aa_dark():
    r = _contrast(DARK["muted"], DARK["bg"])
    assert r >= AA, f"dark --muted {DARK['muted']} on --bg {DARK['bg']} = {r:.2f} < AA"


def test_amber_warn_text_clears_aa_on_tile_both_themes():
    # `.tile-status.is-warn` + `.stale-badge` render --amber as text on a tile;
    # pin both themes (the dark value #C79A4A ships and is used the same way).
    for theme, toks in (("light", LIGHT), ("dark", DARK)):
        r = _contrast(toks["amber"], toks["tile"])
        assert r >= AA, f"{theme} --amber {toks['amber']} on --tile = {r:.2f} < AA"


def test_on_accent_pressed_chip_clears_aa_both_themes():
    # The pressed timeline chip / primary button: text on an --accent fill.
    for theme, toks in (("light", LIGHT), ("dark", DARK)):
        r = _contrast(toks["on-accent"], toks["accent"])
        assert r >= AA, f"{theme} --on-accent on --accent = {r:.2f} < AA"


def test_blue_calendar_time_clears_aa_both_themes():
    # The V3.8 fix: --blue had no dark value (dark-blue-on-dark-tile). Pin both.
    assert _contrast(LIGHT["blue"], LIGHT["tile"]) >= AA, "light --blue on --tile < AA"
    assert _contrast(DARK["blue"], DARK["tile"]) >= AA, "dark --blue on --tile < AA"


def test_semantic_flags_clear_aa_on_tile():
    # --green/--red as flag text on a white card row.
    for tok in ("green", "red", "accent"):
        r = _contrast(LIGHT[tok], LIGHT["tile"])
        assert r >= AA, f"--{tok} {LIGHT[tok]} on --tile = {r:.2f} < AA"
