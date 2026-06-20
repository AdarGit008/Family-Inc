# Family Inc. — Visual Overview

> **Non-canon visual aid**, generated 2026-06-20 from the five canon docs (`SPEC.md`, `ENGINEERING.md`, `DESIGN.md`, `BACKLOG.md`, `ROADMAP.md`) + the `deploy/systemd/` units. Safe to delete or regenerate; the canon docs remain the source of truth. Open in any Mermaid-rendering viewer (GitHub, VS Code, Obsidian, the dashboard) to see the diagrams.

A household operating system for **Adar + Shanee** (+ 2 young kids, adult-mediated). It watches obligations — appointments, renewals, deadlines, school/daycare chatter, finances, property listings — and reflects them back through **two calm surfaces** (a few WhatsApp messages + a PWA dashboard) over **one master Google Sheet**. All automation runs unattended on **one VPS** ("the appliance"). Israeli context throughout: Hebrew/RTL, ILS, Asia/Jerusalem, Hebcal.

## The three architectural invariants

| Invariant | What it means |
|---|---|
| **One machine** | The bridge + every timer share one VPS, so a failure is total and obvious (never partial/silent). |
| **One data plane** | Python writes the Sheet via a gspread **service account**; the dashboard reads/writes via per-adult **gapi OAuth**. `Family_OS.xlsx` is a seed template only. |
| **One write path to phones** | Everything that reaches a human goes through `lib/outbox.py` — budget, dedup, quiet-hours, and scope live there exactly once. |

---

## 1. System landscape — what talks to what

```mermaid
flowchart LR
  subgraph EXT["External services"]
    direction TB
    WA_in["WhatsApp groups<br/>(Meta, via Baileys)"]
    YAD["Yad2 / Madlan"]
    APIFY["Apify<br/>(secondary listings)"]
    BANK["Mizrahi bank<br/>(read-only; Max/Cal dormant)"]
    LLM["DeepSeek LLM<br/>(keyword fallback if keyless)"]
    HEB["Hebcal"]
    SMTP["SMTP email<br/>(delivery fallback)"]
  end

  subgraph VPS["The appliance — one VPS (systemd timers + 1 always-on bridge)"]
    direction TB
    BRIDGE["Baileys bridge<br/>(always-on, poll 15s)"]
    SUMM["WhatsApp summarizer<br/>(hourly)"]
    ENGINE["Reminders engine<br/>(07:25, computes)"]
    DIGEST["Daily digest<br/>(07:30, sends)"]
    WEEKLY["Weekly briefing<br/>(Sat 21:00)"]
    PROP["Property scraper<br/>(07:10 / 19:10)"]
    FIN["Finance scrape + ingest<br/>(06:00)"]
    OUTBOX["Outbox lib/outbox.py<br/>THE chokepoint"]
  end

  SHEET[("Family_OS<br/>Google Sheet<br/>master DB")]

  subgraph SURF["Surfaces"]
    direction TB
    PHONES["Adar + Shanee<br/>iPhones (WhatsApp)"]
    PWA["Dashboard PWA<br/>(GitHub Pages)"]
  end

  WA_in --> BRIDGE --> SUMM
  YAD --> PROP
  APIFY -.-> PROP
  BANK --> FIN
  HEB --> DIGEST
  SUMM -->|"classify"| LLM
  FIN -->|"rules-miss"| LLM

  ENGINE --> SHEET
  SUMM --> SHEET
  PROP --> SHEET
  FIN --> SHEET
  SHEET --> DIGEST
  SHEET --> WEEKLY
  ENGINE -->|"computed fires"| DIGEST

  DIGEST --> OUTBOX
  SUMM --> OUTBOX
  WEEKLY --> OUTBOX
  OUTBOX --> BRIDGE --> PHONES
  OUTBOX -.->|"bridge stale 24h+"| SMTP --> PHONES

  SHEET <-->|"read + write-back"| PWA
  PWA --- PHONES
```

---

## 2. The keystone loop — reminders → digest → write-back

