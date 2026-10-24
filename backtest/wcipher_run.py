"""Steg 10 del 5: tjänar W-Cipher-signalerna pengar efter avgifter och svensk skatt? Och ska de styra en satellit?

  .venv\\Scripts\\python.exe -m backtest.wcipher_run      # några sekunder, alla kärnor -> backtest/cache/del5.json

Förregistrerat (inga fler inställningar än de här):
  Signaler: backtest/wcipher.py = js/wcipher.js, standardparametrarna, på BTC/USD från Bitstamp (dag och 4 timmar).
  Varianter (köp-signaler -> ut-signaler):
    bas       kop, guld -> salj, blod
    stora     alla stora: kop, guld, div_upp -> salj, blod, div_ned
    kop_salj  kop, guld -> salj           (guld är en djupare kop, så den räknas som kop)
    blod_ut   kop, guld -> blod
  Lägen:
    long   (spot): köp-signal = allt i BTC, ut-signal = allt till kontant. Kraken-lik börs, som autopiloten.
    ls     (terminer, 1x): köp-signal = lång, ut-signal = kort (vänder). Avgift 0,05 % + glidning 0,05 % per affär,
           finansiering 0,01 % per 8 timmar på positionen, betalas av både långa och korta (försiktigt antagande).
  Utförande: signalen på stapel i (vid stängning) handlas på stapel i+1:s ÖPPNING. Ingen titt framåt.
  Start: utan position, första signalen avgör. Sista stapeln: allt stängs, skatt, uttag till svensk bank.
  Skatt: TaxBook-reglerna (30 %, förluster 70 %, genomsnittsmetoden). Terminer förenklas: varje stängd position är en
    vinst eller förlust (efter avgifter och finansiering) som för krypto. Skatten betalas från kontot året efter.
  Satellit: X % (10, 20) av startkapitalet till den bästa varianten på 2014-2019, resten = autopiloten (live-koden).
    De två delarna ombalanseras aldrig mot varandra. Skatten räknas per del (summan blir densamma som för en person
    så länge ett års underskott är under 100 000 kr; skillnaden är bara när skatten betalas).
Metod: varianterna väljs på 2014-2019, kontrolleras oförändrade på 2020-idag. Startdatum varje kvartal 2014-2024.
"""
import json
import statistics
import sys
from bisect import bisect_left, bisect_right
from datetime import date
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest import candles, data, run, sim, wcipher  # noqa: E402
from backtest.costs import KRAKEN, Exchange, TaxBook  # noqa: E402

TRAIN, TEST, FULL = run.TRAIN, run.TEST, run.FULL
VARIANTS = {
    "bas": ({"kop", "guld"}, {"salj", "blod"}),
    "stora": ({"kop", "guld", "div_upp"}, {"salj", "blod", "div_ned"}),
    "kop_salj": ({"kop", "guld"}, {"salj"}),
    "blod_ut": ({"kop", "guld"}, {"blod"}),
}
TFS = ("1d", "4h")
HOURS = {"1d": 24, "4h": 4}
FUT_FEE = (0.05 + 0.05) / 100       # taker + glidning per affär
FUNDING_8H = 0.01 / 100              # per 8 timmar, på positionens värde
MAINT = 0.005                        # underhållsmarginal (likvidation), andel av positionens värde
# Terminsbörsen: samma växling och SEPA som Kraken-lik (pengarna in och ut går samma väg).
FUTURES = Exchange("Terminer (1x)", 0.05, 0.05, "EUR", 1.0, 10.0)
SATELLITE = (0.10, 0.20)


