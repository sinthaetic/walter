"""Steg 10 del 3: alla jämförelser i historiktestet -> tabeller (markdown) och backtest/cache/del3.json.

  .venv\\Scripts\\python.exe -m backtest.run            # allt (några minuter, använder alla kärnor)
  .venv\\Scripts\\python.exe -m backtest.run --quick    # bara huvudtabellen

Metod mot överanpassning:
  1. Inställning: ALLA varianter i rutnätet körs på 2014-01-01 -> 2019-12-31 (Kraken-lik börs). Där väljs
     kandidaterna (högst kronor på banken, största nedgång <= 60 %).
  2. Kontroll: kandidaterna körs OFÖRÄNDRADE på 2020-01-01 -> idag (data de aldrig sett).
  3. Startdatum: start varje kvartal 2014-2024 (slut = idag), median och sämsta per 100 000 kr.
"""
import copy
import itertools
import json
import statistics
import sys
from datetime import date
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest import data, sim  # noqa: E402
from backtest.costs import BITSTAMP, KRAKEN, SAFELLO  # noqa: E402

TRAIN = ("2014-01-01", "2019-12-31")
TEST = ("2020-01-01", "2026-10-22")
FULL = ("2014-01-01", "2026-10-22")
MAX_DD = 0.60
EXCHANGES = {"Kraken": KRAKEN, "Bitstamp": BITSTAMP, "Safello": SAFELLO}

CAPS = {"35/20/20": {"BTC": 0.35, "ETH": 0.2, "GOLD": 0.2},
        "50/15/10": {"BTC": 0.5, "ETH": 0.15, "GOLD": 0.1},
        "75/0/0": {"BTC": 0.75, "ETH": 0.0, "GOLD": 0.0}}
ETH = {"eth30": {}, "eth90": {"eth_ma_days": 90}, "eth200": {"eth_ma_days": 200},
       "eth30band5": {"eth_band_pct": 5}, "eth90band5": {"eth_ma_days": 90, "eth_band_pct": 5},
       "ethFast": {"eth_fixed": True}, "ethOff": "off"}
GOLD = {"gold": {}, "gold7": {"gold_confirm_days": 7}, "gold30": {"gold_confirm_days": 30},
        "goldVix": "vix", "goldOff": {"no_gold": True}, "goldAlways": {"gold_always": True}}
# Lägesgränser buyAtRed/buyLittleAtRed/parkeraAtRed (wakeAtRed 5 som i dag). Lägena själva är kvar.
MODES = {"2/4/7": (2, 4, 7), "3/5/7": (3, 5, 7), "4/5/7": (4, 5, 7)}


def benchmarks():
    return [
        sim.mix({"BTC": 0.35}, name="Ombalanserad BTC 35 % (Walters tak, alltid Köper)"),
        sim.mix({"BTC": 0.75}, name="Ombalanserad BTC 75 % (alltid fullt)"),
        sim.mix({"BTC": 0.35, "ETH": 0.2, "GOLD": 0.2}, name="Ombalanserad BTC 35 + ETH 20 + guld 20 (75 %)"),
        sim.hold_btc(0.35),
        sim.mix({"BTC": 0.35, "ETH": 0.2, "GOLD": 0.2}, rebalance=False,
                name="Köp en gång: BTC 35 + ETH 20 + guld 20 (75 %)"),
        sim.hold_btc(0.75),
    ]


