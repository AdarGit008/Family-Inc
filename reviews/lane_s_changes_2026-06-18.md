# Session changes — Brief 2, Lane S (publish / privacy safety)

Source: `reviews/fix_brief_2_…` Lane S (GAP-5 + deploy-systemd#4). Lane S trips
the review gate (publish/privacy). Tests 356→357 green.

## GAP-5 — `Family_OS.xlsx` binary blind spot

**Audit conclusion (all 18 tabs):** the committed seed is **synthetic by
construction** — bracketed placeholders, fake round dates, public brand names
(Bank Hapoalim/Cal/Harel/Clalit…), `example.com` emails, `000000000` Teudat-Zehut,
`[phone]`/`[email]` placeholders, sequential last-4s (1234/5678/…). A definitive
scan for real emails / IL phones / 9-digit IDs / JIDs / 12+-digit account numbers
across every cell returned **zero** real hits.

The only real identifiers are the two adult principals' first names `Adar`/`Shanee`.
These are **accepted-public by design**, not PII to scrub: they are the system's
owner-routing tokens (`reminders_engine.OWNER_TO_RECIPIENTS` lowercases the Owner
column → `adar`/`shanee`), the Settings UserMap display names, named throughout
`CLAUDE.md` (roles table), and the git author identity. Scrubbing them from the
seed alone would break routing + ~15 tests + canon-consistency for **zero** privacy
gain. So GAP-5's feared real-PII leak (Contacts/Health/Finance-Accounts) was
unfounded.

**Fix = the brief's "dedicated check" alternative:**
- New `tests/test_seed_safety.py` audits every tab and FAILS if any high-severity
  PII pattern (real email / IL phone / non-placeholder Teudat-Zehut / JID /
  account number) is ever added to the seed — making "public-safe by construction"
  enforced, not assumed, and catching future drift before a push. The principal
  names are explicitly allow-listed (documented). Guard regexes self-verified to
  fire on real values and ignore `example.com` / `000000000`.
- `deploy/publish_paths.txt` documents WHY the binary seed is kept at HEAD and
  guarded (it's the hermetic test backend; a binary can't be `--replace-text`
  scrubbed) rather than history-stripped via `--invert-paths` (which would break
  the test suite). No real PII in history (the seed has always been a template).

## deploy-systemd#4 — `publish.sh` regex gauntlet

`publish.sh` gauntlet 2 skipped `regex:` redaction rules (`case … regex:*) continue`),
so filter-repo APPLIED them but they were never VERIFIED before the public
force-push. Now the gauntlet verifies `regex:` rules with PCRE (`git grep -P`) and
**fails loud** if PCRE is unavailable, instead of silently passing.

## Not changed
No seed scrub (it's already clean). No history rewrite (no real PII in history;
the principal names are accepted-public). `Adar`/`Shanee` left intact as routing
tokens. Lane B/C and the rest of Lane E remain deferred.
