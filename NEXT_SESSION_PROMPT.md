# Next session — Family Inc

*Generated 2026-06-25 by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current focus only.

**Current focus: v3 Today redesign — V3.7 love-notes (parent-to-parent ephemeral note; appliance endpoint + Cloudflare Tunnel, **text first / voice second**) (V3.6 cross-domain timeline landed 2026-06-25 — PO calls ratified, SPEC §7.6 graduated; V3.7 is Sheet-independent — the first dashboard datum that is **neither the Sheet nor the outbox** — and needs the love-note on-box storage shape + the `pages.yml` sed / `DASHBOARD_LOVENOTE_URL` secret / 4th config-smoke anchor; the voice phase needs the SPEC §4 carve-out; V3.3 snooze still gates on Lane C).**

*(The focus headline is set by a `**Focus:** …` pin in `BACKLOG.md` → `## Now`; absent a pin it's the freshest 🔵 lane.)*

Active lanes (🔵 in progress — work the focus above first; don't open the others without a PO call):

- M6.3 — consumer wiring + close. Briefing Money section + dashboard Money drawer read live; the >35d stale-import warning is armed (`FINANCE_STALE_IMPORT_DAYS`). Budget-SUMIFS installer ran live …
- M6.4 — analysis layer. *Repo half built + tested (2026-06-18).* The on-box rules engine (`automation/lib/categorize.py` + committed `seeds/14_Finance_Category_Rules.csv`) populates …
- M6.5 — cards lane (un-deferred 2026-06-23, the third VPS hour). Cal (Visa) is live — hooked up via a one-time headed `--auth` device-trust login (xvfb + x11vnc over an SSH tunnel; `FINANCE.md §4`) …
- v3 Today redesign (decided 2026-06-25; building). The dashboard Today surface gets a cool retone + new IA + two net-new components (parent-to-parent love-note, cross-domain timeline). 8 design calls …

Recent commits (the dated decision record — decisions fold into the canon, not a separate log):

- 2026-06-25 docs: regenerate next-session prompt (post V3.5)
- 2026-06-25 feat(dashboard): V3.5 — portfolios + one data-driven bottom-sheet (replaces the accordions)
- 2026-06-25 feat(dashboard): V3.4 — 3-day scroll-snap calendar strip
- 2026-06-25 feat(dashboard): V3.2 — Today scaffold + 3-tier status pill (replaces pill + banner)
- 2026-06-25 fix(kickoff): focus follows a PO Focus pin + all 🔵 lanes, not a stale section title
- 2026-06-25 docs: regenerate next-session prompt (post V3.1 retone)

Session contract: don't open lanes outside the current focus without a PO call ·
constants → config, utilities → `automation/lib/`, message copy → templates ·
a directional call = edit the relevant canon doc to the new present-tense state
(short inline *why* if non-obvious) with the dated rationale in the commit message ·
session end: tests green if code moved, `BACKLOG.md` flipped, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