# ---------- Marknaden: ljus, signaler och växelkurs ----------
class Tape:
    """Ett ljusflöde med signaler och dagens växelkurs (EUR per USD, SEK per EUR), allt förberäknat."""

    def __init__(self, tf, series, bars=None):
        self.tf = tf
        bars = bars if bars is not None else candles.load(tf)
        res = wcipher.compute(bars)
        self.days = [candles.day_of(b["time"]) for b in bars]
        self.o = [b["open"] for b in bars]
        self.h = [b["high"] for b in bars]
        self.lo = [b["low"] for b in bars]
        self.c = [b["close"] for b in bars]
        self.kinds = {}
        for s in res["signals"]:
            self.kinds.setdefault(s["i"], set()).add(s["kind"])
        usdsek, eursek = sim._Asof(series["usdsek"]), sim._Asof(series["eursek"])
        self.fx = {}  # dag -> (EUR per USD, SEK per EUR)
        for d in sorted(set(self.days)):
            u, e = usdsek(d), eursek(d)
            self.fx[d] = (u / e, e) if u and e else None

    def target(self, i, variant, mode):
        """Önskad position efter stapel i: 1 lång, 0 kontant, -1 kort, None = ingen ny signal."""
        k = self.kinds.get(i)
        if not k:
            return None
        buy, sell = VARIANTS[variant]
        b, s = bool(k & buy), bool(k & sell)
        if b == s:
            return None  # ingen signal, eller båda på samma stapel: gör inget
        if b:
            return 1
        return -1 if mode == "ls" else 0

    def span(self, start, end):
        return bisect_left(self.days, start), bisect_right(self.days, end)


