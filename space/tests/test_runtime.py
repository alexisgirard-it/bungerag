from __future__ import annotations

import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


SPACE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SPACE_DIR))

from runtime import BoundedLRUCache, QuotaExceeded, QuotaGuard, classify_exception  # noqa: E402


class CacheTests(unittest.TestCase):
    def test_lru_evicts_the_least_recently_used_item(self):
        cache: BoundedLRUCache[str, int] = BoundedLRUCache(max_size=2)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertEqual(cache.get("a"), 1)
        cache.put("c", 3)
        self.assertIsNone(cache.get("b"))
        self.assertEqual(cache.get("a"), 1)
        self.assertEqual(cache.get("c"), 3)


class QuotaTests(unittest.TestCase):
    def test_reserved_capacity_is_counted_before_commit(self):
        guard = QuotaGuard(daily_limit=2, per_client_limit=1)
        reservation = guard.reserve("client-a", today="2026-07-31")
        with self.assertRaises(QuotaExceeded) as caught:
            guard.reserve("client-a", today="2026-07-31")
        self.assertEqual(caught.exception.scope, "client")
        self.assertTrue(guard.commit(reservation))
        self.assertEqual(guard.snapshot()["completed_total"], 1)

    def test_release_restores_capacity(self):
        guard = QuotaGuard(daily_limit=1, per_client_limit=1)
        reservation = guard.reserve("client-a", today="2026-07-31")
        self.assertTrue(guard.release(reservation))
        replacement = guard.reserve("client-b", today="2026-07-31")
        self.assertIsNotNone(replacement)

    def test_day_rollover_resets_completed_counts(self):
        guard = QuotaGuard(daily_limit=1, per_client_limit=1)
        first = guard.reserve("client-a", today="2026-07-31")
        guard.commit(first)
        second = guard.reserve("client-a", today="2026-08-01")
        self.assertEqual(second.day, "2026-08-01")

    def test_concurrent_reservations_never_exceed_global_limit(self):
        guard = QuotaGuard(daily_limit=3, per_client_limit=3)

        def reserve(index: int) -> bool:
            try:
                guard.reserve(f"client-{index}", today="2026-07-31")
                return True
            except QuotaExceeded:
                return False

        with ThreadPoolExecutor(max_workers=12) as pool:
            accepted = list(pool.map(reserve, range(12)))
        self.assertEqual(sum(accepted), 3)
        self.assertEqual(guard.snapshot()["reserved_total"], 3)


class ErrorClassificationTests(unittest.TestCase):
    def test_provider_quota_is_not_reported_as_internal(self):
        self.assertEqual(classify_exception(RuntimeError("quota Gemini epuise")), "provider")

    def test_unknown_bug_is_internal(self):
        self.assertEqual(classify_exception(ValueError("bad invariant")), "internal")


if __name__ == "__main__":
    unittest.main()
