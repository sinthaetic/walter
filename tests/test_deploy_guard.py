import json
import sys
import tempfile
import io
import os
import shutil
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fetcher"))
import walter_deploy as wd
import walter_public as wpub
import walter_vault as v
import walter_auto
import walter_fetch
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
        for name in (".env", "etf_raw.json", "state.json", "owner-cache.json", "paper-journal-V2.1-FIXAD.csv",
                     "paper-journal-V3.csv"):
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
                                    "tradingview/w-cipher.pine", "tradingview/w-cipher-a.pine",
                                    "data/market.js", "data/cache.json", "data/pulse.js", "data/owner.enc"])

    def test_pulse_js_passes_leak_check(self):
        """data/pulse.js (bara datum och heltal) är tillåten och stoppas inte av läckspärren."""
        self.assertIn("data/pulse.js", wd.ALLOW)
        pulse = ROOT / "data" / "pulse.js"
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data").mkdir()
            shutil.copy2(pulse, Path(t) / "data" / "pulse.js")
            self.assertEqual(wd.leak_check(t), [])


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


def enc_file(path, obj, code="k"):
    Path(path).write_text(json.dumps(v.encrypt(obj, code, iter=1000)), encoding="utf-8")


class PublishOwnerTest(unittest.TestCase):
    """Lokal deploy: publicerade owner.enc slås ihop FÖRE ny skrivs, annars stopp. Inget nätverk."""

    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        d = Path(self.t.name)
        self.cache, self.out = d / "owner-cache.json", d / "out-owner.enc"
        self.cache.write_text(json.dumps({"daily": {"d2": 20}}), encoding="utf-8")
        self.patches = [mock.patch.object(walter_fetch, "OWNER_CACHE", self.cache),
                        mock.patch.object(walter_fetch, "CACHE", d / "cache.json"),
                        mock.patch.object(wd, "OWNER_ENC", self.out),
                        mock.patch("walter_paper.rebuild", return_value={"mode": "PARKERA"})]
        for x in self.patches:
            x.start()

    def tearDown(self):
        for x in self.patches:
            x.stop()
        self.t.cleanup()

    def fake_fetch(self, obj, code="k"):
        def f(repo, dst):
            if obj is None:
                return False
            enc_file(dst, obj, code)
            return True
        return mock.patch.object(wd, "fetch_published_owner_enc", side_effect=f)

    def test_merges_published_days_before_write(self):
        with self.fake_fetch({"state": {}, "daily": {"d1": 1, "d2": 2}, "notis": {"n": 1}}):
            wd.publish_owner("k", "https://example.invalid/r.git")
        got = v.decrypt(json.loads(self.out.read_text(encoding="utf-8")), "k")
        self.assertEqual(got["daily"], {"d1": 1, "d2": 20})
        self.assertEqual(got["notis"], {"n": 1})
        self.assertEqual(got["state"], {"mode": "PARKERA"})

    def test_first_run_without_published_owner_enc(self):
        with self.fake_fetch(None):
            wd.publish_owner("k", "https://example.invalid/r.git")
        self.assertEqual(v.decrypt(json.loads(self.out.read_text(encoding="utf-8")), "k")["daily"], {"d2": 20})

    def test_refuses_when_published_cannot_be_decrypted(self):
        with self.fake_fetch({"daily": {"d1": 1}}, code="gammal"), mock.patch.dict(os.environ, {"WALTER_GLOM_GAMLA_DAGAR": ""}):
            with self.assertRaises(SystemExit):
                wd.publish_owner("k", "https://example.invalid/r.git")
        self.assertFalse(self.out.exists())

    def test_override_allows_new_code(self):
        with self.fake_fetch({"daily": {"d1": 1}}, code="gammal"), \
                mock.patch.dict(os.environ, {"WALTER_GLOM_GAMLA_DAGAR": "1"}), mock.patch.object(wd, "warn"):
            wd.publish_owner("k", "https://example.invalid/r.git")
        self.assertTrue(self.out.exists())

    def test_no_repo_skips_fetch(self):
        with mock.patch.object(wd, "fetch_published_owner_enc") as f:
            wd.publish_owner("k", "")
        f.assert_not_called()
        self.assertTrue(self.out.exists())

    def test_write_owner_enc_without_key_removes_and_warns(self):
        self.out.write_text("gammal", encoding="utf-8")
        with mock.patch.object(wd, "warn") as w:
            wd.write_owner_enc(None)
        self.assertFalse(self.out.exists())
        self.assertIn("WALTER_OWNER_KEY", w.call_args[0][0])


