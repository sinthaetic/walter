"""Sätt in pengar (insättning): samma köp som månadssparandet, CLI:t för ägaren (insattning.bat) och paritet
med js/engine.js (tests/fixtures/engine-cases.json -> deposit). Bara temp-filer – rör aldrig data/."""
import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fetcher"))
sys.path.insert(0, str(ROOT / "tests"))
import walter_deploy as wd  # noqa: E402
import walter_fetch as wf  # noqa: E402
import walter_paper as wp  # noqa: E402
import walter_vault as v  # noqa: E402
from test_autopilot import FRIDAY, RULES, pf, state  # noqa: E402

KEY = "TEST-KOD"
FIX = json.loads((ROOT / "tests" / "fixtures" / "engine-cases.json").read_text(encoding="utf-8"))


def on_weights():
    return pf(25000, {"BTC": 35000, "ETH": 20000, "GOLD": 20000})


def raw_of(p, rules=RULES):
    return {"portfolio": copy.deepcopy(p), "rules": copy.deepcopy(rules), "mode": "NORMAL", "updatedAt": "2026-10-22",
            "journal": [{"date": "2026-10-22", "plain": "gammal"}], "k4": []}


class DepositTest(unittest.TestCase):
    def test_parse_amount(self):
        self.assertEqual(wp.parse_amount("500"), 500)
        self.assertEqual(wp.parse_amount(" 1 000 kr "), 1000)
        self.assertEqual(wp.parse_amount("100"), 100)
        self.assertEqual(wp.parse_amount("100 000 000"), 100000000)
        for bad in ("99", "100 000 001", "", "abc", "5,5", "-500", "1e3", "500.0", None, 500):
            self.assertIsNone(wp.parse_amount(bad), bad)

    def test_buys_toward_weights_with_new_cash_only(self):
        prop = wp.propose_deposit(state(on_weights()), FRIDAY, 500)
        self.assertEqual([(t["asset"], t["side"], t["sek"]) for t in prop["trades"]],
                         [("BTC", "köp", 175.0), ("ETH", "köp", 100.0), ("GOLD", "köp", 100.0)])
        raw = raw_of(on_weights())
        entry = wp.apply_deposit(raw, prop, FRIDAY)
        self.assertEqual(entry["plain"],
                         "Insättning: 500 kr in. Jag köpte bitcoin för 175 kr, ethereum för 100 kr och guld för 100 kr.")
        self.assertEqual(entry["deposit"], {"sek": 500.0})
        self.assertIsNone(entry["red"])
        self.assertEqual(raw["mode"], "NORMAL")  # läget ändras aldrig av en insättning
        hist = raw["portfolio"]["history"]
        self.assertEqual(hist[0], {"date": FRIDAY, "value": 100500.0, "cash": 25500.0, "flow": 500.0, "note": "insättning"})
        self.assertEqual(hist[1]["note"], "köp")
        self.assertEqual(raw["portfolio"]["holdings"]["CASH"], 25125.0)
        self.assertEqual(raw["journal"][0], entry)
        self.assertNotIn("check", entry)  # söndagskollen räknas inte som gjord

    def test_never_sells_and_min_cash_holds(self):
        heavy = pf(25000, {"BTC": 50000, "ETH": 20000, "GOLD": 5000})  # BTC över sin andel
        prop = wp.propose_deposit(state(heavy), FRIDAY, 10000)
        self.assertTrue(all(t["side"] == "köp" for t in prop["trades"]))
        self.assertNotIn("BTC", [t["asset"] for t in prop["trades"]])
        cash_after = 25000 + 10000 - sum(t["sek"] for t in prop["trades"])
        self.assertGreaterEqual(cash_after + 1e-6, RULES["minCash"] * 110000)

    def test_min_trade_relative_to_deposit_and_missing_price(self):
        prop = wp.propose_deposit(state(on_weights(), gold=False), FRIDAY, 1000)
        self.assertEqual([t["asset"] for t in prop["trades"]], ["BTC", "ETH"])
        self.assertEqual(prop["deposit"]["waiting"], ["GOLD"])
        self.assertIn("Jag väntar på pris för guld, så den delen ligger som kontanter.", prop["plain"])

    def test_lamps_strategy_cash_only(self):
        rules = dict(RULES, strategy="lamps")
        prop = wp.propose_deposit(state(on_weights(), rules=rules), FRIDAY, 500)
        self.assertEqual(prop["trades"], [])
        raw = raw_of(on_weights(), rules)
        entry = wp.apply_deposit(raw, prop, FRIDAY)
        self.assertEqual(raw["portfolio"]["holdings"]["CASH"], 25500.0)
        self.assertTrue(entry["plain"].startswith("Insättning: 500 kr in. Med lamp-strategin köper jag inte direkt"))

    def test_flows_excluded_from_sharpe_and_levels(self):
        # Sharpe: insättningen räknas bort ur dagens avkastning
        s = wp.sharpe({"2026-10-01": 100, "2026-10-02": 100, "2026-10-03": 600, "2026-10-04": 600},
                      {"2026-10-03": 500}, "2026-09-01", today="2026-10-05")
        self.assertIsNone(s["value"])  # inga svängningar alls när insättningen räknas bort (sd = 0)


class DepositCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.state, self.enc = d / "state.json", d / "state.enc"
        self.state.write_text(json.dumps(raw_of(on_weights())), encoding="utf-8")
        self.owner = d / "owner-cache.json"
        self.owner.write_text(json.dumps({"daily": {FRIDAY: 99999.0, "2026-10-22": 100000.0}}), encoding="utf-8")
        self.built, self.synced, self.pushed = [], [], []
        built = lambda w: dict(state(on_weights()), fetchedAt="2026-10-23T08:13:00+02:00")  # noqa: E731
        # push_source är ALLTID mockad här: ett test får aldrig committa eller pusha på riktigt
        self.patches = [patch.object(wd, "push_source", lambda m=None: self.pushed.append(m) or True),
                        patch.object(wf, "OWNER_CACHE", self.owner),
                        patch.object(wf, "BASE", self.state), patch.object(v, "ENC", self.enc),
                        patch.object(v, "STATE", self.state), patch.object(v, "owner_key", lambda: KEY),
                        patch.object(v, "sync_from_repo", lambda: self.synced.append(1) or "same"),
                        patch.object(wp, "rebuild", built),
                        patch.object(wf, "write_js", lambda s: self.built.append(s))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def run_cli(self, text):
        out = io.StringIO()
        with redirect_stdout(out):
            entry = wp.deposit_cli(wf, text, today=FRIDAY)
        return entry, out.getvalue()

    def test_writes_flow_journal_buys_and_locks(self):
        entry, out = self.run_cli("500")
        self.assertEqual(self.synced, [1])  # Walters affärer hämtades först
        raw = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(raw["journal"][0]["plain"], entry["plain"])
        self.assertTrue(entry["plain"].startswith("Insättning: 500 kr in. Jag köpte bitcoin för 175 kr"))
        flows = [h for h in raw["portfolio"]["history"] if h.get("note") == wp.DEPOSIT_NOTE]
        self.assertEqual([(h["date"], h["flow"]) for h in flows], [(FRIDAY, 500.0)])
        self.assertAlmostEqual(raw["portfolio"]["positions"]["BTC"]["costSek"], 35175.0)
        self.assertEqual(v.decrypt(json.loads(self.enc.read_text(encoding="utf-8")), KEY), raw)
        self.assertEqual(len(self.built), 1)
        self.assertIn("Klart.", out)
        # Pushad direkt, och dagens värde i owner-cache är värdet efter insättningen (Sharpe)
        self.assertEqual(self.pushed, ["Insättning 500 kr 2026-10-23"])
        self.assertIn("pushad till main", out)
        daily = json.loads(self.owner.read_text(encoding="utf-8"))["daily"]
        self.assertEqual(daily, {FRIDAY: 100000, "2026-10-22": 100000.0})

    def test_push_failure_said_clearly(self):
        with patch.object(wd, "push_source", lambda m=None: False):
            entry, out = self.run_cli("500")
        self.assertIsNotNone(entry)  # insättningen står lokalt och i state.enc
        self.assertIn("state.enc kom INTE upp till main", out)

    def test_minimum_enforced_nothing_written(self):
        before = self.state.read_text(encoding="utf-8")
        for bad in ("99", "abc", "0", "100 000 001"):
            entry, out = self.run_cli(bad)
            self.assertIsNone(entry)
            self.assertIn("minst 100 kr", out)
        self.assertEqual(self.state.read_text(encoding="utf-8"), before)
        self.assertFalse(self.enc.exists())
        self.assertEqual(self.synced, [])
        self.assertEqual(self.pushed, [])

    def test_stale_prices_or_unclear_sync_nothing_written(self):
        before = self.state.read_text(encoding="utf-8")
        with patch.object(wp, "rebuild", lambda w: dict(state(on_weights()), fetchedAt="2026-10-10T08:00:00Z")):
            entry, out = self.run_cli("500")
        self.assertIsNone(entry)
        self.assertIn("kör hamta.bat först", out)
        with patch.object(v, "sync_from_repo", lambda: "local"):
            self.assertIsNone(self.run_cli("500")[0])
        with patch.object(v, "owner_key", lambda: None):
            self.assertIsNone(self.run_cli("500")[0])
        self.assertEqual(self.state.read_text(encoding="utf-8"), before)
        self.assertFalse(self.enc.exists())

    def test_lamps_strategy_cash_only(self):
        lamps = dict(RULES, strategy="lamps")
        with patch.object(wp, "rebuild", lambda w: dict(state(on_weights(), rules=lamps), fetchedAt="2026-10-23")):
            entry, _ = self.run_cli("1 000 kr")
        raw = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(raw["portfolio"]["holdings"]["CASH"], 26000.0)
        self.assertEqual(raw["portfolio"]["positions"]["BTC"]["costSek"], 35000)
        self.assertIn("lamp-strategin", entry["plain"])


class PushSourceTest(unittest.TestCase):
    """walter_deploy.push_source med mockad git: bara main, bara data/state.enc, säger till när pushen faller."""
    def run_push(self, branch="main", push_rc=0, staged=True):
        calls = []

        def run(cmd, cwd=None, **k):
            calls.append(cmd)
            rc = 1 if cmd[1:3] == ["diff", "--cached"] and staged else push_rc if cmd[1] == "push" else 0
            return type("R", (), {"returncode": rc})()
        with patch.object(wd.subprocess, "run", run), patch.object(wd, "current_branch", lambda: branch), \
                patch.object(wd, "warn") as warn, patch.dict("os.environ", {"GITHUB_ACTIONS": ""}):
            ok = wd.push_source("Insättning 500 kr 2026-10-23")
        return ok, calls, warn

    def test_commits_only_state_enc_and_pushes_main(self):
        ok, calls, _ = self.run_push()
        self.assertTrue(ok)
        self.assertIn(["git", "commit", "-q", "-m", "Insättning 500 kr 2026-10-23", "--", "data/state.enc"], calls)
        self.assertEqual(calls[-1], ["git", "push", "-q", "origin", "HEAD:main"])

    def test_push_failure_returns_false(self):
        ok, _, warn = self.run_push(push_rc=1)
        self.assertFalse(ok)
        self.assertIn("Kunde inte pusha", warn.call_args[0][0])

    def test_not_main_never_pushes(self):
        ok, calls, _ = self.run_push(branch="feature")
        self.assertFalse(ok)
        self.assertEqual(calls, [])


class DeploySyncGuardTest(unittest.TestCase):
    def test_stops_on_pullfail_or_local(self):
        for res, word in (("pullfail", "kunde inte hämta main"), ("local", "nyare än Walters låsta")):
            with patch.object(wd, "load_env"), patch.object(v, "sync_from_repo", lambda r=res: r), \
                    patch.object(wd, "build_state") as build, patch.object(wd, "push_source") as push, \
                    patch.object(wd, "lock_if_changed") as lock:
                with self.assertRaises(SystemExit) as cm:
                    wd.main()
            self.assertIn(word, str(cm.exception.code))
            build.assert_not_called(); push.assert_not_called(); lock.assert_not_called()


class FixtureTest(unittest.TestCase):
    def test_fixture_has_deposit_cases(self):
        names = [c["name"] for c in FIX["deposit"]["cases"]]
        for n in ("dep_on_weights", "dep_heavy_btc", "dep_gold_missing", "dep_lamps", "dep_no_gold_on_exchange"):
            self.assertIn(n, names)


if __name__ == "__main__":
    unittest.main()
