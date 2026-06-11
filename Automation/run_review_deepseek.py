#!/usr/bin/env python3
"""Run a milestone review prompt against the DeepSeek API.

Companion to review.py: review.py *assembles* the prompt (use --dry-run > file),
this script *sends* it to DeepSeek and saves the response as the audit trail.
Will be folded into review.py as a provider in M1.

Two modes:
  plain (default)  one blocking call — use on a normal machine
  --chunk          one bounded call per invocation, conversation state kept in
                   --state JSON; rerun until it prints DONE. For environments
                   that cap process lifetime (e.g. sandboxed shells).

Usage:
    DEEPSEEK_API_KEY=... python3 Automation/run_review_deepseek.py \
        --prompt Briefings/<assembled_prompt>.md [--model deepseek-chat] \
        [--out Briefings/review_<ts>.md] [--chunk --state /tmp/ds_state.json]

The API key comes ONLY from the environment — never hardcode it, never commit it.
"""

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

API_URL = "https://api.deepseek.com/chat/completions"
DRY_RUN_MARKER = "DRY RUN — prompt that would be sent:"


def load_prompt(path: str) -> str:
    """Read the prompt file; strip review.py's --dry-run header if present."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if DRY_RUN_MARKER in text:
        after = text.split(DRY_RUN_MARKER, 1)[1]
        lines = after.splitlines()
        while lines and (not lines[0].strip() or set(lines[0].strip()) == {"="}):
            lines.pop(0)
        text = "\n".join(lines)
    return text.strip()


def call_api(messages: list, model: str, max_tokens: int, key: str, timeout: int) -> dict:
    body = json.dumps({"model": model, "messages": messages,
                       "max_tokens": max_tokens, "stream": False}).encode()
    req = urllib.request.Request(
        API_URL, data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def write_out(out_path: str, model: str, prompt_path: str, content: str, meta: str) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    header = (f"# Milestone review · {model} · {ts}\n\n"
              f"*Prompt: `{prompt_path}` · {meta}*\n\n---\n\n")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header + content + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--model", default="deepseek-chat",
                    help="deepseek-chat (default) or deepseek-reasoner (plain mode only)")
    ap.add_argument("--max-tokens", type=int, default=8000, help="plain-mode output cap")
    ap.add_argument("--out", default=None)
    ap.add_argument("--chunk", action="store_true", help="one bounded call per run")
    ap.add_argument("--chunk-tokens", type=int, default=1100)
    ap.add_argument("--state", default="/tmp/ds_review_state.json")
    args = ap.parse_args()

    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        print("ERROR: DEEPSEEK_API_KEY not set.", file=sys.stderr)
        return 2

    out_path = args.out or f"Briefings/review_{dt.datetime.now():%Y-%m-%d_%H-%M}.md"

    if not args.chunk:  # ---- plain mode ----
        prompt = load_prompt(args.prompt)
        print(f"INFO sending {len(prompt):,} chars to {args.model} …", flush=True)
        try:
            data = call_api([{"role": "user", "content": prompt}],
                            args.model, args.max_tokens, key, timeout=900)
        except Exception as e:  # noqa: BLE001 — fail loud
            print(f"ERROR {type(e).__name__}: {e}", file=sys.stderr)
            return 1
        ch = data["choices"][0]
        u = data.get("usage", {})
        write_out(out_path, args.model, args.prompt, ch["message"].get("content") or "",
                  f"finish: {ch.get('finish_reason')} · tokens {u.get('prompt_tokens')}/"
                  f"{u.get('completion_tokens')}")
        print(f"DONE → {out_path}")
        return 0

    # ---- chunked mode: one call per invocation, state carries the conversation ----
    if os.path.exists(args.state):
        with open(args.state, encoding="utf-8") as f:
            state = json.load(f)
    else:
        state = {"messages": [{"role": "user", "content": load_prompt(args.prompt)}],
                 "parts": [], "out_tokens": 0}

    try:
        data = call_api(state["messages"], args.model, args.chunk_tokens, key, timeout=40)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR {type(e).__name__}: {e} — state untouched, rerun.", file=sys.stderr)
        return 1

    ch = data["choices"][0]
    piece = ch["message"].get("content") or ""
    finish = ch.get("finish_reason")
    state["parts"].append(piece)
    state["out_tokens"] += data.get("usage", {}).get("completion_tokens", 0)

    if finish == "length":
        # continue the assistant turn next invocation
        if state["messages"][-1]["role"] == "assistant":
            state["messages"][-1]["content"] += piece
        else:
            state["messages"].append({"role": "assistant", "content": piece})
            state["messages"].append(
                {"role": "user",
                 "content": "Continue your review exactly where it cut off. "
                            "Do not repeat anything already written."})
        # keep the continue-instruction after the growing assistant message
        if state["messages"][-1]["role"] == "assistant":
            state["messages"].append(
                {"role": "user",
                 "content": "Continue your review exactly where it cut off. "
                            "Do not repeat anything already written."})
        with open(args.state, "w", encoding="utf-8") as f:
            json.dump(state, f)
        print(f"CONTINUE (part {len(state['parts'])}, {state['out_tokens']} tokens so far)")
        return 3

    write_out(out_path, args.model, args.prompt, "".join(state["parts"]),
              f"chunked × {len(state['parts'])} · {state['out_tokens']} output tokens")
    if os.path.exists(args.state):
        os.remove(args.state)
    print(f"DONE → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
