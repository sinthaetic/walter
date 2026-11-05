"""Del 5c (nov 2026): Market Cipher-regelboken från guiderna (quantzee.com, tradelogic.pro), bestämd innan körningen.
- Trendfilter (Cipher A): köp bara när trendbandet pekar upp (EMA 2 över EMA 8), blanka bara när det pekar ned.
- Ankare + trigger ("double dip"): en grön prick (kop/guld) är ankaret. En senare uppåtkorsning av vågen inom 30 staplar
  med HÖGRE vågbotten än ankaret är triggern -> köp på nästa öppning. En divergens (div_upp) räknas också som trigger.
  Blankning spegelvänt: röd prick (salj) = ankare, senare nedåtkorsning med LÄGRE vågtopp = trigger.
- Stopp-förlust: under lägsta priset sedan ankaret (över högsta vid blankning).
- Ut: röd prick (salj) eller blod stänger ett köp, grön prick (kop/guld) stänger en blankning, annars stoppet.
Förenklat bort: delvinster vid toppar i pengaflödet, volym, stöd/motstånd (går inte att avgöra utan ögat).
Kör: .venv\\Scripts\\python.exe -m backtest.regelbok_run
"""
import statistics
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import candles, data, run, wcipher, wcipher_run as W  # noqa: E402

UP, DN = {"liten_upp", "kop", "guld"}, {"liten_ned", "salj"}
WINDOW = 30


class Regelbok(W.Tape):
    def __init__(self, tf, series):
        bars = candles.load(tf)
        super().__init__(tf, series, bars)
        res = wcipher.compute(bars)
        wt2, e2, e8 = res["wt2"], res["ribbon"][1], res["ribbon"][7]
        self.long_in, self.short_in, self.stops = set(), set(), {}
        anc_l = anc_s = None  # (stapel, vågvärde, lägsta/högsta pris sedan)
        for i in range(len(bars)):
            k = self.kinds.get(i, set())
            if anc_l:
                anc_l = (anc_l[0], anc_l[1], min(anc_l[2], self.lo[i]))
            if anc_s:
                anc_s = (anc_s[0], anc_s[1], max(anc_s[2], self.h[i]))
            trend_up, trend_dn = e2[i] > e8[i], e2[i] < e8[i]
            if k & UP and anc_l and 0 < i - anc_l[0] <= WINDOW and wt2[i] > anc_l[1] and trend_up:
                self.long_in.add(i); self.stops[i] = anc_l[2]; anc_l = None
            elif "div_upp" in k and trend_up:
                self.long_in.add(i); self.stops[i] = min(self.lo[max(0, i - 10):i + 1])
            if k & DN and anc_s and 0 < i - anc_s[0] <= WINDOW and wt2[i] < anc_s[1] and trend_dn:
                self.short_in.add(i); self.stops[i] = anc_s[2]; anc_s = None
            elif "div_ned" in k and trend_dn:
                self.short_in.add(i); self.stops[i] = max(self.h[max(0, i - 10):i + 1])
            if k & {"kop", "guld"} and i not in self.long_in:
                anc_l = (i, wt2[i], self.lo[i])
            if "salj" in k and i not in self.short_in:
                anc_s = (i, wt2[i], self.h[i])

    def target(self, i, variant, mode, pos=0):
        k = self.kinds.get(i, set())
        if i in self.long_in:
            return 1
        if i in self.short_in and mode == "ls":
            return -1
        if pos > 0 and k & {"salj", "blod"}:
            return 0
        if pos < 0 and k & {"kop", "guld"}:
            return 0
        return None


_T = None


def _init():
    global _T
    s = data.load_all()
    _T = {tf: Regelbok(tf, s) for tf in ("1d", "4h")}


def _job(job):
    tag, (tf, mode, start, end) = job
    return tag, W.summary(W.run_wc(_T[tf], "regelbok", mode, start, end, 100000))


def main():
    end = W.FULL[1]
    combos = [(tf, m) for tf in ("1d", "4h") for m in ("long", "ls")]
    jobs = [((tf, m, p), (tf, m, a, b)) for tf, m in combos
            for p, (a, b) in (("2014-2019", W.TRAIN), ("2020-idag", W.TEST))]
    jobs += [((tf, m, q), (tf, m, q, end)) for tf, m in combos for q in run.quarters()]
    with Pool(initializer=_init) as pool:
        res = dict(pool.imap(_job, jobs, chunksize=2))
    print("Regelboken, kr på banken per 100 000 kr (avgifter + svensk skatt)")
    print(f"{'variant':<16}{'2014-2019':>11}{'2020-idag':>11}{'median 44':>11}{'10% sämsta':>12}{'största fall':>14}"
          f"{'tömt':>7}{'rundor/år':>11}{'träff':>7}{'vinst/förlust':>16}")
    for tf, m in combos:
        st = [v for k, v in res.items() if k[:2] == (tf, m) and k[2] not in ("2014-2019", "2020-idag")]
        b = [x["bank"] for x in st]
        full = res[(tf, m, "2014-2019")]
        aw = statistics.median(x["avg_win"] or 0 for x in st)
        al = statistics.median(x["avg_loss"] or 0 for x in st)
        print(f"{tf + ' ' + ('bara köp' if m == 'long' else 'köp+blanka'):<16}{full['bank']:>11,.0f}"
              f"{res[(tf, m, '2020-idag')]['bank']:>11,.0f}{statistics.median(b):>11,.0f}"
              f"{statistics.quantiles(b, n=10, method='inclusive')[0]:>12,.0f}{max(x['dd'] for x in st):>13.0%}"
              f"{sum(bool(x.get('liquidations')) for x in st):>5}/{len(st)}"
              f"{statistics.median(x['per_year'] or 0 for x in st):>11.1f}"
              f"{statistics.median(x['win_rate'] or 0 for x in st):>7.0%}"
              f"{aw:>+8.0%} /{al:>+6.0%}".replace(",", " "))


if __name__ == "__main__":
    main()
