"""WALTER-hämtaren: hämtar gratis marknadsdata och skriver data/state.js.

  python fetcher/walter_fetch.py            hämta allt och bygg state.js
  python fetcher/walter_fetch.py --offline  bygg bara om state.js (t.ex. efter ny journalpost)

data/state.json är handredigerad (journal, portfölj, mode, regler) och skrivs aldrig av hämtaren.
data/cache.json minns senast hämtade värden, så att en källa som strular inte nollar något.
Mode ändras aldrig automatiskt – journalen är facit. Hämtaren räknar lamporna och Walters förslag
(walter_paper.py), men handlar aldrig: förslaget godkänns med paper.bat.
"""

import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

import requests

import walter_paper as wp
import walter_public as wpub

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "state.json"
CACHE = ROOT / "data" / "cache.json"
OWNER_CACHE = ROOT / "data" / "owner-cache.json"  # ägarens dagsvärden och notis, aldrig i repot
OUT = ROOT / "data" / "state.js"
MARKET_OUT = ROOT / "data" / "market.js"  # publik marknadsfil (lampor, priser, regler, logg)
ENV = Path(__file__).resolve().parent / ".env"

HTTP = requests.Session()
HTTP.headers["User-Agent"] = "WALTER/1.9 (paper trading)"
MONTHS = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


# ---------- Format (svenska, som i app.js) ----------
def num(v, d=0):
    s = f"{abs(v):,.{d}f}".replace(",", " ").replace(".", ",")
    return ("−" if v < 0 else "") + s


def pct(v, d=1):
    return ("+" if v > 0 else "−" if v < 0 else "") + num(abs(v), d) + " %"


def day(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month - 1]}"


def warn(msg):
    """Gul varning i terminalen. Avbryter aldrig hämtningen."""
    print(f"[33m  VARNING  {msg}[0m")


def safe(e):
    """Felmeddelande utan nycklar – requests lägger hela URL:en (med api_key=…) i texten."""
    return re.sub(r"(api_key|apikey|key|token)=[^&\s]+", r"\1=***", str(e), flags=re.I)


def get_json(url, **kw):
    r = HTTP.get(url, timeout=kw.pop("timeout", 20), **kw)
    r.raise_for_status()
    return r.json()


# ---------- Källor ----------
def yahoo_hist(symbol, period="6mo"):
    """Dagsstängningar från yfinance, äldst först: [(datum, stängning), ...]."""
    import yfinance as yf

    h = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=False).dropna(subset=["Close"])
    if len(h) < 2:
        raise ValueError(f"för lite data för {symbol}")
    return [(i.date().isoformat(), float(c)) for i, c in zip(h.index, h["Close"])]


def ma(closes, n):
    """Snitt av de senaste n värdena (eller alla, om det finns färre)."""
    tail = closes[-n:]
    return sum(tail) / len(tail)


def month_ago(series):
    """Värdet ungefär en månad (30 dagar) före det senaste. series: [(datum, värde)], äldst först."""
    last = date.fromisoformat(series[-1][0])
    older = [v for d, v in series if (last - date.fromisoformat(d)).days >= 30]
    if not older:
        raise ValueError("för kort historik för en månad bakåt")
    return older[-1]


def fetch_indices():
    out = {}
    nd = yahoo_hist("^IXIC", "10d")
    out["nasdaq"] = {"changePct": round((nd[-1][1] / nd[-2][1] - 1) * 100, 2), "asOf": nd[-1][0]}
    sp = yahoo_hist("^GSPC", "6mo")
    closes = [c for _, c in sp]
    ma50 = ma(closes, 50)
    out["spx"] = {"value": round(closes[-1], 2), "changePct": round((closes[-1] / closes[-2] - 1) * 100, 2),
                  "ma50": round(ma50, 2), "belowMa": closes[-1] < ma50, "asOf": sp[-1][0]}
    return out


