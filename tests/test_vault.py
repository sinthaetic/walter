import base64
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "fetcher"))
import walter_vault as v


class VaultTest(unittest.TestCase):
    def test_roundtrip(self):
        d = {"a": 1, "å": "ö"}
        self.assertEqual(v.decrypt(v.encrypt(d, "k", iter=1000), "k"), d)

    def test_wrong_code_raises(self):
        with self.assertRaises(v.VaultError):
            v.decrypt(v.encrypt({}, "k", iter=1000), "fel")

    def test_envelope_shape(self):
        e = v.encrypt({}, "k", iter=1000)
        self.assertEqual(set(e), {"v", "kdf", "iter", "salt", "iv", "ct"})
        self.assertEqual(e["v"], 1)
        self.assertEqual(e["kdf"], "PBKDF2-SHA256")
        self.assertEqual(len(base64.b64decode(e["salt"])), 16)
        self.assertEqual(len(base64.b64decode(e["iv"])), 12)

    def test_fresh_salt_iv(self):
        a, b = v.encrypt({"x": 1}, "k", iter=1000), v.encrypt({"x": 1}, "k", iter=1000)
        for k in ("salt", "iv", "ct"):
            self.assertNotEqual(a[k], b[k])

    def test_new_code_format(self):
        self.assertRegex(v.new_code(), r"^([A-HJ-NP-Z2-9]{5}-){5}[A-HJ-NP-Z2-9]{5}$")

    def test_lock_unlock_temp(self):
        import tempfile, json
        with tempfile.TemporaryDirectory() as t:
            s, e = Path(t) / "state.json", Path(t) / "state.enc"
            s.write_text('{"a": "å"}', encoding="utf-8")
            v.lock_state("k", s, e, iter=1000)
            s.unlink()
            v.unlock_state("k", s, e)
            self.assertEqual(json.loads(s.read_text(encoding="utf-8")), {"a": "å"})


if __name__ == "__main__":
    unittest.main()
