"""Lamporna historiskt – samma definitioner som fetcher/walter_fetch.lamp_updates, men bara värden med datum <= dagen.

lamps_on(day, series, thresholds) -> {lampId: "red" | "green" | None}
series: {namn: {ISO-datum: värde}} med namnen btc, spx, vix, dxy, us10y, btc_mvrvz, sopr, etf (se backtest/data.py).
Saknas en serie, är värdet för gammalt (lampMaxAgeDays) eller för kort historik -> None. KPI -> alltid None.
"""
from bisect import bisect_right
from datetime import date

LAMP_IDS = ["spx", "btcTrend", "btcWeek", "vix", "us10y", "dxy", "etf", "cpi", "mvrv", "sopr"]
# Publiceringsfördröjning i dagar (värdet daterat d syns först d+lag), mätt mot live-cachen okt 2026:
LAG_DAYS = {"btc_mvrvz": 1, "sopr": 7, "etf": 1}
DEFAULT_MAX_AGE = {"default": 4, "etf": 6, "mvrv": 10, "sopr": 10, "cpi": 35}
MIN_AVAILABLE = 4

_KEYS = {}


def _keys(s):
    """Sorterade datum för en serie, cachade (id + längd + kanter hindrar att en ändrad dict ger gamla svar)."""
    k = _KEYS.get(id(s))
    if k is None or k[0] is not s or k[1] != len(s):
        k = (s, len(s), sorted(s))
        _KEYS[id(s)] = k
    return k[2]


def _ord(iso):
    return date.fromisoformat(iso[:10]).toordinal()


def _visible(series, name, day):
    """[(datum, värde)] med datum <= dagen minus publiceringsfördröjning, äldst först – men som snabb vy:
    returnerar (datumlista, antal synliga, serie)."""
    s = series.get(name)
    if not s:
        return None
    cutoff = date.fromordinal(_ord(day) - LAG_DAYS.get(name, 0)).isoformat()
    ks = _keys(s)
    n = bisect_right(ks, cutoff)
    return (ks, n, s) if n else None


def _last(vis, k):
    """Sista k värdena (äldst först) eller None om det finns färre."""
    ks, n, s = vis
    if n < k:
        return None
    return [s[d] for d in ks[n - k:n]]


def _asof(vis):
    return vis[0][vis[1] - 1]


def lamps_on(day, series, thresholds, max_age=None):
    ages = max_age or DEFAULT_MAX_AGE
    out = {i: None for i in LAMP_IDS}
    red = lambda cond: "red" if cond else "green"

    def fresh(lamp, vis):
        limit = ages.get(lamp, ages.get("default", 4))
        return _ord(day) - _ord(_asof(vis)) <= limit

    def put(lamp, vis, fn):
        if vis is None or not fresh(lamp, vis):
            return
        r = fn()
        if r is not None:
            out[lamp] = r

    t = thresholds
    vis = _visible(series, "spx", day)
    def f_spx():
        c = _last(vis, t["spxMaDays"])
        return None if c is None else red(c[-1] < sum(c) / len(c))
    put("spx", vis, f_spx)

    vis = _visible(series, "btc", day)
    def f_trend():
        c = _last(vis, t["btcMaDays"])
        return None if c is None else red(c[-1] < sum(c) / len(c))
    put("btcTrend", vis, f_trend)
    def f_week():
        c = _last(vis, 8)  # som hämtaren: bp[-1] mot bp[-8]
        return None if c is None else red((c[-1] / c[0] - 1) * 100 < t["btcWeekDropPct"])
    put("btcWeek", vis, f_week)

    vis = _visible(series, "vix", day)
    put("vix", vis, lambda: red(vis[2][_asof(vis)] > t["vixAbove"]))

    vis = _visible(series, "us10y", day)
    def f_10y():
        ks, n, s = vis
        last_d = _ord(ks[n - 1])
        older = [i for i in range(n) if last_d - _ord(ks[i]) >= 30]  # som month_ago: senaste värdet >= 30 d äldre
        if not older:
            return None
        return red(s[ks[n - 1]] - s[ks[older[-1]]] > t["us10yRisePp"])
    put("us10y", vis, f_10y)

    vis = _visible(series, "dxy", day)
    def f_dxy():
        c = _last(vis, t["dxyMaDays"])
        return None if c is None else red(c[-1] > sum(c) / len(c))
    put("dxy", vis, f_dxy)

    vis = _visible(series, "etf", day)
    def f_etf():
        c = _last(vis, t["etfDays"])
        return None if c is None else red(sum(c) < 0)
    put("etf", vis, f_etf)

    # cpi: ingen gratis historik -> None

    vis = _visible(series, "btc_mvrvz", day)
    put("mvrv", vis, lambda: red(vis[2][_asof(vis)] > t["mvrvZ"]))

    vis = _visible(series, "sopr", day)
    def f_sopr():
        c = _last(vis, t["soprAvgDays"])
        return None if c is None else red(sum(c) / len(c) < t["sopr"])
    put("sopr", vis, f_sopr)
    return out


def score(lamps):
    """(röda av 10 | None, antal lampor med data). Andel röda bland de som har data × 10; None vid färre än 4."""
    have = [v for v in lamps.values() if v is not None]
    if len(have) < MIN_AVAILABLE:
        return None, len(have)
    return sum(v == "red" for v in have) / len(have) * 10, len(have)
