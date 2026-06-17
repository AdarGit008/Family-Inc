# Resume prompt — Family Inc (hand-written 2026-06-16, post-D-040)

*Paste everything below the line to open the next session from the exact point. This is a hand-written exact-resume artifact, NOT the `session_kickoff.py` output — `NEXT_SESSION_PROMPT.md` is the canonical generic opener, but it names **M4** as "current" (it sorts first and has open ⬜ items), whereas the real immediate action is the **M5 Apify deploy** below; M4 is gated ≥1 week live (~2026-06-20). Delete this file once M5 is closed.*

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md` (roles, principles, guardrails), then `BACKLOG.md` (M5 section) + `DECISIONS.md` D-037→D-040. Everything below is the exact state at the end of the 2026-06-16 D-040 session.

## Where we are (exact)

- **v1 is live + accepted** (`v1-live`). The D-040 change is committed + pushed (Mac) — confirm with `git log --oneline -3` (expect the D-040 commit at/near HEAD).
- **M5 property tracker is BUILT and the anti-bot wall is RESOLVED in code (D-040).** D-039 proved the block is the VPS **datacenter IP**, not the browser, so Apify was added as a **SECONDARY** source (`automation/lib/apify.py`): the on-box Chromium scraper stays primary and unchanged; Apify (its own residential proxy pool) is consulted per saved-search only when the primary is blocked/empty (backup) or has missing fields (gap-fill), merged with the **primary always winning**. Actors: `amit123~yadscraper` (Yad2, reuses the saved-search URL) + `swerve~madlan-scraper` (Madlan, parametric). Strict fail-loud / no-invented-data; **per-search + per-kind once/day** cost gate (milestone review CRITICAL, D-040); token-gated **inert without `FAMILY_INC_APIFY_TOKEN`**. 259 tests green.
- Milestone review was run + resolved in-session (`reviews/review_milestone_2026-06-16_10-32.md`): the per-search/per-kind gate is the applied CRITICAL fix; the §11 ≤₪120/mo ceiling is monitored-not-enforced (monthly result-counter cap is a logged v1.1 candidate).

## DO FIRST — close M5 (PO deploy on the VPS, as `familyinc`)

The whole lane is inert until the token is placed; the appliance is currently untouched by D-040.

1. `./deploy/deploy.sh` (pull → sync → tests → restart); run `sudo ./deploy/provision.sh` once if Chromium for the primary isn't installed.
2. **`/etc/family-inc/env`** (mode 600): add `FAMILY_INC_APIFY_TOKEN=…` (Apify Console → API & Integrations; free tier seeds enough credit to verify).
3. **`/etc/family-inc/property_searches.json`**: real saved searches; **each Madlan entry needs an `apify: {city, dealType, …}` block** (swerve is parametric — Yad2 needs nothing, it reuses the url). Template: `deploy/property_searches.example.json`.
4. `sudo systemctl enable --now family-property.timer && sudo systemctl start family-property.service`, then `journalctl -u family-property.service -n 60`. With the IP blocked this exercises the Apify backup end-to-end — verify `Property-Listings` rows land + the morning "🏠 דירות חדשות" section appears.
5. **M5 closes** once a live scrape is verified. Flip `BACKLOG.md` M5 → ✅; the external-model review folds into the M4 "review on the live system" item (D-035 precedent) — no separate run.

## Then / also true

- **M4 (summarizer hardening)** is the next milestone after ≥1 week live (earliest ~2026-06-20). Decided-but-unbuilt: DeepSeek backend wiring (D-032), 30-day `WhatsApp_Inbox` rolloff (D-036), quiet-day partner-symmetry (D-036), sender→role roster, Phase F weekly accuracy surface. Don't start until the gate passes.
- v1.1 candidate logged this session: an Apify monthly result-counter cap (programmatic §11 backstop).

## Working-environment quirks

- **Git index ops run on the PO's Mac, never the sandbox.** Stale `.git/index.lock` → `rm -f .git/index.lock` on the Mac. In the sandbox, inspect git read-only only (`git --no-optional-locks status`).
- **Sandbox tests:** `cd` repo, `export UV_PROJECT_ENVIRONMENT=$HOME/fi-venv`, `uv run --frozen pytest -q` (259). The repo `.venv` is macOS-only.
- **Apify is untestable live in the sandbox** (no token/network) — the suite covers it via a `runner` injection seam; `_run_actor` is the only network call and is never hit by tests.

## Session contract

Don't open lanes outside the chosen work without a PO call logged as the next D-number · constants → `automation/lib/config.py`, utilities → `automation/lib/`, copy → `templates.py` · session end: tests green if code moved, `BACKLOG.md` flipped, directional calls logged, regenerate `NEXT_SESSION_PROMPT.md`, and hand the PO ONE terminal block. Git index operations run on the PO's machine, never in the sandbox.
