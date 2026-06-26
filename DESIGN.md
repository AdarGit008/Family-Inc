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
- **Quiet day**: the status pill shows the sage `clear` tier (`Nothing urgent`, or `Sunday briefing ready` on Sundays) and the desk renders its warm empty line ("Nothing on fire. ☕" / "שום דבר לא בוער. ☕"). The screen is never blank.
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