The heart of the system. Note: **queueing is not delivery** — rows are stamped back onto the Sheet only after the bridge *confirms* the send, on the *next* run.

```mermaid
sequenceDiagram
  autonumber
  participant E as Reminders engine 07:25
  participant S as Family_OS Sheet
  participant D as Daily digest 07:30
  participant O as Outbox (chokepoint)
  participant B as Baileys bridge
  participant P as Phones (Adar + Shanee)

  E->>S: read Reminders (skip Done/Skipped, skip tombstoned under 6h)
  E->>E: compute OVERDUE / LEAD-TIME / DUE TODAY fires
  Note over E: computes only — never sends
  E->>D: hand over computed fires
  D->>S: pull WhatsApp digest + property + Hebcal sections
  D->>O: queue ONE message per adult (kind=briefing)
  D->>D: write digest_pending.jsonl (NOT stamped yet)
  O->>B: dispatch (budget / quiet-hours / dedup checked)
  B->>P: send 1:1 (only JIDs in recipients.json)
  B->>B: record confirmed send to whatsapp_sent.jsonl
  Note over D,S: on the next --send run
  D->>S: reconcile_deliveries() stamps Last Sent / Status<br/>only for bridge-confirmed rows (unconfirmed 48h+ re-fire)
```

---

## 3. The daily clock — 7 systemd timers (Asia/Jerusalem)

Morning order is deliberate: finance lands first so balances are fresh, then reminders compute *before* the digest assembles. `family-digest.service` has `After=family-reminders.service`. All timers are `Persistent=true` (catch up missed runs after downtime).

```mermaid
gantt
  title Daily clock — Asia/Jerusalem
  dateFormat HH:mm
  axisFormat %H:%M
  section Always-on
  Baileys bridge (listen + send)        :active, 00:00, 24h
  WhatsApp summarizer (hourly, x24)     :        00:00, 24h
  section Morning chain
  Finance scrape + ingest               :crit, 06:00, 40m
  Property scrape (AM)                  :      07:10, 15m
  Reminders engine (compute, no send)   :      07:25, 8m
  Daily digest -> WhatsApp + write-back :crit, 07:30, 12m
  section Evening
  Property scrape (PM)                  :      19:10, 15m
```

**Off this 24h axis:** Weekly briefing **Sat 21:00**, backup to Drive **Sun 03:00**, and **quiet hours 22:00–07:00** (ordinary alerts + briefings held; criticals pierce).

---

## 4. The outbox chokepoint + delivery fallback

Every sender funnels here. Three message *kinds* get different treatment; the 2/day budget ledger is **shared across all senders** so two scripts can't each spend their own quota.

```mermaid
flowchart TD
  A["Any sender<br/>digest / summarizer / weekly"] --> Q["outbox.queue(to, body, kind)"]
  Q --> K{"kind?"}
  K -->|"critical"| C["send immediately, any hour<br/>log budget_bypassed_critical"]
  K -->|"briefing"| BR{"quiet hours?<br/>22:00-07:00"}
  K -->|"alert"| AL{"budget left?<br/>cap 2/day per recipient"}
  BR -->|"yes"| H1["hold until 07:00"]
  BR -->|"no"| SEND
  AL -->|"no"| DEFER["defer to tomorrow's digest<br/>log alert_suppressed_by_budget"]
  AL -->|"yes"| QH{"quiet hours?"}
  QH -->|"yes"| H2["hold until 07:00"]
  QH -->|"no"| SEND
  C --> SEND["write outbox.jsonl"]
  H1 --> SEND
  H2 --> SEND
  SEND --> BRIDGE["Baileys bridge<br/>poll 15s · dedup (id,target)"]
  BRIDGE -->|"healthy"| PH["1:1 to the two adults"]
  BRIDGE -.->|"stale 24h+"| EMAIL["SMTP email fallback<br/>(degraded, not green)"]
  EMAIL --> PH
```

