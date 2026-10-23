import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fetcher"))
import walter_fetch as wf
import walter_public as wpub

PRIVATE = ("journal", "portfolio", "k4", "capitalChange", "daily", "notis", "proposal")


def fixture_state(statuses=None):
    statuses = statuses or ["red"] * 3 + ["green"] * 7
    return {
        "journal": [{"x": 1}], "portfolio": {"value": 1}, "k4": [1], "capitalChange": {"manualTopUp": 1},
        "daily": {}, "notis": {"t": 1}, "proposal": {"p": 1},
        "fetchedAt": "2026-10-22T08:00:00", "version": "1.13",
        "levels": {"1": {"asset": "BTC", "name": "Bitcoin", "unlocked": True, "since": "2026-10-21"},
                   "2": {"asset": "ETH", "name": "Ethereum", "description": "text"},
                   "3": {"asset": "GULD", "name": "Guld", "gainPct": 50, "maxDd": 12, "description": "text"}},
        "rules": {"parkeraAtRed": 7, "wakeAtRed": 5, "modes": {"buyAtRed": 2, "buyLittleAtRed": 4}},
        "lamps": [{"id": f"l{i}", "name": f"L{i}", "rule": "r", "status": s, "value": "v", "asOf": "2026-10-22"}
                  for i, s in enumerate(statuses)],
        "market": {"usdsek": {"value": 10, "asOf": "2026-10-22"}, "eursek": {"value": 11, "asOf": "2026-10-22"},
                   "btc": {"value": 100, "belowMa200": False, "asOf": "2026-10-22"}, "ethBtc": {"value": 0.05},
                   "gold": {"value": 50, "asOf": "2026-10-22"}, "ethBtcAbove30dMa": True,
                   "vix": {"value": 18.5}, "spx": {"belowMa": False}},
    }


