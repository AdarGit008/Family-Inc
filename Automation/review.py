"""
Family inc. — Session-end review automation

Automates steps 1+3 of the session-end review ritual (CLAUDE.md §"Session-end
ritual"). Builds the canonical adversarial-but-fair review prompt, attaches
the lane-specific context files, sends to Ollama, and writes the full audit
trail to Briefings/.

Provider = Ollama (switched from OpenCode Zen 2026-06-04, Adar's call).
One OpenAI-compatible endpoint for everything:

    {OLLAMA_HOST}/v1/chat/completions

- **Ollama Cloud** (default): OLLAMA_HOST unset → https://ollama.com.
  Needs OLLAMA_API_KEY. Catalog: https://ollama.com/search?c=cloud
  (deepseek, gpt-oss, qwen, kimi, glm, …; list models via GET /v1/models).
- **Local Ollama**: set OLLAMA_HOST=http://localhost:11434 — no key needed.
  ₪0/run, fully in-house, same privacy posture as the WhatsApp bridge.

The ritual's "Gemini" is a ROLE (external adversarial reviewer outside our
context), not a vendor commitment — any sufficiently strong model can hold it.
Pick with --model.

──────────────────────────────────────────────────────────────────────────────
 WHERE TO PUT THE API KEY (cloud only)
──────────────────────────────────────────────────────────────────────────────

1. Get your key at https://ollama.com → sign in → API keys.

2. Put it in your shell as the OLLAMA_API_KEY env var. Easiest persistent
   spot on macOS (zsh):

       echo 'export OLLAMA_API_KEY="..."' >> ~/.zshrc
       source ~/.zshrc

   Verify: `echo $OLLAMA_API_KEY` should print the key.

3. Or one-shot for a single run (good when you don't want it in shell history):

       OLLAMA_API_KEY="..." python3 Automation/review.py ...

The script never reads from a file or prompts interactively — only env. If
the var is missing (and the host is not local), the script falls back to MOCK
MODE and writes a placeholder audit file (same convention as
friday_briefing.py).

──────────────────────────────────────────────────────────────────────────────

Run:
    # Standard end-of-session review for a dashboard lane:
    python3 review.py --lane dashboard \\
        --changes session_changes.md \\
        --extra-files Dashboard/index.html,Dashboard/app.js,Dashboard/styles.css

    # Different model than the default:
    python3 review.py --lane spec --model qwen3-coder:480b --changes - < changes.md

    # Local Ollama (no key, no cloud):
    OLLAMA_HOST=http://localhost:11434 python3 review.py --lane spec \\
        --model llama3.3 --changes session_changes.md

    # Sanity-check the prompt before burning tokens:
    python3 review.py --lane dashboard --changes session_changes.md --dry-run

Output:
    Briefings/review_<lane>_<YYYY-MM-DD_HH-MM>.md  — prompt + response
    (also prints the response body to stdout)

Cost: Ollama Cloud has a free tier (rate-limited) + flat-rate paid plans —
no per-token billing to estimate. Local = free.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

# Uses `requests` (already in Automation/README.md's pip line) — it bundles
# certifi, so SSL Just Works on every Python install. Stdlib urllib hits
# CERTIFICATE_VERIFY_FAILED on macOS python.org installs without running
# `Install Certificates.command` first.
try:
    import requests
except ImportError as _e:
    raise SystemExit(
        "review.py requires the 'requests' package. Install with:\n"
        "    pip install requests"
    ) from _e

ROOT = Path(__file__).parent.parent  # Family Inc/
BRIEFINGS_DIR = ROOT / "Briefings"

API_KEY_ENV = "OLLAMA_API_KEY"
HOST_ENV = "OLLAMA_HOST"                 # set to http://localhost:11434 for local
DEFAULT_HOST = "https://ollama.com"      # Ollama Cloud
DEFAULT_MODEL = "deepseek-v3.1:671b"     # strong adversarial reviewer; override with --model

log = logging.getLogger("review")

# ----------------------------------------------------------------------------
# Prompt template — MIRROR of CLAUDE.md §"Step 1 — Claude generates the Gemini
# prompt". If you edit the canonical ritual in CLAUDE.md, also update this
# constant. Kept inline (not parsed) so the script doesn't break if CLAUDE.md
# is reorganized.
# ----------------------------------------------------------------------------

PROMPT_TEMPLATE = """\
You are reviewing engineering decisions made in a working session on the "Family Inc"
household-automation project. You are the explicit adversarial-but-fair reviewer. The
team owners (Adar = CTO, Shanee = Chief Design + PO) value pushback over agreement.