> Documented deeper fallbacks (not in code): **Twilio WhatsApp** → **Inforu SMS**, revisited only after 2+ failures of the layers above.

---

## 5. Data model — who writes each tab, who reads it

One source of truth per domain. `lib/sheet.py` is the **only** Python writer; the dashboard writes back via OAuth. Schema changes are **additive-only**.

```mermaid
flowchart LR
  subgraph W["Writers"]
    direction TB
    ENG["Reminders engine"]
    DIGw["Daily digest"]
    SUMw["Summarizer"]
    PRPw["Property scraper"]
    FINw["Finance ingest"]
    INSTw["Budget installer"]
    HUM["Humans (PWA + manual)"]
  end
  subgraph TABS["Family_OS Sheet tabs"]
    direction TB
    R[("Reminders<br/>keystone")]
    WI[("WhatsApp_Inbox / _Archive")]
    GC[("WhatsApp_Group_Config")]
    PL[("Property-Listings")]
    FT[("Finance-Transactions")]
    FA[("Finance-Accounts")]
    FB[("Finance-Budget")]
    OT[("People / Goals / Health /<br/>Education / Car / Contracts /<br/>Calendar-Events / Settings ...")]
  end
  subgraph RD["Readers"]
    direction TB
    DIGr["Daily digest"]
    WKr["Weekly briefing"]
    PWAr["Dashboard PWA"]
  end
  ENG --> R
  DIGw --> R
  HUM --> R
  HUM --> GC
  HUM --> OT
  SUMw --> WI
  PRPw --> PL
  FINw --> FT
  FINw --> FA
  INSTw --> FB
  FT -->|"SUMIFS"| FB
  R --> DIGr
  R --> PWAr
  PL --> DIGr
  FA --> WKr
  FT --> WKr
  FB --> WKr
  FA --> PWAr
  FB --> PWAr
  OT --> PWAr
```

**Keys:** Reminders write-back stamps cols `M LastDoneBy · N DoneAt · O WriteQueue_Tombstone`. Property dedups on `listing_id` (vs `seen.json`). Finance dedups on `Txn-ID` = stable hash of `Date|Amount|Description|Account` (the provider id was rejected — it collided and dropped ~70% of rows on first import).

---

## 6. The two ingestion lanes — property + finance

Both deliver **silently** and never spend the alert budget.

```mermaid
flowchart TD
  subgraph PROP["Property lane (silent)"]
    direction TB
    Y["Yad2 / Madlan<br/>saved-search pages"] --> PS["property_scrape.py<br/>headed Chromium under Xvfb"]
    AP["Apify (secondary,<br/>primary always wins)"] -.-> PS
    PS --> SEEN{"new listing_id?<br/>(diff vs seen.json)"}
    SEEN -->|"no"| DROP["ignore"]
    SEEN -->|"yes"| PLT[("Property-Listings tab")]
    PLT --> DG["07:30 digest<br/>new-listings section"]
  end
  subgraph FINX["Finance lane (live: Mizrahi debit since 2026-06-19)"]
    direction TB
    MZ["Mizrahi portal<br/>(read-only; Max/Cal dormant)"] --> SC["scrape.js Node<br/>~45-day window"]
    SC --> CSV["per-provider CSV<br/>(/var/lib staging)"]
    CSV --> ING["finance_ingest.py"]
    ING --> RULES{"on-box rules<br/>match category?"}
    RULES -->|"yes"| FTX[("Finance-Transactions<br/>Txn-ID dedup")]
    RULES -->|"no (remainder)"| GPT["DeepSeek<br/>desc + amount only"]
    GPT --> FTX
    ING --> FAC[("Finance-Accounts<br/>upsert")]
    FTX -->|"SUMIFS"| FBD[("Finance-Budget")]
    FBD --> CONS["Weekly Money section<br/>+ dashboard drawer"]
    FAC --> CONS
  end
```

---

## 7. WhatsApp summarizer — classification pipeline

Hard rules run first (cheap, deterministic); only the remainder reaches the LLM; if there's no key, a keyword fallback keeps it working keyless.

