import json
import os
import stat
import tempfile
import unittest

from storage import atomic_write_json


class AtomicWriteJsonTests(unittest.TestCase):
    def test_writes_unicode_json_and_returns_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "nested", "state.json")
            data = {"name": "燕云十六声", "ids": ["a", "b"]}

            result = atomic_write_json(path, data)

            self.assertIs(result, data)
            with open(path, "r", encoding="utf-8") as stream:
                self.assertEqual(json.load(stream), data)
            with open(path, "rb") as stream:
                self.assertTrue(stream.read().endswith(b"\n"))

    def test_failed_serialization_keeps_previous_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "state.json")
            atomic_write_json(path, {"version": 1})

            with self.assertRaises(TypeError):
                atomic_write_json(path, {"bad": {1, 2, 3}})

            with open(path, "r", encoding="utf-8") as stream:
                self.assertEqual(json.load(stream), {"version": 1})
            leftovers = [name for name in os.listdir(folder) if name.endswith(".tmp")]
            self.assertEqual(leftovers, [])

    def test_replacement_preserves_existing_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "state.json")
            atomic_write_json(path, {"version": 1})
            os.chmod(path, 0o600)

            atomic_write_json(path, {"version": 2})

            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