# ---------- Körningen ----------
def run_wc(tape, variant, mode, start, end, start_sek=100000, exchange=KRAKEN):
    """En W-Cipher-variant från start till end. Returnerar sim.Result + extra (trade-statistik)."""
    ex = FUTURES if mode == "ls" else exchange
    fee = FUT_FEE if mode == "ls" else exchange.trade_fee
    fund = FUNDING_8H * HOURS[tape.tf] / 8
    a, b = tape.span(start, end)
    a = next(i for i in range(a, b) if tape.fx[tape.days[i]])
    res = sim.Result(f"W-Cipher {variant} {mode} {tape.tf}", tape.days[a], tape.days[b - 1], start_sek=start_sek)
    book = TaxBook()
    q, rate = tape.fx[tape.days[a]]
    cash = ex.deposit(start_sek, rate)
    res.fees_sek += start_sek - cash * rate
    pos = 0            # 1 lång, -1 kort, 0 inget
    units = 0.0
    entry = None       # {"i", "px", "equity", "cost_sek"}
    pending = None
    paid = set()
    last_year = int(tape.days[a][:4])
    trips, bars_in, worst_adverse = [], 0, 0.0
    dead = False
    res.extra_liq = []
    first_year = last_year
    fx_last = (q, rate)

    def px_q(price_usd, d):
        return price_usd * fxd(d)[0]

    def fxd(d):
        nonlocal fx_last
        v = tape.fx.get(d)
        if v:
            fx_last = v
        return fx_last

    def equity(p):
        if mode == "ls" and pos:
            return cash + pos * units * (p - entry["px"])
        return cash + units * p

    def close(i, p, d, why):
        nonlocal cash, units, pos, entry
        rate_ = fxd(d)[1]
        if mode == "ls":
            pnl = pos * units * (p - entry["px"])
            f = units * p * fee
            cash += pnl - f
            result = pnl * rate_ - f * rate_ - entry["cost_sek"]
            ret = (pnl - f - entry["cost_q"]) / entry["equity"]
            _realize(book, d, result)
            res.fees_sek += f * rate_
        else:
            gross = units * p
            f = gross * fee
            cash += gross - f
            book.sell(d, "BTC", units, (gross - f) * rate_)
            res.fees_sek += f * rate_
            ret = p / entry["px"] * (1 - fee) ** 2 - 1
        res.trades.append({"date": d, "side": "stäng", "why": why})
        trips.append({"side": pos, "ret": ret, "bars": i - entry["i"],
                      "day": entry["day"]})
        units, pos, entry = 0.0, 0, None

    def open_(i, p, d, side):
        nonlocal cash, units, pos, entry
        rate_ = fxd(d)[1]
        eq = cash
        if mode == "ls":
            f = eq * fee
            units = eq / p
            cash -= f
            entry = {"i": i, "px": p, "equity": eq, "cost_sek": f * rate_, "cost_q": f, "day": d}
        else:
            f = eq * fee
            units = (eq - f) / p
            book.buy("BTC", units, eq * rate_)
            cash = 0.0
            entry = {"i": i, "px": p, "equity": eq, "cost_sek": 0.0, "day": d}
        res.fees_sek += f * rate_
        pos = side
        res.trades.append({"date": d, "side": "lång" if side > 0 else "kort", "why": "signal"})

    def liquidated(i, worst, d):
        """1x: en kort position likvideras när priset nästan fördubblats (underhållsmarginal MAINT). Allt
        kollateral är då borta. En lång 1x-position likvideras först nära noll."""
        nonlocal cash, units, pos, entry, dead
        eq = cash + pos * units * (worst - entry["px"])
        if eq > MAINT * units * worst:
            return False
        rate_ = fxd(d)[1]
        _realize(book, d, -cash * rate_ - entry["cost_sek"])
        res.trades.append({"date": d, "side": "likviderad", "why": "likvidation"})
        trips.append({"side": pos, "ret": -1.0, "bars": i - entry["i"], "day": entry["day"]})
        res.extra_liq.append(d)
        cash, units, pos, entry, dead = 0.0, 0.0, 0, None, True
        return True

    def pay_tax(i, d, year):
        nonlocal cash, units
        tax = book.tax(year)
        paid.add(year)
        if tax <= 0:
            if book.credit(year) > 0:
                res.credits[year] = book.credit(year)
            return
        rate_ = fxd(d)[1]
        need = ex.quote_for_sek(tax, rate_)
        if mode != "ls" and pos and cash < need:  # spot: sälj en bit BTC
            p = px_q(tape.o[i], d)
            sell = min(units, (need - cash) / (p * (1 - fee)) * 1.0001)
            gross = sell * p
            cash += gross * (1 - fee)
            book.sell(d, "BTC", sell, gross * (1 - fee) * rate_)
            res.fees_sek += gross * fee * rate_
            units -= sell
        cash -= need
        res.taxes[year] = tax
        res.fees_sek += need * rate_ - tax

    for i in range(a, b):
        d = tape.days[i]
        q_, rate_ = fxd(d)
        p_open = tape.o[i] * q_
        if pending is not None and pending != pos:
            if pos:
                close(i, p_open, d, "signal")
            if pending and not dead and cash > 0:
                open_(i, p_open, d, pending)
        pending = None
        y = int(d[:4])
        if y > last_year:
            for yy in range(first_year, y):
                if yy not in paid:
                    pay_tax(i, d, yy)
            last_year = y
        p = tape.c[i] * q_
        if pos:
            bars_in += 1
            hi, lo = tape.h[i] * q_, tape.lo[i] * q_
            adverse = (entry["px"] - lo) / entry["px"] if pos > 0 else (hi - entry["px"]) / entry["px"]
            worst_adverse = max(worst_adverse, adverse)
            if mode == "ls" and liquidated(i, hi if pos < 0 else lo, d):
                pass
            elif mode == "ls":
                f = units * p * fund
                cash -= f
                entry["cost_sek"] += f * rate_
                entry["cost_q"] += f
                res.fees_sek += f * rate_
        res.daily[d] = equity(p) * rate_
        res.tax_out[d] = res.tax_sek
        if i == b - 1:
            break
        t = tape.target(i, variant, mode)
        if t is not None:
            pending = t

    d = tape.days[b - 1]
    if pos:
        close(b - 1, tape.c[b - 1] * fxd(d)[0], d, "slut")
    tax_left = 0.0
    for yy in range(first_year, int(d[:4]) + 1):
        if yy in paid:
            continue
        t = book.tax(yy)
        if t > 0:
            res.taxes[yy] = t
            tax_left += t
        elif book.credit(yy) > 0:
            res.credits[yy] = book.credit(yy)
    bank, wfee = ex.withdraw(cash, fxd(d)[1])
    res.fees_sek += wfee
    res.final_sek = bank - tax_left + res.credit_sek
    res.extra = {"liquidations": res.extra_liq, "trips": trips, "time_in": bars_in / max(1, b - a), "worst_adverse": worst_adverse,
                 "years": (date.fromisoformat(res.end) - date.fromisoformat(res.start)).days / 365.25}
    return res


