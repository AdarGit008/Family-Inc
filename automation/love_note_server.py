"""
Family inc. — love-note endpoint (V3.7, SPEC §7.7).

THE one dashboard datum that is neither the Sheet nor the outbox: a tiny
authenticated dashboard→appliance HTTP endpoint holding ONE ephemeral note per
direction (Adar→Shanee, Shanee→Adar). A note dies at 24h-or-on-replacement and
shows on the recipient's NEXT dashboard open — no push, no alert-budget spend
(briefings > notifications, §3). Voice memos are a frozen phase-2 (SPEC §4 media
carve-out graduates only when voice ships); this server is text-only.

Hard guarantees (the load-bearing negatives — see tests/test_love_note_server):
  • never imports automation.lib.outbox — it is NOT an alert path (§3 chokepoint)
  • never WRITES the Sheet — it only READS Settings.UserMap to map email→parent
  • never persists or logs the caller's Google OAuth token
  • tight CORS — the Pages origin only; blank origin → CORS denies everyone, so
    the whole feature self-disables fail-safe (never promise a dead affordance)
  • unknown / non-parent email → 403; dual expiry (lazy on read + hourly sweep)
  • one note per direction — a second send overwrites the first

Shape: stdlib ThreadingHTTPServer bound to localhost; a Cloudflare Tunnel fronts
it (ENGINEERING §5). Storage is one flat JSON file per direction under the state
dir ({slug(from)}__to__{slug(to)}.json), atomic tmp+replace — the property /
finance seen.json idiom. The PWA verifies its live Google access_token by
forwarding it once to Google's userinfo endpoint; the email maps to a parent via
Settings.UserMap, then the token is dropped.

Separation of concerns (so the suite needs no sockets and no network):
  handle()         — pure: (method, path, headers, body) → (status, headers, obj).
                     Auth, dispatch, CORS, expiry — all here, all unit-tested.
  _token_introspect — the ONLY network seam (token → Google tokeninfo claims);
                     _verify_token wraps it (email_verified + audience); tests
                     monkeypatch the seam.
  _live_settings   — the ONLY Sheet read (cached); handle() takes it as a getter.
  LoveNoteHandler  — the thin BaseHTTPRequestHandler shell over handle().

Run:  uv run python automation/love_note_server.py        # binds LOVENOTE_PORT
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python automation/love_note_server.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import hashlib
import json
import logging
import time as _time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Optional

from automation.lib import config
from automation.lib import sheet

log = logging.getLogger("lovenote")

PATH = "/lovenote"
_ALLOW_METHODS = "GET, PUT, DELETE, OPTIONS"
_ALLOW_HEADERS = "Authorization, Content-Type"


class LoveNoteAuthError(RuntimeError):
    """The caller could not be resolved to one of the two parents (→ 403)."""


@dataclass
class Identity:
    me: str            # signed-in email (lowercased)
    me_name: str       # display name (Settings.UserMap)
    partner: str       # the other adult's email
    partner_name: str


# ---------------------------------------------------------------------------
# Storage — one flat JSON file per direction (flat-file idiom, like seen.json).
# A note is keyed by who it is FROM and who it is TO, so the two directions
# never collide and a re-send overwrites in place (one note per direction).
# ---------------------------------------------------------------------------
def slug(email: str) -> str:
    """Filesystem-safe key for an email (lowercased alphanumerics, '_' runs)."""
    out = []
    for ch in (email or "").strip().lower():
        out.append(ch if ch.isalnum() else "_")
    return "".join(out).strip("_") or "_"


def note_path(state_dir: Path, from_email: str, to_email: str) -> Path:
    return Path(state_dir) / f"{slug(from_email)}__to__{slug(to_email)}.json"


def _parse_iso(v) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(v))
    except (TypeError, ValueError):
        return None


def read_note(path: Path, now: datetime) -> Optional[dict]:
    """The note at `path`, or None — applying LAZY expiry: an expired or garbled
    file is unlinked on read (the belt; the hourly sweep is the suspenders)."""
    if not path.exists():
        return None
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        path.unlink(missing_ok=True)
        return None
    if not isinstance(rec, dict):          # valid JSON but not an object → garbled
        path.unlink(missing_ok=True)
        return None
    exp = _parse_iso(rec.get("expires_at"))
    if exp is None or now >= exp:
        path.unlink(missing_ok=True)
        return None
    return rec


def write_note(path: Path, rec: dict) -> None:
    """Atomic write (tmp + replace), exactly like the outbox/property writers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def clear_note(path: Path) -> None:
    path.unlink(missing_ok=True)


