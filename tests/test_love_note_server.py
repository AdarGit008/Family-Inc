"""Love-note endpoint (V3.7, SPEC §7.7) — the load-bearing negatives + behavior.

The server is the first dashboard datum that is neither the Sheet nor the outbox,
so its GUARANTEES are tested as explicitly as its happy path:
  • no-outbox-import   — it is not an alert path (§3 chokepoint stays the only one)
  • no-Sheet-write     — it only READS Settings.UserMap; the request path writes nothing
  • token-never-stored — the forwarded Google token lands in no file
  • CORS allowlist     — only the Pages origin gets Access-Control-Allow-Origin
  • unknown-email 403  — a non-parent signer is refused
  • dual expiry        — lazy (on read) + the hourly sweep
  • one per direction  — a re-send overwrites; clear removes
"""
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from automation.lib.sheet import Settings
from automation import love_note_server as lns

NOW = datetime(2026, 6, 25, 9, 0, 0)
ORIGIN = "https://example.github.io"
SETTINGS = Settings(usermap={"adar@x.com": "Adar", "shanee@x.com": "Shanee"})
TOKENS = {"tok-adar": "adar@x.com", "tok-shanee": "shanee@x.com"}


def call(method, *, state_dir, token="tok-adar", body=b"", now=NOW, origin=ORIGIN,
         settings=SETTINGS, allowed=ORIGIN, path=lns.PATH, verify=None):
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if origin is not None:
        headers["Origin"] = origin
    return lns.handle(
        method, path, headers, body, now=now,
        get_settings=lambda: settings,
        verify_token=verify or (lambda t: TOKENS.get(t)),
        state_dir=state_dir, allowed_origin=allowed,
        ttl_hours=24, max_chars=500)


# ---------------------------------------------------------------------------
# Happy path — send → the partner sees it on their next open; the author sees
# their own waiting note; neither sees their own as "inbound".
# ---------------------------------------------------------------------------
def test_send_then_partner_gets_inbound(tmp_path):
    status, _, _ = call("PUT", state_dir=tmp_path, token="tok-adar",
                        body=b'{"text":"love you \xe2\x9d\xa4"}'.decode("utf-8").encode())
    assert status == 200

    s_status, _, s_body = call("GET", state_dir=tmp_path, token="tok-shanee")
    assert s_status == 200
    assert s_body["inbound"]["from"] == "Adar"
    assert "love you" in s_body["inbound"]["text"]
    assert "expires_at" not in s_body["inbound"]      # no delivery/seen signal back
    assert s_body["outbound"] is None

    a_status, _, a_body = call("GET", state_dir=tmp_path, token="tok-adar")
    assert a_status == 200
    assert a_body["inbound"] is None                  # the author never sees their own as inbound
    assert a_body["outbound"]["to"] == "Shanee"
    assert a_body["outbound"]["expires_at"]


def test_one_note_per_direction_overwrites(tmp_path):
    call("PUT", state_dir=tmp_path, token="tok-adar", body=b'{"text":"first"}')
    call("PUT", state_dir=tmp_path, token="tok-adar", body=b'{"text":"second"}')
    _, _, body = call("GET", state_dir=tmp_path, token="tok-shanee")
    assert body["inbound"]["text"] == "second"
    # exactly one file for adar→shanee, none stale
    files = list(tmp_path.glob("*__to__*.json"))
    assert len(files) == 1


def test_both_directions_are_independent(tmp_path):
    call("PUT", state_dir=tmp_path, token="tok-adar", body=b'{"text":"A to S"}')
    call("PUT", state_dir=tmp_path, token="tok-shanee", body=b'{"text":"S to A"}')
    _, _, a = call("GET", state_dir=tmp_path, token="tok-adar")
    _, _, s = call("GET", state_dir=tmp_path, token="tok-shanee")
    assert a["inbound"]["from"] == "Shanee" and a["inbound"]["text"] == "S to A"
    assert s["inbound"]["from"] == "Adar" and s["inbound"]["text"] == "A to S"


def test_delete_clears_only_own_outbound(tmp_path):
    call("PUT", state_dir=tmp_path, token="tok-adar", body=b'{"text":"oops"}')
    status, _, _ = call("DELETE", state_dir=tmp_path, token="tok-adar")
    assert status == 200
    _, _, s = call("GET", state_dir=tmp_path, token="tok-shanee")
    assert s["inbound"] is None
    assert not list(tmp_path.glob("*__to__*.json"))


# ---------------------------------------------------------------------------
# Auth — token presence/validity, and email→parent resolution.
# ---------------------------------------------------------------------------
def test_missing_token_401(tmp_path):
    status, _, _ = call("GET", state_dir=tmp_path, token=None)
    assert status == 401


