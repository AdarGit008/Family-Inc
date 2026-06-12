"""
Family inc. — Milestone review automation (ENGINEERING.md §11, D-012)

Reviews fire on MILESTONES only: new spec, architecture change, anything
touching delivery/budget/privacy guarantees, and each M-close. This script
builds the canonical adversarial-but-fair review prompt, attaches the canon
docs + lane files, sends to the chosen provider, and writes the audit trail
to reviews/.

Providers (--provider):

- **ollama** (default) — one OpenAI-compatible endpoint for everything:
  `{OLLAMA_HOST}/v1/chat/completions`. Cloud (https://ollama.com, needs
  OLLAMA_API_KEY) or local (OLLAMA_HOST=http://localhost:11434, no key,
  ₪0/run, same privacy posture as the WhatsApp bridge).
- **deepseek** — https://api.deepseek.com, key from DEEPSEEK_API_KEY env ONLY
  (folded in from run_review_deepseek.py, M1). Supports --chunk for
  environments that cap process lifetime (one bounded call per invocation,
  conversation state in --state JSON; rerun until DONE).

The ritual's "Gemini" is a ROLE (external adversarial reviewer outside our
context), not a vendor commitment — any sufficiently strong model can hold it
(D-020 ran on DeepSeek when Gemini was unavailable). Pick with --model.

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
    # Milestone-close review (attaches all five canon docs):
    python3 automation/review.py --lane milestone \\
        --changes reviews/session_changes_<date>.md

    # Lane-scoped review with extra files:
    python3 automation/review.py --lane dashboard --changes changes.md \\
        --extra-files Dashboard/index.html,Dashboard/app.js

    # DeepSeek provider (key from env only):
    DEEPSEEK_API_KEY=... python3 automation/review.py --provider deepseek \\
        --lane milestone --changes changes.md

    # Local Ollama (no key, no cloud):
    OLLAMA_HOST=http://localhost:11434 python3 automation/review.py \\
        --lane spec --model llama3.3 --changes changes.md

    # Sanity-check the prompt before burning tokens:
    python3 automation/review.py --lane milestone --changes changes.md --dry-run

Output:
    reviews/review_<lane>_<YYYY-MM-DD_HH-MM>.md  — prompt + response, the
    audit trail (also prints the response body to stdout)

Failure behavior (ENGINEERING §11): a failed or truncated review never blocks
a milestone — the failure is written into the audit file; log it and proceed.

Cost: Ollama Cloud has a free tier; local = free; DeepSeek is per-token (cheap).
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

ROOT = Path(__file__).parent.parent  # repo root
REVIEWS_DIR = ROOT / "reviews"       # tracked audit trail (ENGINEERING §11)

API_KEY_ENV = "OLLAMA_API_KEY"
HOST_ENV = "OLLAMA_HOST"                 # set to http://localhost:11434 for local
DEFAULT_HOST = "https://ollama.com"      # Ollama Cloud
DEFAULT_MODEL = "deepseek-v3.1:671b"     # strong adversarial reviewer; override with --model

DEEPSEEK_KEY_ENV = "DEEPSEEK_API_KEY"    # env ONLY — never a file, never committed
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"

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
A household operating system for a two-adult, two-young-kid family in Israel
(ILS, Hebrew/RTL, Maccabi healthcare). Master DB = one Google Sheet. PWA dashboard
pinned to both iPhones, write-back to the Sheet. Messages via WhatsApp (self-hosted
Baileys bridge) through a single budgeted outbox. Operating principles (SPEC.md §3):
briefings > notifications, alert budget 2/day, no kid-facing UI, boring tech,
one source of truth per domain, fail loud / degrade quiet.

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
# Lane → default attachment mapping. The five canon docs (D-019) are the only
# specs that exist; superseded numbered docs live in Archive/ and are never
# attached.
# ----------------------------------------------------------------------------

ALWAYS_ATTACH = [
    "CLAUDE.md",
    "SPEC.md",
    "BACKLOG.md",
]

LANE_DEFAULTS: dict[str, list[str]] = {
    "milestone": [
        # M-close: the full canon. Session's code/doc deltas via --extra-files.
        "ENGINEERING.md",
        "DESIGN.md",
        "DECISIONS.md",
    ],
    "dashboard": [
        "DESIGN.md",
        # Dashboard/{index.html,app.js,styles.css} — pass via --extra-files,
        # since which ones were touched varies session-to-session.
    ],
    "automation": [
        "ENGINEERING.md",
        # Specific automation/*.py via --extra-files
    ],
    "whatsapp": [
        "DESIGN.md",   # message design system lives in DESIGN §6
    ],
    "spec": [
        "ENGINEERING.md",
        "DESIGN.md",
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

    def label(self) -> str:
        where = "local" if self.is_local() else "cloud"
        return f"Ollama {where} (`{self.model}`)"

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


@dataclass
class DeepSeekProvider:
    """DeepSeek API — folded in from run_review_deepseek.py (M1).

    Key from DEEPSEEK_API_KEY env ONLY. Models: deepseek-chat (default),
    deepseek-reasoner (plain mode only). Plain mode = one blocking call;
    chunked mode (--chunk) = one bounded call per invocation with the
    conversation kept in a state JSON — for environments that cap process
    lifetime (e.g. sandboxed shells). Rerun until it prints DONE.
    """

    model: str = DEEPSEEK_DEFAULT_MODEL
    api_key: str = ""

    def __post_init__(self):
        self.api_key = os.environ.get(DEEPSEEK_KEY_ENV, "")
        if self.model == DEFAULT_MODEL:  # ollama default leaked through --model
            self.model = DEEPSEEK_DEFAULT_MODEL

    def is_local(self) -> bool:
        return False

    def has_key(self) -> bool:
        return bool(self.api_key)

    def label(self) -> str:
        return f"DeepSeek (`{self.model}`)"

    def _call_messages(self, messages: list, max_tokens: int, timeout: int = 900) -> dict:
        return _post_json(
            DEEPSEEK_URL,
            {"model": self.model, "messages": messages,
             "max_tokens": max_tokens, "stream": False},
            {"Authorization": f"Bearer {self.api_key}"},
            timeout=timeout,
        )

    def call(self, system: str, user: str, max_tokens: int = 8000) -> str:
        resp = self._call_messages(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens)
        return _extract_text(resp)

    def call_chunked(self, system: str, user: str, state_path: Path,
                     chunk_tokens: int = 1100) -> tuple[str, str]:
        """One bounded call; returns ("CONTINUE"|"DONE", text_so_far)."""
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
        else:
            state = {"messages": [{"role": "system", "content": system},
                                  {"role": "user", "content": user}],
                     "parts": [], "out_tokens": 0}

        data = self._call_messages(state["messages"], chunk_tokens, timeout=40)
        ch = data["choices"][0]
        piece = ch["message"].get("content") or ""
        state["parts"].append(piece)
        state["out_tokens"] += data.get("usage", {}).get("completion_tokens", 0)

        if ch.get("finish_reason") == "length":
            # continue the assistant turn next invocation
            if state["messages"][-1]["role"] == "assistant":
                state["messages"][-1]["content"] += piece
            else:
                state["messages"].append({"role": "assistant", "content": piece})
            state["messages"].append(
                {"role": "user",
                 "content": "Continue your review exactly where it cut off. "
                            "Do not repeat anything already written."})
            state_path.write_text(json.dumps(state), encoding="utf-8")
            return "CONTINUE", "".join(state["parts"])

        if state_path.exists():
            state_path.unlink()
        return "DONE", "".join(state["parts"])


def make_provider(name: str, model: str):
    if name == "deepseek":
        return DeepSeekProvider(model=model)
    return OllamaProvider(model=model)


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
            f"Provider response malformed: {e}. "
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
            f"Provider returned no text content{hint}. "
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
    provider,
    files: list[AttachedFile],
    user_prompt: str,
    response: str,
    elapsed_s: float,
) -> Path:
    REVIEWS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    out_path = REVIEWS_DIR / f"review_{lane}_{ts}.md"
    header = (
        f"# Milestone review — {lane} lane\n\n"
        f"- **When:** {datetime.now().isoformat(timespec='seconds')}\n"
        f"- **Provider:** {provider.label()}\n"
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
(MOCK MODE — no provider key found; this is a placeholder so the audit-trail
file still gets written. Set OLLAMA_API_KEY, or OLLAMA_HOST=http://localhost:11434
for a local instance, or DEEPSEEK_API_KEY with --provider deepseek.)

### Missed alternatives
- None evaluated.

### Affirmations
- None evaluated.

### Concrete suggestions
- Set a provider key in your shell (see top of review.py) and re-run.

### One question for the team
- Which model do we want as the default reviewer? (ollama default: {DEFAULT_MODEL})
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
                    help="Which lane this review covers (drives default file attachments). "
                         "M-closes use 'milestone' (attaches all five canon docs).")
    ap.add_argument("--changes", required=True,
                    help='Path to a markdown file with the "What this session changed" '
                         'bullet list, or "-" for stdin.')
    ap.add_argument("--provider", default="ollama", choices=["ollama", "deepseek"],
                    help="Reviewer provider (default: ollama).")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"Model id (ollama default: {DEFAULT_MODEL}; "
                         f"deepseek default: {DEEPSEEK_DEFAULT_MODEL}).")
    ap.add_argument("--chunk", action="store_true",
                    help="DeepSeek only: one bounded call per invocation; rerun until DONE "
                         "(for shells that cap process lifetime).")
    ap.add_argument("--state", default="/tmp/family_inc_review_state.json",
                    help="Chunk-mode conversation state file.")
    ap.add_argument("--extra-files", default="",
                    help="Comma-separated additional files to attach (relative to project root).")
    ap.add_argument("--no-defaults", action="store_true",
                    help="Skip lane default attachments.")
    ap.add_argument("--no-always", action="store_true",
                    help="Also skip the always-attached canon docs.")
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

    provider = make_provider(args.provider, args.model)

    if args.chunk and not isinstance(provider, DeepSeekProvider):
        raise SystemExit("--chunk is only supported with --provider deepseek")

    if not provider.has_key():
        log.warning("RUNNING IN MOCK MODE — no key for provider %r (see top of this file)",
                    args.provider)
        response = MOCK_RESPONSE
        elapsed = 0.0
    elif args.chunk:
        t0 = time.monotonic()
        status, text = provider.call_chunked(SYSTEM_INSTRUCTION, user_prompt,
                                             Path(args.state))
        elapsed = time.monotonic() - t0
        if status == "CONTINUE":
            print(f"CONTINUE — rerun the same command (state: {args.state}, "
                  f"{len(text):,} chars so far)")
            sys.exit(3)
        response = text
    else:
        log.info("sending to %s...", provider.label())
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
    print(f"Review response ({provider.label()}, {elapsed:.1f}s)")
    print("=" * 78 + "\n")
    print(response)
    print("\n" + "=" * 78)
    print(f"Full audit trail: {out_path}")
    print("=" * 78)


if __name__ == "__main__":
    main()
