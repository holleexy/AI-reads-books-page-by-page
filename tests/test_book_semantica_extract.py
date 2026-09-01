import os
import sys
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from book_semantica.extract import LLMExtractionError, _extract_concurrency, _extract_items


class ExtractConcurrencyTests(unittest.TestCase):
    def test_default_concurrency_is_two(self):
        self.assertEqual(_extract_concurrency(SimpleNamespace()), 2)

    def test_concurrency_clamps_to_one_through_four(self):
        self.assertEqual(_extract_concurrency(SimpleNamespace(extract_concurrency=0)), 1)
        self.assertEqual(_extract_concurrency(SimpleNamespace(extract_concurrency=9)), 4)

    def test_two_items_overlap_when_concurrency_is_two(self):
        current = 0
        max_seen = 0
        lock = threading.Lock()

        def extract_ents(text, **kwargs):
            nonlocal current, max_seen
            with lock:
                current += 1
                max_seen = max(max_seen, current)
            time.sleep(0.2)
            with lock:
                current -= 1
            return [{"id": text, "name": text, "type": "CONCEPT"}]

        def extract_rels(text, extracted, **kwargs):
            del text, extracted, kwargs
            return []

        items = [{"text": "alpha"}, {"text": "beta"}]
        config = SimpleNamespace(book_key="k", extract_concurrency=2, model="m")
        entities, relations, methods = _extract_items(
            items, config, extract_ents, extract_rels
        )
        self.assertGreaterEqual(max_seen, 2)
        self.assertEqual([e["name"] for e in entities], ["alpha", "beta"])
        self.assertEqual(relations, [])
        self.assertEqual(methods["ner_method"], "llm")

    def test_ner_failure_raises_without_pattern_fallback(self):
        def extract_ents(text, **kwargs):
            raise RuntimeError("boom")

        def extract_rels(text, extracted, **kwargs):
            raise AssertionError("relation must not run after NER failure")

        with self.assertRaises(LLMExtractionError) as ctx:
            _extract_items(
                [{"text": "x"}],
                SimpleNamespace(book_key="k", extract_concurrency=2, model="m"),
                extract_ents,
                extract_rels,
            )
        self.assertIn("LLM NER failed", str(ctx.exception))


