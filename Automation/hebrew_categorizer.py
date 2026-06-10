"""
Family inc. — Hebrew transaction categorizer

Three-layer pipeline:
  1. Cache layer  — Automation/cache/merchant_cache.json (normalized vendor -> category)
  2. Regex layer  — 20 hard-coded common Israeli merchants
  3. LLM fallback — Claude API (if ANTHROPIC_API_KEY set), 4-shot prompt; writes back to cache

Categories used (matches Family_OS Finance-Bdgt tab — adjust if the
budget tab changes):
  Groceries, Dining, Fuel, Transport, Utilities, Housing, Health,
  Childcare, Subscriptions, Shopping, Entertainment, Other

Public API:
  categorize(vendor: str, amount: float) -> str

Run:
  python hebrew_categorizer.py   # smoke test with 10 Hebrew vendors
"""
from __future__ import annotations
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent
CACHE_DIR = ROOT / "cache"
CACHE_PATH = CACHE_DIR / "merchant_cache.json"

log = logging.getLogger("categorizer")

CATEGORIES = [
    "Groceries", "Dining", "Fuel", "Transport", "Utilities", "Housing",
    "Health", "Childcare", "Subscriptions", "Shopping", "Entertainment", "Other",
]

# ---------------------------------------------------------------------------
# Layer 2 — 20 common Israeli merchants
# Patterns are matched against the normalized vendor (lowercased, trimmed).
# Hebrew patterns kept as Unicode regex; English entries fall through.
# ---------------------------------------------------------------------------
MERCHANT_RULES: list[tuple[str, str]] = [
    # Groceries
    (r"שופרסל",           "Groceries"),
    (r"רמי\s*לוי",        "Groceries"),
    (r"ויקטורי|victory",  "Groceries"),
    (r"יוחננוף|yochananof","Groceries"),
    (r"מגה|אושר\s*עד",    "Groceries"),
    (r"טיב\s*טעם",        "Groceries"),
    # Fuel
    (r"^פז\b|paz",        "Fuel"),
    (r"דלק|sonol|סונול", "Fuel"),
    (r"דור\s*אלון|delek","Fuel"),
    # Dining / fast food
    (r"מקדונלדס|mcdonald","Dining"),
    (r"ארומה|aroma",      "Dining"),
    (r"קפה\s*קפה",        "Dining"),
    (r"דומינו|domino",    "Dining"),
    # Transport / parking
    (r"רכבת|ישראל\s*קטרים","Transport"),
    (r"פנגו|pango|cellopark","Transport"),
    # Utilities / telco
    (r"חברת\s*חשמל",      "Utilities"),
    (r"בזק|partner|cellcom|פלאפון|hot|yes","Utilities"),
    # Health
    (r"סופר\s*פארם|super\s*pharm|בי\s*באר", "Health"),
    (r"מכבי|maccabi|כללית|clalit","Health"),
    # Subscriptions
    (r"netflix|נטפליקס|spotify|ספוטיפיי|youtube|apple\.com|google", "Subscriptions"),
]
# Pre-compile
_COMPILED = [(re.compile(p, re.IGNORECASE), c) for p, c in MERCHANT_RULES]

# ---------------------------------------------------------------------------
# Cache layer
# ---------------------------------------------------------------------------
def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

def _save_cache(cache: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")

def normalize(vendor: str) -> str:
    return re.sub(r"\s+", " ", vendor.strip().lower())

# ---------------------------------------------------------------------------
# Layer 3 — Claude fallback
# ---------------------------------------------------------------------------
FEWSHOT = [
    ("שופרסל דיל", 412.30, "Groceries"),
    ("פז כפר סבא", 310.00, "Fuel"),
    ("נטפליקס", 65.90,    "Subscriptions"),
    ("סופר פארם", 187.40, "Health"),
]

def _llm_classify(vendor: str, amount: float) -> Optional[str]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        log.warning("anthropic SDK not installed — skipping LLM fallback")
        return None
    shots = "\n".join(f"Vendor: {v}\nAmount: {a}\nCategory: {c}" for v, a, c in FEWSHOT)
    prompt = (
        "Classify the Israeli transaction into ONE of these categories: "
        + ", ".join(CATEGORIES)
        + ". Reply with only the category word.\n\n"
        + shots
        + f"\n\nVendor: {vendor}\nAmount: {amount}\nCategory:"
    )
    try:
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (msg.content[0].text or "").strip().split()[0]
        return text if text in CATEGORIES else "Other"
    except Exception as e:
        log.warning("Claude classify failed (%s)", e)
        return None

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def categorize(vendor: str, amount: float) -> str:
    n = normalize(vendor)
    cache = _load_cache()
    if n in cache:
        return cache[n]
    for pat, cat in _COMPILED:
        if pat.search(n):
            cache[n] = cat
            _save_cache(cache)
            return cat
    cat = _llm_classify(vendor, amount) or "Other"
    cache[n] = cat
    _save_cache(cache)
    return cat

# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------
SAMPLE = [
    ("שופרסל דיל",       412.30),
    ("פז כפר סבא",       310.00),
    ("רמי לוי שיווק",    640.00),
    ("מקדונלדס חיפה",    78.00),
    ("ארומה אספרסו",     32.00),
    ("נטפליקס",          65.90),
    ("סופר פארם",        187.40),
    ("בזק בינלאומי",     299.00),
    ("פנגו חניה",        14.00),
    ("חברת חשמל לישראל", 540.00),
]

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not has_key:
        print("(no ANTHROPIC_API_KEY — LLM fallback disabled, will use 'Other' for unknown)")
    print(f"{'vendor':<22} {'amount':>8}  category")
    print("-" * 50)
    for v, a in SAMPLE:
        c = categorize(v, a)
        print(f"{v:<22} {a:>8.2f}  {c}")
