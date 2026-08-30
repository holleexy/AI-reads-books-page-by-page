import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import semantica  # noqa: F401
except ImportError as exc:
    SEMANTICA_IMPORT_ERROR = exc
    semantica = None
else:
    SEMANTICA_IMPORT_ERROR = None


@unittest.skipUnless(
    semantica is not None,
    f"semantica is not importable in this interpreter: {SEMANTICA_IMPORT_ERROR}",
)
class XAIProviderRegistrationTests(unittest.TestCase):
    def test_register_xai_uses_xai_base_url_and_grok(self):
        from semantica.semantic_extract.providers import create_provider
        from semantica.semantic_extract.registry import provider_registry

        from book_semantica.xai_provider import (
            XAI_BASE_URL,
            XAI_DEFAULT_MODEL,
            register_xai_provider,
        )

        register_xai_provider()
        cls = provider_registry.get("xai")
        self.assertIsNotNone(cls)
        provider = create_provider(
            "xai",
            api_key="test-not-a-real-key",
            use_pool=False,
        )
        self.assertEqual(provider.base_url, "https://api.x.ai/v1")
        self.assertEqual(provider.base_url, XAI_BASE_URL)
        self.assertEqual(provider.model, "grok-4.6")
        self.assertEqual(provider.model, XAI_DEFAULT_MODEL)
        self.assertEqual(provider.api_key, "test-not-a-real-key")

    def test_register_is_idempotent(self):
        from semantica.semantic_extract.registry import provider_registry

        from book_semantica.xai_provider import register_xai_provider

        register_xai_provider()
        register_xai_provider()
        self.assertEqual(provider_registry.get("xai").__name__, "XAIProvider")

    def test_missing_xai_key_does_not_fall_back_to_openai(self):
        import os

        from book_semantica.xai_provider import XAIProvider

        old = os.environ.pop("XAI_API_KEY", None)
        try:
            with self.assertRaises(ValueError):
                XAIProvider(api_key=None)
        finally:
            if old is not None:
                os.environ["XAI_API_KEY"] = old


if __name__ == "__main__":
    unittest.main()
