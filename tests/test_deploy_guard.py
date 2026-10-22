import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fetcher"))
import walter_deploy as wd
import walter_public as wpub
import walter_vault as v
from tests.test_public import fixture_state


def site(files):
    """Temp-mapp med {relativ sökväg: innehåll}."""
    t = tempfile.TemporaryDirectory()
    for rel, text in files.items():
        p = Path(t.name) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return t


class LeakCheckTest(unittest.TestCase):
    def test_leak_check_finds_journal(self):
        with site({"data/x.js": 'window.X = {"journal": []};'}) as t:
            hits = wd.leak_check(Path(t))
            self.assertEqual(len(hits), 1)
            self.assertIn("x.js", hits[0])

    def test_leak_check_finds_each_private_word(self):
        for word in ("journal", "portfolio", "k4", "capitalChange", "daily", "notis", "proposal",
                     "WALTER_OWNER_KEY", "etf_raw.json"):
            with site({"data/cache.json": f'{{"{word}": 1}}'}) as t:
                self.assertTrue(wd.leak_check(Path(t)), word)

    def test_leak_check_ignores_owner_enc(self):
        enc = json.dumps(v.encrypt({"journal": [1], "portfolio": {}}, "k", iter=1000))
        with site({"data/owner.enc": enc + ' "journal" '}) as t:
            self.assertEqual(wd.leak_check(Path(t)), [])

    def test_leak_check_ignores_js_dir(self):
        with site({"js/app.js": "state.portfolio; state.k4;"}) as t:
            self.assertEqual(wd.leak_check(Path(t)), [])

    def test_leak_check_clean_market_js(self):
        with tempfile.TemporaryDirectory() as t:
            st = fixture_state()
            snap = wpub.snapshot(st)
            (Path(t) / "data").mkdir()
            wpub.write_market_js(snap, wpub.append_log([], snap), Path(t) / "data" / "market.js")
            self.assertEqual(wd.leak_check(Path(t)), [])

    def test_leak_check_finds_state_js_and_reports_anywhere(self):
        with site({"data/state.js": "x", "assets/reports/k.txt": "x", "css/state.js": "x"}) as t:
            hits = " ".join(wd.leak_check(Path(t)))
            self.assertIn("reports", hits)
            self.assertEqual(hits.count("state.js"), 2)

    def test_leak_check_finds_blocked_names(self):
        for name in (".env", "etf_raw.json", "state.json", "owner-cache.json", "paper-journal-V2.1-FIXAD.csv"):
            with site({f"assets/{name}": "x"}) as t:
                self.assertTrue(wd.leak_check(Path(t)), name)


class OwnerEncTest(unittest.TestCase):
    def test_owner_enc_roundtrip(self):
        s, oc = {"journal": [{"a": "å"}], "mode": "PARKERA"}, {"daily": {"2026-10-22": 1.5}, "notis": {"t": 1}}
        out = v.decrypt(wd.build_owner_enc(s, oc, "k"), "k")
        self.assertEqual(out["state"], s)
        self.assertEqual(out["daily"], oc["daily"])
        self.assertEqual(out["notis"], oc["notis"])

    def test_owner_enc_empty_owner_cache(self):
        out = v.decrypt(wd.build_owner_enc({}, {}, "k"), "k")
        self.assertEqual(out, {"state": {}, "daily": {}, "notis": None})

    def test_allow_has_no_private_files(self):
        self.assertEqual(wd.ALLOW, ["index.html", "cipher.html", "css", "js", "assets",
                                    "data/market.js", "data/cache.json", "data/owner.enc"])


class MergeOwnerTest(unittest.TestCase):
    def test_merge_owner_cache_from_pages(self):
        with tempfile.TemporaryDirectory() as t:
            enc, oc = Path(t) / "owner.enc", Path(t) / "owner-cache.json"
            enc.write_text(json.dumps(v.encrypt({"state": {}, "daily": {"d1": 1, "d2": 2}, "notis": {"n": "gh"}},
                                                "k", iter=1000)), encoding="utf-8")
            oc.write_text(json.dumps({"daily": {"d2": 20, "d3": 3}}), encoding="utf-8")
            v.merge_owner_cache(enc, "k", oc)
            got = json.loads(oc.read_text(encoding="utf-8"))
            self.assertEqual(got["daily"], {"d1": 1, "d2": 20, "d3": 3})  # lokalt vinner vid samma datum
            self.assertEqual(got["notis"], {"n": "gh"})

    def test_merge_owner_cache_wrong_key_keeps_file(self):
        with tempfile.TemporaryDirectory() as t:
            enc, oc = Path(t) / "owner.enc", Path(t) / "owner-cache.json"
            enc.write_text(json.dumps(v.encrypt({"daily": {"d1": 1}}, "k", iter=1000)), encoding="utf-8")
            self.assertFalse(v.merge_owner_cache(enc, "fel", oc))
            self.assertFalse(oc.exists())


if __name__ == "__main__":
    unittest.main()