def test_invalid_token_401(tmp_path):
    status, _, _ = call("GET", state_dir=tmp_path, token="garbage")
    assert status == 401


def test_unknown_email_403(tmp_path):
    status, _, body = call("GET", state_dir=tmp_path, token="tok-stranger",
                           verify=lambda t: "stranger@x.com")
    assert status == 403
    assert "unknown" in body["error"]


def test_usermap_not_two_adults_403(tmp_path):
    solo = Settings(usermap={"adar@x.com": "Adar"})
    status, _, _ = call("GET", state_dir=tmp_path, token="tok-adar", settings=solo)
    assert status == 403


# ---------------------------------------------------------------------------
# Validation.
# ---------------------------------------------------------------------------
def test_empty_note_400(tmp_path):
    status, _, _ = call("PUT", state_dir=tmp_path, body=b'{"text":"   "}')
    assert status == 400


def test_too_long_note_400(tmp_path):
    status, _, _ = call("PUT", state_dir=tmp_path,
                        body=b'{"text":"' + b"x" * 600 + b'"}')
    assert status == 400


def test_bad_json_400(tmp_path):
    status, _, _ = call("PUT", state_dir=tmp_path, body=b"not json")
    assert status == 400


# ---------------------------------------------------------------------------
# Expiry — lazy (on read) and the hourly sweep.
# ---------------------------------------------------------------------------
def test_lazy_expiry_on_read(tmp_path):
    call("PUT", state_dir=tmp_path, token="tok-adar", body=b'{"text":"fades"}')
    later = NOW + timedelta(hours=25)
    _, _, s = call("GET", state_dir=tmp_path, token="tok-shanee", now=later)
    assert s["inbound"] is None
    assert not list(tmp_path.glob("*__to__*.json"))   # unlinked on the expired read


def test_sweep_removes_only_expired(tmp_path):
    fresh = lns.note_path(tmp_path, "adar@x.com", "shanee@x.com")
    stale = lns.note_path(tmp_path, "shanee@x.com", "adar@x.com")
    lns.write_note(fresh, {"text": "keep", "expires_at": (NOW + timedelta(hours=1)).isoformat()})
    lns.write_note(stale, {"text": "drop", "expires_at": (NOW - timedelta(hours=1)).isoformat()})
    removed = lns.sweep(tmp_path, NOW)
    assert removed == 1
    assert fresh.exists() and not stale.exists()


# ---------------------------------------------------------------------------
# CORS — exactly one allowed origin; a foreign origin gets no ACAO.
# ---------------------------------------------------------------------------
def test_cors_allows_only_the_pages_origin(tmp_path):
    _, headers, _ = call("GET", state_dir=tmp_path, token="tok-adar", origin=ORIGIN)
    assert headers.get("Access-Control-Allow-Origin") == ORIGIN


def test_cors_denies_foreign_origin(tmp_path):
    _, headers, _ = call("GET", state_dir=tmp_path, token="tok-adar",
                         origin="https://evil.example.com")
    assert "Access-Control-Allow-Origin" not in headers


def test_cors_blank_allowed_origin_denies_all(tmp_path):
    # FAMILY_INC_LOVENOTE_ORIGIN unset → the feature self-disables fail-safe.
    _, headers, _ = call("GET", state_dir=tmp_path, token="tok-adar", allowed="")
    assert "Access-Control-Allow-Origin" not in headers


def test_options_preflight_is_204_with_cors(tmp_path):
    status, headers, body = call("OPTIONS", state_dir=tmp_path, token=None)
    assert status == 204 and body is None
    assert headers["Access-Control-Allow-Origin"] == ORIGIN
    assert "GET" in headers["Access-Control-Allow-Methods"]


def test_healthz_needs_no_auth(tmp_path):
    status, _, body = call("GET", state_dir=tmp_path, token=None, path="/healthz")
    assert status == 200 and body["status"] == "ok"


# ---------------------------------------------------------------------------
# Load-bearing negatives — the guarantees that make this safe to expose.
# ---------------------------------------------------------------------------
def test_token_is_never_persisted(tmp_path):
    secret = "ya29.SUPER-SECRET-ACCESS-TOKEN"
    status, _, _ = call("PUT", state_dir=tmp_path, token=secret,
                        verify=lambda t: "adar@x.com" if t == secret else None,
                        body=b'{"text":"hi"}')
    assert status == 200
    for p in tmp_path.rglob("*"):
        if p.is_file():
            assert secret not in p.read_text(encoding="utf-8"), f"token leaked into {p.name}"


