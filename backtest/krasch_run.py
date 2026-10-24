"""Steg 10 del 6: krasch-broms (A), nödjustering mellan söndagar (B) och båda (C) mot autopiloten.

  .venv\\Scripts\\python.exe -m backtest.krasch_run    # några minuter, alla kärnor -> backtest/cache/del6.json

Förregistrerat rutnät (bestämt innan något kördes):
  A: stop_pct X in {15, 20, 25, 30, 40} %  x  återköp över N-dagarssnitt N in {50, 100, 200}.  BTC och ETH var för sig.
  B: emergency_pp Y in {10, 15, 20} procentenheter (söndagens 5 %-band kvar).
  C: A x B (hela rutnätet, 45 celler).
Val bara på 2014-2019: kvartalsstarter 2014-01..2018-10 med slut 2019-12-31 (20 starter, minst ett år var).
Kontroll oförändrad: kvartalsstarter 2020-01..2024-10 med slut idag (20 starter), samt de vanliga 44 starterna
2014-2024 till idag och de två enkla körningarna 2014-2019 och 2020-idag. Kraken-lik börs, svensk skatt.
Platå = alla grannar (ett steg i X, N eller Y) inom 15 % av cellen i median och 10 % sämsta (inställningsstarterna).
Bästa platå = högsta sämsta-p10 i grannskapet, sedan sämsta median (samma regel som del 3b).
Kraschfönster (körning från 2014-01-01): största fall topp -> botten inom fönstret och dagar från toppen tills
värdet är tillbaka (skatt som betalats räknas tillbaka, som i max_dd).
"""
import copy
import json
import statistics
import sys
from datetime import date
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest import run, sim  # noqa: E402
from backtest.costs import KRAKEN  # noqa: E402

XS = (15, 20, 25, 30, 40)
NS = (50, 100, 200)
YS = (10, 15, 20)
TOL = 0.15
TIE = 0.05
END = run.FULL[1]
TRAIN_STARTS = [q for q in run.quarters(2014, 2018)]
TEST_STARTS = [q for q in run.quarters(2020, 2024)]
ALL_STARTS = run.quarters()
WINDOWS = {"2018 (topp dec 2017)": ("2017-12-01", "2018-12-31"),
           "mars 2020": ("2020-02-01", "2020-04-30"),
           "2022 (topp nov 2021)": ("2021-10-01", "2022-12-31")}


def strat(x=0, n=200, y=0):
    if not x and not y:
        return sim.autopilot(name="Autopiloten (live)")
    bits = ([f"broms {x} %/snitt {n}"] if x else []) + ([f"nöd {y} pp"] if y else [])
    return sim.Strategy(name=" + ".join(bits), rules=copy.deepcopy(sim.AUTOPILOT_RULES),
                        stop_pct=x, stop_ma_days=n, emergency_pp=y)


def cells():
    out = {("auto", 0, 0, 0): strat()}
    out.update({("A", x, n, 0): strat(x, n) for x in XS for n in NS})
    out.update({("B", 0, 0, y): strat(y=y) for y in YS})
    out.update({("C", x, n, y): strat(x, n, y) for x in XS for n in NS for y in YS})
    return out


def _job(job):
    key, st, start, end = job
    r = sim.run(st, start, end, KRAKEN, series=run._S, lamp_cache=run._C)
    out = {"bank": r.final_sek, "dd": r.max_dd, "trades": r.n_trades, "fees": r.fees_sek, "tax": r.tax_sek,
           "stops": sum(1 for s in r.stops if s[2] == "ut")}
    if start == "2014-01-01" and end == END:
        out["windows"] = windows(r)
    return key, start, end, out


def windows(r):
    v = {d: r.daily[d] + r.tax_out.get(d, 0) for d in r.daily}
    ds = sorted(v)
    out = {}
    for name, (w0, w1) in WINDOWS.items():
        inside = [d for d in ds if w0 <= d <= w1]
        best = (0.0, None, None)
        pk = None
        for d in inside:
            if pk is None or v[d] > v[pk]:
                pk = d
            dd = 1 - v[d] / v[pk]
            if dd > best[0]:
                best = (dd, pk, d)
        dd, pk, tr = best
        rec = next((d for d in ds if d > tr and v[d] >= v[pk]), None) if tr else None
        out[name] = {"dd": dd, "peak": pk, "trough": tr, "recovered": rec,
                     "days": (date.fromisoformat(rec) - date.fromisoformat(pk)).days if rec else None}
    return out


def p10(v):
    return statistics.quantiles(v, n=10, method="inclusive")[0]


def agg(rows):
    b = [r["bank"] for r in rows]
    return {"median": statistics.median(b), "p10": p10(b), "worst": min(b), "max_dd": max(r["dd"] for r in rows),
            "trades": statistics.median(r["trades"] for r in rows), "fees": statistics.median(r["fees"] for r in rows),
            "tax": statistics.median(r["tax"] for r in rows), "stops": statistics.median(r["stops"] for r in rows),
            "n": len(rows)}


def neighbours(key):
    kind, x, n, y = key
    out = []
    if kind in ("A", "C"):
        i, j = XS.index(x), NS.index(n)
        out += [(kind, XS[i + d], n, y) for d in (-1, 1) if 0 <= i + d < len(XS)]
        out += [(kind, x, NS[j + d], y) for d in (-1, 1) if 0 <= j + d < len(NS)]
    if kind in ("B", "C"):
        k = YS.index(y)
        out += [(kind, x, n, YS[k + d]) for d in (-1, 1) if 0 <= k + d < len(YS)]
    return out


