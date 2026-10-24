"""Månadssparande (savings) och målläge (goal) i autopiloten. Samma regler som js/engine.js (paritet via
tests/fixtures/engine-cases.json -> savingsGoal)."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fetcher"))
sys.path.insert(0, str(ROOT / "tests"))
import walter_paper as wp  # noqa: E402
from test_autopilot import FRIDAY, RULES, SUNDAY, pf, state  # noqa: E402

FIX = json.loads((ROOT / "tests" / "fixtures" / "engine-cases.json").read_text(encoding="utf-8"))["savingsGoal"]


def on_weights(first="2026-10-01"):
    return pf(25000, {"BTC": 35000, "ETH": 20000, "GOLD": 20000}, first=first)


def sv(day=23, since="2026-10-01", amt=1000):
    return {"monthlySek": amt, "day": day, "since": since}


def with_(p, savings=None, goal=None, journal=None):
    s = state(p)
    s["journal"] = journal if journal is not None else [{"date": "2026-10-19", "check": True}]
    if savings is not None:
        s["savings"] = savings
    if goal is not None:
        s["goal"] = goal
    return s


class SavingsTest(unittest.TestCase):
    def test_deposit_day_buys_with_new_cash_only(self):
        prop = wp.propose(with_(on_weights(), sv(23)), today=FRIDAY)
        self.assertEqual([(t["asset"], t["side"], t["sek"]) for t in prop["trades"]],
                         [("BTC", "köp", 350.0), ("ETH", "köp", 200.0), ("GOLD", "köp", 200.0)])
        self.assertTrue(prop["needsApproval"])
        self.assertFalse(prop["decisionDay"])  # en fredag: bara sparandet, ingen ombalansering
        self.assertTrue(prop["plain"].startswith(
            "Månadssparande: 1 000 kr in. Jag köper bitcoin för 350 kr, ethereum för 200 kr och guld för 200 kr."))

    def test_apply_writes_flow_row_and_journal(self):
        p = on_weights()
        s = with_(p, sv(23))
        raw = {"portfolio": copy.deepcopy(p), "rules": RULES, "mode": "NORMAL", "updatedAt": FRIDAY,
               "journal": [], "k4": [], "savings": sv(23)}
        entry = wp.apply(raw, wp.propose(s, today=FRIDAY), FRIDAY)
        rows = [h for h in raw["portfolio"]["history"] if h.get("note") == wp.SAVINGS_NOTE]
        self.assertEqual(rows, [{"date": FRIDAY, "value": 101000.0, "cash": 26000.0, "flow": 1000.0,
                                 "note": "månadssparande", "month": "2026-10"}])
        self.assertTrue(entry["plain"].startswith("Månadssparande: 1 000 kr in. Jag köpte bitcoin för 350 kr"))
        self.assertEqual(entry["savings"], {"sek": 1000.0, "months": ["2026-10"]})
        self.assertEqual(raw["portfolio"]["holdings"]["CASH"], 25250.0)
        # Samma dag igen: månaden är gjord, inget nytt
        again = wp.propose(dict(s, portfolio=raw["portfolio"], journal=raw["journal"]), today=FRIDAY)
        self.assertIsNone(again["savings"])

    def test_missed_day_caught_up_next_day(self):
        prop = wp.propose(with_(on_weights(), sv(22)), today=FRIDAY)
        self.assertEqual(prop["savings"]["months"], ["2026-10"])

    def test_two_months_missed_two_deposits(self):
        prop = wp.propose(with_(on_weights(), sv(20, "2026-09-01")), today=FRIDAY)
        self.assertEqual(prop["savings"]["months"], ["2026-09", "2026-10"])
        self.assertEqual(prop["savings"]["sek"], 2000)
        self.assertIn("Månadssparande: 2 000 kr in (sep och okt).", prop["plain"])
        raw = {"portfolio": copy.deepcopy(on_weights()), "rules": RULES, "mode": "NORMAL", "updatedAt": FRIDAY,
               "journal": [], "k4": []}
        wp.apply(raw, prop, FRIDAY)
        self.assertEqual([h["month"] for h in raw["portfolio"]["history"] if h.get("month")], ["2026-09", "2026-10"])

    def test_amount_zero_is_nothing(self):
        prop = wp.propose(with_(on_weights(), sv(23, amt=0)), today=FRIDAY)
        self.assertIsNone(prop["savings"])
        self.assertEqual(prop["trades"], [])
        self.assertFalse(prop["needsApproval"])

    def test_not_before_day_or_since(self):
        self.assertEqual(wp.savings_due(sv(24), [], FRIDAY), [])            # 24 okt har inte kommit
        self.assertEqual(wp.savings_due(sv(10, "2026-10-15"), [], FRIDAY), [])  # 10 okt är före since
        self.assertEqual(wp.savings_due({"monthlySek": 1000, "day": 20}, [], FRIDAY), ["2026-10"])  # utan since: bara denna månad
        self.assertEqual(wp.savings_due(sv(29), [], FRIDAY), [])            # dag 29 är ogiltig
        self.assertEqual(wp.savings_due({"monthlySek": 500, "day": 25.0, "since": "2026-10-01"}, [], "2026-10-25"),
                         ["2026-10"])

    def test_min_cash_floor(self):
        # Kontanterna under golvet: insättningen fyller golvet först, inget köps
        p = pf(24000, {"BTC": 36000, "ETH": 20000, "GOLD": 20000})
        prop = wp.propose(with_(p, sv(23)), today=FRIDAY)
        self.assertEqual(prop["trades"], [])
        self.assertIn("Pengarna ligger som kontanter tills vidare.", prop["plain"])

    def test_sunday_savings_then_rebalance(self):
        p = pf(25000, {"BTC": 50000, "ETH": 15000, "GOLD": 10000})
        prop = wp.propose(with_(p, sv(25), journal=[]), today=SUNDAY)
        sides = [(t["asset"], t["side"]) for t in prop["trades"]]
        self.assertEqual(sides[:2], [("ETH", "köp"), ("GOLD", "köp")])  # sparandet först: det som ligger under
        self.assertIn(("BTC", "sälj"), sides)
        self.assertTrue(prop["decisionDay"])


class GlideTest(unittest.TestCase):
    def test_factor(self):
        self.assertEqual(wp.glide_factor(None, SUNDAY), 1.0)
        self.assertEqual(wp.glide_factor({"date": "2029-01-01"}, SUNDAY), 1.0)       # mer än 24 månader
        self.assertAlmostEqual(wp.glide_factor({"date": "2027-10-25"}, SUNDAY), 0.5, places=2)  # 12 månader
        self.assertEqual(wp.glide_factor({"date": SUNDAY}, SUNDAY), 0.0)            # på dagen
        self.assertEqual(wp.glide_factor({"date": "2026-01-01"}, SUNDAY), 0.0)      # efter
        self.assertEqual(wp.glide_factor({"date": "2027-02-30"}, SUNDAY), 1.0)      # ogiltigt datum = inget mål

    def test_weights_scaled_and_all_cash_at_date(self):
        half = wp.propose(with_(on_weights(), goal={"date": "2027-10-25"}, journal=[]), today=SUNDAY)
        self.assertAlmostEqual(half["weights"]["BTC"], 0.35 * half["glide"])
        self.assertEqual({t["side"] for t in half["trades"]}, {"sälj"})
        # Små rester inom bandet säljs också när datumet är nått
        p = pf(97000, {"BTC": 3000})
        done = wp.propose(with_(p, goal={"date": SUNDAY}, journal=[]), today=SUNDAY)
        self.assertEqual([(t["asset"], t["side"]) for t in done["trades"]], [("BTC", "sälj")])
        # Utan mål: en rest på 3 % ligger kvar (inom bandet) – vanliga regler
        self.assertEqual([t for t in wp.propose(with_(copy.deepcopy(p), journal=[]), today=SUNDAY)["trades"]
                          if t["side"] == "sälj"], [])

    def test_no_extra_trades_on_weekday(self):
        prop = wp.propose(with_(on_weights(), goal={"date": "2027-04-23"}), today=FRIDAY)
        self.assertEqual(prop["trades"], [])  # glidningen sker bara på söndagens koll


class FixtureTest(unittest.TestCase):
    def test_fixture_has_parity_cases(self):
        """JS-paritetstesterna (tests/js/engine.test.js) läser de här fallen. Kör make_fixtures.py när motorn ändras."""
        names = {c["name"] for c in FIX["cases"]}
        for need in ("sv_deposit_day", "sv_missed_day_next_day", "sv_two_months_missed", "sv_amount_zero",
                     "gl_far_full_weights", "gl_12_months_half", "gl_goal_date_all_cash"):
            self.assertIn(need, names)
        c = next(c for c in FIX["cases"] if c["name"] == "gl_12_months_half")
        self.assertEqual(c["expect"]["glide"], 0.4997)

if __name__ == "__main__":
    unittest.main()
