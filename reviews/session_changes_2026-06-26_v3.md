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