def fetch_vix():
    h = yahoo_hist("^VIX", "10d")
    last, prev = h[-1][1], h[-2][1]
    return {"vix": {"value": round(last, 2), "changePct": round((last / prev - 1) * 100, 1), "asOf": h[-1][0]}}


def fetch_dxy():
    h = yahoo_hist("DX-Y.NYB", "6mo")
    closes = [c for _, c in h]
    ma50 = ma(closes, 50)
    return {"dxy": {"value": round(closes[-1], 3), "ma50": round(ma50, 3), "aboveMa": closes[-1] > ma50, "asOf": h[-1][0]}}


def fetch_us10y():
    """FRED DGS10 (officiellt API) i första hand, Yahoo ^TNX om FRED inte svarar.
    Lampan tittar på förändringen mot en månad sedan."""
    try:
        series = fred_api("DGS10", 40)
        src = "FRED"
    except Exception as e:
        if not os.environ.get("FRED_API_KEY"):
            warn("FRED_API_KEY saknas i fetcher/.env – 10-årig ränta tas från Yahoo ^TNX i stället.")
        else:
            print(f"    FRED svarade inte ({type(e).__name__}), tar ^TNX från Yahoo")
        series = yahoo_hist("^TNX", "3mo")
        if series[-1][1] > 20:  # gammal Yahoo-skala (räntan × 10)
            series = [(d, v / 10) for d, v in series]
        src = "Yahoo ^TNX"
    (as_of, last), (_, prev) = series[-1], series[-2]
    m1 = month_ago(series)
    return {"us10y": {"value": round(last, 2), "changeBp": round((last - prev) * 100), "monthAgo": round(m1, 2),
                      "change1mPp": round(last - m1, 2), "asOf": as_of, "source": src}}


def fetch_coingecko():
    btc = get_json("https://api.coingecko.com/api/v3/simple/price", params={"ids": "bitcoin", "vs_currencies": "usd", "include_24hr_change": "true"})
    chart = get_json("https://api.coingecko.com/api/v3/coins/ethereum/market_chart",
                     params={"vs_currency": "btc", "days": 30, "interval": "daily"})
    prices = [p for _, p in chart["prices"]]
    try:  # guld får aldrig ta med sig BTC/ETH-lamporna om det felar
        gold = get_json("https://api.coingecko.com/api/v3/simple/price", params={"ids": "pax-gold", "vs_currencies": "usd"})
        gold_out = {"gold": {"value": round(gold["pax-gold"]["usd"], 2), "asOf": date.today().isoformat()}}
    except Exception as e:
        warn(f"PAXG (guld) kunde inte hämtas ({safe(e)}) – guldpriset blir null.")
        gold_out = {}
    ma30 = sum(prices) / len(prices)
    hist = get_json("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
                    params={"vs_currency": "usd", "days": 220, "interval": "daily"})
    bp = [p for _, p in hist["prices"]]
    if len(bp) < 200:
        raise ValueError(f"för kort BTC-historik ({len(bp)} dagar)")
    ma200 = ma(bp, 200)
    week = (bp[-1] / bp[-8] - 1) * 100
    return {
        "btc": {"value": round(btc["bitcoin"]["usd"]), "unit": "usd", "asOf": date.today().isoformat(),
                "changePct24h": round(btc["bitcoin"]["usd_24h_change"], 2) if btc["bitcoin"].get("usd_24h_change") is not None else None,
                "ma200": round(ma200), "belowMa200": bp[-1] < ma200, "change7dPct": round(week, 1)},
        **gold_out,
        "ethBtc": {"value": round(prices[-1], 5), "ma30": round(ma30, 5)},
        "ethBtcAbove30dMa": prices[-1] > ma30,
    }