def sweep(state_dir: Path, now: datetime) -> int:
    """Hourly belt-and-suspenders: unlink every expired/garbled note. Returns the
    count removed. read_note() does the unlinking; we just tally."""
    state_dir = Path(state_dir)
    if not state_dir.exists():
        return 0
    removed = 0
    for p in sorted(state_dir.glob("*__to__*.json")):
        existed = p.exists()
        if read_note(p, now) is None and existed and not p.exists():
            removed += 1
    return removed


# ---------------------------------------------------------------------------
# Identity — Settings.UserMap is the two adults; the partner is the other one.
# ---------------------------------------------------------------------------
def resolve_identity(settings, email: str) -> Identity:
    email = (email or "").strip().lower()
    usermap = {k.strip().lower(): v for k, v in (settings.usermap or {}).items()}
    if email not in usermap:
        raise LoveNoteAuthError("unknown account")
    others = [e for e in usermap if e != email]
    if len(others) != 1:   # household is exactly two adults (§3) — fail loud
        raise LoveNoteAuthError("UserMap is not exactly two adults")
    partner = others[0]
    return Identity(me=email, me_name=usermap[email],
                    partner=partner, partner_name=usermap[partner])


def _make_record(idy: Identity, text: str, now: datetime, ttl_hours: int) -> dict:
    return {
        "from": idy.me, "from_name": idy.me_name,
        "to": idy.partner, "to_name": idy.partner_name,
        "text": text,
        "sent_at": now.isoformat(timespec="seconds"),
        "expires_at": (now + timedelta(hours=ttl_hours)).isoformat(timespec="seconds"),
    }


def _inbound_view(rec: dict) -> dict:
    # What the RECIPIENT sees — the sender + text + when. No "seen"/delivery
    # signal back to the sender (SPEC §3.7: the UI must not imply either).
    return {"from": rec.get("from_name", ""), "text": rec.get("text", ""),
            "sent_at": rec.get("sent_at", "")}


def _outbound_view(rec: dict) -> dict:
    # What the AUTHOR sees of their own waiting note (so they can replace/clear).
    return {"to": rec.get("to_name", ""), "text": rec.get("text", ""),
            "sent_at": rec.get("sent_at", ""), "expires_at": rec.get("expires_at", "")}


# ---------------------------------------------------------------------------
# CORS — allow-list of exactly one origin (the Pages PWA). A blank/unmatched
# origin gets NO Access-Control-Allow-Origin, so the browser blocks the read and
# the feature is inert until FAMILY_INC_LOVENOTE_ORIGIN is set on the box.
# ---------------------------------------------------------------------------
def _cors_headers(origin: str, allowed_origin: str) -> dict:
    h = {"Vary": "Origin"}
    if allowed_origin and origin and origin == allowed_origin:
        h["Access-Control-Allow-Origin"] = allowed_origin
        h["Access-Control-Allow-Methods"] = _ALLOW_METHODS
        h["Access-Control-Allow-Headers"] = _ALLOW_HEADERS
        h["Access-Control-Max-Age"] = "600"
    return h


def _header(headers, name: str) -> str:
    """Case-insensitive header read for both a dict (tests) and http.client's
    Message (the live handler)."""
    if headers is None:
        return ""
    get = getattr(headers, "get", None)
    if get is not None:
        v = get(name)
        if v is None and isinstance(headers, dict):
            low = {k.lower(): val for k, val in headers.items()}
            v = low.get(name.lower())
        return v or ""
    return ""


def _bearer(headers) -> str:
    auth = _header(headers, "Authorization")
    return auth[7:].strip() if auth.startswith("Bearer ") else ""