def plateau(train, kind):
    rows = []
    for key, v in train.items():
        if key[0] != kind:
            continue
        nb = [train[k] for k in neighbours(key)]
        hood = [v] + nb
        flat = all(abs(x[m] - v[m]) / v[m] <= TOL for x in nb for m in ("median", "p10"))
        rows.append({"key": key, "flat": flat, "hood_p10": min(x["p10"] for x in hood),
                     "hood_median": min(x["median"] for x in hood), **v})
    rows.sort(key=lambda r: (not r["flat"], -r["hood_p10"], -r["hood_median"]))
    return rows


def verdict(c, a):
    """Regeln: minst lika bra på 10 % sämsta OCH median (inom 5 % = lika, då vinner lägre nedgång) i båda perioderna."""
    def ok(cv, av):
        if any(cv[m] < av[m] * (1 - TIE) for m in ("median", "p10")):
            return False  # sämre än 5 % på något av måtten
        if all(cv[m] <= av[m] * (1 + TIE) for m in ("median", "p10")):  # lika: lägre nedgång avgör
            return True if cv["max_dd"] < av["max_dd"] - 0.005 else "lika"
        return True
    res = {p: ok(c[p], a[p]) for p in ("train", "test")}
    wins = all(res.values())
    strictly = any(r is True for r in res.values())
    return {"periods": res, "replaces": bool(wins and strictly)}


def fk(x):
    return f"{x / 1000:,.0f}".replace(",", " ") + " 000" if x >= 1000 else f"{x:.0f}"


def main():
    strats = cells()
    jobs = []
    for key, st in strats.items():
        jobs += [(key, st, q, "2019-12-31") for q in TRAIN_STARTS]
        jobs += [(key, st, q, END) for q in ALL_STARTS]  # TEST_STARTS ingår
    raw = {}
    with Pool(initializer=run._init) as pool:
        for key, start, end, r in pool.imap_unordered(_job, jobs, chunksize=8):
            raw.setdefault(key, {})[(start, end)] = r
    summ = {}
    for key, v in raw.items():
        summ[key] = {
            "train": agg([v[(q, "2019-12-31")] for q in TRAIN_STARTS]),
            "test": agg([v[(q, END)] for q in TEST_STARTS]),
            "all": agg([v[(q, END)] for q in ALL_STARTS]),
            "single_train": v[("2014-01-01", "2019-12-31")]["bank"],
            "single_test": v[("2020-01-01", END)]["bank"],
            "full": v[("2014-01-01", END)],
        }
    train = {k: s["train"] for k, s in summ.items()}
    picks, flat = {}, {}
    for kind in ("A", "B", "C"):
        rows = plateau(train, kind)
        picks[kind] = rows[0]["key"]
        flat[kind] = rows[0]["flat"]
        print(f"\n{kind}: platåer (inställning 2014-2019)")
        for r in rows[:8]:
            print(" ", r["key"][1:], "platå" if r["flat"] else "-", fk(r["median"]), fk(r["p10"]),
                  f"{r['max_dd']:.0%}", "grannskap p10", fk(r["hood_p10"]))
    base = summ[("auto", 0, 0, 0)]
    out = {"picks": {k: list(v) for k, v in picks.items()}, "cells": {}, "verdict": {}}
    print("\n| Variant | Median 2014-19 | p10 2014-19 | DD | Median 2020- | p10 2020- | DD | Median 44 | p10 44 | DD 44 |"
          " Affärer | Avgifter | Skatt | 2014-2019 | 2020-idag |")
    for key in [("auto", 0, 0, 0)] + [picks[k] for k in "ABC"]:
        s = summ[key]
        print(f"| {strats[key].name} | {fk(s['train']['median'])} | {fk(s['train']['p10'])} | "
              f"{s['train']['max_dd']:.0%} | {fk(s['test']['median'])} | {fk(s['test']['p10'])} | "
              f"{s['test']['max_dd']:.0%} | {fk(s['all']['median'])} | {fk(s['all']['p10'])} | {s['all']['max_dd']:.0%} | "
              f"{s['all']['trades']:.0f} | {fk(s['all']['fees'])} | {fk(s['all']['tax'])} | {fk(s['single_train'])} | "
              f"{fk(s['single_test'])} |")
        if key[0] != "auto":
            v = verdict(s, base)
            v["plateau"] = flat[key[0]]
            v["replaces"] = v["replaces"] and flat[key[0]]
            out["verdict"][key[0]] = v
    print("\nKraschfönster (körning från 2014-01-01): fall topp->botten, dagar till tillbaka på toppen")
    for key in [("auto", 0, 0, 0)] + [picks[k] for k in "ABC"]:
        w = summ[key]["full"]["windows"]
        print(strats[key].name, " · ".join(f"{n}: -{x['dd']:.0%} ({x['days'] if x['days'] is not None else 'ej'} d,"
                                           f" {x['peak']}->{x['trough']})" for n, x in w.items()))
    print("\nBeslut:", json.dumps(out["verdict"], ensure_ascii=False))
    out["cells"] = {"|".join(map(str, k)): v for k, v in summ.items()}
    path = ROOT / "backtest" / "cache" / "del6.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("skrev", path)
    return out


if __name__ == "__main__":
    main()
