"""Månadssparande och målläge i historiktestet (samma kod som live: walter_paper.propose via sim.run).

  .venv\\Scripts\\python.exe -m backtest.savings_run    # några minuter, alla kärnor -> backtest/cache/sparande.json

A. Autopiloten med 1 000 kr i månaden (den 25:e), start 1 000 kr, från 2018-01-01 och 2021-01-01 till idag.
   Kronor på banken efter skatt och avgifter, mot summan som sattes in.
B. Målläget för 3-årsmål: start 100 000 kr den 1:a varje månad 2014-01..2023-10, slut = målets datum (3 år senare,
   allt säljs och tas ut). Med och utan glidning mot kontanter. 10 % sämsta (p10), median och sämsta.
Kraken-lik börs, svensk skatt (som övriga körningar).
"""
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

END = run.FULL[1]
MONTHLY = 1000
GOAL_STARTS = [f"{y}-{m:02d}-01" for y in range(2014, 2024) for m in range(1, 13) if f"{y}-{m:02d}" <= "2023-10"]


def plus_years(iso, n):
    d = date.fromisoformat(iso)
    return d.replace(year=d.year + n).isoformat()


def _job(job):
    kind, start, end, glide = job
    if kind == "dca":
        st = sim.Strategy(name="Autopilot + 1 000 kr/mån", rules=sim.AUTOPILOT_RULES, savings_sek=MONTHLY)
        r = sim.run(st, start, end, KRAKEN, start_sek=MONTHLY, series=run._S, lamp_cache=run._C)
        return job, {"bank": r.final_sek, "in": r.deposited_sek, "tax": r.tax_sek, "fees": r.fees_sek,
                     "trades": r.n_trades}
    st = sim.Strategy(name="Autopilot", rules=sim.AUTOPILOT_RULES, goal_date=end if glide else None)
    r = sim.run(st, start, end, KRAKEN, start_sek=100000, series=run._S, lamp_cache=run._C)
    return job, {"bank": r.final_sek, "dd": r.max_dd}


def p10(v):
    return statistics.quantiles(v, n=10, method="inclusive")[0]


def fk(x):
    return f"{x:,.0f}".replace(",", " ")


def main():
    jobs = [("dca", s, END, False) for s in ("2018-01-01", "2021-01-01")]
    jobs += [("goal", s, plus_years(s, 3), g) for s in GOAL_STARTS for g in (False, True)]
    out = {}
    with Pool(initializer=run._init) as pool:
        for job, r in pool.imap_unordered(_job, jobs, chunksize=4):
            out[job] = r
    print("\nA. Autopiloten + 1 000 kr/mån (start 1 000 kr, insättning den 25:e), till", END)
    print("| Från | Insatt | På banken efter skatt | Skatt | Avgifter | Affärer |")
    res = {"dca": {}, "goal": {}}
    for s in ("2018-01-01", "2021-01-01"):
        r = out[("dca", s, END, False)]
        res["dca"][s] = r
        print(f"| {s[:4]} | {fk(r['in'])} | {fk(r['bank'])} | {fk(r['tax'])} | {fk(r['fees'])} | {r['trades']} |")
    print(f"\nB. 3-årsmål, start 100 000 kr, {len(GOAL_STARTS)} starter ({GOAL_STARTS[0]}..{GOAL_STARTS[-1]})")
    print("| Variant | p10 | Median | Sämsta | Bästa | Max nedgång (median) |")
    for g in (False, True):
        rows = [out[("goal", s, plus_years(s, 3), g)] for s in GOAL_STARTS]
        b = [x["bank"] for x in rows]
        agg = {"p10": p10(b), "median": statistics.median(b), "worst": min(b), "best": max(b),
               "dd_median": statistics.median(x["dd"] for x in rows), "n": len(b)}
        res["goal"]["glide" if g else "none"] = agg
        print(f"| {'Med glidning' if g else 'Utan glidning'} | {fk(agg['p10'])} | {fk(agg['median'])} | "
              f"{fk(agg['worst'])} | {fk(agg['best'])} | {agg['dd_median']:.0%} |")
    pairs = [(out[("goal", s, plus_years(s, 3), False)]["bank"], out[("goal", s, plus_years(s, 3), True)]["bank"])
             for s in GOAL_STARTS]
    res["goal"]["glide_better_share"] = sum(1 for a, b in pairs if b > a) / len(pairs)
    print(f"Glidningen gav mer på banken i {res['goal']['glide_better_share']:.0%} av starterna.")
    path = ROOT / "backtest" / "cache" / "sparande.json"
    path.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("skrev", path)
    return res


if __name__ == "__main__":
    main()
