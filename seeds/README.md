# seeds/ — personal seed data (gitignored)

CSV seeds for the Family_OS Sheet and the group-config. They contain personal
values (names, health schedules, group names), so `*.csv` here is gitignored —
the files live on the machines that need them (PO laptops + the appliance) and
in the Sheet itself once imported. The repo stays public-portfolio-safe by
construction (CLAUDE.md guardrails).

Expected files (M3 seeding, BACKLOG.md):

| File | Feeds |
| --- | --- |
| `Reminders_Import_M3.csv` | **the go-live import** — Reminders tab, §6.1 column layout |
| `08_Israeli_Reminders_Seed.csv` | source backlog the import was drafted from (kept for history) |
| `09_Vaccine_Schedule_Seed.csv` | Health tab (Tipat Halav schedule) |
| `10_Dashboard_Goals_Seed.csv` | Goals tab |
| `12_WhatsApp_Group_Config_Seed.csv` | summarizer group routing + keywords |
| `13_Sender_Roster_Seed.csv` | summarizer sender→role roster (M4, D-044) |

## `13_Sender_Roster_Seed.csv` — sender → role roster (M4)

Maps a WhatsApp sender to a role so the summarizer's §7.3 hard rules 2–3
(daycare teacher in the evening window; vaad-bayit utility notices) fire on real
traffic — the Baileys bridge only knows a JID and a push-name, not a role.

Columns: `sender_jid,sender_name,role`. Give a row a `sender_jid` (stable) or a
`sender_name` (the push-name, less stable) or both; either one is used as a
lookup key. `role` is required (blank-role rows are skipped) — the values the
rules care about are `teacher` and `vaad_bayit`. A message that already carries
an explicit role keeps it; the roster only fills `unknown`/missing roles. The
file is optional: absent → empty roster, rules fall back to the message's own
role. Personal (JIDs/names) → gitignored like the rest of `seeds/`.

## Importing `Reminders_Import_M3.csv` (go-live step 5)

31 rows, drafted 2026-06-12 from the 08 seed + the 2026-05-30 kickoff health
backlog (routine family health reminders, document renewals, September daycare
onboarding). Changes vs the 08 seed: the stale daycare-registration row (due
Feb 2026, past) was replaced by September-onboarding rows; one recurring-bill
owner reassigned per kickoff money ownership. **Review dates and owners before
importing.** (Wording genericized 2026-06-12, D-030b; the old phrasing leaves
history with the publication rewrite.)

Columns match SPEC §6.1 A–P exactly; K–O are intentionally blank (K/L are
sheet formulas, M–O are dashboard-written). To import without killing the
formula columns: paste the data into `A2:J` and `P2:P`, then drag the K2:L2
formulas down. Dates are DD/MM/YYYY.

If you cloned fresh and this directory is empty, copy the seeds from the
family Drive folder or the appliance backup.
