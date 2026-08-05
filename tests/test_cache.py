import os
import sys
from unittest import TestCase, main
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from fakeredis import FakeStrictRedis

from src.agent.models import AgentResponse
from src.cache.cache import SemanticCache, _cosine_similarity, CACHE_KEY_PREFIX


def _make_embedding(base: list[float], noise: float = 0.0) -> list[float]:
    arr = np.array(base, dtype=np.float64)
    if noise:
        arr += np.random.RandomState(42).normal(0, noise, len(base))
    arr = arr / np.linalg.norm(arr)
    return arr.tolist()


# Base vector for "SparkClean" queries
_SPARKCLEAN_BASE = _make_embedding([1.0] * 10 + [0.0] * 10)

# Similar vector (cosine ~0.99)
_SPARKCLEAN_SIMILAR = _make_embedding([0.99] * 10 + [0.01] * 10)

# Vector for "GlucoJoy" queries (cosine ~0.5 with SparkClean base)
_GLUCOJOY_BASE = _make_embedding([0.0] * 10 + [1.0] * 10)

# Vector for "weather" queries (cosine ~0.0 with everything)
_WEATHER_BASE = _make_embedding([1.0, -1.0] * 10)

# Very similar vector (cosine ~0.98)
_SPARKCLEAN_VERY_SIMILAR = _make_embedding([0.98] * 10 + [0.02] * 10)

# Slightly different (cosine ~0.0 with SparkClean base — below threshold)
_SPARKCLEAN_DIFFERENT = _make_embedding([0.0] * 10 + [1.0] * 10)

# GlucoJoy similar
_GLUCOJOY_SIMILAR = _make_embedding([0.01] * 10 + [0.99] * 10)


def _mock_embedding(text: str) -> list[float]:
    text_lower = text.lower()
    if "sparkclean" in text_lower and "spike" in text_lower:
        return _SPARKCLEAN_BASE
    if "sparkclean" in text_lower and "promotion" in text_lower:
        return _SPARKCLEAN_SIMILAR
    if "sparkclean" in text_lower and "price" in text_lower:
        return _SPARKCLEAN_VERY_SIMILAR
    if "sparkclean" in text_lower and "sale" in text_lower:
        return _SPARKCLEAN_DIFFERENT
    if "sparkclean" in text_lower:
        return _SPARKCLEAN_BASE
    if "glucoj" in text_lower and "stockout" in text_lower:
        return _GLUCOJOY_BASE
    if "glucoj" in text_lower and "product" in text_lower:
        return _GLUCOJOY_SIMILAR
    if "glucoj" in text_lower:
        return _GLUCOJOY_BASE
    if "weather" in text_lower or "temperature" in text_lower:
        return _WEATHER_BASE
    return _make_embedding([0.5] * 20)


def _make_response(answer: str, intent: str = "WHAT") -> AgentResponse:
    return AgentResponse(
        answer=answer,
        intent=intent,
        citations=["test:source"],
        confidence=0.95,
        status="OK",
    )


