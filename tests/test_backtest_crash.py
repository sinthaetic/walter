"""Steg 10 del 6: krasch-broms (stop_pct) och nödjustering (emergency_pp) i historiktestet. Syntetisk data.
Beslut på dag d:s stängning, affären på dag d+1:s pris, och framtida priser ändrar inget före dem."""
import copy
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fetcher"))
from backtest import sim
from backtest.costs import Exchange

FREE = Exchange("gratis", 0, 0, "SEK", 0, 0)


def days(start, n):
    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n)]


def series(ds, btc):
    return {"btc": dict(zip(ds, btc)), "usdsek": {d: 1.0 for d in ds}, "gold": {d: 10.0 for d in ds},
            "eth": {d: 5.0 for d in ds}}


def ap(**kw):
    return sim.Strategy(name="t", rules=copy.deepcopy(sim.AUTOPILOT_RULES), **kw)


def btc_trades(r):
    return [(t["date"], t["side"], t["priceSek"]) for t in r.trades if t["why"] == "walter" and t["asset"] == "BTC"]


class CrashBrake(unittest.TestCase):
    # 2021-01-04 är en måndag. BTC 100 -> 110 (topp) -> faller till 85 (-23 %) en onsdag -> under snittet -> upp igen.
    ds = days("2021-01-04", 40)
    btc = [100.0] * 3 + [110.0] * 4 + [100.0, 95.0, 85.0, 80.0] + [70.0] * 6 + [90.0] * 23

    def test_stop_sells_next_day_and_buys_back_above_ma(self):
        s = series(self.ds, self.btc)
        r = sim.run(ap(stop_pct=20, stop_ma_days=5), self.ds[0], self.ds[-1], FREE, series=s)
        t = btc_trades(r)
        self.assertEqual(t[0], (self.ds[1], "köp", 100.0))           # första dagen: köp
        stop_day = self.ds[9]                                         # 85 <= 110 * 0,8 = 88
        self.assertIn((stop_day, "BTC", "ut"), r.stops)
        self.assertIn((self.ds[10], "sälj", 80.0), t)                 # nästa dags pris, inte stoppdagens
        self.assertFalse(any(d == stop_day for d, *_ in t))
        back = self.ds[17]                                            # 90 > snittet (70) efter att ha varit under
        self.assertIn((back, "BTC", "in"), r.stops)
        self.assertIn((self.ds[18], "köp", 90.0), t)
        units = r.raw["portfolio"]["positions"]["BTC"]["units"]
        self.assertEqual(units, 0)                                    # slutdagen säljer allt
        # Utan bromsen: ingen försäljning i fallet (bandet 5 pp hålls till söndag)
        plain = btc_trades(sim.run(sim.autopilot(), self.ds[0], self.ds[-1], FREE, series=s))
        self.assertNotIn((self.ds[10], "sälj", 80.0), plain)

    def test_no_lookahead(self):
        """Att ändra priserna efter dag k ändrar inga affärer till och med dag k."""
        k = 12
        a = sim.run(ap(stop_pct=20, stop_ma_days=5, emergency_pp=10), self.ds[0], self.ds[-1], FREE,
                    series=series(self.ds, self.btc))
        other = self.btc[:k + 1] + [300.0] * (len(self.ds) - k - 1)
        b = sim.run(ap(stop_pct=20, stop_ma_days=5, emergency_pp=10), self.ds[0], self.ds[-1], FREE,
                    series=series(self.ds, other))
        before = lambda r: [t for t in r.trades if t["date"] <= self.ds[k]]  # noqa: E731
        self.assertEqual(before(a), before(b))
        self.assertEqual([s for s in a.stops if s[0] < self.ds[k]], [s for s in b.stops if s[0] < self.ds[k]])

    def test_off_is_the_autopilot(self):
        s = series(self.ds, self.btc)
        a = sim.run(sim.autopilot(), self.ds[0], self.ds[-1], FREE, series=s)
        b = sim.run(ap(), self.ds[0], self.ds[-1], FREE, series=s)
        self.assertEqual(a.trades, b.trades)


class Emergency(unittest.TestCase):
    def test_rebalances_midweek_only_past_y(self):
        ds = days("2021-01-04", 20)  # måndag; söndagar ds[6], ds[13]
        # onsdag ds[2]: BTC x1,5 -> andelen ca 45 % (10 pp över 35 %), torsdag ds[3]: x2 -> ca 52 % (17 pp)
        btc = [100.0, 100.0, 150.0, 200.0] + [200.0] * 16
        s = series(ds, btc)
        r15 = btc_trades(sim.run(ap(emergency_pp=15), ds[0], ds[-1], FREE, series=s))
        self.assertEqual(r15[1], (ds[4], "sälj", 200.0))  # beslut torsdag (17 pp > 15), affär fredag
        r20 = btc_trades(sim.run(ap(emergency_pp=20), ds[0], ds[-1], FREE, series=s))
        self.assertEqual(r20[1], (ds[7], "sälj", 200.0))  # 17 pp < 20: väntar på söndagens koll, affär måndag
        plain = btc_trades(sim.run(sim.autopilot(), ds[0], ds[-1], FREE, series=s))
        self.assertEqual(plain, r20)


if __name__ == "__main__":
    unittest.main()