```mermaid
flowchart TD
  M["New group message<br/>(inbox.jsonl)"] --> H1{"muted group?"}
  H1 -->|"yes"| ROUTINE["ROUTINE (raise nothing)"]
  H1 -->|"no"| H2{"critical keyword?"}
  H2 -->|"yes"| CRIT["CRITICAL<br/>budget-exempt, pierces mute"]
  H2 -->|"no"| H3{"alert keyword /<br/>teacher-evening / vaad?"}
  H3 -->|"yes"| ALERT["ALERT"]
  H3 -->|"no"| H4{"media-only?"}
  H4 -->|"yes"| ROUTINE
  H4 -->|"no"| LLMC["LLM classify<br/>(1 msg + up to 3 context)"]
  LLMC -.->|"no key"| KW["keyword fallback"]
  LLMC --> CLASS{"class?"}
  KW --> CLASS
  CLASS -->|"ALERT"| ALERT
  CLASS -->|"DIGEST"| DGsec["into 07:30 digest"]
  CLASS -->|"ROUTINE"| ROUTINE
  CRIT --> OB["Outbox"]
  ALERT --> OB
```

---

## 8. Deploy topology — committed ≠ deployed

`deploy.sh` is the only way code reaches the box; red tests abort the deploy and leave running code untouched. Timers pick up new code on their next fire — only the long-running bridge is restarted.

```mermaid
flowchart LR
  DEV["PO machine<br/>git push"] --> ORIGIN["origin/main (GitHub)"]
  ORIGIN -->|"git pull --ff-only"| DEP["deploy.sh on VPS"]
  DEP --> SYNC["uv sync --frozen<br/>npm ci (bridge + finance)"]
  SYNC --> TEST{"pytest -q green?"}
  TEST -->|"red"| ABORT["abort — running code untouched"]
  TEST -->|"green"| RESTART["systemctl restart family-bridge<br/>(timers pick up code next fire)"]
  ORIGIN -->|"dashboard/** push"| PAGES["GitHub Actions<br/>-> GitHub Pages"]
  PAGES --> IPH["PWA on both iPhones<br/>(next open)"]
```

---

## 9. Status & roadmap

```mermaid
flowchart TB
  subgraph SHIPPED["Shipped — v1-live since 2026-06-13"]
    direction LR
    s1["Keystone loop"]
    s2["Weekly briefing"]
    s3["WhatsApp summarizer"]
    s4["Property tracker"]
    s5["Delivery hardening<br/>(SMTP fallback)"]
    s6["Go-live + PWA published"]
  end
  subgraph PROG["In progress — M6 finance ingestion"]
    direction LR
    p1["M6.1 schema (done)"]
    p2["M6.2 live on Mizrahi<br/>(done, 98/98)"]
    p3["M6.3 consumers<br/>briefing + dashboard"]
    p4["M6.4 analysis layer"]
  end
  subgraph GATED["Gated ~2026-06-26 — needs 1 week live data"]
    direction LR
    g1["Classifier-accuracy run"]
    g2["External milestone review"]
    g3["Shanee budget-vocab migration"]
  end
  subgraph FROZEN["Frozen — needs a PO call to unfreeze"]
    direction LR
    f1["big-charge alert (500 ILS+)"]
    f2["ai-briefing (privacy call)"]
    f3["GCal / iCloud ingest"]
  end
  SHIPPED --> PROG --> GATED
```

**v1.1 ranked sequence** (bars are *illustrative ordering*, not committed dates — the real window now→~06-26 is a hardening slot, not a feature slot):

