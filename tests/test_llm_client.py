import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import read_books


class LlmClientTests(unittest.TestCase):
    def test_endpoint_is_xai_not_omniroute(self):
        self.assertEqual(read_books.BASE_URL, "https://api.x.ai/v1")
        self.assertNotIn("20128", read_books.BASE_URL)
        self.assertTrue(read_books.PRIMARY_MODEL.startswith("grok-"))
        self.assertTrue(read_books.FALLBACK_MODEL.startswith("grok-"))

    def test_create_client_prefers_xai_api_key(self):
        env = {"XAI_API_KEY": "xai-test-key", "CURSOR_API_KEY": "crsr-test-key"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("OMNIROUTE_API_KEY", None)
            client = read_books.create_client()
        self.assertEqual(client.provider, "xai")
        self.assertEqual(client.auth_mode, "api_key")
        self.assertIn("api.x.ai", client.base_url)

    def test_create_client_falls_back_to_cursor(self):
        env = {"CURSOR_API_KEY": "crsr-test-key", "XAI_DISABLE_OAUTH": "1"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("XAI_API_KEY", None)
            os.environ.pop("OMNIROUTE_API_KEY", None)
            client = read_books.create_client()
        self.assertEqual(client.provider, "cursor")
        self.assertEqual(client.auth_mode, "cursor")

    def test_create_client_requires_xai_or_cursor_key(self):
        env = {"XAI_DISABLE_OAUTH": "1"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("XAI_API_KEY", None)
            os.environ.pop("CURSOR_API_KEY", None)
            os.environ.pop("OMNIROUTE_API_KEY", None)
            with self.assertRaisesRegex(RuntimeError, "XAI_API_KEY|xAI OAuth|CURSOR_API_KEY"):
                read_books.create_client()


if __name__ == "__main__":
    unittest.main()
