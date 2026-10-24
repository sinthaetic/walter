"""W-Cipher i Python: en trogen kopia av js/wcipher.js compute() (samma parametrar, uppvärmning och signalregler),
för historiktestet. Paritetstest: tests/js/wcipher.test.js mot tests/fixtures/wcipher-bars.json (make_fixtures.py).

  compute(bars) -> {"wt1", "wt2", "rsi", ..., "signals": [{"i", "time", "kind", "side", "big"}], ...}

bars: [{"time", "open", "high", "low", "close"}], äldst först. Allt är kausalt: signalen på stapel i använder bara
staplar <= i (fraktalerna tittar två staplar bakåt), så den kan handlas först på nästa stapels öppning.
Ändras js/wcipher.js ska den här filen ändras likadant (och fixturen göras om).
"""

PARAMS = {
    "chan": 9, "avg": 12, "ma": 3,
    "zone": 60, "deep": 75,
    "divTop": 45, "divBottom": -65,
    "mfiLen": 60, "mfiMult": 150, "mfiY": 2.5,
    "rsiLen": 14, "rsiLow": 30,
    "stochLen": 14, "stochK": 3, "stochD": 3,
    "ribbon": [5, 11, 15, 18, 21, 24, 28, 34],
    "warmup": 60,
}

KINDS = {  # side, big (samma som KINDS i js/wcipher.js)
    "kop": ("buy", True), "salj": ("sell", True), "guld": ("buy", True),
    "liten_upp": ("buy", False), "liten_ned": ("sell", False),
    "div_upp": ("buy", True), "div_ned": ("sell", True),
    "trend_upp": ("buy", False), "trend_ned": ("sell", False),
    "blod": ("sell", True),
}


def ema(xs, n):
    k, out = 2 / (n + 1), []
    for i, x in enumerate(xs):
        out.append(x if i == 0 else x * k + out[i - 1] * (1 - k))
    return out


def sma(xs, n):
    out, s = [], 0.0
    for i, x in enumerate(xs):
        s += x
        if i >= n:
            s -= xs[i - n]
        out.append(s / min(i + 1, n))
    return out


def rma(xs, n):
    out = []
    for i, x in enumerate(xs):
        out.append(x if i == 0 else (out[i - 1] * (n - 1) + x) / n)
    return out


def rsi(c, n):
    up, dn = [0], [0]
    for i in range(1, len(c)):
        d = c[i] - c[i - 1]
        up.append(max(d, 0))
        dn.append(max(-d, 0))
    u, d = rma(up, n), rma(dn, n)
    return [100 if d[i] == 0 else 100 - 100 / (1 + x / d[i]) for i, x in enumerate(u)]


def stoch(xs, n):
    out = []
    for i, x in enumerate(xs):
        w = xs[max(0, i - n + 1):i + 1]
        lo, hi = min(w), max(w)
        out.append(50 if hi == lo else (x - lo) / (hi - lo) * 100)
    return out


def _cross_up(a, b, i):
    return a[i - 1] < b[i - 1] and a[i] >= b[i]


def _cross_down(a, b, i):
    return a[i - 1] > b[i - 1] and a[i] <= b[i]


def compute(bars, p=None):
    p = p or PARAMS
    n = len(bars)
    O = [b["open"] for b in bars]
    H = [b["high"] for b in bars]
    L = [b["low"] for b in bars]
    C = [b["close"] for b in bars]

    ap = [(H[i] + L[i] + C[i]) / 3 for i in range(n)]
    esa = ema(ap, p["chan"])
    d = ema([abs(a - esa[i]) for i, a in enumerate(ap)], p["chan"])
    wt1 = ema([(a - esa[i]) / ((0.015 * d[i]) or 1) for i, a in enumerate(ap)], p["avg"])
    wt2 = sma(wt1, p["ma"])
    mfi = [v - p["mfiY"] for v in
           sma([(C[i] - O[i]) / ((H[i] - L[i]) or 1) * p["mfiMult"] for i in range(n)], p["mfiLen"])]
    r = rsi(C, p["rsiLen"])
    k = sma(stoch(r, p["stochLen"]), p["stochK"])

    ribbon = [ema(C, ln) for ln in p["ribbon"]]
    e1, e2, e8 = ribbon[0], ribbon[1], ribbon[7]

    signals, divergences = [], []

    def add(i, kind):
        side, big = KINDS[kind]
        signals.append({"i": i, "time": bars[i]["time"], "kind": kind, "side": side, "big": big})

    last_top, last_bottom = -1, -1
    for i in range(max(4, p["warmup"]), n):
        up, dn = _cross_up(wt1, wt2, i), _cross_down(wt1, wt2, i)
        if up:
            add(i, "guld" if wt2[i] <= -p["deep"] and r[i] < p["rsiLow"] else "kop" if wt2[i] <= -p["zone"]
                else "liten_upp")
        if dn:
            add(i, "salj" if wt2[i] >= p["zone"] else "liten_ned")
        if _cross_up(e2, e8, i):
            add(i, "trend_upp")
        if _cross_up(e8, e2, i):
            add(i, "trend_ned")
        if dn and wt2[i] > 0 and _cross_down(e1, e2, i):
            add(i, "blod")

        f = i - 2
        top = wt2[i - 4] < wt2[f] and wt2[i - 3] < wt2[f] and wt2[f] > wt2[i - 1] and wt2[f] > wt2[i]
        bottom = wt2[i - 4] > wt2[f] and wt2[i - 3] > wt2[f] and wt2[f] < wt2[i - 1] and wt2[f] < wt2[i]
        if top:
            if last_top >= 0 and wt2[f] >= p["divTop"] and wt2[f] < wt2[last_top] and H[f] > H[last_top]:
                divergences.append({"side": "sell", "from": last_top, "to": f})
                add(i, "div_ned")
            last_top = f
        if bottom:
            if last_bottom >= 0 and wt2[f] <= p["divBottom"] and wt2[f] > wt2[last_bottom] and L[f] < L[last_bottom]:
                divergences.append({"side": "buy", "from": last_bottom, "to": f})
                add(i, "div_upp")
            last_bottom = f

    return {"params": p, "wt1": wt1, "wt2": wt2, "mfi": mfi, "rsi": r, "stochK": k, "ribbon": ribbon,
            "signals": signals, "divergences": divergences}
