"""Historiktestets avgifter, skatt och dag-för-dag-sim (backtest/costs.py, backtest/sim.py). Ingen nätverkstrafik,
bara syntetisk data. Lamporna byts mot ett manus (lamps.py testas för sig i test_backtest_lamps.py)."""
import copy
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fetcher"))
from backtest import lamps as bl
from backtest import sim
from backtest.costs import Exchange, TaxBook
import walter_paper as wp

FREE = Exchange("gratis", 0, 0, "SEK", 0, 0)
RED_ORDER = ["cpi", "sopr", "mvrv", "etf", "dxy", "us10y", "vix", "btcWeek", "btcTrend", "spx"]


def days(start, n):
    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n)]


def const(ds, v):
    return {d: v for d in ds}


def lamps_script(script):
    """Falsk lamps_on: script = {datum: antal röda av 10}; senaste datum <= dagen gäller. spx blir röd sist."""
    keys = sorted(script)

    def fake(day, series, thresholds, max_age=None):
        r = [script[k] for k in keys if k <= day][-1]
        return {i: ("red" if n < r else "green") for n, i in enumerate(RED_ORDER)}
    return fake


def run(strategy, script, series, ds, exchange=FREE, start_sek=100000):
    with mock.patch.object(bl, "lamps_on", lamps_script(script)):
        return sim.run(strategy, ds[0], ds[-1], exchange, start_sek=start_sek, series=series)


def walter_trades(res, asset=None, side=None):
    return [t for t in res.trades if t["why"] == "walter" and (asset is None or t["asset"] == asset)
            and (side is None or t["side"] == side)]


class Tax(unittest.TestCase):
    def test_average_cost_with_fees(self):
        b = TaxBook()
        b.buy("BTC", 1, 101)   # 100 + 1 kr avgift
        b.buy("BTC", 1, 202)
        self.assertAlmostEqual(b.avg_cost("BTC"), 151.5)
        r = b.sell("2020-05-01", "BTC", 1, 250 - 2.5)  # säljavgiften minskar priset
        self.assertAlmostEqual(r, 96.0)
        self.assertAlmostEqual(b.avg_cost("BTC"), 151.5)  # snittet ändras inte av en försäljning
        self.assertAlmostEqual(b.sell("2020-06-01", "BTC", 1, 100), -51.5)
        self.assertEqual(b.units["BTC"], 0)

    def test_70_percent_loss_rule_per_year(self):
        b = TaxBook()
        b.buy("BTC", 2, 2000)
        b.buy("GOLD", 1, 1000)
        b.sell("2020-03-01", "BTC", 1, 2000)   # +1000
        b.sell("2020-09-01", "GOLD", 1, 500)   # −500 (PAXG räknas som krypto)
        self.assertAlmostEqual(b.taxable(2020), 1000 - 0.7 * 500)
        self.assertAlmostEqual(b.tax(2020), 0.3 * 650)
        b.sell("2021-02-01", "BTC", 1, 400)    # −600, eget år: ingen kvittning mot 2020
        self.assertEqual(b.tax(2021), 0)
        self.assertAlmostEqual(b.tax(2020), 195)