# ---------------------------------------------------------------------------
# The pure request core — every behavior + guarantee lives here, socket-free.
# ---------------------------------------------------------------------------
def handle(method: str, path: str, headers, body: bytes, *, now: datetime,
           get_settings: Callable[[], object], verify_token: Callable[[str], Optional[str]],
           state_dir: Path, allowed_origin: str, ttl_hours: int, max_chars: int):
    """(method, path, headers, body) → (status:int, headers:dict, obj:dict|None).
    `get_settings` and `verify_token` are the only side-effecting seams (Sheet
    read + token verification); tests inject fakes for both."""
    origin = _header(headers, "Origin")
    cors = _cors_headers(origin, allowed_origin)

    if method == "OPTIONS":                         # CORS preflight — no auth
        return 204, cors, None
    if path == "/healthz" and method == "GET":      # liveness for the tunnel
        return 200, cors, {"status": "ok"}
    if path != PATH:
        return 404, cors, {"error": "not found"}

    token = _bearer(headers)
    if not token:
        return 401, cors, {"error": "missing bearer token"}
    email = verify_token(token)
    if not email:
        return 401, cors, {"error": "invalid token"}

    try:
        settings = get_settings()
    except Exception as e:                           # Sheet unreachable → degrade
        log.warning("settings read failed (%s) — love-note unavailable", type(e).__name__)
        return 503, cors, {"error": "settings unavailable"}
    try:
        idy = resolve_identity(settings, email)
    except LoveNoteAuthError as e:
        return 403, cors, {"error": str(e)}

    inbound_path = note_path(state_dir, idy.partner, idy.me)   # partner → me
    outbound_path = note_path(state_dir, idy.me, idy.partner)  # me → partner

    if method == "GET":
        inbound = read_note(inbound_path, now)
        outbound = read_note(outbound_path, now)
        return 200, cors, {
            "inbound": _inbound_view(inbound) if inbound else None,
            "outbound": _outbound_view(outbound) if outbound else None,
        }

    if method == "PUT":
        try:
            payload = json.loads(body or b"{}")
        except ValueError:
            return 400, cors, {"error": "bad json"}
        if not isinstance(payload, dict):       # valid JSON but not an object
            return 400, cors, {"error": "bad json"}
        text = str(payload.get("text", "")).strip()
        if not text:
            return 400, cors, {"error": "empty note"}
        if len(text) > max_chars:
            return 400, cors, {"error": f"note too long (max {max_chars})"}
        rec = _make_record(idy, text, now, ttl_hours)
        write_note(outbound_path, rec)
        return 200, cors, {"status": "ok", "sent_at": rec["sent_at"],
                           "expires_at": rec["expires_at"]}

    if method == "DELETE":
        clear_note(outbound_path)
        return 200, cors, {"status": "ok"}

    return 405, cors, {"error": "method not allowed"}


