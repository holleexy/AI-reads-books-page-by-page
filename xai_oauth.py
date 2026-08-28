"""Load and refresh xAI Grok OAuth tokens stored by Hermes."""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

XAI_OAUTH_CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
DEFAULT_TOKEN_ENDPOINT = "https://auth.x.ai/oauth2/token"
REFRESH_SKEW_SECONDS = 120


class XaiOAuthError(RuntimeError):
    pass


def oauth_disabled() -> bool:
    value = os.environ.get("XAI_DISABLE_OAUTH", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def candidate_auth_files() -> list[Path]:
    explicit = os.environ.get("XAI_OAUTH_AUTH_JSON", "").strip()
    if explicit:
        return [Path(explicit)]

    files: list[Path] = []
    hermes_home = os.environ.get("HERMES_HOME", "").strip()
    if hermes_home:
        files.append(Path(hermes_home) / "auth.json")
    files.extend(
        [
            Path.home() / ".hermes" / "auth.json",
            Path("/opt/hermes-cli/.hermes/auth.json"),
            Path("/opt/hermes-cli-prod/.hermes/auth.json"),
            Path("/var/lib/happy/.hermes/auth.json"),
        ]
    )
    seen: set[str] = set()
    unique: list[Path] = []
    for path in files:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def unwrap_tokens(state: dict | None) -> tuple[dict, dict]:
    if not isinstance(state, dict):
        return {}, {}
    tokens = state.get("tokens")
    discovery = state.get("discovery") if isinstance(state.get("discovery"), dict) else {}
    if not isinstance(tokens, dict):
        return {}, {}
    nested = tokens.get("tokens")
    if isinstance(nested, dict) and str(nested.get("access_token") or "").strip():
        nested_discovery = tokens.get("discovery") if isinstance(tokens.get("discovery"), dict) else discovery
        return nested, nested_discovery
    if str(tokens.get("access_token") or "").strip():
        flat_discovery = tokens.get("discovery") if isinstance(tokens.get("discovery"), dict) else discovery
        return tokens, flat_discovery
    return {}, {}


def access_token_needs_refresh(access_token: str, *, skew_seconds: int = REFRESH_SKEW_SECONDS) -> bool:
    if not isinstance(access_token, str) or "." not in access_token:
        return False
    try:
        parts = access_token.split(".")
        if len(parts) < 2:
            return False
        payload_b64 = parts[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("ascii")).decode("utf-8"))
        exp = payload.get("exp")
        if not isinstance(exp, (int, float)):
            return False
        return float(exp) <= time.time() + max(0, int(skew_seconds))
    except Exception:
        return False


def validate_token_endpoint(url: str) -> str:
    endpoint = (url or "").strip() or DEFAULT_TOKEN_ENDPOINT
    parsed = urlparse(endpoint)
    if parsed.scheme != "https":
        raise XaiOAuthError(f"xAI token_endpoint must be https: {endpoint!r}")
    host = (parsed.hostname or "").lower()
    if host != "x.ai" and not host.endswith(".x.ai"):
        raise XaiOAuthError(f"xAI token_endpoint host {host!r} is not on x.ai")
    return endpoint