class Sim(unittest.TestCase):
    def tax_scenario(self, buy_back):
        ds = days("2020-12-01", 36)  # .. 2021-01-05
        btc = {d: (100.0 if d < "2020-12-05" else 200.0) for d in ds}
        series = {"btc": btc, "usdsek": const(ds, 1.0)}
        rules = copy.deepcopy(sim.DEFAULT_RULES)
        rules["minCash"], rules["caps"]["BTC"] = 0, 1.0
        script = {ds[0]: 0, "2020-12-10": 3}
        if buy_back:
            script["2020-12-20"] = 0
        return run(sim.Strategy(rules=rules), script, series, ds)

    def test_tax_paid_next_year_from_cash(self):
        res = self.tax_scenario(buy_back=False)
        self.assertAlmostEqual(res.taxes[2020], 15000, delta=1)   # halva sålt med +50 000 vinst
        self.assertFalse([t for t in res.trades if t["why"] == "skatt"])
        self.assertAlmostEqual(res.taxes[2021], 15000, delta=1)   # slutförsäljningen
        self.assertAlmostEqual(res.final_sek, 170000, delta=1)
        self.assertEqual(res.daily["2020-12-31"] - res.daily["2021-01-01"], res.taxes[2020])

    def test_forced_sale_when_cash_is_short(self):
        res = self.tax_scenario(buy_back=True)
        forced = [t for t in res.trades if t["why"] == "skatt"]
        self.assertEqual([t["date"] for t in forced], ["2021-01-01"])
        self.assertAlmostEqual(forced[0]["sek"], 15000, delta=5)
        self.assertGreater(res.book.gains[2021], 0)  # tvångsförsäljningen beskattas 2021
        self.assertAlmostEqual(res.taxes[2020], 15000, delta=1)
        self.assertAlmostEqual(res.final_sek, 170000, delta=2)

    def test_fx_only_at_deposit_and_withdrawal(self):
        ds = days("2021-01-01", 20)
        series = {"btc": const(ds, 100.0), "usdsek": const(ds, 10.0), "eursek": const(ds, 11.0)}
        script = {d: (0 if i % 2 else 3) for i, d in enumerate(ds)}  # Köper / Köper lite varannan dag
        ex = Exchange("eur", 0, 0, "EUR", 1.0, 10)
        res = run(sim.Strategy(), script, series, ds, exchange=ex)
        self.assertGreater(res.n_trades, 10)
        self.assertAlmostEqual(res.final_sek, 100000 * 0.99 * 0.99 - 10, delta=0.5)
        self.assertAlmostEqual(res.fees_sek, 100000 - res.final_sek, delta=0.5)

    def test_executes_at_next_days_price(self):
        ds = days("2021-01-01", 5)
        series = {"btc": {d: (100.0 if d == ds[0] else 120.0) for d in ds}, "usdsek": const(ds, 10.0)}
        res = run(sim.Strategy(), {ds[0]: 0}, series, ds)
        t = res.trades[0]
        self.assertEqual((t["date"], t["side"], t["priceSek"]), (ds[1], "köp", 1200.0))

    def test_default_matches_walter_paper(self):
        ds = days("2021-03-01", 3)
        series = {"btc": const(ds, 50000.0), "usdsek": const(ds, 10.0)}
        ex = Exchange("safello", 0.8, 0.2, "SEK", 0, 0)
        res = run(sim.Strategy(), {ds[0]: 3}, series, ds, exchange=ex)

        rules = copy.deepcopy(sim.DEFAULT_RULES)
        rules["withdrawalFees"].update(takerPct=0.8, slippagePct=0.2)
        raw = {"rules": rules, "mode": "AVVAKTAR", "level": 1, "journal": [], "k4": [], "updatedAt": "",
               "portfolio": {"start": 100000, "value": 100000, "peak": 100000, "positions": {}, "history": [],
                             "holdings": {"BTC": 0, "ETH": 0, "GOLD": 0, "CASH": 100000}}}
        market = {"usdsek": {"value": 10.0}, "btc": {"value": 50000.0}, "ethBtc": {"value": None},
                  "gold": {"value": None}, "vix": {"value": None}, "spx": {"belowMa": False},
                  "ethBtcAbove30dMa": None}
        prop = wp.propose(dict(raw, market=market, lampScore={"source": "data", "red": 3}))
        self.assertEqual(prop["mode"], "NORMAL")
        keys = ("asset", "side", "units", "sek", "feeSek", "priceSek")
        mine = [{k: t[k] for k in keys} for t in walter_trades(res)]
        self.assertEqual(mine, [{k: t[k] for k in keys} for t in prop["trades"]])
        entry = wp.apply(raw, prop, ds[1])
        self.assertEqual(res.raw["journal"][-1]["facts"], entry["facts"])  # äldsta posten = dag 2

    def test_hysteresis(self):
        self.assertEqual(sim.hysteresis_mode(2, "NORMAL", sim.DEFAULT_RULES), "NORMAL")
        self.assertEqual(sim.hysteresis_mode(1, "NORMAL", sim.DEFAULT_RULES), "OFFENSIV")
        self.assertEqual(sim.hysteresis_mode(4, "AVVAKTAR", sim.DEFAULT_RULES), "AVVAKTAR")
        self.assertEqual(sim.hysteresis_mode(5, "OFFENSIV", sim.DEFAULT_RULES), "AVVAKTAR")  # oro: direkt
        self.assertEqual(sim.hysteresis_mode(6, "PARKERA", sim.DEFAULT_RULES), "PARKERA")
        ds = days("2021-01-01", 4)
        series = {"btc": const(ds, 100.0), "usdsek": const(ds, 1.0)}
        script = {ds[0]: 3, ds[1]: 2}
        self.assertEqual(run(sim.Strategy(), script, series, ds).modes[ds[1]], "OFFENSIV")
        self.assertEqual(run(sim.Strategy(hysteresis=True), script, series, ds).modes[ds[1]], "NORMAL")

    def test_band_pp(self):
        ds = days("2021-01-01", 6)
        series = {"btc": {d: (100.0 if d <= ds[1] else 115.0) for d in ds}, "usdsek": const(ds, 1.0)}
        base = run(sim.Strategy(), {ds[0]: 0}, series, ds)
        band = run(sim.Strategy(band_pp=5), {ds[0]: 0}, series, ds)
        self.assertEqual(len(walter_trades(base, "BTC", "sälj")), 1)  # 38 % mot målet 35 % -> trimmar
        self.assertEqual(len(walter_trades(band, "BTC", "sälj")), 0)
        self.assertEqual(len(walter_trades(band, "BTC", "köp")), 1)   # första köpet är större än bandet

    def test_no_partial_sells(self):
        ds = days("2021-01-01", 10)
        series = {"btc": const(ds, 100.0), "usdsek": const(ds, 1.0)}
        script = {ds[0]: 0, ds[3]: 3, ds[6]: 8}
        base = run(sim.Strategy(), script, series, ds)
        nps = run(sim.Strategy(no_partial_sells=True), script, series, ds)
        self.assertEqual(len(walter_trades(base, "BTC", "sälj")), 2)  # Köper lite: halva, Vilar: resten
        sells = walter_trades(nps, "BTC", "sälj")
        self.assertEqual([t["date"] for t in sells], [ds[7]])         # bara Vilar
        self.assertEqual(nps.raw["portfolio"]["positions"]["BTC"]["units"], 0)

    def gold_series(self, ds):
        return {"btc": const(ds, 100.0), "usdsek": const(ds, 1.0), "gold": const(ds, 2000.0),
                "vix": {d: (25.0 if d in (ds[1], ds[2]) else 15.0) for d in ds}}

    def test_gold_days(self):
        ds = days("2021-01-01", 8)
        base = run(sim.Strategy(no_levels=True), {ds[0]: 0}, self.gold_series(ds), ds)
        slow = run(sim.Strategy(no_levels=True, gold_days=3), {ds[0]: 0}, self.gold_series(ds), ds)
        self.assertEqual([(t["date"], t["side"]) for t in walter_trades(base, "GOLD")],
                         [(ds[2], "köp"), (ds[4], "sälj")])
        self.assertEqual(walter_trades(slow, "GOLD"), [])

    def test_no_gold(self):
        ds = days("2021-01-01", 8)
        res = run(sim.Strategy(no_levels=True, no_gold=True), {ds[0]: 0}, self.gold_series(ds), ds)
        self.assertEqual(walter_trades(res, "GOLD"), [])
        self.assertTrue(walter_trades(res, "BTC"))

    def test_no_levels(self):
        hist = days("2020-11-01", 70)
        ds = [d for d in hist if d >= "2021-01-01"]
        series = {"btc": const(hist, 100.0), "usdsek": const(hist, 1.0),
                  "eth": {d: 1.0 + i * 0.01 for i, d in enumerate(hist)}}  # ETH/BTC stiger: över 30d-snittet
        base = run(sim.Strategy(), {ds[0]: 0}, series, ds)
        free = run(sim.Strategy(no_levels=True), {ds[0]: 0}, series, ds)
        self.assertEqual(walter_trades(base, "ETH"), [])  # Level 1: ingen ETH
        self.assertEqual(walter_trades(free, "ETH", "köp")[0]["date"], ds[1])

    def test_benchmarks(self):
        ds = days("2021-01-01", 10)
        btc = {d: (100.0 if d < ds[-1] else 200.0) for d in ds}
        series = {"btc": btc, "usdsek": const(ds, 1.0)}
        ex = Exchange("x", 0.8, 0.2, "SEK", 0, 0)
        for share in (0.35, 0.75):
            res = sim.run(sim.hold_btc(share), ds[0], ds[-1], ex, series=series)
            f = 0.01
            buy = share * 100000
            proceeds = buy * (1 - f) * 2 * (1 - f)
            expect = 100000 - buy + proceeds - 0.3 * (proceeds - buy)
            self.assertAlmostEqual(res.final_sek, expect, delta=0.5)
            self.assertEqual(res.n_trades, 2)
            self.assertEqual(res.taxes, {2021: res.book.tax(2021)})


