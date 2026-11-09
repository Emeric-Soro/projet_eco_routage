"""Tests de la réutilisation du cache de calibration (sans jeux de données)."""
from pathlib import Path
import tempfile
import unittest
from calibration_cache import fingerprint, load_or_build

class CalibrationCacheTests(unittest.TestCase):
    def test_cache_hit(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source.parquet"
            source.write_bytes(b"data")
            key = fingerprint([source], {"min": 100})
            count = []
            def compute():
                count.append(1)
                return {"factor": 42}
            self.assertEqual(load_or_build(root / "cache", "cal", key, compute), {"factor": 42})
            self.assertEqual(load_or_build(root / "cache", "cal", key, compute), {"factor": 42})
            self.assertEqual(len(count), 1)

    def test_invalidates_when_file_or_parameters_change(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "data.parquet"
            source.write_bytes(b"one")
            initial = fingerprint([source], {"threshold": 1})
            self.assertNotEqual(initial, fingerprint([source], {"threshold": 2}))
            source.write_bytes(b"substantially different dataset")
            self.assertNotEqual(initial, fingerprint([source], {"threshold": 1}))

    def test_corrupted_file_is_rebuilt(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "cal-key.pickle").write_bytes(b"broken")
            self.assertEqual(load_or_build(root, "cal", "key", lambda: 15), 15)
            self.assertEqual(load_or_build(root, "cal", "key", lambda: 30), 15)

    def test_new_file_invalidates_fingerprint(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "new.parquet"
            before = fingerprint([source], {})
            source.write_bytes(b"yes")
            self.assertNotEqual(before, fingerprint([source], {}))

if __name__ == "__main__":
    unittest.main()