class LockIfChangedTest(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        d = Path(self.t.name)
        self.src, self.enc = d / "state.json", d / "state.enc"
        self.patches = [mock.patch.object(v, "STATE", self.src), mock.patch.object(v, "ENC", self.enc),
                        mock.patch.object(v, "ITER", 1000)]
        for x in self.patches:
            x.start()

    def tearDown(self):
        for x in self.patches:
            x.stop()
        self.t.cleanup()

    def test_noop_when_equal(self):
        self.src.write_text('{"a": 1}', encoding="utf-8")
        enc_file(self.enc, {"a": 1})
        before = self.enc.read_text(encoding="utf-8")
        wd.lock_if_changed("k")
        self.assertEqual(self.enc.read_text(encoding="utf-8"), before)

    def test_refuses_when_enc_newer_and_different(self):
        self.src.write_text('{"a": 1}', encoding="utf-8")
        enc_file(self.enc, {"a": 2})
        os.utime(self.src, (1, 1))
        before = self.enc.read_text(encoding="utf-8")
        with self.assertRaises(SystemExit):
            wd.lock_if_changed("k")
        self.assertEqual(self.enc.read_text(encoding="utf-8"), before)

    def test_locks_when_json_newer(self):
        enc_file(self.enc, {"a": 2})
        os.utime(self.enc, (1, 1))
        self.src.write_text('{"a": 1}', encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            wd.lock_if_changed("k")
        self.assertEqual(v.decrypt(json.loads(self.enc.read_text(encoding="utf-8")), "k"), {"a": 1})


class CliAndGateTest(unittest.TestCase):
    def test_sla_ihop_missing_file(self):
        out = io.StringIO()
        with redirect_stdout(out):
            v.main(["sla-ihop", str(Path(tempfile.gettempdir()) / "finns-inte-walter.enc")])
        self.assertIn("inget att slå ihop", out.getvalue())

    def test_gate_without_state_json_skips(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            gh = d / "out.txt"
            out = io.StringIO()
            out.reconfigure = lambda **kw: None  # main() slår på utf-8 i terminalen
            with mock.patch.object(walter_auto, "STATE", d / "state.json"), \
                    mock.patch.object(walter_auto, "CACHE", d / "cache.json"), \
                    mock.patch.object(sys, "argv", ["walter_auto.py"]), \
                    mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(gh)}), redirect_stdout(out):
                walter_auto.main()
            self.assertEqual(gh.read_text(encoding="utf-8"), "run=false\n")
            self.assertIn("ingen state.json", out.getvalue())


if __name__ == "__main__":
    unittest.main()


def log_row(d, ready=True, red=3):
    return {"date": d, "ready": ready, "red": red, "px": None, "ethBtcAbove30dMa": None, "vix": None,
            "spxBelowMa": None}


class MergePublishedCacheTest(unittest.TestCase):
    """Lokal deploy: dagar som Actionen lagt i publicerade cache.json tappas inte. Inget nätverk."""

    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.cache = Path(self.t.name) / "cache.json"
        self.p = mock.patch.object(walter_fetch, "CACHE", self.cache)
        self.p.start()

    def tearDown(self):
        self.p.stop()
        self.t.cleanup()

    def fake(self, obj):
        def f(repo, dst):
            if obj is None:
                return False
            Path(dst).write_text(json.dumps(obj), encoding="utf-8")
            return True
        return mock.patch.object(wd, "fetch_published_cache", side_effect=f)

    def test_pages_newer_adds_action_days_and_keeps_newer_market(self):
        self.cache.write_text(json.dumps({"fetchedAt": "2026-10-20T10:00:00", "market": {"x": 1},
                                          "marketLog": [log_row("2026-10-19"), log_row("2026-10-20")]}),
                              encoding="utf-8")
        pages = {"fetchedAt": "2026-10-22T10:00:00", "market": {"x": 2},
                 "marketLog": [log_row("2026-10-20", red=5), log_row("2026-10-21"), log_row("2026-10-22")]}
        with self.fake(pages), redirect_stdout(io.StringIO()):
            wd.merge_published_cache("https://example.invalid/r.git")
        got = json.loads(self.cache.read_text(encoding="utf-8"))
        self.assertEqual([r["date"] for r in got["marketLog"]],
                         ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22"])
        self.assertEqual(got["marketLog"][1]["red"], 5)  # nyare cachen vinner
        self.assertEqual(got["market"], {"x": 2})
        self.assertEqual(got["fetchedAt"], "2026-10-22T10:00:00")

    def test_ready_row_never_replaced_by_not_ready(self):
        local = {"fetchedAt": "2026-10-20T10:00:00", "marketLog": [log_row("2026-10-20", red=2)]}
        pages = {"fetchedAt": "2026-10-20T12:00:00", "marketLog": [log_row("2026-10-20", ready=False, red=0)]}
        got = wd.merge_market_cache(local, pages)
        self.assertEqual(got["marketLog"], [log_row("2026-10-20", red=2)])

    def test_local_newer_keeps_local_market_and_wins_rows(self):
        local = {"fetchedAt": "2026-10-23T09:00:00", "market": {"x": "lokal"},
                 "marketLog": [log_row("2026-10-22", red=7)]}
        pages = {"fetchedAt": "2026-10-22T09:00:00", "market": {"x": "pages"},
                 "marketLog": [log_row("2026-10-21"), log_row("2026-10-22", red=1)]}
        got = wd.merge_market_cache(local, pages)
        self.assertEqual(got["market"], {"x": "lokal"})
        self.assertEqual([(r["date"], r["red"]) for r in got["marketLog"]],
                         [("2026-10-21", 3), ("2026-10-22", 7)])

    def test_first_run_without_published_cache(self):
        self.cache.write_text('{"fetchedAt": "2026-10-20T10:00:00"}', encoding="utf-8")
        with self.fake(None):
            wd.merge_published_cache("https://example.invalid/r.git")
        self.assertEqual(json.loads(self.cache.read_text(encoding="utf-8")), {"fetchedAt": "2026-10-20T10:00:00"})

    def test_first_run_without_local_cache(self):
        pages = {"fetchedAt": "2026-10-22T10:00:00", "marketLog": [log_row("2026-10-22")]}
        with self.fake(pages), redirect_stdout(io.StringIO()):
            wd.merge_published_cache("https://example.invalid/r.git")
        self.assertEqual(json.loads(self.cache.read_text(encoding="utf-8"))["marketLog"], [log_row("2026-10-22")])

    def test_private_keys_never_written(self):
        pages = {"fetchedAt": "2026-10-22T10:00:00", "daily": {"d": 1}, "notis": {"n": 1}, "marketLog": []}
        with self.fake(pages), redirect_stdout(io.StringIO()):
            wd.merge_published_cache("https://example.invalid/r.git")
        got = json.loads(self.cache.read_text(encoding="utf-8"))
        self.assertNotIn("daily", got)
        self.assertNotIn("notis", got)

    def test_no_repo_skips_fetch(self):
        with mock.patch.object(wd, "fetch_published_cache") as f:
            wd.merge_published_cache("")
        f.assert_not_called()


class PublishConfigTest(unittest.TestCase):
    def test_repo_without_key_refuses(self):
        with self.assertRaises(SystemExit) as e:
            wd.check_publish_config(None, "https://example.invalid/r.git")
        self.assertIn("WALTER_OWNER_KEY", str(e.exception))

    def test_ok_with_key_or_without_repo(self):
        wd.check_publish_config("k", "https://example.invalid/r.git")
        wd.check_publish_config(None, "")


class PushSourceTest(unittest.TestCase):
    def run_push(self, branch):
        calls = []

        def fake_run(args, **kw):
            calls.append(args)
            return mock.Mock(returncode=0)
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": ""}), \
                mock.patch.object(wd, "current_branch", return_value=branch), \
                mock.patch.object(wd.subprocess, "run", side_effect=fake_run), \
                mock.patch.object(wd, "warn") as w, \
                mock.patch.object(wd, "ROOT", ROOT):
            wd.push_source()
        return calls, w

    def test_pushes_head_to_main_explicitly(self):
        calls, _ = self.run_push("main")
        self.assertIn(["git", "push", "-q", "origin", "HEAD:main"], calls)

    def test_other_branch_does_not_commit_or_push(self):
        calls, w = self.run_push("steg-9")
        self.assertEqual(calls, [])
        self.assertIn("main", w.call_args[0][0])
