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


if __name__ == "__main__":
    unittest.main()
