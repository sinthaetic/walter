"""Krypto-rubriker till Pro-sidan: data/news.js (window.WALTER_NEWS), byggd i Actionen före deploy.
Bara rubrik, källa, tid och länk – aldrig artikeltext. Nyheterna ändrar inget i Walter.
Källor (RSS): CoinDesk, Cryptonews, och DI filtrerat på kryptoord (DI har inget eget kryptoflöde; Cryptofeber har stängt sitt).
Poster (rubrik, länk eller källa) med ord som publiceringens läckspärr letar efter (walter_deploy.PRIVATE_WORDS och
BLOCK) hoppas över, så att t.ex. "Wall Street Journal" eller en länk med "daily" aldrig stoppar deployen.
Kör: python fetcher/walter_news.py   (ett fel i en källa hoppar bara över den källan)
"""
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "news.js"
FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", None),
    ("Cryptonews", "https://cryptonews.com/news/feed/", None),
    ("DI", "https://www.di.se/rss", re.compile(r"krypto|bitcoin|ethereum|stablecoin|blockkedja", re.I)),
]
KEEP = 12
# Samma ord som walter_deploy.PRIVATE_WORDS + BLOCK-namnen (inte importerat: deploy-modulen laddar hela hämtaren).
# Jämförs utan skiftläge, alltså strängare än läckspärren. tests/test_news.py håller listorna lika.
BLOCKED = ["journal", "portfolio", "k4", "capitalchange", "daily", "notis", "proposal", "walter_owner_key",
           ".env", "etf_raw.json", "state.json", "state.js", "owner-cache.json", "paper-journal-"]


def blocked(item):
    text = json.dumps(item, ensure_ascii=False).lower()
    return any(w in text for w in BLOCKED)


def items(source, url, only=None, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Walter nyheter; +https://sinthaetic.github.io/walter/)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        root = ET.fromstring(r.read())
    out = []
    for it in root.iter("item"):
        title = re.sub(r"<[^>]+>|\s+", " ", it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        try:
            at = parsedate_to_datetime(it.findtext("pubDate") or "").astimezone(timezone.utc)
        except (TypeError, ValueError):
            continue
        if not title or not link.startswith("https://"):
            continue
        if only and not only.search(title):
            continue
        item = {"t": title[:200], "url": link, "src": source, "at": at.strftime("%Y-%m-%dT%H:%M:%SZ")}
        if not blocked(item):
            out.append(item)
    return out


def build(fetch=items):
    got, failed = [], []
    for source, url, only in FEEDS:
        try:
            got += fetch(source, url, only)
        except Exception as e:  # en trasig källa ska aldrig stoppa de andra eller deployen
            failed.append(f"{source} ({type(e).__name__})")
    got.sort(key=lambda x: x["at"], reverse=True)
    return {"updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "items": got[:KEEP]}, failed


def main():
    news, failed = build()
    if not news["items"]:
        print("Inga rubriker hämtades – news.js lämnas som den var.", ", ".join(failed))
        return 0
    OUT.write_text("window.WALTER_NEWS = " + json.dumps(news, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    print(f"Skrev {len(news['items'])} rubriker till {OUT}." + (f" Kunde inte hämta: {', '.join(failed)}." if failed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
