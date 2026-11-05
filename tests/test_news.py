"""fetcher/walter_news.py: rubriker till Pro. Inga nätanrop – källorna ersätts med en fejkad hämtning."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fetcher"))
import walter_deploy as wd  # noqa: E402
import walter_news as wn  # noqa: E402

RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Bitcoin faller 5 %</title><link>https://ex.se/a</link><pubDate>Thu, 05 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Wall Street Journal: krypto</title><link>https://ex.se/b</link><pubDate>Thu, 05 Nov 2026 11:00:00 GMT</pubDate></item>
<item><title>Airbnb rusar</title><link>https://ex.se/c</link><pubDate>Thu, 05 Nov 2026 12:00:00 GMT</pubDate></item>
<item><title>Ingen https</title><link>javascript:alert(1)</link><pubDate>Thu, 05 Nov 2026 13:00:00 GMT</pubDate></item>
</channel></rss>"""


class FakeResp:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class NewsTest(unittest.TestCase):
    def test_filters_blocked_words_keyword_and_non_https(self):
        orig = wn.urllib.request.urlopen
        wn.urllib.request.urlopen = lambda req, timeout=0: FakeResp(RSS)
        try:
            all_ = wn.items("X", "https://x")
            di = wn.items("DI", "https://x", wn.FEEDS[2][2])
        finally:
            wn.urllib.request.urlopen = orig
        self.assertEqual([i["t"] for i in all_], ["Bitcoin faller 5 %", "Airbnb rusar"])  # journal + javascript: bort
        self.assertEqual([i["t"] for i in di], ["Bitcoin faller 5 %"])                   # bara kryptoord
        self.assertEqual(all_[0]["at"], "2026-11-05T10:00:00Z")

    def test_broken_source_is_skipped_and_newest_first(self):
        def fetch(source, url, only):
            if source == "Cryptonews":
                raise OSError("nere")
            return [{"t": source, "url": "https://x", "src": source, "at": "2026-11-0%dT00:00:00Z" % (1 if source == "DI" else 2)}]
        news, failed = wn.build(fetch)
        self.assertEqual([i["src"] for i in news["items"]], ["CoinDesk", "DI"])
        self.assertEqual(failed, ["Cryptonews (OSError)"])

    def test_blocked_words_match_deploy_guard(self):
        self.assertEqual(sorted(wn.BLOCKED), sorted(w.lower() for w in wd.PRIVATE_WORDS))

    def test_news_js_passes_leak_check(self):
        news, _ = wn.build(lambda s, u, o: [{"t": "Bitcoin stiger", "url": "https://x", "src": s, "at": "2026-11-05T00:00:00Z"}])
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data").mkdir()
            (Path(t) / "data" / "news.js").write_text("window.WALTER_NEWS = " + str(news) + ";", encoding="utf-8")
            self.assertEqual(wd.leak_check(Path(t)), [])


if __name__ == "__main__":
    unittest.main()
