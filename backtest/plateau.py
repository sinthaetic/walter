"""Steg 10 del 3b: hur säker är den långsamma Walter? Platårutnät över startdagar.

  .venv\\Scripts\\python.exe -m backtest.plateau     # några minuter, alla kärnor -> backtest/cache/del3b.json

Varje cell körs från varje kvartal 2014-2024 till idag (44 starter, Kraken-lik börs). Per cell: median och
10:e percentilen av kronor på banken, största nedgång (värsta start) och antal affärer (median per start).
En PLATÅ = en cell där alla grannar (ett steg bort i snitt, bekräftelse, minsta affär eller avrundning) ligger
inom 15 % av cellen, både i median och 10:e percentil. Vi väljer mitten av den bästa platån, inte den bästa cellen.
"""
import copy
import json
import statistics
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest import data, run, sim  # noqa: E402
from backtest.costs import KRAKEN  # noqa: E402

SMOOTH = (20, 30, 45, 60, 90, 120)
CONFIRM = (1, 3, 5, 7, 9)       # veckor (= beslut, ett per vecka)
BAND = (0, 5)                   # 0 = bara minTradePct 2 %, 5 = hoppa över affärer under 5 %
ROUND = ("nearest", "up", "down")
PLATEAU_ROUND = ("nearest", "up")  # avrundningarna som platån måste hålla för ("båda")
CAPS = {"35/20/20": {"BTC": 0.35, "ETH": 0.2, "GOLD": 0.2}, "50/15/10": {"BTC": 0.5, "ETH": 0.15, "GOLD": 0.1},
        "60/10/5": {"BTC": 0.6, "ETH": 0.1, "GOLD": 0.05}, "75/0/0": {"BTC": 0.75, "ETH": 0.0, "GOLD": 0.0}}
TOL = 0.15
MAX_DD = 0.60
SPLIT = "2018-01-01"            # starter före spänner över toppen i dec 2017
END = run.FULL[1]


def slow(smooth, confirm, band, rounding="nearest", caps="50/15/10"):
    """Den långsamma Walter från del 3 med valda värden. ETH följer läget, guld på taket efter Level 3."""
    st = run.variant(f"långsam s{smooth} b{confirm} m{band} {rounding} {caps}", caps="50/15/10", eth="ethFast",
                     gold="goldAlways", confirm=confirm, smooth=smooth, cadence=7, band_pp=band, rounding=rounding)
    st.rules["caps"] = dict(CAPS[caps])
    return st


def passive_levels(caps="35/20/20"):
    """Fasta andelar men Levels kvar: Walter som alltid står på Köper (ETH efter Level 2, guld efter Level 3)."""
    st = slow(0, 0, 5, caps=caps)
    st.name = f"Passiv {caps} med Levels (vecka, 5 %-band)"
    st.smooth_days = st.confirm_days = 0
    st.rules["modes"].update(buyAtRed=10, buyLittleAtRed=10)
    st.rules.update(parkeraAtRed=11, wakeAtRed=10, ethMaxRed=10)
    return st


def passive_grid():
    """Platån för den passiva mixen själv: hur ofta (dag/vecka/månad) × band (2/5/10 %) × tak."""
    out = {}
    for k in ("35/20/20", "50/15/10", "60/10/5"):
        for cad in (1, 7, 30):
            for band in (2, 5, 10):
                out[(k, cad, band)] = sim.mix(CAPS[k], cadence_days=cad, band_pp=band,
                                              name=f"Passiv {k} var {cad}:e dag band {band}")
    return out


def baselines():
    w = {"BTC": 0.35, "ETH": 0.2, "GOLD": 0.2}
    return {
        "Passiv 35/20/20 med Levels (vecka, 5 %-band)": passive_levels(),
        "Walter i dag": sim.Strategy(),
        "Ombalanserad 35/20/20 (varje dag, 2 %)": sim.mix(w),
        "Ombalanserad BTC 35 %": sim.mix({"BTC": 0.35}),
        "Passiv 35/20/20 (vecka, 5 %-band)": sim.mix(w, cadence_days=7, band_pp=5, name="Passiv 35/20/20 vecka band5"),
        "Passiv 50/15/10 (vecka, 5 %-band)": sim.mix(CAPS["50/15/10"], cadence_days=7, band_pp=5,
                                                     name="Passiv 50/15/10 vecka band5"),
    }


def _one(job):
    key, st, start = job
    r = sim.run(st, start, END, KRAKEN, series=run._S, lamp_cache=run._C)
    modes = list(r.modes.values())
    return key, start, {"bank": r.final_sek, "dd": r.max_dd, "trades": r.n_trades,
                        "parked": sum(m == "PARKERA" for m in modes),
                        "switches": sum(1 for a, b in zip(modes, modes[1:]) if a != b)}


def p10(v):
    return statistics.quantiles(v, n=10, method="inclusive")[0]


def summary(starts):
    """starts: {kvartal: resultat} -> median, p10, nedgång, affärer, och samma delat före/efter 2018."""
    def agg(qs):
        b = [starts[q]["bank"] for q in qs]
        return {"median": statistics.median(b), "p10": p10(b), "worst": min(b), "n": len(qs)}
    qs = sorted(starts)
    out = agg(qs)
    out.update(max_dd=max(starts[q]["dd"] for q in qs), trades=statistics.median(starts[q]["trades"] for q in qs),
               trades_2014=starts[qs[0]]["trades"], parked_2014=starts[qs[0]]["parked"],
               switches_2014=starts[qs[0]]["switches"], bank_2014=starts[qs[0]]["bank"],
               before=agg([q for q in qs if q < SPLIT]), after=agg([q for q in qs if q >= SPLIT]))
    return out


