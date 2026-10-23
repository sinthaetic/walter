"""Historiska dagsserier för historiktestet (bara gratis källor), cachade i backtest/cache/.

Varje serie är en dict {ISO-datum: värde}. load(namn) läser cachen eller hämtar; refresh() hämtar om allt.
Serier: btc, eth (USD, Coin Metrics), btc_mvrvz (egen uträkning, samma formel som hämtaren),
gold (GC=F), spx, vix, dxy, us10y (yfinance), usdsek, eurusd, eursek (FRED), sopr (BGeometrics), etf (bykaranteli).
"""
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(__file__).resolve().parent / "cache"
ENV = ROOT / "fetcher" / ".env"
HTTP = requests.Session()
HTTP.headers["User-Agent"] = "WALTER/1.9 (backtest)"
NAMES = ["btc", "eth", "btc_mvrvz", "gold", "spx", "vix", "dxy", "us10y",
         "usdsek", "eurusd", "eursek", "sopr", "etf"]


def _get(url, **kw):
    r = HTTP.get(url, timeout=kw.pop("timeout", 60), **kw)
    r.raise_for_status()
    return r


def _coinmetrics(asset, metrics):
    url = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    params = {"assets": asset, "metrics": metrics, "frequency": "1d",
              "start_time": "2010-07-01", "page_size": 10000}
    rows = []
    while url:
        data = _get(url, params=params).json()
        rows += data.get("data", [])
        url, params = data.get("next_page_url"), None
    return rows


def mvrvz_from_rows(rows):
    """Z = (mcap - realiserat) / std(mcap över all historik t.o.m. dagen). Samma som walter_fetch.mvrv_z_coinmetrics,
    men hela serien. Bara förflutna värden används per dag."""
    out, n, s, s2 = {}, 0, 0.0, 0.0
    for row in rows:
        if not row.get("CapMVRVCur") or not row.get("CapMrktCurUSD"):
            continue
        mc, mvrv = float(row["CapMrktCurUSD"]), float(row["CapMVRVCur"])
        n += 1; s += mc; s2 += mc * mc
        sd = max(s2 / n - (s / n) ** 2, 0) ** 0.5
        if sd > 0 and n >= 30:
            out[row["time"][:10]] = (mc - mc / mvrv) / sd
    return out


def _fetch_btc():
    rows = _coinmetrics("btc", "PriceUSD,CapMrktCurUSD,CapMVRVCur")
    return {"btc": {r["time"][:10]: float(r["PriceUSD"]) for r in rows if r.get("PriceUSD")},
            "btc_mvrvz": mvrvz_from_rows(rows)}


def _fetch_eth():
    rows = _coinmetrics("eth", "PriceUSD")
    return {"eth": {r["time"][:10]: float(r["PriceUSD"]) for r in rows if r.get("PriceUSD")}}


def _yahoo(symbol):
    import yfinance as yf
    h = yf.Ticker(symbol).history(period="max", interval="1d", auto_adjust=False).dropna(subset=["Close"])
    return {i.date().isoformat(): float(c) for i, c in zip(h.index, h["Close"])}


def _fred_csv(series):
    txt = _get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}").text
    out = {}
    for line in txt.splitlines()[1:]:
        d, _, v = line.partition(",")
        try:
            out[d] = float(v)
        except ValueError:
            pass  # "." = ingen observation
    return out


def _riksbank(series):
    rows = _get(f"https://api.riksbank.se/swea/v1/Observations/{series}/1993-01-01/{date.today().isoformat()}").json()
    return {r["date"]: float(r["value"]) for r in rows if r.get("value") is not None}


def _fetch_fx():
    """Riksbanken (officiellt, SEK per USD/EUR sedan 1993) i första hand, FRED fredgraph.csv som reserv."""
    try:
        usdsek, eursek = _riksbank("SEKUSDPMI"), _riksbank("SEKEURPMI")
        eurusd = {d: eursek[d] / usdsek[d] for d in eursek if d in usdsek}
    except Exception:
        usdsek, eurusd = _fred_csv("DEXSDUS"), _fred_csv("DEXUSEU")
        eursek = {d: usdsek[d] * eurusd[d] for d in usdsek if d in eurusd}
    return {"usdsek": usdsek, "eurusd": eurusd, "eursek": eursek}