def _realize(book, day, result):
    y = int(day[:4])
    if result >= 0:
        book.gains[y] = book.gains.get(y, 0) + result
    else:
        book.losses[y] = book.losses.get(y, 0) - result
    book.sales.append((day, "BTC-termin", 0, 0, 0, result))


def combine(core, sat, name):
    """Kärna + satellit som en portfölj: dagsvärden summeras (satelliten bär senaste värdet framåt)."""
    out = sim.Result(name, core.start, core.end, start_sek=core.start_sek + sat.start_sek)
    last_v, last_t = 0.0, 0.0
    sd = sorted(sat.daily)
    j = 0
    for d in sorted(core.daily):
        while j < len(sd) and sd[j] <= d:
            last_v, last_t = sat.daily[sd[j]], sat.tax_out.get(sd[j], 0)
            j += 1
        out.daily[d] = core.daily[d] + last_v
        out.tax_out[d] = core.tax_out.get(d, 0) + last_t
    out.final_sek = core.final_sek + sat.final_sek
    out.fees_sek = core.fees_sek + sat.fees_sek
    for k in set(core.taxes) | set(sat.taxes):
        out.taxes[k] = core.taxes.get(k, 0) + sat.taxes.get(k, 0)
    for k in set(core.credits) | set(sat.credits):
        out.credits[k] = core.credits.get(k, 0) + sat.credits.get(k, 0)
    out.trades = core.trades + sat.trades
    return out


# ---------- Sammanfattning ----------
def summary(r):
    e = getattr(r, "extra", None) or {}
    yrs = (date.fromisoformat(r.end) - date.fromisoformat(r.start)).days / 365.25
    out = {"name": r.strategy, "start": r.start, "end": r.end, "bank": r.final_sek, "dd": r.max_dd,
           "trades": r.n_trades, "fees": r.fees_sek, "tax": r.tax_sek, "credit": r.credit_sek, "years": yrs,
           "cagr": r.cagr}
    if e:
        tr = e["trips"]
        wins = [t["ret"] for t in tr if t["ret"] > 0]
        loss = [t["ret"] for t in tr if t["ret"] <= 0]
        out.update(liquidations=e["liquidations"], time_in=e["time_in"], worst_adverse=e["worst_adverse"], trips=len(tr),
                   win_rate=len(wins) / len(tr) if tr else None,
                   avg_win=statistics.mean(wins) if wins else None,
                   avg_loss=statistics.mean(loss) if loss else None,
                   per_year=len(tr) / yrs if yrs else None)
    return out


def yearly(r):
    """Avkastning per kalenderår på börsen (före slutskatt; skatt som dragits räknas tillbaka)."""
    by = {}
    for d in sorted(r.daily):
        by.setdefault(d[:4], []).append(r.daily[d] + r.tax_out.get(d, 0))
    out, prev = {}, None
    for y in sorted(by):
        first = prev if prev is not None else by[y][0]
        out[y] = by[y][-1] / first - 1 if first > 0 else None
        prev = by[y][-1]
    return out


# ---------- Parallellt ----------
_S, _T = None, None


def _init():
    global _S, _T
    _S = data.load_all()
    _T = {tf: Tape(tf, _S) for tf in TFS}