## Project one-paragraph context
Adar's household-automation system. Master DB = Google Sheets. PWA dashboard pinned
to iPhone, write-back to the Sheet. Briefings via WhatsApp (self-hosted Baileys bridge). Israeli context
(ILS, Hebrew, Maccabi healthcare). Family = 2 adults + 2 kids (⟨child-1⟩ 3yr, ⟨child-2⟩ 3mo).
Operating principles: briefings > notifications, alert budget 2/day, no kid-facing UI,
boring tech, one source of truth per domain.

## What this session changed
{session_changes}

## What I want you to review
1. Architectural soundness of the changes above.
2. Missed alternatives or simpler paths we didn't consider.
3. Tradeoffs we made implicitly without writing them down.
4. Risks / failure modes not covered.
5. Internal consistency across the changed files.

## What I do NOT want you to review
- Style, tone, formatting, copyediting.
- Adherence to design "best practices" in the abstract — only call those out if
  ignoring them creates a concrete risk for THIS project.
- The roles or session ritual itself (out of scope; that's our process).
- Files I did not list in "What this session changed" — assume those are settled.

## Required output (use these headings, in this order)
### Concerns
Things that should change. Be specific (file + section). Rank by severity.

### Missed alternatives
Paths we likely didn't explore. One-sentence each. Don't develop them — just name them.

### Affirmations
Decisions you think are correct, especially non-obvious ones. Brief.

### Concrete suggestions
Edits we could make right now. Phrase as "replace X with Y because Z."

### One question for the team
The single most useful question you'd ask Adar+Shanee+Claude if you had one.

Be terse. We're going to act on this directly.

---

## Attached context files

The following files are attached for you to read. Each is delimited by a header line.
Reference them by relative path in your review.

{attached_files}
"""

SYSTEM_INSTRUCTION = (
    "You are an adversarial-but-fair engineering reviewer. Output the five required "
    "sections in order and nothing else. Be specific (cite file paths + sections). "
    "Push back when warranted; the team values disagreement over agreement."
)

# ----------------------------------------------------------------------------
# Lane → default attachment mapping (mirrors CLAUDE.md §"Step 2")
# ----------------------------------------------------------------------------

ALWAYS_ATTACH = [
    "CLAUDE.md",
    "06_Lift_Recommendations_2026-05-30.md",
]

LANE_DEFAULTS: dict[str, list[str]] = {
    "dashboard": [
        "05_Dashboard_Design.md",
        "Dashboard/DESIGN_LOG.md",
        # Dashboard/{index.html,app.js,styles.css} — pass via --extra-files,
        # since which ones were touched varies session-to-session.
    ],
    "automation": [
        "02_Reminders_Engine_Spec.md",
        # Specific Automation/*.py via --extra-files
    ],
    "setup": [
        # Specific Setup/*.md via --extra-files
    ],
    "whatsapp": [
        "07_WhatsApp_Group_Summarizer_Spec.md",
    ],
    "spec": [
        # New doc + referenced docs via --extra-files
    ],
}

# ----------------------------------------------------------------------------
# Ollama provider — one OpenAI-compatible endpoint, cloud or local
# ----------------------------------------------------------------------------


@dataclass
class OllamaProvider:
    """Ollama — cloud (https://ollama.com, needs OLLAMA_API_KEY) or local
    (OLLAMA_HOST=http://localhost:11434, no key).

    Single request shape for every model: POST {host}/v1/chat/completions
    (OpenAI Chat Completions compatible). This replaced OpenCode Zen's
    four-route dispatch on 2026-06-04 — one shape, less to break.
    """

    model: str = DEFAULT_MODEL
    api_key: str = ""
    host: str = DEFAULT_HOST

    def __post_init__(self):
        self.api_key = os.environ.get(API_KEY_ENV, "")
        self.host = os.environ.get(HOST_ENV, DEFAULT_HOST).rstrip("/")

    def is_local(self) -> bool:
        return "localhost" in self.host or "127.0.0.1" in self.host

    def has_key(self) -> bool:
        # Local Ollama needs no key; cloud does.
        return self.is_local() or bool(self.api_key)

    def call(self, system: str, user: str, max_tokens: int = 8000) -> str:
        url = f"{self.host}/v1/chat/completions"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        log.info("POST %s (model=%s)", url, self.model)
        resp = _post_json(url, body, headers)
        return _extract_text(resp)


def _post_json(url: str, body: dict, headers: dict, timeout: int = 180) -> dict:
    h = {"content-type": "application/json", **headers}
    r = requests.post(url, headers=h, json=body, timeout=timeout)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} {r.reason}: {r.text[:1000]}")
    return r.json()


def _extract_text(resp: dict) -> str:
    """Pull the assistant text out of an OpenAI Chat Completions response.

    Detects truncation (finish_reason: "length") and surfaces it as a suffix
    so a partial review isn't mistaken for a complete one. Reasoning models
    may return their visible answer alongside a `reasoning` field — we only
    take `content`.
    """
    incomplete_reason = None
    choices = resp.get("choices") or [] if isinstance(resp, dict) else []
    if choices and choices[0].get("finish_reason") == "length":
        incomplete_reason = "length"

    try:
        text = resp["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        # Preserve more of the raw payload (4KB) so debugging is possible.
        raise RuntimeError(
            f"Ollama response malformed: {e}. "
            f"Raw response (truncated): {json.dumps(resp)[:4000]}"
        ) from e

    if not text:
        hint = ""
        if incomplete_reason:
            hint = (
                " — response truncated by 'length'. Reasoning models burn "
                "output tokens on internal reasoning before the visible "
                "answer; try --max-tokens 32000+ or a non-reasoning model."
            )
        raise RuntimeError(
            f"Ollama returned no text content{hint}. "
            f"Raw response (truncated): {json.dumps(resp)[:4000]}"
        )

    if incomplete_reason:
        # Append a note so partial output isn't mistaken for a complete review.
        text += (
            f"\n\n---\n*Note: this response was truncated "
            f"(reason: `{incomplete_reason}`). Re-run with `--max-tokens 32000` "
            f"or a non-reasoning model for the full review.*\n"
        )
    return text


# ----------------------------------------------------------------------------
# File assembly
# ----------------------------------------------------------------------------


@dataclass
class AttachedFile:
    rel_path: str
    contents: str

    def render(self) -> str:
        return f"=== File: {self.rel_path} ===\n{self.contents}\n=== End: {self.rel_path} ===\n"


def resolve_files(paths: Iterable[str]) -> list[AttachedFile]:
    """Read each path (relative to ROOT) into an AttachedFile.

    Missing files are warned about and skipped — better to send a partial
    review than fail the whole session over a typo.
    """
    seen: set[str] = set()
    out: list[AttachedFile] = []
    for p in paths:
        p = p.strip()
        if not p or p in seen:
            continue
        seen.add(p)
        abs_path = (ROOT / p).resolve()
        if not abs_path.exists():
            log.warning("attached file not found, skipping: %s", p)
            continue
        try:
            text = abs_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            log.warning("attached file not utf-8, skipping: %s", p)
            continue
        out.append(AttachedFile(rel_path=p, contents=text))
    return out


def read_changes(source: str) -> str:
    """Read the 'What this session changed' bullet list.

    Either a path to a markdown file, or '-' for stdin.
    """
    if source == "-":
        return sys.stdin.read().strip()
    path = Path(source)
    if not path.is_absolute():
        path = (ROOT / source).resolve()
    if not path.exists():
        raise SystemExit(f"changes file not found: {source}")
    return path.read_text(encoding="utf-8").strip()


def assemble_prompt(session_changes: str, files: list[AttachedFile]) -> str:
    attached = "\n".join(f.render() for f in files)
    return PROMPT_TEMPLATE.format(
        session_changes=session_changes,
        attached_files=attached,
    )


# ----------------------------------------------------------------------------
# Output
# ----------------------------------------------------------------------------


def write_audit(
    lane: str,
    provider: OllamaProvider,
    files: list[AttachedFile],
    user_prompt: str,
    response: str,
    elapsed_s: float,
) -> Path:
    BRIEFINGS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    out_path = BRIEFINGS_DIR / f"review_{lane}_{ts}.md"
    where = "local" if provider.is_local() else "cloud"
    header = (
        f"# Gemini-style Review — {lane} lane\n\n"
        f"- **When:** {datetime.now().isoformat(timespec='seconds')}\n"
        f"- **Provider:** Ollama {where} (`{provider.model}`)\n"
        f"- **Elapsed:** {elapsed_s:.1f}s\n"
        f"- **Attached files ({len(files)}):**\n"
    )
    file_list = "\n".join(f"  - `{f.rel_path}` ({len(f.contents):,} chars)" for f in files)
    body = (
        f"{header}{file_list}\n\n"
        f"---\n\n## Response\n\n{response}\n\n"
        f"---\n\n<details>\n<summary>Full prompt sent (click to expand)</summary>\n\n"
        f"```\n{user_prompt}\n```\n\n</details>\n"
    )
    out_path.write_text(body, encoding="utf-8")
    return out_path


# ----------------------------------------------------------------------------
# Mock fallback (matches the Automation pack convention)
# ----------------------------------------------------------------------------

MOCK_RESPONSE = f"""\
### Concerns
(MOCK MODE — OLLAMA_API_KEY is not set and OLLAMA_HOST is not local; this is
a placeholder so the audit-trail file still gets written. See the module
docstring for where to put your Ollama API key, or set
OLLAMA_HOST=http://localhost:11434 for a local instance.)

### Missed alternatives
- None evaluated.

### Affirmations
- None evaluated.

### Concrete suggestions
- Set OLLAMA_API_KEY in your shell (see top of review.py) and re-run.

### One question for the team
- Which model in the Ollama catalog do we want as the default reviewer?
  (script default: {DEFAULT_MODEL})
"""


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    ap = argparse.ArgumentParser(
        description="Send a session-end review to Ollama (cloud or local).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="API key: set OLLAMA_API_KEY (https://ollama.com → API keys). "
               "Local: set OLLAMA_HOST=http://localhost:11434 (no key needed).",
    )
    ap.add_argument("--lane", required=True, choices=sorted(LANE_DEFAULTS.keys()),
                    help="Which session lane this review covers (drives default file attachments).")
    ap.add_argument("--changes", required=True,
                    help='Path to a markdown file with the "What this session changed" '
                         'bullet list, or "-" for stdin.')
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"Ollama model id (default: {DEFAULT_MODEL}). "
                         f"Cloud catalog: https://ollama.com/search?c=cloud "
                         f"(or GET {DEFAULT_HOST}/v1/models).")
    ap.add_argument("--extra-files", default="",
                    help="Comma-separated additional files to attach (relative to project root).")
    ap.add_argument("--no-defaults", action="store_true",
                    help="Skip lane default attachments.")
    ap.add_argument("--no-always", action="store_true",
                    help="Also skip CLAUDE.md + 06_Lift_Recommendations.")
    ap.add_argument("--max-tokens", type=int, default=16000,
                    help="Max output tokens from the provider (default 16000). "
                         "Reasoning models (gpt-5*-pro, o-series) need 32000+ "
                         "because reasoning tokens count against this budget.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the assembled prompt + size estimate, do not call the API.")
    args = ap.parse_args()

    # Assemble file list: ALWAYS_ATTACH + lane defaults + extras, deduped, in order.
    file_paths: list[str] = []
    if not args.no_always:
        file_paths.extend(ALWAYS_ATTACH)
    if not args.no_defaults:
        file_paths.extend(LANE_DEFAULTS[args.lane])
    if args.extra_files:
        file_paths.extend([p.strip() for p in args.extra_files.split(",") if p.strip()])

    files = resolve_files(file_paths)

    session_changes = read_changes(args.changes)
    user_prompt = assemble_prompt(session_changes, files)

    total_chars = len(user_prompt)
    approx_tokens = total_chars // 4
    log.info("assembled prompt: %d files, %s chars (~%s tokens)",
             len(files), f"{total_chars:,}", f"{approx_tokens:,}")
    for f in files:
        log.info("  attached: %s (%s chars)", f.rel_path, f"{len(f.contents):,}")

    if args.dry_run:
        print("\n" + "=" * 78)
        print("DRY RUN — prompt that would be sent:")
        print("=" * 78 + "\n")
        print(user_prompt)
        return

    provider = OllamaProvider(model=args.model)

    if not provider.has_key():
        log.warning("RUNNING IN MOCK MODE — %s not set (see top of this file)", API_KEY_ENV)
        response = MOCK_RESPONSE
        elapsed = 0.0
    else:
        log.info("sending to Ollama %s (%s)...",
                 "local" if provider.is_local() else "cloud", provider.model)
        t0 = time.monotonic()
        try:
            response = provider.call(SYSTEM_INSTRUCTION, user_prompt, args.max_tokens)
        except Exception as e:
            # Don't lose the work — write the failure into the audit file so
            # we can recover the raw response and debug the shape mismatch.
            elapsed = time.monotonic() - t0
            log.error("provider call failed after %.1fs: %s", elapsed, e)
            response = (
                f"### Provider call failed\n\n"
                f"```\n{e}\n```\n\n"
                f"Audit file written so the request payload is preserved. "
                f"Re-run with a known-good model or report this shape to the "
                f"script maintainer.\n"
            )
            out_path = write_audit(args.lane, provider, files, user_prompt, response, elapsed)
            log.error("audit trail (with failure): %s", out_path)
            sys.exit(1)
        elapsed = time.monotonic() - t0
        log.info("response received in %.1fs (%d chars)", elapsed, len(response))

    out_path = write_audit(args.lane, provider, files, user_prompt, response, elapsed)
    log.info("audit trail: %s", out_path)

    # Print the response body to stdout for immediate consumption.
    print("\n" + "=" * 78)
    print(f"Review response (Ollama {provider.model}, {elapsed:.1f}s)")
    print("=" * 78 + "\n")
    print(response)
    print("\n" + "=" * 78)
    print(f"Full audit trail: {out_path}")
    print("=" * 78)


if __name__ == "__main__":
    main()
