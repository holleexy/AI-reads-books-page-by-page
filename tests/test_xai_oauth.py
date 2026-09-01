import base64
import json
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import xai_oauth


def _b64url(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def fake_jwt(*, exp: int) -> str:
    return f"{_b64url({'alg': 'none'})}.{_b64url({'exp': exp})}.sig"


def nested_store(*, access: str, refresh: str = "refresh-test", endpoint: str = "https://auth.x.ai/oauth2/token") -> dict:
    return {
        "providers": {
            "xai-oauth": {
                "auth_mode": "oauth",
                "tokens": {
                    "discovery": {"token_endpoint": endpoint},
                    "tokens": {
                        "access_token": access,
                        "refresh_token": refresh,
                        "expires_in": 21600,
                        "token_type": "Bearer",
                    },
                },
            }
        }
    }


def flat_store(*, access: str, refresh: str = "refresh-test") -> dict:
    return {
        "providers": {
            "xai-oauth": {
                "tokens": {
                    "access_token": access,
                    "refresh_token": refresh,
                    "discovery": {"token_endpoint": "https://auth.x.ai/oauth2/token"},
                }
            }
        }
    }


class UnwrapTokensTests(unittest.TestCase):
    def test_unwraps_nested_hermes_shape(self):
        tokens, discovery = xai_oauth.unwrap_tokens(nested_store(access="abc")["providers"]["xai-oauth"])
        self.assertEqual(tokens["access_token"], "abc")
        self.assertEqual(tokens["refresh_token"], "refresh-test")
        self.assertEqual(discovery["token_endpoint"], "https://auth.x.ai/oauth2/token")

    def test_unwraps_flat_shape(self):
        tokens, discovery = xai_oauth.unwrap_tokens(flat_store(access="flat-token")["providers"]["xai-oauth"])
        self.assertEqual(tokens["access_token"], "flat-token")


class JwtExpiryTests(unittest.TestCase):
    def test_expired_jwt_needs_refresh(self):
        token = fake_jwt(exp=int(time.time()) - 60)
        self.assertTrue(xai_oauth.access_token_needs_refresh(token))

    def test_fresh_jwt_does_not_need_refresh(self):
        token = fake_jwt(exp=int(time.time()) + 7200)
        self.assertFalse(xai_oauth.access_token_needs_refresh(token))

    def test_opaque_non_jwt_needs_refresh(self):
        self.assertTrue(xai_oauth.access_token_needs_refresh("opaque-provider-access"))

    def test_token_expiring_in_30_minutes_needs_refresh(self):
        token = fake_jwt(exp=int(time.time()) + 1800)
        self.assertTrue(xai_oauth.access_token_needs_refresh(token))

    def test_unparseable_jwt_needs_refresh(self):
        self.assertTrue(xai_oauth.access_token_needs_refresh("abc.!!!not-json!!!.sig"))

    def test_jwt_missing_exp_needs_refresh(self):
        token = f"{_b64url({'alg': 'none'})}.{_b64url({'sub': 'no-exp'})}.sig"
        self.assertTrue(xai_oauth.access_token_needs_refresh(token))


class ResolveAccessTokenTests(unittest.TestCase):
    def test_reads_valid_token_from_auth_json(self):
        token = fake_jwt(exp=int(time.time()) + 7200)
        with self._auth_file(nested_store(access=token)) as path:
            with patch.dict(os.environ, {"XAI_OAUTH_AUTH_JSON": str(path), "XAI_DISABLE_OAUTH": ""}, clear=False):
                os.environ.pop("XAI_DISABLE_OAUTH", None)
                resolved = xai_oauth.resolve_access_token()
        self.assertEqual(resolved, token)

    def test_prefers_fresh_pool_token_over_expired_provider(self):
        stale = fake_jwt(exp=int(time.time()) - 10)
        fresh = fake_jwt(exp=int(time.time()) + 7200)
        store = nested_store(access=stale, refresh="stale-refresh")
        store["credential_pool"] = {
            "xai-oauth": [
                {
                    "access_token": fresh,
                    "refresh_token": "pool-refresh",
                    "last_status": "ok",
                }
            ]
        }
        with self._auth_file(store) as path:
            with patch.object(xai_oauth, "refresh_tokens") as refresh:
                with patch.dict(os.environ, {"XAI_OAUTH_AUTH_JSON": str(path)}, clear=False):
                    os.environ.pop("XAI_DISABLE_OAUTH", None)
                    resolved = xai_oauth.resolve_access_token()
        self.assertEqual(resolved, fresh)
        refresh.assert_not_called()

    def test_refreshes_expired_token_and_persists(self):
        old = fake_jwt(exp=int(time.time()) - 10)
        new = fake_jwt(exp=int(time.time()) + 3600)
        with self._auth_file(nested_store(access=old, refresh="old-refresh")) as path:
            with patch.object(xai_oauth, "refresh_tokens", return_value={
                "access_token": new,
                "refresh_token": "new-refresh",
                "expires_in": 21600,
            }) as refresh:
                with patch.dict(os.environ, {"XAI_OAUTH_AUTH_JSON": str(path)}, clear=False):
                    os.environ.pop("XAI_DISABLE_OAUTH", None)
                    resolved = xai_oauth.resolve_access_token()
            self.assertEqual(resolved, new)
            refresh.assert_called_once()
            saved = json.loads(path.read_text(encoding="utf-8"))
            inner = saved["providers"]["xai-oauth"]["tokens"]["tokens"]
            self.assertEqual(inner["access_token"], new)
            self.assertEqual(inner["refresh_token"], "new-refresh")

    def test_refuses_non_xai_token_endpoint(self):
        with self.assertRaisesRegex(xai_oauth.XaiOAuthError, "token_endpoint"):
            xai_oauth.validate_token_endpoint("https://evil.example/oauth2/token")

    def test_returns_none_when_refresh_fails(self):
        old = fake_jwt(exp=int(time.time()) - 10)
        with self._auth_file(nested_store(access=old, refresh="dead-refresh")) as path:
            with patch.object(xai_oauth, "refresh_tokens", side_effect=xai_oauth.XaiOAuthError("invalid_grant")):
                with patch.dict(os.environ, {"XAI_OAUTH_AUTH_JSON": str(path)}, clear=False):
                    os.environ.pop("XAI_DISABLE_OAUTH", None)
                    resolved = xai_oauth.resolve_access_token()
        self.assertIsNone(resolved)

    def test_skips_failed_file_and_tries_next_candidate(self):
        dead = fake_jwt(exp=int(time.time()) - 10)
        stale_next = fake_jwt(exp=int(time.time()) - 5)
        live = fake_jwt(exp=int(time.time()) + 7200)
        with self._auth_file(nested_store(access=dead, refresh="dead-refresh")) as dead_path:
            with self._auth_file(nested_store(access=stale_next, refresh="live-refresh")) as live_path:
                with patch.object(xai_oauth, "candidate_auth_files", return_value=[dead_path, live_path]):
                    with patch.object(
                        xai_oauth,
                        "refresh_tokens",
                        side_effect=[
                            xai_oauth.XaiOAuthError("invalid_grant"),
                            {
                                "access_token": live,
                                "refresh_token": "next-refresh",
                                "expires_in": 21600,
                            },
                        ],
                    ) as refresh:
                        with patch.dict(os.environ, {}, clear=False):
                            os.environ.pop("XAI_DISABLE_OAUTH", None)
                            os.environ.pop("XAI_OAUTH_AUTH_JSON", None)
                            resolved = xai_oauth.resolve_access_token()
        self.assertEqual(resolved, live)
        self.assertEqual(refresh.call_count, 2)

    def test_disable_env_skips_oauth(self):
        token = fake_jwt(exp=int(time.time()) + 3600)
        with self._auth_file(nested_store(access=token)) as path:
            env = {"XAI_OAUTH_AUTH_JSON": str(path), "XAI_DISABLE_OAUTH": "1"}
            with patch.dict(os.environ, env, clear=False):
                self.assertIsNone(xai_oauth.resolve_access_token())

    def _auth_file(self, store: dict):
        from tempfile import TemporaryDirectory

        class _Ctx:
            def __enter__(self_inner):
                self_inner._tmp = TemporaryDirectory()
                path = Path(self_inner._tmp.name) / "auth.json"
                path.write_text(json.dumps(store), encoding="utf-8")
                return path

            def __exit__(self_inner, *args):
                self_inner._tmp.cleanup()

        return _Ctx()


class CreateClientOAuthTests(unittest.TestCase):
    def test_prefers_oauth_over_cursor(self):
        import read_books

        token = fake_jwt(exp=int(time.time()) + 3600)
        env = {"CURSOR_API_KEY": "crsr-test-key"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("XAI_API_KEY", None)
            os.environ.pop("XAI_DISABLE_OAUTH", None)
            with patch.object(read_books.xai_oauth, "resolve_access_token", return_value=token):
                client = read_books.create_client()
        self.assertEqual(client.provider, "xai")
        self.assertEqual(client.auth_mode, "oauth")
        self.assertIn("api.x.ai", client.base_url)

    def test_api_key_still_wins(self):
        import read_books

        env = {"XAI_API_KEY": "xai-test-key", "CURSOR_API_KEY": "crsr-test-key"}
        with patch.dict(os.environ, env, clear=False):
            with patch.object(read_books.xai_oauth, "resolve_access_token", return_value="should-not-use"):
                client = read_books.create_client()
        self.assertEqual(client.provider, "xai")
        self.assertEqual(client.auth_mode, "api_key")


if __name__ == "__main__":
    unittest.main()
