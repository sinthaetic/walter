"""backtest/pulse.py: lampornas historik till data/pulse.js (översiktens graf)."""
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from backtest import pulse


def days(start, n):
    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n)]


def flat(ds, v):
    return {d: v for d in ds}


class PulseTest(unittest.TestCase):
    def setUp(self):
        self.ds = days("2020-01-01", 260)
        # 4 lampor med data: VIX (röd över 20), 10Y (stilla = grön), BTC-trend + BTC-vecka (stilla = grön)
        self.series = {
            "btc": flat(self.ds, 100.0),
            "vix": {d: (30.0 if d >= "2020-09-01" else 10.0) for d in self.ds},
            "us10y": flat(self.ds, 4.0),
        }

    def test_starts_at_first_day_with_four_lamps_and_rounds_nearest(self):
        rows = pulse.build(self.series)
        # BTC-trend kräver 200 dagars historik -> fjärde lampan först dag 200 (index 199)
        self.assertEqual(rows[0][0], self.ds[199])
        self.assertTrue(all(isinstance(r, int) for _, r in rows))
        by = dict(rows)
        self.assertEqual(by[self.ds[199]], 0)   # VIX 10 -> 0 röda av 4
        self.assertEqual(by[self.ds[-1]], 3)    # 1 röd av 4 = 2,5 -> närmaste = 3

    def test_days_with_too_few_lamps_are_skipped(self):
        s = dict(self.series)
        s["vix"] = {d: v for d, v in s["vix"].items() if not ("2020-08-01" <= d <= "2020-08-10")}
        rows = dict(pulse.build(s))
        self.assertNotIn("2020-08-09", rows)    # VIX äldre än 4 dagar -> bara 3 lampor
        self.assertIn("2020-08-20", rows)

    def test_render_is_js_with_dates_and_numbers_only(self):
        rows = [["2020-01-01", 2], ["2020-01-02", 7]]
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "pulse.js"
            pulse.write(rows, p)
            text = p.read_text(encoding="utf-8")
        self.assertIn("window.WALTER_PULSE = [", text)
        body = text[text.index("["):text.rindex("]") + 1]
        self.assertEqual(json.loads(body), rows)


if __name__ == "__main__":
    unittest.main()
