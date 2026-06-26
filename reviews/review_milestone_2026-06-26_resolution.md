# v3 milestone close — review resolution (2026-06-26)

Two gates ran for the V3.9 close of the v3 Today redesign (V3.1–V3.8). This is the
Apply / Defend / Open resolution for both. Raw external review:
`review_milestone_2026-06-26_20-47.md`. Changes summary: `session_changes_2026-06-26_v3.md`.

## Gate 1 — external DeepSeek milestone review (`review.py --lane milestone`)

5 concerns, 5 missed-alternatives, 4 affirmations, 1 team question. No milestone blocker.

| # | Concern | Resolution |
|---|---|---|
| 1 (HIGH) | `app.js` interactive logic (batch fan-out, focus-trap, snooze, love-note fetch) has no test harness | **Open** → the already-tracked *Dashboard JS test harness* lane. The reviewer's middle-path — extract the write path (`applyWrites`/`enqueueWrites`/`flushQueue`) into a DOM-free module and pure-function-test it, no jsdom — is recorded as that lane's recommended **first** step. |
| 2 (HIGH) | Love-note DoS / token-replay / tunnel-pivot | **Mostly Defend.** Path fail-closed already exists (`love_note_server.py:240` → 404 non-`/lovenote`); server binds `127.0.0.1:8787` only, so the tunnel can't pivot to the bridge. Token-replay reviewer-rated low (static PWA). **Rate-limiting → Open** (bounded today by systemd CPUQuota/TasksMax + the 120 s verify-cache). |
| 3 (MED) | SPEC §7.7 didn't document replacement semantics | **Applied** — added the atomic-and-silent / no-version-history / replaced-before-seen-is-never-seen clause to SPEC §7.7. |
| 4 (MED) | Notes >120 chars silently dropped from digest | **Defend** — by design (`daily_digest.py:88`, `NOTES_MAX_CHARS=120`, DESIGN §6 "notes ride along only when short"); the note is still on the Sheet + dashboard, only the WhatsApp line omits it. Optional composer char-hint → **Open**. |
| 5 (LOW) | Tunnel ingress config not in repo, can diverge | **Defend** — single-port localhost binding already constrains it; ENGINEERING §5 documents localhost-only + tunnel-as-sole-path. |

**Affirmations (reviewer):** the §3.1 love-note exception is "correctly bounded"; the
no-revoke switch-account is "correct"; the col-D ISO write/read is "well-engineered";
the batch→single-`applyWrites` fan-out is "architecturally sound."

**Missed alternatives** — all named, none adopted: Sheet-tab love-notes (deliberately
rejected — the note is ephemeral, not Sheet-shaped, the §3.1 call); build-time
self-disable (the blank-origin fail-safe already self-disables); shared-memory verify
cache (in-memory is fine, restart-loss is acceptable); separate subdomain; PUT
idempotency key (PUT already overwrites one-per-direction).

**Team question** — *Cloudflare Worker instead of an inbound listener?* → **Open**, routed
to the love-note phase-2 PO-call set (alongside voice). A Worker would remove the box's
inbound listener entirely but re-architects the endpoint; not a v3-close decision.

## Gate 2 — internal canon-vs-code conformance audit (9 contract areas, adversarially verified)

Every area returned `overall_conformant: true`. 3 findings, all downgraded to **nit** by
the refute-verifier — each a doc/comment catch-up where canon trailed the shipped code,
zero behavior change. All **Applied**:

| Area | Finding | Applied fix |
|---|---|---|
| SPEC §7.6 | Timeline drops blank-title dated rows (`app.js:1873`) — a 4th, unstated exclusion | SPEC §7.6 inclusion rule now names the blank-title exclusion. |
| DESIGN §4 | Quiet-day desk copy is the shipped "Nothing on fire. ☕", but §4 said "(nothing urgent)" | DESIGN §4 reconciled to the shipped warm copy (the pill keeps "Nothing urgent"). |
| SPEC §7.7 | Two stale comments (`love_note_server.py:24`, `app.js:1027`) said "userinfo" where code + SPEC use **tokeninfo** (load-bearing for the confused-deputy check) | Both comments corrected to tokeninfo. |

## Net

1 external Apply + 3 internal Applies (all doc/comment truth-in-canon, no behavior change);
the rest Defend or Open. 4 Open follow-ups tracked in `BACKLOG.md` → Deferred:
JS interactive-logic harness (with the write-path-extraction first step), love-note
rate-limit, love-note 120-char composer hint, and the Worker-vs-tunnel phase-2 PO call.
**No milestone-blocking finding** — expected for a lane already slice-reviewed 7-lens each.
