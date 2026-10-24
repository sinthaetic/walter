"""Ägarens Walter handlar själv (walter_paper.auto), datorn hämtar affärerna (walter_vault.sync_from_repo),
och notisen säger vad han gjorde. Bara temp-filer – rör aldrig data/."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fetcher"))
import walter_fetch as wf
import walter_notis as wn
import walter_paper as wpaper
import walter_vault as v

KEY = "TEST-KOD"
TODAY = "2026-10-23"


def raw_state():
    return {"mode": "AVVAKTAR", "updatedAt": "2026-10-22", "journal": [{"date": "2026-10-22", "plain": "gammal"}],
            "rules": {}, "k4": [],
            "portfolio": {"holdings": {"CASH": 1000.0, "BTC": 0, "ETH": 0, "GOLD": 0}, "positions": {},
                          "peak": 1000.0, "value": 1000.0, "history": []}}


def proposal(ready=True):
    if not ready:
        return {"asOf": TODAY, "ready": False, "plain": "Walter väntar på data."}
    return {"asOf": TODAY, "ready": True, "red": 3, "mode": "NORMAL", "currentMode": "AVVAKTAR",
            "trades": [{"asset": "BTC", "side": "köp", "units": 0.001, "priceSek": 100000.0,
                        "sek": 100.0, "feeSek": 0.5}],
            "valueSek": 1000.0, "plain": "Walter vill köpa bitcoin för 100 kr.", "needsApproval": True}


class AutoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.state, self.enc = d / "state.json", d / "state.enc"
        self.state.write_text(json.dumps(raw_state()), encoding="utf-8")
        self.built = []
        self.patches = [patch.object(wf, "BASE", self.state), patch.object(v, "ENC", self.enc),
                        patch.object(v, "STATE", self.state),
                        patch.object(v, "owner_key", lambda: KEY),
                        patch.object(wpaper, "rebuild", lambda w: {"built": True}),
                        patch.object(wf, "write_js", lambda s: self.built.append(s))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def run_auto(self, prop):
        with patch.object(wpaper, "propose", lambda s, **k: prop):
            return wpaper.auto(wf, today=TODAY)

    def test_trades_and_marks_auto_and_locks(self):
        entry = self.run_auto(proposal())
        self.assertIsNotNone(entry)
        self.assertTrue(entry["auto"])
        raw = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(raw["mode"], "NORMAL")
        self.assertEqual(raw["journal"][0]["date"], TODAY)
        self.assertTrue(raw["journal"][0]["auto"])
        self.assertEqual(raw["portfolio"]["positions"]["BTC"]["units"], 0.001)
        self.assertEqual(v.decrypt(json.loads(self.enc.read_text(encoding="utf-8")), KEY), raw)
        self.assertEqual(len(self.built), 1)  # state.js byggdes om

    def test_only_once_per_day(self):
        self.assertIsNotNone(self.run_auto(proposal()))
        self.assertIsNone(self.run_auto(proposal()))
        raw = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual([j["date"] for j in raw["journal"]], [TODAY, "2026-10-22"])

    def test_manual_entry_today_does_not_block(self):
        raw = raw_state()
        raw["journal"].insert(0, {"date": TODAY, "plain": "manuell"})
        self.state.write_text(json.dumps(raw), encoding="utf-8")
        self.assertIsNotNone(self.run_auto(proposal()))

    def test_not_ready_does_nothing(self):
        before = self.state.read_text(encoding="utf-8")
        self.assertIsNone(self.run_auto(proposal(ready=False)))
        self.assertEqual(self.state.read_text(encoding="utf-8"), before)
        self.assertFalse(self.enc.exists())

    def test_nothing_to_approve_does_nothing(self):
        p = proposal()
        p.update(trades=[], mode="AVVAKTAR", needsApproval=False)
        self.assertIsNone(self.run_auto(p))
        self.assertFalse(self.enc.exists())

    def test_autopilot_check_without_trades_is_written(self):
        # Söndagens koll utan affär skrivs ändå (auto + check), så att en missad söndag märks nästa dag
        p = {"asOf": TODAY, "ready": True, "strategy": "autopilot", "red": 3, "mode": "AVVAKTAR",
             "currentMode": "AVVAKTAR", "trades": [], "valueSek": 1000.0, "decisionDay": True, "check": True,
             "plain": "Söndag: allt ligger inom marginalen. Jag rör ingenting.", "needsApproval": True,
             "weights": {"BTC": 0.35, "ETH": 0.2, "GOLD": 0.2}}
        entry = self.run_auto(p)
        self.assertTrue(entry["auto"] and entry["check"])
        self.assertTrue(entry["plain"].startswith("Söndag: allt ligger inom marginalen."))
        self.assertIsNone(self.run_auto(p))  # en gång per dag

    def test_no_key_does_not_trade(self):
        before = self.state.read_text(encoding="utf-8")
        with patch.object(v, "owner_key", lambda: None):
            self.assertIsNone(self.run_auto(proposal()))
        self.assertEqual(self.state.read_text(encoding="utf-8"), before)


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".git").mkdir()
        self.state, self.enc = self.root / "state.json", self.root / "state.enc"
        self.calls = []
        self.p_key = patch.object(v, "owner_key", lambda: KEY)
        self.p_key.start()
        self.p_env = patch.dict(os.environ, {}, clear=False)
        self.p_env.start()
        os.environ.pop("GITHUB_ACTIONS", None)

    def tearDown(self):
        self.p_env.stop()
        self.p_key.stop()
        self.tmp.cleanup()

    def put(self, path, obj, mtime, enc=False):
        text = json.dumps(v.encrypt(obj, KEY, iter=1000)) if enc else json.dumps(obj)
        path.write_text(text, encoding="utf-8")
        os.utime(path, (mtime, mtime))

    def fake_run(self, pulled=None, rc=0, stderr=""):
        def run(cmd, **kw):
            self.calls.append(cmd)
            if pulled is not None:  # "git pull" kom med en ny state.enc
                self.put(self.enc, pulled, 5000, enc=True)

            class R:
                returncode = rc
            R.stderr = stderr
            R.stdout = ""
            return R()
        return run

    def sync(self, run):
        out = io.StringIO()
        with redirect_stdout(out):
            res = v.sync_from_repo(root=self.root, state=self.state, enc=self.enc, run=run)
        return res, out.getvalue()

    def local(self):
        return json.loads(self.state.read_text(encoding="utf-8"))

    def test_unlocks_when_enc_newer_and_different(self):
        self.put(self.state, {"a": 1}, 1000)
        self.put(self.enc, {"a": 2}, 2000, enc=True)
        res, _ = self.sync(self.fake_run())
        self.assertEqual(res, "unlocked")
        self.assertEqual(self.local(), {"a": 2})
        self.assertEqual(self.calls[0][:3], ["git", "pull", "--ff-only"])

    def test_unlocks_what_pull_brought(self):
        # efter förra las-upp är state.json nyare än state.enc men lika – det är inga lokala ändringar
        self.put(self.enc, {"a": 1}, 1000, enc=True)
        self.put(self.state, {"a": 1}, 2000)
        res, _ = self.sync(self.fake_run(pulled={"a": 2, "auto": True}))
        self.assertEqual(res, "unlocked")
        self.assertEqual(self.local(), {"a": 2, "auto": True})

    def test_keeps_newer_local_changes(self):
        self.put(self.enc, {"a": 1}, 1000, enc=True)
        self.put(self.state, {"a": 3}, 3000)
        res, out = self.sync(self.fake_run(pulled={"a": 2}))
        self.assertEqual(res, "local")
        self.assertEqual(self.local(), {"a": 3})
        self.assertIn("nyare", out)
        self.assertIn("las (tar dina, skriver över Walters) eller las-upp (tar Walters)", out)

    def test_unlock_keeps_backup(self):
        self.put(self.state, {"a": 1}, 1000)
        self.put(self.enc, {"a": 2}, 2000, enc=True)
        res, _ = self.sync(self.fake_run())
        self.assertEqual(res, "unlocked")
        bak = self.state.with_name("state.json.bak")
        self.assertEqual(json.loads(bak.read_text(encoding="utf-8")), {"a": 1})

    def test_failed_pull_is_said_and_not_unlocked(self):
        self.put(self.state, {"a": 1}, 1000)
        self.put(self.enc, {"a": 2}, 2000, enc=True)
        res, out = self.sync(self.fake_run(rc=1, stderr="fatal: Not possible to fast-forward, aborting."))
        self.assertEqual(res, "pullfail")
        self.assertIn("Kunde inte hämta main – kör git status", out)
        self.assertEqual(self.local(), {"a": 1})

    def test_offline_pull_is_quiet(self):
        self.put(self.state, {"a": 1}, 1000)
        self.put(self.enc, {"a": 2}, 2000, enc=True)
        err = "fatal: unable to access 'https://github.com/x/walter.git/': Could not resolve host: github.com"
        res, out = self.sync(self.fake_run(rc=128, stderr=err))
        self.assertEqual(res, "unlocked")
        self.assertNotIn("Kunde inte hämta", out)

    def test_same_content_does_nothing(self):
        self.put(self.state, {"a": 1}, 1000)
        self.put(self.enc, {"a": 1}, 2000, enc=True)
        before = self.state.stat().st_mtime
        res, _ = self.sync(self.fake_run())
        self.assertEqual(res, "same")
        self.assertEqual(self.state.stat().st_mtime, before)

    def test_does_nothing_in_github_actions(self):
        self.put(self.state, {"a": 1}, 1000)
        self.put(self.enc, {"a": 2}, 2000, enc=True)
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            res, _ = self.sync(self.fake_run())
        self.assertIsNone(res)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.local(), {"a": 1})

    def test_quiet_when_git_missing(self):
        self.put(self.state, {"a": 1}, 1000)
        self.put(self.enc, {"a": 2}, 2000, enc=True)

        def boom(cmd, **kw):
            raise FileNotFoundError("git")
        res, _ = self.sync(boom)
        self.assertEqual(res, "unlocked")  # offline/ingen git: jobbar med det som finns


class PaperCliTest(unittest.TestCase):
    def run_main(self, argv, sync_result="same"):
        calls = {"auto": 0, "sync": 0}

        def fake_auto(w, today=None, say=lambda s: None):
            calls["auto"] += 1
            say("Walter handlar inte: test.")

        def fake_sync():
            calls["sync"] += 1
            return sync_result

        def no_input(prompt=""):
            raise AssertionError("input() får inte anropas")

        out = io.StringIO()
        out.reconfigure = lambda **kw: None
        with patch.object(sys, "argv", ["walter_paper.py", *argv]), patch.object(wpaper, "auto", fake_auto),                 patch.object(v, "sync_from_repo", fake_sync), patch("builtins.input", no_input),                 patch.object(wpaper, "rebuild", lambda w: {}),                 patch.object(wpaper, "propose", lambda s: proposal()), redirect_stdout(out):
            wpaper.main()
        return calls, out.getvalue()

    def test_auto_flag_runs_auto_without_sync_or_input(self):
        calls, out = self.run_main(["--auto"])
        self.assertEqual(calls, {"auto": 1, "sync": 0})
        self.assertIn("Walter handlar inte: test.", out)

    def test_manual_stops_before_ja_when_local_changes(self):
        for res in ("local", "pullfail"):
            calls, out = self.run_main([], sync_result=res)
            self.assertEqual(calls, {"auto": 0, "sync": 1})
            self.assertIn("Inget handlat", out)


class NotisAutoTest(unittest.TestCase):
    def state(self, journal):
        return {"portfolio": {"value": 1000, "holdings": {"CASH": 900}}, "market": {"btc": {"value": None}},
                "lampScore": {"red": 3, "total": 10}, "mode": "NORMAL", "journal": journal}

    def test_mentions_todays_auto_trade(self):
        j = [{"date": TODAY, "auto": True, "mode": "NORMAL",
              "plain": "WALTER köpte bitcoin för 100 kr. 3 av 10 lampor var röda, så läget är Köper lite. 900 kr ligger som kontanter."}]
        text = wn.text_for(self.state(j), "kvall", "22:05", today=TODAY)
        self.assertIn("Walter köpte bitcoin för 100 kr", text)

    def test_mentions_auto_mode_change(self):
        j = [{"date": TODAY, "auto": True, "mode": "NORMAL",
              "plain": "3 av 10 lampor var röda, så läget är Köper lite. 900 kr ligger som kontanter."}]
        text = wn.text_for(self.state(j), "morgon", "08:13", today=TODAY)
        self.assertIn("Walter bytte själv läge till Köper lite", text)

    def ap_state(self, journal, **prop):
        s = self.state(journal)
        s["proposal"] = dict({"strategy": "autopilot", "ready": True, "trades": [], "decisionDay": False,
                              "nextCheck": "2026-10-25"}, **prop)
        return s

    def test_autopilot_lamps_are_weather(self):
        text = wn.text_for(self.ap_state([]), "kvall", "22:05", today=TODAY)
        self.assertIn("Väder: 3/10 lampor röda (Köper lite).", text)
        self.assertNotIn("Walter håller", text)
        self.assertIn("Autopilot: inget att göra i dag. Nästa koll söndag 25 okt.", text)

    def test_autopilot_within_band_and_trade_today(self):
        sun = "2026-10-25"
        j = [{"date": sun, "auto": True, "check": True, "mode": "NORMAL",
              "plain": "Söndag: allt ligger inom marginalen. Jag rör ingenting."}]
        text = wn.text_for(self.ap_state(j, nextCheck="2026-11-01"), "kvall", "22:05", today=sun)
        self.assertIn("Autopilot: dagens koll är gjord, allt inom marginalen. Nästa koll söndag 1 nov.", text)
        j = [{"date": sun, "auto": True, "check": True, "mode": "NORMAL",
              "plain": "WALTER köpte guld för 8 684 kr. Autopiloten justerade andelarna."}]
        text = wn.text_for(self.ap_state(j, nextCheck="2026-11-01"), "kvall", "22:05", today=sun)
        self.assertIn("Autopilot: Walter köpte guld för 8 684 kr i dag, helt själv.", text)

    def test_autopilot_pending_and_waiting(self):
        text = wn.text_for(self.ap_state([], trades=[{"asset": "BTC"}], decisionDay=True), "morgon", "08:13",
                           today=TODAY)
        self.assertIn("Autopilot: justerar andelarna vid nästa körning.", text)
        self.assertIn("Autopilot: väntar på priser.", wn.text_for(self.ap_state([], ready=False), "morgon", "08:13",
                                                                   today=TODAY))

    def test_quiet_without_auto_today(self):
        old = [{"date": "2026-10-22", "auto": True, "mode": "NORMAL", "plain": "WALTER köpte bitcoin för 100 kr."}]
        manual = [{"date": TODAY, "mode": "NORMAL", "plain": "WALTER köpte bitcoin för 100 kr."}]
        for j in (old, manual, []):
            self.assertNotIn("Walter köpte", wn.text_for(self.state(j), "kvall", "22:05", today=TODAY))


if __name__ == "__main__":
    unittest.main()
