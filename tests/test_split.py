import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fetcher"))
import walter_fetch as wf
import walter_vault as v


class SplitTest(unittest.TestCase):
    def test_strip_private_cache(self):
        c = {"market": {"a": 1}, "fetchedAt": "x", "sources": {}, "daily": {"d": 1}, "notis": {"t": 1}}
        out = wf.strip_private_cache(c)
        self.assertEqual(set(out), {"market", "fetchedAt", "sources"})
        self.assertIn("daily", c)  # tar inte bort i originalet

    def test_build_reads_daily_from_owner_cache(self):
        seen = {}
        orig = wf.wp.sharpe
        wf.wp.sharpe = lambda d, flows, first: seen.setdefault("d", dict(d)) and None
        try:
            state = json.loads((ROOT / "data" / "state.json").read_text(encoding="utf-8"))
            wf.build(state, {"daily": {"1999-01-01": 111}}, False,
                     owner_cache={"daily": {"2000-01-01": 222}, "notis": {"text": "hej"}})
        finally:
            wf.wp.sharpe = orig
        self.assertIn("2000-01-01", seen["d"])
        self.assertNotIn("1999-01-01", seen["d"])
        self.assertEqual(state["notis"], {"text": "hej"})

    def test_merge_daily(self):
        self.assertEqual(v.merge_daily({"d1": 1, "d2": 2}, {"d2": 3, "d3": 4}), {"d1": 1, "d2": 3, "d3": 4})


if __name__ == "__main__":
    unittest.main()
