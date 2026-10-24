"""Historiktestet dag för dag: Walters regler, avgifter, växling och svensk skatt, allt till kronor på banken.

  run(Strategy(), "2014-01-01", "2026-10-22", KRAKEN) -> Result

Så går en dag d till:
  1. Gårdagens beslut GENOMFÖRS till dag d:s pris (ingen handel på samma dags pris som beslutet).
  2. Första dagen på ett nytt år betalas förra årets skatt från kontanterna (tvångsförsäljning pro rata om de inte räcker).
  3. Portföljen värderas till dag d:s pris.
  4. Beslut för i morgon: lamps_on(d) + data med datum <= d, level som js/engine.js levelFor, sedan
     walter_paper.propose på en state byggd för dagen. Högst ett beslut per dag.
Sista dagen säljs allt, sista årets skatt räknas direkt och allt tas ut till svensk bank.

Allt i portföljen räknas i börsens valuta (EUR eller SEK) – walter_paper kallar det "SEK", men reglerna är bara
procent så valutan spelar ingen roll för besluten. Skatten räknas i SEK med dagens kurs (Skatteverket).
"""
import copy
import math
import sys
from bisect import bisect_right
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fetcher"))
import walter_paper as wp  # noqa: E402

from backtest import lamps as bl  # noqa: E402
from backtest.costs import Exchange, TaxBook  # noqa: E402

# Dagens regler (data/state.json -> rules och levels, 23 okt 2026). state.json är ägarens fil och finns inte
# i repot, så testet har en egen kopia. Avgifterna i withdrawalFees byts mot börsens i run().
DEFAULT_RULES = {
    "strategy": "lamps",  # den gamla lamp-strategin; autopiloten = autopilot() nedan
    "parkeraAtRed": 7, "wakeAtRed": 5,
    "modes": {"buyAtRed": 2, "buyLittleAtRed": 4, "littleShare": 0.5},
    "paper": {"minTradePct": 2}, "maxInvested": 0.75, "minCash": 0.25,
    "caps": {"BTC": 0.35, "ETH": 0.2, "GOLD": 0.2},
    "unlock": {"early": {"days": 15, "gainPct": 20, "maxDd": 8, "minGreen": 7},
               "normal": {"days": 30, "gainPct": 10, "maxDd": 12}},
    "ethMaxRed": 4,
    "gold": {"vixAbove": 20, "spxBelowMa": True, "allowedWhenParked": True},
    "withdrawalFees": {"takerPct": 0.4, "slippagePct": 0.2, "sepaEur": 1, "fxPct": 1},
    "lampThresholds": {"spxMaDays": 50, "btcMaDays": 200, "btcWeekDropPct": -10, "vixAbove": 20,
                       "us10yRisePp": 0.25, "dxyMaDays": 50, "etfDays": 5, "mvrvZ": 3,
                       "soprAvgDays": 7, "sopr": 1},
    "lampMaxAgeDays": {"default": 4, "etf": 6, "mvrv": 10, "sopr": 10, "cpi": 35},
}
DEFAULT_LEVELS = {"3": {"asset": "GULD", "gainPct": 50, "maxDd": 12}}
SEV = {"OFFENSIV": 0, "NORMAL": 1, "AVVAKTAR": 2, "PARKERA": 3}
BY_SEV = {v: k for k, v in SEV.items()}
LAMPS = 10
_SUGGEST = wp.suggest_mode  # originalet (hysteresis_mode byter tillfälligt ut wp.suggest_mode)


