"""W-Cipher i historiktestet: porten (backtest/wcipher.py) och simuleringen (backtest/wcipher_run.py)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest import wcipher  # noqa: E402
from backtest import wcipher_run as wr  # noqa: E402

FIX = json.loads((ROOT / "tests" / "fixtures" / "wcipher-bars.json").read_text(encoding="utf-8"))


def _series(days):
    """Växelkurser: 1 USD = 10 SEK, 1 EUR = 10 SEK (EUR per USD = 1), alla dagar."""
    return {"usdsek": {d: 10.0 for d in days}, "eursek": {d: 10.0 for d in days}}


def _flat_tape(prices, kinds, tf="1d", highs=None):
    """Ett ljusflöde dag för dag (open = close = pris) med påhittade signaler {i: {sort}}."""
    t0 = 1388534400  # 2014-01-01
    step = 86400 if tf == "1d" else 14400
    bars = [{"time": t0 + i * step, "open": p, "high": (highs or {}).get(i, p), "low": p, "close": p}
            for i, p in enumerate(prices)]
    from backtest import candles
    tape = wr.Tape(tf, _series({candles.day_of(b["time"]) for b in bars}), bars=bars)
    tape.kinds = {i: set(k) for i, k in kinds.items()}
    return tape


class TestPort(unittest.TestCase):
    def test_fixture_matches_port(self):
        r = wcipher.compute(FIX["bars"])
        self.assertEqual([[s["i"], s["kind"]] for s in r["signals"]], FIX["expect"]["signals"])
        self.assertEqual(r["wt1"], FIX["expect"]["wt1"])

    def test_causal(self):
        """Signalerna t.o.m. stapel k ändras inte av senare staplar (ingen titt framåt)."""
        full = wcipher.compute(FIX["bars"])["signals"]
        for k in (150, 251, 399):
            part = wcipher.compute(FIX["bars"][:k + 1])["signals"]
            self.assertEqual([(s["i"], s["kind"]) for s in part], [(s["i"], s["kind"]) for s in full if s["i"] <= k])

    def test_no_signals_in_warmup(self):
        r = wcipher.compute(FIX["bars"])
        self.assertTrue(all(s["i"] >= wcipher.PARAMS["warmup"] for s in r["signals"]))


class TestSim(unittest.TestCase):
    def test_signal_trades_next_open(self):
        prices = [100.0] * 5 + [200.0] * 5
        tape = _flat_tape(prices, {3: {"kop"}})
        tape.o[4] = 150.0  # stapel 4 öppnar på 150: köpet ska ske där, inte på stapel 3:s stängning
        r = wr.run_wc(tape, "bas", "long", "2014-01-01", "2014-01-10")
        self.assertEqual(r.trades[0]["date"], "2014-01-05")
        trip = r.extra["trips"][0]
        self.assertAlmostEqual(trip["ret"], 200 / 150 * (1 - 0.01) ** 2 - 1)

    def test_round_trip_costs_on_flat_price(self):
        tape = _flat_tape([100.0] * 10, {2: {"kop"}, 5: {"salj"}})
        r = wr.run_wc(tape, "bas", "long", "2014-01-01", "2014-01-10")
        # 1 % växling in, 1 % avgift köp, 1 % avgift sälj, 1 % växling ut, 10 kr SEPA; förlusten ger skattereduktion
        bank_before_credit = 100000 * 0.99 * 0.99 * 0.99 * 0.99 - 10
        self.assertAlmostEqual(r.final_sek - r.credit_sek, bank_before_credit, places=4)
        self.assertGreater(r.credit_sek, 0)

    def test_short_profits_when_price_falls_and_pays_funding(self):
        prices = [100.0] * 3 + [50.0] * 3
        tape = _flat_tape(prices, {1: {"salj"}})
        r = wr.run_wc(tape, "bas", "ls", "2014-01-01", "2014-01-06")
        self.assertEqual(r.trades[0]["side"], "kort")
        trip = r.extra["trips"][0]
        # +50 % minus avgifter (2 × 0,1 %) och finansiering (0,03 % per dag på positionens värde)
        self.assertGreater(trip["ret"], 0.49)
        self.assertLess(trip["ret"], 0.5 - 0.002)

    def test_short_liquidated_when_price_doubles(self):
        prices = [100.0] * 4 + [150.0] * 4
        tape = _flat_tape(prices, {1: {"salj"}}, highs={5: 205.0})
        r = wr.run_wc(tape, "bas", "ls", "2014-01-01", "2014-01-08")
        self.assertEqual(r.extra["liquidations"], ["2014-01-06"])
        self.assertEqual(r.extra["trips"][-1]["ret"], -1.0)
        self.assertLess(r.final_sek, 31000)  # bara skattereduktionen för förlusten kommer tillbaka

    def test_long_only_ignores_short_and_blod_exit_variant(self):
        tape = _flat_tape([100.0] * 10, {2: {"kop"}, 4: {"salj"}, 6: {"blod"}})
        r = wr.run_wc(tape, "blod_ut", "long", "2014-01-01", "2014-01-10")
        self.assertEqual([t["side"] for t in r.trades], ["lång", "stäng"])
        self.assertEqual(r.trades[1]["date"], "2014-01-08")

    def test_combine_adds_parts(self):
        tape = _flat_tape([100.0] * 10, {2: {"kop"}})
        a = wr.run_wc(tape, "bas", "long", "2014-01-01", "2014-01-10", 80000)
        b = wr.run_wc(tape, "bas", "long", "2014-01-01", "2014-01-10", 20000)
        c = wr.combine(a, b, "x")
        self.assertAlmostEqual(c.final_sek, a.final_sek + b.final_sek)
        self.assertAlmostEqual(c.daily["2014-01-05"], a.daily["2014-01-05"] + b.daily["2014-01-05"])


if __name__ == "__main__":
    unittest.main()
