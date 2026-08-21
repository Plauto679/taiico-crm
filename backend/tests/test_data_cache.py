import json
import tempfile
import threading
import time
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.data_cache import PersistentDataCache


class PersistentDataCacheTests(unittest.TestCase):
    def test_fresh_value_avoids_reloading(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = PersistentDataCache(Path(directory))
            calls = []
            first = cache.get_or_load("source", lambda: calls.append(1) or {"rows": [1]}, ttl_seconds=60)
            second = cache.get_or_load("source", lambda: calls.append(2) or {}, ttl_seconds=60)
            self.assertEqual(first.value, second.value)
            self.assertEqual(second.state, "hit")
            self.assertEqual(calls, [1])

    def test_value_survives_new_cache_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            PersistentDataCache(path).set("source", {"rows": [1, 2]})
            result = PersistentDataCache(path).get_or_load("source", lambda: {}, ttl_seconds=60)
            self.assertEqual(result.value, {"rows": [1, 2]})
            self.assertEqual(result.state, "hit")

    def test_stale_value_returns_immediately_and_refreshes(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = PersistentDataCache(Path(directory))
            cache.set("source", {"version": 1})
            path = cache._path("source")
            document = json.loads(path.read_text())
            document["stored_at"] = time.time() - 20
            path.write_text(json.dumps(document))
            cache._entries.clear()
            refreshed = threading.Event()

            def loader():
                refreshed.set()
                return {"version": 2}

            result = cache.get_or_load("source", loader, ttl_seconds=1)
            self.assertEqual(result.value, {"version": 1})
            self.assertEqual(result.state, "stale")
            self.assertTrue(refreshed.wait(1))
            for _ in range(50):
                if cache.get_or_load("source", loader, ttl_seconds=60).value == {"version": 2}:
                    break
                time.sleep(0.01)
            self.assertEqual(cache.get_or_load("source", loader, ttl_seconds=60).value, {"version": 2})

    def test_invalidation_removes_memory_and_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = PersistentDataCache(Path(directory))
            cache.set("source", {"version": 1})
            cache.invalidate("source")
            self.assertFalse(cache._path("source").exists())
            result = cache.get_or_load("source", lambda: {"version": 2}, ttl_seconds=60)
            self.assertEqual(result.value, {"version": 2})

    def test_concurrent_misses_use_one_loader(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = PersistentDataCache(Path(directory))
            calls = 0
            calls_lock = threading.Lock()

            def loader():
                nonlocal calls
                with calls_lock:
                    calls += 1
                time.sleep(0.03)
                return {"ready": True}

            results = []
            threads = [threading.Thread(target=lambda: results.append(cache.get_or_load("source", loader, ttl_seconds=60).value)) for _ in range(5)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(calls, 1)
            self.assertEqual(results, [{"ready": True}] * 5)


if __name__ == "__main__":
    unittest.main()
