# Next session — Family Inc · Finance ingestion (PLANNING)

*Paste everything below the line to open the session. This is a **planning session** (no appliance touch, no new lane built) — like the D-031–034 data-fetching planning session. Output = PO calls logged in `DECISIONS.md` + a build plan, not code.*

*Note: M4's external milestone review (+ first real accuracy-review run) is still gated to ~2026-06-20 and remains open — finance planning is independent of it and can run first.*

---

You are opening a Family Inc planning session as Lead Architect. Read `CLAUDE.md` (roles, principles, guardrails) and `DECISIONS.md` D-031/D-033 before proposing anything. The topic is **unfreezing the finance-ingestion lane** (banks + credit cards). This is a frozen lane and a **major directional call → joint Adar + Shanee**, not a routine one.

**What's already decided (don't re-litigate — confirm or amend):**

* **Build architecture is pre-resolved (D-031):** runtime = the VPS, a `systemd` timer ~06:00 (NOT Render, NOT a second runtime); `israeli-bank-scrapers` (puppeteer/headless-Linux); staging = none (scrape → local CSV in `/var/lib/family-inc/finance/` → Python ingest → `lib/sheet`, the sole Sheet writer, D-016); the `Finance_CSVs` Drive folder is dropped. 2FA (Max/Cal): first run interactive (OTP once, session persisted), later re-challenges **fail loud** (§10.2 → fail-flag → digest), never silent.
* **Scope is raw only (D-033):** if finance thaws it delivers **raw, uncategorized** transactions. Hebrew categorization + anomaly/subscription detection were **killed** — they'd be net-new lanes, not part of this.
* **Consumer side partly exists:** the weekly briefing already has a Money section + a "stale Last Imported" hygiene warning (>35d) reading `Finance-Accts` — waiting for data.

**The two gating questions (both JOINT):**

1. **The unfreeze condition itself** — the lane is frozen pending *"POs commit to the monthly finance review using the data."* Stale finance data lies; without the ~20–30 min/month habit, don't thaw. Is the commitment real?
2. **The principle conflict — this is the crux.** SPEC §3 lists **"no credential storage"** as a non-negotiable v1 principle, but ingestion requires storing bank/card login creds (D-031 put them in `/etc/family-inc/bank_creds.json`). **Unfreezing finance amends a non-negotiable principle.** Decide explicitly: do we permit it, under what guardrails (mode 600, one box, encryption at rest, blast-radius limits), and how do we keep "no money movement" intact (the scrapers are read-only by nature — lean on that)?

**Then scope the build (if thawed):**

3. Which institutions (banks + cards — Max/Cal/Isracard, which bank)? What lands per transaction (date, amount, description, account, balance)?
4. Sheet schema: `Finance-Accts`, `Finance-Budget` (resolve the §6.4 `Finance-Budget` vs as-built `Finance-Bdgt` name drift flagged 2026-06-12), and a `Finance-Transactions` tab? Rolloff/retention?
5. Failure modes + what the briefing says (2FA re-challenge, a bank changing its site, scraper breakage).

**Pre-read:** confirm `israeli-bank-scrapers` is still maintained and working in 2026 (D-031 pinned v6.7.x) before committing the architecture.

Session contract: planning only — no appliance touch, no code lane opened until the joint unfreeze call lands in `DECISIONS.md` with the next D-number. Constants → config, utilities → `automation/lib/`. Regenerate `NEXT_SESSION_PROMPT.md` at session end. Git index operations run on the PO's machine, never in the sandbox.