def mvrv_z_coinmetrics():
    """MVRV-Z räknad själv från Coin Metrics Community (gratis, ingen nyckel, hela historiken sedan 2010):
    Z = (marknadsvärde − realiserat värde) / standardavvikelsen för marknadsvärdet över all historik t.o.m. dagen.
    Realiserat värde = marknadsvärde / MVRV. Stämmer med BGeometrics inom ±0,1 (kontrollerat okt 2026)."""
    url = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    params = {"assets": "btc", "metrics": "CapMrktCurUSD,CapMVRVCur", "frequency": "1d",
              "start_time": "2010-07-01", "page_size": 10000}
    rows = []
    while url:
        data = get_json(url, params=params, timeout=60)
        rows += data.get("data", [])
        url, params = data.get("next_page_url"), None
    n = s = s2 = 0
    z = None
    for row in rows:
        if not row.get("CapMVRVCur") or not row.get("CapMrktCurUSD"):
            continue
        mc, mvrv = float(row["CapMrktCurUSD"]), float(row["CapMVRVCur"])
        n += 1; s += mc; s2 += mc * mc
        sd = max(s2 / n - (s / n) ** 2, 0) ** 0.5
        if sd > 0:
            z, as_of = (mc - mc / mvrv) / sd, row["time"][:10]
    if z is None or n < 3000:
        raise ValueError(f"för lite historik från Coin Metrics ({n} dagar)")
    return {"value": round(z, 2), "asOf": as_of, "source": "Coin Metrics (egen uträkning)"}


def fetch_bgeometrics():
    # MVRV-Z: Coin Metrics i första hand (en dag efter), BGeometrics som reserv (ungefär en vecka efter).
    try:
        z = mvrv_z_coinmetrics()
    except Exception as e:
        print(f"    Coin Metrics svarade inte ({type(e).__name__}), tar MVRV-Z från BGeometrics")
        b = get_json("https://bitcoin-data.com/v1/mvrv-zscore/last")
        z = {"value": round(float(b["mvrvZscore"]), 2), "asOf": b["d"], "source": "BGeometrics"}
    start = date.fromordinal(date.today().toordinal() - 25).isoformat()
    s = [x for x in get_json("https://bitcoin-data.com/v1/sopr", params={"startday": start}) if x.get("sopr") is not None]
    if len(s) < 7:
        raise ValueError(f"för lite SOPR-data ({len(s)} dagar)")
    last7 = [float(x["sopr"]) for x in s[-7:]]
    return {
        "mvrvZ": z,
        "sopr": {"value": round(last7[-1], 4), "avg7": round(sum(last7) / 7, 4), "asOf": s[-1]["d"]},
    }


def fred_api(series, limit=10):
    """FRED:s officiella API (gratis nyckel FRED_API_KEY i fetcher/.env). [(datum, värde)], äldst först."""
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise RuntimeError("ingen FRED_API_KEY")
    data = get_json("https://api.stlouisfed.org/fred/series/observations",
                    params={"series_id": series, "api_key": key, "file_type": "json",
                            "sort_order": "desc", "limit": limit})
    obs = [(o["date"], float(o["value"])) for o in data["observations"] if o["value"] not in ("", ".")]
    if len(obs) < 2:
        raise ValueError(f"för lite data för {series}")
    return obs[::-1]


def fetch_fx():
    """USDSEK + EURSEK från Riksbanken (officiellt API). USDSEK från FRED DEXSDUS som reserv.
    Ingen fast reservkurs – misslyckas båda behåller cachen senaste live-kursen med sitt datum."""
    out = {}
    for key, series in (("usdsek", "SEKUSDPMI"), ("eursek", "SEKEURPMI")):
        try:
            o = get_json(f"https://api.riksbank.se/swea/v1/Observations/Latest/{series}")
            out[key] = {"value": round(float(o["value"]), 4), "asOf": o["date"], "source": "Riksbanken"}
        except Exception as e:
            if key != "usdsek":
                print(f"    Riksbanken svarade inte för {key} ({type(e).__name__})")
                continue
            print(f"    Riksbanken svarade inte för USDSEK ({type(e).__name__}), provar FRED")
            if not os.environ.get("FRED_API_KEY"):
                warn("FRED_API_KEY saknas – ingen reserv för USDSEK. Senast sparade kurs behålls.")
                continue
            as_of, v = fred_api("DEXSDUS")[-1]
            out[key] = {"value": round(v, 4), "asOf": as_of, "source": "FRED DEXSDUS"}
    if not out:
        raise RuntimeError("ingen valutakurs svarade")
    return out