def test_request_path_never_writes_the_sheet(tmp_path, monkeypatch):
    # Patch every Sheet writer to blow up; a full round-trip must touch none.
    from automation.lib import sheet
    for writer in ("update_reminders", "append_rows", "upsert_rows",
                   "write_cells", "roll_off_old_rows"):
        monkeypatch.setattr(sheet, writer,
                            lambda *a, **k: pytest.fail("love-note wrote the Sheet"))
    call("PUT", state_dir=tmp_path, token="tok-adar", body=b'{"text":"safe"}')
    call("GET", state_dir=tmp_path, token="tok-shanee")
    call("DELETE", state_dir=tmp_path, token="tok-adar")


def test_module_never_imports_the_outbox():
    # Parse the real import statements (not prose — the docstring names the outbox
    # to say it is deliberately avoided). Love-note is not an alert path: the
    # outbox stays the one chokepoint to a human (§3).
    import ast
    tree = ast.parse(Path(lns.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(n.name for n in node.names)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            imported.update(f"{mod}.{n.name}" for n in node.names)
    assert not any("outbox" in m for m in imported), \
        f"love-note must not import the outbox — found {imported}"


def test_slug_is_filesystem_safe():
    assert lns.slug("Adar.008@Gmail.com") == "adar_008_gmail_com"
    assert lns.slug("") == "_"


# ---------------------------------------------------------------------------
# Robustness — valid-but-non-object JSON must 400 / be swept, not crash (review).
# ---------------------------------------------------------------------------
def test_non_object_json_put_is_400_not_a_crash(tmp_path):
    for body in (b"null", b'"hi"', b"[1,2]", b"42", b"true"):
        status, _, _ = call("PUT", state_dir=tmp_path, body=body)
        assert status == 400, f"body {body!r} should 400, not crash"


def test_garbled_non_dict_note_file_is_unlinked(tmp_path):
    p = lns.note_path(tmp_path, "shanee@x.com", "adar@x.com")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("42", encoding="utf-8")          # valid JSON, not an object
    assert lns.read_note(p, NOW) is None
    assert not p.exists()
    # a GET over the (now-removed) garbled file must not 500
    status, _, body = call("GET", state_dir=tmp_path, token="tok-adar")
    assert status == 200 and body["inbound"] is None


# ---------------------------------------------------------------------------
# Token audience — _verify_token rejects a token minted for another OAuth client
# when LOVENOTE_ALLOWED_AUD is configured (the confused-deputy guard).
# ---------------------------------------------------------------------------
def _introspect(**claims):
    return lambda _t: claims


def test_verify_rejects_wrong_audience(monkeypatch):
    from automation.lib import config
    lns._verify_cache.clear()
    monkeypatch.setattr(config, "LOVENOTE_ALLOWED_AUD", "good-client")
    monkeypatch.setattr(lns, "_token_introspect",
                        _introspect(email="adar@x.com", email_verified="true", aud="evil-client"))
    assert lns._verify_token("tok-wrong-aud") is None


def test_verify_accepts_matching_audience(monkeypatch):
    from automation.lib import config
    lns._verify_cache.clear()
    monkeypatch.setattr(config, "LOVENOTE_ALLOWED_AUD", "good-client")
    monkeypatch.setattr(lns, "_token_introspect",
                        _introspect(email="Adar@x.com", email_verified="true", aud="good-client"))
    assert lns._verify_token("tok-good-aud") == "adar@x.com"


def test_verify_skips_audience_when_unconfigured(monkeypatch):
    from automation.lib import config
    lns._verify_cache.clear()
    monkeypatch.setattr(config, "LOVENOTE_ALLOWED_AUD", "")
    monkeypatch.setattr(lns, "_token_introspect",
                        _introspect(email="shanee@x.com", email_verified="true", aud="anything"))
    assert lns._verify_token("tok-no-aud-cfg") == "shanee@x.com"


def test_verify_requires_verified_email(monkeypatch):
    from automation.lib import config
    lns._verify_cache.clear()
    monkeypatch.setattr(config, "LOVENOTE_ALLOWED_AUD", "")
    monkeypatch.setattr(lns, "_token_introspect",
                        _introspect(email="adar@x.com", email_verified="false"))
    assert lns._verify_token("tok-unverified") is None


def test_verify_caches_by_hash_not_raw_token(monkeypatch):
    from automation.lib import config
    lns._verify_cache.clear()
    monkeypatch.setattr(config, "LOVENOTE_ALLOWED_AUD", "")
    calls = {"n": 0}

    def counting(_t):
        calls["n"] += 1
        return {"email": "adar@x.com", "email_verified": "true"}
    monkeypatch.setattr(lns, "_token_introspect", counting)
    secret = "raw-secret-token-xyz"
    assert lns._verify_token(secret) == "adar@x.com"
    assert lns._verify_token(secret) == "adar@x.com"   # served from cache
    assert calls["n"] == 1                              # Google hit once
    assert secret not in lns._verify_cache             # keyed by sha256, never the raw token

