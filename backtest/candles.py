"""BTC/USD-ljus (OHLC) för W-Cipher-testet, gratis från Bitstamps publika API, cachade i backtest/cache/.

  load("1d") / load("4h") -> [{"time": unix-sekunder, "open", "high", "low", "close", "volume"}], äldst först.
  .venv\\Scripts\\python.exe -m backtest.candles --refresh   # hämtar om och skriver täckningen

Bitstamp har BTC/USD sedan sept 2011 (dag och 4 timmar). Sidor om 1000 ljus. Staplar utan handel (volym 0,
open=high=low=close) behålls som de är: det är så börsen själv visar dem.
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

CACHE_DIR = Path(__file__).resolve().parent / "cache"
URL = "https://www.bitstamp.net/api/v2/ohlc/btcusd/"
STEPS = {"1d": 86400, "4h": 14400}
START = 1314835200  # 2011-09-01


def _path(tf):
    return CACHE_DIR / f"btc_ohlc_{tf}.json"


def fetch(tf, start=START):
    step, out, t = STEPS[tf], {}, start
    http = requests.Session()
    http.headers["User-Agent"] = "WALTER/2.0 (backtest)"
    now = time.time()
    while t < now - step:
        r = http.get(URL, params={"step": step, "limit": 1000, "start": t}, timeout=60)
        r.raise_for_status()
        rows = r.json()["data"]["ohlc"]
        if not rows:
            break
        for x in rows:
            ts = int(x["timestamp"])
            out[ts] = {"time": ts, "open": float(x["open"]), "high": float(x["high"]), "low": float(x["low"]),
                       "close": float(x["close"]), "volume": float(x["volume"])}
        last = int(rows[-1]["timestamp"])
        if last + step <= t:
            break
        t = last + step
        time.sleep(0.3)
    bars = [out[k] for k in sorted(out)]
    # Sista stapeln kan vara ofärdig: ta bara stängda staplar.
    return [b for b in bars if b["time"] + step <= now]


def load(tf, refresh=False):
    p = _path(tf)
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    bars = fetch(tf)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bars), encoding="utf-8")
    return bars


def day_of(ts):
    return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()


def coverage(bars, tf):
    step = STEPS[tf]
    gaps = [(b["time"] - a["time"]) // step - 1 for a, b in zip(bars, bars[1:])]
    flat = sum(1 for b in bars if b["volume"] == 0)
    return {"tf": tf, "first": day_of(bars[0]["time"]), "last": day_of(bars[-1]["time"]), "n": len(bars),
            "missing": sum(g for g in gaps if g > 0), "max_gap": max(gaps, default=0), "zero_volume": flat}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for tf in STEPS:
        print(coverage(load(tf, refresh="--refresh" in sys.argv), tf))
