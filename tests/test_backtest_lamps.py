"""Historiklamporna (backtest/lamps.py): ingen framtidsläcka, trösklar, gammal data, poängskala. Ingen nätverkstrafik."""
import random
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fetcher"))
from backtest import lamps as bl
from backtest.data import mvrvz_from_rows
import walter_fetch as wf

T = {"spxMaDays": 50, "btcMaDays": 200, "btcWeekDropPct": -10, "vixAbove": 20, "us10yRisePp": 0.25,
     "dxyMaDays": 50, "etfDays": 5, "mvrvZ": 3, "soprAvgDays": 7, "sopr": 1}
D0 = date(2024, 1, 1)


def iso(i):
    return (D0 + timedelta(days=i)).isoformat()


def ser(values, start=0):
    return {iso(start + i): v for i, v in enumerate(values)}


def last_day(values, start=0):
    return iso(start + len(values) - 1)


class Lamps(unittest.TestCase):
    def test_no_lookahead(self):
        base = ser([100.0] * 60)
        day = iso(59)
        before = bl.lamps_on(day, {"spx": base}, T)
        future = dict(base)
        future[iso(60)] = 1.0  # krasch dagen efter
        self.assertEqual(before, bl.lamps_on(day, {"spx": future}, T))
        self.assertEqual(bl.lamps_on(iso(60), {"spx": future}, T)["spx"], "red")

    def test_lag_hides_recent_values(self):
        z = ser([5.0] * 20)  # MVRV-Z 5 (rött) men fördröjt 1 dag
        self.assertIsNone(bl.lamps_on(iso(0), {"btc_mvrvz": z}, T)["mvrv"])
        self.assertEqual(bl.lamps_on(iso(1), {"btc_mvrvz": z}, T)["mvrv"], "red")
        sopr = ser([0.9] * 20)
        self.assertIsNone(bl.lamps_on(iso(12), {"sopr": sopr}, T)["sopr"])
        # 7 dagars fördröjning: första fulla 7-dagars-snittet syns dag 6+7
        self.assertEqual(bl.lamps_on(iso(13), {"sopr": sopr}, T)["sopr"], "red")

    def test_spx_and_dxy(self):
        down = [100.0] * 49 + [90.0]
        up = [100.0] * 49 + [110.0]
        self.assertEqual(bl.lamps_on(last_day(down), {"spx": ser(down)}, T)["spx"], "red")
        self.assertEqual(bl.lamps_on(last_day(up), {"spx": ser(up)}, T)["spx"], "green")
        self.assertEqual(bl.lamps_on(last_day(up), {"dxy": ser(up)}, T)["dxy"], "red")
        self.assertEqual(bl.lamps_on(last_day(down), {"dxy": ser(down)}, T)["dxy"], "green")
        self.assertIsNone(bl.lamps_on(last_day(down[:20]), {"spx": ser(down[:20])}, T)["spx"])  # för kort

    def test_btc_trend_and_week(self):
        below = [100.0] * 199 + [80.0]
        above = [100.0] * 199 + [120.0]
        self.assertEqual(bl.lamps_on(last_day(below), {"btc": ser(below)}, T)["btcTrend"], "red")
        self.assertEqual(bl.lamps_on(last_day(above), {"btc": ser(above)}, T)["btcTrend"], "green")
        drop = [100.0] * 7 + [89.0]   # -11 % mot 7 dagar sedan
        mild = [100.0] * 7 + [91.0]
        self.assertEqual(bl.lamps_on(last_day(drop), {"btc": ser(drop)}, T)["btcWeek"], "red")
        self.assertEqual(bl.lamps_on(last_day(mild), {"btc": ser(mild)}, T)["btcWeek"], "green")

    def test_vix(self):
        for v, want in ((25.0, "red"), (20.0, "green"), (15.0, "green")):
            self.assertEqual(bl.lamps_on(iso(0), {"vix": {iso(0): v}}, T)["vix"], want)

    def test_us10y_month(self):
        rise = {iso(i): 4.0 for i in range(31)}
        rise[iso(31)] = 4.30
        self.assertEqual(bl.lamps_on(iso(31), {"us10y": rise}, T)["us10y"], "red")
        flat = dict(rise)
        flat[iso(31)] = 4.20
        self.assertEqual(bl.lamps_on(iso(31), {"us10y": flat}, T)["us10y"], "green")
        short = {iso(i): 4.0 for i in range(10)}
        self.assertIsNone(bl.lamps_on(iso(9), {"us10y": short}, T)["us10y"])

    def test_etf_mvrv_sopr(self):
        etf = ser([5.0, 5.0, 5.0, 5.0, -30.0])
        self.assertEqual(bl.lamps_on(iso(5), {"etf": etf}, T)["etf"], "red")
        etf2 = ser([5.0, 5.0, 5.0, 5.0, -10.0])
        self.assertEqual(bl.lamps_on(iso(5), {"etf": etf2}, T)["etf"], "green")
        self.assertEqual(bl.lamps_on(iso(3), {"btc_mvrvz": {iso(0): 3.1}}, T)["mvrv"], "red")
        self.assertEqual(bl.lamps_on(iso(3), {"btc_mvrvz": {iso(0): 2.9}}, T)["mvrv"], "green")
        s = ser([1.1] * 10)  # sista datum dag 9, syns dag 16, gammalt > 10 dagar från dag 20
        self.assertEqual(bl.lamps_on(iso(19), {"sopr": s}, T)["sopr"], "green")
        self.assertIsNone(bl.lamps_on(iso(20), {"sopr": s}, T)["sopr"])

    def test_staleness(self):
        s = {iso(0): 30.0}
        self.assertEqual(bl.lamps_on(iso(4), {"vix": s}, T)["vix"], "red")
        self.assertIsNone(bl.lamps_on(iso(5), {"vix": s}, T)["vix"])  # default 4 dagar

    def test_cpi_always_none(self):
        self.assertIsNone(bl.lamps_on(iso(0), {}, T)["cpi"])

    def test_score(self):
        def L(*v):
            return dict(zip(bl.LAMP_IDS, list(v) + [None] * (10 - len(v))))
        self.assertEqual(bl.score(L("red", "red", "green", "green")), (5.0, 4))
        self.assertEqual(bl.score(L(*["red"] * 3 + ["green"] * 3)), (5.0, 6))
        self.assertEqual(bl.score(L(*["red"] * 10)), (10.0, 10))
        r, n = bl.score(L("red", "red", "green"))
        self.assertIsNone(r)
        self.assertEqual(n, 3)
        self.assertAlmostEqual(bl.score(L("red", "red", "green", "green", "green", "green"))[0], 2 / 6 * 10)

    def test_mvrvz_no_lookahead(self):
        rows = [{"time": iso(d) + "T00:00:00.000000000Z", "CapMrktCurUSD": str(100.0 + d * d),
                 "CapMVRVCur": "1.5"} for d in range(60)]
        a = mvrvz_from_rows(rows[:45])
        b = mvrvz_from_rows(rows)
        self.assertTrue(a)
        for d, v in a.items():
            self.assertAlmostEqual(v, b[d])

    def test_matches_live_fetcher(self):
        n = 260
        day = iso(n - 1)
        rnd = random.Random(1)

        def walk(x0):
            xs, x = [], x0
            for _ in range(n):
                x *= 1 + rnd.uniform(-0.03, 0.03)
                xs.append(x)
            return xs
        btc, spx, dxy = walk(60000), walk(5000), walk(100)
        vix = [18.0 + (i % 7) for i in range(n)]
        tnx = [4.0 + 0.02 * (i % 30) for i in range(n)]
        sopr = [1.0 + 0.01 * ((i % 5) - 2) for i in range(n)]
        z = [2.0 + 0.5 * ((i % 9) - 4) / 4 for i in range(n)]
        etf = [(-1) ** i * (i % 5 + 1) * 1e6 for i in range(n)]
        series = {"btc": ser(btc), "spx": ser(spx), "dxy": ser(dxy), "vix": ser(vix), "us10y": ser(tnx),
                  "sopr": ser(sopr), "btc_mvrvz": ser(z), "etf": ser(etf)}
        got = bl.lamps_on(day, series, T)
        # samma indata byggda som hämtaren gör (med publiceringsfördröjningarna)
        ma = wf.ma
        sopr_v, z_v, etf_v = sopr[: n - 7], z[: n - 1], etf[: n - 1]
        pairs = list(ser(tnx).items())
        m = {
            "spx": {"belowMa": spx[-1] < ma(spx, 50), "value": spx[-1], "ma50": ma(spx, 50), "asOf": day},
            "btc": {"belowMa200": btc[-1] < ma(btc, 200), "value": btc[-1], "ma200": ma(btc, 200),
                    "change7dPct": (btc[-1] / btc[-8] - 1) * 100, "asOf": day},
            "vix": {"value": vix[-1], "asOf": day},
            "us10y": {"value": tnx[-1], "change1mPp": tnx[-1] - wf.month_ago(pairs), "asOf": day},
            "dxy": {"aboveMa": dxy[-1] > ma(dxy, 50), "value": dxy[-1], "ma50": ma(dxy, 50), "asOf": day},
            "etfFlow": {"sum5dUsd": sum(etf_v[-5:]), "asOf": iso(n - 2)},
            "mvrvZ": {"value": z_v[-1], "asOf": iso(n - 2)},
            "sopr": {"avg7": sum(sopr_v[-7:]) / 7, "asOf": iso(n - 8)},
        }
        live = wf.lamp_updates(m, T)
        for lamp in bl.LAMP_IDS:
            if lamp == "cpi":
                self.assertIsNone(got["cpi"])
            else:
                self.assertEqual(got[lamp], live[lamp][0], lamp)
        self.assertEqual(sum(v is not None for v in got.values()), 9)


if __name__ == "__main__":
    unittest.main()
