# Family Inc. — Design Specification

*The product has two surfaces: WhatsApp messages and the dashboard PWA. Both are designed here. v2.0 · 2026-06-11 · supersedes `Archive/05_Dashboard_Design.md` (absorbed, contradiction fixed: the offline model is queue + tombstone everywhere; the "explicit lock" wording is dead).*

---

## 1. Design principles

1. **Calm tech.** The system reports what happened and what's next; it never scolds, streaks, paces, or counts what you missed. Quiet days are a success state, not an empty state.
2. **The message is the product.** Most days the family touches Family Inc. only through WhatsApp. Message copy gets the same design rigor as pixels.
3. **Dense, then disclosed.** Today shows every domain at a glance; detail hides behind one tap. Linear/Notion density, not wellness-app whitespace.
4. **Partner-symmetric surfaces.** Attribution without scoring: domain leads, names follow.
5. **Honest affordances.** Nothing on either surface suggests an action the system can't take (no reply commands until reply parsing ships; no disabled-looking-but-tappable buttons).
6. **Hebrew-first, RTL-first.** English is the fallback, not the default. LTR runs (numbers, URLs) wrapped in `<bdi>`.

## 2. Visual system (dashboard)

### Color — warm paper + indigo

| Token | Light | Dark | Use |
|---|---|---|---|
| `--surface` | `#FAF8F5` | `#15161A` | page |
| `--ink` | `#1A1A1F` | `#E8E6E1` | text |
| `--muted` | `#71717A` | `#A1A1AA` | secondary text, ticks |
| `--accent` | `#5E6AD2` | `#5E6AD2` | arc, links, active tab |
| `--ok` | `#3F8F5F` | sage | all-clear, success |
| `--warn` | `#C58B3A` | amber | due-today |
| `--alert` | `#C44545` | terracotta | overdue |

Semantic colors appear only on status; the accent is the single brand color. No gradients except the skeleton shimmer.

### Type

- **Heebo** — Hebrew UI (default chrome).
- **Inter** — Latin UI (fallback chrome); tabular figures on.
- **Geist Mono** — money only (`₪4,280`) so amounts read as data at a glance.
- Scale: 17/15/13 body-secondary-caption; one display size (28) for the arc number and drawer KPIs. No font weight above 600.

### Components

- **Progress arc** (fixed 56px strip): ring + "N completed · last 7 days" + seven weekday ticks (✓/·). Rolling count, never a streak; never shows a target or deficit. Tap → per-domain mini-arcs.
- **Status banner**: one line — red if any overdue, amber if any fire-today, sage "all clear" otherwise.
- **Reminder row**: flag dot · title · due phrase; tap reveals `✓ done` `+Nd` `note` pills. Snooze pills: 1/3/7/14/30.
- **Domain drawers** (Money/Health/Goals/Car/Contracts): closed = one big KPI + sparkline; open = detail list. 
- **Bright-line goal viz**: target line + actual line + safety band (ahead/on-pace/behind) for multi-year goals — progress bars are banned for anything >90 days.
- **Connection pill**: 🟢 live / ⛔ offline — N queued. The only place sync state appears.
- **Sticky status pill** (top): one-liner like "Weekly briefing ready · 2 alerts" — our budget-friendly stand-in for OS-level notification surfaces.

## 3. Information architecture (Today-first)

```
Today (home)
├── Header: Family inc. · date · sticky status pill · connection pill
├── Progress arc strip
├── Banner (overdue / today / all-clear)
├── TODAY — reminders where Auto-flag ∈ {OVERDUE, FIRE TODAY}
├── CALENDAR — today's Calendar-Events
├── NEXT 7 DAYS — week-out reminders + events
└── ▸ Drawers: Money · Health · Goals · Car · Contracts
Briefing tab — latest weekly briefing rendered
Settings tab — sign-in · Sheet ID · language toggle · demo toggle · queue inspector
```

Rationale (kept from the four-direction exploration, `Archive/05`): Today-first wins the 8 AM glance; tiles demote to drawers; briefing gets a tab, not the home; stream and briefing-first lose on weekday staleness.

## 4. States

- **Loading**: skeleton shell <50ms with cached-snapshot shapes (counts from cache, else 3/2/3/4 rows); shimmer 1.6s; header/pills/tabs are real from t=0; cached values replace skeletons, live values cross-fade 120ms. Skeletons never shimmer while offline — static gray is more honest.
- **Quiet day**: arc keeps its ticks, banner shows sage "all clear", TODAY renders "(nothing urgent)". The screen is never blank.
- **Offline**: pill flips to "⛔ offline — N queued"; rows keep working; a queued row shows "⏳ queued — will sync on reconnect". **Buttons never disable offline.**
- **Write failure (online)**: optimistic UI rolls back; inline "Couldn't save — retry?"; token expiry → silent refresh once, then a re-sign-in banner.
- **Back from vacation (30 overdue)**: top 10 by due date + "+20 more" expander; banner offers bulk-done multi-select; arc shows the honest low count with zero commentary.

## 5. Interaction contract (write-back)