def load_env():
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def fetch_etf():
    key = os.environ.get("BYKARANTELI_API_KEY")
    if not key:
        raise RuntimeError("ingen BYKARANTELI_API_KEY (se fetcher/.env.example)")
    data = get_json("https://bykaranteli.com/api/public/etf", headers={"Authorization": f"Bearer {key}"})
    dump = ROOT / "data" / "etf_raw.json"
    dump.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        btc = data["assets"]["BTC"]
        latest = btc["latest_finalized"]
        last, last_flow = latest["date"][:10], float(latest["net_inflow_usd"])
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"kände inte igen svaret ({e}) – sparat i {dump}")
    # Månaden hittills = slutförda dagar i last_30_days för samma månad som senaste dagen.
    days = {d["date"][:10]: float(d["net_inflow_usd"]) for d in btc.get("last_30_days", [])
            if d.get("date") and isinstance(d.get("net_inflow_usd"), (int, float))}
    days[last] = last_flow
    mtd = sum(v for d, v in days.items() if d.startswith(last[:7]))
    last5 = [days[d] for d in sorted(days)[-5:]]
    return {"etfFlow": {"mtdUsd": round(mtd), "sum5dUsd": round(sum(last5)), "lastDayUsd": round(last_flow), "asOf": last}}


SOURCES = [
    ("Börsindex (yfinance)", fetch_indices),
    ("VIX (yfinance)", fetch_vix),
    ("Dollarindex (yfinance)", fetch_dxy),
    ("10-årig ränta (FRED / Yahoo ^TNX)", fetch_us10y),
    ("BTC + ETH/BTC (CoinGecko)", fetch_coingecko),
    ("USDSEK + EURSEK (Riksbanken)", fetch_fx),
    ("MVRV-Z (Coin Metrics) + SOPR (BGeometrics)", fetch_bgeometrics),
    ("ETF-flöden (ByKaranteli)", fetch_etf),
]