@dataclass
class Strategy:
    """Regler + varianter. Alla varianter är av som standard (= dagens Walter, med närmaste avrundning och
    skattereduktion för förlustår, som är modellrättningar och inte regeländringar)."""
    name: str = "Walter i dag"
    rules: dict = None
    levels: dict = None
    # Modellen
    rounding: str = "nearest"       # röda av 10 från andelen: "nearest" (2,5 -> 3) | "up" (försiktigt) | "down"
    loss_credit: bool = True        # förlustår: skattereduktion för underskottet (på bankkontot, egen rad)
    # Varianter (av = 0/False)
    hysteresis: bool = False        # buffert för alla lägen: till ett lugnare läge krävs 1 lampa till under gränsen
    band_pp: float = 0              # handla bara en tillgång om affären är större än N procentenheter (helsälj alltid)
    no_partial_sells: bool = False  # sälj bara när målet är 0 (aldrig minska mellan Köper/Köper lite/Avvaktar)
    gold_days: int = 0              # guldsignalen måste hålla N dagar i rad för att KÖPA (0 = av)
    gold_confirm_days: int = 0      # guldsignalen byter (på eller av) först när den nya hållit N dagar i rad
    gold_always: bool = False       # ingen guldtajming: guld ligger på sitt tak hela tiden (när Level 3 nåtts)
    no_gold: bool = False
    no_levels: bool = False         # allt upplåst från dag 1
    confirm_days: int = 0           # ett nytt läge måste föreslås N dagar i rad innan Walter byter
    smooth_days: int = 0            # röda = snittet av de senaste N dagarnas poäng (före avrundning)
    cadence_days: int = 1           # beslut bara var N:e dag (7 = en gång i veckan, på söndagar)
    eth_ma_days: int = 30           # ETH köps när ETH/BTC ligger över sitt N-dagarssnitt
    eth_band_pct: float = 0         # ... och byter först när kvoten gått N % förbi snittet (på eller av)
    eth_fixed: bool = False         # ingen ETH/BTC-tajming: ETH följer läget som BTC (när ETH är upplåst)
    # Jämförelser utan lampor: fasta andelar {"BTC": 0.35, ...}
    weights: dict = None
    rebalance: bool = True          # True: tillbaka till andelarna när de glidit mer än minTradePct; False: köp en gång


AUTOPILOT_RULES = dict(copy.deepcopy(DEFAULT_RULES), strategy="autopilot",
                       decision={"weekday": "söndag", "bandPp": 5})


def autopilot(name="Autopilot 35/20/20 (söndag, 5 %-band)", rules=None):
    """Walters strategi sedan 23 okt 2026. Besluten tas av walter_paper.propose (samma kod som live), så att
    historiktestet och Walter inte kan glida isär."""
    return Strategy(name=name, rules=copy.deepcopy(rules or AUTOPILOT_RULES))


def hold_btc(share):
    return Strategy(name=f"Köp en gång: BTC {share * 100:.0f} %", weights={"BTC": share}, rebalance=False)


def mix(weights, rebalance=True, name=None, cadence_days=1, band_pp=0):
    """Jämförelse med fasta andelar, utan lampor (alltid samma andelar, aldrig Vilar).
    cadence_days=7: ombalansera bara söndagar. band_pp=5: bara när en andel glidit mer än 5 % av portföljen."""
    if name is None:
        parts = "+".join(f"{a} {w * 100:.0f}" for a, w in weights.items())
        name = f"{'Ombalanserad' if rebalance else 'Köp en gång'}: {parts} %"
    return Strategy(name=name, weights=dict(weights), rebalance=rebalance, cadence_days=cadence_days,
                    band_pp=band_pp)


@dataclass
class Result:
    strategy: str
    start: str
    end: str
    daily: dict = field(default_factory=dict)      # datum -> värde i SEK på börsen (före uttag och slutskatt)
    tax_out: dict = field(default_factory=dict)    # datum -> hittills uttaget för skatt, SEK (för max_dd)
    modes: dict = field(default_factory=dict)      # datum -> läge efter dagens beslut
    trades: list = field(default_factory=list)
    fees_sek: float = 0.0                           # handel + växling + SEPA
    taxes: dict = field(default_factory=dict)      # år -> betald skatt SEK
    level_days: dict = field(default_factory=dict)  # level -> första dagen
    final_sek: float = 0.0                          # på banken, inklusive skattereduktionen (credit_sek)
    start_sek: float = 0.0
    credits: dict = field(default_factory=dict)    # år -> skattereduktion för förlustår, SEK

    @property
    def tax_sek(self):
        return sum(self.taxes.values())

    @property
    def credit_sek(self):
        return sum(self.credits.values())

    @property
    def n_trades(self):
        return len(self.trades)

    @property
    def cagr(self):
        yrs = (date.fromisoformat(self.end) - date.fromisoformat(self.start)).days / 365.25
        return (self.final_sek / self.start_sek) ** (1 / yrs) - 1 if yrs > 0 and self.final_sek > 0 else None

    @property
    def max_dd(self):
        """Största nedgång från toppen. Skatt som tagits ut räknas tillbaka – den är ingen marknadsförlust."""
        peak, dd = 0.0, 0.0
        for d in sorted(self.daily):
            v = self.daily[d] + self.tax_out.get(d, 0)
            peak = max(peak, v)
            dd = max(dd, (peak - v) / peak if peak else 0)
        return dd


