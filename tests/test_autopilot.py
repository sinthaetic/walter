"""Autopiloten (rules.strategy = "autopilot"): fasta andelar 35/20/20, koll på söndagar, 5 %-band.
Lamporna räknas och visas men ändrar inga affärer. Den gamla lamp-strategin finns kvar bakom "lamps"."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fetcher"))
import walter_paper as wp  # noqa: E402

SUNDAY, FRIDAY = "2026-10-25", "2026-10-23"
RULES = {"strategy": "autopilot", "decision": {"weekday": "söndag", "bandPp": 5},
         "parkeraAtRed": 7, "wakeAtRed": 5, "modes": {"buyAtRed": 2, "buyLittleAtRed": 4, "littleShare": 0.5},
         "paper": {"minTradePct": 2}, "maxInvested": 0.75, "minCash": 0.25,
         "caps": {"BTC": 0.35, "ETH": 0.2, "GOLD": 0.2}, "ethMaxRed": 4,
         "gold": {"vixAbove": 20, "spxBelowMa": True, "allowedWhenParked": True},
         "withdrawalFees": {"takerPct": 0.4, "slippagePct": 0.2, "sepaEur": 1, "fxPct": 1}}
PX = {"BTC": 1000000.0, "ETH": 40000.0, "GOLD": 30000.0}


def market(gold=True):
    return {"usdsek": {"value": 1}, "btc": {"value": PX["BTC"]}, "ethBtc": {"value": PX["ETH"] / PX["BTC"]},
            "gold": {"value": PX["GOLD"] if gold else None}, "vix": {"value": 15}, "spx": {"belowMa": False},
            "ethBtcAbove30dMa": False}


def pf(cash, sek=None, first="2026-10-01"):
    """Portfölj med kontanter + innehav i SEK {tillgång: kronor} till PX."""
    pos, hold = {}, {"BTC": 0, "ETH": 0, "GOLD": 0, "CASH": cash}
    for a, s in (sek or {}).items():
        pos[a] = {"units": s / PX[a], "costSek": s, "since": "2026-10-01"}
        hold[a] = s
    v = sum(hold.values())
    return {"start": 100000, "value": v, "peak": v, "holdings": hold, "positions": pos, "firstTrade": first,
            "history": []}


def state(p, red=3, mode="NORMAL", rules=RULES, gold=True, source="data"):
    return {"rules": copy.deepcopy(rules), "market": market(gold), "portfolio": p, "mode": mode, "level": 1,
            "lampScore": {"source": source, "red": red}}


class AutopilotTest(unittest.TestCase):
    def test_sunday_within_band_does_nothing(self):
        p = pf(26000, {"BTC": 38000, "ETH": 18000, "GOLD": 18000})
        prop = wp.propose(state(p), today=SUNDAY)
        self.assertEqual(prop["trades"], [])
        self.assertTrue(prop["ready"])
        self.assertEqual(prop["strategy"], "autopilot")
        self.assertIn("Söndag: allt ligger inom marginalen. Jag rör ingenting.", prop["plain"])
        self.assertIn("Nästa koll söndag 1 nov.", prop["plain"])
        self.assertEqual(prop["nextCheck"], "2026-11-01")

    def test_sunday_outside_band_sells_back_to_weight(self):
        p = pf(25000, {"BTC": 41000, "ETH": 17000, "GOLD": 17000})
        prop = wp.propose(state(p), today=SUNDAY)
        self.assertEqual([(t["asset"], t["side"]) for t in prop["trades"]], [("BTC", "sälj")])
        self.assertAlmostEqual(prop["trades"][0]["sek"], 6000, places=2)
        self.assertIn("Söndag: bitcoin har vuxit till 41 % – jag säljer för 6 000 kr, tillbaka till 35 %.",
                      prop["plain"])

    def test_sells_first_then_buys(self):
        p = pf(25000, {"BTC": 50000, "ETH": 15000, "GOLD": 10000})
        prop = wp.propose(state(p), today=SUNDAY)
        self.assertEqual([(t["asset"], t["side"]) for t in prop["trades"]], [("BTC", "sälj"), ("GOLD", "köp")])
        # ETH 15 % ligger precis på bandet (inte mer än 5) och rörs inte; guld 10 % köps tillbaka till 20 %
        self.assertAlmostEqual(prop["trades"][1]["sek"], 10000, places=2)

    def test_weekday_waits_for_sunday(self):
        p = pf(25000, {"BTC": 50000, "ETH": 15000, "GOLD": 10000}, first="2026-10-19")
        prop = wp.propose(state(p), today=FRIDAY)
        self.assertEqual(prop["trades"], [])
        self.assertIn("Nästa koll söndag 25 okt.", prop["plain"])
        self.assertFalse(prop["decisionDay"])

    def test_first_trade_any_day(self):
        prop = wp.propose(state(pf(100000, first=None)), today=FRIDAY)
        self.assertEqual([(t["asset"], t["sek"]) for t in prop["trades"]],
                         [("BTC", 35000.0), ("ETH", 20000.0), ("GOLD", 20000.0)])
        self.assertTrue(prop["plain"].startswith("Första dagen: jag köper bitcoin för 35 000 kr (35 %), ethereum för 20 000 kr (20 %) och guld för 20 000 kr (20 %). Nästa koll söndag 25 okt."))

    def test_missing_asset_stays_cash(self):
        prop = wp.propose(state(pf(100000, first=None)), today=FRIDAY, assets={"BTC": True, "ETH": True})
        self.assertEqual([t["asset"] for t in prop["trades"]], ["BTC", "ETH"])
        self.assertEqual(prop["missing"], ["GOLD"])
        self.assertIn("Guld finns inte på din börs, så den delen ligger kvar som kontanter.", prop["plain"])

    def test_missing_price_waits_for_that_asset(self):
        prop = wp.propose(state(pf(100000, first=None), gold=False), today=FRIDAY)
        self.assertEqual([t["asset"] for t in prop["trades"]], ["BTC", "ETH"])
        self.assertEqual(prop["waiting"], ["GOLD"])
        self.assertIn("Jag väntar på pris för guld.", prop["plain"])

    def test_lamps_do_not_change_trades(self):
        p = pf(100000, first=None)
        calm = wp.propose(state(copy.deepcopy(p), red=0, mode="OFFENSIV"), today=FRIDAY)
        storm = wp.propose(state(copy.deepcopy(p), red=9, mode="OFFENSIV"), today=FRIDAY)
        self.assertEqual(calm["trades"], storm["trades"])
        self.assertEqual(storm["mode"], "PARKERA")  # läget räknas fortfarande (väderrapporten)

    def test_lamps_not_ready_still_trades(self):
        prop = wp.propose(state(pf(100000, first=None), source="journal"), today=FRIDAY)
        self.assertTrue(prop["ready"])
        self.assertEqual(len(prop["trades"]), 3)
        self.assertEqual(prop["mode"], "NORMAL")
        self.assertIsNone(prop["red"])

    def test_default_strategy_is_autopilot(self):
        rules = {k: v for k, v in RULES.items() if k not in ("strategy", "decision")}
        prop = wp.propose(state(pf(100000, first=None), rules=rules), today=FRIDAY)
        self.assertEqual(prop["strategy"], "autopilot")

    def test_lamps_strategy_kept(self):
        rules = dict(RULES, strategy="lamps")
        prop = wp.propose(state(pf(100000, first=None), red=1, rules=rules), today=FRIDAY)
        self.assertEqual(prop["mode"], "OFFENSIV")
        self.assertEqual([t["asset"] for t in prop["trades"]], ["BTC"])  # Level 1: bara bitcoin

    def test_apply_writes_journal(self):
        p = pf(100000, first=None)
        raw = {"portfolio": copy.deepcopy(p), "rules": RULES, "mode": "NORMAL", "updatedAt": FRIDAY,
               "journal": [], "k4": []}
        prop = wp.propose(state(p), today=FRIDAY)
        entry = wp.apply(raw, prop, FRIDAY)
        self.assertTrue(entry["plain"].startswith("WALTER köpte bitcoin för 35 000 kr"))
        self.assertIn("Marknaden är blandad (3 av 10 varningar)", entry["plain"])
        self.assertEqual(raw["portfolio"]["firstTrade"], FRIDAY)
        self.assertEqual(raw["portfolio"]["holdings"]["CASH"], 25000.0)
        self.assertEqual(raw["mode"], "NORMAL")

    def heavy(self):
        return pf(25000, {"BTC": 50000, "ETH": 15000, "GOLD": 10000})

    def test_missed_sunday_checks_first_day_after(self):
        # Senaste koll 11 okt, söndag 18 okt missades -> fredag 23 okt gör söndagens koll
        s = state(self.heavy())
        s["journal"] = [{"date": "2026-10-20", "auto": True, "mode": "NORMAL"}, {"date": "2026-10-11", "check": True}]
        prop = wp.propose(s, today=FRIDAY)
        self.assertTrue(prop["decisionDay"])
        self.assertEqual([t["side"] for t in prop["trades"]], ["sälj", "köp"])
        self.assertTrue(prop["plain"].startswith("Fredag (söndagens koll): bitcoin har vuxit till 50 %"))

    def test_missed_sunday_only_once(self):
        s = state(self.heavy())
        s["journal"] = [{"date": "2026-10-21", "check": True}]  # koll gjord onsdag efter söndag 18 okt
        prop = wp.propose(s, today=FRIDAY)
        self.assertFalse(prop["decisionDay"])
        self.assertEqual(prop["trades"], [])

    def test_checked_today_not_again(self):
        s = state(self.heavy())
        s["journal"] = [{"date": SUNDAY, "check": True}]
        prop = wp.propose(s, today=SUNDAY)
        self.assertFalse(prop["decisionDay"])
        self.assertFalse(prop["needsApproval"])
        self.assertEqual(prop["plain"], "Dagens koll är gjord. Nästa koll söndag 1 nov.")

    def test_check_without_trades_is_journaled(self):
        p = pf(26000, {"BTC": 38000, "ETH": 18000, "GOLD": 18000})
        prop = wp.propose(state(p, mode="NORMAL"), today=SUNDAY)
        self.assertTrue(prop["needsApproval"])  # Actionen skriver kollen, så att en missad söndag märks
        raw = {"portfolio": copy.deepcopy(p), "rules": RULES, "mode": "NORMAL", "updatedAt": SUNDAY,
               "journal": [], "k4": []}
        entry = wp.apply(raw, prop, SUNDAY)
        self.assertTrue(entry["check"])
        self.assertTrue(entry["plain"].startswith("Söndag: allt ligger inom marginalen."))
        self.assertEqual(wp.last_check(raw["journal"], raw["portfolio"]), SUNDAY)

    def test_waiting_price_is_not_a_finished_check(self):
        prop = wp.propose(state(pf(100000, first="2026-10-19"), gold=False), today=SUNDAY)
        self.assertTrue(prop["decisionDay"])
        self.assertFalse(prop["check"])  # guldet väntar -> kollen görs om nästa dag

    def test_price_outage_catch_up_is_quiet(self):
        # Missad söndag + guldpris saknas + inget annat att göra: ingen journalpost, försök igen i morgon
        p = pf(25000, {"BTC": 35000, "ETH": 20000, "GOLD": 10000})
        s = state(p, gold=False)
        s["journal"] = [{"date": "2026-10-11", "check": True}]
        prop = wp.propose(s, today=FRIDAY)
        self.assertTrue(prop["decisionDay"])
        self.assertEqual(prop["trades"], [])
        self.assertFalse(prop["needsApproval"])
        self.assertEqual(prop["plain"], "Fredag (söndagens koll): jag väntar på pris för guld. Jag försöker igen i morgon.")
        # Själva söndagen skrivs kollen ändå (en gång)
        s2 = state(copy.deepcopy(p), gold=False)
        s2["portfolio"]["firstTrade"] = "2026-10-19"
        self.assertTrue(wp.propose(s2, today=SUNDAY)["needsApproval"])

    def test_next_check(self):
        self.assertEqual(wp.next_check("2026-10-25", RULES), "2026-11-01")
        self.assertEqual(wp.next_check("2026-10-24", RULES), "2026-10-25")


if __name__ == "__main__":
    unittest.main()