# ---------- Lampor ----------
def lamp_updates(m, t):
    """id -> (status, värde, datum som värdet gäller). Saknas data för en lampa behålls den gamla."""
    out = {}
    red = lambda cond: "red" if cond else "green"

    spx = m.get("spx", {})
    if spx.get("belowMa") is not None:
        out["spx"] = (red(spx["belowMa"]), f"{num(spx['value'])} (snitt {num(spx['ma50'])})", spx["asOf"])
    btc = m.get("btc", {})
    if btc.get("belowMa200") is not None:
        out["btcTrend"] = (red(btc["belowMa200"]), f"${num(btc['value'])} (snitt ${num(btc['ma200'])})", btc["asOf"])
    if btc.get("change7dPct") is not None:
        out["btcWeek"] = (red(btc["change7dPct"] < t["btcWeekDropPct"]), pct(btc["change7dPct"]), btc["asOf"])
    vix = m.get("vix", {})
    if vix.get("value") is not None and vix.get("asOf"):
        out["vix"] = (red(vix["value"] > t["vixAbove"]), num(vix["value"], 2), vix["asOf"])
    r = m.get("us10y", {})
    if r.get("change1mPp") is not None:
        ch = r["change1mPp"]
        out["us10y"] = (red(ch > t["us10yRisePp"]),
                        f"{num(r['value'], 2)} % ({'+' if ch >= 0 else '−'}{num(abs(ch), 2)} på en månad)", r["asOf"])
    dxy = m.get("dxy", {})
    if dxy.get("aboveMa") is not None:
        out["dxy"] = (red(dxy["aboveMa"]), f"{num(dxy['value'], 2)} (snitt {num(dxy['ma50'], 2)})", dxy["asOf"])
    etf = m.get("etfFlow", {})
    if etf.get("asOf") and etf.get("sum5dUsd") is not None:
        v = etf["sum5dUsd"]
        out["etf"] = (red(v < 0), f"{'−' if v < 0 else '+'}${num(abs(v) / 1e6)}M på 5 dagar", etf["asOf"])
    # KPI (utfall mot förväntan) finns inte gratis – värdena skrivs för hand i state.json → market.cpi.
    cpi = m.get("cpi", {})
    if cpi.get("actual") is not None and cpi.get("expected") is not None and cpi.get("asOf"):
        out["cpi"] = (red(cpi["actual"] > cpi["expected"]), f"{num(cpi['actual'], 1)} % mot {num(cpi['expected'], 1)} %", cpi["asOf"])
    z = m.get("mvrvZ", {})
    if z.get("value") is not None and z.get("asOf"):
        out["mvrv"] = (red(z["value"] > t["mvrvZ"]), f"{num(z['value'], 2)} ({day(z['asOf'])})", z["asOf"])
    sopr = m.get("sopr", {})
    if sopr.get("avg7") is not None:
        out["sopr"] = (red(sopr["avg7"] < t["sopr"]), f"{num(sopr['avg7'], 3)} snitt 7 d ({day(sopr['asOf'])})", sopr["asOf"])
    return out


def stale(as_of, max_days, today):
    """True om värdet är äldre än max_days dagar."""
    return (date.fromisoformat(today) - date.fromisoformat(as_of[:10])).days > max_days


# ---------- Bygg ----------
def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


PRIVATE_CACHE_KEYS = ("daily", "notis")


def strip_private_cache(cache):
    """Marknadscachen som får ligga öppet: utan ägarens dagsvärden och notis."""
    return {k: v for k, v in cache.items() if k not in PRIVATE_CACHE_KEYS}


def load_caches():
    """(cache, owner_cache). Ligger daily/notis kvar i en gammal cache flyttas de till owner_cache."""
    cache, owner = read_json(CACHE, {}), read_json(OWNER_CACHE, {})
    for k in PRIVATE_CACHE_KEYS:
        if k in cache:
            old = cache[k]
            owner[k] = {**old, **owner.get(k, {})} if k == "daily" else owner.get(k) or old
    return strip_private_cache(cache), owner