class TestCosineSimilarity(TestCase):
    def test_identical_vectors(self):
        v = [1.0, 0.0, 0.0]
        self.assertAlmostEqual(_cosine_similarity(v, v), 1.0)

    def test_orthogonal_vectors(self):
        self.assertAlmostEqual(_cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_opposite_vectors(self):
        self.assertAlmostEqual(_cosine_similarity([1.0, 0.0], [-1.0, 0.0]), -1.0)

    def test_partial_similarity(self):
        sim = _cosine_similarity([1.0, 0.0], [0.707, 0.707])
        self.assertGreater(sim, 0.7)
        self.assertLess(sim, 0.71)

    def test_zero_vector(self):
        self.assertEqual(_cosine_similarity([0.0, 0.0], [1.0, 0.0]), 0.0)


class TestSemanticCache(TestCase):
    def setUp(self):
        self.fake_redis = FakeStrictRedis(decode_responses=True)
        self.cache = SemanticCache(redis_client=self.fake_redis)
        self.embed_patcher = patch("src.cache.cache.get_embedding", side_effect=_mock_embedding)
        self.embed_patcher.start()

    def tearDown(self):
        self.embed_patcher.stop()
        self.fake_redis.flushall()

    # --- Cache miss scenarios ---

    def test_01_cache_miss_first_query(self):
        """First query should miss cache"""
        result = self.cache.get("Why did SparkClean 1kg sales spike in Mumbai?")
        self.assertIsNone(result)

    def test_02_cache_miss_different_topic(self):
        """Different topic after caching should miss"""
        self.cache.set("Why did SparkClean 1kg sales spike?", _make_response("SparkClean spike"))
        result = self.cache.get("What is the weather in Mumbai?")
        self.assertIsNone(result)

    def test_03_cache_miss_barely_similar(self):
        """Query with similarity below threshold should miss"""
        self.cache.set("SparkClean 1kg sales spike in Mumbai", _make_response("SparkClean spike"))
        result = self.cache.get("SparkClean 1kg sale in Mumbai")
        self.assertIsNone(result)

    # --- Cache hit scenarios ---

    def test_04_cache_hit_exact_match(self):
        """Exact same query should hit"""
        query = "Why did SparkClean 1kg sales spike in Mumbai?"
        self.cache.set(query, _make_response("Because of a promotion"))
        result = self.cache.get(query)
        self.assertIsNotNone(result)
        self.assertEqual(result.answer, "Because of a promotion")
        self.assertEqual(result.intent, "WHAT")

    def test_05_cache_hit_similar_paraphrase(self):
        """Semantically similar paraphrase should hit"""
        self.cache.set(
            "Why did SparkClean 1kg sales spike in Mumbai?",
            _make_response("15% price-off promotion"),
        )
        result = self.cache.get("What caused the SparkClean 1kg promotion spike in Mumbai?")
        self.assertIsNotNone(result)
        self.assertEqual(result.answer, "15% price-off promotion")

    def test_06_cache_hit_minor_wording(self):
        """Minor wording changes should hit"""
        self.cache.set(
            "SparkClean 1kg price promotion Mumbai",
            _make_response("Price promotion drove sales"),
        )
        result = self.cache.get("SparkClean 1kg price in Mumbai promotion")
        self.assertIsNotNone(result)

    def test_07_cache_hit_glucojoy_similar(self):
        """Similar GlucoJoy queries should hit"""
        self.cache.set(
            "What is GlucoJoy stockout situation?",
            _make_response("GlucoJoy is a glucose product", "WHAT"),
        )
        result = self.cache.get("Tell me about GlucoJoy product details")
        self.assertIsNotNone(result)

    def test_08_cache_hit_multi_entry_correct_match(self):
        """With multiple cached entries, the best match is returned"""
        self.cache.set("What is the weather in Mumbai?", _make_response("It is sunny", "WHAT"))
        self.cache.set(
            "Why did SparkClean 1kg sales spike in Mumbai?",
            _make_response("15% price-off promotion drove the spike", "WHY"),
        )
        result = self.cache.get("What caused the SparkClean 1kg spike in Mumbai?")
        self.assertIsNotNone(result)
        self.assertIn("promotion", result.answer.lower())

    # --- Cache lifecycle ---

    def test_09_cache_ttl_expiry(self):
        """Expired entries should not be returned"""
        self.cache.set("Why did SparkClean spike?", _make_response("Promotion"))
        # Manually expire the key
        key = CACHE_KEY_PREFIX + str(hash("Why did SparkClean spike?"))
        self.fake_redis.expire(key, 0)
        self.fake_redis.expire("semcache:index", 0)
        import time
        time.sleep(0.01)
        # Index key is expired, so no active keys
        result = self.cache.get("Why did SparkClean spike?")
        self.assertIsNone(result)

    def test_10_cache_clear(self):
        """Clearing the cache should remove all entries"""
        self.cache.set("Query 1", _make_response("Answer 1"))
        self.cache.set("Query 2", _make_response("Answer 2"))
        self.cache.clear()
        self.assertIsNone(self.cache.get("Query 1"))
        self.assertIsNone(self.cache.get("Query 2"))

    def test_11_cache_round_trip(self):
        """Full round-trip: set then get exact match"""
        expected = _make_response("SparkClean spike was driven by a 15% promotion", "WHY")
        self.cache.set("Why did SparkClean 1kg spike in Mumbai?", expected)
        result = self.cache.get("Why did SparkClean 1kg spike in Mumbai?")
        self.assertIsNotNone(result)
        self.assertEqual(result.answer, expected.answer)
        self.assertEqual(result.intent, expected.intent)
        self.assertEqual(result.citations, expected.citations)
        self.assertEqual(result.confidence, expected.confidence)
        self.assertEqual(result.status, expected.status)

    def test_12_cache_hit_refreshes_ttl(self):
        """Cache hit should refresh the TTL"""
        self.cache.set("Why did SparkClean spike?", _make_response("Promotion"))
        key = CACHE_KEY_PREFIX + str(hash("Why did SparkClean spike?"))
        initial_ttl = self.fake_redis.ttl(key)
        # Simulate some time passing
        self.fake_redis.expire(key, 2)
        self.cache.get("Why did SparkClean spike?")
        refreshed_ttl = self.fake_redis.ttl(key)
        self.assertGreater(refreshed_ttl, 2)


if __name__ == "__main__":
    main()