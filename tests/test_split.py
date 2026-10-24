import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fetcher"))
import walter_fetch as wf
import walter_vault as v


def minimal_state():
    return {"market": {}, "lamps": [], "rules": {"lampThresholds": {}}, "updatedAt": "2000-01-01",
            "portfolio": {"peak": 50, "history": []}}


class SplitTest(unittest.TestCase):
    def test_strip_private_cache(self):
        c = {"market": {"a": 1}, "fetchedAt": "x", "sources": {}, "daily": {"d": 1}, "notis": {"t": 1}}
        out = wf.strip_private_cache(c)
        self.assertEqual(set(out), {"market", "fetchedAt", "sources"})
        self.assertIn("daily", c)  # tar inte bort i originalet

    def test_build_reads_daily_from_owner_cache(self):
        state = minimal_state()
        sharpe_input = {}

        def fake_sharpe(daily, flows, first_trade):
            sharpe_input.update(daily)
            return None

        with patch.object(wf.wp, "valuation", lambda pf, px: ({}, 100)),                 patch.object(wf.wp, "prices_sek", lambda m: {}),                 patch.object(wf.wp, "propose", lambda s: {}),                 patch.object(wf.wp, "sharpe", fake_sharpe):
            wf.build(state, {"daily": {"1999-01-01": 111}}, False,
                     owner_cache={"daily": {"2000-01-01": 222}, "notis": {"text": "hej"}})
        self.assertIn("2000-01-01", sharpe_input)
        self.assertNotIn("1999-01-01", sharpe_input)
        self.assertEqual(state["portfolio"]["peak"], 222)
        self.assertEqual(state["notis"], {"text": "hej"})

    def test_build_ignores_daily_before_start_date(self):
        state = minimal_state()
        state["startDate"] = "2026-10-24"
        seen = {}

        def fake_sharpe(daily, flows, first_trade):
            seen.update(daily)
            return None

        with patch.object(wf.wp, "valuation", lambda pf, px: ({}, 1000)), \
                patch.object(wf.wp, "prices_sek", lambda m: {}), \
                patch.object(wf.wp, "propose", lambda s: {}), \
                patch.object(wf.wp, "sharpe", fake_sharpe):
            state["portfolio"]["peak"] = 1000
            wf.build(state, {}, False, owner_cache={"daily": {"2026-10-23": 254332, "2026-10-25": 1010}})
        self.assertNotIn("2026-10-23", seen)
        self.assertEqual(state["portfolio"]["peak"], 1010)

    def test_paper_rebuild_keeps_notis_and_daily(self):
        import walter_paper as wpaper
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "state.json").write_text(json.dumps(minimal_state()), encoding="utf-8")
            (d / "cache.json").write_text(json.dumps({"market": {}}), encoding="utf-8")
            (d / "owner-cache.json").write_text(
                json.dumps({"daily": {"2000-01-01": 222}, "notis": {"text": "hej"}}), encoding="utf-8")
            with patch.object(wf, "BASE", d / "state.json"), patch.object(wf, "CACHE", d / "cache.json"),                     patch.object(wf, "OWNER_CACHE", d / "owner-cache.json"),                     patch.object(wf.wp, "valuation", lambda pf, px: ({}, 100)),                     patch.object(wf.wp, "prices_sek", lambda m: {}),                     patch.object(wf.wp, "propose", lambda s: {}):
                built = wpaper.rebuild(wf)
        self.assertEqual(built["notis"], {"text": "hej"})
        self.assertEqual(built["portfolio"]["peak"], 222)

    def test_merge_daily(self):
        self.assertEqual(v.merge_daily({"d1": 1, "d2": 2}, {"d2": 3, "d3": 4}), {"d1": 1, "d2": 3, "d3": 4})


if __name__ == "__main__":
    unittest.main()
