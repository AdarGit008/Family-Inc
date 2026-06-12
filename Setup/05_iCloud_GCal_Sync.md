# 05 — iCloud → Google Calendar Sync

**Time budget: ~15min.** Easiest win in the whole runbook. Do this first if you want a confidence builder.

## Why this matters

Shanee lives in iCloud Calendar. Adar's whole stack (PWA briefing, GCal, Sunday digest) reads Google Calendar. Today the only way Adar sees Shanee's plans is to ask. After this, every event Shanee puts on her calendar shows up automatically — refreshes roughly every 10 minutes — and the PWA briefing already merges everything visible in Adar's GCal, so nothing else has to change.

## Step 1 — Shanee publishes her iCloud calendar

On Shanee's iPhone:

1. **Calendar app → Calendars (bottom)**
2. Tap the **(i)** next to "Home" (or whichever calendar she keeps the family stuff on).
3. Scroll to **Public Calendar** → toggle **on**.
4. Tap **Share Link** → AirDrop or Messages it to Adar.
5. The URL starts `webcal://p…-caldav.icloud.com/published/…`.

> If she keeps personal + family on separate calendars, repeat for each. Don't publish a "Work" calendar she doesn't want shared.

## Step 2 — Convert webcal → https

In the URL, replace the leading `webcal://` with `https://`. Google Calendar needs the https form.

## Step 3 — Add to Adar's Google Calendar

On a desktop browser (this option is not exposed in the mobile UI):

1. Open [calendar.google.com](https://calendar.google.com).
2. Left rail → **Other calendars → +** → **From URL**.
3. Paste the `https://...ics` URL.
4. Click **Add calendar**.
5. It appears under "Other calendars" with a default name. Rename to "Shanee (iCloud)".

## Step 4 — Refresh cadence

Google polls subscribed ICS feeds roughly every **6–12 hours** by default — slower than the ~10 min you'd like. Two ways to speed up:

- **Easy**: leave it. The briefing runs on a daily cadence so a 6h lag rarely matters.
- **Tighter**: pipe through `feedburner`-style relays or use a Zapier "Schedule → Calendar" zap that calls Google's incremental sync endpoint hourly. Skip unless you actually feel the lag.

## Step 5 — Color coding

In Adar's GCal, hover the calendar in the left rail → three dots → pick:

- **Adar (primary)** → green (`Basil`)
- **Shanee (iCloud)** → blue (`Blueberry`)
- **Kids (kid-1/kid-2)** → tangerine (`Tangerine`) — if you make one
- **Family inc. system events** (auto-created from Reminders) → graphite (`Graphite`)

The PWA briefing reads the GCal color into the event tile, so this is the only place you need to set it.

## Step 6 — Test the merged view

Shanee adds a fake event "TEST FAM" 1h from now. Within an hour:

- [ ] The event appears on Adar's GCal day view.
- [ ] The PWA dashboard's "Today" panel shows it.
- [ ] Tomorrow morning's briefing run lists it under "Shanee's day".

## Verify it worked

- [ ] iCloud public URL works in a browser (it'll download an `.ics`).
- [ ] Google Calendar shows the calendar in "Other calendars" with Shanee's color.
- [ ] At least one event from Shanee's iCloud appears on Adar's view.
- [ ] PWA briefing's merged view includes that event.
- [ ] Shanee can delete a public-calendar event on her side and it disappears from Adar's view within a refresh cycle.