# ---------- Hjälp ----------
class _Asof:
    """Senaste värdet med datum <= dagen (och högst max_age dagar gammalt)."""

    def __init__(self, s):
        self.s = s or {}
        self.k = sorted(self.s)

    def __call__(self, day, max_age=None):
        i = bisect_right(self.k, day)
        if not i:
            return None
        d = self.k[i - 1]
        if max_age is not None and (date.fromisoformat(day) - date.fromisoformat(d)).days > max_age:
            return None
        return self.s[d]


@contextmanager
def _patched(mod, name, fn):
    old = getattr(mod, name)
    setattr(mod, name, fn)
    try:
        yield
    finally:
        setattr(mod, name, old)


def hysteresis_mode(red, current, rules):
    """Som walter_paper.suggest_mode, men ett byte till ett LUGNARE läge kräver att det håller även med en lampa
    till röd (samma idé som Vilar-bufferten, nu för alla lägen). Byte till ett oroligare läge sker direkt."""
    new = _SUGGEST(red, current, rules)
    if current not in SEV or SEV[new] >= SEV[current]:
        return new
    plain = _SUGGEST(red + 1, "", rules)
    return BY_SEV[min(SEV[current], max(SEV[new], SEV[plain]))]


def level_for(value, peak, deposits, days, red, rules, levels):
    """Spegel av js/engine.js levelFor (marknadsvinst över insättningar, drawdown från toppen)."""
    peak = max(peak or 0, value)
    dd = (peak - value) / peak * 100 if peak > 0 else 0
    gain = value - deposits
    pct = gain / deposits * 100 if deposits > 0 else 0
    green = LAMPS - red
    lv3 = (levels or {}).get("3")
    if lv3 and gain > 0 and pct >= lv3["gainPct"] and dd < lv3["maxDd"]:
        return 3
    e, n = rules["unlock"]["early"], rules["unlock"]["normal"]
    early = days >= e["days"] and pct >= e["gainPct"] and dd < e["maxDd"] and green >= e["minGreen"]
    normal = days >= n["days"] and pct >= n["gainPct"] and dd < n["maxDd"]
    return 2 if gain > 0 and (early or normal) else 1


def red_count(score_value, rounding="up"):
    """Andel röda × 10 till ett heltal. "up": 2 av 6 -> 3,3 -> 4 (försiktigt), "nearest": -> 3 (2,5 -> 3),
    "down": -> 3. Liten marginal mot flyttalsfel."""
    v = round(score_value, 6)
    if rounding == "nearest":
        return math.floor(v + 0.5)
    if rounding == "down":
        return math.floor(v)
    return math.ceil(v)


class Confirm:
    """Ett nytt värde gäller först när det setts N dagar i rad (N <= 1: direkt)."""

    def __init__(self, days, value=None):
        self.days, self.value, self.cand, self.n = days, value, None, 0

    def __call__(self, want):
        if want == self.value:
            self.cand, self.n = None, 0
        else:
            self.n = self.n + 1 if want == self.cand else 1
            self.cand = want
            if self.n >= self.days:
                self.value, self.cand, self.n = want, None, 0
        return self.value


