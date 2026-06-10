# Family inc. — What the system will (and won't) do

*A one-pager for [Partner], so we're aligned before any real data goes in. Five-minute read. We can change anything later.*

Date: 2026-05-27

---

## What we're building

A small set of automations that keep us on top of family life — car renewals, kids' appointments, money, long-term goals — without either of us having to remember everything. One Google Sheet is the brain; WhatsApp is how it talks to us.

## What the system will see

| Domain | What gets stored |
|---|---|
| People | Names, DOB, Kupat Holim, primary doctor, allergies, blood type — for you, me, and the kids |
| Calendars | Events from our Google + iCloud calendars (read-only) |
| Finance | Bank/credit-card transactions, **from CSVs we drop in manually each month** — no bank logins ever |
| Health | Provider, last visit, next due date, action needed |
| Education | School, year, key dates, teacher contact |
| Car | Plate, test date, insurance renewal, license, mechanic |
| Contracts | Mortgage, insurance, utilities — renewal dates and costs |
| Goals | 1–3 long-term family goals we agree on, with 90-day milestones |

All of it lives in our own Google Drive folder, under our Google accounts. **No third party stores any of it.**

## What the system will NOT do

- **Move money.** Ever. No bank logins. No payment authorization. CSVs only, viewed after the fact.
- **Message anyone but us two.** Not kids, not extended family, not doctors. Only the two of us get WhatsApp messages.
- **Make medical decisions.** It surfaces "next dental cleaning due" — it does not pick the dentist.
- **Track moods, feelings, or anything we add to an off-limits list.**
- **Store passwords or credentials.** None. The Twilio key for WhatsApp lives in a separate config, not the Sheet.
- **Share with Anthropic / Claude beyond what's needed to run automations.** No training, no analytics piggy-backing.

## How we'll know it's working

- **Daily, 07:30:** at most one WhatsApp digest each, only if there's actually something to act on.
- **Sunday evening:** one combined briefing across all domains, ~5 minutes to read together with coffee.
- **Monthly, 1st:** finance digest with anomalies flagged.
- **Hard cap: 2 messages per day per person.** If the system needs to send more, it queues for tomorrow.

If it ever feels like spam, we turn the cap to 1, or pause the whole thing. The "off" switch is one toggle in the Sheet.

## How we get rid of it

If at any point you want out:

1. Move or delete the `Family inc.` folder in Google Drive — that's all the data, gone.
2. Cancel the Twilio number — that's all the outgoing messages, gone.
3. Remove the scheduled Cowork task — that's the automation, gone.

There is no other place the data lives. No app, no cloud DB, no backups outside the Drive folder.

## What I need from you

Three things, when you're ready:

1. **A yes/no on storing health and finance data in our Google Drive folder.** (Default: yes; the data is already ours, this just organizes it.)
2. **The default alert budget: 2 WhatsApp messages/day, each.** Push back if 1 feels better.
3. **One Sunday evening of 90 minutes** to walk through the kickoff conversation in `01_Family_Kickoff_Guide.md`. That session is what turns the empty Sheet into something useful — without it, none of this earns its keep.

Anything you want changed, removed, or off-limits — say it now and I'll write it into the design before we wire anything up.

— Adar

---

*Off-limits list (add anything you want):*

- [ ] _______________________________________________
- [ ] _______________________________________________
- [ ] _______________________________________________

*Signed-off: ☐ Yes  ☐ With changes (note above)  ☐ Not yet*