def variant(name, caps="35/20/20", eth="eth30", gold="gold", confirm=0, smooth=0, cadence=1, levels=True,
            hysteresis=False, band_pp=0, no_partial_sells=False, rounding="nearest", modes="2/4/7"):
    rules = copy.deepcopy(sim.DEFAULT_RULES)
    rules["caps"] = dict(CAPS[caps])
    buy, little, park = MODES[modes]
    rules["modes"].update(buyAtRed=buy, buyLittleAtRed=little)
    rules["parkeraAtRed"] = park
    kw = {}
    e, g = ETH[eth], GOLD[gold]
    if e == "off":
        rules["caps"]["ETH"] = 0
    else:
        kw.update(e)
    if g == "vix":
        rules["gold"]["spxBelowMa"] = False
    else:
        kw.update(g)
    return sim.Strategy(name=name, rules=rules, confirm_days=confirm, smooth_days=smooth, cadence_days=cadence,
                        no_levels=not levels, hysteresis=hysteresis, band_pp=band_pp,
                        no_partial_sells=no_partial_sells, rounding=rounding, **kw)


def label(p):
    """Kort namn för en parameteruppsättning (dict)."""
    bits = [p.get("caps", "35/20/20"), p.get("eth", "eth30"), p.get("gold", "gold")]
    if p.get("modes", "2/4/7") != "2/4/7":
        bits.append("lägen" + p["modes"])
    for k, short in (("confirm", "bekr"), ("smooth", "snitt"), ("cadence", "var")):
        if p.get(k, 0) > (1 if k == "cadence" else 0):
            bits.append(f"{short}{p[k]}")
    if not p.get("levels", True):
        bits.append("utanLevels")
    for k in ("hysteresis", "no_partial_sells"):
        if p.get(k):
            bits.append(k)
    if p.get("band_pp"):
        bits.append(f"band{p['band_pp']}")
    if p.get("rounding", "nearest") != "nearest":
        bits.append(p["rounding"])
    return " ".join(bits)


def simplicity(p):
    """Antal ändringar mot dagens Walter (färre = enklare)."""
    base = {"caps": "35/20/20", "eth": "eth30", "gold": "gold", "confirm": 0, "smooth": 0, "cadence": 1,
            "levels": True, "hysteresis": False, "band_pp": 0, "no_partial_sells": False, "modes": "2/4/7"}
    return sum(1 for k, v in base.items() if p.get(k, v) != v)


# ---------- Körning i flera processer ----------
_S, _C = None, None


def _init():
    global _S, _C
    _S, _C = data.load_all(), {}


def _one(job):
    tag, strategy, start, end, exname = job
    r = sim.run(strategy, start, end, EXCHANGES[exname], series=_S, lamp_cache=_C)
    yrs = (date.fromisoformat(r.end) - date.fromisoformat(r.start)).days / 365.25
    return tag, {"name": strategy.name, "start": r.start, "end": r.end, "ex": exname, "bank": r.final_sek,
                 "cagr": r.cagr, "dd": r.max_dd, "trades": r.n_trades, "fees": r.fees_sek, "tax": r.tax_sek,
                 "credit": r.credit_sek, "years": yrs,
                 "switches": sum(1 for a, b in zip(list(r.modes.values()), list(r.modes.values())[1:]) if a != b)}


def run_jobs(jobs, pool):
    return list(pool.imap(_one, jobs, chunksize=8))


def grid():
    out = []
    for caps, eth, gold, confirm, smooth, cadence, band, modes in itertools.product(
            CAPS, [e for e in ETH if e != "eth90"], [g for g in GOLD if g != "goldVix"], (0, 7, 14, 30),
            (0, 30, 60, 90), (1, 7), (0, 5), MODES):
        if caps == "75/0/0" and (eth != "eth30" or gold != "gold"):
            continue  # inget ETH eller guld att variera
        out.append(dict(caps=caps, eth=eth, gold=gold, confirm=confirm, smooth=smooth, cadence=cadence,
                        band_pp=band, modes=modes))
    return out