def refresh_tokens(refresh_token: str, *, token_endpoint: str = "") -> dict:
    if not isinstance(refresh_token, str) or not refresh_token.strip():
        raise XaiOAuthError("xAI OAuth is missing refresh_token")
    endpoint = validate_token_endpoint(token_endpoint)
    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "client_id": XAI_OAUTH_CLIENT_ID,
            "refresh_token": refresh_token,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise XaiOAuthError(f"xAI token refresh failed: HTTP {exc.code} {detail}".strip()) from exc
    except Exception as exc:
        raise XaiOAuthError(f"xAI token refresh failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise XaiOAuthError("xAI token refresh response was not a JSON object")
    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise XaiOAuthError("xAI token refresh did not return access_token")
    return {
        "access_token": access_token,
        "refresh_token": str(payload.get("refresh_token") or "").strip(),
        "expires_in": payload.get("expires_in"),
    }


def _pool_entry_usable(entry: dict) -> bool:
    access = str(entry.get("access_token") or "").strip()
    refresh = str(entry.get("refresh_token") or "").strip()
    if not access or not refresh:
        return False
    reset_at = entry.get("last_error_reset_at")
    if isinstance(reset_at, (int, float)) and reset_at > time.time():
        return False
    return True


def iter_credentials(store: dict) -> list[dict]:
    found: list[dict] = []
    providers = store.get("providers")
    state = providers.get("xai-oauth") if isinstance(providers, dict) else None
    tokens, discovery = unwrap_tokens(state if isinstance(state, dict) else None)
    access = str(tokens.get("access_token") or "").strip()
    refresh = str(tokens.get("refresh_token") or "").strip()
    if access and refresh:
        found.append(
            {
                "access": access,
                "refresh": refresh,
                "discovery": discovery,
                "kind": "provider",
                "pool_index": None,
            }
        )
    pool = store.get("credential_pool")
    entries = pool.get("xai-oauth") if isinstance(pool, dict) else None
    if isinstance(entries, list):
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict) or not _pool_entry_usable(entry):
                continue
            found.append(
                {
                    "access": str(entry.get("access_token") or "").strip(),
                    "refresh": str(entry.get("refresh_token") or "").strip(),
                    "discovery": {},
                    "kind": "pool",
                    "pool_index": index,
                }
            )
    return found


def _write_store(path: Path, store: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(path))


def persist_tokens(
    path: Path,
    store: dict,
    payload: dict,
    *,
    kind: str = "provider",
    pool_index: int | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    if kind == "pool" and pool_index is not None:
        pool = store.setdefault("credential_pool", {})
        if not isinstance(pool, dict):
            store["credential_pool"] = {}
            pool = store["credential_pool"]
        entries = pool.setdefault("xai-oauth", [])
        if isinstance(entries, list) and 0 <= pool_index < len(entries) and isinstance(entries[pool_index], dict):
            entry = entries[pool_index]
            entry["access_token"] = payload["access_token"]
            if payload.get("refresh_token"):
                entry["refresh_token"] = payload["refresh_token"]
            entry["last_refresh"] = now
            entry["last_status"] = "ok"
        _write_store(path, store)
        return

    providers = store.setdefault("providers", {})
    if not isinstance(providers, dict):
        store["providers"] = {}
        providers = store["providers"]
    state = providers.setdefault("xai-oauth", {})
    if not isinstance(state, dict):
        state = {}
        providers["xai-oauth"] = state
    wrapper = state.get("tokens")
    if isinstance(wrapper, dict) and isinstance(wrapper.get("tokens"), dict):
        inner = wrapper["tokens"]
        inner["access_token"] = payload["access_token"]
        if payload.get("refresh_token"):
            inner["refresh_token"] = payload["refresh_token"]
        if payload.get("expires_in") is not None:
            inner["expires_in"] = payload["expires_in"]
        wrapper["last_refresh"] = now
    else:
        tokens = wrapper if isinstance(wrapper, dict) else {}
        tokens["access_token"] = payload["access_token"]
        if payload.get("refresh_token"):
            tokens["refresh_token"] = payload["refresh_token"]
        if payload.get("expires_in") is not None:
            tokens["expires_in"] = payload["expires_in"]
        state["tokens"] = tokens
    state["last_refresh"] = now
    _write_store(path, store)


def resolve_access_token() -> str | None:
    if oauth_disabled():
        return None
    for path in candidate_auth_files():
        if not path.is_file():
            continue
        try:
            store = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(store, dict):
            continue
        creds = iter_credentials(store)
        if not creds:
            continue
        for cred in creds:
            if not access_token_needs_refresh(cred["access"]):
                return cred["access"]
        for cred in creds:
            try:
                payload = refresh_tokens(
                    cred["refresh"],
                    token_endpoint=str(cred["discovery"].get("token_endpoint") or ""),
                )
            except XaiOAuthError:
                continue
            persist_tokens(
                path,
                store,
                payload,
                kind=cred["kind"],
                pool_index=cred["pool_index"],
            )
            return payload["access_token"]
        return creds[0]["access"]
    return None
