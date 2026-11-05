"""Del 5e (nov 2026): "Blood in the Water" (thrive.fi/blog/trading/market-cipher), bestämd innan körningen.
- Ankare: grön prick (vågen korsar upp) med vågen på −75 eller lägre.
- In: nästa gröna prick (andra eller tredje) inom 30 staplar, medan vågen fortfarande är under noll -> köp på nästa öppning.
- Stopp: under lägsta priset sedan ankaret ("kapitulationsbotten"). Ut: vågen korsar upp över noll (guidens första mål).
Bara köp (guiden beskriver bara köpsidan). Förenklat bort: DBSI, delvinster, tidsstopp.
Kör: .venv\\Scripts\\python.exe -m backtest.blood_run
"""
import statistics
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import candles, data, run, wcipher, wcipher_run as W  # noqa: E402

UP = {"liten_upp", "kop", "guld"}


class Blood(W.Tape):
    def __init__(self, tf, series):
        bars = candles.load(tf)
        super().__init__(tf, series, bars)
        wt2 = wcipher.compute(bars)["wt2"]
        self.buy, self.out, self.stops = set(), set(), {}
        anc = None  # (stapel, lägsta pris sedan)
        for i in range(1, len(bars)):
            k = self.kinds.get(i, set())
            if anc:
                anc = (anc[0], min(anc[1], self.lo[i]))
            if k & UP and anc and 0 < i - anc[0] <= 30 and wt2[i] < 0:
                self.buy.add(i); self.stops[i] = anc[1]; anc = None
            elif k & UP and wt2[i] <= -75:
                anc = (i, self.lo[i])
            if wt2[i - 1] <= 0 < wt2[i]:
                self.out.add(i)

    def target(self, i, variant, mode, pos=0):
        if i in self.buy:
            return 1
        if pos > 0 and i in self.out:
            return 0
        return None


_T = None


def _init():
    global _T
    s = data.load_all()
    _T = {tf: Blood(tf, s) for tf in ("1d", "4h")}


def _job(job):
    tag, (tf, start, end) = job
    return tag, W.summary(W.run_wc(_T[tf], "blood", "long", start, end, 100000))


def main():
    end = W.FULL[1]
    jobs = [((tf, p), (tf, a, b)) for tf in ("1d", "4h") for p, (a, b) in (("2014-2019", W.TRAIN), ("2020-idag", W.TEST))]
    jobs += [((tf, q), (tf, q, end)) for tf in ("1d", "4h") for q in run.quarters()]
    with Pool(initializer=_init) as pool:
        res = dict(pool.imap(_job, jobs, chunksize=2))
    print("Blood in the Water (bara köp), kr på banken per 100 000 kr (avgifter + svensk skatt)")
    for tf in ("1d", "4h"):
        st = [v for k, v in res.items() if k[0] == tf and k[1] not in ("2014-2019", "2020-idag")]
        b = [x["bank"] for x in st]
        print(f"{tf}: 2014-2019 {res[(tf, '2014-2019')]['bank']:,.0f} · 2020-idag {res[(tf, '2020-idag')]['bank']:,.0f} · "
              f"median {statistics.median(b):,.0f} · 10% sämsta {statistics.quantiles(b, n=10, method='inclusive')[0]:,.0f} · "
              f"rundor/år {statistics.median(x['per_year'] or 0 for x in st):.1f} · "
              f"träff {statistics.median(x['win_rate'] or 0 for x in st):.0%} · vinst/förlust "
              f"{statistics.median(x['avg_win'] or 0 for x in st):+.1%} / {statistics.median(x['avg_loss'] or 0 for x in st):+.1%} · "
              f"tid i marknad {statistics.median(x['time_in'] for x in st):.0%}".replace(",", " "))


if __name__ == "__main__":
    main()