def pick(out):
    """Regeln: högst i BÅDA perioderna och bäst median över startdatum, bland dem med största nedgång <= 60 %.
    Ingen vinner alla tre -> poäng = sämsta av (inställning / bästa, kontroll / bästa, median / bästa).
    Inom 5 % av bästa poängen väljs den enklaste. Görs både bland alla och bara bland Walter-varianter."""
    per = {}
    for r in out["periods"]:
        if r["ex"] == "Kraken":
            per.setdefault(r["label"], {})[r["period"]] = r
    bench = {s.name for s in benchmarks()}
    simple = {lab: simplicity(p) for lab, p in out["cands"].items()}
    rows = []
    for lab, v in per.items():
        st = out["starts"][lab]
        dd = max(v["train"]["dd"], v["test"]["dd"], v["full"]["dd"], st["max_dd"])
        rows.append({"label": lab, "train": v["train"]["bank"], "test": v["test"]["bank"], "median": st["median"],
                     "dd": dd, "bench": lab in bench, "simple": simple.get(lab, 0)})
    res = {}
    for scope, pool_ in (("alla", rows), ("walter", [r for r in rows if not r["bench"]])):
        ok = [r for r in pool_ if r["dd"] <= MAX_DD]
        best = {k: max(r[k] for r in ok) for k in ("train", "test", "median")}
        for r in ok:
            r["score"] = min(r[k] / best[k] for k in ("train", "test", "median"))
        top = max(r["score"] for r in ok)
        near = sorted([r for r in ok if r["score"] >= top - 0.05], key=lambda r: (r["simple"], -r["score"]))
        res[scope] = {"best": dict(max(ok, key=lambda r: r["score"])), "chosen": dict(near[0]),
                      "ranking": [dict(r) for r in sorted(ok, key=lambda r: -r["score"])[:12]],
                      "winners": {k: max(ok, key=lambda r: r[k])["label"] for k in ("train", "test", "median")}}
    return res


def quarters(first=2014, last=2024):
    return [f"{y}-{m:02d}-01" for y in range(first, last + 1) for m in (1, 4, 7, 10)]


def fmt(x):
    return f"{x:,.0f}".replace(",", " ")


def table(rows, cols):
    head = "| " + " | ".join(c for c, _ in cols) + " |\n|" + "---|" * len(cols) + "\n"
    return head + "".join("| " + " | ".join(f(r) for _, f in cols) + " |\n" for r in rows)


MONEY = [("Strategi", lambda r: r["label"]), ("Bank kr", lambda r: fmt(r["bank"])),
         ("Per år", lambda r: f"{(r['cagr'] or 0) * 100:.1f} %"), ("Största nedgång", lambda r: f"{r['dd'] * 100:.0f} %"),
         ("Affärer", lambda r: str(r["trades"])), ("Avgifter kr", lambda r: fmt(r["fees"])),
         ("Skatt kr", lambda r: fmt(r["tax"])), ("Skattereduktion kr", lambda r: fmt(r["credit"]))]


def headline(pool):
    """Del 4: Walters autopilot (live-koden via sim.autopilot) mot den fasta veckomixen i del 3b, 44 starter
    varje kvartal 2014-2024 till idag, Kraken-lik börs. Siffrorna ska stämma med docs/BACKTEST.md."""
    import statistics as st
    w = {"BTC": 0.35, "ETH": 0.2, "GOLD": 0.2}
    strats = {"Autopilot (live-koden)": sim.autopilot(),
              "Passiv 35/20/20 vecka band5 (del 3b)": sim.mix(w, cadence_days=7, band_pp=5)}
    jobs = [((n, q), s, q, FULL[1], "Kraken") for n, s in strats.items() for q in quarters()]
    res = {}
    for (n, q), r in run_jobs(jobs, pool):
        res.setdefault(n, []).append(r)
    rows = []
    for n, v in res.items():
        b = [x["bank"] for x in v]
        rows.append({"label": n, "median": st.median(b), "p10": st.quantiles(b, n=10, method="inclusive")[0],
                     "max_dd": max(x["dd"] for x in v), "trades": st.median(x["trades"] for x in v), "n": len(v)})
    print(table(rows, [("Strategi", lambda r: r["label"]), ("Median", lambda r: fmt(r["median"])),
                       ("10 % sämsta", lambda r: fmt(r["p10"])), ("Största nedgång", lambda r: f"{r['max_dd']:.0%}"),
                       ("Affärer (median)", lambda r: f"{r['trades']:.0f}"), ("Starter", lambda r: str(r["n"]))]))
    return rows


