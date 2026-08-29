import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import read_books
import xai_oauth


class PagesToProcessTests(unittest.TestCase):
    def test_retries_failed_pages_after_finished_scan(self):
        pages, retrying = read_books.pages_to_process(
            start_page=509,
            end_page=509,
            progress_last=509,
            failed_pages=[40, 508, 41],
            summary_generated=False,
        )
        self.assertTrue(retrying)
        self.assertEqual(pages, [40, 41, 508])

    def test_skips_retry_when_summary_exists(self):
        pages, retrying = read_books.pages_to_process(
            start_page=509,
            end_page=509,
            progress_last=509,
            failed_pages=[40],
            summary_generated=True,
        )
        self.assertFalse(retrying)
        self.assertEqual(pages, [])

    def test_continues_from_last_page_during_normal_resume(self):
        pages, retrying = read_books.pages_to_process(
            start_page=50,
            end_page=509,
            progress_last=50,
            failed_pages=[],
            summary_generated=False,
        )
        self.assertFalse(retrying)
        self.assertEqual(pages[0], 50)
        self.assertEqual(pages[-1], 508)


class AuthErrorTests(unittest.TestCase):
    def test_detects_bad_oauth_credentials(self):
        exc = Exception("Error code: 403 - unauthenticated:bad-credentials")
        self.assertTrue(read_books._is_auth_error(exc))

    def test_ignores_rate_limit(self):
        exc = Exception("rate_limit_exceeded cooling down")
        self.assertFalse(read_books._is_auth_error(exc))


class CallApiOauthRefreshTests(unittest.TestCase):
    def test_refreshes_oauth_client_on_auth_error(self):
        client = read_books.LlmClient(
            provider="xai",
            base_url="https://api.x.ai/v1",
            openai=MagicMock(),
            auth_mode="oauth",
        )
        err = openai_api_error("403 unauthenticated:bad-credentials")
        ok = MagicMock()
        ok.choices = [MagicMock(message=MagicMock(content='{"has_content": false, "knowledge": []}'))]
        client.openai.chat.completions.create.side_effect = [err, ok]

        with patch.object(read_books.xai_oauth, "resolve_access_token", return_value="new-token") as refresh:
            with patch.object(read_books, "OpenAI", return_value=client.openai) as factory:
                text = read_books.call_api(
                    client,
                    model="grok-4.6",
                    messages=[{"role": "user", "content": "hi"}],
                )
        self.assertIn("has_content", text)
        refresh.assert_called_with(force_refresh=True)
        factory.assert_called()


def openai_api_error(message: str):
    import openai

    return openai.APIError(message, request=None, body=None)


class ForceRefreshTests(unittest.TestCase):
    def test_force_refresh_skips_unexpired_token(self):
        import base64
        import json
        import os
        import time
        from tempfile import TemporaryDirectory

        def b64url(payload: dict) -> str:
            raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

        def fake_jwt(*, exp: int) -> str:
            return f"{b64url({'alg': 'none'})}.{b64url({'exp': exp})}.sig"

        old = fake_jwt(exp=int(time.time()) + 3600)
        new = fake_jwt(exp=int(time.time()) + 7200)
        store = {
            "providers": {
                "xai-oauth": {
                    "tokens": {
                        "discovery": {"token_endpoint": "https://auth.x.ai/oauth2/token"},
                        "tokens": {
                            "access_token": old,
                            "refresh_token": "r1",
                            "expires_in": 21600,
                        },
                    }
                }
            }
        }
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "auth.json"
            path.write_text(json.dumps(store), encoding="utf-8")
            with patch.object(
                xai_oauth,
                "refresh_tokens",
                return_value={"access_token": new, "refresh_token": "r2", "expires_in": 21600},
            ) as refresh:
                with patch.dict(os.environ, {"XAI_OAUTH_AUTH_JSON": str(path)}, clear=False):
                    os.environ.pop("XAI_DISABLE_OAUTH", None)
                    resolved = xai_oauth.resolve_access_token(force_refresh=True)
            self.assertEqual(resolved, new)
            refresh.assert_called_once()


if __name__ == "__main__":
    unittest.main()