def run_all(jobs, pool):
    res = {}
    for key, q, r in pool.imap_unordered(_one, jobs, chunksize=4):
        res.setdefault(key, {})[q] = r
    return {k: summary(v) for k, v in res.items()}


def neighbours(cell):
    s, c, m, rnd = cell
    i, j = SMOOTH.index(s), CONFIRM.index(c)
    out = []
    for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        if 0 <= i + di < len(SMOOTH) and 0 <= j + dj < len(CONFIRM):
            out.append((SMOOTH[i + di], CONFIRM[j + dj], m, rnd))
    out.append((s, c, BAND[1 - BAND.index(m)], rnd))
    out += [(s, c, m, r) for r in PLATEAU_ROUND if r != rnd]
    return out


def plateau(grid):
    """Per cell (bara PLATEAU_ROUND): platå om alla grannar inom TOL i median och p10. Poäng = sämsta p10 i
    grannskapet (cellen + grannar), sedan sämsta median. Alla celler och grannar måste ha nedgång <= MAX_DD."""
    rows = []
    for cell, v in grid.items():
        if cell[3] not in PLATEAU_ROUND:
            continue
        nb = [grid[n] for n in neighbours(cell)]
        hood = [v] + nb
        flat = all(abs(x[k] - v[k]) / v[k] <= TOL for x in nb for k in ("median", "p10"))
        rows.append({"cell": cell, "flat": flat, "dd_ok": all(x["max_dd"] <= MAX_DD for x in hood),
                     "hood_p10": min(x["p10"] for x in hood), "hood_median": min(x["median"] for x in hood),
                     "spread": max(abs(x[k] - v[k]) / v[k] for x in nb for k in ("median", "p10")), **v})
    rows.sort(key=lambda r: (not (r["flat"] and r["dd_ok"]), -r["hood_p10"], -r["hood_median"]))
    return rows


def fmt(x):
    return f"{x / 1000:,.0f}k".replace(",", " ")


def main():
    quarters = run.quarters()
    out = {}
    with Pool(initializer=run._init) as pool:
        # 1. Tajmingrutnätet, tak 50/15/10
        cells = [(s, c, m, r) for s in SMOOTH for c in CONFIRM for m in BAND for r in ROUND]
        grid = run_all([(cell, slow(*cell), q) for cell in cells for q in quarters], pool)
        rows = plateau(grid)
        out["grid"] = {"|".join(map(str, k)): v for k, v in grid.items()}
        out["plateau"] = [dict(r, cell="|".join(map(str, r["cell"]))) for r in rows]
        centre = rows[0]["cell"]
        print("platåns mitt:", centre)
        for r in rows[:15]:
            print(r["cell"], "platå" if r["flat"] else "-", fmt(r["median"]), fmt(r["p10"]),
                  f"{r['max_dd']:.0%}", "grannar sämst p10", fmt(r["hood_p10"]), f"spridning {r['spread']:.0%}")
        # Medianer per (snitt, bekräftelse) för nearest/band 5, som karta
        for m in BAND:
            for rnd in ROUND:
                print(f"\nmin trade {m}, {rnd}: median / p10 (k)")
                for s in SMOOTH:
                    print(s, "  ".join(f"{grid[(s, c, m, rnd)]['median'] / 1e3:4.0f}/{grid[(s, c, m, rnd)]['p10'] / 1e3:3.0f}"
                                       for c in CONFIRM))

        # 2. Taken vid platåns tajming
        s, c, m, _ = centre
        caps = run_all([((k, rnd), slow(s, c, m, rnd, k), q) for k in CAPS for rnd in ROUND for q in quarters], pool)
        out["caps"] = {f"{k}|{rnd}": v for (k, rnd), v in caps.items()}
        for (k, rnd), v in sorted(caps.items()):
            print(k, rnd, fmt(v["median"]), fmt(v["p10"]), f"{v['max_dd']:.0%}", v["trades"])

        # 3-4. Jämförelser
        base = run_all([(n, st, q) for n, st in baselines().items() for q in quarters], pool)
        out["baselines"] = base
        for n, v in base.items():
            print(n, fmt(v["median"]), fmt(v["p10"]), f"{v['max_dd']:.0%}", v["trades"],
                  "före", fmt(v["before"]["median"]), "efter", fmt(v["after"]["median"]), fmt(v["after"]["p10"]))

        # 5. Den passiva mixens egen platå
        pg = run_all([(key, st, q) for key, st in passive_grid().items() for q in quarters], pool)
        out["passive"] = {"|".join(map(str, k)): v for k, v in pg.items()}
        for k, v in sorted(pg.items()):
            print("passiv", k, fmt(v["median"]), fmt(v["p10"]), f"{v['max_dd']:.0%}", v["trades"],
                  "efter 2018", fmt(v["after"]["median"]), fmt(v["after"]["p10"]))
    out["centre"] = "|".join(map(str, centre))
    path = ROOT / "backtest" / "cache" / "del3b.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("skrev", path)
    return out


if __name__ == "__main__":
    main()