Every tap maps to one batched Sheet write per SPEC §6.1 (intent columns + `DoneAt`/`LastDoneBy` on completion + `WriteQueue_Tombstone` always):

| Action | Writes | UI |
|---|---|---|
| ✓ done | Status=Done, DoneAt, LastDoneBy, Tombstone (+ recurrence bump) | row clears from its list |
| +Nd | Due+=N, Status=Snoozed, Tombstone (no DoneAt — snooze isn't completion) | row re-sorts |
| note | append to Notes with `[date name]` prefix, Tombstone | inline confirm |

Offline: same writes queued (`localStorage.pendingWrites[]`, cap 50 with a one-shot loss warning at the cap); flush in tap order on reconnect; idempotent via tombstone.

## 6. WhatsApp message design system

The most-used UI in the product. Rules:

- **One morning message.** Engine fires, group digest, and Hebcal line are assembled into a single 07:30 message per recipient — never 2–3 separate sends.
- **Line economy.** One line per item: flag emoji · title · due phrase. Notes only if ≤120 chars. >5 items → top 5 by priority + "+N more — בלוח" (in the dashboard).
- **Emoji are semantics, not decoration**: 🔴 overdue · 🟠 today · 🟡 week-out · 🟢 month-out · ⚠ needs-a-look · 🕯 Shabbat line. No other emoji in generated copy.
- **No reply affordances** until reply parsing ships (SPEC §3.7). Messages end with content, not instructions. When v1.1 lands, the reply grammar returns as a single footer line.
- **Hebrew copy register**: short, warm, zero exclamation marks, no imperatives toward a person ("לקבוע תור" not "תקבעי תור!"). Dates as "יום ג׳ 17/6". Money as ₪ with thousands separator.
- **Attribution**: domain first, name inline.

### Templates (v1)

Daily digest (the only routine alert-channel message):

```
🏠 Family inc. · יום ו׳ 12/6
🔴 טסט שנתי לרכב — באיחור 3 ימים
🟠 תור שיניים לילד — היום
🟡 ביטוח דירה — בעוד 6 ימים

קבוצות (24ש׳):
גן — מחר יום פרי, להביא 🍐 (גננת, 22:14)
ועד — מעלית מושבתת חמישי 09:00–12:00

🕯 הדלקת נרות 19:24 · צאת שבת 20:35
```

Critical (budget-bypassing, rare): single line, no frame — `⚠ {group}: {one_liner} ({sender}, {time})`.

Weekly briefing (Sat 21:00): five scenes, vertical, one line each opener — *the week's spend · kids' moment · next week's three things · one goal line · one contract heads-up* — then short sections. Strava-year-in-review meets Morning Brew; typography is the design.

Bridge-health warning prepends, never replaces: `⚠ הגשר שקט 14 שעות — ייתכן שפספסנו הודעות`.

## 7. i18n rules

- `<html lang="he" dir="rtl">` default; `localStorage.familyinc.lang="en"` flips lang/dir + chrome strings (pre-paint, no flash).
- Logical CSS properties only (`padding-inline-start`); no left/right literals.
- Chrome strings in the parallel STRINGS table; data values (merchants, group names, guide links) render Hebrew regardless of toggle.
- Dates `DD/MM`, week starts Sunday, `he-IL` number formatting in both languages (the audience is Israeli in either chrome).
- Brand stays Latin "Family inc." everywhere incl. home-screen title.
- WhatsApp messages are Hebrew-only (no toggle exists there; the recipients are known).

## 8. Accessibility & ergonomics

Tap targets ≥44px; contrast AA against both surfaces (the muted zinc fails on dark — use `#A1A1AA` minimum); focus-visible outlines on; reduced-motion media query kills shimmer + cross-fades; PWA `apple-touch-icon` relies on the OS glass treatment, no fake translucency in-app; thumb-zone: action pills render below the row, not above.

## 9. Manual smoke checklist (per dashboard deploy)

1. Cold load <1s on phone over LTE; skeletons → live without layout shift.
2. Hebrew default renders RTL with no mirrored numerals; toggle flips chrome only.
3. Mark done online → row clears, Sheet shows M/N/O stamped.
4. Airplane mode → tap done → pill shows queued → reconnect → flush; engine log shows tombstone skip if within window.
5. Demo toggle never touches the live Sheet.
6. Lighthouse PWA installable; offline reload serves shell + cached data.

## 10. History

- 2026-06-15: appreciation ticker removed entirely (D-036) — a passive "recently completed" surface still risked reading as a partner scoreboard; supersedes the domain-grouped ticker (D-004) and its §2/§3/§4/§5/§8 references.
- 2026-06-11: v2.0. Absorbed `Archive/05_Dashboard_Design.md`; removed the contradictory "explicit offline lock" refinement (queue+tombstone is the single offline model); elevated WhatsApp messages to a designed surface; banned reply affordances until parsing ships; single-morning-message rule added.
- 2026-05-30: arc/ticker/skeleton/queue+tombstone refinements; Hebrew-default chrome; domain-grouped ticker (post-review resolutions preserved in `Archive/05_Dashboard_Design.md`).
