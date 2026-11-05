"""Del 5b (nov 2026): ägarens regel – bara divergenser på vågen.
Köp när vågbottnarna går uppåt medan priset gör en lägre botten (div_upp), sälj/blanka när topparna går nedåt
medan priset gör en högre topp (div_ned). Samma motor, avgifter och skatt som del 5 (backtest/wcipher_run.py).
Bestämt innan körningen: en regel, tre tidsramar (vecka, dag, 4 h), bara köp och köp+blanka.
Kör: .venv\\Scripts\\python.exe -m backtest.div_run
"""
import statistics
import sys
from datetime import date, datetime, timedelta, timezone
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import candles, data, run, wcipher_run as W  # noqa: E402

W.VARIANTS["div"] = ({"div_upp"}, {"div_ned"})
W.HOURS["1w"] = 168
TFS = ("1w", "1d", "4h")


def weekly(daily):
    """Veckoljus (måndag–söndag) av dagsljusen."""
    out = []
    for b in daily:
        d = datetime.fromtimestamp(b["time"], timezone.utc).date()
        monday = d - timedelta(days=d.weekday())
        t = int(datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc).timestamp())
        if out and out[-1]["time"] == t:
            w = out[-1]
            w["high"], w["low"], w["close"] = max(w["high"], b["high"]), min(w["low"], b["low"]), b["close"]
            w["volume"] = w.get("volume", 0) + b.get("volume", 0)
        else:
            out.append(dict(b, time=t))
    return out


_T = None


def _init():
    global _T
    s = data.load_all()
    _T = {"1w": W.Tape("1w", s, weekly(candles.load("1d"))), "1d": W.Tape("1d", s), "4h": W.Tape("4h", s)}


def _job(job):
    tag, (tf, mode, start, end) = job
    return tag, W.summary(W.run_wc(_T[tf], "div", mode, start, end, 100000))


def main():
    end = W.FULL[1]
    combos = [(tf, m) for tf in TFS for m in ("long", "ls")]
    jobs = [((tf, m, p), (tf, m, a, b)) for tf, m in combos
            for p, (a, b) in (("2014-2019", W.TRAIN), ("2020-idag", W.TEST))]
    jobs += [((tf, m, q), (tf, m, q, end)) for tf, m in combos for q in run.quarters()]
    with Pool(initializer=_init) as pool:
        res = dict(pool.imap(_job, jobs, chunksize=2))
    print("Divergens-regeln, kr på banken per 100 000 kr (avgifter + svensk skatt)")
    print(f"{'variant':<18}{'2014-2019':>12}{'2020-idag':>12}{'median 44':>12}{'10% sämsta':>12}"
          f"{'största fall':>14}{'tömt':>7}{'rundor/år':>11}{'träff':>8}")
    for tf, m in combos:
        starts = [v for k, v in res.items() if k[:2] == (tf, m) and k[2] not in ("2014-2019", "2020-idag")]
        b = [x["bank"] for x in starts]
        p10 = statistics.quantiles(b, n=10, method="inclusive")[0]
        full = res[(tf, m, "2014-2019")]
        print(f"{tf + ' ' + ('bara köp' if m == 'long' else 'köp+blanka'):<18}"
              f"{full['bank']:>12,.0f}{res[(tf, m, '2020-idag')]['bank']:>12,.0f}"
              f"{statistics.median(b):>12,.0f}{p10:>12,.0f}{max(x['dd'] for x in starts):>13.0%}"
              f"{sum(bool(x.get('liquidations')) for x in starts):>5}/{len(starts)}"
              f"{statistics.median(x.get('per_year') or 0 for x in starts):>11.1f}"
              f"{statistics.median(x.get('win_rate') or 0 for x in starts):>8.0%}".replace(",", " "))


if __name__ == "__main__":
    main()
