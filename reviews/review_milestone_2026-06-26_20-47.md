# Milestone review — milestone lane

- **When:** 2026-06-26T20:47:42
- **Provider:** DeepSeek (`deepseek-chat`)
- **Elapsed:** 44.0s
- **Attached files (8):**
  - `CLAUDE.md` (7,805 chars)
  - `SPEC.md` (48,443 chars)
  - `BACKLOG.md` (40,243 chars)
  - `ENGINEERING.md` (17,550 chars)
  - `DESIGN.md` (22,619 chars)
  - `dashboard/index.html` (14,636 chars)
  - `dashboard/app.js` (117,530 chars)
  - `dashboard/styles.css` (30,307 chars)

---

## Response

### Concerns

1. **HIGH: `dashboard/app.js` ~2458 lines near line 1 — the interactive logic (desk batch fan-out, focus-trap, absolute-snooze, love-note fetch) has NO test harness.** The V3.8 pure-function tests cover `parseDate`/`fmtISO`/`flagFor`/`bumpDate` only. The batch write path (`handleBatchDone`, `handleBatchSnooze`, `handleBatchNote`), the focus-trap (`onSheetKeydown`), the sheet open/close (`openSheet`/`closeSheet`), and the love-note fetch (`loadLoveNote`) are covered only by `node --check` + manual DESIGN §9 smoke. A single refactor could silently break the tombstone stamp or the focus-return. Deferring the jsdom harness to a separate lane means shipping the milestone with untested interactive code that touches the live Sheet. The explicit rationale — "build-step decision vs no-build-step principle" — is a legitimate tradeoff, but the risk is that a post-milestone fix to `app.js` will be made without the harness, and the fix will introduce its own bugs. **File:** `dashboard/app.js` (entirety, but specifically functions `handleBatchDone` line ~1550, `handleBatchSnooze` line ~1620, `handleBatchNote` line ~1660, `onSheetKeydown` line ~1320, `loadLoveNote` line ~820). **Suggestion:** Write a minimal jsdom-based test for `applyWrites`, `enqueueWrites`, and `flushQueue` — these are the highest-risk functions because a bug there corrupts the Sheet. The harness doesn't need to boot the whole app; it can import the relevant functions as ES module stanzas or as a test helper file. Defer the full interactive harness to the separate lane, but don't ship the core write path untested.

2. **HIGH: `automation/love_note_server.py` — the Cloudflare Tunnel is the box's first inbound listener (SPEC §7.7, ENGINEERING §5).** The threat model is described as "auth-gated + CORS-locked + body-capped", but three classes are not addressed:
   - **DoS of the love-note endpoint:** The server runs a `ThreadingHTTPServer` on localhost, but the tunnel can accept many connections. A flood of `PUT`/`DELETE` requests (even authenticated — the token cache would hit Google tokeninfo for each new token) could saturate the box. No rate-limiting, no connection-per-IP throttling, no `--max-connections` is documented. 
   - **Token replay:** `access_token→Google-tokeninfo verify` is correct, but an attacker who steals the access_token (e.g., via XSS in the dashboard, which is a static PWA so XSS is low-risk) can send arbitrary notes until the token expires. The token is "never persisted" but it's cached in memory keyed by SHA-256 — an attacker who can read the server's memory can extract the cache, though this is low.
   - **Tunnel as a pivot:** The tunnel's ingress rules are set in the Cloudflare dashboard, not in the repo. If the tunnel is misconfigured to allow paths other than `/lovenote`, the attacker reaches the localhost server and could probe for other services on the same machine (e.g., the Baileys bridge, which has no auth). **Recommendation:** Add a `--allowed-paths` flag to the love-note server or fail-CLOSED on any path that isn't `/lovenote`. Also, document the tunnel's ingress rules in `deploy/FINANCE.md` or `ENGINEERING.md` §5.

3. **MEDIUM: `SPEC.md` §7.7 — "no `seen` signal" is explicit, but the love-note implementation (`dashboard/app.js` line ~1180) renders the inbound note on the recipient's "next open."** This is correct per the spec, but there is no mention of what happens if the recipient opens the dashboard while the sender is still composing. The `GET /lovenote` call returns `{inbound, outbound}` — the outbound note is yours, which you see in the composer. If you open the dashboard while your partner is typing a note but hasn't sent it yet, the `GET` returns an empty `inbound` (since the note hasn't been `PUT`). That's fine. But if you open the dashboard after your partner has sent a note, you see it. If you then close the dashboard and your partner replaces the note, the next `GET` returns the new note. The 24h expiry is lazy on read — so a note that was sent 23h ago and then replaced is gone. This is consistent. The risk is a subtle expectation mismatch: a parent who saw a note at 9am and re-opens at 2pm expects to see the same note, but if the sender replaced it at 1pm, the original note is gone forever. The spec says "one note per direction, replacement replaces" — this is correct, but it should be documented in the UI copy or the love-note heading (e.g., "Partner's note (updated)" to signal that the note can change). **File:** `SPEC.md` §7.7 line ~400. **Suggestion:** Add a note to §7.7: "The recipient sees the note at read time; the note may be replaced by the sender before the recipient opens the dashboard. The recipient is not notified of a replacement — the inbound card shows the current note without historical versioning."

4. **MEDIUM: `dashboard/app.js` ~line 1670 — `handleBatchNote` appends to `Notes` with a stamp `[YYYY-MM-DD Name]`.** This is fine. But the sheet append is `r.notes + stamp + text`. If the notes cell is >120 chars, the engine's §7.1 says "appended to a message if ≤120 chars" — the engine filters on send, not on write. The dashboard writes arbitrary-length notes. The engine then decides whether to include the note in the digest. This is not a bug, but it means a very long note could be silently dropped from the digest (the engine checks ≤120). The user has no feedback that the note was too long. **Suggestion:** Either: (a) add a character counter to the note textarea that warns at 120 chars (matching the engine's threshold), or (b) relax the engine's 120-char limit for multi-line notes (since the user wrote it on purpose). The current state is acceptable but undocumented.

5. **LOW: `ENGINEERING.md` §5 — "the love-note endpoint is the box's FIRST inbound HTTP listener."** The Cloudflare Tunnel is described as a "token-managed connector" with "ingress set in the Cloudflare dashboard." This means the tunnel's configuration is NOT in the repo and can diverge from the code. If the PO sets up the tunnel incorrectly (e.g., allowing `/` instead of `/lovenote`), the box could be exposed. **Suggestion:** Add a startup self-check in `love_note_server.py` that verifies the `Host` header matches the expected tunnel origin (the `CLOUDFLARED_TUNNEL_TOKEN` is a Cloudflare token, not a host check). Alternatively, add a `--origin` flag that the server uses to validate `Origin` headers (CORS already does this, but only for browser requests — a non-browser attacker could send a direct request with no `Origin` header, which CORS doesn't block). The current CORS check is for browser-origin, not for tunnel-origin.

### Missed alternatives

1. **Serve love-notes entirely from the Sheet** (a hidden `LoveNotes` tab with one row per direction, same 24h expiry via a nightly cleanup timer) — this would have avoided the inbound listener entirely and kept the Sheet as the true "one source of truth."

2. **Self-disable the love-note feature at build time** if the tunnel secret is absent (remove the love-note slot from the dashboard HTML) — instead of leaving an inert slot that could be accidentally shown if a future code change misses the hidden check.

3. **Use a shared memory cache (memcached/redis) for the love-note token verify cache** instead of the SHA-256 in-memory cache — the in-memory cache is lost on server restart, which is fine, but a leak of the cache is a token-identity leak.

4. **Make the love-note endpoint a **separate subdomain** (e.g., `lovenote.familyapp.com`) instead of a Cloudflare Tunnel to localhost** — this would isolate the attack surface from the rest of the appliance (though it adds DNS complexity).

5. **Require the love-note `PUT` body to include an idempotency key** — the current implementation is not idempotent: if you `PUT` the same note twice (e.g., a network retry), the second `PUT` overwrites the first (same direction, so it's still one note). This is acceptable but undocumented.

### Affirmations

1. **Love-note as a §3.1 exception is correctly bounded.** It's one ephemeral datum per direction, 24h expiry, no push, no 'seen' signal, appliance-local storage with mode 700. The precedent is narrow enough that it doesn't erode the "one source of truth" principle for structural data (budget, reminders, etc.).

2. **The no-revoke switch-account decision is correct.** Revoking the OAuth grant on account switch would force the other parent to re-consent, and re-picking the same account would result in a lost session. Dropping the superseded token is the right tradeoff.

3. **The col-D ISO `YYYY-MM-DD` write + `parseDate` read resolution is well-engineered.** Handling ISO first, then the he-IL DD/MM/DD.MM render, plus rejecting impossible dates (31/02), means the snooze/recurrence round-trip is robust.

4. **The batch desk fan-out to a single `applyWrites` call is architecturally sound.** It prevents the old per-row fan-out that could lead to partial completes on a network failure mid-batch.

### Concrete suggestions

1. **Replace the deferred jsdom harness decision with a minimal write-path test.** In `tests/test_dashboard_write_path.py`, write pure-function tests for `applyWrites`, `enqueueWrites`, and `flushQueue` by extracting those functions into a stubbable module (`dashboard/lib/write.js`) that doesn't depend on the DOM. The module only needs `gapi`, `localStorage`, and `state`. This gives you regression coverage for the core write logic without a jsdom harness. Defer the full interactive harness to the separate lane.

2. **In `automation/love_note_server.py`, add a startup self-check that the `Origin` header matches the configured `LOVENOTE_ORIGIN` and that the path is exactly `/lovenote`.** Fail closed on any other path. Add `--max-body-size-bytes` and `--max-requests-per-minute` config knobs (simple integer in `/etc/family-inc/env`, default 100 bytes and 60 req/min). This addresses the DoS and pivot concerns.

3. **In `SPEC.md` §7.7, add an explicit note about replacement semantics:** "A note is replaced atomically on `PUT`. The recipient may never see a note if it is replaced before their next dashboard open. There is no version history — the appliance holds only the current note for each direction."

4. **In `dashboard/app.js` (the love-note section), add a character counter to the note textarea that warns at 120 characters** (matching the engine's digest-inclusion threshold). Use the existing `data-i18n` pattern for the warning text. This prevents silent drops.

### One question for the team

**Is the Cloudflare Tunnel the right long-term placement for the love-note endpoint, or should the endpoint be served through the existing GitHub Pages static site by making it a Cloudflare Worker (avoiding the inbound listener entirely)?** The Worker would use the same OAuth token verification, but would not create a persistent TCP connection to the appliance, reducing attack surface. If the Worker is not feasible, what is the cost ceiling the team is willing to accept for the tunnel (e.g., $0-5/month on Cloudflare Zero Trust free plan)?

---

<details>
<summary>Full prompt sent (click to expand)</summary>

```
You are reviewing engineering decisions made in a working session on the "Family Inc"
household-automation project. You are the explicit adversarial-but-fair reviewer. The
team owners (Adar = CTO, Shanee = Chief Design + PO) value pushback over agreement.

## Project one-paragraph context
A household operating system for a two-adult, two-young-kid family in Israel
(ILS, Hebrew/RTL, Maccabi healthcare). Master DB = one Google Sheet. PWA dashboard
pinned to both iPhones, write-back to the Sheet. Messages via WhatsApp (self-hosted
Baileys bridge) through a single budgeted outbox. Operating principles (SPEC.md §3):
briefings > notifications, alert budget 2/day, no kid-facing UI, boring tech,
one source of truth per domain, fail loud / degrade quiet.

## What this session changed
# Session changes — v3 Today redesign (milestone close, 2026-06-26)

**Milestone:** the dashboard *Today* surface, fully redesigned across 8 build
slices (V3.1→V3.8). This is the milestone-close review before flipping the lane
✅ and folding the contracts into canon. The lane was decided 2026-06-25 (8
design calls co-signed by Adar + Shanee after an 8-dimension adversarial review;
decision record in `V3_RECONCILE.md`, lane contract in `ROADMAP.md` §3.8).

Each slice already passed its own per-slice adversarial review (7-lens for the
UI slices, 3-lens for the security-bearing love-note endpoint) — those findings
are landed. **This review is the holistic pass:** does the whole redesign hang
together, are the new *contracts* sound, did we accumulate cross-slice drift?

## What the redesign is

The Today surface went from 6 domain accordions + a green "all-clear" banner to:
a **3-tier status pill** (red/amber/sage, never color-only, `role=status`), a
**select-to-act desk** (batch-action reminder rows), a **3-day scroll-snap
calendar strip**, a **±30-day coming-up band**, a **portfolio grid** (5 tiles)
opening **one** data-driven bottom-sheet, a **cross-domain timeline**, and a
net-new **parent-to-parent love-note**. Cool retone throughout; full i18n/RTL +
WCAG-AA a11y pass.

## The slices (and the contract each introduced)

- **V3.1 — token retone.** Cool palette + IBM Plex Mono all-numerals + AA-cleared
  amber/muted; rename-with-aliases so no selector broke. (DESIGN §2 graduated.)
- **V3.2 — scaffold + 3-tier status pill.** `#view-today` rebuilt into named
  slots; the single pill (red/amber/sage + a neutral `loading` tier) replaces the
  old pill **and** banner — closing the premature "all clear" that showed before
  data loaded. (DESIGN §2/§3/§4/§9.)
- **V3.3 — select-to-act desk + ±30d coming-up + absolute snooze.** Reminder rows
  became `role=checkbox` selection rows fanning `state.deskSelection` out to **one**
  `applyWrites` per action (the relative-snooze `+Nd` pills retired for an absolute
  ISO `Due = <date>` so an overdue row snoozed forward clears OVERDUE). Gated on
  Lane C's col-D write contract (now ISO `YYYY-MM-DD`; SPEC §6.1/§7.6/§8.5).
- **V3.4 — 3-day scroll-snap calendar strip.** Read-only today/+1/+2; `renderNext7`
  narrowed to 3–7d so the strip and the list can't double-render.
- **V3.5 — portfolio grid + one data-driven bottom-sheet.** 6 accordions → 5
  `<button>` tiles → **one** shared `role=dialog`/`aria-modal` sheet (focus-trap +
  scroll-lock + `#app` `inert` + focus-return). Education dropped from Today (data
  retained → the timeline).
- **V3.6 — cross-domain timeline.** A 6th tile opens the shared sheet onto a
  read-only chronology of *every dated row across all domains* on one axis
  (1wk→5yr zoom + category-chip filter). The everything-dated inclusion rule + the
  full Domain→category map graduated to **SPEC §7.6**; Education's only Today home
  is this timeline.
- **V3.7 — love-notes (text phase).** The first dashboard datum that is **neither
  the Sheet nor the outbox** — a sanctioned **SPEC §3.1 exception**. A net-new
  appliance endpoint (`automation/love_note_server.py`, stdlib HTTP on localhost):
  one ephemeral note per direction, 24h-or-on-replacement expiry, flat-JSON-per-
  direction storage, `access_token`→Google-tokeninfo verify (opt-in audience check
  vs the dashboard OAuth client) → `Settings.UserMap`→parent (unknown→403), token
  never persisted/logged, tight CORS to the Pages origin (blank origin → self-
  disable fail-safe), body cap + chunked-reject pre-auth. 3 systemd units + a
  **Cloudflare Tunnel** connector (the box's first inbound listener). SPEC §7.7 +
  §3.1 exception + §8.6 privacy bullet; ENGINEERING §5/§6. Voice is a frozen
  phase-2 (SPEC §4/§7.7 stored-media carve-out, not built).
- **V3.8 — i18n + a11y + Settings (the closer).** A declarative `data-i18n-aria`
  walker (retires hand-rolled boot aria-labels); a global `:focus-visible` + one
  consolidated `prefers-reduced-motion` block; a hermetic **WCAG-AA contrast
  assertion** test; a **real switch-account** Google re-auth (`prompt:
  'select_account'`) that **does not revoke** the prior token; the **token-alias
  endgame** (the 6 V3.1 back-compat aliases migrated + deleted; `--blue` kept as a
  theme-paired info token + given its dark value); cheap **pure-function JS tests**
  (no build step). SPEC §7.6 + DESIGN §2/§3/§8/§9.

## Cross-cutting decisions worth a second look

- **`app.js` is now ~2458 lines** — past ENGINEERING §7's ~2000-line JS-harness
  trigger. We shipped pure-function node tests (`parseDate`/`fmtISO`/`flagFor`/
  `bumpDate`) but the **interactive** logic (desk batch fan-out, sheet focus-trap,
  absolute-snooze, love-note fetch) is covered only by `node --check` + STRINGS
  he↔en parity + the manual DESIGN §9 smoke. A real jsdom harness is a **build-step
  decision vs the no-build-step principle** — deliberately deferred as its own lane.
- **No-revoke switch-account.** Revoking on account-switch drops the *shared* OAuth
  grant — it would sign you out on a same-account re-pick and force the other parent
  to re-consent. So we drop the revoke entirely; `LastDoneBy` stays truthful
  (identity = the live OAuth session, never a label flip).
- **`--blue` kept** as a theme-paired info token rather than folded into an existing
  token, given its missing dark value was the dark calendar-time bug; Shanee's
  "keep a distinct info blue" call.
- **Total test count 423 → 468 green** across the lane.

## For the reviewer — focus

1. **The SPEC §3.1 exception (love-notes).** Is carving out "one ephemeral, non-
   persisted, parent-to-parent datum" from the "one source of truth per domain"
   principle sound, or does the precedent erode the principle? Is the contract
   (no Sheet, no outbox, 24h expiry, no 'seen' signal) drawn tightly enough?
2. **The Cloudflare Tunnel as the appliance's first inbound listener.** New attack
   surface on a box whose whole security posture was "no inbound, read-only egress."
   The endpoint is auth-gated + CORS-locked + body-capped — is that the right
   threat model, or did we miss a class (DoS the box, token replay, tunnel as a
   pivot)?
3. **Shipping a 2458-line `app.js` at milestone close with no interactive-logic
   harness.** Is deferring the jsdom harness the right risk call, or should the
   milestone not close until the batch-write fan-out + focus-trap have real tests?
4. **The no-revoke switch-account.** Truthful `LastDoneBy` + shared-grant
   preservation vs. the inability to actually revoke a device's access from the UI.
   Sound, or a missing affordance we're papering over?
5. **Cross-slice consistency.** 8 slices touched the same `#view-today` and the same
   token set incrementally. Any contract we graduated in an early slice that a later
   slice silently contradicted?

## What I want you to review
1. Architectural soundness of the changes above.
2. Missed alternatives or simpler paths we didn't consider.
3. Tradeoffs we made implicitly without writing them down.
4. Risks / failure modes not covered.
5. Internal consistency across the changed files.

## What I do NOT want you to review
- Style, tone, formatting, copyediting.
- Adherence to design "best practices" in the abstract — only call those out if
  ignoring them creates a concrete risk for THIS project.
- The roles or session ritual itself (out of scope; that's our process).
- Files I did not list in "What this session changed" — assume those are settled.

## Required output (use these headings, in this order)
### Concerns
Things that should change. Be specific (file + section). Rank by severity.

### Missed alternatives
Paths we likely didn't explore. One-sentence each. Don't develop them — just name them.

### Affirmations
Decisions you think are correct, especially non-obvious ones. Brief.

### Concrete suggestions
Edits we could make right now. Phrase as "replace X with Y because Z."

### One question for the team
The single most useful question you'd ask Adar+Shanee+Claude if you had one.

Be terse. We're going to act on this directly.

---

## Attached context files

The following files are attached for you to read. Each is delimited by a header line.
Reference them by relative path in your review.

=== File: CLAUDE.md ===
# Family Inc. — Session Context

*Auto-loaded at the top of every session opened in this folder. Consolidated 2026-06-17 (the SPEC bump: canon rewritten clean, the D-NN decision log retired to `Archive/`). 2026-06-20: spec-ahead pass — `ROADMAP.md` added as the 5th canon doc; canon reconciled to code. Keep under 100 lines.*

## What this is

A household operating system for Adar + Shanee (+ 2 young kids, adult-mediated). Master DB = the `Family_OS` Google Sheet. Two product surfaces: WhatsApp messages (self-hosted Baileys bridge) and a PWA dashboard pinned to both iPhones. All automation runs on **one VPS** ("the appliance"). Israeli context throughout: Hebrew/RTL, ILS, Asia/Jerusalem, Maccabi, Hebcal.

## Canon — five documents, one job each

| Doc | Owns | Open it for |
|---|---|---|
| `SPEC.md` | what the system is: scope, architecture, data model, contracts, policies | any contract or "how should X behave" |
| `ENGINEERING.md` | how it's built/run: repo layout, toolchain, VPS, deploy, tests, ops | any "how do we do X" |
| `DESIGN.md` | both surfaces: dashboard UI + WhatsApp message design, i18n, states | any pixel or copy question |
| `BACKLOG.md` | current status: shipped, in-progress, gated, frozen lanes | where we are / what's frozen |
| `ROADMAP.md` | the forward plan: the ranked v1.1 sequence + per-lane forward contracts (spec **ahead** of build) | what to build next / a future lane's contract |

The first four are **present-tense snapshots** of the current state; `ROADMAP.md` is the **near-future** plan (a lane's contract graduates into `SPEC.md` when it ships). `Archive/` holds superseded docs and the full dated decision history (the old `DECISIONS.md` D-001…D-052 log) — read-only, for "didn't we decide…". Status lives **only** in `BACKLOG.md`; the forward sequence lives **only** in `ROADMAP.md`.

## Roles & authority

| Role | Person |
|---|---|
| CTO + co-PO | **Adar** — engineering direction, ships code |
| Chief Design + co-PO | **Shanee** — product direction, UX feel |
| Lead Architect | **Claude** — design, code, tradeoffs; defers to POs on product, to Adar on engineering detail |
| Reviewer | external model via `automation/review.py` (DeepSeek default) — milestone reviews only |

Either PO can lead a session and take routine calls solo; major directional calls (new feature, principle change, removing shipped behavior) are joint. Session leader = whoever opened the session; Claude treats them as "the PO" unless they defer.

## Non-negotiable principles (full versions: SPEC §3)

One source of truth per domain · boring tech · alert budget 2/day enforced at the outbox (criticals bypass, briefings exempt) · briefings > notifications · partner-symmetric, no scoring · fail loud, degrade quiet · never promise an affordance that doesn't exist · no money movement, no credential storage (except appliance-local read-only finance logins + the device-trust browser profiles they authorize), no messages beyond the two adults, no kid-facing UI.

## Current state (live)

**v1 live & accepted since 2026-06-13 (`v1-live`).** Running on the appliance: the keystone loop (reminders → WhatsApp digest + dashboard write-back), the weekly briefing (deterministic template), the group summarizer (on **DeepSeek**, keyword fallback keyless), and the **property tracker** (Yad2 on-box + Madlan via Apify, silent listings in the morning digest). Delivery has an email fallback; the outbox enforces the budget.

**M6 finance ingestion — live on Mizrahi (debit) since 2026-06-19:** daily read-only scrape → categorized, idempotent Sheet write (verified 98/98, dedup on a natural-key Txn-ID). **Cal (Visa) hooked up 2026-06-23** — the household is **not** debit-only: Cal is an *immediate-debit* card whose spend hits the Mizrahi statement merchant-less, so its own scrape brings the categorizable per-merchant detail (live **headless** via a one-time `--auth` device-trust login; first import 103 txns, **~90% categorized**). The Mizrahi-side Cal settlement lines map to an excluded **`Card Settlement`** bucket (not a budget row) so each purchase counts **once**, via the Cal side. **Shanee's debit card** turns out to be a Cal-cleared immediate-debit card on the **already-connected Cal login** — so it needs **no new `--auth`**; its repo change is just the `רכישה בכרטיס דביט` `Card Settlement` mirror token (landed 2026-06-23, pending a box-verify that her per-merchant rows ride the existing Cal scrape). Other statement cards remain (cards lane **un-deferred**, `BACKLOG.md`). M6.3 (briefing/dashboard consumers) + M6.4 (analysis layer) remain. **Gated to ~2026-06-26** (needs ≥1 week of live finance data): the first real classifier-accuracy run + the external milestone review. Full status: `BACKLOG.md`; the forward plan + lane contracts: `ROADMAP.md`.

**2026-06-23 (second VPS hour):** box-side verification (ROADMAP lane 7) confirmed the asserted-live claims; the CI gate (lane 1) merged to `main` (first run red on `setup-uv@v8` → pinned `@v7`); the Mizrahi scraper lib was bumped 6.7.3→6.7.8 after a 06-22 login-flow failure; and a **~77%-blank live-categorization gap** was surfaced.

**2026-06-23 (third VPS hour — Cal hookup):** the "77% blank" turned out **mostly structural, not an engine failure** — the blanks are merchant-less wrappers (Cal settlements, ATM, cheque, other cards), correctly UNKNOWN. Cal's own scrape categorizes its rows at ~90%, so the fix is *more sources*, not a better classifier. The `Card Settlement` exclusion (rules + test seam, 422 green) prevents the immediate-debit double-count. **Shanee's debit card** is the first "remaining card" worked (2026-06-23): it rides the connected Cal login (no new `--auth`), so the change is just its `רכישה בכרטיס דביט` mirror token (landed; box-verify pending). Still gated to 06-26 (Shanee's vocab migration + a re-categorize backfill of historical blanks + the remaining statement cards).

## Session protocol

0. `git pull --ff-only` before touching anything — other agents push to origin; the local folder is not assumed current.
1. Read `BACKLOG.md` first — it says where we are.
2. Work the current item; don't open new lanes without a PO call.
3. Constants go in config, utilities in `automation/lib/`, message copy in templates (reviewable against `DESIGN.md` §6).
4. **Decisions fold into the canon, not a log.** A directional call = edit the relevant doc to the new present-tense state, add a short inline *why* if it's non-obvious, and carry the dated rationale in the commit message. Major/joint calls land the same way. (The separate D-NN log is retired; git history is the dated record.)
5. Session end: tests green if code moved, `BACKLOG.md` statuses flipped, `python3 automation/session_kickoff.py` regenerated `NEXT_SESSION_PROMPT.md`, and the PO gets ONE terminal block (stage → review gate if milestone-closing → commit → push) to run on their machine.
6. **Milestone reviews only** (new spec / architecture shift / budget-privacy-delivery change / each milestone close): run `automation/review.py`, resolve as Apply / Defend / Open. Tiny edits never trigger a review.

## Guardrails for Claude in this repo

- Never put names, phone numbers, JIDs, or real finance values in committed files — they belong in the Sheet, `/etc/family-inc/`, or gitignored seeds (the repo is public-portfolio-safe by construction).
- Never add an alert path that bypasses the outbox chokepoint (`automation/lib/outbox.py`).
- Schema changes are additive-only on the Sheet (old rows must keep parsing).
- Committed ≠ deployed: a feature or placed secret is inert until `deploy.sh` pulls it; confirm the box is at origin HEAD before declaring anything live.
- Git operations run on the PO's machine, never in a sandbox.
- If SPEC and code disagree, say so before "fixing" either.

=== End: CLAUDE.md ===

=== File: SPEC.md ===
# Family Inc. — System Specification

*What the system is: scope, architecture, data model, contracts, policies. v3.1 · 2026-06-20.*
*This is a present-tense snapshot — it describes how the system behaves today, not how it got here. The dated history (every prior "we changed X to Y" rationale) lives in `Archive/`. Companions: `ENGINEERING.md` (how it's built and run) · `DESIGN.md` (how it looks and reads) · `BACKLOG.md` (current status) · `ROADMAP.md` (the forward v1.1 plan + lane contracts).*

---

## 1. Overview

Family Inc. is a household operating system for a two-adult, two-child family in Israel. It watches the family's obligations — appointments, renewals, deadlines, school/daycare chatter — and reflects them back through **two calm surfaces**: a small number of WhatsApp messages, and a PWA dashboard pinned to both adults' iPhones. The master database is a single Google Sheet. The automation runs unattended on one small VPS ("the appliance").

The core promise: **nothing important gets dropped, without anyone having to watch a screen.**

### What it is not

- Not a chore-gamification app. No streaks, no scores, no nagging.
- Not a kid-facing product. Children's data is structured but adult-mediated.
- Not a finance robot. It never moves money; the only financial credentials it holds are appliance-local, read-only portal logins (and the per-provider device-trust browser profiles they authorize) used to *read* balances and transactions.
- Not a chat bot. It speaks at scheduled moments, or for genuine urgency, within a hard budget.

## 2. Context

| | |
|---|---|
| Household | 2 adults (joint product owners) + 2 young children |
| Locale | Israel — Hebrew-first, RTL, ILS, Sunday-start week, Jewish-calendar aware (Shabbat, chagim) |
| Healthcare | Maccabi (no public API — any ingestion is mail/manual) |
| Devices | Two iPhones (PWA + WhatsApp), one VPS, no other infrastructure |
| Cost ceiling | ~₪120/mo all-in (VPS ~₪20 + LLM ~₪35 + margin). Anything above needs a PO call |

Roles and decision authority live in `CLAUDE.md`. Personal data — names, phone JIDs, health specifics, real budgets — lives only in the Sheet and in gitignored config/seed files, never in committed code or docs. The repo is public-portfolio-safe by construction.

## 3. Operating principles

Phrased so a reviewer can check compliance:

1. **One source of truth per domain.** Every datum has exactly one authoritative home (almost always a Sheet tab). Anything else holding it is a cache or a view, and is allowed to be lost.
2. **Boring tech.** Google Sheets over a database; vanilla JS over a framework; systemd timers over orchestration; JSONL files over message queues. A new dependency must remove a failure mode, not just add a capability we like.
3. **Alerts are a budget.** Hard cap of 2 unsolicited messages per recipient per day, enforced at one chokepoint (§7.5). Critical-safety messages bypass it with an audit trail. Scheduled briefings are exempt — they are appointments, not interruptions. *(Enforced in one place because two scripts that each kept their own 2/day counter could combine to 4+/day.)*
4. **Briefings > notifications.** The default unit of communication is a scheduled digest. A real-time message is the exception that must justify itself.
5. **Partner-symmetric.** Both adults see everything, can act on everything, and appear as equals. No leaderboards, no scoring.
6. **Fail loud, degrade quiet.** Infrastructure failures surface in the next briefing ("bridge silent 14h"), never as silence. Feature degradation (LLM down → deterministic fallback) must not page anyone. **Time-critical, user-facing data is the exception to "degrade quiet":** when a fetch fails for a time-sensitive line — e.g. Shabbat/chag candle-lighting times — surface an explicit "unavailable" line, never silence, because a missing safety line that's indistinguishable from "nothing today" is itself a silent failure (GAP-7, 2026-06-20).
7. **Never promise an affordance the system doesn't have.** No reply commands in messages until reply parsing ships; no buttons that don't write.

## 4. Scope

### Live today

| Capability | One-line contract |
|---|---|
| Reminders engine | Daily 07:25: read the Reminders tab, compute due / lead-time / overdue fires. |
| Daily digest | Daily 07:30: assemble engine fires + WhatsApp group digest + new-property listings + Hebcal line into **one** message per adult, and send. **Both adults every day** (§7.2). |
| Weekly briefing | Sat 21:00: whole-Sheet narrative rendered from a deterministic template. |
| Hebcal enrichment | Friday/holiday awareness lines in briefings (candle-lighting, chagim). |
| WhatsApp summarizer | Hourly: classify group messages ALERT / DIGEST / ROUTINE; alerts within budget; a digest section at 07:30. |
| Property tracker | New Yad2 / Madlan listings land silently in the Sheet + a digest section (§12.1). |
| Dashboard (PWA) | Today-first read view + write-back (done / snooze / note) with offline queue and a tombstone race guard. |
| Delivery | Self-hosted Baileys bridge: 1:1 messages to the two adults only, via a durable outbox. |

### Building now

**Finance ingestion (M6, §12.2).** Read-only scrape → categorized transactions + balances in the Sheet → silent surfacing in the briefing and dashboard. **Live on Mizrahi (debit) since 2026-06-19**; the consumer wiring (M6.3) and analysis layer (M6.4) are landing. **Cal (Visa) hooked up 2026-06-23** — an immediate-debit card whose spend also lands merchant-less on the Mizrahi statement, so the Mizrahi-side Cal lines map to an excluded `Card Settlement` bucket (counted once via the card); more cards remain (M6.5). See `BACKLOG.md`.

**Love-notes (V3.7, §7.7).** A parent-to-parent ephemeral note over a small authenticated dashboard→appliance endpoint — the one dashboard datum that is **neither the Sheet nor the outbox**. The **text** phase is code-complete, deploy-gated on standing up the Cloudflare Tunnel + its `DASHBOARD_LOVENOTE_URL` secret; **voice** is a frozen phase-2 (below). See `BACKLOG.md`.

### Non-goals (permanent)

Money movement · credential storage *(except appliance-local, read-only financial portal logins and the device-trust browser profiles they authorize)* · messaging anyone beyond the two adults · posting into any group · kid-facing surfaces · medical advice (scheduling only).

### Frozen (out of scope until a stated condition is met)

Pediatric milestones, goal coaching, PDF/OCR/voice capture, Gmail bill parsing, Maccabi forwarders, WhatsApp reply parsing. Each unfreeze condition is in `BACKLOG.md`; frozen code lives in `attic/`, unmaintained. *(Voice capture's first bounded unfreeze is the love-note **voice memo** (§7.7 phase-2): ≤24h, appliance-local, the single exception to "media is never stored" — it graduates only with its own §4/§7.7 carve-out, which has not landed; the love-note text phase stores no media.)* Anomaly/subscription detection is **killed** (not frozen) — the false-positive cost isn't worth it. A keyword categorizer, also once killed, returns in a bounded form only as the on-box finance rules engine (§12.2).

## 5. System architecture

```
                       ┌─────────────────────────────────────────────┐
                       │  GOOGLE (data plane)                        │
                       │  Family_OS Google Sheet  ←  master DB       │
                       │  Drive: /Briefings, /Documents              │
                       └────────▲───────────────────────▲────────────┘
                gspread (svc acct)│                      │ gapi (user OAuth)
                                  │                      │
┌─────────────────────────────────┴───────────┐   ┌──────┴───────────────────┐
│  THE APPLIANCE (one VPS, Asia/Jerusalem)    │   │  DASHBOARD (PWA)         │
│                                             │   │  GitHub Pages, vanilla   │
│  systemd timers:                            │   │  JS, pinned to 2 iPhones │
│   07:25 reminders engine (compute)          │   │  read: batchGet          │
│   07:30 daily digest (assemble + send)      │   │  write: batchUpdate +    │
│   hourly whatsapp summarizer                │   │   DoneAt / LastDoneBy /  │
│   ~06:00 finance scrape (M6: live)          │   │   WriteQueue_Tombstone   │
│   2×/day property scrape                    │   └──────────────────────────┘
│   Sat 21:00 weekly briefing                 │
│                                             │         ┌──────────────────┐
│  Baileys bridge (Node, systemd service):    │ WhatsApp│ Adar + Shanee    │
│   reads groups → inbox.jsonl                │────────▶│ (the only        │
│   polls outbox.jsonl → sends 1:1            │         │  recipients)     │
│   recipients.json = hard scope guard        │         └──────────────────┘
│                                             │
│  lib/outbox.py = THE chokepoint:            │
│   budget ledger, dedup, kinds, quiet hours  │
└─────────────────────────────────────────────┘
```

Key properties:

- **One write path to phones.** Every script that wants to reach a human appends to the outbox via `lib/outbox.py`. Budget, dedup, quiet hours, and scope live there once.
- **One data plane.** All Python uses gspread with a service account; the dashboard uses gapi with each adult's own OAuth. The local `Family_OS.xlsx` is a seed template only — nothing reads it at runtime. *(A split between openpyxl reads and a gapi dashboard would be two diverging sources of truth.)*
- **One machine.** Bridge and automation share the VPS. Its failure mode is total and therefore obvious (heartbeat goes stale → the next successful briefing says so; if >24h, the email fallback fires). *(The bridge needs to be always-on anyway, so a second runtime would only add a failure domain.)*
- **LLM calls are decoration, not structure.** Every LLM-dependent step has a deterministic fallback (templated briefing, keyword classification). The system delivers value with the API key revoked.

## 6. Data model — the `Family_OS` Google Sheet

Authoritative tab list. The three tabs with code contracts get column-level schemas below; the rest are human-edited and read loosely (missing columns tolerated, rows with unparseable dates surfaced as data-hygiene lines, never crashing a run). All schema changes are **additive-only** — old rows must keep parsing.

### 6.1 `Reminders` (keystone)

| Col | Field | Written by | Notes |
|---|---|---|---|
| A | Title | humans | used verbatim in messages |
| B | Domain | humans | Car / Health / Education / Finance / Contracts / Goals / Other |
| C | Owner | humans | Adar / Shanee / Both |
| D | Due Date | humans, engine + dashboard (recurrence bump / snooze) | a real Sheets **date** cell (he-IL renders it DD/MM); machine writes emit the **ISO `YYYY-MM-DD`** literal — Sheets parses ISO locale-unambiguously — and both surfaces **read** ISO *or* the DD/MM·DD.MM render (Lane C) |
| E | Lead Times | humans | CSV of day offsets, e.g. `60,30,7,1` |
| F | Recurrence | humans | One-off / Yearly / Monthly / Quarterly / Weekly / Custom |
| G | Status | engine, dashboard | Pending / Snoozed / Sent / Done / Skipped / Overdue |
| H | Last Sent | engine | ISO datetime of the last fire for this row |
| I | Channel | humans | WhatsApp / Email / None |
| J | Notes | humans, dashboard (append) | appended to a message if ≤120 chars |
| K | Days Until | sheet formula | `=D−TODAY()` |
| L | Auto-flag | sheet formula | OVERDUE / FIRE TODAY / WEEK OUT / MONTH OUT |
| M | LastDoneBy | dashboard | display name from `Settings.UserMap` |
| N | DoneAt | dashboard | ISO datetime; feeds the 7-day arc |
| O | WriteQueue_Tombstone | dashboard | ISO datetime stamped on **every** dashboard write; the engine skips rows tombstoned <6h (§8.3) |
| P | Guide URL | humans | optional how-to / Kol-Zchut link, appended to messages |

**Dashboard write contract:** every write-back is one `batchUpdate` touching its intent columns **plus M, N (when completing), and always O.** A dashboard that doesn't stamp O is non-conformant. **Snooze writes an *absolute* future Due date** (today + the chosen offset, or a picked date — never `Due += N`), so an already-overdue row snoozed forward clears OVERDUE cleanly. The Today **desk** is select-to-act (V3.3): a multi-row selection fans its done / snooze / note out to **one** `batchUpdate`, every row's columns resolved by header name (Lane C, §7.6).

### 6.2 `WhatsApp_Inbox` (hot, 30-day rolloff) + `WhatsApp_Archive` (text-only, forever)

`WhatsApp_Inbox` columns: msg_id, group_name, group_type, sender_name, sender_role, received_at, text, has_media, classification, one_liner, action_required, action_owner, critical, dispatched, dispatched_at, digested_at. After each successful append, rows older than 30 days roll off (the Archive never rolls). `WhatsApp_Archive` keeps msg_id / group / sender / received_at / text / one_liner only. **Media is never stored** — only the fact that it existed. The `critical` / `dispatched` fields are the outbox *outcome* record; budget enforcement itself lives only in the outbox ledger.

### 6.3 `WhatsApp_Group_Config`

group_name · group_type · importance_default (alert_eligible / digest_only / mute) · alert_recipients (both / adar / shanee / none) · close_contacts · alert_keywords (regex `;`-list) · critical_keywords (regex `;`-list, budget-bypassing).

### 6.4 Other tabs

`People`, `Calendars`, `Calendar-Events`, `Finance-Budget`, `Finance-Accounts`, `Finance-Transactions` (finance landing zone — schema in §12.2), `Goals`, `Health`, `Education`, `Car`, `Contracts`, `Contacts`, `Lists`, `Settings` (Key|Value rows — keys containing `@` are UserMap entries email→display-name; key `lang` is the chrome default), `Reminders-Archive` (one-offs roll here monthly), `Property-Listings` (scraper-written — schema in §12.1). `Calendars` and `Lists` are human-only (no code contract; read loosely, out of code scope). Money values are **ILS only**.

## 7. Component contracts

### 7.1 Reminders engine — daily 07:25 (computes, does not send)

```
validate the header row against the §6.1 column map; on mismatch: abort the run,
  log schema_drift, surface it in the next briefing. (Guards the dual write-path:
  dashboard and engine must agree on columns before anything fires; write-backs
  validate BEFORE the batch is issued, so a drifted sheet is never written by
  position.)
read Reminders where Status ∉ {Done, Skipped}.  (NOT "∈ {Pending, Snoozed,
  Overdue}": a 60,30,7,1 lead-time chain would die at its first Sent stamp.
  Same-day re-fires are blocked by the Last-Sent guard instead.)
  skip if WriteQueue_Tombstone is within 6h      → log skipped_due_to_tombstone + age
  fire if days_until < 0 AND last sent ≥3d ago   → OVERDUE
       or days_until ∈ Lead Times                → LEAD-TIME
       or days_until == 0                         → DUE TODAY
hand fires to the 07:30 daily digest (§7.2).
on CONFIRMED delivery (in the digest): Last Sent = now; Status = Sent | Overdue.
  (Confirmed = the bridge's whatsapp_sent.jsonl, reconciled at the next run; the
  §10.2 SMTP fallback confirms inline. NOT on queue — the bridge delivers
  asynchronously, so stamping a merely-queued digest let a bridge that dropped
  its session read "Sent" while the reminder never arrived, and the Last-Sent
  guard then silently suppressed the re-fire. Stamping on confirmation closes
  that silent-loss; an unconfirmed digest leaves its rows unstamped → they
  re-fire. See §7.5.)
recurrence on Done: bump Due Date by the period, Status → Pending, Last Sent
  cleared; Feb-29-class dates clamp to the last day of the target month + a
  review flag; Custom is flagged, never guessed.
heartbeat: append one line to logs/reminders_log.csv every run.
```

### 7.2 Daily digest (07:30) + weekly briefing (Sat 21:00)

**Daily digest:** one short message assembled from engine fires + the WhatsApp digest section + new-property listings + a Hebcal line (Fridays / erev chag), queued as `kind=briefing`. **One morning message, not several** — assembly happens before queuing. On **confirmed delivery** the digest stamps each fired row's Last Sent / Status per §7.1 (the bridge delivers asynchronously, so a digest queued one morning is stamped when the next run reconciles its confirmation; the SMTP fallback stamps inline).

**Both adults, every day.** The digest is assembled and queued for adar **and** shanee on every run. An adult with no fires of their own still gets the briefing — the quiet-day line plus the shared sections (WhatsApp groups, property). This keeps the surface partner-symmetric and means silence always signals a *broken* digest, never an empty day. Because it is `kind=briefing` it is budget-exempt, so briefing the empty-handed adult never spends an alert slot.

**Weekly briefing:** read all tabs → render the **deterministic-template** sections — week ahead · reminders firing this week · overdue · Money · Goals · data hygiene · system self-report · classifier accuracy → write to `Briefings/` and queue `kind=briefing`. The **Classifier accuracy** section carries the week's WhatsApp ALERT-tier counts, by-rule tally, and the <1/week false-positive target; the **self-report** line carries runs-green, messages classified, tombstone skips, and LLM spend. *(Deterministic by design — no LLM call. An LLM-written "five-scene narrative" (the week's spend · a kids' moment · next week's three things · a goal line · a contract heads-up) over whole-Sheet context is a deferred v1.1 lane — `ROADMAP.md` §ai-briefing — not a gap: it needs a whole-Sheet→provider privacy call and keeps this template as its proven fallback.)*

Both message kinds are budget-exempt and subject only to quiet hours.

### 7.3 WhatsApp summarizer — hourly

Reads new inbox lines → classifies: **hard rules first** — a critical/safety keyword is a budget-exempt ALERT that **pierces even a muted group**; below that tier a **muted group raises nothing** (mute is itself a hard rule); otherwise, for non-muted groups, alert-keyword / teacher-evening / vaad-utilities → ALERT and media-only → ROUTINE — then the LLM (the configured provider) for the rest with up to 3 messages of group context, then a deterministic keyword fallback when no key is present → writes Inbox + Archive rows → ALERT rows route per group config → `outbox(kind=alert)`, or `kind=critical` on a critical-keyword match. A digest-only group with a critical match raises a "⚠ NEEDS A LOOK" block at the top of the next digest. Family-group criticals do **not** override digest-only routing (critical_keywords already bypass per group). *(Mute is the one knob that silences ordinary alerts entirely; a true safety keyword is the deliberate exception — PO call 2026-06-18.)*

A weekly accuracy pass (`automation/accuracy_review.py`) re-reads the week's Inbox rows and re-derives each ALERT's triggering rule by reusing the live `hard_rule_alert` function — so the review can't drift from the classifier, and needs no schema change. It surfaces ALERT-tier false positives against the **<1/week** bar, folds a compact pulse into the weekly briefing, and writes a full operator report to `Briefings/`. The "fix" for a false positive is narrowing the offending keyword pattern.

### 7.4 Bridge — Baileys, Node, systemd service

Listens to **groups** → `inbox.jsonl`. Polls `outbox.jsonl` every 15s → sends **1:1 only** to JIDs present in `recipients.json` (machine-local, gitignored); any other target is refused and logged. Per-(id, target) dedup against a sent ledger. Heartbeat file on connect / message / 15-min idle. Never posts to groups. Inbound 1:1 chats from the two known senders (`recipients.json` JIDs) are **silently logged** to `replies.jsonl` as raw material for the v1.1 reply-parsing feature — the bridge does **not** act on them and **never acks** (no affordance it can't honor — §3.7); every other 1:1 sender is dropped. *(LID-addressed 1:1s fall through the known-sender guard and are dropped until v1.1. Self-hosted Baileys, not a paid API: ₪0 marginal, no business-API verification or template approval, free-form Hebrew. Pinned to Baileys 7.x on ESM — the pre-7 line broke companion self-sends after WhatsApp's LID identity migration.)*

### 7.5 Outbox (`lib/outbox.py`) — the chokepoint

```
queue(to: "adar"|"shanee"|"both", body, kind: "alert"|"critical"|"briefing", *, source, msg_id)
  briefing → exempt from budget; subject to quiet hours (22:00–07:00 → hold to 07:00)
  alert    → consult ledger[date][recipient]; if ≥2 → defer: append to tomorrow's
             digest, log alert_suppressed_by_budget; else send + increment
  critical → send immediately, any hour, log budget_bypassed_critical
  all      → idempotent by (id, target); ledger + queue are durable JSONL on disk
```

The ledger is shared across **all** senders — the engine and the summarizer can't each spend a separate 2/day. *(The daily digest is `kind=briefing`, not `alert`: as an alert it consumed a budget slot and, worse, an over-budget alert defers *into* the next digest — which is itself the message, a circular dependency.)*

**Delivery confirmation (cross-run reconcile).** The bridge delivers asynchronously and records each confirmed send to `whatsapp_sent.jsonl`. So queueing is **not** delivery: the daily digest does not stamp on queue — it writes a pending row per recipient to `digest_pending.jsonl`, and at the start of every `--send` run `reconcile_deliveries()` stamps Last Sent / Status (§7.1), clears the reported fail-flag lines, and consumes the budget-deferred alerts that digest carried — but only for the entries the bridge has since confirmed. An entry left unconfirmed past 48h is dropped and logged; its reminders stay unstamped and re-fire (fail loud, degrade quiet). The §10.2 SMTP fallback is itself the confirmation, so it stamps and consumes inline. Because the stamp now lands a run *after* the digest, reconcile re-reads the Sheet and honors the engine's own write guards: it never overwrites a row the user has since completed (Status Done/Skipped), rescheduled, or that recurrence bumped, defers a row with a §8.3 write in flight, and dates Last Sent to the digest's own send day. *(A bounded in-run wait was tried and rejected: it duplicates digests if bridge latency ever exceeds the window and couples the run to the bridge's async timing. Reconcile stamps whenever the bridge eventually confirms — next run or the one after.)*

### 7.6 Dashboard (PWA)

Read: `batchGet` over all bound ranges (UI contract in `DESIGN.md`). Write: per the §6.1 write contract — optimistic UI, an offline queue in `localStorage.pendingWrites[]` (cap 50), flushed on reconnect in tap order, failed flushes retried on the next online event. The write surface resolves its target columns by **header name** (not a hardcoded letter) and **pauses writes on header drift** — the JS mirror of the engine's §7.1 schema guard (Lane C), so a restructured Reminders tab can't be written by position. Identity: Google sign-in → `Settings.UserMap` → display name. **Switch-account** (D3) is a real OAuth re-auth — the Google account chooser (`prompt:'select_account'`), never a label flip — so `LastDoneBy` always reflects the parent actually signed in; cancelling the chooser is a no-op and the superseded token is simply dropped (never revoked — `revoke()` would drop the shared user+client grant). Settings carries **no** notification-toggle, bank-connect, or export controls (D7). Demo mode renders `mock_data.json` and never calls gapi.

**Cross-domain timeline (read-only derived view, V3.6).** The Today *Timeline* tile flattens every dated row already read above into one chronology, governed by two ratified rules. **Milestone-inclusion:** one timeline item per dated field — `Reminders.Due Date` (excluding the terminal Status values {Done, Skipped}), `Calendar-Events.Date`, `Goals.Target Date`, `Health.Next Due`, `Car`'s {Annual Test, Insurance Renewal, License Expiry}, `Education.Next Key Date`, `Contracts.Renewal Date` — kept only within the window `today − 14d … today + 5y`; undated and out-of-window rows are excluded. **Domain→category** (the filter set): each item carries exactly one of `finance · health · car · education · goals · contracts · calendar · other`; calendar and other are assigned by source, every other source maps to its own domain, and a reminder's free-text `Domain` (§6.1 col B) maps near-identity (lower-cased) with any unrecognised value falling to `other` — **never dropped**. The view is read-only (no write contract — items are edited at their source tab) and fully Sheet-derived (no new tab). This timeline is **Education's only Today home** (Education has no portfolio tile).

### 7.7 Love-note endpoint (V3.7)

The one dashboard datum that is **neither the Sheet nor the outbox** — the sanctioned exception to §3.1 (its authoritative home is an appliance file, not a Sheet tab). A parent-to-parent ephemeral note over a small authenticated dashboard→appliance HTTP endpoint (`automation/love_note_server.py`, bound to localhost; a Cloudflare Tunnel fronts it). **One note per direction** (Adar→Shanee, Shanee→Adar), stored as one flat JSON file per direction under the appliance state dir (`/var/lib/family-inc/lovenote`, mode 700), **expiring at 24h-or-on-replacement** — lazy on read **plus** an hourly sweep (`sweep_love_notes.py`). **No push:** a note appears on the recipient's **next dashboard open**, spends **no alert budget**, never rides `lib/outbox.py`, never writes the Sheet, and carries **no delivery/"seen" signal** back to the sender (§3.7) — `DELETE` clears only the author's own note. **Auth:** the PWA forwards its live Google access_token; the server verifies it once against Google's **tokeninfo** endpoint (which also exposes the token's audience — so when the dashboard's OAuth client id is configured [`FAMILY_INC_LOVENOTE_AUD`] the server rejects a token minted for any *other* app, closing the confused-deputy gap), maps the verified email to a parent via `Settings.UserMap` (unknown → 403), then **drops the token — never logged, never persisted** (a short in-memory cache keyed by the token's SHA-256, never the raw token, avoids re-hitting Google under a burst). **CORS** is allow-listed to the Pages origin only; a blank/unset origin denies every browser, so the feature **self-disables fail-safe** (never promise a dead affordance, §3.7). The listener also caps request bodies (413) and rejects unframed (chunked) bodies pre-auth. **Text only** — voice is a frozen phase-2 (§4).

## 8. Cross-cutting policies

### 8.1 Alert budget

2 unsolicited messages / recipient / day, enforced only in `lib/outbox.py`. When over budget, trim priority: OVERDUE and kids' Health always survive; **Goals are de-prioritised first** (`DROP_FIRST_DOMAINS` — sorted out ahead of WEEK/MONTH-OUT, since the weekly briefing already covers them; not a hard exclusion — a Goals fire still rides along when there is room under the per-digest cap), then WEEK/MONTH-OUT. If >10% of fires are suppressed over a rolling 14 days, the next weekly briefing says "budget is biting — raise the cap or tighten the rules?".

### 8.2 Quiet hours

22:00–07:00 Asia/Jerusalem. Alerts and briefings hold; criticals do not.

### 8.3 Offline write / engine race (tombstone)

The dashboard stamps `WriteQueue_Tombstone` (ISO-T datetime) on every write; queued offline writes re-stamp it **at flush time**, so the cell always carries the moment the write *landed* on the Sheet. The engine skips a row while `tombstone + 6h > now()` (one clock: the window starts at flush, not at the tap). *(Date-only tombstones had silently disabled this guard — the hour resolution is load-bearing.)* Residual accepted race: a phone that flushes a queued tap inside the same minute the engine reads → at most one duplicate alert; the flush itself is idempotent. Every skip is logged with the tombstone age, and the weekly briefing reports "N tombstone skips · max age seen" — widen the window from data, not anecdote. **Background-timer races (accepted):** the Sheet-writing timers are deliberately staggered — finance 06:00, reminders 07:25, digest 07:30, property on its own slot — so they don't run concurrently, and each writes a disjoint tab/column set (finance → `Finance-*`; engine + digest → `Reminders`; property → `Property-Listings`); `gspread` batch updates are atomic per call. v1 attempts no cross-timer transaction: the residual is a run that overran into the next timer's window, at most a stale read that self-heals next run.

### 8.4 Idempotency & dedup

Outbox messages carry stable ids: summarizer `wa-{msg_id}`, briefings `brief-{type}-{date}` — the daily digest queues once per recipient as `brief-daily-{date}`; **individual reminders carry no outbox id** (the engine computes, the digest delivers). The bridge dedups per (id, target). Engine re-runs on the same day are no-ops (the Last-Sent guard). The digest's confirmed-delivery stamp (§7.5) keys its pending rows on the same `brief-{type}-{date}` id and drops a settled row once stamped, so reconcile is idempotent — a re-run never double-stamps or re-consumes a deferred alert.

### 8.5 Time & locale

All schedules in Asia/Jerusalem (DST-correct via system TZ, never UTC offsets). Dates are **displayed** DD/MM/YYYY; week starts Sunday; money `Intl.NumberFormat('he-IL', ILS)` / `₪{n:,}` in Python. The one **stored** date both surfaces write, `Reminders.Due Date` (§6.1 col D), is a real Sheets date — machine writes emit the **ISO** literal (locale-safe) and the reads accept ISO or the he-IL DD/MM·DD.MM render (Lane C), so it round-trips regardless of the Sheet's locale. Chrome strings are Hebrew-default with an English fallback; data values stay Hebrew always. Machine-written datetime stamps (Last Sent, DoneAt, WriteQueue_Tombstone) are ISO-8601 `T`-form **text** on both surfaces — the `T` stops Sheets from coercing them into locale date cells, so they round-trip byte-exact and keep the hour resolution the 6h tombstone window needs.

### 8.6 Privacy & security

- WhatsApp plaintext exists in places we don't fully control — Meta's servers (inherent) and the configured LLM provider — plus the VPS we do. Exactly **one** LLM provider is configured at a time (DeepSeek by default — §8.7), and **every provider is treated identically**: the privacy guarantee is not *which* vendor may see the text but *how little it ever sees* — LLM classification sends one message + up to 3 context messages, never whole threads or cross-group context, whichever provider is active. Switching providers is an operator key-swap, not a policy change. *(DeepSeek is the default on cost; it routes group plaintext through PRC-jurisdiction infra — a deliberate privacy-vs-jurisdiction call by the POs, accepted because volume is negligible, every path has a keyless fallback, and the operator may swap providers at will.)*
- **Finance categorization:** the configured LLM provider may assign a category to the **rules-miss remainder only** — a transaction's **description + amount**, never account numbers, balances, credentials, identifiers, or the whole ledger. The on-box rules engine tags first, so most transactions never leave the box.
- **Love-notes (§7.7):** the appliance holds one ephemeral text note per direction (`/var/lib/family-inc/lovenote`, mode 700, never in the repo/backups); the caller's Google OAuth access_token is verified once against Google and then **dropped — never logged or persisted**, and CORS is allow-listed to the Pages origin. No voice/media is stored (text only) until the §4 carve-out.
- Secrets — `recipients.json`, the service-account JSON, `FAMILY_INC_DEEPSEEK_API_KEY`, `FAMILY_INC_APIFY_TOKEN` (property secondary source), `bank_creds.json` (read-only finance logins), SMTP password — live in `/etc/family-inc/`, mode 600, never in the repo. The **device-trust browser profiles** (Max/Cal only; `/var/lib/family-inc/finance/profiles/<provider>`, mode 700) are appliance-local bearer state — not in `/etc`, never in the repo or backups.
- Phone numbers / JIDs appear nowhere except `recipients.json` on the VPS.
- The service account has access to exactly one spreadsheet, nothing else in Drive.
- Known accepted risk: Baileys is an unofficial client — some account-ban risk, elevated on datacenter IPs. Mitigations: household volume (≤10 msg/day), a person-to-person pattern, a dedicated paired session. Fallback chain in §10.

### 8.7 LLM usage

One wrapper (`lib/llm.py`); model ids in config, not at call sites; per-call cost logged to `logs/llm_costs.csv`. The active provider is chosen by **key presence**: `FAMILY_INC_DEEPSEEK_API_KEY` → DeepSeek (`deepseek-chat`, via its OpenAI-compatible endpoint over stdlib urllib — no SDK); else `ANTHROPIC_API_KEY` → a Haiku-class provider, **treated identically** (the minimal-payload rule in §8.6 is provider-independent); else the deterministic fallback (keyword classification, template briefing). Classification requests strict JSON mode and tolerates trailing prose in the reply. The weekly briefing makes no LLM call. The weekly self-report line (ENGINEERING §8) carries the week's LLM spend; the first briefing of each month reports month-to-date.

## 9. Failure modes

| Failure | Detection | Behavior |
|---|---|---|
| VPS down | heartbeat stale (external check optional, v1.1) | total outage; on recovery the outbox flushes; missed runs reported in the next briefing |
| Bridge logged out / WA break | heartbeat stale >12h | digest prepends "⚠ BRIDGE SILENT Nh"; >24h → email-fallback digest to both adults |
| WhatsApp account banned | send failures + logout | switch to email digests same-day (one-line config); decide the §10 path |
| Sheet API 5xx / quota | gspread retries with backoff, then skips the run | "missed yesterday" line in the next successful run |
| LLM API down / keyless | exception → fallback path | templated briefing / keyword classification; logged, not alerted |
| Bad row data (unparseable date) | per-row try/except | row skipped + listed under "data hygiene" in the weekly briefing |
| Sheet header drift | engine header validation, every run | run aborts before firing anything; schema_drift logged + surfaced |
| Outbox/inbox JSONL torn line | reader skips the malformed tail | self-heals next poll (single-writer appends) |
| Clock skew / future tombstone | tombstone > now | treated as valid for the full window, anomaly logged |
| Both adults edit the same row | last-writer-wins | acceptable at household scale, by decision |

## 10. Fallback chain (delivery)

1. **Baileys bridge** (primary).
2. **Email digest** to both adults — automatic and mechanical: the daily-digest task checks the bridge heartbeat before queuing; if stale >24h it sends the identical rendered content via SMTP and notes "delivered by email — bridge down Nh". No watcher process; the sender itself degrades. Every send-run logs its transport to `logs/delivery_log.csv`; **email-fallback days are degraded, not green** — the weekly briefing surfaces them, so a dying bridge can't hide behind a working fallback.
3. **Twilio WhatsApp** — documented fallback, not in code. Adopt only if Baileys proves unworkable (recurring bans); accepts template-approval constraints.
4. **Inforu SMS** — deep fallback, Hebrew-capable, ILS billing; revisit only after 2+ failures above.

## 11. Acceptance (v1 — met)

v1 went live and was accepted on 2026-06-15 (tagged `v1-live`): the 07:30 WhatsApp digest reached both phones three consecutive days with no intervention; a reminder completed a full done→recurrence cycle; an alert-keyword group message reached the right recipients while a family-group meme reached no one; a critical keyword fired after the daily budget was spent; an offline dashboard write flushed on reconnect with the engine logging a tombstone skip and no duplicate; the weekly briefing arrived with its Hebcal and budget sections and the LLM-down fallback was verified; logs showed seven green days; monthly cost confirmed ≤ ₪120. New features inherit the same bar: live, observed green on the appliance, with a deterministic fallback proven.

## 12. Data ingestion lanes

Specs for ingestion lanes that are unfrozen. All ingestion obeys the same rules: one runtime (the VPS), `lib/sheet` is the only Sheet writer, no new path bypasses `lib/outbox.py`, secrets only in `/etc/family-inc/`.

### 12.1 Property listings — Yad2 / Madlan (live)

Active house search. New listings land silently and surface in the morning digest.

| Facet | Spec |
|---|---|
| **Source** | Saved-search result pages on Yad2 (primary) and Madlan. One or more saved-search URLs per portal in `/etc/family-inc/property_searches.json` (personal criteria, gitignored). No public API: the **primary** path scrapes; a permitted **secondary** source (Apify) backs it up when the scrape is blocked and fills missing fields. |
| **Mechanism** | Headless Chromium on the VPS (run headed under Xvfb with light stealth, because a plain headless browser from a datacenter IP is challenged). A scraper loads each saved-search URL, extracts listing cards (`listing_id`, price, rooms, size, location, url, posted-at), and diffs the `listing_id` set against `/var/lib/family-inc/property/seen.json`. New ids = new listings. |
| **Secondary source (Apify)** | `automation/lib/apify.py` is the only Apify client. It is consulted **per saved-search only** when the primary is blocked/empty (backup) or returned listings with missing fields (gap-fill), then merged with the **primary always winning** — Apify only adds missed listings and fills blanks, never overwrites. Actors: `amit123~yadscraper` (Yad2, ingests the saved-search URL) and `swerve~madlan-scraper` (Madlan, parametric — needs a `{city,dealType,…}` `apify` block; params are never guessed from the URL). Strict and fail-loud: a junk item (missing id, corrupt number) is skipped; an item error is fatal **only** when a call returned items but **none** were usable; a missing token / HTTP error / timeout is a loud `ApifyError`. Apify runs from a residential proxy pool, clearing the anti-bot wall the datacenter IP cannot. Priced per result, so it runs at most **once/calendar-day per search per kind**, under the §11 ≤₪120/mo ceiling; absent the token, the whole path is inert (primary-only). |
| **Runtime** | One systemd timer (`family-property.timer`), 1–2×/day (not real-time — listings don't churn by the minute and tighter polling raises ban risk). `TimeoutStartSec` + `MemoryMax` bound a stuck browser; independent of the bridge. |
| **Sheet landing zone** | `Property-Listings`: `listing_id` (dedup key) · `portal` · `first_seen` (ISO-T) · `price_ils` · `rooms` · `size_sqm` · `location` · `url` · `status` (human-edited: new/seen/contacted/dismissed). Append-only via `lib/sheet`; a listing that drops out of results is left in place. |
| **Delivery** | New listings land **silently** and surface in a "🏠 דירות חדשות / New listings" section of the 07:30 digest. They never alert and never bypass the budget — property is not critical-safety. |
| **Failure handling** | A scrape error or anti-bot block sets the fail-flag (`OnFailure` → `logs/fail.flag`); the next digest reports "property scrape failed" and the weekly briefing surfaces persistent failures. The realized escape hatch from a persistent block is the Apify secondary; an anti-detect browser on-box is a further fallback. |

### 12.2 Finance — Mizrahi / Max / Cal (live on Mizrahi + Cal, M6)

A committed monthly finance review is the standing consumer. Scope = Mizrahi (bank) + Max + Cal (cards); **categorized + month-over-month trends**; investments/brokerage out of scope. Anomaly detection stays killed. Delivery is silent. **Live on Mizrahi (debit) since 2026-06-19** (daily read-only scrape → categorized, idempotent Sheet write); the consumer wiring (M6.3) + analysis layer (M6.4) are landing. **Cal (Visa) live since 2026-06-23** — an *immediate-debit* card whose spend also lands merchant-less on the Mizrahi statement, so its own scrape supplies the per-merchant detail and the Mizrahi-side Cal settlement lines map to an excluded **`Card Settlement`** category (not a `Finance-Budget` row → out of the actuals `SUMIFS`) so each purchase counts **once**, via the card. More cards remain — Shanee's debit card + others (`BACKLOG.md` M6.5).

| Facet | Spec |
|---|---|
| **Source** | The online portals of Mizrahi-Tefahot + Max + Cal, read via `israeli-bank-scrapers` (Puppeteer/headless-Linux, pinned 6.7.8, Node ≥ 22.13 — the library's own `engines` floor). No public API; the library drives each portal's web session. **Read-only by nature** — it fetches balances + transactions and cannot move money. |
| **Mechanism** | A systemd timer runs `automation/finance/scrape.js`: logs into each provider with creds from `/etc/family-inc/bank_creds.json`, fetches balances + a **fixed ~45-day** transaction window (`FAMILY_INC_FINANCE_WINDOW_DAYS`; `Txn-ID` dedup makes overlapping reruns idempotent, so a fixed window is simpler and correct — no since-last-success state to keep), writes one CSV per provider to `/var/lib/family-inc/finance/`. `automation/finance_ingest.py` then normalizes, dedups on `Txn-ID`, and writes via `lib/sheet`. Node scrapes; **Python owns every Sheet write.** The local CSV is the only staging — no Drive. Same-day reruns overwrite the day's CSV and dedup on ingest → idempotent; the import advance gates on a successful Sheet write. **Categorization:** an on-box keyword→category rules engine tags each transaction at ingest; the configured LLM provider assigns categories the rules miss (description + amount on the rules-miss remainder only — §8.6). |
| **Runtime** | One systemd timer (`family-finance.timer`), **~06:00 daily** — ahead of the 07:25/07:30 morning runs so balances are fresh for the M6.3 finance consumers (the weekly briefing Money section + dashboard drawer + the >35d stale-import line). The **daily run is headless** Puppeteer (no Xvfb). The one-time `--auth` device-trust login (Auth model, below) runs **headed under xvfb + x11vnc** — the box already runs xvfb for the property scraper. Cadence is the first tuning knob: if Max/Cal re-challenges prove noisy, drop the cards to 2–3×/week and keep the bank daily. |
| **Auth model** | Read-only portal logins live at `/etc/family-inc/bank_creds.json` (mode 600, never in the repo, never logged). This is where the "no credential storage" non-goal is narrowed — *appliance-local, read-only financial logins*: this creds file **and** the per-provider device-trust browser profiles it authorizes (below), both appliance-local — while "no money movement" stays absolute (the scrapers cannot transfer). **2FA / device-trust:** Mizrahi is password-only. Max + Cal can re-challenge a fresh browser, and `israeli-bank-scrapers` 6.7.8 has **no programmatic OTP entry** for them (their credentials are username+password only; the library's `triggerTwoFactorAuth`/`otpCodeRetriever` path is OneZero-only). So **Max + Cal** each get a **persistent browser profile** (a Chromium `--user-data-dir`, mode 700, under the finance staging dir) — the device-trust cookie jar, a bearer artifact, hence covered by the narrowing above; **Mizrahi**, password-only, stays ephemeral (no stored session). A **one-time operator-driven headed login** — `node automation/finance/scrape.js --auth <provider>`, run on-box under xvfb+x11vnc viewed over an SSH tunnel (`deploy/FINANCE.md` §4) — clears the challenge once by hand; the portal then trusts that profile and the **daily headless run reuses it** and is not re-challenged. A re-challenge still **fails loud** (next digest); the remedy is re-running `--auth` (a same-window rerun stays idempotent via `Txn-ID` dedup). This is the persisted-session hardening, **brought forward to M6.2** because the cards need it to run unattended. **Cal live (2026-06-23):** the debit-only assumption was wrong — Cal was hooked up via the headed `--auth cal` login (the **first** real exercise of this path; verified daily-headless after), confirming the spec above against a live card. Remaining cards split by portal: one on a **new** portal needs a ~20-min `--auth` of its own; one on an **already-connected** login needs **no new auth** — it rides the existing scrape. **Shanee's debit card (M6.5, 2026-06-23) is the latter** — a Cal-cleared immediate-debit card on the connected Cal login, so its only repo change was the mirror token, no `--auth`; pending the 06-26 box-verify that her per-merchant rows actually ride that connected login (else a second `cal`-keyed provider). Either way each immediate-debit card also gets a **`Card Settlement`** mirror token (the Mizrahi side maps there so the spend isn't double-counted); the exclusion tokens sit **below** the merchant rules (a last-resort fallback) so a merchant-bearing line always categorizes by its merchant first — no other code change. |
| **Sheet landing zone** | Two tabs via `lib/sheet`. **`Finance-Accounts`** — one row per account/card, current-state (upserted on `Account Name`): `Account Name` · `Type` · `Bank/Provider` · `Last 4` · `Owner` · `Currency` · `Last Imported` (drives the >35d stale-import warning) · `Balance Snapshot` · `Notes`. The importer overwrites only the machine-owned columns, so a human's `Owner`/`Notes` survive a re-import. **`Finance-Transactions`** — one row per transaction, append-only, `Txn-ID` dedup: `Date` · `Account` · `Description` · `Amount (ILS)` (signed) · `Category` · `Cat-Source` (rule/llm) · `Txn-ID` · `Imported-At`. `Txn-ID` is a **stable hash of `Date|Amount|Description|Account`** (the natural key) — the provider `identifier` is recorded in the CSV but is **not** the key, because `israeli-bank-scrapers` reuses one identifier across distinct Mizrahi charges (trusting it dropped ~70% of rows on the first live import, 2026-06-19); the natural key separated every transaction with zero collisions and is stable across re-fetches. **Column order is load-bearing** — the `Finance-Budget` actuals `SUMIFS` over Date (A) / Amount (D) / Category (E). The date criteria are a **text-prefix wildcard** on the ISO-text `Date` (`<yyyy-mm>&"*"` for the month, `<yyyy>&"*"` for YTD, plus a `Last Month (ILS)` column for month-over-month): a serial `DATE()` window read ₪0 against the RAW-appended text dates, and keeping the append RAW leaves `Txn-ID` dedup intact — so text-prefix is chosen over a `USER_ENTERED` append, which would coerce `Txn-ID`/`Account` (M6.4). M6.3 installs the same formulas onto the live `Finance-Budget` tab via an idempotent installer (`automation/finance_budget_formulas.py`, single-sourced from `lib/finance_budget` and pinned against the seed) that stamps the machine columns only — a category row's Category/Target and every Notes cell are human-owned and never written (only the TOTAL row's Target is a machine `=SUM`), so there's no hand-copy and the stray-formula class is impossible — then verifies actuals go non-zero on the first real month. Retention: keep all (low volume; the monthly review wants history). |
| **Delivery** | Finance lands **silently**: balances, per-category spend, month-over-month trends, and actuals-vs-`Finance-Budget` surface in the weekly briefing **Money** section + the dashboard **Money** drawer, alongside the >35d stale-import line — **never an alert, never a budget bypass.** The only finance *message* is fail-loud. A ">₪500 single charge" alert is deliberately not wired (it's an alert path that brushes the killed anomaly lane — deferred to a deliberate PO call). |
| **Failure handling** | An OTP / device re-challenge (remedy: re-run `--auth <provider>`), a site-change error, or a Sheet-write failure sets the fail-flag; the next digest reports it ("⚠ <provider> צריך אימות מחדש" / "finance scrape failed") and the weekly briefing surfaces persistent failures + the >35d stale line. CSVs are retained on a Sheet-write failure (no data loss; retry next run). If a Cloudflare wall ever appears, the escape hatch is the maintained anti-detect fork on-box, then a managed-proxy pivot. A box compromise leaks read-only visibility only — no transfer capability. |

## 13. References

`ENGINEERING.md` — runtime, repo layout, testing, ops. `DESIGN.md` — dashboard UI, message design system, i18n. `BACKLOG.md` — current status; what's frozen. `ROADMAP.md` — the sequenced forward plan + v1.1 lane contracts. `Archive/` — the dated decision history and superseded docs.

=== End: SPEC.md ===

=== File: BACKLOG.md ===
# Backlog

*The only live status record. What's shipped, what's in flight, what's parked, what's frozen.*
*Legend: ✅ done · 🔵 in progress · ⬜ todo · 🧊 frozen. Scope and acceptance live in `SPEC.md`. The dated history of how each item landed lives in `Archive/`.*

## Now

**▶ Focus:** v3 Today redesign — **V3.9** (milestone review via `review.py` + canon close + BACKLOG flip) is the final slice; all UI + i18n/a11y slices are code-complete. **✅ V3.8 i18n + a11y + Settings shipped 2026-06-26**: a declarative **`data-i18n-aria` walker** (in `applyChromeStrings`, retiring the hand-rolled boot aria-labels); a **global `:focus-visible`** + **one consolidated `prefers-reduced-motion`** block (replaced 3 scattered ones; neutralizes transitions + `:active` scale + scroll); a hermetic **WCAG-AA contrast assertion** test (pins `--muted`/`--amber`/`--on-accent`/`--blue`, "assert don't re-pick"); a **real switch-account re-auth** (D3 — Google account chooser, **no token-revoke** so `LastDoneBy` stays truthful and re-picking yourself can't sign you out) + D7 (no notif/bank/export markup); the **token-alias endgame** (the 6 V3.1 aliases migrated across 24 refs + deleted; `--blue` kept as a theme-paired info token, given its missing dark value — the dark calendar-time fix, Shanee's "keep distinct info blue" call); and **cheap pure-function JS tests** (`parseDate`/`fmtISO`/`flagFor`/`bumpDate` via plain node, no toolchain — the **interactive-logic JS harness is a tracked deferred lane**, Deferred below). 2 PO calls settled (JS-test depth · `--blue` fate); **7-lens adversarial review** (correctness · auth/security · a11y · i18n/RTL · CSS-tokens · canon · test-quality, each refute-verified) → **9 confirmed, all fixed** — the switch-account **same-account-revoke major** dissolved by dropping the revoke entirely (revoke drops the shared grant), + the chooser-cancel dangling state, the redundant `.desk-row` focus ring, the missing dark-`--amber` assertion, and a TZ-fragile round-trip pin; **0 refuted**. SPEC §7.6 + DESIGN §2/§3/§8/§9 graduated, **468 tests green** — code-complete, **deploy-gated by the Pages publish**. V3.1–V3.7 on Pages; V3.7 love-notes **text** is additionally tunnel-gated; **voice** is a frozen phase-2.
<!-- ^ this Focus pin steers session_kickoff.py's next-session headline; retarget it when the active lane changes. -->

**🔭 Spec-ahead pass — 2026-06-20.** A full audit (**50 verified** canon-vs-code drift findings, 0 false positives) reconciled the canon to reality, and a value/risk/dependency roadmap pass produced **`ROADMAP.md`** — the sequenced v1.1 plan + per-lane forward contracts (5th canon doc). PO calls landed: GAP-7 → **fix (fail loud)**; reviewer default → **`review.py` flipped to DeepSeek** (code now matches the "DeepSeek default" canon; ollama is the keyless fallback); the 3 never-built DESIGN components (progress arc, connection pill, skeleton/shimmer) → **removed**; spec-ahead → **ROADMAP.md**. ~30 drift edits applied across SPEC/ENGINEERING/DESIGN/README + code one-liners (git history is the dated record). Suite **390/390** green, tree clean at HEAD. **CI gate (lane 1) built this session (2026-06-22) — see the dedicated paragraph below; next build lane = GAP-7 Hebcal fail-loud (`ROADMAP.md` §2 rank 2).** Two Brief-2 stragglers that had fallen off the board are now tracked: **reminders-engine#1** (closed by the SPEC §8.4 reconcile — no `rem-` id is emitted) and **reminders-engine#3** (OVERDUE 3-day boundary test, folded into Lane E). **Box-side verification ran 2026-06-23 (the second VPS hour) — see the dedicated paragraph below; the asserted-live claims are now box-verified.** Open before the 06-26 gate: define the classifier-accuracy **pass threshold**; **fix the live categorization yield** (the VPS hour found ~77% of live transactions uncategorized → `Finance-Budget` actuals understated).

**✅ CI gate (ROADMAP §1, lane 1) — merged to `main` 2026-06-23 (`9bf50cb`).** New `.github/workflows/tests.yml` runs the hermetic suite on every push + PR to `main`, so a red commit can't merge. Three parts: the **pytest gate** (mirrors `deploy.sh`'s `FAMILY_INC_SHEET_ID= uv run --frozen pytest -q`, + Node 22 so the `@requires_node` syntax-check tests run, not skip); a **repo-wide PII-leak guard** (`tests/test_repo_pii_guard.py`) scanning every tracked text file via patterns extracted to **`automation/lib/pii.py`** — one source of truth, now also backing the seed guard (`test_seed_safety.py` refactored, behaviour identical) — **scoped + allowlisted** per PO call (synthetic-by-design `tests/`/`seeds/`/`reviews/`/`Archive/`/`mock_data.json`/lockfiles exempt; the new transaction-shaped `ILS_AMOUNT` skips `.md` prose; identifiers scanned everywhere); and a **`config.js` smoke** (`tests/test_dashboard_config_smoke.py`) pinning `pages.yml`'s sed anchors + `node --check`. Built as **pytest, not a grep step** (rides `deploy.sh` on the box — no `deploy.sh` change) and runs on the **whole tree, no path filter** (so a PII paste anywhere trips it) — both deviations from the §1 sketch, recorded in `ROADMAP.md`. Suite **390 → 421** (+26 pattern regression cases + guard + smoke). Adversarially reviewed (4 lenses). **No external `review.py` gate**: a hermetic test addition, no spec/arch/policy change (CLAUDE.md §6). **The first Actions run (2026-06-22) was RED** — `astral-sh/setup-uv@v8` is unresolvable (setup-uv publishes floating major tags only through v7; v8 exists only as full release tags like `v8.2.0`), so the job died at *Set up job* in ~3s with empty logs; the earlier "`@v8`, verified against the live tag list" note was wrong (`v8` is a release prefix, not a usable ref). **Fixed by pinning `@v7`** (`5168c6d`); first green run confirmed 2026-06-23, then **merged to `main`** (`9bf50cb`, fast-forward, bundled with the finance-lib bump). Lane 1 closed; the gate now guards every PR to `main`.

**✅ Box-side verification (ROADMAP §3.0 lane 7) — ran 2026-06-23 (the second VPS hour).** A read-only 36-check appliance sweep confirmed the live system is **fundamentally healthy**: bridge up + daily digests delivered to both phones (baileys), all 7 timers + 16 units byte-match the repo, single sudo capability + secrets locked down (Mizrahi-only, none in git), outbox budget/quiet-hours/email-fallback/GAP-2 contracts intact, summarizer on DeepSeek (0 fallback drops), property + backups working, live Sheet reads verified (Txn-IDs 117/117 unique, no doubling). **Three findings, all resolved or triaged:** (1) the box was **3 days stale** (`c282afb`, −4 commits — violating committed≠deployed) → **`deploy.sh` to HEAD** (`9bf50cb`); (2) the **finance scrape was down since 06-22** — an `israeli-bank-scrapers` `#/change-pass` URL timeout while a *human* login showed no password-change screen (library-vs-site drift, or a transient bank hiccup — **not** a forced password change) → **bumped 6.7.3 → 6.7.8** (5 patches behind; live re-scrape green, fresh data); (3) **categorization is ~77% blank** (90/117 rows) → a **prioritized M6.4 item before 06-26** (see M6.4). The build of the read-only runbook + adversarial check ran as a Workflow; execution was PO-on-box (no box access from the repo machine).

**v1 is live and accepted** (since 2026-06-13, tagged `v1-live`): the morning WhatsApp digest, the weekly briefing, the dashboard write-back loop, and the group summarizer all run unattended on the appliance. The **property tracker** is live (Yad2 on-box + Madlan via Apify). The summarizer runs on **DeepSeek**. **Finance ingestion (M6) is live on Mizrahi (debit) since 2026-06-19** — daily read-only scrape → categorized, idempotent Sheet write; M6.3 (consumers) + M6.4 (analysis) remain; **Cal (Visa) hooked up 2026-06-23** (an immediate-debit card whose own scrape brings the categorizable merchant detail — ~90% categorized) so the **cards lane is un-deferred** (M6.5; **Shanee's debit-card mirror landed 2026-06-23** (box-verify pending) — a Cal-cleared card on the connected Cal login, no new auth; more statement cards to add). The M6 classifier-accuracy run + external milestone review are **gated to ~2026-06-26** (a week of live finance data from go-live). The two summarizer-review items remain gated ~2026-06-20.

**✅ Audit fix lane — Brief 1 (blocker + 7 majors), landed 2026-06-18** (from the 2026-06-18 full-project audit in `reviews/`): bridge 1:1 chats are now **log-only, no ack** (B1, SPEC §7.4); the candle-lighting line fires on **erev-chag** too (B2); **criticals pierce mute** while non-critical rules are suppressed in muted groups, closing the budget-bypass (B3, SPEC §7.3); LLM privacy reconciled **provider-agnostic** (B4, SPEC §8.6/§8.7); finance gap-fill **chunk-loops** so a large first import is fully categorized (B5, M6); `deploy.sh` installs the **finance Node deps** + restores `--frozen` (B7, M6 — unblocks M6.2); the weekly briefing carries the **ENGINEERING §8 self-report line** (B6); the dashboard offline queue **caps at 50 with a one-shot warning** (B8). Tests green (350). **Brief 2** (10 gaps + minors + disputed) remains open. The fix touched privacy/delivery/budget → the `review.py` gate **ran 2026-06-18** (DeepSeek; `reviews/review_milestone_2026-06-18_16-41.md`): B1/B4/B5/B7/B8 affirmed; one false-positive defended (the mute short-circuit already follows the critical check), `chag_candles` window widened to +5d (Applied), and the dashboard-recurrence-bump finding routed to **Brief 2 GAP-4** (Open — pre-existing, out of lane).

**🔵 Brief 2 (small fixes) — Lane A + Lane E canon-hygiene landed 2026-06-18.** Lane A (finance hardening, M6-critical): GAP-1 `Dining`→`Dining out` aligned + a guard test pinning `rules.vocab ⊆ budget` (Fees/Income/Shopping held as a tracked allow-list **pending Shanee's budget-vocab migration** — the authority); finance-ingest#3 distinct in-batch-dup counter; OTP "interactive" promise scrubbed to truth (decision #1); fixed 45-day window doc'd (decision #2); Node pin bumped to ≥22.13 (the lib's real floor); GAP-6 `data_only` caveat + tests-quality#3 comment; seeds/README documents the committed rules CSV. Lane E hygiene: `Haiku`→DeepSeek docstring, ENGINEERING boundary-rules wording, 7-timers, finance-timer/SPEC consumer wording, D-NN sweep, BACKLOG Hebcal-line correction, `FINANCE_PLAN.md`→`Archive/`.

**✅ Lane S (publish/privacy safety) — landed 2026-06-18.** Audited all 18 tabs of the committed `Family_OS.xlsx`: **confirmed synthetic by construction** — no real emails (all `example.com`), phones, Teudat-Zehut (`000000000`), JIDs, or account numbers; the only real identifiers are the principals' first names `Adar`/`Shanee`, which are **accepted-public by design** (owner-routing tokens `OWNER_TO_RECIPIENTS`, Settings UserMap, CLAUDE.md roles, git author) — so GAP-5's feared real-PII leak was unfounded. Added **`tests/test_seed_safety.py`** (the dedicated check — fails CI if any high-severity PII is ever pasted into the seed) and documented in `publish_paths.txt` why the binary seed is kept-at-HEAD-and-guarded rather than history-stripped. deploy-systemd#4: `publish.sh` gauntlet now verifies `regex:` redaction rules (PCRE) instead of silently skipping them. Tests 355→357. **Review gate ran** (DeepSeek; `reviews/review_spec_2026-06-18_19-02.md`): core decisions affirmed; Applied — seed-safety test hardened (config sanity-check so it can't pass vacuously + Unicode-domain email detection) and `publish.sh` no-PCRE failure made actionable; Defended the O(N·M) re-grep + the "rewrite gauntlet in Python" alternative (fail-loud suffices); a full seed-recovery script left as a deferred nicety (the test already fails loud + names the recovery command).

**🔵 Lane B (robustness seams) — GAP-2 + budget#3 landed 2026-06-19; GAP-3 + bridge-node#2 remain.** Earlier (2026-06-18) the bounded outbox-integrity cluster landed: **outbox-budget#1** — the budget ledger now writes atomically (tmp+replace) and reads **fail-CLOSED** (a corrupt ledger reads as cap-reached → alerts defer, never flood; loud for the operator); **outbox-budget#2** — an `fcntl` lock around the ledger read-modify-write so concurrent senders can't double-spend the 2/day cap; **GAP-10** — the bridge's `processOutbox` got per-row try/catch (one failed `sendMessage` no longer abandons the rest of the batch; transient failures retry, only terminal sent/refused suppress); **GAP-8** — the multi-timer Sheet race documented as accepted (SPEC §8.3). **✅ GAP-2 (the [high] silent-loss path) + outbox-budget#3 — cross-run reconcile, 2026-06-19.** The digest no longer stamps Last Sent/Status when it *queues*; it records a pending row per recipient (`digest_pending.jsonl`) and `reconcile_deliveries()` (start of each `--send` run) stamps — and clears the fail flag, and consumes the budget-deferred alerts the digest carried (budget#3) — only for the entries the bridge has **confirmed** in `whatsapp_sent.jsonl`. Unconfirmed past **48h** (PO call) → dropped + logged, reminders re-fire (no silent loss). The SMTP fallback confirms inline. "Sent" on the Sheet now means *delivered*. Because the stamp lands a run after the digest, reconcile re-reads the Sheet and never resurrects a row the user has since completed/rescheduled/recurrence-bumped (or one with a §8.3 write in flight), and dates Last Sent to the digest's send day — a blocker the adversarial review caught and that now has its own regression tests. The rejected bounded-in-run-wait is documented in SPEC §7.5. Transport log moved to confirmation time (`baileys` on confirm; `queued-stale` at queue only when the bridge is visibly down, or on stale-drop). The interim-risk window (silent-loss open since v1) is **PO-acknowledged**. Tests 358→369. Canon: SPEC §7.1/§7.2/§7.5/§8.4. **Review gate (delivery+budget) runs at close.** Remaining Lane B: GAP-3 (JSONL rotation), bridge-node#2 (bridge scope-guard test harness).

**Deferred** (next sessions): **Lane B remainder** (GAP-3 JSONL rotation, bridge-node#2 scope-guard harness), Lane C (dashboard), and Lane E's code-correctness + test-gap items (digest >30d flag, derive_rule, property-apify, OVERDUE-overflow test, reply_handler stub flags, the deferred "budget is biting" line — decision #3). **⬜ Dashboard JS test harness (raised V3.8):** `dashboard/app.js` (~2440 lines) crossed the ~2000-line JS-harness trigger (ENGINEERING §7). V3.8 added cheap **pure-function** node tests (`tests/test_dashboard_js_pure.py` — `parseDate`/`fmtISO`/`flagFor`/`bumpDate`, no toolchain), but the **interactive** logic (desk selection + batch write fan-out, bottom-sheet focus-trap, absolute-snooze, love-note fetch) is still covered only by `node --check` + the manual DESIGN §9 smoke. A real harness (jsdom + a runner) is a **build-step decision** vs the no-build-step principle — a deliberate PO call, deferred as its own lane (don't bolt a toolchain on mid-redesign).

## Shipped

- **Keystone loop** — reminders engine (07:25) → daily digest (07:30) → WhatsApp, with dashboard write-back, the outbox budget chokepoint, quiet hours, and the offline-write tombstone guard.
- **Weekly briefing** (Sat 21:00) — deterministic template, the system self-report, and a classifier-accuracy section. *(The candle-lighting Hebcal line is the daily digest's, not the weekly briefing's.)*
- **WhatsApp summarizer** — 5 hard rules + DeepSeek (with keyless keyword fallback), per-group routing, critical-keyword bypass.
- **Daily digest is partner-symmetric** — both adults briefed every day; the empty-handed adult gets the quiet-day line + shared sections, budget-free.
- **Property tracker** — saved-search scrape (headed Chromium under Xvfb) + Apify secondary (backup + gap-fill, primary always wins), silent `Property-Listings` landing + morning digest section.
- **Delivery hardening** — email (SMTP) fallback when the bridge is silent >24h, fail-flag → next-digest reporting, transport logging; email days count as degraded, not green.
- **Go-live + publication** — VPS provisioned, Baileys paired (7.x/ESM), GitHub Pages + PWA pinned to both phones, repo history rewritten clean and made public.
- **Classifier-accuracy surface** — `accuracy_review.py` re-derives each ALERT's rule from persisted Inbox fields (no schema change); a compact pulse folds into the weekly briefing.

## In progress — M6 finance ingestion

Banks + cards, categorized + trends, delivered silently. Read-only logins permitted on the appliance; "no money movement" unchanged. Full contract: `SPEC.md` §12.2.

- ✅ **M6.1 — repo port + schema (hermetic, no appliance).** `automation/finance/scrape.js` (read-only login → CSV) + `finance_ingest.py` (CSV → normalize → Txn-ID dedup → `lib/sheet`: append `Finance-Transactions`, upsert `Finance-Accounts`). Finance tabs standardized to `Finance-Budget`/`Finance-Accounts`/`Finance-Transactions`; `Category`/`Cat-Source` ship present-but-blank (the budget `SUMIFS` keys on the Category column position). `family-finance.{service,timer}` + provision wiring. Tests green; no live bank contact.
- ✅ **M6.2 — appliance deploy + first live auth (the "VPS hour"), live 2026-06-19.** Box brought to HEAD + finance units installed; `bank_creds.json` placed (Mizrahi only); the 3 live tabs renamed; Mizrahi proven end-to-end — daily read-only scrape → categorized Sheet write, **98/98 transactions, idempotent on re-run**. Two live bugs caught + fixed: (1) a forced Mizrahi **password change** (cleared by hand; `FINANCE.md §0`); (2) a silent **73% data-loss dedup bug** — `israeli-bank-scrapers` hands Mizrahi a *non-unique* `identifier` and `txn_id()` trusted it (96→26); fixed to a **natural-key hash** (`date|amount|description|account`), tests rewritten + regression added (378 green), SPEC §12.2 updated, deployed. **Cards were deferred here on a "debit-only household" assumption that turned out wrong — un-deferred 2026-06-23 when Cal was hooked up (M6.5); the `--auth` device-trust path, built-but-dormant since 06-19, was finally exercised.** Follow-up (deferred): `append_rows` should re-write a missing header so a stray Sheet clear can't silently double the tab. **Runbook: `deploy/FINANCE.md`.** **Library maintenance (2026-06-23, the second VPS hour):** the daily scrape failed 06-22 on an `israeli-bank-scrapers` `#/change-pass` login-flow timeout (no real password change — a human login was clean) → bumped **6.7.3 → 6.7.8** (the library patch-tracks Mizrahi site changes; we were 5 behind); CI green, box deployed to HEAD, live re-scrape green (3 runs 06-23, fresh data). The recurring-interstitial fragility is the standing risk; if it returns on 6.7.8, escalate to a headed `--auth` run (`FINANCE.md §4`) to see what the bot session faces.
- 🔵 **M6.3 — consumer wiring + close.** Briefing Money section + dashboard Money drawer read live; the >35d stale-import warning is armed (`FINANCE_STALE_IMPORT_DAYS`). **Budget-SUMIFS installer ran live 2026-06-20** (`automation/finance_budget_formulas.py`): stamped the 66 machine cells onto `Finance-Budget`, actuals verified **non-zero** (Groceries/Transport; Health ₪0 — no health debits in-window, re-check in the 06-26 accuracy run) — the M6.4 reconciliation tail is now live. *Live-tab drift caught + fixed:* the early-created live tab was one column short of canon — the M6.4 helper block's **`J` `Last Month (ILS)`** header was never backfilled, so the installer's load-bearing-column guard refused; set `J1` by hand, then it stamped clean. **Installer then hardened (390 green):** it now titles its own *absent* machine headers (incl. `J`) and stamps, refusing only on a missing *human* header (Category/Target) or a real column shift — so Shanee's migration needs only Category + Monthly Target present, no machine-column setup (`deploy/FINANCE.md §6`, `test_budget_installer_titles_absent_machine_header`). **Dashboard `config.js` was a non-issue:** Pages generates it from `config.example.js` (already full tab names) on every `dashboard/**` push, and the TOTAL-row-exclusion fix shipped via Pages 2026-06-20 — no box-side edit. The dashboard Money drawer + Sunday money summary exclude the `Finance-Budget` `TOTAL` row (fixed at the `parseAll` source so both surfaces inherit it; the briefing's `section_money` already skipped it, tested); `mock_data.json` carries a TOTAL row so DEMO_MODE matches live. **Remaining = acceptance only:** the first real monthly review (~30 days in); classifier-accuracy run + external review gated ~2026-06-26.
- 🔵 **M6.4 — analysis layer.** *Repo half built + tested (2026-06-18).* The on-box rules engine (`automation/lib/categorize.py` + committed `seeds/14_Finance_Category_Rules.csv`) populates `Category`/`Cat-Source` at ingest; DeepSeek gap-fills the rules-miss remainder (description + amount only, §8.6). The briefing Money section gained per-category spend + month-over-month (the dashboard drawer reads the same tab — M6.3). **Reconciliation (the build-note landmine, resolved):** budget actuals now `SUMIFS` with a **text-prefix wildcard** on the ISO-text Date (`<yyyy-mm>&"*"`), not a serial `DATE()` window that read ₪0 — chosen over `USER_ENTERED` (which would coerce `Txn-ID`/`Account` and break dedup); the append stays RAW. Seed formulas updated + a regression test pins the form. **Installer built + tested 2026-06-20:** `automation/finance_budget_formulas.py` (single-sourced from `lib/finance_budget`, pinned against the seed) idempotently stamps the machine columns onto the live tab — machine columns only (a category row's Category/Target and every Notes cell untouched; only the TOTAL's Target is a machine sum), so there's no hand-copy and the "stray Notes SUMIFS" copy-artifact class is gone. **Gated to live data:** run it on the box (`--dry-run` first) + verify actuals go non-zero on the first real month. **PROVISIONAL** category vocab until Shanee's budget migration firms it up — when she remaps, just re-run the installer. Silent delivery; no anomaly detection. **Live categorization — reframed 2026-06-23 (Cal hookup): the earlier "~77% blank" alarm is *mostly structural, not a classifier failure*.** The blank rows on the Mizrahi debit are merchant-less wrappers (Cal settlements, ATM, cheque, other cards) that correctly return UNKNOWN — there is no merchant to categorize. Proof: **Cal's own scrape categorizes its 102 rows at ~90%** (the full tab now reads 48 rules + 74 LLM), because the card carries per-merchant descriptions. So the fix is **more sources** (hook up the remaining cards — M6.5), **Shanee's vocab migration** (firms the provisional vocab for the categorizable rows), and a **one-time re-categorize backfill** of the historical blank rows — none exists today (`finance_ingest` only categorizes *new* rows, so the backlog never re-enters the engine). This trio is the substance of the gated 06-26 accuracy work; the `Finance-Budget` total is understated only by the genuinely-uncategorizable cash/cheque/other-card spend until those cards are added.
- 🔵 **M6.5 — cards lane (un-deferred 2026-06-23, the third VPS hour).** **Cal (Visa) is live** — hooked up via a one-time headed `--auth` device-trust login (xvfb + x11vnc over an SSH tunnel; `FINANCE.md §4`), now scraping **headless** daily (first import 103 txns, ~90% categorized). Cal is *immediate-debit*, so each purchase already lands merchant-less on the Mizrahi statement; the Cal scrape is what supplies the per-merchant detail. The Mizrahi-side Cal settlement lines map to an excluded **`Card Settlement`** bucket — a rules entry (`כא"ל`/`ויזה כאל` tokens; ASCII-quote `U+0022` verified against live data, no over-match incl. Shanee's `כרטיס דביט` and the `כארם` restaurant) + a test seam (`test_card_settlement_excludes_cal_mirror`, plus the vocab-test `excluded` set + inverse guard so a future budget migration can't make it a budget row; 422 green) — so each Cal purchase counts **once**, via the Cal side, never the mirror. **Verified no double-count empirically** (both Money consumers read the by-category `Finance-Budget` actuals; the mirror lines stay out of the SUMIFS). **Open:** **(a) Shanee's debit card — mirror token landed 2026-06-23 (this session).** It turns out to be a Cal-cleared *immediate-debit* card on the **already-connected Cal login**, so it needed **no new `--auth`** — *correcting the morning's "each remaining card needs its own auth" assumption*. The only repo change is the `רכישה בכרטיס דביט` → `Card Settlement` mirror token (its per-merchant detail rides the existing Cal scrape), plus **flipping the 06-23-morning over-match guard** (`test_card_settlement_excludes_cal_mirror`: `רכישה בכרטיס דביט` was asserted *not*-excluded when her card wasn't yet scraped; now asserted excluded — a `דמי כרטיס דביט` fee-line guard (tightened 2026-06-25 to assert `== Fees`) so the full `רכישה ב…` phrase can't catch a card fee). **Over-match fix (2026-06-25):** the whole `Card Settlement` exclusion block was moved *below* every merchant rule (a last-resort fallback), plus merchant-suffix contract assertions and a `test_excluded_bucket_never_shadows_a_merchant` ordering-invariant test; 423 green. **Box-verify pending (de-risked, not blocking):** (i) confirm her per-merchant rows actually ride the existing Cal scrape — the mirror only reclassifies the Mizrahi line blank→excluded (budget total unchanged either way), so the "count once" correctness completes when her Cal rows are confirmed flowing; if they're on a *separate* Cal login, add a second `cal`-keyed provider + creds + `--auth`. (ii) **RESOLVED 2026-06-25 (structural):** the exclusion block now sits *below* the merchant rules, so a merchant-suffixed settlement line categorizes by its merchant and only genuinely merchant-less wrappers fall through — the 06-23-flagged latent over-match is closed independent of the live feed (the invariant test pins it). The other statement cards still need each source confirmed before a mirror (`ויזה-דביט`; `חיוב ויזה כאל עתידי` is already caught by the `ויזה כאל` token). **(b)** the historical **backfill** (M6.4) to move the existing 66 Cal mirror rows to `Card Settlement` (the rule is forward-only — it tags new rows at ingest; correctness already holds since blanks are excluded, but the yield metric + ledger clarity want it).
- ⬜ **Parallel (Shanee).** Budget migration — her manual budget → `Finance-Budget`; gives the actuals a target and defines the category vocab the rules engine maps to.

## Gated — summarizer review (opens ~2026-06-20, needs ≥1 week live)

- ⬜ **First real classifier-accuracy run + false-positive cleanup** — run `accuracy_review.py` over a full week of live DeepSeek output; narrow any over-firing keyword patterns.
- ⬜ **External milestone review on the live system** — folds in the property lane's review too.

## v1.1 candidates — now sequenced & contracted in `ROADMAP.md`

The pool below was **ranked, phased, and given forward contracts** in `ROADMAP.md` (the 2026-06-20 spec-ahead pass). Status still lives here; the **plan + contracts** live there. In brief:

- **Now → ~06-26 (hardening):** CI gate (+ PII-leak guard + `config.js` smoke) · GAP-7 fail-loud fix · ~~Lane C dashboard write-contract (col-D format + header guard)~~ **✅ shipped 06-26** (col-D stays a real date cell; both surfaces write the ISO literal; `parseDate` reads ISO + he-IL DD/MM·DD.MM; JS write surface header-guarded → SPEC §6.1/§7.6/§8.5; unblocks V3.3) · uptime-ping · box-side verification · stale-digest→briefing line · JSONL rotation · Lane E batch.
- **After 06-26:** M6.3/M6.4 acceptance (classifier-accuracy run + budget-vocab migration + external review) · classifier-fp-metric · bridge scope-guard harness *(hard prereq to reply-parsing)*.
- **Later v1.1 (post the 30-day hold, each a PO call):** reply-parsing (needs a budget-exempt `ack` kind) · inbox-trigger · apify-cap · calendar-connectors (decomposed — Hebrew-string pass pullable early).
- **Frozen (joint / Shanee call):** big-charge-alert (brushes the **killed** anomaly lane) · ai-briefing (whole-Sheet→provider privacy expansion) · GCal/iCloud auto-ingest (credential-storage amendment).
- **🔵 v3 Today redesign (decided 2026-06-25; building).** The dashboard Today surface gets a cool retone + new IA + two net-new components (parent-to-parent love-note, cross-domain timeline). 8 design calls co-signed (Adar + Shanee) after an 8-dimension adversarial review; decision record + design tokens in `V3_RECONCILE.md`, lane contract + V3.1–V3.9 build sequence in `ROADMAP.md` §3.8, file-level build plan in `V3_BUILD_PLAN.md`. **All 4 build blockers resolved 2026-06-25** — window: **build the whole lane now**; col-D → **ISO `YYYY-MM-DD`**; days 3–7 calendar → **coming-up strip carries events**; love-note exposure → **Cloudflare Tunnel**. **✅ V3.1 token retone landed 2026-06-25** (cool palette + IBM Plex Mono all-numerals + AA-cleared amber/muted; rename-with-aliases so no selector breaks; semantic washes wired to tokens via `color-mix`; DESIGN §2 Color/Type graduated + smoke #9 added; 423 tests green) — **code-complete, deploy-gated by the Pages publish** (committed ≠ deployed). **✅ V3.2 scaffold + 3-tier pill landed 2026-06-25** (`#view-today` rebuilt into named slots love-note/calendar/desk/coming-up/portfolios with the legacy renderers kept green inside; single 3-tier status pill — red/amber/sage + mono count + a neutral `loading` tier — replacing the old pill **and** the banner: `role=status`/`aria-live`, never color-only, and it closes the old green-`banner clear`-on-load premature-"all clear"; shared `computeCounts()` ready for V3.3's desk; a `source==='shabbat'` parseAll seam for V3.4; DESIGN §2/§3/§4/§9 graduated; a new `node --check app.js` CI guard; 7-lens adversarial review → 2 real findings fixed (Shabbat seam was over-tagging the whole Hebcal feed; a stale §4 banner reference); **429 tests green**) — **code-complete, deploy-gated by the Pages publish**. **✅ V3.4 3-day scroll-snap calendar landed 2026-06-25** (`#today-cal-strip` — an x-snap strip of exactly 3 panes today/+1/+2, read-only, reusing `.cal-event` rows; the V3.2 `source==='shabbat'` seam → 🕯 glyph + non-color inline-start border; `renderNext7`'s calendar-event window narrowed to **3–7d** so the strip and the Next-7 list can't double-render +1/+2; mock fixture gains a Fri candle-lighting row so DEMO exercises the Shabbat tag; DESIGN §2/§3/§9 graduated; 7-lens adversarial review → **5 fixed** (2 majors: shadow-clip from forced `overflow-y`, the +1/+2 overlap; 1 minor: aria-hidden the 🕯; 2 nits: hardened the time-sort vs un-padded hours, deleted the orphaned `empty.noEventsToday`); **429 tests green**) — **code-complete, deploy-gated by the Pages publish**. **✅ V3.5 portfolios + one data-driven bottom-sheet landed 2026-06-25** (the 6 domain accordions → a grid of 5 `<button>` tiles — Money hero (overall-% donut + category bar + 7-day sparkline), Health (initials-avatars, non-color urgency), Goals (% bar; bright-line moved into the sheet, D8), Car, Contracts — that open **one** shared, data-driven `role=dialog`/`aria-modal` bottom-sheet (focus-trap + scroll-lock + `#app` `inert` + focus-return-to-tile + Esc/scrim/close + reduced-motion); `renderKpi`/`renderSparkline`/`renderGoalLine`/`isSpendTxn` kept + reused; **PO calls 2026-06-25**: Education drops from Today (data retained → V3.6 timeline), 5 tiles now (Timeline tile lands in V3.6), Money donut = overall %; DESIGN §2/§3/§9 graduated; 7-lens adversarial review → **8 fixed** (4 majors: focus-return detached-on-reload, Car warn was color-only, `.sheet-body` couldn't scroll [flex `min-block-size`], + the dup focus-return; 4 minors/nit: `#app` not inert, `-Xd` overdue copy, scroll-reset on reload, the hero amount's bidi-isolation, reduced-motion on tiles); **429 tests green**) — **code-complete, deploy-gated by the Pages publish**. **✅ V3.6 cross-domain timeline landed 2026-06-25** (a 6th portfolio tile [2nd, after the Money hero] opens the shared bottom-sheet onto a **read-only chronology** — every dated row across all domains flattened onto one vertical, date-sorted axis with a now-marker, an exponential **1wk→5yr** zoom [default 3mo], and a category-chip filter [`finance · health · car · education · goals · contracts · calendar · other`]; zoom/filter swap **only** the track + `aria-pressed`, keeping the pressed control's focus; non-color urgency [glyph + due phrase]; **the two PO calls were ratified 2026-06-25** [Adar + Shanee onboard] — the *everything-dated* inclusion rule + the full Domain→category map, with **Education's only Today home = this timeline** — both **graduated to SPEC §7.6**; DESIGN §2/§3/§9-item-13 graduated; a new hermetic **STRINGS he↔en parity test**; 7-lens adversarial review → **6 confirmed fixed** [dark-mode pressed-chip AA via a new theme-paired `--on-accent` token; reset-to-3mo-default on each open; `meta` now rendered for cross-domain disambiguation; the `Archived`-status canon mismatch reconciled to the §6.1 enum; + focus-restore-on-bg-reload, the sticky-controls seam, and the tile `≤14` boundary]; **430 tests green**) — **code-complete, deploy-gated by the Pages publish**. **✅ V3.7 love-notes (text phase) landed 2026-06-25** (the first dashboard datum that is **neither the Sheet nor the outbox**, a sanctioned §3.1 exception: a net-new appliance endpoint `automation/love_note_server.py` — stdlib `ThreadingHTTPServer` on localhost, `GET/PUT/DELETE/OPTIONS /lovenote`, **one ephemeral note per direction**, **24h-or-on-replacement** [lazy read-expiry + an hourly `sweep_love_notes.py`], **flat-JSON-per-direction** storage [the ratified storage-shape call], **access_token→Google-tokeninfo** verify (opt-in **audience check** vs the dashboard's OAuth client when `FAMILY_INC_LOVENOTE_AUD` set — closes the confused-deputy gap; a refinement of the ratified userinfo call surfaced by the review) → `Settings.UserMap`→parent [unknown→403], token **never persisted/logged** [a short SHA-256-keyed in-memory verify cache, never the raw token], **tight CORS** to the Pages origin [blank origin → feature self-disables fail-safe], request-body cap [413] + chunked-reject pre-auth; **3 systemd units** [+ `TasksMax`/`CPUQuota`] + a **Cloudflare-Tunnel** connector unit; the **4th `pages.yml` sed** + `DASHBOARD_LOVENOTE_URL` secret + **4th `config-smoke` anchor**; the dashboard slot [inbound 💌 card hidden-when-empty + composer, no push, **no 'seen' signal**, parent-only gate, draft-preserving re-render] + he↔en STRINGS + `mock_data.json` fixture; **29 new security/behaviour tests** [no-outbox-import · no-Sheet-write · token-never-persisted · CORS allowlist · unknown-email 403 · dual expiry · one-per-direction · audience-reject · non-object-JSON guards]; **SPEC §7.7** [+ §3.1 exception, §4 voice-frozen note, §8.6 privacy bullet] + **ENGINEERING §5/§6** [units + the box's first inbound listener + the 2nd sudoers/restart line] + **DESIGN §3/§9-item-14** graduated; a **3-lens adversarial review** [security/correctness/contract, each finding verified] → **11 confirmed fixed**; **459 tests green**) — **code-complete, deploy-gated** on the PO standing up the Cloudflare Tunnel + the `DASHBOARD_LOVENOTE_URL` secret (committed ≠ deployed; the feature stays inert until both land). **✅ V3.3 desk + coming-up + absolute snooze landed 2026-06-26** (the Lane-C-gated straggler, now unblocked): `renderToday`→a **select-to-act desk** — `deskRow` checkbox-semantics rows (`role=checkbox`, click + Space/Enter, non-color selection = a ✓ box + `--soft` wash + `aria-checked`), `attachRowHandlers` rewired from the `.expanded`/`.snoozing` accordion to selection, a sticky batch bar fanning `state.deskSelection` out to **one** `applyWrites` per action (the recurrence bump multiplied per row); **absolute snooze** — `handleBatchSnooze` writes `Due = <absolute ISO>` (5 chips today+1/3/7/14/30 **+ a `min=today` date picker**), retiring the relative `+Nd` pills, so an overdue row snoozed forward clears OVERDUE (the D4 fix); `renderNext7`→**`renderComingUp`** — a read-only **±30-day** horizontal scroll band with a now-marker (past = calendar events only [overdue stays on the desk — PO call]; future = WEEK/MONTH-OUT reminders + events; today/+1/+2 owned by the 3-day strip; opens positioned at "now", RTL-aware `scrollBy`). The old `handleDone`/`handleSnooze`/`handleAddNote` + `renderReminderRow` deleted; `applyWrites`/`enqueueWrites`/`flushQueue` + the col-O tombstone + `flagFor`/`flagEmoji` kept unchanged. **6 PO calls settled** (5 snooze chips + a date picker · ±30 scroll band · read-only chips · past-events-only back-scroll · inline note composer · — vs the earlier ambiguity). New STRINGS he+en (`snooze.*`/`desk.*`, namespace agreed once with V3.8); SPEC §6.1 write contract + DESIGN §2/§3/§5/§9-items-16–18 graduated; demo fixture enriched (a fire-today row + a month-out reminder + a future event so DEMO exercises the desk + the band's future side). **7-lens adversarial review** (correctness · Lane-C write-contract · a11y · RTL/i18n · CSS · XSS · canon-conformance — each finding refute-verified) → **9 confirmed, all fixed** (note-textarea aria-label · 44px snooze tap-targets · focusable coming-up region · focus-return after a batch · flag-emoji aria-hidden in the checkbox name · live-region selection count · Hebrew `נבחרו: {n}` number-agreement · re-arm the date picker so a repeat pick fires · past-date snooze guard) and **2 correctness claims correctly rejected** (the offline-queue cap still holds — not the B8 bug; the drop-then-mutate is pre-existing single-row behaviour a reload corrects); **460 tests green** (the interactive JS stays `node --check` + STRINGS-parity + manual-smoke covered — `app.js` ~2150 lines now crosses the ~2000-line **JS-harness trigger**: raise a harness lane in V3.8/V3.9). **— code-complete, deploy-gated by the Pages publish** (committed ≠ deployed). **Voice is a frozen phase-2** — SPEC §4/§7.7 stored-media carve-out, **not built**. **✅ V3.8 i18n + a11y + Settings landed 2026-06-26** (the closer over all surfaces): a declarative **`data-i18n-aria` walker** retiring the hand-rolled boot aria-labels; a **global `:focus-visible`** + **one consolidated `prefers-reduced-motion`** block (transitions + `:active` scale + scroll, replacing 3 scattered blocks); a hermetic **WCAG-AA contrast test** (`tests/test_dashboard_a11y_contrast.py` — pins `--muted`/`--amber`/`--on-accent`/`--blue` both themes); a **real switch-account** Google re-auth (`prompt:'select_account'`, identity = the live OAuth session never a label flip, D3) that **does not revoke** the prior token (revoke drops the shared grant → would sign you out on a same-account re-pick + force the other parent to re-consent); **D7** confirmed (no notif/bank/export markup ever built); the **token-alias endgame** (the 6 V3.1 back-compat aliases migrated + deleted, zero-ref audit clean; `--blue` kept as a theme-paired info token + given its dark value); and **cheap pure-function JS tests** (`parseDate`/`fmtISO`/`flagFor`/`bumpDate` via plain node, no npm/build step). **7-lens adversarial review → 9 confirmed/all fixed, 0 refuted** (the same-account-revoke major dissolved by dropping the revoke; + cancel-dangling state, a redundant focus ring, a missing dark-`--amber` assert, a TZ-fragile round-trip). SPEC §7.6 + DESIGN §2/§3/§8/§9 graduated; **468 tests green** — code-complete, **deploy-gated by the Pages publish**. Next: **V3.9** milestone review (`review.py`) + canon close + BACKLOG flip — the v3 lane's last slice.

See `ROADMAP.md` §2 for the ranked sequence and §3 for each lane's contract, acceptance bar, and open PO calls. **Killed stays killed:** anomaly/subscription detection.

## Frozen lanes 🧊

*Frozen = the script lives in `attic/`, unmaintained. Unfreeze = the stated condition holds AND v1 has been stable for 30 days.*

| Lane | Unfreeze condition |
|---|---|
| Pediatric milestones | the Health tab is actively maintained |
| Goal coaching | the Goals tab is updated weekly for a month (proves the habit) |
| PDF→event, receipt OCR, voice capture, Gmail bill parser, Maccabi forwarders | per-item PO request, one at a time |

**Killed** (not frozen — gone from the board): anomaly / subscription detection. A keyword categorizer, also once killed, returns only in bounded form as the on-box finance rules engine (M6.4).

=== End: BACKLOG.md ===

=== File: ENGINEERING.md ===
# Family Inc. — Engineering Handbook

*How the system is built, tested, deployed, and operated. v2.0 · 2026-06-17.*
*Contracts live in `SPEC.md`; this is the "how". If they disagree, `SPEC.md` wins and the disagreement is a bug.*

---

## 1. Repo layout

```
family-inc/
├── CLAUDE.md            # session context for Claude (thin; points here)
├── SPEC.md  ENGINEERING.md  DESIGN.md  BACKLOG.md
├── automation/
│   ├── lib/
│   │   ├── config.py    # env + constants; ALL non-secret constants live here
│   │   ├── sheet.py     # the only gspread client (retry, tab accessors, upsert)
│   │   ├── outbox.py    # the only path to a human (budget ledger, dedup, kinds)
│   │   ├── llm.py       # the only LLM wrapper (provider registry, cost log)
│   │   ├── apify.py     # the only Apify client (property secondary source)
│   │   ├── mailer.py    # the only smtplib import (email fallback)
│   │   ├── categorize.py       # on-box finance rules engine (M6.4)
│   │   ├── finance_budget.py   # budget-SUMIFS formula source of truth
│   │   ├── dates.py     # to_date / to_datetime / fmt_date — one implementation
│   │   └── money.py     # ILS formatting — one implementation
│   ├── reminders_engine.py
│   ├── daily_digest.py           # assembles ONE morning message, sends
│   ├── weekly_briefing.py        # Saturday narrative (template) + accuracy section
│   ├── whatsapp_summarizer.py
│   ├── accuracy_review.py        # weekly classifier accuracy pass
│   ├── property_scrape.py
│   ├── finance/scrape.js         # bank/card scraper (Node) → CSV
│   ├── finance_ingest.py         # CSV → lib/sheet
│   ├── finance_budget_formulas.py # live budget-SUMIFS installer
│   ├── templates.py              # message copy (reviewable against DESIGN.md)
│   ├── reply_handler.py          # parked, v1.1 (reply parsing)
│   ├── import_reminders.py       # one-shot M3 Reminders seeder
│   ├── hebcal_client.py
│   ├── review.py                 # milestone review tool
│   ├── session_kickoff.py        # regenerates NEXT_SESSION_PROMPT.md at session end
│   └── bridge/                   # Baileys listener + sender (Node)
│       ├── baileys_listener.js  package.json
│       └── state/               # gitignored: auth_state/, inbox/, outbox/, ledgers
├── dashboard/            # vanilla PWA (GitHub Pages serves this directory)
│   ├── index.html  app.js  styles.css  sw.js  manifest.webmanifest
│   ├── config.example.js         # committed; real config.js is gitignored
│   └── mock_data.json
├── deploy/
│   ├── systemd/          # *.service + *.timer units (source of truth for schedules)
│   ├── provision.sh      # idempotent VPS setup
│   ├── deploy.sh         # pull + test + restart (the only way code reaches the box)
│   ├── backup.sh         # tar bridge/state + logs → Drive via rclone
│   └── publish.sh        # public-repo history-rewrite kit
├── tests/                # pytest; fixtures/ holds golden files
├── reviews/              # milestone-review audit trail (tracked)
├── seeds/                # CSV seeds — personal values gitignored, README committed
├── Setup/                # live runbooks only (VPS, bridge pairing, OAuth, ICS)
├── Archive/              # superseded docs + the dated decision history — read-only
├── attic/                # frozen scripts — unmaintained, excluded from tests
└── logs/ Briefings/      # runtime output (gitignored except .gitkeep)
```

Boundary rules (convention, reviewer-checked — no CI enforces them yet): scripts never define a utility that belongs in `lib/` (no redefining `to_date`/`fmt_money`). Each external-site touch is the sole, named function in its own module — the bridge listener, finance `scrape.js`, `property_scrape.py`, `lib/apify.py`, and `hebcal_client.py` — never scattered ad-hoc. Nothing outside `lib/sheet.py` constructs a gspread client. Nothing outside `lib/llm.py` imports an LLM SDK. Nothing outside `lib/outbox.py` reaches a human.

## 2. Toolchain

| Layer | Choice | Notes |
|---|---|---|
| Python | 3.12 + **uv** | `uv sync --frozen` on the box; lockfile committed; appliance path is `uv run --frozen` |
| Key deps | gspread, google-auth, anthropic, pytest, requests | additions need a one-line justification in the commit body |
| Node | 22 LTS, plain npm | bridge + finance scraper only; `npm ci --omit=dev`; lockfiles committed. The `engines` floors are the real minimums (bridge ≥20.11, finance ≥22.13); `provision.sh` installs 22 LTS |
| Browser | per-lane Chromium | **Playwright Chromium** (property; ephemeral `uv run --with playwright`, headed under `xvfb-run`) + **Puppeteer Chromium** bundled by `israeli-bank-scrapers` (finance; daily headless). The one-time `--auth` device-trust login is headed under xvfb+x11vnc, persisting a per-provider profile under `/var/lib/family-inc/finance/profiles/`, mode 700 — but **x11vnc is NOT installed by `provision.sh`** (it installs xvfb+xauth only); the operator adds x11vnc when first using `--auth`. Low urgency while cards are deferred. No chromium apt package is installed; each lane pulls its own browser, kept out of the uv lockfile |
| Scheduling | **systemd timers** | journald logs, `OnFailure=` hooks, `Persistent=true` catches missed runs after reboots |
| Dashboard hosting | GitHub Pages via Actions serving `main:/dashboard` | static, zero backend; the workflow generates the gitignored `config.js` from Actions secrets |
| Secrets | `/etc/family-inc/` mode 600 | `service-account.json`, `env` (DeepSeek/Anthropic keys, SMTP, Apify token), `recipients.json`, `property_searches.json`, `bank_creds.json` |

## 3. Configuration

- `automation/lib/config.py` loads secrets from `/etc/family-inc/env`. **All non-secret constants — alert-budget cap, tombstone window, quiet hours, digest size, lead/recurrence thresholds, inbox retention, model ids — are defined directly in `config.py`.** There is no `config.toml`.
- **No constant may be defined in a script.** This rule exists because the alert-budget cap was once defined twice with independent ledgers — exactly the class of bug it prevents.
- Dashboard config: `config.example.js` committed with placeholders; real `config.js` (Sheet ID, OAuth client id) gitignored and generated at deploy.

## 4. Coding standards

- Python: type hints on public functions; dataclasses for Sheet rows; no bare `except:` — catch narrowly, log with context, and **decide**: degrade (LLM paths) or surface (data paths). Silent swallowing is the bug class that once hid the mock/real boundary for two weeks.
- Every script is also a library: `main()` guarded, pure logic importable for tests.
- Logging: stdlib `logging` to stderr (journald captures); one structured CSV per domain in `logs/` for the self-reporting briefing lines.
- JS (dashboard): single-file vanilla discipline; state lives in the one `state` object; every Sheet write goes through `applyWrites()` and conforms to the SPEC §6.1 write contract.
- Hebrew in code: string literals fine, identifiers English. Message copy lives in template constants (`templates.py`), not inline f-strings, so `DESIGN.md` can review it.

## 5. The appliance (VPS)

`deploy/provision.sh` is idempotent and run as root once:

1. Create user `familyinc` (no sudo); `timedatectl set-timezone Asia/Jerusalem`.
2. Install uv + Node 22; clone the repo to `/opt/family-inc`; `uv sync --frozen`; `npm ci --omit=dev` in `bridge/` and `finance/`; install xvfb+xauth (the Playwright browser and Puppeteer's Chromium are pulled per-lane, not by an apt package).
3. Copy `deploy/systemd/*` → `/etc/systemd/system/`; `systemctl enable --now` the bridge service + all timers + the love-note + tunnel services (V3.7; install `cloudflared` and place `CLOUDFLARED_TUNNEL_TOKEN` first).
4. Place secrets in `/etc/family-inc/` by hand (never scripted, never copied off the box).
5. Pair Baileys: `systemctl stop family-bridge && node bridge/baileys_listener.js` once, scan the QR, restart. `bridge/state/auth_state/` is in the weekly backup — **after a VPS rebuild, restore it before re-pairing**; a fresh QR scan is the fallback, not the default. (A Baileys *major*-version bump is the one case that requires wiping `auth_state/` and re-pairing.)

Units (schedules are code — change them via PR, not on the box):

| Unit | Schedule | Runs |
|---|---|---|
| `family-bridge.service` | always-on, `Restart=on-failure` | Baileys listener + outbox sender |
| `family-finance.timer` | ~06:00 daily | bank scrape → ingest (live on Mizrahi/debit since 2026-06-19; cards Max/Cal deferred) |
| `family-property.timer` | 07:10 + 19:10 | property scrape → Sheet + digest section |
| `family-reminders.timer` | 07:25 daily | reminders engine (computes, doesn't send) |
| `family-digest.timer` | 07:30 daily | daily digest assembly → outbox |
| `family-summarizer.timer` | hourly, 24h | classifier — runs at night so **criticals** can fire any hour; ordinary alerts are still held 22:00–07:00 by the outbox |
| `family-weekly.timer` | Sat 21:00 | weekly briefing + classifier-accuracy section |
| `family-backup.timer` | Sun 03:00 | tar `bridge/state` + `logs/` → Drive via rclone |
| `family-lovenote.service` | always-on, `Restart=on-failure` | love-note endpoint (V3.7, SPEC §7.7) — localhost HTTP, fronted by the tunnel |
| `family-lovenote-tunnel.service` | always-on, `Restart=on-failure` | Cloudflare Tunnel → the love-note endpoint (token-managed; ingress set in the Cloudflare dashboard) |
| `family-lovenote-sweep.timer` | hourly | expire love-notes past 24h (belt-and-suspenders behind the server's lazy read-expiry) |

All timers: `Persistent=true`; `OnFailure=family-fail-flag@%n.service` appends the failing unit to `logs/fail.flag`. The next **delivered** digest reports it (a Hebrew line prepended) and clears the file; a flag still present on Saturday means digests aren't landing, and the weekly briefing says so.

**The love-note endpoint is the box's FIRST inbound HTTP listener** (everything else is an outbound timer/sender). It binds `127.0.0.1:8787` only; the Cloudflare Tunnel is the sole public path, so there is no port-forward and no home-IP exposure. It reads `Settings.UserMap` (the live Sheet, service account) and needs `FAMILY_INC_LOVENOTE_ORIGIN` (the Pages origin, for CORS) + `CLOUDFLARED_TUNNEL_TOKEN` in `/etc/family-inc/env`; a blank origin keeps the feature inert. Unlike the timers, the server is long-running — a deploy that changes its code needs an explicit `systemctl restart family-lovenote` (add it to the `familyinc` sudoers whitelist alongside `family-bridge`), since no timer picks it up.

## 6. Deployment

`deploy/deploy.sh` on the box:

```
git pull --ff-only
uv sync --frozen && (cd automation/bridge && npm ci --omit=dev) && (cd automation/finance && npm ci --omit=dev)
FAMILY_INC_SHEET_ID= uv run --frozen pytest -q   # red tests abort the deploy; running code is untouched
sudo /usr/bin/systemctl restart family-bridge    # whitelisted sudoers line
# family-lovenote restarted too when installed (guarded; long-running, not a timer)
```

Timers pick up new code automatically on the next fire (they exec scripts from the repo); the two **long-running** services — `family-bridge` and `family-lovenote` (V3.7) — are the exception and `deploy.sh` restarts both (the love-note restart is guarded, so it no-ops until the unit is installed). **Committed is not deployed** — a placed secret or a merged feature is inert until `deploy.sh` pulls it; confirm the box is at origin HEAD before declaring anything live. The `familyinc` user has exactly two sudo capabilities (restart `family-bridge` / `family-lovenote`, both restart-only), so a compromised script can't escalate.

**Pre-merge CI:** `.github/workflows/tests.yml` runs the hermetic pytest suite — including the seed-safety guard, the repo-wide PII-leak guard (`tests/test_repo_pii_guard.py` + the shared patterns in `lib/pii.py`), and the dashboard `config.js` smoke — on every push + PR to `main`, so a red commit can't merge. It gates **merge**, not the box: `deploy.sh` still runs the same suite on the appliance as the safety net before restarting the bridge (no `deploy.sh` change — the guards are plain pytest, so they ride the existing run). The job has no path filter (the PII guard scans the whole tree, so a leaked value in docs or config trips it too) and installs Node 22 so the `@requires_node` syntax-check tests run rather than skip.

Dashboard deploys are `git push` (Pages rebuilds in ~30s); the PWA on both phones picks up on next open. `sw.js` cache-busts on a version bump in `config.example.js`, mirrored into `config.js`.

## 7. Testing policy

These suites exist and stay green:

| Suite | Covers |
|---|---|
| `test_engine.py` | fire-reason matrix (overdue/lead/due-today), tombstone skip window incl. future-skew, recurrence bumps incl. Feb-29 clamp + Custom flagging, send-success stamping, Last-Sent rerun idempotency |
| `test_outbox.py` | budget ledger: 2-cap, critical bypass, briefing exemption, shared-ledger across senders, (id,target) dedup, quiet-hours hold |
| `test_summarizer.py` | the 5 hard rules, per-group routing incl. `none`→NEEDS-A-LOOK, keyword fallback without a key, dispatch through the outbox, Sheet-tab persistence + rerun dedup, JSON-parse tolerance |
| `test_render_golden.py` | weekly briefing + daily digest rendered against `tests/fixtures/*.md` golden files (byte-exact; update goldens deliberately) |
| `test_sheet.py` | row-parsing tolerance, schema-drift guard both directions + flag heal, batched write path incl. formula survival, Settings/UserMap, upsert |
| `test_property.py` | card parse/normalize, BlockedError, empty result, seen-diff, Sheet-dedup, digest section, junk rejection |
| `test_apify.py` | adapter field maps, backup vs gap-fill, primary-wins merge, per-search/per-kind cost gate, fail-loud-only-on-zero-usable, token-inert |
| `test_finance.py` | mock CSV → ingest → mock Sheet, Txn-ID dedup/idempotency, fail-loud on missing creds, account upsert preserving human fields, column-order pin |

**Tests are hermetic.** An autouse fixture blanks `FAMILY_INC_SHEET_ID`, the LLM keys, and the SMTP creds, so the appliance's `deploy.sh` pytest can never reach the live Sheet, a real model, or actually send email. LLM calls are never made in tests — `lib/llm.py` has a fake injected via env. The dashboard has a manual smoke checklist in `DESIGN.md` §9 (no JS harness — boring tech; revisit if `app.js` exceeds ~2,000 lines).

## 8. Observability

- journald per unit (`journalctl -u family-reminders`).
- `logs/reminders_log.csv`, `logs/llm_costs.csv`, `logs/outbox_ledger/`, `logs/delivery_log.csv` (transport per send-run: baileys | smtp | queued-stale). The classifier's per-message record lives on the `WhatsApp_Inbox` Sheet tab, not in `logs/`.
- Self-reporting: the weekly briefing carries one system line — "7/7 runs green · 41 messages classified · 2 tombstone skips (max age 1.4h) · ₪6.10 LLM spend". Any fail-flag, schema-drift, or stale heartbeat replaces it with a warning. The humans never check logs unless the briefing tells them to.
- External uptime ping (healthchecks.io free tier) is an accepted gap — a hard VPS-down is currently silent; listed v1.1.

**"No digest by 08:00" runbook** (the most likely 24h failure is a logged-out WhatsApp session on a healthy VPS):

1. Check email — if the digest arrived there, the bridge is down but the system is fine: SSH in, re-pair the QR (restore `auth_state/` first if post-rebuild).
2. No email either → the VPS is down: reboot from the provider console; `Persistent=true` timers fire the missed runs on boot.
3. Repeated same-week logouts → treat as a ban signal; invoke the `SPEC.md` §10 fallback decision.

## 9. Git & repo conventions

- `main` is deployable; small focused commits; imperative subjects; the body explains *why* when non-obvious.
- Sessions `git pull --ff-only` before any work (origin is the sync point between agents) and commit at session end (the leader pushes; Pages + `deploy.sh` consume `main`). Git operations run on the PO's machine, never in a sandbox.
- No long-lived branches — this is a two-committer repo (Adar + Claude-in-session).
- The Sheet schema only ever gains columns (additive, backwards-compatible); old rows without M/N/O are treated as never-tombstoned. Rollback at any point = `git revert` + redeploy.
- Tags: `v1-live` at acceptance, then `vX.Y` per milestone.

## 10. Review ritual

Reviews fire on **milestones**, not every session: a new spec, an architecture change, anything touching delivery/budget/privacy guarantees, and each milestone close. Mechanism: `automation/review.py` builds the prompt + attachment list; the reviewer is the best available external model (DeepSeek default; substitutions logged). A keyless local fallback is available via `--provider ollama` (₪0/run, on-box privacy). Findings are resolved in-session as Apply / Defend / Open, and any directional outcome is recorded. Tiny edits never trigger a review. On a milestone-closing session the gate runs **blocking inside the handoff chain** (`… && review gate && git commit && git push`) — a MAJOR finding stops the commit until resolved or explicitly overridden by the PO. A failed or truncated review never blocks a milestone: log it, proceed, note it in `BACKLOG.md`.

## 11. Definition of done (any work item)

Code merged with tests for its logic · constants in config · errors either degrade or surface (no silent paths) · contracts updated in `SPEC.md`/`DESIGN.md` if changed · `BACKLOG.md` status flipped · deployed and observed green once on the appliance.

=== End: ENGINEERING.md ===

=== File: DESIGN.md ===
# Family Inc. — Design Specification

*The product has two surfaces: WhatsApp messages and the dashboard PWA. Both are designed here. v3.1 · 2026-06-20. The single offline model is queue + tombstone everywhere.*

---

## 1. Design principles

1. **Calm tech.** The system reports what happened and what's next; it never scolds, streaks, paces, or counts what you missed. Quiet days are a success state, not an empty state.
2. **The message is the product.** Most days the family touches Family Inc. only through WhatsApp. Message copy gets the same design rigor as pixels.
3. **Dense, then disclosed.** Today shows every domain at a glance; detail hides behind one tap. Linear/Notion density, not wellness-app whitespace.
4. **Partner-symmetric surfaces.** Attribution without scoring: domain leads, names follow. No passive "recently completed" surface either — even a neutral one risks reading as a scoreboard between partners.
5. **Honest affordances.** Nothing on either surface suggests an action the system can't take (no reply commands until reply parsing ships; no disabled-looking-but-tappable buttons).
6. **Hebrew-first, RTL-first.** English is the fallback, not the default. LTR runs (numbers, URLs) wrapped in `<bdi>`.

## 2. Visual system (dashboard)

### Color — cool grey + blue *(v3 retone, shipped V3.1 2026-06-25; token names match `styles.css` canon)*

| Token | Light | Dark (provisional) | Use |
|---|---|---|---|
| `--bg` | `#EBEEF2` | `#14161B` | page |
| `--tile` | `#FFFFFF` | `#1C2027` | card / sheet surface |
| `--ink` | `#12151C` | `#E7E9ED` | text |
| `--muted` | `#5F6878` | `#A1AAB8` | secondary text (AA-cleared) |
| `--line` | `#E1E5EB` | `#2A2E36` | hairlines |
| `--accent` | `#2C57C8` | `#6E8BE8` | links, active tab — single brand color |
| `--green` | `#2F8559` | `#4CA877` | all-clear, success |
| `--amber` | `#8A5E12` | `#C79A4A` | due-today (darkened to clear AA) |
| `--red` | `#C4403B` | `#DB6B63` | overdue |
| `--blue` | `#4A6FA5` | `#82A9D9` | info — calendar event times (`.cal-time`) |

Semantic colors appear only on status; the accent is the single brand color. No gradients. Semantic washes are `color-mix` off these tokens so they track the palette. Dark mode is **provisional** (its own pass later). The V3.1 back-compat aliases (`--card`/`--border`/`--ink-dim`/`--orange`/`--yellow`/`--radius`) were **retired in V3.8** — every selector now uses the canonical token (a zero-ref audit confirmed none remained); `--blue` stays as a real info token, theme-paired in every block (V3.8 gave it its dark value). `--rad 20px` (cards/sheets), `--rad-sm 8px` (inputs), 999px pills; card shadow `0 1px 2px/0 8px 22px`, bottom-sheet `--sheet-shadow`.

### Type

- **Heebo** — Hebrew UI (default chrome).
- **Inter** — Latin UI (fallback chrome); tabular figures on.
- **IBM Plex Mono** — **all numerals** (money `₪4,280`, dates, counts, times, %) so figures read as data at a glance, via the `.num` utility + `<time>` (loose count/% spans get tagged as later slices render them).
- Scale: 17/15/13 body-secondary-caption; one display size (28) for drawer KPIs. No font weight above 600.

### Components

- **3-tier status pill** (Today view, sticky; *v3, V3.2 — replaced the old status banner + plain pill*): a single signal, always visible (clear is a resting state, never hidden). Tier by priority `overdue` (red) > `today` (amber) > `clear` (sage), rendered as a decorative glyph + a **mono count** + a **text label** (`{n}` `overdue` / `{n}` `due today` / `Nothing urgent` / `Sunday briefing ready` on Sundays) — never color-only: the count + label carry the meaning. A `loading` tier holds first paint so it never reads as a premature "all clear". One signal at a time — our budget-friendly stand-in for OS-level notifications.
- **3-day calendar strip** (Today view; *v3, V3.4*): a horizontal scroll-snap strip of exactly three day-panes (today/+1/+2), each a day-head (today/tomorrow/weekday + date) over its `Calendar-Events`. **Read-only** — a glance surface, no tap/write affordance; events are edited at their source. An empty day shows a short line so the strip never collapses (stable snap geometry). RTL "just works" off `dir=rtl` + logical props. Days 3–7 live in the coming-up strip, so this stays today+2 with no overlap. The 🕯 Shabbat line (the `source==='shabbat'` seam) carries a glyph + a non-color inline-start border, never hue alone.
- **Select-to-act desk** (Today; *v3, V3.3 — replaced the tap-to-expand reminder row*): the OVERDUE/FIRE-TODAY reminders as **checkbox** rows (flag dot · title · due phrase; keyboard-operable; selection is never color-only — a ✓ box + wash + `aria-checked`). Selecting ≥1 reveals a **sticky batch bar** (`✓ done` · `+ snooze` · `+ note`) that fans the whole selection out to **one** Sheet write. **Snooze is absolute**: chips (tomorrow · +3 · 1 week · 2 weeks · 1 month) + a date picker resolve to an absolute Due date (so an overdue row snoozed forward clears OVERDUE); the note is an inline composer appended to each selected row's Notes.
- **Coming-up strip** (Today; *v3, V3.3 — replaced "Next 7 days"*): a **read-only** ±30-day horizontal scroll band with a **now**-marker. Date-sorted: WEEK-OUT/MONTH-OUT reminders + calendar events; the past side carries past calendar events (overdue reminders stay on the desk), the future side what's coming. today/+1/+2 events stay in the 3-day calendar strip (no double-render). Opens positioned at "now"; scroll back for the past, forward for what's ahead.
- **Portfolio tiles + one bottom-sheet** (Today; *v3, V3.5 — replaced the accordions*): a grid of domain **tiles** (Money hero = an overall-% donut + category bar + 7-day sparkline · Timeline = count of upcoming milestones · Health = initials-avatars with non-color urgency · Goals = a % bar · Car · Contracts) — each a `<button>` that opens **one** shared, data-driven **bottom-sheet** (`role=dialog`/`aria-modal`; Esc / scrim / close dismiss; focus-trapped + scroll-locked; focus returns to the launching tile; reduced-motion honored). Never six panels. Status is never color-only (text + glyph). Education has **no** Today tile (its data folds into the Timeline). The **Timeline** tile (*v3, V3.6*) opens a read-only **cross-domain timeline** — every dated row across all domains flattened onto one vertical, date-sorted axis with a now-marker, an exponential 1wk→5yr zoom (default 3mo), and a category-chip filter (`finance · health · car · education · goals · contracts · calendar · other`); items are edited at their source tab, never here.
- **Bright-line goal viz**: target line + actual line + safety band (ahead/on-pace/behind) for multi-year goals — progress bars are banned for anything >90 days. The Goals **tile** shows a simple % bar; the bright-line lives in the Goals **bottom-sheet** (D8).
- **Stale-data badge**: shown only when a live load fails and a cache exists — `לא מקוון — נתונים מ-{when}`. There is no positive "live" indicator; the pending-write count lives in Settings → queue inspector.

## 3. Information architecture (Today-first)

```
Today (home)
├── Header: Family inc. · date
├── 3-tier status pill (sticky) — overdue (red) / today (amber) / clear (sage); loading tier on first paint
├── LOVE-NOTE (V3.7) — a parent-to-parent ephemeral note (💌): an inbound card (hidden when none) above a small composer (write/replace/clear); appliance-backed, NOT the Sheet; the whole slot is hidden unless configured + signed in
├── CALENDAR — a 3-day scroll-snap strip (today/+1/+2), read-only; 🕯 marks the Shabbat line
├── DESK (select-to-act) — reminders where Auto-flag ∈ {OVERDUE, FIRE TODAY}; multi-select → one batch (done / absolute-snooze / note)
├── COMING UP — a read-only ±30-day scroll band (now-marker): week/month-out reminders + calendar events (today/+1/+2 stay in the calendar strip); scroll back for past events
└── PORTFOLIOS — domain tiles (Money · Timeline · Health · Goals · Car · Contracts) → one shared bottom-sheet; the Timeline tile opens a read-only cross-domain chronology (1wk→5yr zoom + category filter); Education folds in here (no separate tile)
Sunday tab — a live week-ahead view computed from the Sheet (week ahead · reminders this week · overdue · Money · Goals · data hygiene), NOT the rendered weekly-briefing markdown
Settings tab — account (switch-account = a real Google re-auth · sign-out · force-refresh) · language toggle · theme · Sheet ID · demo toggle · queue inspector (pending-write count); no notification-toggle / bank-connect / export controls (D7)
```

Today-first wins the 8 AM glance; tiles demote to drawers; the Sunday week-ahead gets a tab, not the home.

## 4. States

- **Loading**: the status pill shows its neutral `loading` tier (`Loading…`) while the first `batchGet` is in flight — never a premature "all clear"; header/tabs are real from t=0; lists render once data arrives (cached snapshot first if present, then live). No skeleton or shimmer.
- **Quiet day**: the status pill shows the sage `clear` tier (`Nothing urgent`, or `Sunday briefing ready` on Sundays) and TODAY renders "(nothing urgent)". The screen is never blank.
- **Offline**: a one-shot toast confirms each queued write; the stale-data badge shows if the view was served from cache; rows keep working and re-render optimistically (the pending-write count is in Settings). **Buttons never disable offline.**
- **Write failure (online)**: optimistic UI rolls back; inline "Couldn't save — retry?"; token expiry → silent refresh once, then a re-sign-in banner.
- **Back from vacation (30 overdue)**: top 10 by due date + "+20 more" expander; bulk-done multi-select via the V3.3 select-to-act desk, with zero commentary.

## 5. Interaction contract (write-back)

Every action maps to one batched Sheet write per SPEC §6.1 (intent columns + `DoneAt`/`LastDoneBy` on completion + `WriteQueue_Tombstone` always); the select-to-act desk (V3.3) fans a multi-row selection into a **single** batch:

| Action | Writes | UI |
|---|---|---|
| ✓ done | Status=Done, DoneAt, LastDoneBy, Tombstone (+ recurrence bump) | row clears from the desk |
| snooze | Due = an **absolute** date (today + offset, or a picked day), Status=Snoozed, Tombstone (no DoneAt — snooze isn't completion) | row leaves the desk once future (OVERDUE cleared) |
| note | append to Notes with `[date name]` prefix, Tombstone | inline confirm |

Offline: the same writes queue (`localStorage.pendingWrites[]`, cap 50 with a one-shot loss warning at the cap); flush in tap order on reconnect; idempotent via tombstone (re-stamped at flush time).

## 6. WhatsApp message design system

The most-used UI in the product. Rules:

- **One morning message.** Engine fires, group digest, new-property listings, and the Hebcal line are assembled into a single 07:30 message per recipient — never 2–3 separate sends.
- **Both adults, every day.** Each adult gets their own 07:30 message every day — partner-symmetric. An adult with no reminders of their own still receives the briefing: the quiet-day line `אין תזכורות להיום — יום שקט.` followed by whatever shared groups / property sections exist. A truly empty day is just the head + quiet-day line — never *no* message (silence must stay distinguishable from a broken digest) and never a scold (quiet is a success state).
- **Line economy.** One line per item: flag emoji · title · due phrase. Notes only if ≤120 chars. >5 items → top 5 by priority + "+N more — בלוח" (in the dashboard).
- **Emoji are semantics, not decoration**: 🔴 overdue · 🟠 today · 🟡 week-out · 🟢 month-out · ⚠ needs-a-look · 🕯 Shabbat line · 🏠 new listings. No other emoji in generated copy.
- **Budget-deferred carry-over.** Alerts the 2/day budget defers ride the *next* morning's digest under a `נשמרו מאתמול (מכסת הודעות):` section — surfaced, never dropped (copy pending Shanee review).
- **No reply affordances** until reply parsing ships. Messages end with content, not instructions. When v1.1 lands, the reply grammar returns as a single footer line.
- **Hebrew copy register**: short, warm, zero exclamation marks, no imperatives toward a person ("לקבוע תור" not "תקבעי תור!"). Dates as "יום ג׳ 17/6". Money as ₪ with a thousands separator.
- **Attribution**: domain first, name inline.

### Templates

Daily digest (the only routine alert-channel message):

```
🏠 Family inc. · יום ו׳ 12/6
🔴 טסט שנתי לרכב — באיחור 3 ימים
🟠 תור שיניים לילד — היום
🟡 ביטוח דירה — בעוד 6 ימים

קבוצות (24ש׳):
גן — מחר יום פרי, להביא 🍐 (גננת, 22:14)
ועד — מעלית מושבתת חמישי 09:00–12:00

🏠 דירות חדשות:
4 חד׳ · ₪2,450,000 · רמת גן

🕯 הדלקת נרות 19:24 · צאת שבת 20:35
```

Quiet day for this adult (no reminders of their own; shared sections still ride along):

```
🏠 Family inc. · יום ג׳ 17/6
אין תזכורות להיום — יום שקט.

קבוצות (24ש׳):
ועד — מעלית מושבתת חמישי 09:00–12:00
```

Critical (budget-bypassing, rare): a single line, no frame — `⚠ {group}: {one_liner} ({sender}, {time})`.

Weekly briefing (Sat 21:00): **deterministic flat sections** — week ahead · reminders firing this week · overdue · Money · Goals · data hygiene · system self-report · classifier accuracy — vertical, one line per item, the typography carrying the design. **Rendered from a deterministic template, no LLM call.** *(The "five-scene narrative" opener — the week's spend · a kids' moment · next week's three things · a goal line · a contract heads-up, Strava-year-in-review meets Morning Brew — is a deferred v1.1 LLM lane (`ROADMAP.md` §ai-briefing) with this template as its fallback, not the current output.)*

Bridge-health warning prepends, never replaces: `⚠ הגשר שקט 14 שעות — ייתכן שפספסנו הודעות`.

## 7. i18n rules

- `<html lang="he" dir="rtl">` default; `localStorage.familyinc.lang="en"` flips lang/dir + chrome strings (pre-paint, no flash).
- Logical CSS properties only (`padding-inline-start`); no left/right literals.
- Chrome strings in the parallel STRINGS table; data values (merchants, group names, guide links) render Hebrew regardless of the toggle.
- Dates `DD/MM`, week starts Sunday, `he-IL` number formatting in both languages (the audience is Israeli in either chrome).
- The brand stays Latin "Family inc." everywhere, including the home-screen title.
- WhatsApp messages are Hebrew-only (no toggle exists there; the recipients are known).

## 8. Accessibility & ergonomics

Tap targets ≥44px. Contrast clears **AA on both surfaces**, pinned by a hermetic test (`tests/test_dashboard_a11y_contrast.py`) over the deliberately-engineered tokens — `--muted`/`--amber` darkened to clear AA, `--on-accent` paired per theme, `--blue` given a dark value (V3.8) — so a future retone can't silently regress them ("assert, don't re-pick"). A **global `:focus-visible`** outline (`:where(a, button, input, select, textarea, [tabindex])`) covers every interactive element; a single **`prefers-reduced-motion`** block neutralizes transitions, the `:active` scale, and scroll animation. Icon-only / unlabelled controls are named in **both languages** declaratively via the `data-i18n-aria` walker (applied at boot from STRINGS). The PWA `apple-touch-icon` relies on the OS glass treatment, no fake translucency in-app; thumb-zone — action pills render below the row, not above.

## 9. Manual smoke checklist (per dashboard deploy)

1. Cold load <1s on phone over LTE; the `Loading…` pill gives way to live lists without layout shift.
2. Hebrew default renders RTL with no mirrored numerals; the toggle flips chrome only.
3. Mark done online → row clears, the Sheet shows M/N/O stamped.
4. Airplane mode → tap done → a queued toast shows → reconnect → flush; the engine log shows a tombstone skip if within the window.
5. The demo toggle never touches the live Sheet.
6. Lighthouse PWA installable; an offline reload serves the shell + cached data.
7. Offline, tap until the queue hits 50 → a one-shot "queue full" warning shows; further taps don't grow the queue; reconnect → flush re-arms the warning.
8. (bridge) A 1:1 message to the bridge number from a known sender is logged to `replies.jsonl` but gets **no reply/ack** (reply-parsing is v1.1, SPEC §7.4); an unknown 1:1 sender is dropped.
9. (V3.1 retone) Cold load shows the cool palette (`--bg #EBEEF2`, `--accent #2C57C8`) and IBM Plex Mono numerals with no Geist FOUC; amber/muted text clears AA on both surfaces; Sunday + Settings inherit the palette with no layout shift; the longest `₪` amount + the drawer KPI row don't wrap under the new mono metrics.
10. (V3.2 pill) The Today status pill shows exactly one tier by priority — red `overdue` + mono count when any overdue, else amber `due today` + count, else sage `Nothing urgent` (or `Sunday briefing ready` on Sundays); first paint shows the neutral `loading` tier (never a premature "all clear"); the tier reads from the count + label, not color alone; the pill is always visible (clear is a resting state) and resolves with no layout shift.
11. (V3.4 calendar) The calendar slot is a 3-day strip of exactly three panes (today/+1/+2) that horizontally **snaps** — verify the snap direction on **iOS** specifically, RTL: today is the right-most pane and snap advances right-to-left, the next pane peeking. Each pane has a day-head (today/tomorrow/weekday + mono date); an empty day shows a short line and does **not** collapse the strip or shift layout. Times render in IBM Plex Mono. A Shabbat line (🕯 + a non-color inline-start border) is distinguishable without color; the cards are read-only (no done/snooze/note affordance). EN fallback flips the day-heads; reduced-motion neutralizes scroll animation.
12. (V3.5 portfolios) The domains render as a tile grid (Money hero + Health/Goals/Car/Contracts), each a `<button>`; tapping one opens **one** shared bottom-sheet for that domain with the full detail (Goals shows the bright-line **in the sheet**, a % bar on the tile [D8]). The sheet traps focus, locks page scroll, dismisses on Esc / scrim / close, and **returns focus to the tile**; reduced-motion disables the slide. Urgency is never color-only (donut %, avatar glyph + day-count, "N over ▲"). No Education tile (folds into the Timeline). RTL default + EN fallback; every new STRINGS key he+en.
13. (V3.6 timeline) The **Timeline** tile (second, after the Money hero) opens the shared bottom-sheet onto a read-only cross-domain chronology: a vertical, date-sorted list with a **now**-marker dividing the recent-past tail from the future. The zoom rungs (1wk/1mo/3mo/1yr/5yr, default 3mo) widen the window; the category chips (all · finance · health · car · education · goals · contracts · calendar · other) filter in place — both update **only** the track + the `aria-pressed` flags, keeping the pressed control's focus (no full-body rebuild). Urgency is never color-only (🔴/⚠/· glyph + due phrase, redundant border). Done/skipped/archived reminders and undated rows never appear; an unmapped reminder Domain still shows under `other`. RTL default + EN fallback; every new STRINGS key he+en.
14. (V3.7 love-note) With `LOVENOTE_URL` configured: signed in as one adult, send a note → the **other** adult sees it as an inbound card (💌 + "from {name}" + text, never color-only) on their **next open**, with **no push**. A second send **replaces** (one note per direction); the sender's "waiting for {name}" + **Clear** removes only their own note; a note older than **24h** is gone (lazy on read + the hourly sweep). The sender gets no "seen" signal. With `LOVENOTE_URL` blank, the whole slot is **absent** (no dead affordance). DEMO_MODE shows the fixture card + a `(demo)` composer. RTL default + EN fallback; every new STRINGS key he+en.
15. (Lane C col-D) Snooze/complete a reminder, reload (incl. **airplane-mode** flush, item 4): the bumped/snoozed Due date **round-trips** — the row keeps its correct day and an overdue row snoozed to a future date leaves OVERDUE (the dashboard reads back col-D whether the Sheet renders it ISO or he-IL DD/MM·DD.MM). Rename/remove a Reminders write column in the Sheet → on next load the dashboard toasts **"writes paused"** and the done/snooze/note taps no-op (no position-write to the wrong column) until the header is restored.
16. (V3.3 desk) The TODAY desk is **select-to-act**: each overdue/fire-today reminder is a checkbox row (tap or Space/Enter toggles; selection is never color-only — a ✓ box + wash + `aria-checked`); no inline expand. Selecting ≥1 reveals the **sticky batch bar** with the live count; tapping ✓ done marks **all** selected rows in one write (recurring rows recurrence-bump), they clear the desk, and the selection + bar reset. The selection also clears on a background reload (no stale `_row`).
17. (V3.3 absolute snooze) On the desk, select a row → `+ snooze` → the chips (tomorrow · +3 · 1 week · 2 weeks · 1 month) **and** the date picker each write an **absolute** Due date. An **OVERDUE** row snoozed to any future date leaves the desk (OVERDUE cleared — the D4 fix); snoozing to tomorrow keeps it as today/fire-today. The picker won't offer past dates (min = today). One snooze over a multi-selection writes all rows in one batch.
18. (V3.3 coming-up) The coming-up slot is a **read-only** ±30-day horizontal scroll band with a **now**-marker; it opens positioned at "now". Scroll **back** shows past calendar events (overdue reminders are **not** repeated here — they live on the desk); scroll **forward** shows week/month-out reminders + upcoming events. today/+1/+2 events appear only in the 3-day calendar strip (no double-render). Verify the RTL scroll direction on **iOS** specifically; chips carry no done/snooze affordance. EN fallback flips copy; every new STRINGS key he+en.
19. (V3.8 i18n + a11y + Settings) **Keyboard-tab** the Today surface: every interactive element shows a visible **`:focus-visible`** ring; tab into the desk rows, the coming-up region, the snooze chips/date-picker, the portfolio tiles, the bottom-sheet (focus stays trapped). With a **screen reader / EN toggle**, the icon-only controls are **named in the active language** (sheet close ✕, coming-up region, snooze date-picker, note field) — flip he↔en and the names flip. With **reduce-motion** on, no transition/scale/scroll animation fires. **Settings → Switch account** opens the Google **account chooser**: pick the *other* parent → the dashboard reloads as them and a new `LastDoneBy` writes their name; **cancel** the chooser → nothing changes (current session intact); re-picking the **same** account does **not** sign you out. Settings shows **no** notif/bank-connect/export controls. Contrast holds AA on both surfaces (the `test_dashboard_a11y_contrast` floor); every new STRINGS key is he+en.

=== End: DESIGN.md ===

=== File: dashboard/index.html ===
<!doctype html>
<!--
  Chrome language: Hebrew default with English fallback toggle in Settings.
  Boot script reads localStorage.lang ("he" | "en") and rewrites lang + dir
  before first paint. Default is "he" / "rtl"; ASCII source below stays in
  English for legibility — the chrome string set lives in app.js.
-->
<html lang="he" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>Family inc.</title>
  <!--
    Description is read at PWA install time and cached by iOS; client-side
    i18n can't reach it post-install. Kept as the language-neutral brand so
    the Hebrew/English toggle isn't contradicted by the home-screen string.
  -->
  <meta name="description" content="Family inc." />
  <meta name="theme-color" content="#2C57C8" />

  <!-- iOS PWA -->
  <meta name="apple-mobile-web-app-capable" content="yes" />
  <meta name="apple-mobile-web-app-status-bar-style" content="default" />
  <meta name="apple-mobile-web-app-title" content="Family inc." />
  <!-- iOS 26 auto-applies the Liquid Glass treatment to this icon. -->
  <link rel="apple-touch-icon" href="icon-180.png" />

  <link rel="manifest" href="manifest.webmanifest" />
  <link rel="icon" type="image/svg+xml" href="icon.svg" />

  <!-- Google Fonts: Inter (UI), Heebo (Hebrew fallback), IBM Plex Mono (all numerals) -->
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Heebo:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" />

  <link rel="stylesheet" href="styles.css" />
  <!-- Pre-paint lang/dir + theme application from user preference (default: he/rtl, auto theme) -->
  <script>
    (function () {
      try {
        var saved = localStorage.getItem('familyinc.lang');
        if (saved === 'en') {
          document.documentElement.setAttribute('lang', 'en');
          document.documentElement.setAttribute('dir', 'ltr');
        }
        var theme = localStorage.getItem('familyinc.theme');
        if (theme === 'light' || theme === 'dark') {
          document.documentElement.setAttribute('data-theme', theme);
        }
      } catch (_) { /* localStorage blocked — keep he/rtl + auto theme defaults */ }
    })();
  </script>
</head>
<body>
  <!-- Sign-in screen (shown when not authenticated and not in demo mode) -->
  <div id="signin-screen" class="signin" hidden>
    <div style="font-size: 48px">🏠</div>
    <h2>Family inc.</h2>
    <p data-i18n-html="signin.prompt">Sign in with the Google account that has access to your <code>Family_OS</code> sheet.</p>
    <button class="signin-btn" id="signin-btn" data-i18n="signin.button">Sign in with Google</button>
    <p style="margin-top:24px;font-size:12px" data-i18n-html="signin.demoLine">
      Or <a href="#" id="demo-link">try with demo data</a>.
    </p>
  </div>

  <!-- App shell -->
  <div id="app" hidden>
    <header class="app-header">
      <h1>🏠 Family inc.</h1>
      <div class="date" id="header-date"></div>
    </header>

    <div id="stale-badge" class="stale-badge" hidden></div>

    <!-- TODAY view — V3.2 scaffold. Vertical order is the signed v3 IA
         (V3_RECONCILE): pill · love-note · calendar · desk · coming-up ·
         portfolios. Each slot below wraps its LEGACY render target so the
         existing renderers stay green this slice; V3.3–V3.7 swap the innards
         slot-by-slot. -->
    <section class="view active" id="view-today">
      <!-- 3-tier status pill (replaces the old pill + the status banner). Starts
           in the loading tier so it never reads as a premature "all clear";
           renderStatusPill sets data-tier + glyph/count/label once data lands.
           Tier is conveyed by color + count + label (never color-only). -->
      <div id="status-pill" class="status-pill" data-tier="loading" role="status" aria-live="polite">
        <span class="pill-glyph" id="status-pill-glyph" aria-hidden="true"></span>
        <span class="pill-count num" id="status-pill-count" hidden></span>
        <span class="pill-label" id="status-pill-text" data-i18n="state.loading">Loading…</span>
      </div>

      <!-- Love-note slot (V3.7) — a parent-to-parent ephemeral note. renderLoveNote
           fills it: an inbound card (the note your partner left, hidden when none)
           above a small composer (write/replace/clear your own note). Stays hidden
           entirely unless the feature is configured (cfg.LOVENOTE_URL) + signed in,
           so it never promises a dead affordance (SPEC §3). The note shows on the
           recipient's next open — no push, no "seen" signal (SPEC §3.7). -->
      <div id="love-note-slot" hidden></div>

      <!-- Calendar slot (V3.4) — a 3-day scroll-snap strip (today/+1/+2),
           read-only. render3DayCalendar fills #today-cal-strip with exactly 3
           panes; days 3–7 live in the coming-up strip below. -->
      <div id="calendar-slot" class="section">
        <h2 data-i18n="section.calendar">Calendar</h2>
        <div id="today-cal-strip" class="cal-strip"></div>
      </div>

      <!-- Desk slot (V3.3) — a select-to-act list: each OVERDUE/FIRE-TODAY reminder
           is a checkbox-semantics row; selecting ≥1 reveals the sticky batch bar
           (done / snooze / note) that fans out to ONE applyWrites batch. -->
      <div id="desk" class="section">
        <h2 data-i18n="section.todayList">Today</h2>
        <div id="today-list" role="group"></div>
        <!-- Sticky batch action bar — hidden until ≥1 row is selected. The snooze
             chips resolve to ABSOLUTE Due dates (an overdue row snoozed forward
             clears OVERDUE — the D4 fix); the note row is an inline composer. -->
        <div id="desk-actionbar" class="desk-actionbar" hidden>
          <div class="desk-actionbar-main">
            <span class="desk-sel-count num" id="desk-sel-count" role="status" aria-live="polite"></span>
            <div class="desk-actionbar-btns">
              <button class="action-btn primary" type="button" data-batch="done" data-i18n="row.done">✓ done</button>
              <button class="action-btn" type="button" data-batch="snooze" data-i18n="row.snooze">+ snooze</button>
              <button class="action-btn" type="button" data-batch="note" data-i18n="row.note">+ note</button>
            </div>
          </div>
          <div class="desk-snooze-row" id="desk-snooze-row" hidden role="group" data-i18n-aria="snooze.label" aria-label="Snooze to…">
            <button class="snooze-chip" type="button" data-snooze-days="1" data-i18n="snooze.tomorrow">Tomorrow</button>
            <button class="snooze-chip" type="button" data-snooze-days="3" data-i18n="snooze.in3">+3d</button>
            <button class="snooze-chip" type="button" data-snooze-days="7" data-i18n="snooze.week">1 week</button>
            <button class="snooze-chip" type="button" data-snooze-days="14" data-i18n="snooze.twoweeks">2 weeks</button>
            <button class="snooze-chip" type="button" data-snooze-days="30" data-i18n="snooze.month">1 month</button>
            <input type="date" id="desk-snooze-date" class="snooze-date" data-i18n-aria="snooze.pickDate" aria-label="Pick a date" />
          </div>
          <div class="desk-note-row" id="desk-note-row" hidden>
            <textarea id="desk-note-input" rows="2" maxlength="500" data-i18n-placeholder="desk.notePlaceholder" data-i18n-aria="desk.notePlaceholder" placeholder="Write a note…" aria-label="Write a note…"></textarea>
            <button class="action-btn primary" type="button" id="desk-note-send" data-i18n="lovenote.send">Send</button>
          </div>
        </div>
      </div>

      <!-- Coming-up slot (V3.3) — a read-only ±30-day horizontal scroll band with a
           now-marker: scroll back for past calendar events, forward for week/month-
           out reminders + upcoming events. today/+1/+2 events stay in the 3-day strip. -->
      <div id="coming-up" class="section">
        <h2 data-i18n="section.comingUp">Coming up</h2>
        <div id="coming-up-strip" class="coming-up-strip" tabindex="0" role="group" data-i18n-aria="section.comingUp" aria-label="Coming up"></div>
      </div>

      <!-- Portfolios slot (V3.5) — a grid of domain TILES that open one shared,
           data-driven bottom-sheet on tap (renderPortfolios builds the faces,
           buildSheet the sheet body). Education has no Today tile (its data folds
           into the V3.6 timeline); Timeline's tile lands with its sheet in V3.6. -->
      <div id="portfolios" class="section">
        <h2 data-i18n="section.domains">Domains</h2>
        <div id="portfolio-grid" class="portfolio-grid"></div>
      </div>
    </section>

    <!-- SUNDAY view -->
    <section class="view sunday" id="view-sunday">
      <h2 class="briefing-title" data-i18n="sunday.title">Sunday Briefing</h2>
      <div class="week" id="sunday-week"></div>

      <div class="sub" data-i18n="sunday.weekAhead">Week ahead</div>
      <div id="sunday-week-ahead"></div>

      <div class="sub" data-i18n="sunday.remindersThisWeek">Reminders firing this week</div>
      <div id="sunday-reminders"></div>

      <div class="sub" data-i18n="sunday.overdue">Overdue</div>
      <div id="sunday-overdue"></div>

      <div class="sub" data-i18n="sunday.money">Money</div>
      <div id="sunday-money"></div>

      <div class="sub" data-i18n="sunday.goals">Goals</div>
      <div id="sunday-goals"></div>

      <div class="sub" data-i18n="sunday.hygiene">Data hygiene</div>
      <div id="sunday-hygiene"></div>
    </section>

    <!-- SETTINGS view -->
    <section class="view settings" id="view-settings">
      <div class="section">
        <h2 data-i18n="settings.account">Account</h2>
        <div class="row">
          <div id="settings-account" data-i18n="state.loading">Loading…</div>
          <div class="actions" style="display:flex">
            <!-- D3: a real Google account switch (sign-out → re-auth with the account
                 chooser), never a label flip — keeps col-M LastDoneBy = the parent
                 actually signed in (SPEC §7.6). No notif / bank-connect / export
                 controls live here (D7). -->
            <button class="action-btn" id="switch-account-btn" data-i18n="settings.switchAccount">Switch account</button>
            <button class="action-btn" id="signout-btn" data-i18n="settings.signOut">Sign out</button>
            <button class="action-btn" id="refresh-btn" data-i18n="settings.forceRefresh">Force refresh</button>
          </div>
        </div>
      </div>
      <div class="section">
        <h2 data-i18n="settings.language">Language</h2>
        <div class="row">
          <div class="actions" style="display:flex">
            <button class="action-btn" data-lang="he" data-i18n="settings.langHebrew">עברית</button>
            <button class="action-btn" data-lang="en" data-i18n="settings.langEnglish">English</button>
          </div>
        </div>
      </div>
      <div class="section">
        <h2 data-i18n="settings.appearance">Appearance</h2>
        <div class="row">
          <div class="actions" style="display:flex">
            <button class="action-btn" data-theme="light" data-i18n="settings.themeLight">☀️ Light</button>
            <button class="action-btn" data-theme="dark" data-i18n="settings.themeDark">🌙 Dark</button>
            <button class="action-btn" data-theme="auto" data-i18n="settings.themeAuto">🔄 Auto</button>
          </div>
        </div>
      </div>
      <div class="section">
        <h2 data-i18n="settings.sheet">Sheet</h2>
        <div class="row">
          <label><span data-i18n="settings.sheetIdLabel">Sheet ID</span>
            <input id="settings-sheetid" placeholder="from Google Sheet URL" data-i18n-placeholder="settings.sheetIdPlaceholder" />
          </label>
          <label><span data-i18n="settings.demoModeLabel">Demo mode</span>
            <select id="settings-demo">
              <option value="true" data-i18n="settings.demoOn">On (use mock data)</option>
              <option value="false" data-i18n="settings.demoOff">Off (live Google Sheet)</option>
            </select>
          </label>
          <div class="actions" style="display:flex; margin-top: 12px">
            <button class="action-btn primary" id="settings-save" data-i18n="settings.saveReload">Save & reload</button>
          </div>
        </div>
      </div>
      <div class="section">
        <h2 data-i18n="settings.pendingWrites">Pending writes</h2>
        <div class="row" id="settings-queue" data-i18n="empty.noQueuedWrites">No queued writes.</div>
      </div>
      <div class="section">
        <h2 data-i18n="settings.about">About</h2>
        <div class="row">
          <span data-i18n="settings.aboutBody">Family inc. dashboard · v0.1 · Phase 6 prototype</span>
          <div class="row-note" data-i18n="settings.aboutNote">Data lives in your Google Sheet. This page is a local view.</div>
        </div>
      </div>
    </section>

    <nav class="tabbar">
      <button data-tab="today" class="active" data-i18n="tabbar.today">Today</button>
      <button data-tab="sunday" data-i18n="tabbar.sunday">Sunday</button>
      <button data-tab="settings" data-i18n="tabbar.settings">Settings</button>
    </nav>
  </div>

  <!-- Bottom-sheet (V3.5) — ONE shared, data-driven drawer; opened per domain by
       openSheet(). role=dialog + aria-modal; Esc / scrim / close dismiss; focus is
       trapped while open and returned to the launching tile on close. -->
  <div id="sheet-scrim" class="sheet-scrim" hidden></div>
  <aside id="sheet" class="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title" hidden>
    <div class="sheet-grip" aria-hidden="true"></div>
    <header class="sheet-head">
      <h2 id="sheet-title" class="sheet-title"></h2>
      <span class="kpi num" id="sheet-kpi"></span>
      <button id="sheet-close" class="sheet-close" type="button" data-i18n-aria="sheet.close" aria-label="Close">✕</button>
    </header>
    <div id="sheet-body" class="sheet-body"></div>
  </aside>

  <div id="toast" class="toast"></div>

  <script src="config.js"></script>
  <script src="app.js"></script>
  <script>
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('sw.js').catch(() => {/* offline only — fine to fail */});
      });
    }
  </script>
</body>
</html>

=== End: dashboard/index.html ===

=== File: dashboard/app.js ===
// Family inc. dashboard — single-file SPA.
// Boring tech: vanilla JS, no build step, no framework.

(() => {
  'use strict';

  const cfg = window.FAMILY_INC_CONFIG;
  // spreadsheets: data; userinfo.email: who is tapping, so write-backs are
  // attributed via Settings.UserMap (SPEC §7.6) instead of a config guess.
  const SCOPES = 'https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/userinfo.email';
  const DISCOVERY = 'https://sheets.googleapis.com/$discovery/rest?version=v4';
  const CACHE_KEY = 'family_inc_cache_v1';
  const QUEUE_KEY = 'family_inc_writequeue_v1';
  const TOKEN_KEY = 'family_inc_token_v1';
  const MAX_PENDING_WRITES = 50;   // offline-queue cap (SPEC §7.6 / DESIGN §6) —
                                   // a one-shot warning fires at the cap, then
                                   // further taps are dropped, not silently lost
  // Lane C — the §6.1 Reminders columns the dashboard WRITES, resolved by header
  // NAME at load so a column insert can't corrupt a position-write; writes pause
  // if any is missing (the JS half of the engine's §7.1 schema-drift guard).
  const REMINDER_WRITE_COLS = ['Due Date', 'Status', 'Last Sent', 'Notes', 'LastDoneBy', 'DoneAt', 'WriteQueue_Tombstone'];

  // ---------------- i18n ----------------
  // Single source of truth for chrome strings. Hebrew is canonical; English
  // mirrors meaning, not literal legacy text. To add a key: drop it here and
  // tag the element with data-i18n="<key>" OR call t('<key>', {vars}) in JS.
  const STRINGS = {
    he: {
      // Tabbar
      'tabbar.today': 'היום',
      'tabbar.sunday': 'ראשון',
      'tabbar.settings': 'הגדרות',
      // Today screen sections
      'section.todayList': 'להיום',
      'section.calendar': 'יומן',
      'section.comingUp': 'בקרוב',
      'section.domains': 'תחומים',
      // Drawers
      'drawer.money': 'כספים',
      'drawer.health': 'בריאות',
      'drawer.goals': 'יעדים',
      'drawer.car': 'רכב',
      'drawer.contracts': 'מנויים וחוזים',
      'drawer.education': 'חינוך',
      'drawer.timeline': 'ציר זמן',
      // Status pill (3-tier; V3.2 replaced the status banner). Labels are
      // count-free — the count renders as its own mono span beside the label.
      'pill.overdue': 'באיחור',
      'pill.dueToday': 'להיום',
      'pill.allClear': 'אין דברים דחופים',
      'pill.sundayReady': 'סיכום ראשון מוכן',
      // Desk batch actions (V3.3 select-to-act). row.* double as the batch-bar labels.
      'row.done': '✓ בוצע',
      'row.snooze': '+ דחה',
      'row.note': '+ הערה',
      'desk.selected': 'נבחרו: {n}',
      'desk.notePlaceholder': 'כתבו הערה…',
      // Absolute-snooze chips (V3.3) — each resolves to an absolute Due date.
      'snooze.tomorrow': 'מחר',
      'snooze.in3': '+3',
      'snooze.week': 'שבוע',
      'snooze.twoweeks': 'שבועיים',
      'snooze.month': 'חודש',
      'snooze.pickDate': 'בחר תאריך',
      'snooze.label': 'דחה ל…',
      // Empty states
      'empty.nothingOnFire': 'שום דבר לא בוער. ☕',
      'empty.nothingThisWeek': 'אין אירועים השבוע.',
      'empty.noEventsDay': 'אין אירועים.',
      'empty.noQueuedWrites': 'אין כתיבות בתור.',
      'empty.next60Days': 'אין אירועים בחודשיים הקרובים.',
      'empty.noBudget': 'אין תקציב עדיין.',
      'empty.noRecentTxns': 'אין עסקאות אחרונות.',
      'empty.noGoals': 'אין יעדים.',
      'empty.noVehicle': 'אין רכב.',
      'empty.noRenewals': 'אין חידושים בחודשיים הקרובים.',
      'empty.noMilestones': 'אין אבני דרך בטווח שנבחר.',
      'empty.noUpcoming': 'אין פריטים קרובים.',
      'empty.noOverdue': 'אין פריטים באיחור.',
      'empty.allClean': 'הכל נקי.',
      'state.allGood': 'הכל בסדר',
      'state.loading': 'טוען…',
      // Calendar
      'cal.allDay': 'כל היום',
      'cal.today': 'היום',
      'cal.tomorrow': 'מחר',
      // Portfolio bottom-sheet
      'sheet.close': 'סגור',
      'sheet.recentTxns': 'עסקאות אחרונות',
      // Cross-domain timeline (V3.6) — zoom rungs + category-filter chips
      'timeline.zoomLabel': 'טווח זמן',
      'timeline.filterLabel': 'סינון לפי תחום',
      'timeline.now': 'עכשיו',
      'timeline.zoom.1wk': 'שבוע',
      'timeline.zoom.1mo': 'חודש',
      'timeline.zoom.3mo': '3 ח׳',
      'timeline.zoom.1yr': 'שנה',
      'timeline.zoom.5yr': '5 ש׳',
      'timeline.cat.all': 'הכל',
      'timeline.cat.finance': 'כספים',
      'timeline.cat.health': 'בריאות',
      'timeline.cat.car': 'רכב',
      'timeline.cat.education': 'חינוך',
      'timeline.cat.goals': 'יעדים',
      'timeline.cat.contracts': 'חוזים',
      'timeline.cat.calendar': 'יומן',
      'timeline.cat.other': 'אחר',
      // Love-note (V3.7) — parent-to-parent ephemeral note
      'lovenote.heading': 'פתק',
      'lovenote.inboundFrom': 'פתק מ{name}',
      'lovenote.composePlaceholder': 'פתק ל{name}…',
      'lovenote.composeGeneric': 'השאר פתק…',
      'lovenote.send': 'שלח',
      'lovenote.clear': 'מחק',
      'lovenote.waiting': 'ממתין ל{name}',
      'lovenote.sentToast': 'הפתק נשלח ל{name}',
      'lovenote.clearedToast': 'הפתק נמחק',
      'lovenote.failedToast': 'שליחת הפתק נכשלה — נסו שוב',
      // Car field labels
      'car.annualTest': 'טסט שנתי',
      'car.insurance': 'ביטוח',
      'car.license': 'רישיון',
      // Generic chrome
      'label.next': 'הבא:',
      // Drawer summary templates
      'summary.upcoming': '{n} בקרוב',
      'summary.active': '{n} פעילים',
      'summary.over': '{n} חורגות',
      'summary.within60': '{n} בחודשיים הקרובים',
      // Sunday view
      'sunday.title': 'סיכום ראשון',
      'sunday.weekAhead': 'השבוע הקרוב',
      'sunday.remindersThisWeek': 'תזכורות לשבוע',
      'sunday.overdue': 'באיחור',
      'sunday.money': 'כספים',
      'sunday.goals': 'יעדים',
      'sunday.hygiene': 'תחזוקת נתונים',
      'sunday.monthToDate': 'מתחילת החודש',
      'sunday.noOverBudget': 'אף קטגוריה לא חרגה.',
      'sunday.hygienePeople': '{n} שורות באנשים עם שמות לדוגמה',
      'sunday.hygieneGoals': '{n} יעדים עם טקסט לדוגמה',
      // Settings
      'settings.account': 'חשבון',
      'settings.sheet': 'גיליון',
      'settings.language': 'שפה',
      'settings.appearance': 'מראה',
      'settings.themeLight': '☀️ בהיר',
      'settings.themeDark': '🌙 כהה',
      'settings.themeAuto': '🔄 אוטומטי',
      'settings.pendingWrites': 'כתיבות בתור',
      'settings.about': 'אודות',
      'settings.sheetIdLabel': 'מזהה הגיליון',
      'settings.sheetIdPlaceholder': 'מתוך כתובת ה-Google Sheet',
      'settings.demoModeLabel': 'מצב הדגמה',
      'settings.demoOn': 'דלוק (נתוני הדגמה)',
      'settings.demoOff': 'כבוי (גיליון אמיתי)',
      'settings.switchAccount': 'החלף חשבון',
      'settings.signOut': 'התנתק',
      'settings.forceRefresh': 'רענן עכשיו',
      'settings.saveReload': 'שמור וטען מחדש',
      'settings.aboutBody': 'Family inc. dashboard · v0.1 · אב-טיפוס שלב 6',
      'settings.aboutNote': 'המידע יושב בגיליון Google שלך. הדף הזה הוא תצוגה מקומית.',
      'settings.demoModeStatus': 'מצב הדגמה',
      'settings.demoNoAccount': 'לא מחובר חשבון Google.',
      'settings.signedInAs': 'מחובר כ-{name}',
      'settings.notSignedIn': 'לא מחובר.',
      'settings.langHebrew': 'עברית',
      'settings.langEnglish': 'English',
      // Stale / offline
      'stale.offline': 'לא מקוון — נתונים מ-{when}',
      // Sign-in screen
      'signin.prompt': 'התחבר עם חשבון Google שיש לו גישה לגיליון <code>Family_OS</code> שלך.',
      'signin.button': 'התחבר עם Google',
      'signin.notConfigured': 'OAuth לא מוגדר',
      'signin.demoLine': 'או <a href="#" id="demo-link">נסה עם נתוני הדגמה</a>.',
      // Error toasts
      'toast.signinFailed': 'ההתחברות נכשלה: {err}',
      'toast.oauthNotConfigured': 'OAuth לא מוגדר — ראה README_SETUP.md',
      'toast.loadFailed': 'לא הצלחתי לטעון נתונים ואין מטמון זמין.',
      'toast.gapiLoadError': 'לא הצלחתי לטעון את Google API. בדוק את החיבור לאינטרנט.',
      'toast.gisLoadError': 'לא הצלחתי לטעון את Google Sign-In. בדוק את החיבור לאינטרנט.',
      'signin.gapiLoadError': 'שגיאה בטעינת Google API',
      'signin.gisLoadError': 'שגיאה בטעינת Google Sign-In',
      'toast.sheetIdInvalid': 'מזהה גיליון לא תקין — בדוק שהוא בפורמט הנכון.',
      'toast.sheetIdTestFailed': 'לא הצלחתי לאמת את מזהה הגיליון: {err}',
      'toast.demoPrefix': '(הדגמה) {label}',
      'toast.queuedOffline': 'נשמר בתור לא מקוון: {label}',
      'toast.queued': 'נשמר בתור: {label}',
      'toast.queueFull': 'התור מלא ({max}) — התחברו לאינטרנט כדי לסנכרן לפני שמירת פעולות נוספות',
      'toast.flushed': 'הוזרמו {n} פעולות מהתור',
      'toast.writesPaused': 'מבנה הגיליון השתנה — כתיבות מושהות (בדקו את כותרות העמודות)',
      // Action labels (used in toasts after write-back)
      'action.markedDone': 'בוצע: {title}',
      'action.doneN': '{n} בוצעו',
      'action.snoozedTo': 'נדחה ל-{date}: {title}',
      'action.snoozedN': '{n} נדחו ל-{date}',
      'action.noteAdded': 'הערה נוספה',
      'action.noteAddedN': 'הערה נוספה ל-{n}',
    },
    en: {
      'tabbar.today': 'Today',
      'tabbar.sunday': 'Sunday',
      'tabbar.settings': 'Settings',
      'section.todayList': 'For today',
      'section.calendar': 'Calendar',
      'section.comingUp': 'Coming up',
      'section.domains': 'Domains',
      'drawer.money': 'Money',
      'drawer.health': 'Health',
      'drawer.goals': 'Goals',
      'drawer.car': 'Car',
      'drawer.contracts': 'Subscriptions & contracts',
      'drawer.education': 'Education',
      'drawer.timeline': 'Timeline',
      'pill.overdue': 'overdue',
      'pill.dueToday': 'due today',
      'pill.allClear': 'Nothing urgent',
      'pill.sundayReady': 'Sunday briefing ready',
      'row.done': '✓ done',
      'row.snooze': '+ snooze',
      'row.note': '+ note',
      'desk.selected': '{n} selected',
      'desk.notePlaceholder': 'Write a note…',
      'snooze.tomorrow': 'Tomorrow',
      'snooze.in3': '+3d',
      'snooze.week': '1 week',
      'snooze.twoweeks': '2 weeks',
      'snooze.month': '1 month',
      'snooze.pickDate': 'Pick a date',
      'snooze.label': 'Snooze to…',
      'empty.nothingOnFire': 'Nothing on fire. ☕',
      'empty.nothingThisWeek': 'Nothing scheduled this week.',
      'empty.noEventsDay': 'No events.',
      'empty.noQueuedWrites': 'No queued writes.',
      'empty.next60Days': 'Nothing in the next two months.',
      'empty.noBudget': 'No budget yet.',
      'empty.noRecentTxns': 'No recent transactions.',
      'empty.noGoals': 'No goals yet.',
      'empty.noVehicle': 'No vehicle.',
      'empty.noRenewals': 'No renewals in the next two months.',
      'empty.noMilestones': 'Nothing in the selected range.',
      'empty.noUpcoming': 'No upcoming items.',
      'empty.noOverdue': 'No overdue items.',
      'empty.allClean': 'All clean.',
      'state.allGood': 'All good',
      'state.loading': 'Loading…',
      'cal.allDay': 'all day',
      'cal.today': 'Today',
      'cal.tomorrow': 'Tomorrow',
      'sheet.close': 'Close',
      'sheet.recentTxns': 'Recent transactions',
      'timeline.zoomLabel': 'Time range',
      'timeline.filterLabel': 'Filter by domain',
      'timeline.now': 'now',
      'timeline.zoom.1wk': '1wk',
      'timeline.zoom.1mo': '1mo',
      'timeline.zoom.3mo': '3mo',
      'timeline.zoom.1yr': '1yr',
      'timeline.zoom.5yr': '5yr',
      'timeline.cat.all': 'all',
      'timeline.cat.finance': 'finance',
      'timeline.cat.health': 'health',
      'timeline.cat.car': 'car',
      'timeline.cat.education': 'education',
      'timeline.cat.goals': 'goals',
      'timeline.cat.contracts': 'contracts',
      'timeline.cat.calendar': 'calendar',
      'timeline.cat.other': 'other',
      // Love-note (V3.7) — parent-to-parent ephemeral note
      'lovenote.heading': 'Note',
      'lovenote.inboundFrom': 'A note from {name}',
      'lovenote.composePlaceholder': 'Leave a note for {name}…',
      'lovenote.composeGeneric': 'Leave a note…',
      'lovenote.send': 'Send',
      'lovenote.clear': 'Clear',
      'lovenote.waiting': 'Waiting for {name}',
      'lovenote.sentToast': 'Note sent to {name}',
      'lovenote.clearedToast': 'Note cleared',
      'lovenote.failedToast': 'Couldn’t send — try again',
      'car.annualTest': 'Annual test',
      'car.insurance': 'Insurance',
      'car.license': 'License',
      'label.next': 'next:',
      'summary.upcoming': '{n} upcoming',
      'summary.active': '{n} active',
      'summary.over': '{n} over',
      'summary.within60': '{n} in next two months',
      'sunday.title': 'Sunday Briefing',
      'sunday.weekAhead': 'Week ahead',
      'sunday.remindersThisWeek': 'Reminders this week',
      'sunday.overdue': 'Overdue',
      'sunday.money': 'Money',
      'sunday.goals': 'Goals',
      'sunday.hygiene': 'Data hygiene',
      'sunday.monthToDate': 'Month-to-date',
      'sunday.noOverBudget': 'No categories over budget.',
      'sunday.hygienePeople': '{n} People row(s) using placeholder names',
      'sunday.hygieneGoals': '{n} Goal(s) using placeholder text',
      'settings.account': 'Account',
      'settings.sheet': 'Sheet',
      'settings.language': 'Language',
      'settings.appearance': 'Appearance',
      'settings.themeLight': '☀️ Light',
      'settings.themeDark': '🌙 Dark',
      'settings.themeAuto': '🔄 Auto',
      'settings.pendingWrites': 'Pending writes',
      'settings.about': 'About',
      'settings.sheetIdLabel': 'Sheet ID',
      'settings.sheetIdPlaceholder': 'from Google Sheet URL',
      'settings.demoModeLabel': 'Demo mode',
      'settings.demoOn': 'On (use mock data)',
      'settings.demoOff': 'Off (live Google Sheet)',
      'settings.switchAccount': 'Switch account',
      'settings.signOut': 'Sign out',
      'settings.forceRefresh': 'Force refresh',
      'settings.saveReload': 'Save & reload',
      'settings.aboutBody': 'Family inc. dashboard · v0.1 · Phase 6 prototype',
      'settings.aboutNote': 'Data lives in your Google Sheet. This page is a local view.',
      'settings.demoModeStatus': 'Demo mode',
      'settings.demoNoAccount': 'No Google account is connected.',
      'settings.signedInAs': 'Signed in as {name}',
      'settings.notSignedIn': 'Not signed in.',
      'settings.langHebrew': 'עברית',
      'settings.langEnglish': 'English',
      'stale.offline': 'Offline — data from {when}',
      'signin.prompt': 'Sign in with the Google account that has access to your <code>Family_OS</code> sheet.',
      'signin.button': 'Sign in with Google',
      'signin.notConfigured': 'OAuth not configured',
      'signin.demoLine': 'Or <a href="#" id="demo-link">try with demo data</a>.',
      'toast.signinFailed': 'Sign-in failed: {err}',
      'toast.oauthNotConfigured': 'OAuth not configured — see README_SETUP.md',
      'toast.loadFailed': 'Could not load data and no cache available.',
      'toast.gapiLoadError': 'Could not load Google sign-in. Check your connection.',
      'toast.gisLoadError': 'Could not load Google sign-in. Check your connection.',
      'signin.gapiLoadError': 'Could not load Google sign-in',
      'signin.gisLoadError': 'Could not load Google sign-in',
      'toast.sheetIdInvalid': 'Invalid Sheet ID — check the format and try again.',
      'toast.sheetIdTestFailed': 'Could not verify Sheet ID: {err}',
      'toast.demoPrefix': '(demo) {label}',
      'toast.queuedOffline': 'Queued offline: {label}',
      'toast.queued': 'Queued: {label}',
      'toast.queueFull': 'Queue full ({max}) — reconnect to sync before queuing more',
      'toast.flushed': 'Flushed {n} queued action(s)',
      'toast.writesPaused': 'Sheet structure changed — writes paused (check the column headers)',
      'action.markedDone': '{title} → done',
      'action.doneN': '{n} → done',
      'action.snoozedTo': '{title} → {date}',
      'action.snoozedN': '{n} → {date}',
      'action.noteAdded': 'Note added',
      'action.noteAddedN': 'Note added to {n}',
    },
  };
  function currentLang() {
    return document.documentElement.lang === 'en' ? 'en' : 'he';
  }
  function t(key, vars) {
    const dict = STRINGS[currentLang()] || STRINGS.he;
    let s = dict[key];
    if (s == null) s = key; // fail visibly if a key is missing
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        s = s.split(`{${k}}`).join(String(v));
      }
    }
    return s;
  }
  // Walks the DOM once at boot and replaces text content of any element tagged
  // with data-i18n="<key>". The English text in index.html is a fallback that
  // shows if JS fails to run. data-i18n-html does innerHTML — use only for keys
  // we control (e.g. signin.demoLine which embeds a known anchor).
  function applyChromeStrings() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.dataset.i18n;
      const v = t(key);
      if (v != null && v !== key) el.textContent = v;
    });
    document.querySelectorAll('[data-i18n-html]').forEach(el => {
      const key = el.dataset.i18nHtml;
      const v = t(key);
      if (v != null && v !== key) el.innerHTML = v;
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.dataset.i18nPlaceholder;
      const v = t(key);
      if (v != null && v !== key) el.setAttribute('placeholder', v);
    });
    // data-i18n-aria → aria-label, so icon-only / unlabelled controls (the sheet
    // close ✕, the coming-up scroll region, the snooze date picker + note textarea)
    // are named in the active language declaratively — replacing the hand-rolled
    // setAttribute calls the earlier slices scattered through boot() (V3.8).
    document.querySelectorAll('[data-i18n-aria]').forEach(el => {
      const key = el.dataset.i18nAria;
      const v = t(key);
      if (v != null && v !== key) el.setAttribute('aria-label', v);
    });
  }

  // ---------------- State ----------------
  const state = {
    user: null,           // {email, name}
    token: null,
    data: null,           // parsed sheet data
    cachedAt: null,
    tab: 'today',
    pendingWrites: [],
    queueFullWarned: false,   // one-shot: warn once at the cap, reset after a flush
    today: stripTime(new Date()),
    tokenClient: null,
    gapiReady: false,
    gisReady: false,
    activeSheet: null,        // domain key of the open bottom-sheet, or null
    sheetReturnFocus: null,   // domain key whose tile regains focus on close (NOT a
                              // node ref — a bg reload rebuilds the grid; re-resolve live)
    timeline: { zoom: '3mo', filter: 'all' },  // V3.6 cross-domain timeline view state
    loveNote: { inbound: null, outbound: null },  // V3.7 — note FROM partner / note I left
    loveNoteSending: false,                       // one-shot guard while a PUT/DELETE is in flight
    driftWarned: false,                           // Lane C — one-shot "writes paused" toast on header drift
    deskSelection: new Set(),                     // V3.3 — selected desk row numbers (strings); ephemeral,
                                                  // cleared on every renderToday rebuild + after each batch
  };

  // ---------------- Utilities ----------------
  function stripTime(d) {
    const x = new Date(d);
    x.setHours(0, 0, 0, 0);
    return x;
  }
  function daysBetween(a, b) {
    return Math.round((stripTime(a) - stripTime(b)) / (1000 * 60 * 60 * 24));
  }
  // Intl-based formatters (Hebrew locale). Defined as helpers so RTL copy "just works".
  const _ilsFmt = new Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 });
  const _dateHEFmt = new Intl.DateTimeFormat('he-IL', { day: '2-digit', month: '2-digit', year: 'numeric' });
  const _dateHEShortFmt = new Intl.DateTimeFormat('he-IL', { day: '2-digit', month: '2-digit' });

  function formatILS(n) {
    if (n == null || isNaN(n)) return '';
    return _ilsFmt.format(Math.round(n));
  }
  function formatDateHE(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    return _dateHEFmt.format(d);
  }
  // Back-compat wrappers — old call sites still work, now wired to Hebrew formatting.
  function fmtDate(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    return _dateHEShortFmt.format(d);
  }
  // Sub-shorthand: just "D.M" (e.g. "7.6") for the Sunday header date range.
  // Intl emits a trailing dot in he-IL for this style; we hand-format to skip it.
  function fmtDateShort(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    return `${d.getDate()}.${d.getMonth() + 1}`;
  }
  function fmtILS(n) { return formatILS(n); }
  // Wraps an amount string in an isolated bidi span so ₪ + Hebrew text don't reorder.
  function amountHtml(n) {
    const s = formatILS(n);
    if (!s) return '';
    return `<span class="amount bidi-amount">${escapeHtml(s)}</span>`;
  }
  function fmtISO(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }
  // Full local ISO datetime (with T, no timezone — naive local, matching the
  // engine). Used for the machine stamps DoneAt + WriteQueue_Tombstone: the
  // T-form stays a TEXT cell in Sheets, so it round-trips byte-exact and the
  // 6h tombstone window keeps hour resolution (a date-only tombstone looks
  // hours old the moment it's written — that race guard was dead, SPEC §8.3).
  function fmtISOts(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    const p = (n) => String(n).padStart(2, '0');
    return `${fmtISO(d)}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  }
  // Lane C: col-D (Due Date) is a real Sheets date cell, so the API renders it
  // back in the he-IL locale (DD/MM/YYYY or DD.MM.YYYY) even when we WRITE ISO.
  // parseDate therefore reads BOTH: ISO (incl. the ISO-T stamps + calendar dates)
  // first — unambiguous — then the locale day-first render. A bare `new Date()`
  // alone returns Invalid for "25/06/2026", which would silently drop a snoozed/
  // recurrence-bumped reminder from Today; this is the read half of that fix.
  function parseDate(v) {
    if (!v) return null;
    if (v instanceof Date) return isNaN(v) ? null : v;
    if (typeof v === 'number') {
      // Excel serial — used if we ever roundtrip from xlsx, but Sheets API
      // returns formatted strings, so this branch is rare.
      return new Date(Math.round((v - 25569) * 86400 * 1000));
    }
    const s = String(v).trim();
    if (!s) return null;
    // ISO YYYY-MM-DD (optionally with a time/stamp) — let Date parse it.
    if (/^\d{4}-\d{2}-\d{2}/.test(s)) {
      const d = new Date(s);
      return isNaN(d) ? null : d;
    }
    // he-IL date render: DD/MM/YYYY or DD.MM.YYYY (day-first; the Sheet locale).
    const m = s.match(/^(\d{1,2})[./](\d{1,2})[./](\d{2,4})$/);
    if (m) {
      const dd = +m[1], mm = +m[2];
      const yy = +m[3] < 100 ? 2000 + +m[3] : +m[3];
      const d = new Date(yy, mm - 1, dd);
      // Reject impossible dates (e.g. 31/02): Date rolls them over, so verify.
      return (isNaN(d) || d.getMonth() !== mm - 1 || d.getDate() !== dd) ? null : d;
    }
    const d = new Date(s);   // last resort (other ISO-ish shapes)
    return isNaN(d) ? null : d;
  }
  function flagFor(daysUntil, status) {
    if (status === 'Done' || status === 'Skipped') return '';
    if (daysUntil == null || isNaN(daysUntil)) return '';
    if (daysUntil < 0) return 'OVERDUE';
    if (daysUntil <= 1) return 'FIRE TODAY';
    if (daysUntil <= 7) return 'WEEK OUT';
    if (daysUntil <= 30) return 'MONTH OUT';
    return '';
  }
  function flagEmoji(f) {
    return { 'OVERDUE': '🔴', 'FIRE TODAY': '🟠', 'WEEK OUT': '🟡', 'MONTH OUT': '🟢' }[f] || '·';
  }
  function flagClass(f) {
    return { 'OVERDUE': 'flag-OVERDUE', 'FIRE TODAY': 'flag-FIRE', 'WEEK OUT': 'flag-WEEK', 'MONTH OUT': 'flag-MONTH' }[f] || '';
  }
  function duePhrase(daysUntil) {
    if (daysUntil == null) return '';
    if (currentLang() === 'he') {
      // Hebrew grammar: singular (יום), dual (יומיים), plural (ימים).
      if (daysUntil < 0) {
        const abs = -daysUntil;
        if (abs === 1) return 'באיחור של יום';
        if (abs === 2) return 'באיחור של יומיים';
        return `באיחור של ${abs} ימים`;
      }
      if (daysUntil === 0) return 'להיום';
      if (daysUntil === 1) return 'מחר';
      if (daysUntil === 2) return 'בעוד יומיים';
      return `בעוד ${daysUntil} ימים`;
    }
    if (daysUntil < 0) return `overdue by ${-daysUntil}d`;
    if (daysUntil === 0) return 'due today';
    if (daysUntil === 1) return 'due tomorrow';
    return `in ${daysUntil}d`;
  }
  function toast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2200);
  }
  function colLetter(n) {
    // 1 → A, 27 → AA
    let s = '';
    while (n > 0) {
      const r = (n - 1) % 26;
      s = String.fromCharCode(65 + r) + s;
      n = Math.floor((n - 1) / 26);
    }
    return s;
  }

  // ---------------- Auth ----------------
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src; s.async = true; s.defer = true;
      s.onload = resolve;
      s.onerror = () => reject(new Error('Failed to load ' + src));
      document.head.appendChild(s);
    });
  }

  async function initAuth() {
    if (cfg.DEMO_MODE) return;
    if (!cfg.CLIENT_ID || cfg.CLIENT_ID.startsWith('PASTE_')) return;

    try {
      await loadScript('https://apis.google.com/js/api.js');
    } catch {
      const btn = document.getElementById('signin-btn');
      if (btn) { btn.textContent = t('signin.gapiLoadError'); btn.disabled = true; }
      toast(t('toast.gapiLoadError'));
      return;
    }
    await new Promise((resolve) => gapi.load('client', resolve));
    await gapi.client.init({ discoveryDocs: [DISCOVERY] });
    state.gapiReady = true;

    try {
      await loadScript('https://accounts.google.com/gsi/client');
    } catch {
      const btn = document.getElementById('signin-btn');
      if (btn) { btn.textContent = t('signin.gisLoadError'); btn.disabled = true; }
      toast(t('toast.gisLoadError'));
      return;
    }
    state.tokenClient = google.accounts.oauth2.initTokenClient({
      client_id: cfg.CLIENT_ID,
      scope: SCOPES,
      callback: (resp) => {
        if (resp.error) { toast(t('toast.signinFailed', { err: resp.error })); return; }
        state.token = resp;
         localStorage.setItem(TOKEN_KEY, JSON.stringify({ access_token: resp.access_token, expires_at: Date.now() + (resp.expires_in * 1000) }));
        afterSignIn();
      },
    });
    state.gisReady = true;

    // Restore session token if still valid (avoids forcing sign-in every reload).
    const saved = localStorage.getItem(TOKEN_KEY);
    if (saved) {
      try {
        const t = JSON.parse(saved);
        if (t.expires_at > Date.now() + 60000) {
          gapi.client.setToken({ access_token: t.access_token });
          state.token = t;
          afterSignIn();
        }
      } catch {}
    }
  }

  function requestSignIn() {
    if (!state.tokenClient) {
      toast(t('toast.oauthNotConfigured'));
      return;
    }
    state.tokenClient.requestAccessToken({ prompt: 'consent' });
  }

  function signOut() {
    localStorage.removeItem(TOKEN_KEY);
    state.token = null;
    state.user = null;
    if (window.google?.accounts?.oauth2) {
      google.accounts.oauth2.revoke(gapi.client.getToken()?.access_token, () => {});
    }
    showSignIn();
  }

  // D3 — switch the signed-in Google account for real (SPEC §7.6): force the account
  // chooser (prompt:'select_account', not 'consent'), so the OTHER parent can sign in.
  // Identity is always the live OAuth session, never a label flip — the token callback
  // → afterSignIn re-resolves the new email → UserMap name, so col-M LastDoneBy stays
  // truthful. Cancelling the chooser is a no-op (the callback never fires; the current
  // session is untouched). We deliberately do NOT revoke the prior token: revoke() drops
  // the whole user+client GRANT, which would both force the other parent to re-consent
  // next time AND kill the new session if the user re-picks the SAME account (a fresh
  // token over the same grant). The superseded token is dropped from the app and expires.
  function switchAccount() {
    if (!state.tokenClient) { toast(t('toast.oauthNotConfigured')); return; }
    state.tokenClient.requestAccessToken({ prompt: 'select_account' });
  }

  async function afterSignIn() {
    // Who signed in? userinfo.email scope → email; the display name comes
    // from Settings.UserMap once the Sheet loads (SPEC §7.6: Google sign-in
    // → Settings.UserMap → display name). cfg.USERS stays as the offline /
    // pre-Settings fallback.
    try {
      const token = gapi.client.getToken()?.access_token;
      const resp = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
        headers: { Authorization: `Bearer ${token}` },
      });
      const info = resp.ok ? await resp.json() : {};
      const email = (info.email || '').toLowerCase();
      state.user = { email: email || 'unknown', name: resolveDisplayName(email) };
    } catch (e) {
      console.warn('Could not resolve signed-in identity', e);
      const emails = Object.keys(cfg.USERS || {});
      state.user = { email: emails[0] || 'unknown', name: (cfg.USERS || {})[emails[0]] || 'You' };
    }
    showApp();
    await loadAll();
    // Settings tab is loaded now — upgrade the display name if UserMap knows us.
    if (state.user) state.user.name = resolveDisplayName(state.user.email);
  }

  // Settings.UserMap (email → display name) → cfg.USERS fallback → 'You'.
  function resolveDisplayName(email) {
    const fromSheet = state.data?.settings?.userMap?.[email];
    if (fromSheet) return fromSheet;
    const fromCfg = (cfg.USERS || {})[email];
    if (fromCfg) return fromCfg;
    // Unknown signer: fall back to the first configured user (pre-M2 behavior)
    const emails = Object.keys(cfg.USERS || {});
    return (cfg.USERS || {})[emails[0]] || 'You';
  }

  // ---------------- Data load ----------------
  async function loadAll() {
    if (cfg.DEMO_MODE) {
      const resp = await fetch('mock_data.json');
      const json = await resp.json();
      state.data = parseAll(json);
      state.cachedAt = new Date();
      state.loveNote = state.data.loveNote || { inbound: null, outbound: null };  // V3.7 demo fixture
      renderAll();
      return;
    }
    try {
      const tabs = cfg.TABS;
      // Order matters — keep in sync with `named` below.
      const ranges = [
        `${tabs.reminders}!A:O`,
        `${tabs.calendarEvents}!A:H`,
        `${tabs.people}!A:I`,
        `${tabs.finance_bdgt}!A:I`,
        `${tabs.finance_txns}!A:I`,
        `${tabs.goals}!A:I`,
        `${tabs.health}!A:I`,
        `${tabs.education}!A:I`,
        `${tabs.car}!A:I`,
        `${tabs.contracts}!A:I`,
        `${tabs.settings || 'Settings'}!A:B`,
      ];
      const resp = await gapi.client.sheets.spreadsheets.values.batchGet({
        spreadsheetId: cfg.SHEET_ID,
        ranges,
        valueRenderOption: 'UNFORMATTED_VALUE',
        dateTimeRenderOption: 'FORMATTED_STRING',
      });
      const named = {
        reminders: resp.result.valueRanges[0].values || [],
        calendarEvents: resp.result.valueRanges[1].values || [],
        people: resp.result.valueRanges[2].values || [],
        finance_bdgt: resp.result.valueRanges[3].values || [],
        finance_txns: resp.result.valueRanges[4].values || [],
        goals: resp.result.valueRanges[5].values || [],
        health: resp.result.valueRanges[6].values || [],
        education: resp.result.valueRanges[7].values || [],
        car: resp.result.valueRanges[8].values || [],
        contracts: resp.result.valueRanges[9].values || [],
        settings: resp.result.valueRanges[10]?.values || [],
      };
      state.data = parseAll(named);
      state.cachedAt = new Date();
      localStorage.setItem(CACHE_KEY, JSON.stringify({ raw: named, at: state.cachedAt.toISOString() }));
      applySheetLang();
      renderAll();
      await flushQueue();
      loadLoveNote();   // V3.7 — the appliance endpoint, not the Sheet; re-renders the slot when it lands
    } catch (e) {
      console.error('Live load failed', e);
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached) {
        const { raw, at } = JSON.parse(cached);
        state.data = parseAll(raw);
        state.cachedAt = new Date(at);
        document.getElementById('stale-badge').hidden = false;
        document.getElementById('stale-badge').textContent = t('stale.offline', { when: state.cachedAt.toLocaleString() });
        renderAll();
      } else {
        toast(t('toast.loadFailed'));
      }
    }
  }

  // Settings.lang is the cross-device DEFAULT chrome language; an explicit
  // local toggle (localStorage.familyinc.lang) always wins (DESIGN §7).
  function applySheetLang() {
    let saved = null;
    try { saved = localStorage.getItem('familyinc.lang'); } catch {}
    if (saved) return; // personal preference wins
    const sheetLang = state.data?.settings?.lang;
    if ((sheetLang === 'en' || sheetLang === 'he') && sheetLang !== currentLang()) {
      document.documentElement.setAttribute('lang', sheetLang);
      document.documentElement.setAttribute('dir', sheetLang === 'en' ? 'ltr' : 'rtl');
      applyChromeStrings();
    }
  }

  // ---------------- Parsers ----------------
  // Sheet tab → header row (row 1) + data rows (row 2+).
  // Each parsed row carries its 1-based sheet row number as `_row` so writes
  // can target the right cell.
  function rowsToObjects(rows) {
    if (!rows || rows.length < 2) return [];
    const headers = rows[0];
    return rows.slice(1).map((r, i) => {
      const o = { _row: i + 2 };
      headers.forEach((h, j) => { o[h] = r[j] ?? null; });
      return o;
    });
  }

  // V3.2 forward seam (consumed by V3.4's 3-day calendar): collapse a candle-
  // lighting Calendar-Events row to the canonical source token 'shabbat' so the
  // calendar can tag it (🕯) without re-deriving. No-op on current data — candle-
  // lighting is a digest-only Hebcal line (automation/daily_digest.py), not a
  // Calendar-Events row — so this only fires if such a row is ever added. Matched
  // PRECISELY, not broadly: only an explicit 'shabbat' Source token OR a candle-
  // lighting title. NOT the generic 'hebcal' feed marker (it would mis-tag every
  // chag/parsha/omer row) and NOT the bare word 'שבת' (would over-tag a Shabbat-
  // dinner event).
  const _SHABBAT_SOURCE_RE = /\bshabbat\b/i;
  const _SHABBAT_TITLE_RE = /הדלקת נרות|candle[\s-]?lighting/i;
  function normalizeCalendarSource(rawSource, title) {
    if (_SHABBAT_SOURCE_RE.test(rawSource) || _SHABBAT_TITLE_RE.test(title)) return 'shabbat';
    return rawSource;
  }

  function parseAll(named) {
    const reminders = rowsToObjects(named.reminders).map(r => {
      const due = parseDate(r['Due Date']);
      const daysUntil = due ? daysBetween(due, state.today) : null;
      const status = r['Status'] || 'Pending';
      return {
        _row: r._row,
        title: r['Title'] || '',
        domain: r['Domain'] || '',
        owner: r['Owner'] || '',
        due,
        leads: (r['Lead Times'] ?? r['Lead Times (days)'] ?? '').toString().split(',').map(x => parseInt(x, 10)).filter(x => !isNaN(x)),
        recurrence: r['Recurrence'] || 'One-off',
        status,
        lastSent: parseDate(r['Last Sent']),
        channel: r['Channel'] || '',
        notes: r['Notes'] || '',
        daysUntil,
        flag: flagFor(daysUntil, status),
        // Phase 6.1 columns (cols M, N, O) — may be blank on legacy sheets
        lastDoneBy: (r['LastDoneBy'] || '').trim(),
        doneAt: parseDate(r['DoneAt']),
        writeQueueTombstone: parseDate(r['WriteQueue_Tombstone']),
      };
    });
    const calendarEvents = rowsToObjects(named.calendarEvents).map(r => {
      const title = r['Title'] || '';
      return {
        _row: r._row,
        date: parseDate(r['Date']),
        start: r['Start'] || '',
        end: r['End'] || '',
        title,
        owner: r['Owner'] || '',
        source: normalizeCalendarSource(r['Source'] || '', title),
        location: r['Location'] || '',
        notes: r['Notes'] || '',
      };
    });
    const people = rowsToObjects(named.people);
    // Settings tab (SPEC §6.4): Key|Value rows — keys containing '@' build
    // UserMap (email → display name); key 'lang' is the chrome default.
    const settings = { userMap: {}, lang: null };
    (named.settings || []).slice(1).forEach(row => {
      const key = String(row?.[0] ?? '').trim();
      const value = String(row?.[1] ?? '').trim();
      if (!key || !value) return;
      if (key.includes('@')) settings.userMap[key.toLowerCase()] = value;
      else if (key.toLowerCase() === 'lang') settings.lang = value;
    });
    const budget = rowsToObjects(named.finance_bdgt).map(r => ({
      category: r['Category'],
      target: parseFloat(r['Monthly Target (ILS)']) || 0,
      actual: parseFloat(r['Actual (current month)']) || 0,
      pct: parseFloat(r['% of Target']) || 0,
      // Drop the header echo and the TOTAL row: TOTAL is a SUM of the categories,
      // so including it would double-count the money-summary totals, list a
      // phantom "TOTAL" line, and miscount over-budget categories. The weekly
      // briefing's section_money skips it the same way (keep the two surfaces in
      // agreement — both read this one tab).
    })).filter(b => b.category && b.category !== 'Category' && b.category !== 'TOTAL');
    const txns = rowsToObjects(named.finance_txns).map(r => ({
      date: parseDate(r['Date']),
      account: r['Account'],
      desc: r['Description'],
      amount: parseFloat(r['Amount (ILS)']) || 0,
      category: r['Category'],
    }));
    const goals = rowsToObjects(named.goals).map(r => ({
      _row: r._row,
      goal: r['Goal'],
      owner: r['Owner'],
      horizon: r['Horizon'],
      targetDate: parseDate(r['Target Date']),
      milestone: r['90-Day Milestone'],
      pct: parseFloat(r['% Complete']) || 0,
      status: r['Status'],
    })).filter(g => g.goal);
    const health = rowsToObjects(named.health).map(r => ({
      person: r['Person'],
      provider: r['Provider'],
      specialty: r['Specialty'],
      nextDue: parseDate(r['Next Due']),
      action: r['Action Needed'],
    })).filter(h => h.person);
    const education = rowsToObjects(named.education).map(r => ({
      child: r['Child'],
      institution: r['Institution'],
      nextDate: parseDate(r['Next Key Date']),
      type: r['Type'],
      action: r['Action Needed'],
    })).filter(e => e.child);
    const car = rowsToObjects(named.car).map(r => ({
      vehicle: r['Vehicle'],
      plate: r['Plate'],
      test: parseDate(r['Annual Test (Rishui)']),
      insurance: parseDate(r['Insurance Renewal']),
      license: parseDate(r['License Expiry']),
    })).filter(c => c.vehicle);
    const contracts = rowsToObjects(named.contracts).map(r => ({
      contract: r['Contract'],
      provider: r['Provider'],
      type: r['Type'],
      renewal: parseDate(r['Renewal Date']),
      monthly: parseFloat(r['Monthly Cost (ILS)']) || 0,
    })).filter(c => c.contract);

    // V3.7 love-note: live data comes from the appliance endpoint (loadLoveNote),
    // NOT the Sheet; in DEMO_MODE the fixture rides along in mock_data.json.
    const loveNote = named.loveNote || null;
    // Lane C: resolve the Reminders write columns by header name (row 1) so a
    // drifted/inserted column pauses writes instead of corrupting the wrong cell.
    const reminderCols = resolveReminderCols(named.reminders && named.reminders[0]);
    return { reminders, calendarEvents, people, budget, txns, goals, health, education, car, contracts, settings, loveNote, reminderCols };
  }

  // Build {name → 1-based column index} for the columns the dashboard writes,
  // from the actual header row. ok=false when any required write column is absent
  // (a renamed/removed/shifted-out header) → writes pause.
  function resolveReminderCols(headerRow) {
    const byName = {};
    (headerRow || []).forEach((h, i) => {
      const key = String(h ?? '').trim().toLowerCase();
      if (key && !(key in byName)) byName[key] = i + 1;
    });
    const cols = {};
    let ok = true;
    REMINDER_WRITE_COLS.forEach(name => {
      const idx = byName[name.toLowerCase()];
      if (idx) cols[name] = idx; else ok = false;
    });
    return { cols, ok };
  }

  // ---------------- Render ----------------
  function renderAll() {
    // Header date is chrome — route through currentLang() so the toggle
    // actually flips the most prominent label on the screen. he-IL and en-GB
    // both render DD/MM date order, which matches Israeli reading habits in
    // either language.
    const _hdrLocale = currentLang() === 'en' ? 'en-GB' : 'he-IL';
    document.getElementById('header-date').textContent = state.today.toLocaleDateString(_hdrLocale, { weekday: 'long', day: 'numeric', month: 'long' });
    // Lane C: surface a header-drift "writes paused" once (re-arms when resolved).
    if (state.data && state.data.reminderCols && !state.data.reminderCols.ok) {
      if (!state.driftWarned) { state.driftWarned = true; toast(t('toast.writesPaused')); }
    } else {
      state.driftWarned = false;
    }
    renderStatusPill();
    renderLoveNote();
    renderToday();
    render3DayCalendar();
    renderComingUp();
    renderPortfolios();
    renderSunday();
    renderSettings();
  }

  // ---------------- Status pill ----------------
  // Shared count helper (V3.2). The status pill consumes it now; V3.3's desk
  // reuses the same numbers (deskCount = overdue + fire-today) so the pill and
  // the desk can never disagree. Reads the parsed r.flag, exactly as the deleted
  // inline banner/pill filters did.
  function computeCounts() {
    const r = (state.data && state.data.reminders) || [];
    const overdue = r.filter(x => x.flag === 'OVERDUE').length;
    const today = r.filter(x => x.flag === 'FIRE TODAY').length;
    return { overdue, today, deskCount: overdue + today };
  }

  // The pill is a single 3-tier signal (overdue > today > clear), always visible
  // (clear is a resting state, never hidden) — plus a loading tier before data
  // lands so it never reads as a premature "all clear". data-tier carries color;
  // the count + label carry the meaning (never color-only, DESIGN §8). The glyph
  // is decorative (aria-hidden in the markup); the count is a mono span.
  function setStatusPill({ tier, glyph = '', count = null, label = '' }) {
    const pill = document.getElementById('status-pill');
    const glyphEl = document.getElementById('status-pill-glyph');
    const countEl = document.getElementById('status-pill-count');
    const labelEl = document.getElementById('status-pill-text');
    if (!pill || !glyphEl || !countEl || !labelEl) return;
    pill.setAttribute('data-tier', tier);
    glyphEl.textContent = glyph;
    glyphEl.hidden = !glyph;   // an empty glyph must not reserve a flex gap (loading tier)
    if (count == null) {
      countEl.hidden = true;
      countEl.textContent = '';
    } else {
      countEl.hidden = false;
      countEl.textContent = String(count);
    }
    labelEl.textContent = label;
  }
  function renderStatusPill() {
    if (!state.data) { setStatusPill({ tier: 'loading', label: t('state.loading') }); return; }
    const { overdue, today } = computeCounts();
    if (overdue > 0) {
      setStatusPill({ tier: 'overdue', glyph: '🔴', count: overdue, label: t('pill.overdue') });
    } else if (today > 0) {
      setStatusPill({ tier: 'today', glyph: '🟠', count: today, label: t('pill.dueToday') });
    } else if (state.today.getDay() === 0) { // Sunday — clear tier, briefing-ready label
      setStatusPill({ tier: 'clear', glyph: '✅', label: t('pill.sundayReady') });
    } else {
      setStatusPill({ tier: 'clear', glyph: '✅', label: t('pill.allClear') });
    }
  }

  // ---------------- Love-note (V3.7) ----------------
  // The one dashboard datum that is neither the Sheet nor the outbox: a parent-
  // to-parent ephemeral note over a small authenticated appliance endpoint
  // (automation/love_note_server.py), fronted by a Cloudflare Tunnel. ONE note
  // per direction, 24h-or-on-replacement; it shows on the recipient's NEXT open
  // — no push, and no "seen"/delivery signal back to the sender (SPEC §3.7).
  // Text-only here; voice is a frozen phase-2 (SPEC §4 carve-out).

  // The endpoint base (no trailing slash), or null when unconfigured — in which
  // case the whole slot stays hidden (never promise an affordance that's dead).
  function loveNoteBase() {
    const u = String(cfg.LOVENOTE_URL || '').trim();
    if (!u || u.startsWith('PASTE_')) return null;
    return u.replace(/\/+$/, '');
  }
  // The live Google access_token the server re-verifies against Google userinfo.
  function loveNoteToken() {
    try {
      return (window.gapi && gapi.client && gapi.client.getToken && gapi.client.getToken()?.access_token)
        || state.token?.access_token || null;
    } catch { return null; }
  }
  // Is the signed-in account actually one of the two parents in UserMap (with a
  // distinct partner to address)? A non-parent viewer with Sheet access would
  // otherwise be shown a live composer the server 403s — a dead affordance.
  function loveNoteIsParent() {
    const um = (state.data && state.data.settings && state.data.settings.userMap) || {};
    const me = ((state.user && state.user.email) || '').toLowerCase();
    if (!me) return false;
    const keys = Object.keys(um).map(e => e.toLowerCase());
    return keys.includes(me) && keys.some(e => e !== me);
  }
  // Demo always shows the component (so the card + composer can be reviewed);
  // live needs the endpoint configured AND the signer to be a known parent.
  function loveNoteEnabled() {
    if (cfg.DEMO_MODE) return true;
    return !!(loveNoteBase() && state.user && loveNoteToken() && loveNoteIsParent());
  }
  // The other adult — the note's recipient. Live: the UserMap entry that isn't
  // me. Fallback (incl. demo, where no one is signed in): whoever wrote to me /
  // whom I last wrote to / the configured pair.
  function loveNotePartnerName() {
    const um = (state.data && state.data.settings && state.data.settings.userMap) || {};
    const me = ((state.user && state.user.email) || '').toLowerCase();
    if (me) { for (const [email, name] of Object.entries(um)) { if (email.toLowerCase() !== me) return name; } }
    if (state.loveNote.inbound?.from) return state.loveNote.inbound.from;
    if (state.loveNote.outbound?.to) return state.loveNote.outbound.to;
    const vals = Object.values(cfg.USERS || {});
    return vals[vals.length - 1] || '';
  }
  // A short, localized "when" for the note timestamp (time if today, else date).
  function loveNoteWhen(iso) {
    const d = parseDate(iso);
    if (!d) return '';
    const locale = currentLang() === 'en' ? 'en-GB' : 'he-IL';
    return daysBetween(d, state.today) === 0
      ? d.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })
      : d.toLocaleDateString(locale, { day: '2-digit', month: '2-digit' });
  }

  // Fetch the note pair {inbound, outbound} for the signed-in user from the
  // appliance endpoint, then re-render the slot. Failures degrade quiet.
  async function loadLoveNote() {
    if (cfg.DEMO_MODE) {
      state.loveNote = (state.data && state.data.loveNote) || { inbound: null, outbound: null };
      renderLoveNote();
      return;
    }
    const base = loveNoteBase(), token = loveNoteToken();
    if (!base || !token) { renderLoveNote(); return; }
    try {
      const resp = await fetch(`${base}/lovenote`, { headers: { Authorization: `Bearer ${token}` } });
      if (resp.ok) state.loveNote = await resp.json();
    } catch (e) {
      console.warn('love-note load failed', e);   // slot just stays empty
    }
    renderLoveNote();
  }

  function renderLoveNote() {
    const slot = document.getElementById('love-note-slot');
    if (!slot) return;
    // Preserve an in-progress draft across this full-innerHTML rebuild: a
    // background re-render (e.g. tapping done/snooze on a reminder while
    // composing) must not wipe unsent text the user is still typing.
    const prevInput = document.getElementById('love-note-input');
    const draft = prevInput ? prevInput.value : null;
    const hadFocus = !!prevInput && document.activeElement === prevInput;
    if (!loveNoteEnabled()) { slot.hidden = true; slot.innerHTML = ''; return; }
    const partner = loveNotePartnerName();
    const inbound = state.loveNote.inbound;
    const outbound = state.loveNote.outbound;
    const placeholder = partner ? t('lovenote.composePlaceholder', { name: partner }) : t('lovenote.composeGeneric');
    // Inbound card: hidden when empty. The 💌 glyph + the "from {name}" label +
    // the wash/border carry it — never color alone (DESIGN §8).
    const inboundCard = inbound ? `
      <div class="love-note-card">
        <div class="love-note-from"><span aria-hidden="true">💌</span> ${escapeHtml(t('lovenote.inboundFrom', { name: inbound.from || partner }))}</div>
        <div class="love-note-text">${escapeHtml(inbound.text || '')}</div>
        ${inbound.sent_at ? `<div class="love-note-when num">${escapeHtml(loveNoteWhen(inbound.sent_at))}</div>` : ''}
      </div>` : '';
    const waiting = outbound
      ? `<span class="love-note-waiting">${escapeHtml(t('lovenote.waiting', { name: partner || outbound.to || '' }))}${outbound.sent_at ? ' · ' + escapeHtml(loveNoteWhen(outbound.sent_at)) : ''}</span>`
      : '';
    const clearBtn = outbound ? `<button class="action-btn danger" id="love-note-clear" type="button">${escapeHtml(t('lovenote.clear'))}</button>` : '';
    slot.innerHTML = `
      <div class="love-note">
        <h2 class="love-note-heading"><span aria-hidden="true">💌</span> ${escapeHtml(t('lovenote.heading'))}</h2>
        ${inboundCard}
        <div class="love-note-compose">
          <textarea id="love-note-input" class="love-note-input" rows="2" maxlength="500"
            placeholder="${escapeHtml(placeholder)}" aria-label="${escapeHtml(placeholder)}">${escapeHtml(outbound?.text || '')}</textarea>
          <div class="love-note-actions">
            ${waiting}
            ${clearBtn}
            <button class="action-btn primary" id="love-note-send" type="button">${escapeHtml(t('lovenote.send'))}</button>
          </div>
        </div>
      </div>`;
    slot.hidden = false;
    const send = document.getElementById('love-note-send');
    if (send) send.addEventListener('click', () => handleSendLoveNote());
    const clear = document.getElementById('love-note-clear');
    if (clear) clear.addEventListener('click', () => handleClearLoveNote());
    // Restore a divergent unsent draft the rebuild would otherwise have wiped.
    const input = document.getElementById('love-note-input');
    if (input && draft != null && draft !== input.value) {
      input.value = draft;
      if (hadFocus) { input.focus(); try { const n = draft.length; input.setSelectionRange(n, n); } catch (_) {} }
    }
  }

  async function handleSendLoveNote() {
    if (state.loveNoteSending) return;
    const input = document.getElementById('love-note-input');
    const text = ((input && input.value) || '').trim();
    if (!text) return;
    const partner = loveNotePartnerName();
    if (cfg.DEMO_MODE) {
      state.loveNote.outbound = { to: partner, text, sent_at: new Date().toISOString() };
      toast(t('toast.demoPrefix', { label: t('lovenote.sentToast', { name: partner }) }));
      renderLoveNote();
      return;
    }
    const base = loveNoteBase(), token = loveNoteToken();
    if (!base || !token) return;
    state.loveNoteSending = true;
    try {
      const resp = await fetch(`${base}/lovenote`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      if (resp.ok) { toast(t('lovenote.sentToast', { name: partner })); await loadLoveNote(); }
      else toast(t('lovenote.failedToast'));
    } catch (e) {
      console.warn('love-note send failed', e);
      toast(t('lovenote.failedToast'));
    } finally {
      state.loveNoteSending = false;
    }
  }

  async function handleClearLoveNote() {
    if (state.loveNoteSending) return;
    if (cfg.DEMO_MODE) {
      state.loveNote.outbound = null;
      toast(t('toast.demoPrefix', { label: t('lovenote.clearedToast') }));
      renderLoveNote();
      return;
    }
    const base = loveNoteBase(), token = loveNoteToken();
    if (!base || !token) return;
    state.loveNoteSending = true;
    try {
      const resp = await fetch(`${base}/lovenote`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
      if (resp.ok) { toast(t('lovenote.clearedToast')); await loadLoveNote(); }
      else toast(t('lovenote.failedToast'));
    } catch (e) {
      console.warn('love-note clear failed', e);
      toast(t('lovenote.failedToast'));
    } finally {
      state.loveNoteSending = false;
    }
  }

  // ---------------- Sparkline + KPI ----------------
  function renderSparkline(svgEl, points) {
    if (!svgEl) return;
    if (!points || points.length < 2) { svgEl.innerHTML = ''; return; }
    const w = 80, h = 24, pad = 2;
    const min = Math.min(...points);
    const max = Math.max(...points);
    const range = max - min || 1;
    const step = (w - pad * 2) / (points.length - 1);
    const coords = points.map((p, i) => {
      const x = pad + i * step;
      const y = h - pad - ((p - min) / range) * (h - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    svgEl.innerHTML = `<polyline points="${coords}" />`;
  }
  function renderKpi(drawerName, value, trend) {
    const kpiEl = document.getElementById(`${drawerName}-kpi`);
    if (!kpiEl) return;
    if (value == null || value === '') {
      kpiEl.textContent = '';
      kpiEl.classList.remove('kpi-pos', 'kpi-neg');
      return;
    }
    kpiEl.textContent = value;
    kpiEl.classList.toggle('kpi-pos', trend === 'pos');
    kpiEl.classList.toggle('kpi-neg', trend === 'neg');
  }

  // ---------------- Goal bright-line viz ----------------
  // Renders a small Beeminder-style chart:
  //   - target band (straight line from targetStart at t=0 → targetEnd at t=100%)
  //   - actual line (from 0 at start to `current` at pctTimeElapsed)
  //   - safety bands tinted around the target line
  function renderGoalLine(svgEl, { targetStart = 0, targetEnd = 100, current = 0, pctTimeElapsed = 0 } = {}) {
    if (!svgEl) return;
    const w = 100, h = 40, pad = 2;
    const yFor = (v) => {
      const clamped = Math.max(0, Math.min(100, v));
      return h - pad - (clamped / 100) * (h - pad * 2);
    };
    const xNow = Math.max(0, Math.min(100, pctTimeElapsed));
    const yT0 = yFor(targetStart);
    const yT1 = yFor(targetEnd);
    const yA0 = yFor(targetStart);
    const yA1 = yFor(current);
    // Safety bands (±5% of target line). Build as polygons spanning full width.
    const targetTopBand = `M 0,${yFor(Math.min(100, targetStart + 5))} L 100,${yFor(Math.min(100, targetEnd + 5))} L 100,0 L 0,0 Z`;
    const okBand        = `M 0,${yFor(Math.min(100, targetStart + 5))} L 100,${yFor(Math.min(100, targetEnd + 5))} L 100,${yFor(Math.max(0, targetEnd - 5))} L 0,${yFor(Math.max(0, targetStart - 5))} Z`;
    const badBand       = `M 0,${yFor(Math.max(0, targetStart - 5))} L 100,${yFor(Math.max(0, targetEnd - 5))} L 100,${h} L 0,${h} Z`;
    svgEl.setAttribute('viewBox', `0 0 ${w} ${h}`);
    svgEl.setAttribute('preserveAspectRatio', 'none');
    svgEl.innerHTML = `
      <path class="band-ok"   d="${targetTopBand}" />
      <path class="band-warn" d="${okBand}" />
      <path class="band-bad"  d="${badBand}" />
      <polyline class="target-line" points="0,${yT0} 100,${yT1}" />
      <polyline class="actual-line" points="0,${yA0} ${xNow},${yA1}" />
      <circle class="now-dot" cx="${xNow}" cy="${yA1}" r="2" />
    `;
  }

  // ---------------- Desk (V3.3 select-to-act) ----------------
  // The Today desk: OVERDUE + FIRE-TODAY reminders as checkbox-semantics rows.
  // Selecting ≥1 reveals a sticky batch bar (done / snooze / note) that fans out
  // to ONE applyWrites batch. Selection is ephemeral — cleared on every rebuild
  // (a background reload can re-number _row) and after each batch.
  function renderToday() {
    state.deskSelection.clear();
    const list = state.data.reminders
      .filter(r => r.flag === 'OVERDUE' || r.flag === 'FIRE TODAY')
      .sort((a, b) => (a.daysUntil ?? 9e9) - (b.daysUntil ?? 9e9));
    const el = document.getElementById('today-list');
    if (!list.length) {
      el.innerHTML = `<div class="empty-caught-up">${escapeHtml(t('empty.nothingOnFire'))} <span class="empty-date">${escapeHtml(formatDateHE(state.today))}</span></div>`;
      syncDeskActionbar();
      return;
    }
    el.innerHTML = list.map(deskRow).join('');
    attachRowHandlers(el);
    syncDeskActionbar();
  }

  // A desk row is a checkbox (keyboard-operable; non-color selection = a ✓ box +
  // wash + aria-checked). NO inline done/snooze/note — action lives in the shared
  // batch bar so one tap acts on the whole selection.
  function deskRow(r) {
    const emoji = flagEmoji(r.flag);
    const cls = flagClass(r.flag);
    return `<div class="row desk-row" data-row="${r._row}" role="checkbox" aria-checked="false" tabindex="0">
      <span class="desk-check" aria-hidden="true"></span>
      <div class="desk-row-body">
        <div class="row-top">
          <span class="row-title"><span class="flag ${cls}" aria-hidden="true">${emoji}</span> ${escapeHtml(r.title)}</span>
          <span class="row-meta">${duePhrase(r.daysUntil)}</span>
        </div>
        ${r.notes ? `<div class="row-note">${escapeHtml(r.notes)}</div>` : ''}
      </div>
    </div>`;
  }

  // Selection toggles (click + Space/Enter). V3.3 replaced the .expanded/.snoozing
  // accordion with desk selection — the inline per-row actions are gone.
  function attachRowHandlers(container) {
    container.querySelectorAll('.desk-row[data-row]').forEach(rowEl => {
      rowEl.addEventListener('click', () => toggleDeskSelection(rowEl));
      rowEl.addEventListener('keydown', (ev) => {
        if (ev.key === ' ' || ev.key === 'Enter') { ev.preventDefault(); toggleDeskSelection(rowEl); }
      });
    });
  }
  function toggleDeskSelection(rowEl) {
    const row = rowEl.dataset.row;
    const sel = state.deskSelection;
    const on = !sel.has(row);
    if (on) sel.add(row); else sel.delete(row);
    rowEl.classList.toggle('selected', on);
    rowEl.setAttribute('aria-checked', String(on));
    syncDeskActionbar();
  }
  // Show/hide the batch bar + count from the live selection; collapse the snooze/
  // note sub-rows whenever the selection empties.
  function syncDeskActionbar() {
    const bar = document.getElementById('desk-actionbar');
    if (!bar) return;
    const n = state.deskSelection.size;
    bar.hidden = n === 0;
    const countEl = document.getElementById('desk-sel-count');
    if (countEl) countEl.textContent = n ? t('desk.selected', { n }) : '';
    if (n === 0) collapseDeskSubrows();
  }
  function collapseDeskSubrows() {
    const s = document.getElementById('desk-snooze-row'); if (s) s.hidden = true;
    const nr = document.getElementById('desk-note-row'); if (nr) nr.hidden = true;
  }
  // Toggle one sub-row (snooze chips OR the note composer), never both at once.
  function toggleDeskSubrow(which) {
    const s = document.getElementById('desk-snooze-row');
    const nr = document.getElementById('desk-note-row');
    if (!s || !nr) return;
    if (which === 'snooze') { const open = s.hidden; nr.hidden = true; s.hidden = !open; }
    else { const open = nr.hidden; s.hidden = true; nr.hidden = !open; if (open) document.getElementById('desk-note-input')?.focus(); }
  }
  function selectedReminders() {
    return [...state.deskSelection].map(findReminder).filter(Boolean);
  }
  // After a batch, focus would otherwise fall to <body> (the batch bar that held
  // it is now hidden + the desk re-rendered). Move it to a stable desk anchor so a
  // keyboard/SR user keeps their place. Programmatic focus after a pointer tap
  // won't trip :focus-visible, so touch users see no stray ring.
  function focusDeskAfterBatch() {
    const list = document.getElementById('today-list');
    if (!list) return;
    const firstRow = list.querySelector('.desk-row');
    if (firstRow) { firstRow.focus(); return; }
    list.setAttribute('tabindex', '-1');
    list.focus();
  }

  // ---------------- Coming-up strip (V3.3) ----------------
  // A read-only ±30-day horizontal scroll band with a now-marker. Two sources,
  // date-sorted: WEEK-OUT/MONTH-OUT reminders (the future side) + calendar events
  // (past 30d ↔ +30d, minus today/+1/+2 which the 3-day strip owns). The desk owns
  // overdue/today reminders, so they are NOT repeated here (PO call 2026-06-26:
  // the back-scroll shows past EVENTS only). Opens positioned at "now"; scroll
  // back for the past, forward for what's coming. No write affordance.
  function renderComingUp() {
    const el = document.getElementById('coming-up-strip');
    if (!el) return;
    const items = comingUpItems();
    if (!items.length) {
      el.innerHTML = `<div class="empty">${escapeHtml(t('empty.noUpcoming'))}</div>`;
      return;
    }
    let html = '', placed = false;
    items.forEach(it => {
      if (!placed && it.daysUntil >= 0) { html += comingUpNowMarker(); placed = true; }
      html += comingUpChip(it);
    });
    if (!placed) html += comingUpNowMarker();   // everything is past → marker at the end
    el.innerHTML = html;
    scrollComingUpToNow(el);
  }

  function comingUpItems() {
    const out = [];
    // Future reminders only (WEEK-OUT/MONTH-OUT = daysUntil 2..30). Overdue +
    // fire-today live on the desk; Done/Skipped carry no flag.
    (state.data.reminders || []).forEach(r => {
      if (!r.due) return;
      if (r.flag === 'WEEK OUT' || r.flag === 'MONTH OUT') {
        out.push({ date: r.due, daysUntil: r.daysUntil, kind: 'reminder', glyph: flagEmoji(r.flag), title: r.title });
      }
    });
    // Calendar events across ±30d, EXCEPT today/+1/+2 (owned by the 3-day strip).
    (state.data.calendarEvents || []).forEach(e => {
      if (!e.date) return;
      const du = daysBetween(e.date, state.today);
      if (du < -30 || du > 30 || (du >= 0 && du <= 2)) return;
      out.push({ date: e.date, daysUntil: du, kind: 'event', glyph: '📆', title: e.title, shabbat: e.source === 'shabbat' });
    });
    return out.sort((a, b) => a.date - b.date);
  }

  function comingUpChip(it) {
    const glyph = it.shabbat ? '🕯' : it.glyph;
    return `<div class="coming-up-chip coming-up-${it.kind}${it.shabbat ? ' shabbat' : ''}">
      <div class="cu-top"><span class="cu-glyph" aria-hidden="true">${glyph}</span><span class="cu-date num">${escapeHtml(fmtDate(it.date))}</span></div>
      <div class="cu-title">${escapeHtml(it.title)}</div>
      <div class="cu-due num">${escapeHtml(relDayPhrase(it.daysUntil))}</div>
    </div>`;
  }
  function comingUpNowMarker() {
    return `<div class="coming-up-now" data-now="1"><span class="cu-now-bar" aria-hidden="true"></span><span class="cu-now-label">${escapeHtml(t('timeline.now'))}</span></div>`;
  }
  // Relative-day phrase for the band: future reuses duePhrase (today/tomorrow/in
  // Nd); past reads "yesterday / N days ago" (a past EVENT is not "overdue").
  function relDayPhrase(daysUntil) {
    if (daysUntil == null) return '';
    if (daysUntil >= 0) return duePhrase(daysUntil);
    const abs = -daysUntil;
    if (currentLang() === 'he') {
      if (abs === 1) return 'אתמול';
      if (abs === 2) return 'לפני יומיים';
      return `לפני ${abs} ימים`;
    }
    if (abs === 1) return 'yesterday';
    return `${abs}d ago`;
  }
  // Position the now-marker near the inline-start so the future is the default
  // view and the past is a scroll-back — horizontal only (never scrollIntoView,
  // which would scroll the PAGE to this below-the-fold strip on load). Uses a
  // bounding-rect delta + scrollBy (the modern unified RTL scrollLeft model:
  // 0 = inline-start, negative toward inline-end), so it works in he-RTL + en-LTR.
  function scrollComingUpToNow(el) {
    requestAnimationFrame(() => {
      const marker = el.querySelector('[data-now="1"]');
      if (!marker) return;
      const isRtl = getComputedStyle(el).direction === 'rtl';
      const er = el.getBoundingClientRect();
      const mr = marker.getBoundingClientRect();
      const PEEK = 48;   // leave a sliver of the immediate past visible past the marker
      const delta = isRtl ? (mr.right - er.right) + PEEK : (mr.left - er.left) - PEEK;
      if (Math.abs(delta) > 1) el.scrollBy({ left: delta, behavior: 'auto' });
    });
  }

  // Minutes-since-midnight for an 'HH:MM' start; all-day ('') sorts first as -1.
  // Robust to an un-padded hour ('9:00') a hand-edited Sheet row might carry,
  // which a lexical string sort would mis-order.
  function calMinutes(s) {
    if (!s) return -1;
    const [h, m] = String(s).split(':');
    return (+h || 0) * 60 + (+m || 0);
  }

  // V3.4: the calendar slot is a 3-day scroll-snap strip (today, +1, +2),
  // replacing the single-day list. Exactly 3 panes ALWAYS render so an empty day
  // never collapses the strip and the horizontal snap keeps stable geometry.
  // Read-only — no data-row, no write affordances; events are edited at their
  // source, the strip is a glance surface. Days 3–7 live in the coming-up/Next-7
  // list (📆-tagged), so this stays today+2 with no overlap.
  function render3DayCalendar() {
    const el = document.getElementById('today-cal-strip');
    if (!el) return;
    const locale = currentLang() === 'en' ? 'en-GB' : 'he-IL';
    el.innerHTML = [0, 1, 2].map(offset => {
      const day = new Date(state.today);
      day.setDate(day.getDate() + offset);
      const events = state.data.calendarEvents
        .filter(e => e.date && daysBetween(e.date, day) === 0)
        .sort((a, b) => calMinutes(a.start) - calMinutes(b.start)); // all-day ('') sorts first
      const body = events.length
        ? events.map(renderCalEvent).join('')
        : `<div class="empty">${escapeHtml(t('empty.noEventsDay'))}</div>`;
      return `<div class="cal-day">
        <div class="cal-day-head">
          <span class="cal-day-name">${escapeHtml(dayLabel(offset, day, locale))}</span>
          <span class="cal-day-date num">${escapeHtml(fmtDate(day))}</span>
        </div>
        ${body}
      </div>`;
    }).join('');
  }

  // Day-head label: today / tomorrow / the weekday name for +2 (locale-aware).
  function dayLabel(offset, day, locale) {
    if (offset === 0) return t('cal.today');
    if (offset === 1) return t('cal.tomorrow');
    return day.toLocaleDateString(locale, { weekday: 'long' });
  }

  // One read-only calendar-event card. A Shabbat line (the V3.2 'shabbat' source
  // seam — also covers erev-chag candle-lighting, same 🕯 treatment) gets a 🕯
  // glyph (aria-hidden, decorative — the title + border carry the meaning) + a
  // non-color inline-start border, never hue alone (DESIGN §8). Times are mono (.num).
  function renderCalEvent(e) {
    const isShabbat = e.source === 'shabbat';
    const time = e.start
      ? escapeHtml(e.start) + (e.end ? '–' + escapeHtml(e.end) : '')
      : escapeHtml(t('cal.allDay'));
    return `<div class="row cal-event${isShabbat ? ' shabbat' : ''}">
      <div class="row-top">
        <span class="row-title">${isShabbat ? '<span aria-hidden="true">🕯 </span>' : ''}${escapeHtml(e.title)}</span>
        <span class="row-meta cal-time num">${time}</span>
      </div>
      ${e.location ? `<div class="row-note">${escapeHtml(e.location)}${e.owner ? ' · ' + escapeHtml(e.owner) : ''}</div>` : ''}
    </div>`;
  }

  // ---------------- Drawers ----------------
  // ---------------- Portfolios + bottom-sheet ----------------
  // V3.5: the six domain accordions become a grid of portfolio TILES (glanceable
  // faces) that open ONE shared, data-driven bottom-sheet on tap — never six
  // panels. Money is the hero (overall-% donut + category bar + 7-day sparkline);
  // Health shows initials-avatars with non-color urgency; Goals a simple % bar
  // (the bright-line lives in the sheet, D8); Car/Contracts a next-date count.
  // Education has no Today tile (its data stays parsed, folds into the V3.6
  // timeline). Tiles are <button>s (native keyboard + role); status is never
  // color-only — text + glyph carry it (DESIGN §8).
  function renderPortfolios() {
    const grid = document.getElementById('portfolio-grid');
    if (!grid) return;
    grid.innerHTML = [moneyTile(), timelineTile(), healthTile(), goalsTile(), carTile(), contractsTile()].join('');
    // The money sparkline needs a live <svg> (renderSparkline writes into it).
    renderSparkline(document.getElementById('money-tile-spark'), txnTrend7d());
    grid.querySelectorAll('.tile[data-portfolio]').forEach(tile => {
      tile.addEventListener('click', () => openSheet(tile.dataset.portfolio));
    });
    // A sheet left open across a background reload rebuilds from fresh state.
    if (state.activeSheet) refreshSheetBody();
  }

  // ---- domain selectors (shared by the tile face + the sheet body) ----
  function upcomingHealth() {
    return state.data.health
      .filter(h => h.nextDue && daysBetween(h.nextDue, state.today) <= 60 && daysBetween(h.nextDue, state.today) >= -30)
      .sort((a, b) => a.nextDue - b.nextDue);
  }
  function upcomingRenewals() {
    return state.data.contracts
      .filter(c => c.renewal && daysBetween(c.renewal, state.today) <= 60 && daysBetween(c.renewal, state.today) >= -30)
      .sort((a, b) => a.renewal - b.renewal);
  }
  function moneyTotals() {
    const b = state.data.budget;
    const target = b.reduce((s, x) => s + x.target, 0);
    const actual = b.reduce((s, x) => s + x.actual, 0);
    return { target, actual, over: b.filter(x => x.pct > 1.0), pct: target ? Math.round(100 * actual / target) : 0 };
  }
  function carNextDate() {
    const car = state.data.car[0];
    if (!car) return null;
    return [car.test, car.insurance, car.license].filter(Boolean).sort((a, b) => a - b)[0] || null;
  }
  function goalsAvgPct() {
    const g = state.data.goals;
    return g.length ? Math.round(g.reduce((s, x) => s + (x.pct || 0), 0) / g.length) : null;
  }

  // ---- tile faces ----
  function moneyTile() {
    const m = moneyTotals();
    const status = m.over.length
      ? `<span class="tile-flag" aria-hidden="true">▲</span> ${escapeHtml(t('summary.over', { n: m.over.length }))}`
      : escapeHtml(t('state.allGood'));
    return `<button class="tile tile-money" data-portfolio="money" type="button">
      <div class="tile-head">
        <span class="tile-name">${escapeHtml(t('drawer.money'))}</span>
        <span class="tile-status${m.over.length ? ' is-warn' : ''}">${status}</span>
      </div>
      <div class="tile-money-viz">
        ${donut(m.pct)}
        <div class="tile-money-side">
          <div class="tile-amount">${amountHtml(m.actual)} <span class="tile-amount-of">/ ${amountHtml(m.target)}</span></div>
          ${catBar(state.data.budget)}
          <svg class="sparkline" id="money-tile-spark" viewBox="0 0 80 24"></svg>
        </div>
      </div>
    </button>`;
  }
  function healthTile() {
    const up = upcomingHealth();
    const status = up.length ? t('summary.upcoming', { n: up.length }) : t('state.allGood');
    const avatars = up.slice(0, 5).map(healthAvatar).join('');
    return `<button class="tile" data-portfolio="health" type="button">
      <div class="tile-head">
        <span class="tile-name">${escapeHtml(t('drawer.health'))}</span>
        <span class="tile-status${up.length ? ' is-warn' : ''}">${escapeHtml(status)}</span>
      </div>
      <div class="avatar-row">${avatars || `<span class="tile-allgood" aria-hidden="true">✓</span>`}</div>
    </button>`;
  }
  function goalsTile() {
    const g = state.data.goals;
    const avg = goalsAvgPct();
    const status = t('summary.active', { n: g.length });
    const body = g.length
      ? `<div class="goal-bar" aria-hidden="true"><span class="goal-bar-fill" style="inline-size:${avg}%"></span></div>
         <div class="tile-sub num">${avg}%</div>`
      : `<div class="empty">${escapeHtml(t('empty.noGoals'))}</div>`;
    return `<button class="tile" data-portfolio="goals" type="button">
      <div class="tile-head">
        <span class="tile-name">${escapeHtml(t('drawer.goals'))}</span>
        <span class="tile-status">${escapeHtml(status)}</span>
      </div>
      ${body}
    </button>`;
  }
  function carTile() {
    const nd = carNextDate();
    const days = nd ? daysBetween(nd, state.today) : null;
    const warn = days != null && days < 14;
    // Warn carries a glyph + a due PHRASE (overdue/today/soon) — never color alone.
    // Pre-escaped here, so it's interpolated raw below.
    const status = nd
      ? (warn ? `<span class="tile-flag" aria-hidden="true">▲</span> ${escapeHtml(duePhrase(days))}`
              : `${escapeHtml(t('label.next'))} ${escapeHtml(formatDateHE(nd))}`)
      : '—';
    return `<button class="tile" data-portfolio="car" type="button">
      <div class="tile-head">
        <span class="tile-name">${escapeHtml(t('drawer.car'))}</span>
        <span class="tile-status${warn ? ' is-warn' : ''}">${status}</span>
      </div>
      <div class="tile-kpi num">${days != null ? Math.abs(days) + 'd' : '—'}</div>
    </button>`;
  }
  function contractsTile() {
    const n = upcomingRenewals().length;
    const status = n ? t('summary.within60', { n }) : t('state.allGood');
    return `<button class="tile" data-portfolio="contracts" type="button">
      <div class="tile-head">
        <span class="tile-name">${escapeHtml(t('drawer.contracts'))}</span>
        <span class="tile-status${n ? ' is-warn' : ''}">${escapeHtml(status)}</span>
      </div>
      <div class="tile-kpi num">${n || '—'}</div>
    </button>`;
  }

  // ---- tile viz primitives (all aria-hidden; meaning lives in the adjacent text) ----
  // Single-ring donut: arc = pct of circumference; the % numeral inside carries the
  // meaning (so the ring is non-color-only); >100% reads 'over' via numeral + ▲.
  function donut(pct) {
    const r = 26, c = 2 * Math.PI * r;
    const frac = Math.max(0, Math.min(1, (pct || 0) / 100));
    return `<svg class="donut${pct > 100 ? ' donut-over' : ''}" viewBox="0 0 64 64" aria-hidden="true">
      <circle class="donut-track" cx="32" cy="32" r="${r}" />
      <circle class="donut-fill" cx="32" cy="32" r="${r}" transform="rotate(-90 32 32)" stroke-dasharray="${(frac * c).toFixed(1)} ${c.toFixed(1)}" />
      <text class="donut-pct" x="32" y="33" text-anchor="middle" dominant-baseline="middle">${Math.round(pct || 0)}%</text>
    </svg>`;
  }
  // Proportional bar of the top categories by spend — informational, not urgency,
  // so neutral fills are fine (over-budget is flagged with ▲ in the sheet).
  function catBar(budget) {
    const cats = (budget || []).filter(b => b.actual > 0).sort((a, b) => b.actual - a.actual).slice(0, 6);
    if (!cats.length) return '';
    const total = cats.reduce((s, b) => s + b.actual, 0) || 1;
    const segs = cats.map((b, i) => `<span class="cat-seg cat-seg-${i % 4}" style="flex:${(b.actual / total).toFixed(3)}"></span>`).join('');
    return `<div class="cat-bar" aria-hidden="true">${segs}</div>`;
  }
  // Initials avatar (NO photo — no stored media) + a non-color urgency badge: a
  // glyph + a day-count (3 buckets: overdue / ≤14d / later), never color alone.
  function healthAvatar(h) {
    const initials = (h.person || '?').trim().slice(0, 2);
    const d = daysBetween(h.nextDue, state.today);
    const bucket = d < 0 ? 'over' : d <= 14 ? 'soon' : 'ok';
    const glyph = { over: '🔴', soon: '⚠', ok: '·' }[bucket];
    return `<span class="avatar avatar-${bucket}" title="${escapeHtml(h.person)}">
      <span class="avatar-initials">${escapeHtml(initials)}</span>
      <span class="avatar-badge"><span aria-hidden="true">${glyph}</span><span class="num">${Math.abs(d)}d</span></span>
    </span>`;
  }

  // ---- the shared bottom-sheet body, per domain (reuses the accordions' detail
  // logic: kv lists, recent-txns, the goal bright-line). Rebuilt on every open and
  // on background reload — one instance, never six. ----
  function buildSheet(domain) {
    switch (domain) {
      case 'money': return moneySheet();
      case 'health': return healthSheet();
      case 'goals': return goalsSheet();
      case 'car': return carSheet();
      case 'contracts': return contractsSheet();
      case 'timeline': return timelineSheet();
      default: return '';
    }
  }
  function moneySheet() {
    const budgetRows = state.data.budget.map(b => `
      <div class="kv"><span>${escapeHtml(b.category)}${b.pct > 1.0 ? ' <span class="tile-flag" aria-hidden="true">▲</span>' : ''}</span><span class="v">${amountHtml(b.actual)} / ${amountHtml(b.target)} (${Math.round(b.pct * 100)}%)</span></div>
    `).join('') || `<div class="empty">${escapeHtml(t('empty.noBudget'))}</div>`;
    const recent = (state.data.txns || []).filter(tx => tx.date && isSpendTxn(tx)).sort((a, b) => b.date - a.date).slice(0, 10);
    const txnRows = recent.map(tx => `
      <div class="kv"><span>${escapeHtml(formatDateHE(tx.date))} · ${escapeHtml(tx.desc || tx.account || '')}</span><span class="v">${amountHtml(tx.amount)}</span></div>
    `).join('') || `<div class="empty">${escapeHtml(t('empty.noRecentTxns'))}</div>`;
    return `${budgetRows}<div class="sheet-sub">${escapeHtml(t('sheet.recentTxns'))}</div>${txnRows}`;
  }
  function healthSheet() {
    return upcomingHealth().map(h => `
      <div class="kv"><span>${escapeHtml(h.person)} · ${escapeHtml(h.specialty || h.provider || '')}</span><span class="v">${escapeHtml(formatDateHE(h.nextDue))}</span></div>
    `).join('') || `<div class="empty">${escapeHtml(t('empty.next60Days'))}</div>`;
  }
  function goalsSheet() {
    return state.data.goals.map((g, i) => `
      <div class="kv"><span>${escapeHtml(g.goal)} <span class="row-meta">· ${escapeHtml(g.owner || '')}</span></span><span class="v num">${g.pct}%</span></div>
      <svg class="goal-line" id="sheet-goal-line-${i}" viewBox="0 0 100 40" preserveAspectRatio="none"></svg>
      ${g.milestone ? `<div class="row-note" style="margin:-2px 0 6px">${escapeHtml(t('label.next'))} ${escapeHtml(g.milestone)}</div>` : ''}
    `).join('') || `<div class="empty">${escapeHtml(t('empty.noGoals'))}</div>`;
  }
  function drawSheetGoalLines() {
    state.data.goals.forEach((g, i) => {
      const svg = document.getElementById(`sheet-goal-line-${i}`);
      if (svg) renderGoalLine(svg, { targetStart: 0, targetEnd: 100, current: g.pct, pctTimeElapsed: goalPctTimeElapsed(g) });
    });
  }
  function carSheet() {
    const car = state.data.car[0];
    if (!car) return `<div class="empty">${escapeHtml(t('empty.noVehicle'))}</div>`;
    const rows = [[t('car.annualTest'), car.test], [t('car.insurance'), car.insurance], [t('car.license'), car.license]]
      .filter(([, d]) => d)
      .map(([k, d]) => `<div class="kv"><span>${escapeHtml(k)}</span><span class="v">${escapeHtml(formatDateHE(d))} (${escapeHtml(duePhrase(daysBetween(d, state.today)))})</span></div>`)
      .join('');
    return rows || `<div class="empty">${escapeHtml(t('empty.noVehicle'))}</div>`;
  }
  function contractsSheet() {
    return upcomingRenewals().map(c => `
      <div class="kv"><span>${escapeHtml(c.contract)} · ${escapeHtml(c.provider || '')}</span><span class="v">${escapeHtml(formatDateHE(c.renewal))}</span></div>
    `).join('') || `<div class="empty">${escapeHtml(t('empty.noRenewals'))}</div>`;
  }
  // Headline metric shown in the sheet head (reuses renderKpi).
  function sheetKpi(domain) {
    if (domain === 'money') { const m = moneyTotals(); return { value: m.target ? `${m.pct}%` : '', trend: m.pct > 100 ? 'neg' : 'pos' }; }
    if (domain === 'health') { const n = upcomingHealth().length; return { value: n ? String(n) : '', trend: n ? 'neg' : 'pos' }; }
    if (domain === 'goals') { const a = goalsAvgPct(); return { value: a == null ? '' : `${a}%`, trend: 'pos' }; }
    if (domain === 'car') { const nd = carNextDate(); const d = nd ? daysBetween(nd, state.today) : null; return { value: d == null ? '' : `${d}d`, trend: d != null && d < 14 ? 'neg' : 'pos' }; }
    if (domain === 'contracts') { const n = upcomingRenewals().length; return { value: n ? String(n) : '', trend: n ? 'neg' : 'pos' }; }
    if (domain === 'timeline') { const n = buildTimelineItems().filter(i => i.daysUntil >= 0).length; return { value: n ? String(n) : '', trend: 'pos' }; }
    return { value: '', trend: null };
  }

  // ---- sheet open/close machinery (focus-trap + scroll-lock + focus-return) ----
  function openSheet(domain) {
    state.activeSheet = domain;
    // Each open lands on the documented default lens (DESIGN §2/§9.13: zoom 3mo,
    // all categories) rather than a stale zoom/filter from a previous open.
    if (domain === 'timeline') state.timeline = { zoom: '3mo', filter: 'all' };
    state.sheetReturnFocus = domain;   // re-resolved to a live tile on close (grid may rebuild)
    document.getElementById('sheet-title').textContent = t('drawer.' + domain);
    refreshSheetBody();
    document.getElementById('sheet-scrim').hidden = false;
    const sheet = document.getElementById('sheet');
    sheet.hidden = false;
    requestAnimationFrame(() => sheet.classList.add('open'));   // slide up from hidden
    document.body.classList.add('sheet-open');                  // scroll-lock the page
    const app = document.getElementById('app');
    if (app) app.inert = true;          // background out of the AT/focus tree (aria-modal alone doesn't)
    document.getElementById('sheet-close').focus();
    document.addEventListener('keydown', onSheetKeydown, true);
  }
  function refreshSheetBody() {
    const domain = state.activeSheet;
    if (!domain) return;
    const body = document.getElementById('sheet-body');
    if (body) {
      const st = body.scrollTop;            // preserve read position + the focused control across a bg-reload rebuild
      const tlSel = _timelineFocusSelector();  // the timeline is the only sheet with focusables in its body
      body.innerHTML = buildSheet(domain);
      body.scrollTop = st;
      if (tlSel) { const b = body.querySelector(tlSel); if (b) b.focus(); }
    }
    if (domain === 'goals') drawSheetGoalLines();
    if (domain === 'timeline') wireTimeline();
    const k = sheetKpi(domain);
    renderKpi('sheet', k.value, k.trend);
  }
  // If a timeline zoom/filter control holds focus, return a selector to re-find it
  // after #sheet-body is rebuilt — so a background reload doesn't drop keyboard focus.
  function _timelineFocusSelector() {
    const a = document.activeElement;
    if (!a || !a.dataset) return null;
    if (a.dataset.tlZoom) return `[data-tl-zoom="${a.dataset.tlZoom}"]`;
    if (a.dataset.tlFilter) return `[data-tl-filter="${a.dataset.tlFilter}"]`;
    return null;
  }
  function closeSheet() {
    if (!state.activeSheet) return;
    const sheet = document.getElementById('sheet');
    sheet.classList.remove('open');
    sheet.hidden = true;
    document.getElementById('sheet-scrim').hidden = true;
    document.body.classList.remove('sheet-open');
    const app = document.getElementById('app');
    if (app) app.inert = false;
    document.removeEventListener('keydown', onSheetKeydown, true);
    state.activeSheet = null;
    const dom = state.sheetReturnFocus;
    state.sheetReturnFocus = null;
    // Re-resolve the launching tile live — a background reload may have rebuilt the
    // grid, detaching the node we opened from; query the fresh button by domain.
    const tile = dom && document.querySelector(`.tile[data-portfolio="${dom}"]`);
    if (tile) tile.focus();
  }
  function onSheetKeydown(e) {
    if (e.key === 'Escape') { e.preventDefault(); closeSheet(); return; }
    if (e.key !== 'Tab') return;
    const sheet = document.getElementById('sheet');
    const f = sheet.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  // Card-settlement mirror lines (an immediate-debit card's spend also lands on the
  // bank statement as a merchant-less settlement) are excluded from raw-transaction
  // SPEND views — the per-merchant card line is the real spend, counted once; summing
  // the mirror too would ~double it. Mirrors automation/lib/categorize.EXCLUDED_CATEGORIES.
  function isSpendTxn(tx) { return tx.category !== 'Card Settlement'; }

  // Build a last-7-day spending series from transactions (signed-amount sum per day).
  // Falls back to null if no transactions are available.
  function txnTrend7d() {
    const txns = state.data.txns || [];
    if (!txns.length) return null;
    const days = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date(state.today);
      d.setDate(d.getDate() - i);
      const sum = txns
        .filter(t => t.date && daysBetween(t.date, d) === 0 && isSpendTxn(t))
        .reduce((s, t) => s + Math.abs(t.amount || 0), 0);
      days.push(sum);
    }
    if (days.every(v => v === 0)) return null;
    return days;
  }

  // ---------------- Cross-domain timeline (V3.6) ----------------
  // A read-only chronological flattening of every dated row across the Sheet's
  // domains into one time axis, opened from the Timeline portfolio tile. The two
  // pure functions below are the ratified contract (graduated to SPEC §7.6):
  // domainCategory (the filter map) + buildTimelineItems (the milestone-inclusion
  // rule). Read-only — items are edited at their source tab, never here.

  // Filterable categories. The reminder Domain is free text (SPEC §6.1 col B:
  // Car/Health/Education/Finance/Contracts/Goals/Other) and maps near-identity
  // (lowercased); calendar/other are assigned by source. Anything unrecognised
  // falls to 'other' and is STILL shown — never dropped.
  const TIMELINE_CATEGORIES = ['finance', 'health', 'car', 'education', 'goals', 'contracts', 'calendar', 'other'];
  function domainCategory(domain) {
    const d = String(domain || '').trim().toLowerCase();
    return TIMELINE_CATEGORIES.includes(d) ? d : 'other';
  }

  // Zoom rungs (exponential 1wk→5yr). The visible window is today−tail … today+days;
  // a short recent-past tail gives the now-marker context without burying the future.
  const TIMELINE_ZOOMS = [
    { key: '1wk', days: 7 },
    { key: '1mo', days: 31 },
    { key: '3mo', days: 92 },
    { key: '1yr', days: 366 },
    { key: '5yr', days: 1830 },
  ];
  const TIMELINE_PAST_TAIL = 14;   // days of recent past kept above the now-marker
  const TIMELINE_MAX_DAYS = 1830;  // +5y horizon (5×366 — a deliberate round over-approximation of 5y); the hard inclusion ceiling

  // The milestone-inclusion rule (SPEC §7.6): one item per dated field across every
  // domain — done/skipped/archived reminders, undated rows, and dates outside
  // [−tail, +5y] excluded. An unmapped reminder Domain still appears (→ 'other').
  function buildTimelineItems() {
    const d = state.data;
    if (!d) return [];
    const items = [];
    const add = (date, title, category, meta) => {
      if (!(date instanceof Date) || isNaN(date)) return;
      if (!String(title || '').trim()) return;   // a dated row with no label is not a useful milestone
      const daysUntil = daysBetween(date, state.today);
      if (daysUntil < -TIMELINE_PAST_TAIL || daysUntil > TIMELINE_MAX_DAYS) return;
      items.push({ date, daysUntil, title, category, meta: meta || '' });
    };
    (d.reminders || []).forEach(r => {
      const st = String(r.status || '').toLowerCase();
      if (st === 'done' || st === 'skipped') return;   // terminal statuses — matches flagFor (Sent/Snoozed/Overdue stay)
      add(r.due, r.title, domainCategory(r.domain), r.owner);
    });
    (d.calendarEvents || []).forEach(e => add(e.date, e.title, 'calendar', e.start || ''));
    (d.goals || []).forEach(g => add(g.targetDate, g.goal, 'goals', g.pct != null ? g.pct + '%' : ''));
    (d.health || []).forEach(h => add(h.nextDue, [h.person, h.specialty || h.provider].filter(Boolean).join(' · '), 'health', h.action));
    (d.car || []).forEach(c => {
      add(c.test, t('car.annualTest'), 'car', c.vehicle);
      add(c.insurance, t('car.insurance'), 'car', c.vehicle);
      add(c.license, t('car.license'), 'car', c.vehicle);
    });
    (d.education || []).forEach(e => add(e.nextDate, [e.child, e.type].filter(Boolean).join(' · '), 'education', e.action));
    (d.contracts || []).forEach(c => add(c.renewal, [c.contract, c.provider].filter(Boolean).join(' · '), 'contracts', ''));
    return items.sort((a, b) => a.date - b.date);
  }

  // ---- timeline tile face (count of upcoming items + the nearest one) ----
  function timelineTile() {
    const upcoming = buildTimelineItems().filter(i => i.daysUntil >= 0);
    const next = upcoming[0];
    const warn = !!next && next.daysUntil <= 14;   // 'soon' boundary — matches timelineItemHtml + healthAvatar
    const status = next
      ? (warn ? `<span class="tile-flag" aria-hidden="true">▲</span> ${escapeHtml(duePhrase(next.daysUntil))}`
              : `${escapeHtml(t('label.next'))} ${escapeHtml(formatDateHE(next.date))}`)
      : '—';
    return `<button class="tile" data-portfolio="timeline" type="button">
      <div class="tile-head">
        <span class="tile-name">${escapeHtml(t('drawer.timeline'))}</span>
        <span class="tile-status${warn ? ' is-warn' : ''}">${status}</span>
      </div>
      <div class="tile-kpi num">${upcoming.length || '—'}</div>
    </button>`;
  }

  // ---- timeline sheet body: sticky controls (zoom rungs + filter chips) + the track ----
  function timelineSheet() {
    const zooms = TIMELINE_ZOOMS.map(z =>
      `<button class="tl-zoom" type="button" data-tl-zoom="${z.key}" aria-pressed="${state.timeline.zoom === z.key}">${escapeHtml(t('timeline.zoom.' + z.key))}</button>`
    ).join('');
    const chips = ['all', ...TIMELINE_CATEGORIES].map(c =>
      `<button class="tl-chip" type="button" data-tl-filter="${c}" aria-pressed="${state.timeline.filter === c}">${escapeHtml(t('timeline.cat.' + c))}</button>`
    ).join('');
    return `<div class="tl-controls">
      <div class="tl-zooms" role="group" aria-label="${escapeHtml(t('timeline.zoomLabel'))}">${zooms}</div>
      <div class="tl-chips" role="group" aria-label="${escapeHtml(t('timeline.filterLabel'))}">${chips}</div>
    </div>
    <div id="tl-track" class="tl-track">${timelineTrackHtml()}</div>`;
  }
  function timelineTrackHtml() {
    const z = TIMELINE_ZOOMS.find(x => x.key === state.timeline.zoom) || TIMELINE_ZOOMS[2];
    const f = state.timeline.filter;
    const items = buildTimelineItems().filter(i => i.daysUntil <= z.days && (f === 'all' || i.category === f));
    if (!items.length) return `<div class="empty">${escapeHtml(t('empty.noMilestones'))}</div>`;
    const nowMarker = `<div class="tl-now"><span class="tl-now-label">${escapeHtml(t('timeline.now'))}</span></div>`;
    let html = '', placed = false;
    items.forEach(i => {
      if (!placed && i.daysUntil >= 0) { html += nowMarker; placed = true; }   // marker before the first future/today item
      html += timelineItemHtml(i);
    });
    if (!placed) html += nowMarker;   // every shown item is in the past tail → marker at the foot
    return html;
  }
  // One read-only timeline row. Urgency is carried by the glyph + the due phrase
  // (text), never color alone (DESIGN §8); the inline-start border is a redundant
  // cue. The muted category tag keeps the cross-domain mix legible at a glance.
  function timelineItemHtml(i) {
    const bucket = i.daysUntil < 0 ? 'over' : i.daysUntil <= 14 ? 'soon' : 'ok';
    const glyph = { over: '🔴', soon: '⚠', ok: '·' }[bucket];
    return `<div class="tl-item tl-${bucket}">
      <span class="tl-glyph" aria-hidden="true">${glyph}</span>
      <span class="tl-date num">${escapeHtml(fmtDate(i.date))}</span>
      <span class="tl-body">
        <span class="tl-title">${escapeHtml(i.title)}</span>
        <span class="tl-cat">${escapeHtml(t('timeline.cat.' + i.category))}${i.meta ? ' · ' + escapeHtml(i.meta) : ''}</span>
      </span>
      <span class="tl-due num">${escapeHtml(duePhrase(i.daysUntil))}</span>
    </div>`;
  }
  // Wire the zoom/filter controls each time the sheet body is built. A control
  // click mutates view state and swaps ONLY #tl-track (+ the aria-pressed flags),
  // so the clicked button keeps focus — never rebuilds the whole body (which would
  // drop focus). innerHTML rebuilds discard old buttons, so re-binding can't leak.
  function wireTimeline() {
    const body = document.getElementById('sheet-body');
    if (!body) return;
    body.querySelectorAll('[data-tl-zoom]').forEach(b =>
      b.addEventListener('click', () => { state.timeline.zoom = b.dataset.tlZoom; updateTimelineView(); }));
    body.querySelectorAll('[data-tl-filter]').forEach(b =>
      b.addEventListener('click', () => { state.timeline.filter = b.dataset.tlFilter; updateTimelineView(); }));
  }
  function updateTimelineView() {
    const body = document.getElementById('sheet-body');
    if (!body) return;
    body.querySelectorAll('[data-tl-zoom]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.tlZoom === state.timeline.zoom)));
    body.querySelectorAll('[data-tl-filter]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.tlFilter === state.timeline.filter)));
    const track = document.getElementById('tl-track');
    if (track) track.innerHTML = timelineTrackHtml();
  }

  // Estimate % of the goal's time window that has elapsed (0..100).
  function goalPctTimeElapsed(g) {
    if (!g.targetDate) return 0;
    const total = Math.max(1, daysBetween(g.targetDate, new Date(g.targetDate.getFullYear(), g.targetDate.getMonth() - 3, g.targetDate.getDate())));
    const elapsed = total - Math.max(0, daysBetween(g.targetDate, state.today));
    return Math.max(0, Math.min(100, Math.round((elapsed / total) * 100)));
  }

  // ---------------- Sunday view ----------------
  function renderSunday() {
    const start = new Date(state.today);
    const dow = start.getDay();
    // Sunday = 0; Israeli week starts Sunday.
    const daysToSunday = dow === 0 ? 0 : 7 - dow;
    const sundayStart = new Date(start);
    sundayStart.setDate(start.getDate() + daysToSunday);
    const weekEnd = new Date(sundayStart);
    weekEnd.setDate(sundayStart.getDate() + 7);

    document.getElementById('sunday-week').textContent = `${fmtDateShort(sundayStart)} — ${fmtDateShort(weekEnd)}`;

    // Week ahead
    const events = state.data.calendarEvents
      .filter(e => e.date && e.date >= sundayStart && e.date < weekEnd)
      .sort((a, b) => a.date - b.date);
    document.getElementById('sunday-week-ahead').innerHTML = events.length
      ? events.map(e => `<div class="kv"><span>${fmtDate(e.date)} ${e.start ? '· ' + e.start : ''} — ${escapeHtml(e.title)}</span><span class="v">${escapeHtml(e.owner || '')}</span></div>`).join('')
      : `<div class="empty">${escapeHtml(t('empty.nothingThisWeek'))}</div>`;

    // Reminders firing this week
    const weekRem = state.data.reminders
      .filter(r => r.daysUntil != null && r.daysUntil >= 0 && r.daysUntil <= 7 && r.status !== 'Done')
      .sort((a, b) => a.daysUntil - b.daysUntil);
    document.getElementById('sunday-reminders').innerHTML = weekRem.length
      ? weekRem.map(r => `<div class="kv"><span>${flagEmoji(r.flag)} ${escapeHtml(r.title)}</span><span class="v">${fmtDate(r.due)}</span></div>`).join('')
      : `<div class="empty">${escapeHtml(t('empty.noUpcoming'))}</div>`;

    // Overdue
    const overdue = state.data.reminders.filter(r => r.flag === 'OVERDUE').sort((a, b) => a.daysUntil - b.daysUntil);
    document.getElementById('sunday-overdue').innerHTML = overdue.length
      ? overdue.map(r => `<div class="kv"><span>🔴 ${escapeHtml(r.title)}</span><span class="v">${duePhrase(r.daysUntil)}</span></div>`).join('')
      : `<div class="empty">${escapeHtml(t('empty.noOverdue'))}</div>`;

    // Money
    const totalT = state.data.budget.reduce((s, b) => s + b.target, 0);
    const totalA = state.data.budget.reduce((s, b) => s + b.actual, 0);
    const over = state.data.budget.filter(b => b.pct > 1.0);
    document.getElementById('sunday-money').innerHTML = `
      <div class="kv"><span>${escapeHtml(t('sunday.monthToDate'))}</span><span class="v">${amountHtml(totalA)} / ${amountHtml(totalT)} (${totalT ? Math.round(100 * totalA / totalT) : 0}%)</span></div>
      ${over.length ? over.map(b => `<div class="kv"><span>⚠ ${escapeHtml(b.category)}</span><span class="v">${Math.round(b.pct * 100)}%</span></div>`).join('') : `<div class="row-note" style="padding:6px 0">${escapeHtml(t('sunday.noOverBudget'))}</div>`}
    `;

    // Goals
    document.getElementById('sunday-goals').innerHTML = state.data.goals.map(g => `
      <div class="kv"><span>${escapeHtml(g.goal)} <span class="pill">${escapeHtml(g.owner || '')}</span><span class="pill">${escapeHtml(g.status || '')}</span></span><span class="v">${g.pct}%</span></div>
      ${g.milestone ? `<div class="row-note" style="padding: 0 0 6px">${escapeHtml(t('label.next'))} ${escapeHtml(g.milestone)}</div>` : ''}
    `).join('') || `<div class="empty">${escapeHtml(t('empty.noGoals'))}</div>`;

    // Data hygiene
    const placeholderPeople = state.data.people.filter(p => (p['Name'] || '').startsWith('['));
    const placeholderGoals = state.data.goals.filter(g => g.goal.startsWith('['));
    const hygiene = [];
    if (placeholderPeople.length) hygiene.push(t('sunday.hygienePeople', { n: placeholderPeople.length }));
    if (placeholderGoals.length) hygiene.push(t('sunday.hygieneGoals', { n: placeholderGoals.length }));
    document.getElementById('sunday-hygiene').innerHTML = hygiene.length
      ? hygiene.map(h => `<div class="kv"><span>${escapeHtml(h)}</span><span class="v">—</span></div>`).join('')
      : `<div class="empty">${escapeHtml(t('empty.allClean'))}</div>`;
  }

  // ---------------- Settings ----------------
  function renderSettings() {
    const acc = document.getElementById('settings-account');
    if (cfg.DEMO_MODE) {
      acc.innerHTML = `${escapeHtml(t('settings.demoModeStatus'))}<div class="row-note">${escapeHtml(t('settings.demoNoAccount'))}</div>`;
    } else if (state.user) {
      acc.innerHTML = `${escapeHtml(t('settings.signedInAs', { name: state.user.name }))}<div class="row-note">${escapeHtml(state.user.email)}</div>`;
    } else {
      acc.innerHTML = escapeHtml(t('settings.notSignedIn'));
    }
    document.getElementById('settings-sheetid').value = cfg.SHEET_ID;
    document.getElementById('settings-demo').value = String(cfg.DEMO_MODE);
    // Language toggle active state.
    const lang = currentLang();
    document.querySelectorAll('[data-lang]').forEach(b => {
      b.classList.toggle('primary', b.dataset.lang === lang);
    });
    // Theme toggle active state.
    const theme = localStorage.getItem('familyinc.theme') || 'auto';
    document.querySelectorAll('[data-theme]').forEach(b => {
      b.classList.toggle('primary', b.dataset.theme === theme);
    });
    renderQueue();
  }

  function renderQueue() {
    const q = document.getElementById('settings-queue');
    if (!state.pendingWrites.length) { q.textContent = t('empty.noQueuedWrites'); return; }
    q.innerHTML = state.pendingWrites.map(w => `<div class="kv"><span>${w.kind} · row ${w.row}</span><span class="v">${w.queuedAt}</span></div>`).join('');
  }

  // ---------------- Write-back ----------------
  function findReminder(rowNum) {
    return state.data.reminders.find(r => String(r._row) === String(rowNum));
  }

  // Lane C — true only when the Reminders columns resolved cleanly. Fails CLOSED
  // (absent data/cols → not writable): a write guard must pause, never assume.
  // Write handlers no-op + toast rather than hit the wrong column.
  function remindersWritable() {
    return !!(state.data && state.data.reminderCols && state.data.reminderCols.ok);
  }
  // Resolve a Reminders write range by HEADER NAME, e.g. remRange('Due Date', 7)
  // → 'Reminders!D7' — never a hardcoded column letter.
  function remRange(name, rowNum) {
    const cols = state.data && state.data.reminderCols && state.data.reminderCols.cols;
    const idx = cols && cols[name];
    return idx ? `${cfg.TABS.reminders}!${colLetter(idx)}${rowNum}` : null;
  }

  // ---- Desk batch write-backs (V3.3) ----
  // Each fans the current desk selection out to ONE applyWrites batch. SPEC §6.1
  // write contract: intent columns + M, N (on completion) + always O, every
  // column resolved by HEADER NAME (Lane C), never a hardcoded letter. A selection
  // of one is just the n=1 case — there is no separate single-row path anymore.

  async function handleBatchDone() {
    if (!remindersWritable()) { toast(t('toast.writesPaused')); return; }
    const rows = selectedReminders();
    if (!rows.length) return;
    const now = new Date();
    const ts = fmtISOts(now);
    const userName = (state.user && state.user.name) || 'Dashboard';
    const writes = [];
    rows.forEach(r => {
      const rowNum = r._row;
      r.status = 'Done'; r.flag = '';
      r.lastDoneBy = userName; r.doneAt = now; r.writeQueueTombstone = now;
      // Col H (Last Sent) is ENGINE-owned — never written except to clear it on the
      // §7.1 recurrence bump below.
      writes.push({ range: remRange('Status', rowNum), value: 'Done' });
      writes.push({ range: remRange('LastDoneBy', rowNum), value: userName });
      writes.push({ range: remRange('DoneAt', rowNum), value: ts });
      writes.push({ range: remRange('WriteQueue_Tombstone', rowNum), value: ts, tomb: true });
      // Bump recurring (mirror of automation/lib/dates.bump_due — keep in sync).
      // Each recurring row adds its own bump triplet to the batch (the build-plan
      // "batch-done multiplies the bump write set" note — handled per row here).
      if (r.recurrence && r.recurrence !== 'One-off' && r.due) {
        const bumped = bumpDate(r.due, r.recurrence);
        if (bumped) {
          writes.push({ range: remRange('Due Date', rowNum), value: fmtISO(bumped) });
          writes.push({ range: remRange('Status', rowNum), value: 'Pending' });
          writes.push({ range: remRange('Last Sent', rowNum), value: '' });
          r.due = bumped; r.status = 'Pending';
          r.daysUntil = daysBetween(bumped, state.today);
          r.flag = flagFor(r.daysUntil, r.status);
        }
        // Unbumpable period (Custom/unknown): row stays Done; the engine flags it
        // for review (logs/engine_flags.jsonl) instead of either side guessing.
      }
    });
    state.deskSelection.clear();
    await applyWrites(writes, batchLabel('done', rows));
    renderAll();
    focusDeskAfterBatch();
  }

  // Absolute snooze (V3.3, D4): write Due = an ABSOLUTE date (today + offset, or a
  // picked date), NOT Due += N. So an overdue row's daysUntil goes ≥ 0 and flagFor
  // drops OVERDUE — the +Nd-from-due path could leave an already-late row overdue.
  async function handleBatchSnooze(absDate) {
    if (!remindersWritable()) { toast(t('toast.writesPaused')); return; }
    if (!(absDate instanceof Date) || isNaN(absDate)) return;
    const rows = selectedReminders();
    if (!rows.length) return;
    const iso = fmtISO(absDate);
    const ts = fmtISOts(new Date());
    const writes = [];
    rows.forEach(r => {
      const rowNum = r._row;
      r.due = absDate; r.status = 'Snoozed';
      r.daysUntil = daysBetween(absDate, state.today);
      r.flag = flagFor(r.daysUntil, r.status);
      writes.push({ range: remRange('Due Date', rowNum), value: iso });
      writes.push({ range: remRange('Status', rowNum), value: 'Snoozed' });
      writes.push({ range: remRange('WriteQueue_Tombstone', rowNum), value: ts, tomb: true });
    });
    const di = document.getElementById('desk-snooze-date'); if (di) di.value = '';   // re-arm the picker (a repeat of the same date fires no 'change')
    state.deskSelection.clear();
    await applyWrites(writes, batchLabel('snooze', rows, absDate));
    renderAll();
    focusDeskAfterBatch();
  }

  async function handleBatchNote() {
    if (!remindersWritable()) { toast(t('toast.writesPaused')); return; }
    const input = document.getElementById('desk-note-input');
    const text = ((input && input.value) || '').trim();
    if (!text) return;
    const rows = selectedReminders();
    if (!rows.length) return;
    const stamp = `[${fmtISO(new Date())} ${state.user?.name || 'You'}]`;
    const ts = fmtISOts(new Date());
    const writes = [];
    rows.forEach(r => {
      const rowNum = r._row;
      const newNotes = (r.notes ? r.notes + ' \n' : '') + `${stamp} ${text}`;
      r.notes = newNotes;
      writes.push({ range: remRange('Notes', rowNum), value: newNotes });
      writes.push({ range: remRange('WriteQueue_Tombstone', rowNum), value: ts, tomb: true });
    });
    if (input) input.value = '';
    state.deskSelection.clear();
    await applyWrites(writes, batchLabel('note', rows));
    renderAll();
    focusDeskAfterBatch();
  }

  // One toast label for the batch — n=1 names the row, n>1 counts.
  function batchLabel(kind, rows, date) {
    const n = rows.length;
    if (kind === 'done') return n === 1 ? t('action.markedDone', { title: rows[0].title }) : t('action.doneN', { n });
    if (kind === 'snooze') {
      const ds = formatDateHE(date);
      return n === 1 ? t('action.snoozedTo', { title: rows[0].title, date: ds }) : t('action.snoozedN', { n, date: ds });
    }
    if (kind === 'note') return n === 1 ? t('action.noteAdded') : t('action.noteAddedN', { n });
    return '';
  }

  // Mirror of automation/lib/dates.bump_due (SPEC §7.1) — same periods, same
  // clamp-to-month-end rule (Feb-29 → Feb-28, Jan-31 +1mo → Feb-28/29). JS
  // setMonth() overflows instead of clamping, so we clamp by hand. Unknown
  // periods (incl. Custom) return null: no bump, engine flags for review.
  function bumpDate(d, recurrence) {
    const months = { Monthly: 1, Quarterly: 3, Yearly: 12 }[recurrence];
    if (recurrence === 'Weekly') {
      const x = new Date(d);
      x.setDate(x.getDate() + 7);
      return x;
    }
    if (!months) return null;
    const total = d.getFullYear() * 12 + d.getMonth() + months;
    const y = Math.floor(total / 12), m = total % 12;
    const lastDay = new Date(y, m + 1, 0).getDate();
    return new Date(y, m, Math.min(d.getDate(), lastDay));
  }

  // Push writes onto the offline queue, capped at MAX_PENDING_WRITES (SPEC §7.6
  // / DESIGN §6). At the cap we warn ONCE and drop the writes rather than grow
  // the queue unboundedly — silent unbounded growth was the prior bug (B8).
  // Returns true if the writes were queued, false if dropped at the cap.
  function enqueueWrites(writes) {
    if (state.pendingWrites.length >= MAX_PENDING_WRITES) {
      if (!state.queueFullWarned) {
        toast(t('toast.queueFull', { max: MAX_PENDING_WRITES }));
        state.queueFullWarned = true;
      }
      return false;
    }
    writes.forEach(w => state.pendingWrites.push({ kind: 'update', row: extractRow(w.range), range: w.range, value: w.value, tomb: !!w.tomb, queuedAt: new Date().toISOString() }));
    localStorage.setItem(QUEUE_KEY, JSON.stringify(state.pendingWrites));
    renderQueue();
    return true;
  }

  async function applyWrites(writes, label) {
    if (cfg.DEMO_MODE) {
      toast(t('toast.demoPrefix', { label }));
      return;
    }
    if (!navigator.onLine || !state.gapiReady) {
      if (enqueueWrites(writes)) toast(t('toast.queuedOffline', { label }));
      return;
    }
    try {
      const data = writes.map(w => ({ range: w.range, values: [[w.value]] }));
      await gapi.client.sheets.spreadsheets.values.batchUpdate({
        spreadsheetId: cfg.SHEET_ID,
        resource: { valueInputOption: 'USER_ENTERED', data },
      });
      toast(label);
    } catch (e) {
      console.error('Write failed', e);
      if (enqueueWrites(writes)) toast(t('toast.queued', { label }));
    }
  }
  function extractRow(range) { return (range.match(/(\d+)$/) || [])[1] || ''; }

  async function flushQueue() {
    if (!state.pendingWrites.length || cfg.DEMO_MODE) return;
    const queue = state.pendingWrites.slice();
    // SPEC §8.3: the tombstone is written AT FLUSH — the engine's 6h race
    // window starts when the write lands on the Sheet, not when the offline
    // tap happened. Refresh every tombstone value to now; everything else
    // flushes as queued (in tap order). The tombstone is flagged at enqueue by
    // FIELD (w.tomb, Lane C) — never a hardcoded column letter, which could
    // shift if a non-write column left of it is removed.
    const flushTs = fmtISOts(new Date());
    try {
      await gapi.client.sheets.spreadsheets.values.batchUpdate({
        spreadsheetId: cfg.SHEET_ID,
        resource: {
          valueInputOption: 'USER_ENTERED',
          data: queue.map(w => ({
            range: w.range,
            values: [[w.tomb ? flushTs : w.value]],
          })),
        },
      });
      state.pendingWrites = [];
      state.queueFullWarned = false;   // queue drained — re-arm the one-shot cap warning
      localStorage.setItem(QUEUE_KEY, JSON.stringify([]));
      toast(t('toast.flushed', { n: queue.length }));
      renderQueue();
    } catch (e) {
      console.warn('Queue flush failed', e);
    }
  }

  // ---------------- HTML helpers ----------------
  function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  // ---------------- Tabs & UI shell ----------------
  function switchTab(name) {
    state.tab = name;
    document.querySelectorAll('nav.tabbar button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
    document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === `view-${name}`));
  }
  function showApp() {
    document.getElementById('signin-screen').hidden = true;
    document.getElementById('app').hidden = false;
  }
  function showSignIn() {
    document.getElementById('signin-screen').hidden = false;
    document.getElementById('app').hidden = true;
  }

  // ---------------- Boot ----------------
  async function boot() {
    // Apply chrome strings to static markup BEFORE first paint of the shell.
    applyChromeStrings();

    // Restore queue
    try { state.pendingWrites = JSON.parse(localStorage.getItem(QUEUE_KEY)) || []; } catch {}

    // Tab clicks
    document.querySelectorAll('nav.tabbar button').forEach(b => b.addEventListener('click', () => switchTab(b.dataset.tab)));

    // Sign-in screen buttons
    document.getElementById('signin-btn').addEventListener('click', requestSignIn);
    document.getElementById('demo-link').addEventListener('click', (e) => {
      e.preventDefault();
      cfg.DEMO_MODE = true;
      showApp();
      loadAll();
    });

    // Settings buttons
    document.getElementById('switch-account-btn').addEventListener('click', switchAccount);
    document.getElementById('signout-btn').addEventListener('click', signOut);
    document.getElementById('refresh-btn').addEventListener('click', loadAll);

    // Bottom-sheet dismissers (V3.5): the close button + tapping the scrim. The
    // icon-only close button is named via data-i18n-aria (the V3.8 aria walker).
    document.getElementById('sheet-close').addEventListener('click', closeSheet);
    document.getElementById('sheet-scrim').addEventListener('click', closeSheet);

    // Desk batch action bar (V3.3). The bar markup is static, so wire it ONCE here;
    // renderToday only fills #today-list + toggles the bar's visibility/count. The
    // snooze chips resolve to ABSOLUTE dates (today + offset); the date picker any day.
    const deskBar = document.getElementById('desk-actionbar');
    if (deskBar) {
      deskBar.querySelector('[data-batch="done"]')?.addEventListener('click', handleBatchDone);
      deskBar.querySelector('[data-batch="snooze"]')?.addEventListener('click', () => toggleDeskSubrow('snooze'));
      deskBar.querySelector('[data-batch="note"]')?.addEventListener('click', () => toggleDeskSubrow('note'));
      deskBar.querySelectorAll('[data-snooze-days]').forEach(chip =>
        chip.addEventListener('click', () => {
          const target = new Date(state.today);
          target.setDate(target.getDate() + parseInt(chip.dataset.snoozeDays, 10));
          handleBatchSnooze(target);
        }));
      const dateInput = document.getElementById('desk-snooze-date');
      if (dateInput) {
        dateInput.min = fmtISO(state.today);   // discourage snoozing into the past
        // Reject a past date even if a UA lets one slip past the min guard (DESIGN §9 #17).
        dateInput.addEventListener('change', () => { const d = parseDate(dateInput.value); if (d && daysBetween(d, state.today) >= 0) handleBatchSnooze(d); });
      }
      // aria-labels for the snooze row, date picker, and note textarea are now
      // declarative (data-i18n-aria, applied by applyChromeStrings at boot).
      document.getElementById('desk-note-send')?.addEventListener('click', handleBatchNote);
    }
    document.getElementById('settings-save').addEventListener('click', async () => {
      const newSheetId = document.getElementById('settings-sheetid').value.trim();
      const newDemoMode = document.getElementById('settings-demo').value === 'true';

      // D3: Validate Sheet ID format before saving (unless demo mode or blank/unchanged).
      if (!newDemoMode && newSheetId && newSheetId !== cfg.SHEET_ID) {
        // Google Sheets IDs are 44-char base64url strings.
        if (!/^[A-Za-z0-9_-]{10,}$/.test(newSheetId)) {
          toast(t('toast.sheetIdInvalid'));
          return;
        }
        // Test-read one cell to catch typos before committing.
        if (state.gapiReady) {
          const saveBtn = document.getElementById('settings-save');
          saveBtn.disabled = true;
          try {
            await gapi.client.sheets.spreadsheets.values.get({
              spreadsheetId: newSheetId,
              range: 'A1',
            });
          } catch (e) {
            toast(t('toast.sheetIdTestFailed', { err: e.result?.error?.message || e.message || 'unknown' }));
            saveBtn.disabled = false;
            return;
          } finally {
            saveBtn.disabled = false;
          }
        }
      }

      cfg.SHEET_ID = newSheetId;
      cfg.DEMO_MODE = newDemoMode;
      localStorage.setItem('family_inc_config_override', JSON.stringify({ SHEET_ID: cfg.SHEET_ID, DEMO_MODE: cfg.DEMO_MODE }));
      location.reload();
    });

    // Restore config overrides (Sheet ID / demo flag) from a previous Settings save
    try {
      const o = JSON.parse(localStorage.getItem('family_inc_config_override'));
      if (o) Object.assign(cfg, o);
    } catch {}

    // Language toggle clicks (Settings → Language section).
    // Persist preference to localStorage then reload so the pre-paint script
    // applies the correct lang/dir on next boot.
    document.querySelectorAll('[data-lang]').forEach(b => {
      b.addEventListener('click', () => {
        const newLang = b.dataset.lang;
        try { localStorage.setItem('familyinc.lang', newLang); } catch {}
        location.reload();
      });
    });

    // Theme toggle clicks (Settings → Appearance section).
    // Persist preference to localStorage; 'auto' removes the attribute entirely
    // so the CSS media query takes over. Reload for clean pre-paint application.
    document.querySelectorAll('[data-theme]').forEach(b => {
      b.addEventListener('click', () => {
        const val = b.dataset.theme;
        try {
          if (val === 'auto') { localStorage.removeItem('familyinc.theme'); }
          else { localStorage.setItem('familyinc.theme', val); }
        } catch {}
        location.reload();
      });
    });

    // Online → flush queue
    window.addEventListener('online', () => flushQueue());

    if (cfg.DEMO_MODE) {
      showApp();
      await loadAll();
      return;
    }
    if (!cfg.CLIENT_ID || cfg.CLIENT_ID.startsWith('PASTE_')) {
      showSignIn();
      document.getElementById('signin-btn').textContent = t('signin.notConfigured');
      document.getElementById('signin-btn').disabled = true;
      return;
    }
    await initAuth();
    if (!state.token) showSignIn();
  }

  document.addEventListener('DOMContentLoaded', boot);
})();

=== End: dashboard/app.js ===

=== File: dashboard/styles.css ===
/* Family inc. dashboard — single sheet of styles. Boring on purpose. */

:root {
  /* ── v3 cool palette · canonical names (V3_RECONCILE token block) ── */
  --bg: #EBEEF2;            /* page */
  --tile: #FFFFFF;         /* card / sheet surface */
  --tile2: #E9EDF3;        /* recessed surface */
  --ink: #12151C;          /* text */
  --muted: #5F6878;        /* secondary text (darkened to clear AA) */
  --line: #E1E5EB;         /* hairlines */
  --accent: #2C57C8;       /* brand blue (single brand color) */
  --soft: rgba(44,87,200,.10);  /* accent wash */
  --on-accent: #FFFFFF;    /* text on an --accent fill (e.g. pressed chip) — paired per theme for AA */
  --green: #2F8559;        /* sage — success (AA) */
  --amber: #8A5E12;        /* amber — warning (darkened to clear AA) */
  --red: #C4403B;          /* terracotta — alert */
  --blue: #4A6FA5;         /* info — calendar event times (.cal-time); theme-paired (dark below) */
  --shadow: 0 1px 2px rgba(0,0,0,.03), 0 8px 22px rgba(0,0,0,.05);
  --sheet-shadow: 0 -8px 40px rgba(18,21,28,.22);
  --rad: 20px;             /* cards / sheets */
  --rad-sm: 8px;           /* inputs / small chips */
  --font: 'Inter', 'Heebo', -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
  --font-mono: 'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, "Courier New", monospace;
  /* V3.8 alias endgame: the V3.1 back-compat aliases (--card/--border/--ink-dim/
     --orange/--yellow/--radius) are retired — every selector now uses the canonical
     token (a zero-ref audit confirmed none remained). --blue stays: it is a real
     info token (calendar times), not an alias, and is theme-paired in every block. */
}

/* Dark mode is PROVISIONAL (prior hues, cool-retoned) — gets its own pass later.
   Theme blocks set only canonical names; the :root aliases above track them automatically. */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #14161B;
    --tile: #1C2027;
    --tile2: #23262E;
    --ink: #E7E9ED;
    --muted: #A1AAB8;        /* lighter on dark for AA */
    --line: #2A2E36;
    --accent: #6E8BE8;       /* cool blue (dark) */
    --soft: rgba(110,139,232,.16);
    --on-accent: #12151C;    /* dark ink on the light dark-accent (5.67:1) — NOT #fff (3.22:1, fails) */
    --green: #4CA877;        /* provisional dark semantics */
    --amber: #C79A4A;
    --red: #DB6B63;
    --blue: #82A9D9;         /* info (dark) — calendar times stay legible on dark tiles (6.7:1) */
    --shadow: 0 1px 2px rgba(0,0,0,.30), 0 8px 22px rgba(0,0,0,.38);
    --sheet-shadow: 0 -8px 40px rgba(0,0,0,.55);
  }
}

/* Dark mode: explicit override (ignores system preference) */
:root[data-theme="dark"] {
  --bg: #14161B;
  --tile: #1C2027;
  --tile2: #23262E;
  --ink: #E7E9ED;
  --muted: #A1AAB8;
  --line: #2A2E36;
  --accent: #6E8BE8;
  --soft: rgba(110,139,232,.16);
  --on-accent: #12151C;
  --green: #4CA877;
  --amber: #C79A4A;
  --red: #DB6B63;
  --blue: #82A9D9;
  --shadow: 0 1px 2px rgba(0,0,0,.30), 0 8px 22px rgba(0,0,0,.38);
  --sheet-shadow: 0 -8px 40px rgba(0,0,0,.55);
}

/* Light mode: explicit override (ignores system preference) */
:root[data-theme="light"] {
  --bg: #EBEEF2;
  --tile: #FFFFFF;
  --tile2: #E9EDF3;
  --ink: #12151C;
  --muted: #5F6878;
  --line: #E1E5EB;
  --accent: #2C57C8;
  --soft: rgba(44,87,200,.10);
  --on-accent: #FFFFFF;
  --green: #2F8559;
  --amber: #8A5E12;
  --red: #C4403B;
  --blue: #4A6FA5;
  --shadow: 0 1px 2px rgba(0,0,0,.03), 0 8px 22px rgba(0,0,0,.05);
  --sheet-shadow: 0 -8px 40px rgba(18,21,28,.22);
}

* { box-sizing: border-box; }

/* A11y (V3.8) — keyboard focus is always visible. :where() keeps specificity 0, so
   an element wanting a *tuned* ring (.coming-up-strip adds a matching border-radius)
   still wins; the rest inherit this baseline. Programmatic focus after a pointer tap
   won't trip :focus-visible, so touch users see no stray ring. Outline follows the
   element's border-radius in modern browsers. */
:where(a, button, input, select, textarea, [tabindex]):focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

html, body {
  margin: 0;
  padding: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: var(--font);
  font-size: 16px;
  line-height: 1.4;
  -webkit-font-smoothing: antialiased;
  overscroll-behavior-y: contain;
}

body {
  max-width: 640px;
  margin: 0 auto;
  padding-block-start: env(safe-area-inset-top, 0);
  padding-block-end: calc(80px + env(safe-area-inset-bottom, 0));
  padding-inline: 12px;
  min-height: 100vh;
  font-feature-settings: "tnum", "cv11";
}

/* Header */
header.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-block: 12px 8px;
  padding-inline: 4px;
}
header.app-header h1 {
  font-size: 18px;
  margin: 0;
  font-weight: 600;
}
header.app-header .date {
  font-size: 14px;
  color: var(--muted);
}

/* Status pill (Today) — single 3-tier signal (V3.2; replaces the old pill +
   the status banner). Tier ∈ loading|overdue|today|clear, set via data-tier.
   Tier is conveyed by THREE redundant channels — color (data-tier), the count,
   and the text label — so it is never color-only (DESIGN §8). Clear is a
   visible resting state, never hidden. The glyph is decorative (aria-hidden);
   the meaning lives in the count + label. Tier washes mirror the retired
   banner's AA-cleared tokens. */
.status-pill {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-block: 4px 12px;
  padding: 7px 14px;
  border-radius: 999px;
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  border: 1px solid var(--line);
  font-size: 13px;
  font-weight: 500;
  width: max-content;
  max-width: 100%;
}
.status-pill .pill-glyph { font-size: 13px; line-height: 1; }
.status-pill .pill-count { font-weight: 600; }   /* .num supplies mono + tabular-nums */
.status-pill .pill-label { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.status-pill[data-tier="loading"] { background: color-mix(in srgb, var(--bg) 78%, transparent); color: var(--muted); }
.status-pill[data-tier="clear"]   { background: color-mix(in srgb, var(--green) 12%, transparent); color: var(--green); }
.status-pill[data-tier="today"]   { background: color-mix(in srgb, var(--amber) 14%, transparent); color: var(--amber); }
.status-pill[data-tier="overdue"] { background: color-mix(in srgb, var(--red)   14%, transparent); color: var(--red); }

/* V3.2 Today scaffold slots — later slices (V3.3 desk/coming-up, V3.4 calendar,
   V3.5 portfolios, V3.7 love-note) fill these; an empty/hidden slot must not
   reserve space (no layout shift on the rebuilt Today). */
#love-note-slot[hidden] { display: none; }

/* Love-note (V3.7) — a parent-to-parent ephemeral note. The inbound card is set
   apart by an accent wash + an inline-start border + the 💌 glyph, never hue
   alone (DESIGN §8); the composer is a quiet textarea + Send/Clear (reusing the
   shared .action-btn styles). RTL "just works" via logical properties. */
.love-note { margin-block: 4px 18px; }
.love-note-heading {
  text-transform: uppercase;
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--muted);
  margin: 0 4px 8px;
  font-weight: 600;
}
.love-note-card {
  background: var(--soft);
  border: 1px solid var(--line);
  border-inline-start: 3px solid var(--accent);
  border-radius: var(--rad);
  padding: 12px 14px;
  margin-bottom: 10px;
}
.love-note-from { font-size: 12px; font-weight: 600; color: var(--accent); margin-bottom: 4px; }
.love-note-text { font-size: 15px; color: var(--ink); white-space: pre-wrap; overflow-wrap: anywhere; }
.love-note-when { font-size: 11px; color: var(--muted); margin-top: 6px; }
.love-note-compose { display: flex; flex-direction: column; gap: 8px; }
.love-note-input {
  width: 100%;
  resize: vertical;
  min-block-size: 44px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  background: var(--tile);
  color: var(--ink);
  border-radius: var(--rad-sm);
  font-family: inherit;
  font-size: 14px;
  line-height: 1.4;
}
.love-note-input::placeholder { color: var(--muted); }
.love-note-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.love-note-waiting { font-size: 12px; color: var(--muted); margin-inline-end: auto; }

/* Sections */
.section {
  margin-bottom: 18px;
}
.section h2 {
  text-transform: uppercase;
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--muted);
  margin: 0 4px 8px;
  font-weight: 600;
}

/* Row card */
.row {
  background: var(--tile);
  border-radius: var(--rad);
  padding: 12px 14px;
  margin-bottom: 8px;
  box-shadow: var(--shadow);
  border: 1px solid var(--line);
  cursor: pointer;
  transition: transform 0.08s ease;
}
.row:active { transform: scale(0.99); }
.row-top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
}
.row-title {
  font-weight: 500;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}
.row-meta {
  font-size: 13px;
  color: var(--muted);
  white-space: nowrap;
}
.row-note {
  font-size: 13px;
  color: var(--muted);
  margin-top: 4px;
}
.flag { font-size: 13px; }
.flag-OVERDUE { color: var(--red); }
.flag-FIRE { color: var(--amber); }
.flag-WEEK { color: var(--amber); }
.flag-MONTH { color: var(--green); }

/* Amounts — tabular mono, bidi-safe for Hebrew + ₪ */
.amount,
.num,
time {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
}
.bidi-amount {
  unicode-bidi: isolate;
}

/* Actions revealed on expand */
.actions {
  display: none;
  margin-top: 10px;
  flex-wrap: wrap;
  gap: 6px;
}
.action-btn {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink);
  padding: 7px 12px;
  border-radius: 999px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
}
.action-btn:hover { background: var(--bg); }
.action-btn.primary {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}
.action-btn.danger { color: var(--red); }

/* Empty state */
.empty {
  color: var(--muted);
  font-size: 14px;
  padding: 8px 4px;
  font-style: italic;
}
.empty-caught-up {
  background: color-mix(in srgb, var(--green) 10%, transparent);
  color: var(--green);
  border-radius: var(--rad);
  padding: 24px 16px;
  text-align: center;
  font-size: 15px;
  font-weight: 500;
  margin-bottom: 8px;
}
.empty-caught-up .empty-date {
  display: block;
  margin-top: 6px;
  font-size: 13px;
  font-weight: 400;
  color: var(--muted);
  font-family: var(--font-mono);
}

/* ── Desk — select-to-act (V3.3; replaced the .expanded/.snoozing accordion).
   Each overdue/fire-today row is a checkbox: selection is conveyed by THREE
   redundant channels — aria-checked (AT), the ✓ box (glyph), and the wash/border
   (color) — so it is never color-only (DESIGN §8). Logical props → RTL "just
   works" (the check box sits at the inline-start). */
.desk-row { display: flex; align-items: flex-start; gap: 12px; }
.desk-row .desk-row-body { flex: 1; min-width: 0; }
.desk-check {
  flex-shrink: 0;
  inline-size: 22px; block-size: 22px;
  margin-block-start: 1px;
  border: 2px solid var(--line);
  border-radius: 6px;
  display: inline-flex; align-items: center; justify-content: center;
  transition: background 0.08s ease, border-color 0.08s ease;
}
.desk-row[aria-checked="true"] { border-color: var(--accent); background: var(--soft); }
.desk-row[aria-checked="true"] .desk-check { background: var(--accent); border-color: var(--accent); }
.desk-row[aria-checked="true"] .desk-check::after { content: "✓"; color: var(--on-accent); font-size: 13px; line-height: 1; }
/* .desk-row (a div[tabindex=0]) inherits the global :where([tabindex]):focus-visible ring. */

/* Sticky batch action bar — appears when ≥1 row is selected, floats above the
   tabbar while the desk scrolls (sticky-bottom; sits inline when the desk is
   short). The snooze chips + note composer expand inside it, never both at once. */
.desk-actionbar {
  position: sticky;
  inset-block-end: calc(72px + env(safe-area-inset-bottom, 0));
  z-index: 20;
  margin-block-start: 10px;
  background: var(--tile);
  border: 1px solid var(--line);
  border-radius: var(--rad);
  box-shadow: var(--shadow);
  padding: 10px 12px;
}
.desk-actionbar[hidden] { display: none; }
.desk-actionbar-main { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.desk-sel-count { font-size: 13px; font-weight: 600; color: var(--accent); margin-inline-end: auto; }
.desk-actionbar-btns { display: flex; gap: 6px; flex-wrap: wrap; }
.desk-snooze-row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin-block-start: 10px; }
.desk-snooze-row[hidden], .desk-note-row[hidden] { display: none; }
.snooze-chip {
  border: 1px solid var(--line);
  background: var(--tile2);
  color: var(--ink);
  border-radius: 999px;
  padding: 6px 14px;
  font: inherit; font-size: 13px; line-height: 1;
  min-block-size: 44px;   /* DESIGN §8 — the primary snooze affordance clears the tap-target floor */
  cursor: pointer;
}
.snooze-date {
  border: 1px solid var(--line);
  background: var(--tile2);
  color: var(--ink);
  border-radius: 999px;
  padding: 4px 12px;
  font: inherit; font-size: 13px;
  min-block-size: 44px;
}
.desk-note-row { display: flex; gap: 8px; align-items: flex-start; margin-block-start: 10px; }
.desk-note-row textarea {
  flex: 1; min-width: 0;
  resize: vertical; min-block-size: 44px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  background: var(--tile);
  color: var(--ink);
  border-radius: var(--rad-sm);
  font: inherit; font-size: 14px; line-height: 1.4;
}

/* ── Coming-up — a read-only ±30-day horizontal scroll band (V3.3; replaced the
   "Next 7 days" list). A now-marker divides the past (scroll back) from the future;
   the strip opens positioned at "now". Chips are read-only (no tap affordance).
   RTL "just works" off dir=rtl + logical props; gentle proximity snap. */
.coming-up-strip {
  display: flex;
  align-items: stretch;
  gap: 10px;
  overflow-x: auto;
  /* overflow-x:auto forces overflow-y to 'auto', a two-axis box that would clip the
     card shadows flush — reserve block padding so the 0 8px 22px shadow sits inside. */
  padding-block: 2px 12px;
  scroll-snap-type: x proximity;
  scroll-padding-inline: 2px;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.coming-up-strip::-webkit-scrollbar { display: none; }
.coming-up-strip:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: var(--rad-sm); }
.coming-up-chip {
  flex: 0 0 auto;
  inline-size: 152px;
  min-width: 0;
  scroll-snap-align: start;
  background: var(--tile);
  border: 1px solid var(--line);
  border-radius: var(--rad);
  box-shadow: var(--shadow);
  padding: 10px 12px;
  display: flex; flex-direction: column; gap: 4px;
}
.coming-up-chip.shabbat { border-inline-start: 3px solid var(--amber); }
.cu-top { display: flex; align-items: center; gap: 6px; }
.cu-glyph { font-size: 13px; }
.cu-date { font-size: 12px; color: var(--muted); }
.cu-title { font-size: 14px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cu-due { font-size: 12px; color: var(--muted); }
.coming-up-now {
  flex: 0 0 auto;
  scroll-snap-align: center;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px;
  padding-inline: 2px;
}
.cu-now-bar { flex: 1; inline-size: 2px; min-block-size: 44px; background: var(--accent); border-radius: 2px; }
.cu-now-label { color: var(--accent); font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }

/* Reduced motion (V3.8) — one consolidated block. Neutralizes every transition,
   scroll animation, and :active scale-feedback in the app for users who ask for
   less motion (replaces the three per-component blocks the earlier slices added). */
@media (prefers-reduced-motion: reduce) {
  .coming-up-strip, .cal-strip { scroll-behavior: auto; }
  .row, .tile, .sheet, .desk-check, .toast { transition: none; }
  .row:active, .tile:active { transform: none; }
}

/* Calendar — 3-day scroll-snap strip (V3.4). Always 3 panes (today/+1/+2) so an
   empty day never collapses the strip and the horizontal snap keeps stable
   geometry. RTL "just works": the strip inherits dir=rtl + uses logical props,
   so today (the first pane) sits at the inline-start (right) edge and snap
   advances inline. Read-only — these cards carry no tap affordance. */
.cal-strip {
  display: flex;
  align-items: flex-start;        /* an empty pane must not stretch to a tall sibling */
  gap: 12px;
  overflow-x: auto;
  /* overflow-x:auto forces the computed overflow-y to 'auto' too, making this a
     two-axis scroll box that would otherwise clip the card drop-shadows flush —
     so reserve block padding for the 0 8px 22px shadow to sit inside. */
  padding-block: 2px 14px;
  scroll-snap-type: x mandatory;
  scroll-padding-inline: 2px;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;          /* the peeking next pane is the affordance */
}
.cal-strip::-webkit-scrollbar { display: none; }
.cal-day {
  flex: 0 0 calc(100% - 32px);    /* near-full-width; ~32px of the next pane peeks */
  min-width: 0;
  scroll-snap-align: start;
}
.cal-day-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  margin: 2px 4px 8px;
}
.cal-day-name { font-weight: 600; font-size: 14px; }
.cal-day-date { font-size: 13px; color: var(--muted); }

/* Calendar event card — read-only (no tap affordance, no :active feedback) */
.cal-event { padding: 10px 14px; cursor: default; }
.cal-event:active { transform: none; }
.cal-time { color: var(--blue); font-size: 13px; }   /* .num supplies mono + tnum */
/* Shabbat line (🕯) — non-color inline-start border + glyph carry it, not hue alone */
.cal-event.shabbat { border-inline-start: 3px solid var(--amber); }

/* ── Portfolios — a grid of domain TILES (V3.5; replaced the accordions). Each
   tile is a <button> with a glanceable face; tapping opens the one shared bottom-
   sheet. Money is the hero (spans the row). Status is never color-only — text +
   glyph carry it (DESIGN §8); the semantic hues are redundant reinforcement. */
.portfolio-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 6px;
}
.tile {
  display: flex;
  flex-direction: column;
  gap: 10px;
  text-align: start;
  background: var(--tile);
  border: 1px solid var(--line);
  border-radius: var(--rad);
  box-shadow: var(--shadow);
  padding: 14px;
  min-block-size: 104px;
  font-family: inherit;
  color: var(--ink);
  cursor: pointer;
  transition: transform 0.08s ease;
}
.tile:active { transform: scale(0.99); }
.tile-money { grid-column: 1 / -1; }   /* the hero spans the row */
.tile-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.tile-name { font-weight: 600; font-size: 15px; }
.tile-status { font-size: 13px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.tile-status.is-warn { color: var(--amber); }
.tile-flag { font-size: 12px; }
.tile-kpi { font-size: 28px; font-weight: 500; color: var(--accent); line-height: 1; margin-block-start: auto; }
.tile-sub { font-size: 13px; color: var(--muted); }

/* Money hero face: donut (overall %) + side column (amount · category bar · spark) */
.tile-money-viz { display: flex; align-items: center; gap: 14px; }
.tile-money-side { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.tile-amount { font-size: 18px; font-weight: 500; }
.tile-amount-of { color: var(--muted); font-size: 14px; }
.donut { inline-size: 64px; block-size: 64px; flex-shrink: 0; }
.donut-track { fill: none; stroke: var(--line); stroke-width: 7; }
.donut-fill { fill: none; stroke: var(--accent); stroke-width: 7; stroke-linecap: round; }
.donut-over .donut-fill { stroke: var(--red); }
.donut-pct { fill: var(--ink); font-family: var(--font-mono); font-size: 15px; font-weight: 600; }
.cat-bar { display: flex; gap: 2px; block-size: 8px; border-radius: 999px; overflow: hidden; }
.cat-seg { display: block; min-inline-size: 2px; }
.cat-seg-0 { background: var(--accent); }
.cat-seg-1 { background: color-mix(in srgb, var(--accent) 70%, var(--tile2)); }
.cat-seg-2 { background: color-mix(in srgb, var(--accent) 45%, var(--tile2)); }
.cat-seg-3 { background: color-mix(in srgb, var(--accent) 25%, var(--tile2)); }

/* Standalone KPI + sparkline (relocated off the deleted drawer-toggle; used on the
   money tile face + in the sheet head). */
.kpi { font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 20px; font-weight: 500; color: var(--accent); white-space: nowrap; }
.kpi.kpi-neg { color: var(--red); }
.kpi.kpi-pos { color: var(--accent); }
.kpi:empty { display: none; }
.sparkline { width: 80px; height: 24px; color: var(--accent); stroke: currentColor; fill: none; stroke-width: 1.5; }
.sparkline:empty { display: none; }

/* Health avatars: initials (NO photo — no stored media) + a non-color urgency
   badge (glyph + day-count); the ring hue is redundant reinforcement. */
.avatar-row { display: flex; gap: 10px; flex-wrap: wrap; margin-block-start: auto; }
.tile-allgood { color: var(--green); font-size: 20px; }
.avatar { position: relative; display: inline-flex; align-items: center; justify-content: center; inline-size: 38px; block-size: 38px; border-radius: 999px; background: var(--tile2); border: 1px solid var(--line); }
.avatar-initials { font-size: 13px; font-weight: 600; }
.avatar-badge { position: absolute; inset-block-end: -7px; inset-inline-end: -7px; display: inline-flex; align-items: center; gap: 1px; font-size: 9px; background: var(--tile); border: 1px solid var(--line); border-radius: 999px; padding: 0 3px; }
.avatar-badge .num { font-size: 9px; }
.avatar-over { border-color: var(--red); }
.avatar-soon { border-color: var(--amber); }

/* Goals tile bar (D8: tile = simple % bar; the bright-line lives in the sheet) */
.goal-bar { block-size: 8px; border-radius: 999px; background: var(--tile2); overflow: hidden; margin-block-start: auto; }
.goal-bar-fill { display: block; block-size: 100%; background: var(--accent); }

/* ── Bottom-sheet — ONE shared, data-driven drawer (V3.5; replaced the six
   inline accordions). Slides up over a scrim; focus-trapped + scroll-locked. */
.sheet-scrim {
  position: fixed; inset: 0; z-index: 90;
  background: rgba(18, 21, 28, .38);
  -webkit-backdrop-filter: blur(2px); backdrop-filter: blur(2px);
}
.sheet {
  position: fixed; inset-inline: 0; inset-block-end: 0; z-index: 91;
  max-width: 640px; margin-inline: auto;
  display: flex; flex-direction: column;
  background: var(--tile);
  border-start-start-radius: var(--rad); border-start-end-radius: var(--rad);
  box-shadow: var(--sheet-shadow);
  max-block-size: 80vh;
  padding: 8px 16px calc(16px + env(safe-area-inset-bottom, 0));
  transform: translateY(100%);
  transition: transform 0.24s ease;
}
.sheet.open { transform: translateY(0); }
.sheet-grip { flex-shrink: 0; inline-size: 36px; block-size: 4px; border-radius: 999px; background: var(--line); margin: 4px auto 8px; }
.sheet-head { flex-shrink: 0; display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.sheet-title { font-size: 17px; font-weight: 600; margin: 0; flex: 1; min-width: 0; }
.sheet-close { margin-inline-start: auto; border: none; background: transparent; color: var(--muted); font-size: 18px; cursor: pointer; min-inline-size: 44px; min-block-size: 44px; font-family: inherit; }
/* flex:1 + min-block-size:0 make this the shrinkable scroll region (the grip/head
   stay pinned) — without min-block-size:0 a flex item won't scroll below content. */
.sheet-body { flex: 1 1 auto; min-block-size: 0; overflow-y: auto; -webkit-overflow-scrolling: touch; }
.sheet-sub { color: var(--muted); margin-top: 12px; margin-bottom: 2px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; }
body.sheet-open { overflow: hidden; }

.kv {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 14px;
  border-bottom: 1px solid var(--line);
  gap: 12px;
}
.kv:last-child { border-bottom: none; }
.kv .v {
  color: var(--muted);
  font-variant-numeric: tabular-nums;
  font-family: var(--font-mono);
  white-space: nowrap;
}

/* Goal bright-line viz */
.goal-line {
  width: 100%;
  height: 40px;
  display: block;
  margin: 6px 0 4px;
}
.goal-line .band-ok { fill: color-mix(in srgb, var(--green) 12%, transparent); }
.goal-line .band-warn { fill: color-mix(in srgb, var(--amber) 14%, transparent); }
.goal-line .band-bad { fill: color-mix(in srgb, var(--red) 12%, transparent); }
.goal-line .target-line { stroke: var(--muted); stroke-width: 1; stroke-dasharray: 3 3; fill: none; }
.goal-line .actual-line { stroke: var(--accent); stroke-width: 2; fill: none; }
.goal-line .now-dot { fill: var(--accent); }

/* Cross-domain timeline (V3.6) — read-only chronology inside the bottom-sheet.
   Controls stick to the top of the scrolling sheet body; the track is a vertical
   date-sorted list with a now-marker. Urgency is glyph + text, never color-only. */
.tl-controls {
  position: sticky;
  inset-block-start: 0;
  background: var(--tile);
  /* opaque padding (not margin) carries the full gap rows scroll under — a margin
     would leave a transparent hairline where rows bleed through the sticky header */
  padding-block: 8px 12px;
  z-index: 1;
}
.tl-zooms, .tl-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.tl-chips { margin-block-start: 8px; }
.tl-zoom, .tl-chip {
  border: 1px solid var(--line);
  background: var(--tile2);
  color: var(--ink);
  border-radius: 999px;
  padding: 6px 12px;
  font: inherit;
  font-size: 13px;
  line-height: 1;
  min-block-size: 32px;
  cursor: pointer;
}
.tl-zoom[aria-pressed="true"], .tl-chip[aria-pressed="true"] {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--on-accent);   /* theme-paired: #fff on light accent 6.4:1, dark ink on dark accent 5.7:1 */
}
.tl-track { display: flex; flex-direction: column; }
.tl-now {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 10px 0;
  color: var(--accent);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.tl-now::before, .tl-now::after {
  content: "";
  flex: 1;
  block-size: 2px;
  background: var(--accent);
  border-radius: 2px;
}
.tl-item {
  display: grid;
  grid-template-columns: auto auto 1fr auto;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--line);
}
.tl-item:last-child { border-bottom: none; }
.tl-glyph { font-size: 12px; }
.tl-date { font-size: 12px; color: var(--muted); white-space: nowrap; }
.tl-body { min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.tl-title { font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tl-cat { font-size: 11px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tl-due { font-size: 11px; color: var(--muted); white-space: nowrap; }
/* Non-color cue is the glyph + due phrase; the inline-start border is redundant. */
.tl-item.tl-over { border-inline-start: 3px solid var(--red); padding-inline-start: 7px; }
.tl-item.tl-soon { border-inline-start: 3px solid var(--amber); padding-inline-start: 7px; }
.tl-item.tl-over .tl-title { font-weight: 600; }
/* (no reduced-motion rule here: the .tl-* controls declare no transition/animation;
   the only motion in this surface is the sheet slide, handled by the .sheet RM rule.) */

/* Tab bar */
nav.tabbar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--tile);
  border-top: 1px solid var(--line);
  display: flex;
  justify-content: space-around;
  padding: 8px 0 calc(8px + env(safe-area-inset-bottom, 0));
  max-width: 640px;
  margin: 0 auto;
}
nav.tabbar button {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--muted);
  font-size: 13px;
  cursor: pointer;
  padding: 6px 0;
  font-family: inherit;
}
nav.tabbar button.active { color: var(--accent); font-weight: 600; }

/* Sign-in screen */
.signin {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 70vh;
  text-align: center;
  padding: 24px;
}
.signin h2 { margin: 8px 0; font-weight: 600; }
.signin p { color: var(--muted); max-width: 320px; }
.signin-btn {
  margin-top: 18px;
  background: var(--accent);
  color: white;
  border: none;
  padding: 12px 22px;
  border-radius: 999px;
  font-size: 16px;
  cursor: pointer;
  font-family: inherit;
}

/* Stale-cache badge */
.stale-badge {
  font-size: 12px;
  color: var(--amber);
  padding: 6px 10px;
  border-radius: var(--rad-sm);
  background: color-mix(in srgb, var(--amber) 10%, transparent);
  margin-bottom: 8px;
}

/* Hide views */
.view { display: none; }
.view.active { display: block; }

/* Sunday view */
.sunday h2.briefing-title { font-size: 22px; font-weight: 600; margin: 12px 4px 4px; }
.sunday .week { color: var(--muted); margin: 0 4px 16px; font-size: 14px; }
.sunday .sub { color: var(--muted); margin-top: 12px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; }
.sunday .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; background: var(--bg); margin-inline-end: 4px; font-size: 12px; color: var(--muted); }

/* Settings */
.settings .row { cursor: default; }
.settings label { font-size: 13px; color: var(--muted); display: block; margin-top: 8px; }
.settings input, .settings select {
  width: 100%;
  padding: 8px;
  margin-top: 4px;
  border: 1px solid var(--line);
  background: var(--bg);
  color: var(--ink);
  border-radius: var(--rad-sm);
  font-family: inherit;
  font-size: 14px;
}

/* Toast */
.toast {
  position: fixed;
  bottom: 90px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--ink);
  color: var(--bg);
  padding: 10px 16px;
  border-radius: 999px;
  font-size: 14px;
  z-index: 100;
  opacity: 0;
  transition: opacity 0.2s ease;
  pointer-events: none;
}
.toast.show { opacity: 1; }

=== End: dashboard/styles.css ===


```

</details>
