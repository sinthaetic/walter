"""Del 5d (nov 2026): "Entering longs in an uptrend" (marketciphertrading.com/tutorial-videos), bestämd innan körningen.
- Bara köp, bara i uppåttrend = priset över sitt 200-dagarssnitt (högre tidsram, som guiden menar).
  Första försöket med Cipher A-bandet som trend gav 0 affärer: en grön prick (våg under −60) vänder alltid det snabba bandet.
- In: vågen korsar upp (grön prick, kop/guld = under −60) medan pengaflödet är rött (under 0) men stiger.
- Ut: pengaflödet blir grönt (korsar upp över 0). Stopp: lägsta priset de 10 senaste staplarna före köpet.
Kör: .venv\\Scripts\\python.exe -m backtest.mf_run
"""
import statistics
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import candles, data, run, wcipher, wcipher_run as W  # noqa: E402


def uptrend(close, tf):
    """Priset över sitt 200-dagarssnitt (4 h: 1 200 staplar)."""
    n = 200 * (6 if tf == "4h" else 1)
    out, s = [False] * len(close), 0.0
    for i, c in enumerate(close):
        s += c - (close[i - n] if i >= n else 0)
        out[i] = i >= n - 1 and c > s / n
    return out


class Pengaflode(W.Tape):
    def __init__(self, tf, series):
        bars = candles.load(tf)
        super().__init__(tf, series, bars)
        res = wcipher.compute(bars)
        mfi = res["mfi"]
        up = uptrend(self.c, tf)
        self.buy, self.out, self.stops = set(), set(), {}
        for i in range(1, len(bars)):
            k = self.kinds.get(i, set())
            if k & {"kop", "guld"} and up[i] and mfi[i] < 0 and mfi[i] > mfi[i - 1]:
                self.buy.add(i)
                self.stops[i] = min(self.lo[max(0, i - 10):i + 1])
            if mfi[i - 1] <= 0 < mfi[i]:
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
    _T = {tf: Pengaflode(tf, s) for tf in ("1d", "4h")}


def _job(job):
    tag, (tf, start, end) = job
    return tag, W.summary(W.run_wc(_T[tf], "mf", "long", start, end, 100000))


def main():
    end = W.FULL[1]
    jobs = [((tf, p), (tf, a, b)) for tf in ("1d", "4h") for p, (a, b) in (("2014-2019", W.TRAIN), ("2020-idag", W.TEST))]
    jobs += [((tf, q), (tf, q, end)) for tf in ("1d", "4h") for q in run.quarters()]
    with Pool(initializer=_init) as pool:
        res = dict(pool.imap(_job, jobs, chunksize=2))
    print("Pengaflödes-regeln (bara köp), kr på banken per 100 000 kr (avgifter + svensk skatt)")
    for tf in ("1d", "4h"):
        st = [v for k, v in res.items() if k[0] == tf and k[1] not in ("2014-2019", "2020-idag")]
        b = [x["bank"] for x in st]
        print(f"{tf}: 2014-2019 {res[(tf, '2014-2019')]['bank']:,.0f} · 2020-idag {res[(tf, '2020-idag')]['bank']:,.0f} · "
              f"median {statistics.median(b):,.0f} · 10% sämsta {statistics.quantiles(b, n=10, method='inclusive')[0]:,.0f} · "
              f"största fall {max(x['dd'] for x in st):.0%} · rundor/år {statistics.median(x['per_year'] or 0 for x in st):.1f} · "
              f"träff {statistics.median(x['win_rate'] or 0 for x in st):.0%} · tid i marknad "
              f"{statistics.median(x['time_in'] for x in st):.0%}".replace(",", " "))


if __name__ == "__main__":
    main()