class Del3Model(unittest.TestCase):
    """Steg 10 del 3: avrundning, skattereduktion för förlustår, ärliga jämförelser."""

    def test_rounding(self):
        self.assertEqual([sim.red_count(2 / 8 * 10, r) for r in ("up", "nearest", "down")], [3, 3, 2])
        self.assertEqual([sim.red_count(2 / 7 * 10, r) for r in ("up", "nearest", "down")], [3, 3, 2])
        self.assertEqual([sim.red_count(1 / 7 * 10, r) for r in ("up", "nearest", "down")], [2, 1, 1])
        self.assertEqual(sim.red_count(3.0, "up"), 3)  # flyttalsmarginal: 3,0000001 räknas som 3
        self.assertEqual(sim.Strategy().rounding, "nearest")

    def test_rounding_in_sim(self):
        ds = days("2021-01-01", 4)
        series = {"btc": const(ds, 100.0), "usdsek": const(ds, 1.0)}

        def seven(day, series, thresholds, max_age=None):  # 1 röd av 7 lampor = 1,43 av 10
            return {i: (None if i in ("cpi", "sopr", "etf") else ("red" if i == "vix" else "green"))
                    for i in RED_ORDER}
        with mock.patch.object(bl, "lamps_on", seven):
            up = sim.run(sim.Strategy(rounding="up"), ds[0], ds[-1], FREE, series=series)
            near = sim.run(sim.Strategy(), ds[0], ds[-1], FREE, series=series)
        self.assertEqual(up.modes[ds[0]], "OFFENSIV")    # 2 -> Köper
        self.assertEqual(near.modes[ds[0]], "OFFENSIV")  # 1 -> Köper
        self.assertEqual(up.raw["journal"][-1]["red"], 2)
        self.assertEqual(near.raw["journal"][-1]["red"], 1)

    def test_tax_credit_math(self):
        b = TaxBook()
        b.buy("BTC", 1, 1000)
        b.sell("2022-05-01", "BTC", 1, 500)               # −500 -> underskott 0,7 × 500 = 350
        self.assertEqual(b.tax(2022), 0)
        self.assertAlmostEqual(b.credit(2022), 0.3 * 350)
        b.buy("BTC", 1, 400000)
        b.sell("2023-05-01", "BTC", 1, 100000)            # −300 000 -> underskott 210 000
        self.assertAlmostEqual(b.credit(2023), 0.3 * 100000 + 0.21 * 110000)
        self.assertEqual(b.credit(2024), 0)

    def loss_run(self, credit):
        ds = days("2021-12-01", 40)
        btc = {d: (100.0 if d < "2021-12-10" else 50.0) for d in ds}
        series = {"btc": btc, "usdsek": const(ds, 1.0)}
        rules = copy.deepcopy(sim.DEFAULT_RULES)
        rules["minCash"], rules["caps"]["BTC"] = 0, 1.0
        return run(sim.Strategy(rules=rules, loss_credit=credit), {ds[0]: 0, "2021-12-15": 8}, series, ds)

    def test_tax_credit_in_sim(self):
        on, off = self.loss_run(True), self.loss_run(False)
        self.assertAlmostEqual(on.credits[2021], 0.3 * 0.7 * 50000, delta=1)  # sålt för 50 000 under omkostnad
        self.assertEqual(off.credits, {})
        self.assertAlmostEqual(on.final_sek - off.final_sek, on.credit_sek, delta=0.01)
        self.assertAlmostEqual(off.final_sek, 50000, delta=1)

    def test_rebalanced_mix(self):
        ds = days("2021-01-01", 8)
        btc = {d: (100.0 if d <= ds[2] else 200.0) for d in ds}
        series = {"btc": btc, "usdsek": const(ds, 1.0)}
        res = sim.run(sim.mix({"BTC": 0.35}), ds[0], ds[-1], FREE, series=series)
        t = res.trades
        self.assertEqual([(x["date"], x["side"]) for x in t[:2]], [(ds[1], "köp"), (ds[4], "sälj")])
        # efter fördubbling: 70 000 BTC av 135 000 -> sälj ner till 35 % av 135 000
        self.assertAlmostEqual(t[1]["sek"], 70000 - 0.35 * 135000, delta=1)
        once = sim.run(sim.mix({"BTC": 0.35}, rebalance=False), ds[0], ds[-1], FREE, series=series)
        self.assertEqual(once.n_trades, 2)  # köp + slutförsäljning

    def test_mix_weekly_with_band(self):
        """Del 3b: fasta andelar med beslut på söndagar och 5 %-band."""
        ds = days("2021-01-04", 21)  # måndag; söndagar = ds[6], ds[13], ds[20]
        # BTC +20 % dag 2 (35 % -> ca 39 %, under bandet), +100 % dag 9 (långt över bandet)
        btc = {d: (100.0 if i < 2 else 120.0 if i < 9 else 240.0) for i, d in enumerate(ds)}
        series = {"btc": btc, "usdsek": const(ds, 1.0)}
        daily = sim.run(sim.mix({"BTC": 0.35}), ds[0], ds[-1], FREE, series=series)
        slow = sim.run(sim.mix({"BTC": 0.35}, cadence_days=7, band_pp=5), ds[0], ds[-1], FREE, series=series)
        dates = lambda r: [(t["date"], t["side"]) for t in r.trades if t["why"] == "walter"]  # noqa: E731
        self.assertEqual(dates(daily), [(ds[1], "köp"), (ds[3], "sälj"), (ds[10], "sälj")])
        # första köpet direkt, +20 % ligger inom bandet, sälj först dagen efter söndagen ds[13]
        self.assertEqual(dates(slow), [(ds[1], "köp"), (ds[14], "sälj")])

    def test_autopilot_uses_live_path_and_matches_mix(self):
        """Del 4: autopiloten i historiktestet går genom walter_paper.propose och gör samma affärer som den
        fasta veckomixen med 5 %-band."""
        ds = days("2021-01-04", 28)
        btc = {d: (100.0 if i < 2 else 120.0 if i < 9 else 240.0) for i, d in enumerate(ds)}
        series = {"btc": btc, "usdsek": const(ds, 1.0), "gold": const(ds, 10.0),
                  "eth": const(ds, 5.0)}
        w = {"BTC": 0.35, "ETH": 0.2, "GOLD": 0.2}
        calls = []
        real = wp.propose
        with mock.patch.object(wp, "propose", lambda *a, **k: calls.append(1) or real(*a, **k)):
            ap = sim.run(sim.autopilot(), ds[0], ds[-1], FREE, series=series)
        mx = sim.run(sim.mix(w, cadence_days=7, band_pp=5), ds[0], ds[-1], FREE, series=series)
        self.assertTrue(calls)
        key = lambda r: [(t["date"], t["asset"], t["side"], round(t["sek"], 2)) for t in r.trades]  # noqa: E731
        self.assertEqual(key(ap), key(mx))
        self.assertGreater(len([t for t in ap.trades if t["why"] == "walter"]), 3)
        self.assertAlmostEqual(ap.final_sek, mx.final_sek, places=2)

    def test_autopilot_monthly_savings_and_goal(self):
        """Månadssparande: en insättning per månad (dagen efter beslutet), köpt direkt. Målläge: allt kontant
        på målets datum. Allt via walter_paper.propose."""
        ds = days("2021-01-04", 70)
        series = {"btc": const(ds, 100.0), "usdsek": const(ds, 1.0), "gold": const(ds, 10.0), "eth": const(ds, 5.0)}
        st = sim.Strategy(name="spar", rules=copy.deepcopy(sim.AUTOPILOT_RULES), savings_sek=1000, savings_day=25)
        r = sim.run(st, ds[0], ds[-1], FREE, start_sek=10000, series=series)
        rows = [h for h in r.raw["portfolio"]["history"] if h.get("note") == wp.SAVINGS_NOTE]
        self.assertEqual([(h["date"], h["month"], h["flow"]) for h in rows],
                         [("2021-01-26", "2021-01", 1000), ("2021-02-26", "2021-02", 1000)])
        self.assertEqual(r.deposited_sek, 12000)
        self.assertAlmostEqual(r.final_sek, 12000, places=2)  # gratis börs, oförändrade priser
        self.assertTrue([t for t in r.trades if t["date"] == "2021-01-26" and t["side"] == "köp"])
        ds = days("2021-01-04", 800)
        series = {"btc": const(ds, 100.0), "usdsek": const(ds, 1.0), "gold": const(ds, 10.0), "eth": const(ds, 5.0)}
        g = sim.run(sim.Strategy(name="mål", rules=copy.deepcopy(sim.AUTOPILOT_RULES), goal_date=ds[760]),
                    ds[0], ds[790], FREE, series=series)
        walter = [t for t in g.trades if t["why"] == "walter"]
        self.assertEqual({t["side"] for t in walter if t["date"] < ds[2]}, {"köp"})      # full andel från start
        self.assertEqual({t["side"] for t in walter if t["date"] > ds[60]}, {"sälj"})    # sedan bara mot kontanter
        self.assertEqual([t for t in g.trades if t["why"] == "slut"], [])                 # allt kontant före slutet

    def test_buy_once_mix_waits_for_eth(self):
        ds = days("2021-01-01", 10)
        series = {"btc": const(ds, 100.0), "usdsek": const(ds, 1.0), "gold": const(ds, 10.0),
                  "eth": {d: 5.0 for d in ds[4:]}}
        res = sim.run(sim.mix({"BTC": 0.35, "ETH": 0.2, "GOLD": 0.2}, rebalance=False), ds[0], ds[-1], FREE,
                      series=series)
        buys = [(t["date"], t["asset"]) for t in res.trades if t["side"] == "köp"]
        self.assertEqual(buys, [(ds[1], "BTC"), (ds[1], "GOLD"), (ds[5], "ETH")])
        self.assertTrue(sim.mix({"BTC": 0.35}).name.startswith("Ombalanserad"))
        self.assertTrue(sim.hold_btc(0.35).name.startswith("Köp en gång"))


