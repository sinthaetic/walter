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

    def test_tampered_ct_raises(self):
        e = v.encrypt({"a": 1}, "k", iter=1000)
        raw = bytearray(base64.b64decode(e["ct"]))
        raw[0] ^= 1
        e["ct"] = base64.b64encode(bytes(raw)).decode()
        with self.assertRaises(v.VaultError):
            v.decrypt(e, "k")

    def test_broken_envelope_raises(self):
        e = v.encrypt({"a": 1}, "k", iter=1000)
        e2 = dict(e)
        del e2["iv"]
        with self.assertRaises(v.VaultError):
            v.decrypt(e2, "k")
        e["ct"] = e["ct"][:8]
        with self.assertRaises(v.VaultError):
            v.decrypt(e, "k")

    def test_unlock_refuses_newer_state(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as t:
            s, e = Path(t) / "state.json", Path(t) / "state.enc"
            s.write_text('{"a": 1}', encoding="utf-8")
            v.lock_state("k", s, e, iter=1000)
            s.write_text('{"a": 2}', encoding="utf-8")
            os.utime(e, (1, 1))
            with self.assertRaises(SystemExit) as cm:
                v.unlock_state("k", s, e)
            self.assertIn("las", str(cm.exception))
            self.assertEqual(s.read_text(encoding="utf-8"), '{"a": 2}')

    def test_missing_files_exit_clearly(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            s, e = Path(t) / "state.json", Path(t) / "state.enc"
            with self.assertRaises(SystemExit) as cm:
                v.unlock_state("k", s, e)
            self.assertIn("Hittar inte state.enc", str(cm.exception))
            with self.assertRaises(SystemExit) as cm:
                v.lock_state("k", s, e)
            self.assertIn("Hittar inte state.json", str(cm.exception))
            self.assertFalse(e.exists())


if __name__ == "__main__":
    unittest.main()