class PublicTest(unittest.TestCase):
    def test_snapshot_has_no_private_keys(self):
        text = json.dumps(wpub.snapshot(fixture_state()))
        for k in PRIVATE:
            self.assertNotIn(f'"{k}"', text)

        def keys(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    yield k
                    yield from keys(v)
            elif isinstance(o, list):
                for v in o:
                    yield from keys(v)
        self.assertFalse(set(PRIVATE) & set(keys(wpub.snapshot(fixture_state()))))

    def test_snapshot_keys_and_values(self):
        s = wpub.snapshot(fixture_state())
        self.assertEqual(set(s), {"date", "fetchedAt", "ready", "red", "mode", "lamps", "px", "usdsek", "eursek",
                                  "ethBtcAbove30dMa", "btcLong", "vix", "spxBelowMa", "rules",
                                  "levels", "version"})
        self.assertTrue(s["ready"])
        self.assertEqual(s["red"], 3)
        self.assertEqual(s["mode"], "NORMAL")
        self.assertEqual(s["px"]["GOLD"], 500)
        self.assertEqual(s["date"], "2026-10-22")
        self.assertTrue(s["btcLong"])
        self.assertEqual(s["vix"], 18.5)

    def test_snapshot_levels_only_public_fields(self):
        s = wpub.snapshot(fixture_state())
        self.assertEqual(s["version"], "1.13")
        self.assertEqual(s["levels"], {"1": {"asset": "BTC", "name": "Bitcoin"},
                                       "2": {"asset": "ETH", "name": "Ethereum"},
                                       "3": {"asset": "GULD", "name": "Guld", "gainPct": 50, "maxDd": 12}})
        for lv in s["levels"].values():
            self.assertFalse(set(lv) - {"asset", "name", "gainPct", "maxDd"})

    def test_snapshot_without_levels_is_null(self):
        st = fixture_state()
        del st["levels"]
        self.assertIsNone(wpub.snapshot(st)["levels"])

    def test_not_ready_gives_null_mode(self):
        st = fixture_state(["red"] * 2 + [None] + ["green"] * 7)
        s = wpub.snapshot(st)
        self.assertFalse(s["ready"])
        self.assertIsNone(s["mode"])

    def test_missing_data_is_null(self):
        st = fixture_state()
        st["market"] = {}
        s = wpub.snapshot(st)
        self.assertEqual(s["px"], {"BTC": None, "ETH": None, "GOLD": None})
        self.assertIsNone(s["eursek"])
        self.assertIsNone(s["btcLong"])
        self.assertIsNone(s["vix"])

    def test_stale_btc_gives_null_px(self):
        st = fixture_state()
        st["market"]["btc"]["asOf"] = "2026-10-21"
        row = wpub.append_log([], wpub.snapshot(st))[0]
        self.assertIsNone(row["px"]["BTC"])
        self.assertIsNone(row["px"]["ETH"])
        self.assertEqual(row["px"]["GOLD"], 500)

    def test_old_usdsek_nulls_all_px(self):
        st = fixture_state()
        st["rules"]["lampMaxAgeDays"] = {"default": 4}
        st["market"]["usdsek"]["asOf"] = "2026-10-10"
        self.assertEqual(wpub.snapshot(st)["px"], {"BTC": None, "ETH": None, "GOLD": None})

    def test_ready_row_not_overwritten_by_not_ready(self):
        ready = wpub.snapshot(fixture_state())
        notready = wpub.snapshot(fixture_state(["red"] * 2 + [None] + ["green"] * 7))
        log = wpub.append_log(wpub.append_log([], ready), notready)
        self.assertTrue(log[0]["ready"])
        self.assertEqual(log[0]["red"], 3)
        log = wpub.append_log(wpub.append_log([], notready), ready)  # omvänt: senaste vinner
        self.assertTrue(log[0]["ready"])

    def test_gold_failure_keeps_btc(self):
        from unittest.mock import patch
        def fake(url, **kw):
            if kw["params"].get("ids") == "pax-gold":
                raise RuntimeError("nere")
            if kw["params"].get("ids") == "bitcoin":
                return {"bitcoin": {"usd": 100, "usd_24h_change": 1}}
            return {"prices": [[0, 1.0]] * 220}
        with patch.object(wf, "get_json", fake):
            out = wf.fetch_coingecko()
        self.assertNotIn("gold", out)
        self.assertIn("btc", out)

    def test_append_log_one_row_per_day(self):
        a = dict(wpub.snapshot(fixture_state()), red=1)
        b = dict(wpub.snapshot(fixture_state()), red=4)
        log = wpub.append_log(wpub.append_log([], a), b)
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["red"], 4)

    def test_append_log_sorted_never_trimmed(self):
        from datetime import date, timedelta
        log = []
        snap = wpub.snapshot(fixture_state())
        for i in reversed(range(400)):
            log = wpub.append_log(log, dict(snap, date=(date(2025, 1, 1) + timedelta(days=i)).isoformat()))
        self.assertEqual(len(log), 400)
        dates = [r["date"] for r in log]
        self.assertEqual(dates, sorted(dates))

    def test_log_row_keys(self):
        log = wpub.append_log([], wpub.snapshot(fixture_state()))
        self.assertEqual(tuple(log[0]), wpub.LOG_KEYS)

    def test_write_market_js(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "market.js"
            wpub.write_market_js(wpub.snapshot(fixture_state()), [], p)
            t = p.read_text(encoding="utf-8")
        self.assertIn("window.WALTER_MARKET = ", t)
        body = t[t.index("window.WALTER_MARKET = ") + len("window.WALTER_MARKET = "):].rstrip().rstrip(";")
        self.assertEqual(set(json.loads(body)), {"now", "log"})

    def test_strip_private_cache_keeps_market_log(self):
        out = wf.strip_private_cache({"market": {}, "marketLog": [{"date": "d"}], "daily": {}, "notis": {}})
        self.assertEqual(out, {"market": {}, "marketLog": [{"date": "d"}]})


if __name__ == "__main__":
    unittest.main()