class ExtractAuthRetryTests(unittest.TestCase):
    def test_auth_error_refreshes_and_retries_without_pattern_ner(self):
        calls = []
        keys_seen = []
        pattern_used = []

        def extract_ents(text, **kwargs):
            del kwargs
            calls.append(text)
            keys_seen.append(os.environ.get("XAI_API_KEY"))
            if len(calls) == 1:
                raise RuntimeError("Error code: 403 - unauthenticated:bad-credentials")
            return [{"id": text, "name": text, "type": "CONCEPT"}]

        def extract_rels(text, extracted, **kwargs):
            del text, extracted, kwargs
            return []

        def fake_pattern(*args, **kwargs):
            del args, kwargs
            pattern_used.append(True)
            raise AssertionError("pattern NER must not run")

        with patch("xai_oauth.resolve_access_token", return_value="new-access-token") as refresh:
            with patch.dict(os.environ, {"XAI_API_KEY": "old-key"}, clear=False):
                entities, relations, methods = _extract_items(
                    [{"text": "alpha"}],
                    SimpleNamespace(book_key="k", extract_concurrency=1, model="m"),
                    extract_ents,
                    extract_rels,
                )
                self.assertEqual(os.environ.get("XAI_API_KEY"), "new-access-token")
        self.assertEqual(calls, ["alpha", "alpha"])
        refresh.assert_called_with(force_refresh=True)
        self.assertEqual(keys_seen[0], "old-key")
        self.assertEqual(keys_seen[1], "new-access-token")
        self.assertEqual([e["name"] for e in entities], ["alpha"])
        self.assertEqual(relations, [])
        self.assertEqual(methods["ner_method"], "llm")
        self.assertEqual(pattern_used, [])
        for entity in entities:
            method = (entity.get("metadata") or {}).get("extraction_method")
            self.assertNotIn(method, {"pattern", "last_resort_pattern"})

    def test_refresh_none_raises_without_retrying_ner(self):
        calls = []

        def extract_ents(text, **kwargs):
            del kwargs
            calls.append(text)
            raise RuntimeError("unauthenticated:bad-credentials")

        def extract_rels(text, extracted, **kwargs):
            raise AssertionError("relation must not run after NER auth failure")

        with patch("xai_oauth.resolve_access_token", return_value=None) as refresh:
            with patch.dict(os.environ, {"XAI_API_KEY": "old-key"}, clear=False):
                with self.assertRaises(LLMExtractionError) as ctx:
                    _extract_items(
                        [{"text": "x"}],
                        SimpleNamespace(book_key="k", extract_concurrency=1, model="m"),
                        extract_ents,
                        extract_rels,
                    )
        self.assertIn("LLM NER failed", str(ctx.exception))
        self.assertEqual(calls, ["x"])
        refresh.assert_called_with(force_refresh=True)

    def test_retry_still_auth_fails_raises(self):
        calls = []

        def extract_ents(text, **kwargs):
            del kwargs
            calls.append(text)
            raise RuntimeError("HTTP 403 unauthenticated:bad-credentials")

        def extract_rels(text, extracted, **kwargs):
            raise AssertionError("relation must not run after NER auth failure")

        with patch("xai_oauth.resolve_access_token", return_value="new-access-token"):
            with patch.dict(os.environ, {"XAI_API_KEY": "old-key"}, clear=False):
                with self.assertRaises(LLMExtractionError) as ctx:
                    _extract_items(
                        [{"text": "x"}],
                        SimpleNamespace(book_key="k", extract_concurrency=1, model="m"),
                        extract_ents,
                        extract_rels,
                    )
        self.assertIn("LLM NER failed", str(ctx.exception))
        self.assertEqual(calls, ["x", "x"])

    def test_relation_auth_error_refreshes_and_retries(self):
        rel_calls = []

        def extract_ents(text, **kwargs):
            del kwargs
            return [{"id": text, "name": text, "type": "CONCEPT"}]

        def extract_rels(text, extracted, **kwargs):
            del extracted, kwargs
            rel_calls.append(text)
            if len(rel_calls) == 1:
                raise RuntimeError("unauthenticated:bad-credentials")
            return []

        with patch("xai_oauth.resolve_access_token", return_value="new-access-token") as refresh:
            with patch.dict(os.environ, {"XAI_API_KEY": "old-key"}, clear=False):
                entities, relations, methods = _extract_items(
                    [{"text": "alpha"}],
                    SimpleNamespace(book_key="k", extract_concurrency=1, model="m"),
                    extract_ents,
                    extract_rels,
                )
        self.assertEqual(rel_calls, ["alpha", "alpha"])
        refresh.assert_called_with(force_refresh=True)
        self.assertEqual([e["name"] for e in entities], ["alpha"])
        self.assertEqual(relations, [])
        self.assertEqual(methods["relation_method"], "llm")

    def test_concurrent_refresh_is_serialized_and_later_items_see_new_key(self):
        barrier = threading.Barrier(2)
        first_attempt = set()
        first_lock = threading.Lock()
        refresh_current = 0
        refresh_max = 0
        refresh_gate = threading.Lock()
        keys_on_success = []

        def extract_ents(text, **kwargs):
            del kwargs
            with first_lock:
                is_first = text not in first_attempt
                if is_first:
                    first_attempt.add(text)
            if is_first:
                barrier.wait(timeout=5)
                raise RuntimeError("Error code: 403 - unauthenticated:bad-credentials")
            keys_on_success.append(os.environ.get("XAI_API_KEY"))
            return [{"id": text, "name": text, "type": "CONCEPT"}]

        def extract_rels(text, extracted, **kwargs):
            del text, extracted, kwargs
            return []

        def fake_refresh(*, force_refresh=False):
            del force_refresh
            nonlocal refresh_current, refresh_max
            with refresh_gate:
                refresh_current += 1
                refresh_max = max(refresh_max, refresh_current)
            time.sleep(0.15)
            with refresh_gate:
                refresh_current -= 1
            return "new-access-token"

        with patch("xai_oauth.resolve_access_token", side_effect=fake_refresh) as refresh:
            with patch.dict(os.environ, {"XAI_API_KEY": "old-key"}, clear=False):
                entities, relations, methods = _extract_items(
                    [{"text": "alpha"}, {"text": "beta"}],
                    SimpleNamespace(book_key="k", extract_concurrency=2, model="m"),
                    extract_ents,
                    extract_rels,
                )
                self.assertEqual(os.environ.get("XAI_API_KEY"), "new-access-token")
        self.assertEqual(refresh_max, 1)
        self.assertGreaterEqual(refresh.call_count, 1)
        self.assertEqual(set(keys_on_success), {"new-access-token"})
        self.assertEqual(sorted(e["name"] for e in entities), ["alpha", "beta"])
        self.assertEqual(methods["ner_method"], "llm")
        self.assertEqual(relations, [])


if __name__ == "__main__":
    unittest.main()