def main(quick=False):
    out = {}
    with Pool(initializer=_init) as pool:
        out["headline"] = headline(pool)
        # 0. Dagens Walter: gamla modellen -> rättad modell, och avrundningens spann
        base_jobs = []
        for rnd in ("up", "nearest", "down"):
            for credit in (False, True):
                st = sim.Strategy(name=f"Walter i dag ({rnd}, credit={credit})", rounding=rnd, loss_credit=credit)
                base_jobs.append(((rnd, credit), st, *FULL, "Kraken"))
        out["model"] = [dict(r, label=f"avrundning {t[0]}, skattereduktion {'på' if t[1] else 'av'}")
                        for t, r in run_jobs(base_jobs, pool)]
        print(table(out["model"], MONEY))
        if quick:
            return out

        # 1. Inställning på 2014-2019: hela rutnätet
        params = grid()
        jobs = [(i, variant(label(p), **p), *TRAIN, "Kraken") for i, p in enumerate(params)]
        train = dict(run_jobs(jobs, pool))
        rows = [dict(train[i], label=label(p), p=p, simple=simplicity(p)) for i, p in enumerate(params)]
        ok = [r for r in rows if r["dd"] <= MAX_DD]
        ok.sort(key=lambda r: -r["bank"])
        print(f"rutnät: {len(rows)} varianter, {len(ok)} med nedgång <= {MAX_DD:.0%}")
        print(table(ok[:25], MONEY))

        # 1b. Finputs på de 15 bästa: buffert, band, inga delförsäljningar
        extra = []
        for r in ok[:15]:
            for k, v in (("hysteresis", True), ("levels", False), ("no_partial_sells", True),
                         ("gold", "goldVix"), ("eth", "eth90")):
                extra.append(dict(r["p"], **{k: v}))
        jobs = [(i, variant(label(p), **p), *TRAIN, "Kraken") for i, p in enumerate(extra)]
        train2 = dict(run_jobs(jobs, pool))
        rows2 = [dict(train2[i], label=label(p), p=p, simple=simplicity(p)) for i, p in enumerate(extra)]
        allrows = rows + rows2
        ok = sorted([r for r in allrows if r["dd"] <= MAX_DD], key=lambda r: -r["bank"])
        out["train_top"] = ok[:40]
        out["train_n"] = len(allrows)

        # Kandidater: de 8 bästa + den enklaste inom 5 % av bästa + dagens Walter + enstaka-ändringar
        best = ok[0]["bank"]
        within = sorted([r for r in ok if r["bank"] >= 0.95 * best], key=lambda r: (r["simple"], -r["bank"]))
        cands, seen = {}, set()
        for r in sorted(ok[:60], key=lambda r: (-round(r["bank"]), r["simple"])):  # samma resultat -> enklast
            if round(r["bank"]) not in seen and len(cands) < 8:
                seen.add(round(r["bank"]))
                cands[r["label"]] = r["p"]
        if within:
            cands[within[0]["label"]] = within[0]["p"]
        singles = [dict(), dict(confirm=7), dict(confirm=14), dict(smooth=7), dict(smooth=30), dict(cadence=7),
                   dict(eth="ethFast"), dict(eth="eth200"), dict(eth="ethOff"), dict(gold="gold30"),
                   dict(gold="goldOff"), dict(caps="50/15/10"), dict(caps="75/0/0"), dict(band_pp=5),
                   dict(modes="4/5/7"), dict(smooth=60), dict(gold="goldAlways"),
                   dict(eth="ethFast", gold="goldAlways")]
        for p in singles:
            cands.setdefault(label(p), p)
        out["cands"] = cands

        # 2. Kontroll 2020 -> idag + hela perioden, och börserna
        jobs = []
        for lab, p in cands.items():
            for per, (a, b) in (("train", TRAIN), ("test", TEST), ("full", FULL)):
                jobs.append(((lab, per, "Kraken"), variant(lab, **p), a, b, "Kraken"))
            for exn in ("Bitstamp", "Safello"):
                for per, (a, b) in (("train", TRAIN), ("test", TEST)):
                    jobs.append(((lab, per, exn), variant(lab, **p), a, b, exn))
        for st in benchmarks():
            for per, (a, b) in (("train", TRAIN), ("test", TEST), ("full", FULL)):
                jobs.append(((st.name, per, "Kraken"), st, a, b, "Kraken"))
            for exn in ("Bitstamp", "Safello"):
                for per, (a, b) in (("train", TRAIN), ("test", TEST)):
                    jobs.append(((st.name, per, exn), st, a, b, exn))
        res = run_jobs(jobs, pool)
        out["periods"] = [dict(r, label=t[0], period=t[1], ex=t[2]) for t, r in res]

        # 3. Startdatum varje kvartal (Kraken)
        names = list(cands) + [s.name for s in benchmarks()]
        strat = {lab: variant(lab, **p) for lab, p in cands.items()}
        strat.update({s.name: s for s in benchmarks()})
        jobs = [((n, q), strat[n], q, FULL[1], "Kraken") for n in names for q in quarters()]
        res = run_jobs(jobs, pool)
        starts = {}
        for (n, q), r in res:
            starts.setdefault(n, []).append(dict(r, q=q))
        out["starts"] = {n: {"median": statistics.median(x["bank"] for x in v), "worst": min(x["bank"] for x in v),
                             "worst_q": min(v, key=lambda x: x["bank"])["q"],
                             "median_dd": statistics.median(x["dd"] for x in v), "max_dd": max(x["dd"] for x in v),
                             "below_start": sum(x["bank"] < 100000 for x in v), "n": len(v)}
                         for n, v in starts.items()}

        # Avrundningens spann för kandidaterna
        jobs = []
        for lab, p in cands.items():
            for rnd in ("up", "down"):
                for per, (a, b) in (("train", TRAIN), ("test", TEST)):
                    jobs.append(((lab, rnd, per), variant(lab, **dict(p, rounding=rnd)), a, b, "Kraken"))
        out["rounding"] = [dict(r, label=t[0], rnd=t[1], period=t[2]) for t, r in run_jobs(jobs, pool)]

        out["pick"] = pick(out)
        print(json.dumps(out["pick"], ensure_ascii=False, indent=1))

        # 4. Robusthet runt vald Walter: en ändring i taget (tillbaka till dagens värde eller ett steg bort)
        p0 = out["cands"][out["pick"]["walter"]["chosen"]["label"]]
        steps = {"caps": list(CAPS), "eth": ["eth30", "ethFast", "eth30band5"], "gold": ["gold", "goldAlways", "goldOff"],
                 "confirm": [0, 7, 14], "smooth": [0, 30, 60, 90], "cadence": [1, 7], "levels": [True, False],
                 "band_pp": [0, 5], "modes": list(MODES)}
        nb = {label(p0): p0}
        for k, vals in steps.items():
            for v in vals:
                q = dict(p0, **{k: v})
                if q.get("caps") == "75/0/0":
                    q.update(eth="eth30", gold="gold")
                nb.setdefault(label(q), q)
        jobs = []
        for lab, p in nb.items():
            for per, (a, b) in (("train", TRAIN), ("test", TEST)):
                jobs.append(((lab, per), variant(lab, **p), a, b, "Kraken"))
            for q in quarters():
                jobs.append(((lab, q), variant(lab, **p), q, FULL[1], "Kraken"))
        robust = {}
        for (lab, per), r in run_jobs(jobs, pool):
            robust.setdefault(lab, {"p": nb[lab], "simple": simplicity(nb[lab]), "starts": []})
            if per in ("train", "test"):
                robust[lab][per] = r
            else:
                robust[lab]["starts"].append(r)
        for v in robust.values():
            v["median"] = statistics.median(x["bank"] for x in v["starts"])
            v["worst"] = min(x["bank"] for x in v["starts"])
            v["max_dd"] = max([x["dd"] for x in v["starts"]] + [v["train"]["dd"], v["test"]["dd"]])
            del v["starts"]
        out["robust"] = robust

        # 5. Slutval bland kandidater + robusthetsraderna (bara Walter, alltså med lägen), samma poäng som pick().
        #    OBS: robusthetsraderna är valda med kontrollperioden i sikte, så deras kontrollsiffror är optimistiska.
        rows = [r for r in out["pick"]["walter"]["ranking"]]
        rows += [{"label": lab, "train": v["train"]["bank"], "test": v["test"]["bank"], "median": v["median"],
                  "dd": v["max_dd"], "simple": v["simple"]} for lab, v in robust.items()]
        ok = {r["label"]: r for r in rows if r["dd"] <= MAX_DD}.values()
        best = {k: max(r[k] for r in ok) for k in ("train", "test", "median")}
        for r in ok:
            r["score"] = min(r[k] / best[k] for k in ("train", "test", "median"))
        top = max(r["score"] for r in ok)
        rec = sorted([r for r in ok if r["score"] >= top - 0.01], key=lambda r: (r["simple"], -r["score"]))[0]
        alt = max(ok, key=lambda r: r["test"])
        wf = out["train_top"][0]
        params = dict(out["cands"], **{lab: v["p"] for lab, v in robust.items()})
        final = {"rekommenderad": rec["label"], "bäst 2020-": alt["label"], "bäst 2014-2019 (ren walk-forward)":
                 wf["label"], "Walter i dag": label({})}
        out["final"] = {k: {"label": v, "p": params.get(v, {})} for k, v in final.items()}

        # Detaljer för slutvalet + jämförelserna: alla börser, startdatum (alla och från 2020), avrundning
        strat = {k: variant(v, **params.get(v, {})) for k, v in final.items()}
        strat.update({s.name: s for s in benchmarks()})
        jobs = []
        for k, st in strat.items():
            for exn in EXCHANGES:
                for per, (a, b) in (("train", TRAIN), ("test", TEST), ("full", FULL)):
                    jobs.append(((k, "per", per, exn), st, a, b, exn))
            for q in quarters():
                jobs.append(((k, "start", q, "Kraken"), st, q, FULL[1], "Kraken"))
            if k in final:
                for rnd in ("up", "down"):
                    for per, (a, b) in (("train", TRAIN), ("test", TEST)):
                        jobs.append(((k, "rnd", per, rnd), variant(final[k], **dict(params.get(final[k], {}),
                                                                                    rounding=rnd)), a, b, "Kraken"))
        det = {}
        for (k, kind, a, b), r in run_jobs(jobs, pool):
            det.setdefault(k, {"per": {}, "start": {}, "rnd": {}})[kind][f"{a}|{b}" if kind != "start" else a] = r
        for k, v in det.items():
            st = v["start"]
            for tag, qs in (("alla", list(st)), ("från2020", [q for q in st if q >= "2020"])):
                v[tag] = {"median": statistics.median(st[q]["bank"] for q in qs),
                          "worst": min(st[q]["bank"] for q in qs), "max_dd": max(st[q]["dd"] for q in qs),
                          "median_dd": statistics.median(st[q]["dd"] for q in qs),
                          "below": sum(st[q]["bank"] < 100000 for q in qs), "n": len(qs)}
        out["detail"] = det
        print(json.dumps(out["final"], ensure_ascii=False, indent=1))

    path = ROOT / "backtest" / "cache" / "del3.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("skrev", path)
    return out


if __name__ == "__main__":
    main(quick="--quick" in sys.argv)