# ---------------------------------------------------------------------------
# Side-effecting seams — the only network call + the only Sheet read.
# ---------------------------------------------------------------------------
def _token_introspect(token: str) -> Optional[dict]:
    """The ONLY network seam — GET Google's tokeninfo for an access_token, returning
    the parsed claims (email, email_verified, aud, azp, …) or None on any failure.
    Tests monkeypatch THIS. The token is never logged (only the exception type is)."""
    if not token:
        return None
    url = f"{config.GOOGLE_TOKENINFO_URL}?access_token={urllib.parse.quote(token, safe='')}"
    try:
        with urllib.request.urlopen(url, timeout=config.LOVENOTE_HTTP_TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as e:  # degrade quiet
        log.warning("token verification failed (%s)", type(e).__name__)
        return None


_verify_cache: dict = {}   # sha256(token) → (email, monotonic_expiry); in-memory only


def _verify_token(token: str) -> Optional[str]:
    """Verify a Google access_token → the verified email (lowercased), or None.
    Requires a verified email and — when LOVENOTE_ALLOWED_AUD is set — that the
    token's audience is the dashboard's own OAuth client (rejects a token minted
    for another app: the confused-deputy gap). Caches the result by token HASH
    (never the raw token) for a short TTL so a burst doesn't hammer Google."""
    if not token:
        return None
    key = hashlib.sha256(token.encode("utf-8")).hexdigest()
    mono = _time.monotonic()
    hit = _verify_cache.get(key)
    if hit and hit[1] > mono:
        return hit[0]
    data = _token_introspect(token)
    if not data:
        return None
    email = (data.get("email") or "").strip().lower()
    verified = str(data.get("email_verified", data.get("verified_email", ""))).lower()
    if not email or verified not in ("true", "1"):
        return None
    aud_allow = config.LOVENOTE_ALLOWED_AUD
    if aud_allow and data.get("aud") != aud_allow and data.get("azp") != aud_allow:
        log.warning("token audience rejected (not the dashboard's OAuth client)")
        return None
    if len(_verify_cache) > 64:            # bound the cache: drop expired, else one
        for k in ([k for k, v in _verify_cache.items() if v[1] <= mono]
                  or list(_verify_cache)[:1]):
            _verify_cache.pop(k, None)
    _verify_cache[key] = (email, mono + config.LOVENOTE_VERIFY_CACHE_TTL_S)
    return email


_settings_cache: dict = {"value": None, "at": None}


def _live_settings():
    """Settings.UserMap, re-read at most every LOVENOTE_SETTINGS_TTL_S so a burst
    of requests doesn't hammer the Sheets API. The ONLY Sheet read this server
    does — and it is a READ (never a write)."""
    c = _settings_cache
    mono = _time.monotonic()
    if c["value"] is None or c["at"] is None or (mono - c["at"]) > config.LOVENOTE_SETTINGS_TTL_S:
        config.load_env()
        c["value"] = sheet.read_settings()
        c["at"] = mono
    return c["value"]


# ---------------------------------------------------------------------------
# The thin HTTP shell over handle().
# ---------------------------------------------------------------------------
class LoveNoteHandler(BaseHTTPRequestHandler):
    server_version = "FamilyIncLoveNote/1.0"
    protocol_version = "HTTP/1.1"

    def _dispatch(self):
        cors = _cors_headers(self.headers.get("Origin", ""), config.LOVENOTE_ALLOWED_ORIGIN)
        # Reject — BEFORE reading the body or authenticating — a framing we don't
        # implement (chunked) and an oversized body (pre-auth DoS guard).
        if (self.headers.get("Transfer-Encoding") or "").strip():
            return self._write(411, cors, {"error": "length required (chunked unsupported)"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            length = 0
        if length > config.LOVENOTE_MAX_BODY_BYTES:
            return self._write(413, cors, {"error": "payload too large"})
        body = self.rfile.read(length) if length > 0 else b""
        status, headers, obj = handle(
            self.command, self.path.split("?", 1)[0], self.headers, body,
            now=datetime.now(),
            get_settings=_live_settings,
            verify_token=_verify_token,
            state_dir=config.LOVENOTE_STATE_DIR,
            allowed_origin=config.LOVENOTE_ALLOWED_ORIGIN,
            ttl_hours=config.LOVENOTE_TTL_HOURS,
            max_chars=config.LOVENOTE_MAX_CHARS,
        )
        self._write(status, headers, obj)

    def _write(self, status, headers, obj):
        payload = b"" if obj is None else json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        if obj is not None:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if payload:
            self.wfile.write(payload)

    do_GET = do_PUT = do_DELETE = do_OPTIONS = _dispatch

    def log_message(self, fmt, *args):   # NEVER log headers (would leak the token)
        log.info("%s %s -> handled", self.command, self.path.split("?", 1)[0])


def run(port: Optional[int] = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config.load_env()
    port = port or config.LOVENOTE_PORT
    if not config.LOVENOTE_ALLOWED_ORIGIN:
        log.warning("FAMILY_INC_LOVENOTE_ORIGIN unset — CORS denies all browsers; "
                    "the dashboard love-note feature stays inert until it is set")
    config.LOVENOTE_STATE_DIR.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), LoveNoteHandler)
    log.info("love-note server on 127.0.0.1:%d (state=%s, ttl=%dh)",
             port, config.LOVENOTE_STATE_DIR, config.LOVENOTE_TTL_HOURS)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run()