def _job(job):
    tag, kind, args = job
    if kind == "wc":
        tf, variant, mode, start, end, sek = args
        r = run_wc(_T[tf], variant, mode, start, end, sek)
    elif kind == "sim":
        st, start, end, sek = args
        r = sim.run(st, start, end, KRAKEN, start_sek=sek, series=_S)
    else:  # satellit: W-Cipher-varianten, eller (kontroll) samma andel bara köpt BTC som ligger kvar
        tf, variant, mode, start, end, share = args
        core = sim.run(sim.autopilot(), start, end, KRAKEN, start_sek=100000 * (1 - share), series=_S)
        if kind == "satctl":
            sat = sim.run(sim.hold_btc(1.0), start, end, KRAKEN, start_sek=100000 * share, series=_S)
        else:
            sat = run_wc(_T[tf], variant, mode, start, end, 100000 * share)
        r = combine(core, sat, f"Satellit {share:.0%} {variant} {mode} {tf}")
    s = summary(r)
    if start in (TRAIN[0], TEST[0]):
        s["yearly"] = yearly(r)
    return tag, s


def benchmarks():
    return {"Autopiloten (live)": sim.autopilot(),
            "BTC 35 % ombalanserad": sim.mix({"BTC": 0.35}, name="BTC 35 % ombalanserad"),
            "Köp och behåll BTC 100 %": sim.hold_btc(1.0)}


def stats(rows):
    b = [x["bank"] for x in rows]
    return {"median": statistics.median(b), "p10": statistics.quantiles(b, n=10, method="inclusive")[0],
            "worst": min(b), "max_dd": max(x["dd"] for x in rows), "median_dd": statistics.median(x["dd"] for x in rows),
            "trades": statistics.median(x["trades"] for x in rows), "fees": statistics.median(x["fees"] for x in rows),
            "tax": statistics.median(x["tax"] for x in rows),
            "time_in": statistics.median(x["time_in"] for x in rows) if "time_in" in rows[0] else None,
            "below": sum(x < 100000 for x in b), "n": len(rows)}


def main():
    out = {}
    end = FULL[1]
    with Pool(initializer=_init) as pool:
        out["coverage"] = [candles.coverage(candles.load(tf), tf) for tf in TFS]
        wcs = [(tf, v, m) for tf in TFS for v in VARIANTS for m in ("long", "ls")]
        bench = benchmarks()

        # 1. Perioderna: inställning 2014-2019, kontroll 2020-idag, hela
        jobs = [((tf, v, m, per), "wc", (tf, v, m, a, b_, 100000))
                for tf, v, m in wcs for per, (a, b_) in (("train", TRAIN), ("test", TEST), ("full", FULL))]
        jobs += [((n, per), "sim", (st, a, b_, 100000))
                 for n, st in bench.items() for per, (a, b_) in (("train", TRAIN), ("test", TEST), ("full", FULL))]
        per = dict(pool.imap(_job, jobs, chunksize=2))
        out["periods"] = {"|".join(k): v for k, v in per.items()}

        # 2. Val på inställningsperioden: bästa long och bästa ls (kr på banken 2014-2019)
        best = {}
        for m in ("long", "ls"):
            best[m] = max(((tf, v, m) for tf, v, mm in wcs if mm == m), key=lambda k: per[k + ("train",)]["bank"])
        best["sat"] = max((best["long"], best["ls"]), key=lambda k: per[k + ("train",)]["bank"])
        out["best"] = {k: list(v) for k, v in best.items()}
        print("valt på 2014-2019:", out["best"])

        # 3. Startdatum varje kvartal till idag
        qs = run.quarters()
        jobs = [(("wc", tf, v, m, q), "wc", (tf, v, m, q, end, 100000)) for tf, v, m in wcs for q in qs]
        jobs += [(("sim", n, q), "sim", (st, q, end, 100000)) for n, st in bench.items() for q in qs]
        for kind in ("sat", "satctl"):
            jobs += [((kind, f"{s:.2f}", q), kind, best["sat"] + (q, end, s)) for s in SATELLITE for q in qs]
            # i perioderna också
            jobs += [(("satp", f"{kind} {s:.2f}", p_), kind, best["sat"] + (a, b_, s))
                     for s in SATELLITE for p_, (a, b_) in (("train", TRAIN), ("test", TEST))]
        starts = dict(pool.imap(_job, jobs, chunksize=2))

    groups = {}
    for k, v in starts.items():
        if k[0] == "satp":
            out.setdefault("sat_periods", {})[f"{k[1]}|{k[2]}"] = v
            continue
        name = "|".join(k[1:-1]) if k[0] in ("wc", "sim") else f"{k[0]} {k[1]}"
        groups.setdefault(name, []).append(dict(v, q=k[-1]))
    out["starts"] = {n: {"alla": stats(v), "från2020": stats([x for x in v if x["q"] >= "2020"])}
                     for n, v in groups.items()}
    path = ROOT / "backtest" / "cache" / "del5.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("skrev", path)
    report(out)
    return out