def mix_trades(weights, pf, px, total, fee, min_trade, rebalance, bought):
    """Affärer mot fasta andelar. rebalance=False: varje tillgång köps en gång (när priset först finns)."""
    hold, _ = wp.valuation(pf, px)
    cash_free = hold["CASH"] - (1 - sum(weights.values())) * total if rebalance else hold["CASH"]
    trades = []
    for a, w in weights.items():
        if rebalance and px[a] and hold[a] > w * total + min_trade:
            units = (hold[a] - w * total) / px[a]
            trades.append({"asset": a, "side": "sälj", "units": units, "priceSek": px[a],
                           "sek": units * px[a], "feeSek": units * px[a] * fee})
            cash_free += units * px[a] * (1 - fee)
    for a, w in weights.items():
        if not px[a] or (not rebalance and a in bought):
            continue
        sek = min(w * total - hold[a], cash_free)
        if sek > min_trade:
            trades.append({"asset": a, "side": "köp", "units": sek * (1 - fee) / px[a], "priceSek": px[a],
                           "sek": sek, "feeSek": sek * fee})
            cash_free -= sek
            bought.add(a)
    return trades


def filter_trades(prop, pf, total, rules, fee, band_pp=0, no_partial_sells=False):
    """Varianterna band_pp / no_partial_sells: släng affärer, räkna om köpen mot kontanterna som finns."""
    pos = pf.get("positions") or {}
    min_trade = rules["paper"]["minTradePct"] / 100 * total
    cash_free = pf["holdings"]["CASH"] - rules["minCash"] * total
    sells, buys = [], []
    for t in prop["trades"]:
        full = t["side"] == "sälj" and t["units"] >= (pos.get(t["asset"]) or {}).get("units", 0) - 1e-8
        small = band_pp and t["sek"] / total * 100 <= band_pp
        if t["side"] == "sälj":
            if (no_partial_sells and not full) or (small and not full):
                continue
            sells.append(t)
            cash_free += t["sek"] - t["feeSek"]
        elif not small:
            buys.append(t)
    kept = []
    for t in buys:
        sek = min(t["sek"], cash_free)
        if sek < min_trade:
            continue
        cash_free -= sek
        kept.append(dict(t, sek=round(sek, 2), feeSek=round(sek * fee, 2),
                         units=round(sek * (1 - fee) / t["priceSek"], 8)))
    return dict(prop, trades=sells + kept)


# ---------- Körningen ----------
class _Market:
    def __init__(self, series, exchange):
        self.ex = exchange
        self.btc = series.get("btc") or {}
        self.eth = series.get("eth") or {}
        self.gold = _Asof(series.get("gold"))
        self.vix = _Asof(series.get("vix"))
        self.usdsek = _Asof(series.get("usdsek"))
        self.eursek = _Asof(series.get("eursek"))
        self.series = series
        self._ratio = {}

    def rate(self, d):
        """SEK per enhet av börsens valuta."""
        return 1.0 if self.ex.quote == "SEK" else self.eursek(d)

    def usd_q(self, d):
        """Börsens valuta per USD."""
        u, r = self.usdsek(d), self.rate(d)
        return u / r if u and r else None

    def ratio(self, d):
        if d not in self._ratio:
            b, e = self.btc.get(d), self.eth.get(d)
            self._ratio[d] = e / b if b and e else None
        return self._ratio[d]

    def eth_ma(self, d, days):
        """ETH/BTC-snittet över N dagar t.o.m. d. None om historiken är kortare."""
        o = date.fromisoformat(d).toordinal()
        vals = [self.ratio(date.fromordinal(o - i).isoformat()) for i in range(days)]
        if any(v is None for v in vals):
            return None
        return sum(vals) / len(vals)

    def eth_above_ma(self, d, days):
        """ETH/BTC över sitt 30-dagarssnitt (som hämtaren). None om historiken är kortare."""
        ma = self.eth_ma(d, days)
        return None if ma is None else self.ratio(d) > ma

    def build(self, d, lamps=None):
        """Marknadsdelen av en state, som walter_fetch bygger den – men bara data <= d."""
        q = self.usd_q(d)
        btc, ratio, gold = self.btc.get(d), self.ratio(d), self.gold(d, 5)
        vix = self.vix(d, DEFAULT_RULES["lampMaxAgeDays"]["default"])
        spx = (lamps or {}).get("spx")
        return {
            "usdsek": {"value": q},
            "btc": {"value": btc},
            "ethBtc": {"value": ratio},
            "gold": {"value": gold},
            "vix": {"value": vix},
            "spx": {"belowMa": None if spx is None else spx == "red"},
            "ethBtcAbove30dMa": self.eth_above_ma(d, 30) if ratio else None,
        }

    def px(self, d):
        return wp.prices_sek(self.build(d))