def save_caches(cache, owner):
    CACHE.write_text(json.dumps(strip_private_cache(cache), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp = OWNER_CACHE.with_name(OWNER_CACHE.name + ".tmp")  # atomiskt: aldrig en halv fil
    tmp.write_text(json.dumps(owner, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, OWNER_CACHE)


def build(state, cache, fetched_any, owner_cache=None):
    owner_cache = owner_cache or {}
    m = state["market"]
    m.update(cache.get("market", {}))

    if len(state["lamps"]) != 10:
        warn(f"state.json har {len(state['lamps'])} lampor – WALTER räknar med exakt 10. Rätta i state.json.")
    today = date.today().isoformat()
    upd = lamp_updates(m, state["rules"]["lampThresholds"])
    ages = state["rules"].get("lampMaxAgeDays", {})
    for lamp in state["lamps"]:
        if lamp["id"] in upd:
            status, value, as_of = upd[lamp["id"]]
            # För gammal data räknas inte – lampan blir "väntar" i stället för att låtsas vara färsk.
            if stale(as_of, ages.get(lamp["id"], ages.get("default", 4)), today):
                status, value = None, f"{value} – gammal ({day(as_of)})"
            lamp["status"], lamp["value"], lamp["asOf"] = status, value, as_of
    # Datan tar över poängen först när alla lampor har ett värde, annars gäller journalens.
    if fetched_any or cache.get("market"):
        if all(l["status"] is not None for l in state["lamps"]):
            red = sum(l["status"] == "red" for l in state["lamps"])
            state["lampScore"] = {"red": red, "total": len(state["lamps"]),
                                  "asOf": cache.get("fetchedAt", today)[:10], "source": "data"}
        m["asOf"] = cache.get("fetchedAt", today)[:10]
        state["updatedAt"] = max(state["updatedAt"], m["asOf"])
        state["fetchedAt"] = cache.get("fetchedAt")
    # Trade-motorn: dagens värde, förslag och Sharpe. Handlar aldrig – förslaget godkänns med paper.bat.
    pf = state["portfolio"]
    pf["holdings"], pf["value"] = wp.valuation(pf, wp.prices_sek(m))
    daily = owner_cache.get("daily", {})
    pf["peak"] = max([pf["peak"], pf["value"], *daily.values()])
    flows = {h["date"]: h["flow"] for h in pf.get("history", []) if h.get("flow")}
    pf["sharpe"] = wp.sharpe({**daily, today: pf["value"]}, flows, pf.get("firstTrade"))
    state["proposal"] = wp.propose(state)
    if owner_cache.get("notis"):
        state["notis"] = owner_cache["notis"]  # morgon/kväll-notisen från walter_notis.py
    return state


def write_js(state):
    body = json.dumps(state, indent=2, ensure_ascii=False)
    OUT.write_text(
        "// GENERERAD av fetcher/walter_fetch.py – ändra inte här.\n"
        "// Journal, portfölj och mode redigeras i data/state.json, kör sedan hämtaren (eller --offline).\n"
        f"window.WALTER_STATE = {body};\n",
        encoding="utf-8",
    )


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.system("")  # slår på färger (ANSI) i Windows-terminalen
    ap = argparse.ArgumentParser(description="WALTER-hämtaren")
    ap.add_argument("--offline", action="store_true", help="hämta inget, bygg bara om state.js")
    args = ap.parse_args()

    state = read_json(BASE, None)
    if state is None:
        sys.exit(f"Hittar inte {BASE}")
    cache, owner = load_caches()
    ok = 0

    if not args.offline:
        load_env()
        print("WALTER hämtar data …")
        fresh, status = {}, {}
        for name, fn in SOURCES:
            try:
                fresh.update(fn())
                ok += 1
                status[name] = "ok"
                print(f"  OK   {name}")
            except Exception as e:
                status[name] = "fel"
                print(f"  FEL  {name}: {safe(e)}")
        if ok:
            cache["market"] = {**cache.get("market", {}), **fresh}
            cache["sources"] = status  # vilka källor som svarade vid senaste hämtningen
            cache["fetchedAt"] = datetime.now().isoformat(timespec="seconds")
            save_caches(cache, owner)

    state = build(state, cache, ok > 0, owner)
    write_js(state)
    snap = wpub.snapshot(state)
    if ok:
        cache["marketLog"] = wpub.append_log(cache.get("marketLog", []), snap)
        # dagens portföljvärde, för Sharpe (avkastning dag för dag)
        owner.setdefault("daily", {})[date.today().isoformat()] = state["portfolio"]["value"]
        save_caches(cache, owner)
    wpub.write_market_js(snap, cache.get("marketLog", []), MARKET_OUT)

    s = state["lampScore"]
    print(f"\n{s['red']}/{s['total']} röda lampor ({'data' if s['source'] == 'data' else 'från journalen'}).")
    p = state["proposal"]
    print(f"WALTER föreslår: {p['plain']}")
    if p.get("needsApproval"):
        print("Dubbelklicka paper.bat för att godkänna.")
    if not args.offline:
        print(f"{ok}/{len(SOURCES)} källor svarade.")
    print(f"Skrev {OUT} och {MARKET_OUT}")


if __name__ == "__main__":
    main()