def fmt(x):
    return "–" if x is None else f"{x:,.0f}".replace(",", " ")


def pct(x, d=0):
    return "–" if x is None else f"{x * 100:.{d}f} %"


def report(out):
    P = out["periods"]
    print("\n## Alla varianter (kr på banken per 100 000 kr)")
    print("| Variant | 2014–2019 | 2020–idag | DD 14–19 | DD 20– | Affärer/år | Träff | Snitt vinst | Snitt förlust |"
          " Tid i marknad | Värsta motrörelse |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for key in sorted({k.rsplit("|", 1)[0] for k in P}):
        tr, te, fu = P[key + "|train"], P[key + "|test"], P[key + "|full"]
        print(f"| {key} | {fmt(tr['bank'])} | {fmt(te['bank'])} | {pct(tr['dd'])} | {pct(te['dd'])} | "
              + (f"{fu['per_year']:.1f} | {pct(fu['win_rate'])} | {pct(fu['avg_win'], 1)} | {pct(fu['avg_loss'], 1)} | "
                 f"{pct(fu['time_in'])} | {pct(fu['worst_adverse'])} |" if "trips" in fu else "– | – | – | – | – | – |"))
    print("\n## Startdatum (44 starter / 20 från 2020)")
    print("| Strategi | Median | 10 % sämsta | Största DD | Median 2020– | 10 % sämsta 2020– | DD 2020– | Affärer | "
          "Avgifter | Skatt | Tid i marknad |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for n, v in out["starts"].items():
        a, f = v["alla"], v["från2020"]
        print(f"| {n} | {fmt(a['median'])} | {fmt(a['p10'])} | {pct(a['max_dd'])} | {fmt(f['median'])} | "
              f"{fmt(f['p10'])} | {pct(f['max_dd'])} | {a['trades']:.0f} | {fmt(a['fees'])} | {fmt(a['tax'])} | "
              f"{pct(a['time_in'])} |")
    print("\n## Per kalenderår (avkastning på börsen, före slutskatt), start 2014")
    keys = [k for k in P if k.endswith("|full") and "yearly" in P[k]]
    years = sorted(P[keys[0]]["yearly"])
    print("| Variant | " + " | ".join(years) + " |\n|---|" + "---|" * len(years))
    for k in keys:
        yv = P[k]["yearly"]
        print(f"| {k[:-5]} | " + " | ".join(pct(yv.get(y)) for y in years) + " |")
    print("\nSatellit i perioderna:", {k: fmt(v["bank"]) for k, v in out.get("sat_periods", {}).items()})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--report" in sys.argv:
        report(json.loads((ROOT / "backtest" / "cache" / "del5.json").read_text(encoding="utf-8")))
    else:
        main()
