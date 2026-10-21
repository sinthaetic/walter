"""WALTER-hämtaren: hämtar gratis marknadsdata och skriver data/state.js.

  python fetcher/walter_fetch.py            hämta allt och bygg state.js
  python fetcher/walter_fetch.py --offline  bygg bara om state.js (t.ex. efter ny journalpost)

data/state.json är handredigerad (journal, portfölj, mode, regler) och skrivs aldrig av hämtaren.
data/cache.json minns senast hämtade värden, så att en källa som strular inte nollar något.
Mode ändras aldrig automatiskt – journalen är facit. Hämtaren räknar bara lamporna.
"""

import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "state.json"
CACHE = ROOT / "data" / "cache.json"
OUT = ROOT / "data" / "state.js"
ENV = Path(__file__).resolve().parent / ".env"

HTTP = requests.Session()
HTTP.headers["User-Agent"] = "WALTER/1.7 (paper trading)"
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
def yahoo(symbol):
    """Senaste och föregående dagsstängning från yfinance."""
    import yfinance as yf

    h = yf.Ticker(symbol).history(period="10d", interval="1d", auto_adjust=False).dropna(subset=["Close"])
    if len(h) < 2:
        raise ValueError(f"för lite data för {symbol}")
    last, prev = float(h["Close"].iloc[-1]), float(h["Close"].iloc[-2])
    return last, prev, h.index[-1].date().isoformat()


def fetch_indices():
    out = {}
    for key, sym in (("nasdaq", "^IXIC"), ("spx", "^GSPC"), ("dow", "^DJI")):
        last, prev, as_of = yahoo(sym)
        out[key] = {"changePct": round((last / prev - 1) * 100, 2), "asOf": as_of}
    return out


def fetch_vix():
    last, prev, as_of = yahoo("^VIX")
    return {"vix": {"value": round(last, 2), "changePct": round((last / prev - 1) * 100, 1), "asOf": as_of}}


def fetch_dxy():
    last, _, as_of = yahoo("DX-Y.NYB")
    return {"dxy": {"value": round(last, 3), "asOf": as_of}}


def fetch_us10y():
    """FRED DGS10 (officiellt API) i första hand, Yahoo ^TNX om FRED inte svarar."""
    try:
        (as_of, last), (_, prev) = fred_api("DGS10")
        src = "FRED"
    except Exception as e:
        if not os.environ.get("FRED_API_KEY"):
            warn("FRED_API_KEY saknas i fetcher/.env – 10-årig ränta tas från Yahoo ^TNX i stället.")
        else:
            print(f"    FRED svarade inte ({type(e).__name__}), tar ^TNX från Yahoo")
        last, prev, as_of = yahoo("^TNX")
        if last > 20:  # gammal Yahoo-skala (räntan × 10)
            last, prev = last / 10, prev / 10
        src = "Yahoo ^TNX"
    return {"us10y": {"value": round(last, 2), "changeBp": round((last - prev) * 100), "asOf": as_of, "source": src}}


def fetch_coingecko():
    btc = get_json("https://api.coingecko.com/api/v3/simple/price", params={"ids": "bitcoin", "vs_currencies": "usd"})
    chart = get_json("https://api.coingecko.com/api/v3/coins/ethereum/market_chart",
                     params={"vs_currency": "btc", "days": 30, "interval": "daily"})
    prices = [p for _, p in chart["prices"]]
    ma30 = sum(prices) / len(prices)
    return {
        "btc": {"value": round(btc["bitcoin"]["usd"]), "unit": "usd", "asOf": date.today().isoformat()},
        "ethBtc": {"value": round(prices[-1], 5), "ma30": round(ma30, 5)},
        "ethBtcAbove30dMa": prices[-1] > ma30,
    }


def fetch_bgeometrics():
    # Gratisnivån ligger ungefär en vecka efter – asOf visar vilken dag värdet gäller.
    z = get_json("https://bitcoin-data.com/v1/mvrv-zscore/last")
    s = get_json("https://bitcoin-data.com/v1/sopr/last")
    return {
        "mvrvZ": {"value": round(float(z["mvrvZscore"]), 2), "asOf": z["d"]},
        "sopr": {"value": round(float(s["sopr"]), 4), "asOf": s["d"]},
    }


def fred_api(series):
    """FRED:s officiella API (gratis nyckel FRED_API_KEY i fetcher/.env). Senaste två observationerna."""
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise RuntimeError("ingen FRED_API_KEY")
    data = get_json("https://api.stlouisfed.org/fred/series/observations",
                    params={"series_id": series, "api_key": key, "file_type": "json",
                            "sort_order": "desc", "limit": 10})
    obs = [(o["date"], float(o["value"])) for o in data["observations"] if o["value"] not in ("", ".")]
    return obs[0], obs[1]


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
            (as_of, v), _ = fred_api("DEXSDUS")
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
    return {"etfFlow": {"mtdUsd": round(mtd), "lastDayUsd": round(last_flow), "asOf": last}}