```mermaid
gantt
  title v1.1 ranked sequence (illustrative)
  dateFormat YYYY-MM-DD
  axisFormat %m-%d
  section Now -> 06-26 (hardening)
  CI gate + PII guard + config smoke   :a1, 2026-06-20, 2d
  GAP-7 Hebcal fail-loud               :a2, after a1, 1d
  DESIGN reconcile (verify)            :a3, after a1, 1d
  Lane C dashboard write-contract      :a4, after a2, 2d
  uptime-ping dead-man                 :a5, after a2, 1d
  Box-side verification of live claims :a6, after a3, 1d
  section After 06-26
  M6.3/M6.4 acceptance                 :b1, 2026-06-26, 3d
  classifier-fp-metric channel         :b2, after b1, 2d
  bridge scope-guard harness           :b3, after b1, 2d
  section Later v1.1 (post 30-day hold)
  reply-parsing (done/snooze)          :c1, after b3, 4d
  inbox-trigger (sub-hour critical)    :c2, after c1, 3d
  calendar-connectors                  :c3, after c1, 5d
```

---

## 10. Repo layout

```text
Family-Inc/
├── automation/                  # Python — all the brains (timers exec these directly)
│   ├── reminders_engine.py        # 07:25 compute fires (does not send)
│   ├── daily_digest.py            # 07:30 assemble + send one message per adult
│   ├── weekly_briefing.py         # Sat 21:00 deterministic narrative (no LLM)
│   ├── whatsapp_summarizer.py     # hourly classify group messages
│   ├── property_scrape.py         # Yad2 / Madlan listings
│   ├── finance_ingest.py          # CSV -> categorized, deduped Sheet write
│   ├── finance_budget_formulas.py # idempotent SUMIFS installer
│   ├── accuracy_review.py         # weekly classifier false-positive audit
│   ├── hebcal_client.py · templates.py · review.py · session_kickoff.py
│   ├── lib/                       # shared utils — the ONLY place externals are touched
│   │   ├── sheet.py                 # the ONLY Sheet writer (gspread service account)
│   │   ├── outbox.py                # THE chokepoint (budget / dedup / quiet-hours / scope)
│   │   ├── llm.py                   # one LLM wrapper (DeepSeek default, keyless fallback)
│   │   ├── apify.py                 # property secondary source
│   │   └── categorize · finance_budget · money · dates · config · mailer
│   ├── bridge/                    # Node — Baileys WhatsApp bridge (always-on service)
│   └── finance/                   # Node — israeli-bank-scrapers (scrape.js)
├── dashboard/                   # vanilla-JS PWA on GitHub Pages — app.js, index.html, sw.js
├── deploy/                      # deploy.sh, provision.sh, backup.sh, systemd/ units, *.example.json
├── tests/                       # hermetic pytest suite (~390 tests)
├── seeds/                       # CSV seeds (Israeli reminders, finance category rules)
├── Briefings/                   # generated weekly briefings + accuracy reports
├── Archive/                     # superseded canon + retired D-NN decision log
├── SPEC.md ENGINEERING.md DESIGN.md BACKLOG.md ROADMAP.md   # the 5 canon docs
├── CLAUDE.md                    # session context (auto-loaded)
└── Family_OS.xlsx               # seed template ONLY (nothing reads it at runtime)
```

---

## 11. The seven operating principles (SPEC §3)

1. **One source of truth per domain** — every datum has exactly one authoritative home; everything else is a disposable cache/view.
2. **Boring tech** — Sheets over a DB, vanilla JS over a framework, systemd over orchestration, JSONL over queues. A new dependency must *remove* a failure mode.
3. **Alerts are a budget** — hard cap 2/recipient/day at one chokepoint; criticals bypass (with audit trail); scheduled briefings are exempt.
4. **Briefings > notifications** — the default unit is a scheduled digest; a real-time message must justify itself.
5. **Partner-symmetric** — both adults see/act on everything as equals; no scoring; the digest goes to both *every* day so silence always means a broken digest, never an empty one.
6. **Fail loud, degrade quiet** — infra failures surface in the next briefing; feature degradation (LLM down → deterministic fallback) pages no one. Exception: time-critical data (candle-lighting) shows an explicit "unavailable" line, never silence.
7. **Never promise an affordance the system doesn't have** — no reply commands until reply-parsing ships; no buttons that don't write.