class Del3Variants(unittest.TestCase):
    """Steg 10 del 3: varianter mot fram-och-tillbaka-handel."""

    def setUp(self):
        self.ds = days("2021-01-04", 30)  # 2021-01-04 är en måndag
        self.series = {"btc": const(self.ds, 100.0), "usdsek": const(self.ds, 1.0)}

    def test_confirm(self):
        c = sim.Confirm(3, "A")
        self.assertEqual([c(x) for x in "BBABBB"], ["A", "A", "A", "A", "A", "B"])
        self.assertEqual(sim.Confirm(1, "A")("B"), "B")

    def test_confirm_days(self):
        ds = self.ds
        script = {ds[0]: 0, ds[5]: 3, ds[6]: 0, ds[10]: 3}  # en dags blink, sedan riktig ändring
        base = run(sim.Strategy(), script, self.series, ds)
        slow = run(sim.Strategy(confirm_days=3), script, self.series, ds)
        self.assertEqual(base.modes[ds[5]], "NORMAL")
        self.assertEqual(slow.modes[ds[0]], "AVVAKTAR")   # Köper först dag 3
        self.assertEqual(slow.modes[ds[2]], "OFFENSIV")
        self.assertEqual(slow.modes[ds[5]], "OFFENSIV")   # blinken ignoreras
        self.assertEqual(slow.modes[ds[11]], "OFFENSIV")
        self.assertEqual(slow.modes[ds[12]], "NORMAL")
        self.assertLess(len(walter_trades(slow)), len(walter_trades(base)))

    def test_smooth_days(self):
        ds = self.ds
        script = {ds[0]: 0, ds[5]: 6, ds[6]: 0}
        base = run(sim.Strategy(), script, self.series, ds)
        smooth = run(sim.Strategy(smooth_days=5), script, self.series, ds)
        self.assertEqual(base.modes[ds[5]], "AVVAKTAR")
        self.assertEqual(smooth.modes[ds[5]], "OFFENSIV")  # snitt 6/5 = 1,2 -> 1

    def test_cadence_weekly(self):
        ds = self.ds
        script = {d: (0 if i % 2 else 3) for i, d in enumerate(ds)}
        res = run(sim.Strategy(cadence_days=7), script, self.series, ds)
        deciders = {t["date"] for t in walter_trades(res)}
        prev = {b: a for a, b in zip(ds, ds[1:])}
        for d in deciders:
            self.assertEqual(date.fromisoformat(prev[d]).weekday(), 6)  # beslut på söndagar
        self.assertGreater(len(deciders), 1)

    def eth_series(self, ratios):
        hist = days("2020-10-01", len(ratios))
        return hist, {"btc": const(hist, 100.0), "usdsek": const(hist, 1.0),
                      "eth": {d: 100.0 * r for d, r in zip(hist, ratios)}}

    def test_eth_band(self):
        # ETH/BTC: 0,05 länge, sedan +2 % (över snittet men inom ett 5 %-band), sedan +10 %
        ratios = [0.05] * 120 + [0.051] * 10 + [0.055] * 10
        hist, series = self.eth_series(ratios)
        ds = hist[100:]
        base = run(sim.Strategy(no_levels=True), {ds[0]: 0}, series, ds)
        band = run(sim.Strategy(no_levels=True, eth_band_pct=5), {ds[0]: 0}, series, ds)
        b0 = walter_trades(base, "ETH", "köp")[0]["date"]
        k0 = walter_trades(band, "ETH", "köp")[0]["date"]
        self.assertEqual(b0, hist[121])
        self.assertEqual(k0, hist[131])

    def test_eth_ma_days_and_fixed(self):
        ratios = [0.05 + 0.0001 * i for i in range(60)] + [0.055] * 60  # stiger, sedan platt
        hist, series = self.eth_series(ratios)
        ds = hist[40:]
        m30 = run(sim.Strategy(no_levels=True), {ds[0]: 0}, series, ds)
        m200 = run(sim.Strategy(no_levels=True, eth_ma_days=200), {ds[0]: 0}, series, ds)
        fixed = run(sim.Strategy(no_levels=True, eth_fixed=True), {ds[0]: 0}, series, ds)
        self.assertTrue(walter_trades(m30, "ETH", "sälj"))          # platt kvot -> under 30d-snittet -> sälj
        self.assertEqual(walter_trades(m200, "ETH"), [])            # för kort historik för 200 dagar
        self.assertEqual(len(walter_trades(fixed, "ETH")), 1)       # köp och behåll
        self.assertEqual(walter_trades(fixed, "ETH")[0]["date"], ds[1])

    def test_gold_confirm_days(self):
        ds = self.ds
        vix = {d: (25.0 if ds[3] <= d <= ds[12] or d == ds[15] else 15.0) for d in ds}
        series = dict(self.series, gold=const(ds, 2000.0), vix=vix)
        base = run(sim.Strategy(no_levels=True), {ds[0]: 0}, series, ds)
        slow = run(sim.Strategy(no_levels=True, gold_confirm_days=3), {ds[0]: 0}, series, ds)
        self.assertEqual(len(walter_trades(base, "GOLD")), 4)  # två köp och två sälj
        self.assertEqual([(t["date"], t["side"]) for t in walter_trades(slow, "GOLD")],
                         [(ds[6], "köp"), (ds[19], "sälj")])  # på efter 3 dagar; av först efter 3 lugna i rad

    def test_gold_always(self):
        ds = self.ds
        series = dict(self.series, gold=const(ds, 2000.0), vix=const(ds, 15.0))
        base = run(sim.Strategy(no_levels=True), {ds[0]: 0, ds[5]: 8}, series, ds)
        always = run(sim.Strategy(no_levels=True, gold_always=True), {ds[0]: 0, ds[5]: 8}, series, ds)
        self.assertEqual(walter_trades(base, "GOLD"), [])
        self.assertEqual([(t["date"], t["side"]) for t in walter_trades(always, "GOLD")], [(ds[1], "köp")])
        self.assertEqual(always.modes[ds[6]], "PARKERA")  # guldet ligger kvar även när Walter vilar

    def test_gold_vix_only(self):
        ds = self.ds
        series = dict(self.series, gold=const(ds, 2000.0), vix=const(ds, 15.0))
        rules = copy.deepcopy(sim.DEFAULT_RULES)
        rules["gold"]["spxBelowMa"] = False

        def spx_red(day, series, thresholds, max_age=None):
            return {i: ("red" if i == "spx" else "green") for i in RED_ORDER}
        with mock.patch.object(bl, "lamps_on", spx_red):
            base = sim.run(sim.Strategy(no_levels=True), ds[0], ds[-1], FREE, series=series)
            vix_only = sim.run(sim.Strategy(no_levels=True, rules=rules), ds[0], ds[-1], FREE, series=series)
        self.assertTrue(walter_trades(base, "GOLD"))
        self.assertEqual(walter_trades(vix_only, "GOLD"), [])

    def test_caps_variant(self):
        rules = copy.deepcopy(sim.DEFAULT_RULES)
        rules["caps"] = {"BTC": 0.75, "ETH": 0, "GOLD": 0}
        res = run(sim.Strategy(rules=rules), {self.ds[0]: 0}, self.series, self.ds)
        self.assertAlmostEqual(walter_trades(res, "BTC", "köp")[0]["sek"], 75000, delta=1)

    def test_lamp_cache_same_result(self):
        ds = self.ds
        script = {d: (0 if i % 3 else 5) for i, d in enumerate(ds)}
        cache = {}
        a = run(sim.Strategy(), script, self.series, ds)
        with mock.patch.object(bl, "lamps_on", lamps_script(script)):
            b = sim.run(sim.Strategy(), ds[0], ds[-1], FREE, series=self.series, lamp_cache=cache)
        with mock.patch.object(bl, "lamps_on", side_effect=AssertionError("ska läsas från cachen")):
            c = sim.run(sim.Strategy(), ds[0], ds[-1], FREE, series=self.series, lamp_cache=cache)
        self.assertEqual(a.final_sek, b.final_sek)
        self.assertEqual(b.final_sek, c.final_sek)
        self.assertEqual(len(cache), len(ds) - 1)


if __name__ == "__main__":
    unittest.main()