SOURCES = [
    ("Börsindex (yfinance)", fetch_indices),
    ("VIX (yfinance)", fetch_vix),
    ("Dollarindex (yfinance)", fetch_dxy),
    ("10-årig ränta (FRED / Yahoo ^TNX)", fetch_us10y),
    ("BTC + ETH/BTC (CoinGecko)", fetch_coingecko),
    ("USDSEK + EURSEK (Riksbanken)", fetch_fx),
    ("MVRV-Z + SOPR (BGeometrics)", fetch_bgeometrics),
    ("ETF-flöden (ByKaranteli)", fetch_etf),
]


# ---------- Lampor ----------
def lamp_updates(m, t):
    """id -> (status, värde). Saknas data för en lampa behålls den gamla."""
    out = {}
    red = lambda cond: "red" if cond else "green"

    for key in ("nasdaq", "spx", "dow"):
        c = m.get(key, {}).get("changePct")
        if c is not None:
            out[key] = (red(c < t["indexDropPct"]), pct(c))
    vix = m.get("vix", {})
    if vix.get("value") is not None and vix.get("changePct") is not None:
        out["vix"] = (red(vix["changePct"] > t["vixRisePct"]), f"{num(vix['value'], 2)} ({pct(vix['changePct'])})")
    if m.get("us10y", {}).get("value") is not None:
        v = m["us10y"]["value"]
        out["us10y"] = (red(v > t["us10y"]), num(v, 2) + " %")
    if m.get("dxy", {}).get("value") is not None:
        v = m["dxy"]["value"]
        out["dxy"] = (red(v > t["dxy"]), num(v, 2))
    etf = m.get("etfFlow", {})
    if etf.get("asOf") and etf.get("mtdUsd") is not None:
        v = etf["mtdUsd"]
        sign = "−" if v < 0 else "+"
        out["etf"] = (red(v < 0), f"{sign}${num(abs(v) / 1e6)}M i {MONTHS[int(etf['asOf'][5:7]) - 1]}")
    if m.get("mvrvZ", {}).get("value") is not None:
        v = m["mvrvZ"]["value"]
        out["mvrv"] = (red(v > t["mvrvZ"]), f"{num(v, 2)} ({day(m['mvrvZ']['asOf'])})")
    if m.get("sopr", {}).get("value") is not None:
        v = m["sopr"]["value"]
        out["sopr"] = (red(v < t["sopr"]), f"{num(v, 3)} ({day(m['sopr']['asOf'])})")
    # KPI (utfall mot förväntan) finns inte gratis – den lampan sköts för hand i state.json.
    return out


# ---------- Bygg ----------
def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def build(state, cache, fetched_any):
    m = state["market"]
    m.update(cache.get("market", {}))

    if len(state["lamps"]) != 10:
        warn(f"state.json har {len(state['lamps'])} lampor – WALTER räknar med exakt 10. Rätta i state.json.")
    upd = lamp_updates(m, state["rules"]["lampThresholds"])
    for lamp in state["lamps"]:
        if lamp["id"] in upd:
            lamp["status"], lamp["value"] = upd[lamp["id"]]

    today = date.today().isoformat()
    # Datan tar över poängen först när alla lampor har ett värde, annars gäller journalens.
    if fetched_any or cache.get("market"):
        if all(l["status"] is not None for l in state["lamps"]):
            red = sum(l["status"] == "red" for l in state["lamps"])
            state["lampScore"] = {"red": red, "total": len(state["lamps"]),
                                  "asOf": cache.get("fetchedAt", today)[:10], "source": "data"}
        m["asOf"] = cache.get("fetchedAt", today)[:10]
        state["updatedAt"] = max(state["updatedAt"], m["asOf"])
        state["fetchedAt"] = cache.get("fetchedAt")
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
    cache = read_json(CACHE, {})
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
            CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")

    state = build(state, cache, ok > 0)
    write_js(state)

    s = state["lampScore"]
    print(f"\n{s['red']}/{s['total']} röda lampor ({'data' if s['source'] == 'data' else 'från journalen'}).")
    if s["source"] == "data":
        wants_park = s["red"] >= state["rules"]["parkeraAtRed"]
        if wants_park != (state["mode"] == "PARKERA"):
            print(f"OBS: datan säger {'PARKERA' if wants_park else 'inte längre PARKERA'}, "
                  f"men journalen säger {state['mode']}. Skriv en journalpost när du bestämt dig.")
    if not args.offline:
        print(f"{ok}/{len(SOURCES)} källor svarade.")
    print(f"Skrev {OUT}")


if __name__ == "__main__":
    main()