def _fetch_sopr():
    out = {}
    for x in _get("https://bitcoin-data.com/v1/sopr", params={"startday": "2010-01-01"}).json():
        if x.get("sopr") is not None:
            out[x["d"][:10]] = float(x["sopr"])
    return {"sopr": out}


def _load_env():
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def _fetch_etf(old=None):
    """bykaranteli ger bara senaste ~30 dagarna; nya dagar läggs till det som redan ligger i cachen."""
    _load_env()
    key = os.environ.get("BYKARANTELI_API_KEY")
    if not key:
        raise RuntimeError("ingen BYKARANTELI_API_KEY")
    data = _get("https://bykaranteli.com/api/public/etf", headers={"Authorization": f"Bearer {key}"}).json()
    btc = data["assets"]["BTC"]
    out = dict(old or {})
    for d in btc.get("last_30_days", []):
        if d.get("date") and isinstance(d.get("net_inflow_usd"), (int, float)):
            out[d["date"][:10]] = float(d["net_inflow_usd"])
    latest = btc.get("latest_finalized")
    if latest:
        out[latest["date"][:10]] = float(latest["net_inflow_usd"])
    return {"etf": dict(sorted(out.items()))}


# grupp -> (funktion, serier den fyller)
FETCHERS = {
    "btc": (_fetch_btc, ["btc", "btc_mvrvz"]),
    "eth": (_fetch_eth, ["eth"]),
    "gold": (lambda: {"gold": _yahoo("GC=F")}, ["gold"]),
    "spx": (lambda: {"spx": _yahoo("^GSPC")}, ["spx"]),
    "vix": (lambda: {"vix": _yahoo("^VIX")}, ["vix"]),
    "dxy": (lambda: {"dxy": _yahoo("DX-Y.NYB")}, ["dxy"]),
    "us10y": (lambda: {"us10y": _yahoo("^TNX")}, ["us10y"]),
    "fx": (_fetch_fx, ["usdsek", "eurusd", "eursek"]),
    "sopr": (_fetch_sopr, ["sopr"]),
    "etf": (_fetch_etf, ["etf"]),
}


def _path(name):
    return CACHE_DIR / f"{name}.json"


def _save(name, series):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _path(name).write_text(json.dumps(series), encoding="utf-8")


def _group_of(name):
    for g, (_, names) in FETCHERS.items():
        if name in names:
            return g
    raise KeyError(name)


def _download(group):
    fn, names = FETCHERS[group]
    if group == "etf":
        p = _path("etf")
        old = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        res = fn(old)
    else:
        res = fn()
    for n in names:
        _save(n, res[n])
    return res


def load(name):
    """Serien som dict {datum: värde}. Läser cachen, hämtar annars."""
    p = _path(name)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return _download(_group_of(name))[name]


def load_all():
    out = {}
    for n in NAMES:
        try:
            out[n] = load(n)
        except Exception as e:
            print(f"  saknas {n}: {type(e).__name__}", file=sys.stderr)
    return out


def refresh(only=None):
    """Hämtar om allt (eller bara angivna grupper). Returnerar {grupp: None | felmeddelande}."""
    status = {}
    for g in only or FETCHERS:
        try:
            _download(g)
            status[g] = None
        except Exception as e:
            status[g] = f"{type(e).__name__}: {e}"[:200]
        time.sleep(0.5)
    return status


def coverage(series):
    """[(namn, första, sista, antal, största lucka i dagar)]"""
    rows = []
    for n, s in series.items():
        ds = sorted(s)
        if not ds:
            rows.append((n, None, None, 0, 0))
            continue
        ords = [date.fromisoformat(d).toordinal() for d in ds]
        gap = max((b - a for a, b in zip(ords, ords[1:])), default=0)
        rows.append((n, ds[0], ds[-1], len(ds), gap))
    return rows


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--refresh" in sys.argv or not CACHE_DIR.exists():
        for g, err in refresh().items():
            print(("  OK   " if err is None else "  FEL  ") + g + ("" if err is None else f": {err}"))
    for n, a, b, k, gap in coverage(load_all()):
        print(f"{n:10s} {a} .. {b}  n={k}  största lucka {gap} d")
