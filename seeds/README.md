# seeds/ — personal seed data (gitignored)

CSV seeds for the Family_OS Sheet and the group-config. They contain personal
values (names, health schedules, group names), so `*.csv` here is gitignored —
the files live on the machines that need them (PO laptops + the appliance) and
in the Sheet itself once imported. The repo stays public-portfolio-safe by
construction (CLAUDE.md guardrails).

Expected files (M3 seeding, BACKLOG.md):

| File | Feeds |
| --- | --- |
| `08_Israeli_Reminders_Seed.csv` | Reminders tab (≥20 real rows at go-live) |
| `09_Vaccine_Schedule_Seed.csv` | Health tab (Tipat Halav schedule) |
| `10_Dashboard_Goals_Seed.csv` | Goals tab |
| `12_WhatsApp_Group_Config_Seed.csv` | summarizer group routing + keywords |

If you cloned fresh and this directory is empty, copy the seeds from the
family Drive folder or the appliance backup.
