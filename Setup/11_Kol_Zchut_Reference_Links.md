# 11 — Kol-Zchut Reference Links

**Time budget: ~20min.** This is the "fill the new column" task.

## Why this matters

[Kol-Zchut](https://www.kolzchut.org.il/) is the canonical Israeli rights/benefits database — it tells you who's entitled to what, what form to file, where, by when. Most household tasks have a Kol-Zchut page that's better than any government site. We add a `guide_url` column to the `Reminders` tab and pre-fill it for the common cases so when a reminder fires, the briefing already has the right deep link attached.

## Step 1 — Add the column

`Family_OS` → `Reminders` tab → insert a column called `guide_url` (the seed CSV in doc 08 already includes this column — if you imported that, you're done).

The PWA briefing template already renders any non-empty `guide_url` as a clickable "Open guide" link on the reminder card — no template change needed.

## Step 2 — Reference table

Use these URLs when adding manual reminders. Hebrew titles in parentheses for grep-ability.

### Family + parental

| Topic | URL |
|---|---|
| Parental leave / חופשת לידה | https://www.kolzchut.org.il/he/חופשת_לידה |
| Maternity grant (מענק לידה) | https://www.kolzchut.org.il/he/מענק_לידה |
| Child allowance (קצבת ילדים) | https://www.kolzchut.org.il/he/קצבת_ילדים |
| Daycare subsidy (מעונות יום) | https://www.kolzchut.org.il/he/סבסוד_מעון_יום |
| Working-mother tax credit (נקודות זיכוי לאם עובדת) | https://www.kolzchut.org.il/he/נקודות_זיכוי_להורים |
| Working-father tax credit | https://www.kolzchut.org.il/he/נקודות_זיכוי_להורים |
| New-baby-discount on arnona | https://www.kolzchut.org.il/he/הנחה_בארנונה_להורים_לפעוטות |

### Kids — health

| Topic | URL |
|---|---|
| Tipat Halav schedule (טיפת חלב) | https://www.kolzchut.org.il/he/טיפת_חלב |
| Dental for kids under Maccabi | https://www.kolzchut.org.il/he/שירותי_שיניים_לילדים_בקופות_החולים |
| DDH ultrasound under Maccabi (אולטרה-סאונד מפרקי ירכיים) | https://www.kolzchut.org.il/he/בדיקת_אולטרסאונד_מפרקי_ירכיים_לתינוקות |
| Vaccines info | https://www.kolzchut.org.il/he/חיסוני_שגרה_לילדים |
| Speech / hearing / vision screenings | https://www.kolzchut.org.il/he/סריקות_התפתחותיות |

### Documents

| Topic | URL |
|---|---|
| Passport renewal (חידוש דרכון) | https://www.kolzchut.org.il/he/חידוש_דרכון |
| New passport for kids | https://www.kolzchut.org.il/he/הוצאת_דרכון_לקטין |
| Driver license renewal | https://www.kolzchut.org.il/he/חידוש_רישיון_נהיגה |
| Polish citizenship documentation (general) | https://www.kolzchut.org.il/he/קבלת_אזרחות_פולנית |
| Apostille on Israeli docs | https://www.kolzchut.org.il/he/אישור_אפוסטיל |
| Birth certificate retrieval | https://www.kolzchut.org.il/he/הוצאת_תעודת_לידה |

### Tax + finance

| Topic | URL |
|---|---|
| Tofes 101 explained | https://www.kolzchut.org.il/he/טופס_101 |
| Tofes 161 — severance / מענק פרישה | https://www.kolzchut.org.il/he/טופס_161 |
| Tofes 134 — Bituach Leumi exemption | https://www.kolzchut.org.il/he/טופס_134 |
| Capital gains tax (רווחי הון) | https://www.kolzchut.org.il/he/מס_על_רווחי_הון |
| Mortgage rights (משכנתא) | https://www.kolzchut.org.il/he/משכנתא |
| Zakaut diur (זכאות לדיור) | https://www.kolzchut.org.il/he/זכאות_לסיוע_בשכר_דירה |

### Home / property

| Topic | URL |
|---|---|
| Arnona discount eligibility | https://www.kolzchut.org.il/he/הנחה_בארנונה |
| Building permit (היתר בנייה) | https://www.kolzchut.org.il/he/היתר_בנייה |
| Property purchase tax (מס רכישה) | https://www.kolzchut.org.il/he/מס_רכישה |

## Step 3 — Wire it up

When you (or the bill parser / Maccabi parser) append a Reminder, set `guide_url` to the matching link from the table above. The category-to-URL mapping below covers ~80% of auto-generated reminders — paste this into a small Apps Script helper if you want auto-fill:

```javascript
const GUIDE_URLS = {
  'Tax/Arnona':       'https://www.kolzchut.org.il/he/הנחה_בארנונה',
  'Tax/Tofes101':     'https://www.kolzchut.org.il/he/טופס_101',
  'Documents/Passport': 'https://www.kolzchut.org.il/he/חידוש_דרכון',
  'Documents/License':  'https://www.kolzchut.org.il/he/חידוש_רישיון_נהיגה',
  'Health/Maccabi':   'https://www.kolzchut.org.il/he/זכויות_מבוטחי_מכבי',
  'Kids/⟨child-1⟩/School': 'https://www.kolzchut.org.il/he/סבסוד_מעון_יום',
  'Kids/⟨child-2⟩/School': 'https://www.kolzchut.org.il/he/סבסוד_מעון_יום',
  'Home/Pesach':      'https://www.kolzchut.org.il/he/ניקיון_פסח',
};
```

## Verify it worked

- [ ] `Reminders` tab has a `guide_url` column.
- [ ] The seed import from `08_Israeli_Reminders_Seed.csv` populated most rows already.
- [ ] At least one bill-parser reminder has a non-empty `guide_url` after the next run.
- [ ] The PWA briefing shows the link as a button/anchor on the reminder card.
- [ ] Clicking a `kolzchut.org.il` link from the briefing on mobile opens the right page.