def run(strategy, start, end, exchange, start_sek=100000, series=None, lamp_cache=None):
    """lamp_cache: valfri dict som delas mellan körningar på SAMMA serier (snabbare); nyckel = dag + gränser."""
    if series is None:
        from backtest import data
        series = data.load_all()
    rules = copy.deepcopy(strategy.rules or DEFAULT_RULES)
    rules["withdrawalFees"] = dict(rules.get("withdrawalFees", {}), takerPct=exchange.taker_pct,
                                   slippagePct=exchange.slippage_pct)
    if strategy.no_gold:
        rules["caps"]["GOLD"] = 0
    tkey = repr(sorted(rules["lampThresholds"].items())) + repr(sorted((rules.get("lampMaxAgeDays") or {}).items()))
    levels = strategy.levels or DEFAULT_LEVELS
    fee = exchange.trade_fee
    mk = _Market(series, exchange)
    days = [d for d in sorted(mk.btc) if start <= d <= end and mk.rate(d) and mk.usd_q(d)]
    if len(days) < 2:
        raise ValueError("för få dagar med pris")
    res = Result(strategy.name, days[0], days[-1], start_sek=start_sek)
    book = TaxBook()

    rate0 = mk.rate(days[0])
    cash0 = exchange.deposit(start_sek, rate0)
    res.fees_sek += start_sek - cash0 * rate0
    pf = {"start": cash0, "value": cash0, "peak": cash0, "positions": {},
          "holdings": {"BTC": 0, "ETH": 0, "GOLD": 0, "CASH": cash0}, "history": []}
    raw = {"rules": rules, "portfolio": pf, "mode": "AVVAKTAR", "level": 3 if strategy.no_levels else 1,
           "journal": [], "k4": [], "updatedAt": ""}
    res.level_days[raw["level"]] = days[0]
    tax_out_q = 0.0      # uttaget för skatt (räknas tillbaka i levels: skatt är inte marknadsförlust)
    lv_peak = cash0
    paid = set()
    pending = None
    gold_streak = 0
    gold_sig = Confirm(strategy.gold_confirm_days, False)
    mode_ok = Confirm(strategy.confirm_days, raw["mode"])
    eth_on = False
    scores = []
    bought = set()
    min_trade_pct = rules["paper"]["minTradePct"] / 100
    red = 0
    last_year = int(days[0][:4])

    def execute(prop, d, px, why):
        """Gör prop:s affärer till dag d:s pris (antal vid sälj, belopp vid köp) och skriv in via walter_paper.apply."""
        rate = mk.rate(d)
        cash = pf["holdings"]["CASH"]
        pos = pf.get("positions") or {}
        done = []
        for t in prop["trades"]:
            p = px[t["asset"]]
            if p is None:
                continue
            if t["side"] == "sälj":
                units = min(t["units"], (pos.get(t["asset"]) or {}).get("units", 0))
                if units <= 0:
                    continue
                gross = units * p
                done.append({"asset": t["asset"], "side": "sälj", "units": round(units, 8), "priceSek": round(p, 2),
                             "sek": round(gross, 2), "feeSek": round(gross * fee, 2)})
                cash += gross * (1 - fee)
        for t in prop["trades"]:
            p = px[t["asset"]]
            if t["side"] != "köp" or p is None:
                continue
            sek = min(t["sek"], cash)
            if sek <= 0:
                continue
            done.append({"asset": t["asset"], "side": "köp", "units": round(sek * (1 - fee) / p, 8),
                         "priceSek": round(p, 2), "sek": round(sek, 2), "feeSek": round(sek * fee, 2)})
            cash -= sek
        ex = dict(prop, trades=done)
        wp.apply(raw, ex, d)
        for t in done:
            if t["side"] == "köp":
                book.buy(t["asset"], t["units"], t["sek"] * rate)
            else:
                book.sell(d, t["asset"], t["units"], (t["sek"] - t["feeSek"]) * rate)
            res.fees_sek += t["feeSek"] * rate
            res.trades.append(dict(t, date=d, why=why))

    def sell_pro_rata(d, px, need_q, why):
        """Sälj lika stor del av varje innehav så att kontanterna räcker till need_q."""
        hold, _ = wp.valuation(pf, px)
        invested = sum(hold[a] for a in wp.ASSETS if px[a])
        short = need_q - pf["holdings"]["CASH"]
        if short <= 0 or invested <= 0:
            return
        part = min(1.0, short / (invested * (1 - fee)) * 1.0001)
        trades = [{"asset": a, "side": "sälj", "units": pf["positions"][a]["units"] * part}
                  for a in wp.ASSETS if px[a] and (pf["positions"].get(a) or {}).get("units")]
        execute({"mode": raw["mode"], "red": red, "trades": trades}, d, px, why)

    def pay_tax(d, px, year):
        nonlocal tax_out_q
        tax = book.tax(year)
        paid.add(year)
        if tax <= 0:
            if strategy.loss_credit and book.credit(year) > 0:
                res.credits[year] = book.credit(year)
            return
        rate = mk.rate(d)
        need = exchange.quote_for_sek(tax, rate)
        if pf["holdings"]["CASH"] < need:
            sell_pro_rata(d, px, need, "skatt")
        pf["holdings"]["CASH"] = round(pf["holdings"]["CASH"] - need, 2)
        tax_out_q += need
        res.taxes[year] = tax
        res.fees_sek += need * rate - tax

    for i, d in enumerate(days):
        px = mk.px(d)
        if pending is not None:
            execute(pending, d, px, "walter")
            pending = None
        y = int(d[:4])
        if y > last_year:  # första handelsdagen på ett nytt år: betala förra årens skatt
            for yy in range(int(days[0][:4]), y):
                if yy not in paid:
                    pay_tax(d, px, yy)
            last_year = y
        hold, total = wp.valuation(pf, px)
        pf["holdings"].update(hold)
        pf["value"], pf["peak"] = total, max(pf["peak"], total)
        res.daily[d] = total * mk.rate(d)
        res.tax_out[d] = res.tax_sek
        if i == len(days) - 1:
            break

        # ---------- Beslut för i morgon ----------
        if strategy.weights is None and wp.strategy_of(rules) == "autopilot":
            # Live-koden: samma propose som Walter. Lamporna handlar inte, så de räknas inte här.
            prop = wp.propose(dict(raw, market=mk.build(d), lampScore={"source": None}), today=d)
            if prop["trades"]:
                pending = prop  # kollen skrivs i journalen när affärerna genomförs i morgon
            elif prop.get("check"):
                raw["journal"].insert(0, {"date": d, "check": True})  # kollen gjord, inget att göra
            res.modes[d] = "AUTOPILOT"
            continue
        if strategy.weights is not None:
            # cadence_days / band_pp gäller även fasta andelar: ombalansera bara beslutsdagar, och bara när en
            # tillgång glidit mer än max(minTradePct, band_pp) av portföljen (sedan hela vägen tillbaka till målet).
            if strategy.cadence_days > 1 and date.fromisoformat(d).toordinal() % strategy.cadence_days and bought:
                res.modes[d] = "FAST"
                continue
            trades = mix_trades(strategy.weights, pf, px, total, fee,
                                max(min_trade_pct, strategy.band_pp / 100) * total, strategy.rebalance, bought)
            if trades:
                pending = {"mode": "OFFENSIV", "red": 0, "trades": trades}
            res.modes[d] = "FAST"
            continue
        key = (d, tkey)
        lamps = lamp_cache.get(key) if lamp_cache is not None else None
        if lamps is None:
            lamps = bl.lamps_on(d, series, rules["lampThresholds"], rules.get("lampMaxAgeDays"))
            if lamp_cache is not None:
                lamp_cache[key] = lamps
        s, _n = bl.score(lamps)
        if s is None:
            res.modes[d] = raw["mode"]
            continue
        if strategy.smooth_days:
            scores.append(s)
            last = scores[-strategy.smooth_days:]
            s = sum(last) / len(last)
        red = red_count(s, strategy.rounding)
        if not strategy.no_levels:
            lv_value = total + tax_out_q
            lv_peak = max(lv_peak, lv_value)
            days_in = (date.fromisoformat(d) - date.fromisoformat(days[0])).days + 1
            lv = max(raw["level"], level_for(lv_value, lv_peak, cash0, days_in, red, rules, levels))
            if lv > raw["level"]:
                raw["level"] = lv
                res.level_days.setdefault(lv, d)
        if strategy.cadence_days > 1 and date.fromisoformat(d).toordinal() % strategy.cadence_days:
            res.modes[d] = raw["mode"]  # ingen beslutsdag
            continue
        m = mk.build(d, lamps)
        if rules["gold"].get("spxBelowMa", True) is False:
            m = dict(m, spx={"belowMa": False})  # guld bara på VIX (spx.belowMa används bara till guldet)
        g_on = strategy.gold_always or wp.gold_wanted(m, rules["gold"])
        if strategy.gold_days:
            gold_streak = gold_streak + 1 if g_on else 0
            g_on = g_on and gold_streak >= strategy.gold_days
        if strategy.gold_confirm_days:
            g_on = gold_sig(g_on)
        if not g_on:
            m = dict(m, vix={"value": None}, spx={"belowMa": False})
        elif strategy.gold_confirm_days or strategy.gold_always:
            m = dict(m, spx={"belowMa": True})
        ratio = m["ethBtc"]["value"]
        if strategy.eth_fixed:
            m["ethBtcAbove30dMa"] = True if ratio else None
        elif ratio and (strategy.eth_ma_days != 30 or strategy.eth_band_pct):
            ma = mk.eth_ma(d, strategy.eth_ma_days)
            if ma is None:
                m["ethBtcAbove30dMa"] = None
            else:
                b = strategy.eth_band_pct / 100
                if ratio > ma * (1 + b):
                    eth_on = True
                elif ratio < ma * (1 - b) or (not b and ratio <= ma):
                    eth_on = False
                m["ethBtcAbove30dMa"] = eth_on
        state = dict(raw, market=m, lampScore={"source": "data", "red": red})
        suggest = hysteresis_mode if strategy.hysteresis else _SUGGEST
        if strategy.confirm_days:
            mode_ok.value = raw["mode"]
            chosen = mode_ok(suggest(red, raw["mode"], rules))
            suggest = lambda *_a, _c=chosen, **_k: _c  # noqa: E731
        with _patched(wp, "suggest_mode", suggest):
            prop = wp.propose(state)
        if strategy.band_pp or strategy.no_partial_sells:
            prop = filter_trades(prop, pf, total, rules, fee, strategy.band_pp, strategy.no_partial_sells)
        if prop["trades"] or prop["mode"] != raw["mode"]:
            pending = prop
        res.modes[d] = prop["mode"]

    # ---------- Sista dagen: sälj allt, skatt, uttag ----------
    d = days[-1]
    px = mk.px(d)
    trades = [{"asset": a, "side": "sälj", "units": p["units"]}
              for a, p in (pf.get("positions") or {}).items() if p.get("units")]
    if trades:
        execute({"mode": raw["mode"], "red": red, "trades": trades}, d, px, "slut")
    tax_left = 0.0
    for yy in sorted({int(x[:4]) for x in days} - paid):
        t = book.tax(yy)
        if t > 0:
            res.taxes[yy] = t
            tax_left += t
        elif strategy.loss_credit and book.credit(yy) > 0:
            res.credits[yy] = book.credit(yy)
        paid.add(yy)
    rate = mk.rate(d)
    bank, wfee = exchange.withdraw(pf["holdings"]["CASH"], rate)
    res.fees_sek += wfee
    res.final_sek = bank - tax_left + res.credit_sek
    res.book, res.raw = book, raw  # för tester och felsökning
    return res
