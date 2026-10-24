"""WALTER trade-motor för paper.

  python fetcher/walter_paper.py        visa Walters förslag och handla manuellt (skriv JA)
  paper.bat                            samma sak, dubbelklick
  python fetcher/walter_paper.py --auto Walter handlar själv (bara GitHub Actionen), ingen fråga

Hämtaren (walter_fetch.py) räknar förslaget vid varje hämtning och lägger det i state.js, men handlar aldrig.
Walter handlar själv i Actionen (--auto) högst en gång per dag och skriver journalposten med "auto": true.
Varje affär skrivs in i data/state.json: läge, positioner, kontanter, historik, journalpost och K4-rad
för varje försäljning. Läget ändras alltså fortfarande bara via journalen.

Läge från röda lampor (rules): 0–buyAtRed = Köper, upp till buyLittleAtRed = Köper lite, sedan Avvaktar,
parkeraAtRed+ = Vilar. Buffert: från Vilar vaknar Walter först vid wakeAtRed eller färre röda.
Omkostnad räknas med genomsnittsmetoden (Skatteverkets regel för krypto), avgift = taker + slippage.
"""

import json
import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import walter_vault  # noqa: E402

ASSETS = ("BTC", "ETH", "GOLD")
NAMES = {"BTC": "bitcoin", "ETH": "ethereum", "GOLD": "guld"}
K4_NAMES = {"BTC": "Bitcoin (BTC)", "ETH": "Ethereum (ETH)", "GOLD": "Guld (PAXG)"}
WORDS = {"PARKERA": "Vilar", "AVVAKTAR": "Avvaktar", "NORMAL": "Köper lite", "OFFENSIV": "Köper"}
# Autopiloten: lamporna säger hur marknaden mår, inte vad Walter gör
MOODS = {"PARKERA": "mycket orolig", "AVVAKTAR": "orolig", "NORMAL": "blandad", "OFFENSIV": "lugn"}
SHARPE_DAYS = 30


def num(v, d=0):
    s = f"{abs(v):,.{d}f}".replace(",", " ").replace(".", ",")
    return ("−" if v < 0 else "") + s


# ---------- Läge ----------
def suggest_mode(red, current, rules):
    """Vilket läge lamporna pekar på. Bufferten: står Walter i Vilar krävs wakeAtRed eller färre för att vakna."""
    if red >= rules["parkeraAtRed"] or (current == "PARKERA" and red > rules["wakeAtRed"]):
        return "PARKERA"
    if red <= rules["modes"]["buyAtRed"]:
        return "OFFENSIV"
    if red <= rules["modes"]["buyLittleAtRed"]:
        return "NORMAL"
    return "AVVAKTAR"


# ---------- Priser och värde ----------
def prices_sek(m):
    """Pris i SEK per enhet. None = väntar på data (då handlas inte den tillgången)."""
    fx = (m.get("usdsek") or {}).get("value")
    btc = (m.get("btc") or {}).get("value")
    eth_btc = (m.get("ethBtc") or {}).get("value")
    gold = (m.get("gold") or {}).get("value")  # PAXG i USD (CoinGecko pax-gold)
    return {
        "BTC": btc * fx if btc and fx else None,
        "ETH": eth_btc * btc * fx if eth_btc and btc and fx else None,
        "GOLD": gold * fx if gold and fx else None,
    }


def valuation(pf, px):
    """Innehav i SEK till dagens pris. Saknas pris används senast godkända värdet."""
    pos = pf.get("positions") or {}
    hold = {}
    for a in ASSETS:
        units = (pos.get(a) or {}).get("units", 0)
        hold[a] = round(units * px[a], 2) if units and px[a] else (0 if not units else pf["holdings"].get(a, 0))
    hold["CASH"] = pf["holdings"]["CASH"]
    return hold, round(sum(hold.values()), 2)


# ---------- Förslag ----------
def gold_wanted(m, g):
    vix, spx = (m.get("vix") or {}).get("value"), (m.get("spx") or {}).get("belowMa")
    return (vix is not None and vix > g["vixAbove"]) or spx is True


def stockholm_today():
    return datetime.now(ZoneInfo("Europe/Stockholm")).date().isoformat()


def strategy_of(rules):
    """Autopiloten är standard. "lamps" = den gamla strategin där lamporna och läget handlar."""
    return rules.get("strategy") or "autopilot"


def propose(state, today=None, assets=None):
    """Walters förslag från en byggd state (lamporna räknade). Ändrar ingenting.
    today = svenskt datum (YYYY-MM-DD). assets = vad börsen har {tillgång: True}; None = allt."""
    today = today or stockholm_today()
    if strategy_of(state["rules"]) == "autopilot":
        return propose_autopilot(state, today, assets)
    return propose_lamps(state, today)


# ---------- Autopiloten ----------
WEEKDAYS = {"måndag": 0, "tisdag": 1, "onsdag": 2, "torsdag": 3, "fredag": 4, "lördag": 5, "söndag": 6,
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
DAY_WORDS = ("måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag")
MONTHS = ("jan", "feb", "mars", "apr", "maj", "juni", "juli", "aug", "sep", "okt", "nov", "dec")


def decision(rules):
    """(veckodag 0-6, band i procentenheter) från rules.decision. Standard: söndag, 5."""
    d = rules.get("decision") or {}
    return WEEKDAYS[str(d.get("weekday", "söndag")).lower()], d.get("bandPp", 5)


def next_check(today, rules):
    """Nästa beslutsdag efter today (är today beslutsdag: en vecka fram)."""
    t = date.fromisoformat(today)
    return (t + timedelta(days=(decision(rules)[0] - t.weekday()) % 7 or 7)).isoformat()


def last_check(journal, pf):
    """Senaste autopilot-kollen: nyaste journalpost med "check": true, annars första affären (eller None)."""
    for e in journal or []:
        if e.get("check"):
            return e["date"]
    return pf.get("firstTrade")


def is_due(today, rules, pf, journal):
    """Beslutsdag? Första affären någonsin: alltid. Annars beslutsveckodagen, eller första dagen efter en missad
    beslutsdag (senaste kollen före den senaste beslutsdagen). Redan kollat i dag: nej. -> (due, first, catch_up)"""
    if not pf.get("firstTrade"):
        return True, True, False
    t, wd = date.fromisoformat(today), decision(rules)[0]
    lc = last_check(journal, pf)
    if lc == today:
        return False, False, False
    if t.weekday() == wd:
        return True, False, False
    last_dd = (t - timedelta(days=(t.weekday() - wd) % 7)).isoformat()
    missed = lc is None or lc < last_dd
    return missed, False, missed


def day_text(iso):
    d = date.fromisoformat(iso)
    return f"{DAY_WORDS[d.weekday()]} {d.day} {MONTHS[d.month - 1]}"


def weights_for(rules, assets=None, glide=1.0):
    """Målandelar (rules.caps) gånger målläget (glide, 0..1). Det börsen saknar får andel 0 och ligger som kontanter."""
    caps = rules.get("caps") or {}
    w = {a: float(caps.get(a, 0)) * glide for a in ASSETS}
    missing = [a for a in ASSETS if assets is not None and assets.get(a) is not True]
    for a in missing:
        w[a] = 0.0
    return w, missing


# ---------- Målläge ----------
GLIDE_DAYS = 730.5  # 24 månader


def _iso(v):
    try:
        return date.fromisoformat(v) if isinstance(v, str) and len(v) == 10 else None
    except ValueError:
        return None


def glide_factor(goal, today):
    """Målläget: från 24 månader före måldatumet skalas autopilotens andelar med f = dagar kvar / 730,5,
    begränsat till 0..1 och avrundat till 4 decimaler. Inget mål (eller inget giltigt datum) = 1.
    Samma kod som js/engine.js glideFactor (paritetstest)."""
    g = _iso((goal or {}).get("date")) if isinstance(goal, dict) else None
    if g is None:
        return 1.0
    days = (g - date.fromisoformat(today)).days
    return round(min(1.0, max(0.0, days / GLIDE_DAYS)), 4)


# ---------- Månadssparande ----------
SAVINGS_NOTE = "månadssparande"


def savings_plan(s):
    """(belopp, dag) ur savings = {monthlySek, day 1..28, since}. None = av (belopp 0 eller ogiltigt)."""
    if not isinstance(s, dict):
        return None
    amt, d = s.get("monthlySek"), s.get("day", 25)
    if isinstance(amt, bool) or not isinstance(amt, (int, float)) or not math.isfinite(amt) or amt <= 0:
        return None
    if isinstance(d, float) and d.is_integer():
        d = int(d)  # 25.0 i JSON är samma dag som 25 (som Number.isInteger i JS)
    if isinstance(d, bool) or not isinstance(d, int) or not 1 <= d <= 28:
        return None
    return float(amt), d


def savings_due(s, history, today):
    """Månader (YYYY-MM) vars sparande ska in i dag: sparandedagen har passerat, inte före savings.since,
    och månaden finns inte redan som historikrad (note månadssparande, month). Saknas since räknas bara
    innevarande månad. Två missade månader = två insättningar. Samma kod som js/engine.js savingsDue."""
    plan = savings_plan(s)
    if not plan:
        return []
    d = plan[1]
    since = _iso(s.get("since"))
    done = max((h["month"] for h in history or [] if h.get("note") == SAVINGS_NOTE
                and isinstance(h.get("month"), str)), default="")
    t = date.fromisoformat(today)
    y, m = (since.year, since.month) if since else (t.year, t.month)
    out = []
    while (y, m) <= (t.year, t.month):
        key = f"{y:04d}-{m:02d}"
        when = f"{key}-{d:02d}"
        if when <= today and (since is None or when >= since.isoformat()) and key > done:
            out.append(key)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def savings_trades(px, hold, total, weights, rules, fee, deposit):
    """Månadssparandet investeras direkt, bara med de nya pengarna och bara köp: varje tillgång som ligger
    under sin andel (efter insättningen) får sin lucka fylld, skalat så att minCash håller. Affärer under
    minTradePct av INSÄTTNINGEN görs inte (av portföljen skulle varje vanligt sparbelopp stanna i kontanter).
    Saknas pris väntar den tillgången (de pengarna ligger kvar som kontanter). -> (affärer, väntar), oavrundade."""
    free = min(deposit, hold["CASH"] - rules["minCash"] * total)
    min_trade = rules["paper"]["minTradePct"] / 100 * deposit
    gaps, waiting = {}, []
    for a in ASSETS:
        gap = weights[a] * total - hold[a]
        if weights[a] > 0 and gap > 0:
            if px[a] is None:
                waiting.append(a)
            else:
                gaps[a] = gap
    g = sum(gaps.values())
    if free <= 0 or g <= 0:
        return [], waiting
    scale = min(1.0, free / g)
    trades = []
    for a in ASSETS:
        if a not in gaps:
            continue
        sek = gaps[a] * scale
        if sek < min_trade:
            continue
        trades.append({"asset": a, "side": "köp", "units": sek * (1 - fee) / px[a], "priceSek": px[a],
                       "sek": sek, "feeSek": sek * fee})
    return trades, waiting


def month_list(months):
    return _list([MONTHS[int(k[5:7]) - 1] for k in months])


def savings_text(sav, past):
    """Walters ord om månadssparandet. past=True i journalen ("köpte"), annars "köper"."""
    s = f"Månadssparande: {num(sav['sek'])} kr in" + (f" ({month_list(sav['months'])})." if len(sav["months"]) > 1 else ".")
    buys = [f"{NAMES[t['asset']]} för {num(t['sek'])} kr" for t in sav["trades"]]
    if buys:
        s += f" Jag {'köpte' if past else 'köper'} {_list(buys)}."
    elif not sav["waiting"]:
        s += " Pengarna ligger som kontanter tills vidare."
    if sav["waiting"]:
        s += f" Jag väntar på pris för {_list([NAMES[a] for a in sav['waiting']])}, så den delen ligger som kontanter."
    return s


def rebalance_trades(pf, px, hold, total, weights, rules, fee, sell_all=False):
    """Autopilotens affärer: en tillgång som glidit MER än bandet (minst minTradePct) från sin andel går hela
    vägen tillbaka till andelen. Sälj först, köp sedan med kontanterna över minCash. Affärer under minTradePct
    görs inte. Saknas pris väntar den tillgången. sell_all (målets datum är nått): allt säljs, även inom bandet.
    Returnerar (affärer, väntar), oavrundade."""
    band = max(rules["paper"]["minTradePct"], decision(rules)[1]) / 100 * total
    min_trade = rules["paper"]["minTradePct"] / 100 * total
    cash_free = hold["CASH"] - rules["minCash"] * total
    pos = pf.get("positions") or {}
    trades, waiting = [], []
    for a in ASSETS:
        target = weights[a] * total
        if hold[a] > target + (0 if sell_all and target == 0 else band):
            if px[a] is None:
                waiting.append(a); continue
            units = pos[a]["units"] if target == 0 else (hold[a] - target) / px[a]
            gross = units * px[a]
            trades.append({"asset": a, "side": "sälj", "units": units, "priceSek": px[a],
                           "sek": gross, "feeSek": gross * fee})
            cash_free += gross * (1 - fee)
    for a in ASSETS:
        target = weights[a] * total
        if target > hold[a] + band:
            if px[a] is None:
                waiting.append(a); continue
            sek = min(target - hold[a], cash_free)
            if sek < min_trade:
                continue
            trades.append({"asset": a, "side": "köp", "units": sek * (1 - fee) / px[a], "priceSek": px[a],
                           "sek": sek, "feeSek": sek * fee})
            cash_free -= sek
    return trades, waiting


def _list(xs):
    return xs[0] if len(xs) < 2 else ", ".join(xs[:-1]) + " och " + xs[-1]


def autopilot_plain(trades, hold, total, weights, first, due, today, rules, waiting, wanted_missing,
                    catch_up=False, checked_today=False):
    """Walters egna ord om autopiloten. Samma text som js/engine.js (paritetstest)."""
    wd = decision(rules)[0]
    nxt = f"Nästa koll {day_text(next_check(today, rules))}."
    today_word = DAY_WORDS[date.fromisoformat(today).weekday()]
    head = ("Första dagen" if first else
            f"{today_word.capitalize()} ({DAY_WORDS[wd]}ens koll)" if catch_up else today_word.capitalize())
    if not due:
        s = f"Dagens koll är gjord. {nxt}" if checked_today else f"Jag handlar bara på {DAY_WORDS[wd]}ar. {nxt}"
    elif trades:
        parts, fresh = [], []
        for t in trades:
            a = t["asset"]
            share, w = round(hold[a] / total * 100) if total else 0, round(weights[a] * 100)
            if t["side"] == "sälj":
                parts.append(f"{NAMES[a]} har vuxit till {share} % – jag säljer för {num(t['sek'])} kr, "
                             f"tillbaka till {w} %.")
            elif hold[a] <= 0 or share == 0:  # inget (eller bara en sparslant) än: "jag köper bitcoin för …"
                fresh.append(f"{NAMES[a]} för {num(t['sek'])} kr ({w} %)")
            else:
                parts.append(f"{NAMES[a]} ligger på {share} % – jag köper för {num(t['sek'])} kr, "
                             f"tillbaka till {w} %.")
        if fresh:
            parts.append(f"jag köper {_list(fresh)}.")
        parts = [parts[0]] + [p[0].upper() + p[1:] for p in parts[1:]]
        s = f"{head}: {' '.join(parts)} {nxt}"
    elif first:
        s = "Jag börjar så fort jag har priserna."
    elif waiting:
        s = f"{head}: jag väntar på pris för {_list([NAMES[a] for a in waiting])}. Jag försöker igen i morgon."
        waiting = []
    else:
        s = f"{head}: allt ligger inom marginalen. Jag rör ingenting. {nxt}"
    if waiting:
        s += f" Jag väntar på pris för {_list([NAMES[a] for a in waiting])}."
    for a in wanted_missing:
        s += f" {NAMES[a].capitalize()} finns inte på din börs, så den delen ligger kvar som kontanter."
    return s


def propose_autopilot(state, today, assets=None):
    """Fasta andelar (rules.caps), koll på beslutsdagen (rules.decision.weekday, svenskt datum). Första affären
    någonsin (firstTrade saknas) får ske vilken dag som helst. Lamporna räknas bara för läget (väderrapporten)."""
    r, m, pf = state["rules"], state["market"], state["portfolio"]
    score = state.get("lampScore") or {}
    current = state["mode"]
    lamps_ok = score.get("source") == "data"
    red = score["red"] if lamps_ok else None
    mode = suggest_mode(red, current, r) if lamps_ok else current
    px = prices_sek(m)
    # Målläget: andelarna krymper mot kontanter de sista 24 månaderna före målets datum
    glide = glide_factor(state.get("goal"), today)
    weights, missing = weights_for(r, assets, glide)
    wanted = [a for a in ASSETS if (r.get("caps") or {}).get(a, 0) > 0 and a not in missing]
    if wanted and all(px[a] is None for a in wanted):  # inga priser alls: vänta (samma som js/engine.js)
        return {"asOf": today, "ready": False, "strategy": "autopilot", "red": red, "mode": current,
                "currentMode": current, "trades": [], "valueSek": None, "missing": missing, "waiting": [],
                "plain": "Jag väntar på priser innan jag gör något.", "needsApproval": False}
    hold, total = valuation(pf, px)
    journal = state.get("journal") or []
    due, first, catch_up = is_due(today, r, pf, journal)
    fee = (r["withdrawalFees"]["takerPct"] + r["withdrawalFees"]["slippagePct"]) / 100
    # Månadssparandet: in som kontanter, köp direkt med bara de nya pengarna. Sedan söndagens vanliga koll
    # på portföljen efter sparköpen.
    months = savings_due(state.get("savings"), pf.get("history"), today)
    sav, s_trades, hold2, total2 = None, [], hold, total
    if months:
        each = savings_plan(state["savings"])[0]
        dep = each * len(months)
        hold2 = dict(hold, CASH=hold["CASH"] + dep)
        total2 = total + dep
        s_trades, s_wait = savings_trades(px, hold2, total2, weights, r, fee, dep)
        for t in s_trades:
            hold2[t["asset"]] += t["units"] * px[t["asset"]]
            hold2["CASH"] -= t["sek"]
        total2 = sum(hold2.values())
        sav = {"months": months, "eachSek": each, "sek": dep, "valueBefore": round(total, 2), "trades": s_trades,
               "waiting": s_wait}
    trades, waiting = (rebalance_trades(pf, px, hold2, total2, weights, r, fee, glide == 0 and bool(state.get("goal")))
                       if due else ([], []))
    for t in s_trades + trades:
        for k in ("sek", "feeSek", "priceSek"):
            t[k] = round(t[k], 2)
        t["units"] = round(t["units"], 8)
    wanted_missing = [a for a in missing if (r.get("caps") or {}).get(a, 0) > 0]
    plain = autopilot_plain(trades, hold2, total2, weights, first, due, today, r, waiting, wanted_missing,
                            catch_up, last_check(journal, pf) == today and not first)
    plain_auto = plain
    if sav:
        plain = savings_text(sav, False) + " " + (plain if due else f"Nästa koll {day_text(next_check(today, r))}.")
    return {"asOf": today, "ready": True, "strategy": "autopilot", "red": red, "mode": mode, "currentMode": current,
            "trades": s_trades + trades, "valueSek": round(total, 2), "plain": plain, "plainAuto": plain_auto,
            # Kollen skrivs i journalen på beslutsdagen, och en ikapp-dag bara när kollen blev klar (inget väntar på pris),
            # så att ett prisavbrott efter en missad söndag inte ger en journalpost per dag.
            "needsApproval": bool(trades) or bool(sav) or mode != current or (due and (not catch_up or not waiting)),
            "decisionDay": due,
            # En koll räknas som gjord när inget väntar på pris (annars görs den om nästa dag).
            "check": due and not waiting,
            "nextCheck": next_check(today, r), "weights": weights, "missing": missing, "waiting": waiting,
            "glide": glide, "savings": sav}


def propose_lamps(state, today):
    """Den gamla strategin (rules.strategy = "lamps"): lamporna väljer läge, läget och Levels styr affärerna."""
    r, m, pf = state["rules"], state["market"], state["portfolio"]
    score = state["lampScore"]
    if score.get("source") != "data":
        return {"asOf": today, "ready": False,
                "plain": "Walter väntar på data för alla tio lampor innan han föreslår något."}

    red, current = score["red"], state["mode"]
    mode = suggest_mode(red, current, r)
    px = prices_sek(m)
    hold, total = valuation(pf, px)
    share = {"OFFENSIV": 1, "NORMAL": r["modes"]["littleShare"], "AVVAKTAR": None, "PARKERA": 0}[mode]
    level = state["level"]

    # Mål i SEK per tillgång. None = behåll det som finns (Avvaktar).
    target = {}
    target["BTC"] = None if share is None else r["caps"]["BTC"] * share * total
    eth_ok = (level >= 2 and (target["BTC"] or 0) > 0 and m.get("ethBtcAbove30dMa") is True
              and red <= r["ethMaxRed"])
    target["ETH"] = None if share is None else (r["caps"]["ETH"] * share * total if eth_ok else 0)
    # Guld är skyddet: följer oron, inte läget, och får köpas även när Walter vilar.
    target["GOLD"] = r["caps"]["GOLD"] * total if level >= 3 and gold_wanted(m, r["gold"]) else 0

    fee = (r["withdrawalFees"]["takerPct"] + r["withdrawalFees"]["slippagePct"]) / 100
    min_trade = r["paper"]["minTradePct"] / 100 * total
    cash_free = hold["CASH"] - r["minCash"] * total
    trades, waiting = [], []
    for a in ASSETS:  # sälj först, så att kontanterna finns till köpen
        if target[a] is not None and target[a] < hold[a] - min_trade:
            if px[a] is None:
                waiting.append(a); continue
            units = (pf["positions"][a]["units"] if target[a] == 0
                     else (hold[a] - target[a]) / px[a])
            gross = units * px[a]
            trades.append({"asset": a, "side": "sälj", "units": units, "priceSek": px[a],
                           "sek": gross, "feeSek": gross * fee})
            cash_free += gross * (1 - fee)
    for a in ASSETS:
        if target[a] is not None and target[a] > hold[a] + min_trade:
            if px[a] is None:
                waiting.append(a); continue
            sek = min(target[a] - hold[a], cash_free)
            if sek < min_trade:
                continue
            trades.append({"asset": a, "side": "köp", "units": sek * (1 - fee) / px[a], "priceSek": px[a],
                           "sek": sek, "feeSek": sek * fee})
            cash_free -= sek

    for t in trades:
        for k in ("sek", "feeSek", "priceSek"):
            t[k] = round(t[k], 2)
        t["units"] = round(t["units"], 8)

    word = WORDS[mode]
    if trades:
        what = " och ".join(f"{t['side']}a {NAMES[t['asset']]} för {num(t['sek'])} kr" for t in trades)
        plain = f"{red} av 10 lampor är röda. Walter vill {what}."
    elif mode != current:
        plain = f"{red} av 10 lampor är röda. Walter vill byta läge till {word}, men inte handla något."
    else:
        plain = f"{red} av 10 lampor är röda. Walter {word.lower()} och vill inte ändra något."
    if mode == "PARKERA" and current == "PARKERA" and red < r["parkeraAtRed"]:
        plain += f" Han vilar kvar tills det är {r['wakeAtRed']} eller färre röda (bufferten)."
    if waiting:
        plain += f" Väntar på pris för {', '.join(NAMES[a] for a in waiting)}."
    return {"asOf": today, "ready": True, "red": red, "mode": mode, "currentMode": current,
            "trades": trades, "valueSek": round(total, 2), "plain": plain,
            "needsApproval": bool(trades) or mode != current}


# ---------- Sharpe ----------
def sharpe(daily, flows, first_trade, today=None):
    """Sharpe (årstakt, riskfri ränta 0) på dagliga värden. Insättningar räknas bort ur avkastningen.
    None tills det finns SHARPE_DAYS dagar riktig handel. daily = {datum: värde}, flows = {datum: belopp}."""
    if not first_trade:
        return {"value": None, "days": 0, "need": SHARPE_DAYS}
    days = (date.fromisoformat(today or date.today().isoformat()) - date.fromisoformat(first_trade)).days
    pts = sorted((d, v) for d, v in daily.items() if d >= first_trade)
    rets = [(v1 - flows.get(d1, 0)) / v0 - 1 for (_, v0), (d1, v1) in zip(pts, pts[1:]) if v0 > 0]
    if days < SHARPE_DAYS or len(rets) < 2:
        return {"value": None, "days": max(days, 0), "need": SHARPE_DAYS}
    mean = sum(rets) / len(rets)
    sd = (sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)) ** 0.5
    return {"value": round(mean / sd * math.sqrt(365), 2) if sd > 0 else None, "days": days, "need": SHARPE_DAYS}


# ---------- Godkänn ----------
def apply(raw, prop, today):
    """Skriver förslaget in i state.json-innehållet (raw). Returnerar journalposten."""
    pf, r = raw["portfolio"], raw["rules"]
    pos = pf.setdefault("positions", {})
    facts, k4 = [], raw.setdefault("k4", [])
    hist = pf.setdefault("history", [])
    sav = prop.get("savings")
    if sav:  # månadssparandet: en historikrad med flow per månad, före affärerna
        if hist and hist[-1]["date"] == today and not hist[-1].get("flow"):
            hist.pop()
        cash = pf["holdings"]["CASH"]
        for i, mth in enumerate(sav["months"]):
            cash = round(cash + sav["eachSek"], 2)
            hist.append({"date": today, "value": round(sav["valueBefore"] + sav["eachSek"] * (i + 1), 2), "cash": cash,
                         "flow": sav["eachSek"], "note": SAVINGS_NOTE, "month": mth})
            facts.append(f"Månadssparande {mth}: +{num(sav['eachSek'])} kr (låtsasinsättning)")
        pf["holdings"]["CASH"] = cash
    for t in prop["trades"]:
        a, p = t["asset"], pos.setdefault(t["asset"], {"units": 0, "costSek": 0, "since": today})
        if t["side"] == "köp":
            if not p["units"]:
                p["since"] = today
            p["units"] += t["units"]
            p["costSek"] += t["sek"]  # omkostnad inkl. avgift
            pf["holdings"]["CASH"] -= t["sek"]
        else:
            part = min(1, t["units"] / p["units"])
            cost = p["costSek"] * part  # genomsnittsmetoden
            k4.append({"id": f"{a.lower()}-{today}-{len(k4) + 1}", "beteckning": K4_NAMES[a],
                       "antal": t["units"], "kopdatum": p["since"], "saljdatum": today,
                       "forsaljningspris_sek": t["sek"], "omkostnad_sek": round(cost, 2),
                       "trading_fee_sek": t["feeSek"], "withdrawal_fee_sek": 0, "typ": "PAPER",
                       "not": "Omkostnad enligt genomsnittsmetoden. Avgift = taker + slippage."})
            p["units"] = round(p["units"] - t["units"], 8) if part < 1 else 0
            p["costSek"] = round(p["costSek"] - cost, 2) if part < 1 else 0
            pf["holdings"]["CASH"] += t["sek"] - t["feeSek"]
        p["units"], p["costSek"] = round(p["units"], 8), round(p["costSek"], 2)
        facts.append(f"{t['side'].capitalize()}: {num(t['units'], 8)} {a} à {num(t['priceSek'])} kr = "
                     f"{num(t['sek'], 2)} kr, avgift {num(t['feeSek'], 2)} kr")
    pf["holdings"]["CASH"] = round(pf["holdings"]["CASH"], 2)
    px = {t["asset"]: t["priceSek"] for t in prop["trades"]}
    for a in ASSETS:
        units = (pos.get(a) or {}).get("units", 0)
        if a in px:
            pf["holdings"][a] = round(units * px[a], 2)
    pf["value"] = round(sum(pf["holdings"].values()), 2)
    pf["peak"] = max(pf["peak"], pf["value"])
    if prop["trades"] and not pf.get("firstTrade"):
        pf["firstTrade"] = today
    note = "/".join(sorted({t["side"] for t in prop["trades"]})) or "läge"
    if hist and hist[-1]["date"] == today and not hist[-1].get("flow"):
        hist.pop()
    hist.append({"date": today, "value": pf["value"], "cash": pf["holdings"]["CASH"], "note": note})

    raw["mode"] = prop["mode"]
    raw["updatedAt"] = max(raw["updatedAt"], today)
    auto_pilot = prop.get("strategy") == "autopilot"
    if prop.get("red") is not None:
        facts.append(f"Marknaden {MOODS[prop['mode']]}: {prop['red']}/10 varningar" if auto_pilot
                     else f"{prop['red']}/10 röda lampor → {WORDS[prop['mode']]}")
    if auto_pilot:
        facts.append("Autopilot: " + " · ".join(f"{a} {round(w * 100)} %" for a, w in prop["weights"].items()))
    if auto_pilot and prop.get("glide", 1) < 1:
        facts.append(f"Målläge: {round(prop['glide'] * 100)} % av vanliga andelar")
    facts.append(f"Kontant {num(pf['holdings']['CASH'])} kr av {num(pf['value'])} kr")
    rest = prop["trades"][len(sav["trades"]):] if sav else prop["trades"]
    done = " och ".join(f"{'köpte' if t['side'] == 'köp' else 'sålde'} {NAMES[t['asset']]} för {num(t['sek'])} kr"
                        for t in rest)
    if auto_pilot:
        weather = (f"Marknaden är {MOODS[prop['mode']]} ({prop['red']} av 10 varningar) – det ändrar inte vad jag gör. "
                   if prop.get("red") is not None else "")
        said = (f"WALTER {done}. Autopiloten justerade andelarna. " if done
                else f"{prop.get('plainAuto', prop['plain'])} " if prop.get("decisionDay") else "")
        plain = (savings_text(sav, True) + " " if sav else "") + said + weather + \
            f"{num(pf['holdings']['CASH'])} kr ligger som kontanter."
    else:
        plain = (f"WALTER {done}. " if done else "") + \
            f"{prop['red']} av 10 lampor var röda, så läget är {WORDS[prop['mode']]}. " \
            f"{num(pf['holdings']['CASH'])} kr ligger som kontanter."
    entry = {"date": today, "mode": prop["mode"], "red": prop["red"], "plain": plain, "facts": facts}
    if auto_pilot and prop.get("check"):
        entry["check"] = True  # autopilotens koll är gjord i dag (se is_due)
    if sav:
        entry["savings"] = {"sek": sav["sek"], "months": list(sav["months"])}
    raw["journal"].insert(0, entry)
    return entry


def rebuild(wf):
    """Bygg state från state.json + marknadscache + ägarens cache (daily, notis)."""
    cache, owner = wf.load_caches()
    return wf.build(wf.read_json(wf.BASE, None), cache, False, owner)


def auto(wf, today=None, say=lambda s: None):
    """Walter handlar själv (bara i GitHub Actionen, steget "Walter handlar själv").
    Högst en automatisk handel per dag: är journal[0] redan dagens och automatisk görs inget.
    Skriver state.json, låser state.enc och bygger om state.js. Returnerar journalposten eller None."""
    today = today or stockholm_today()
    raw = wf.read_json(wf.BASE, None)
    if raw is None:
        say("Hittar inte data/state.json – Walter handlar inte.")
        return None
    last = (raw.get("journal") or [None])[0] or {}
    if last.get("date") == today and last.get("auto"):
        say(f"Walter har redan handlat själv i dag ({today}).")
        return None
    prop = propose(rebuild(wf), today=today)
    if not prop.get("ready") or not prop.get("needsApproval"):
        say("Walter handlar inte: " + prop.get("plain", "inget förslag."))
        return None
    code = walter_vault.owner_key()
    if not code:  # utan kod kan state.enc inte sparas – då vore affären borta vid nästa körning
        say("WALTER_OWNER_KEY saknas – Walter handlar inte (affären skulle inte kunna sparas).")
        return None
    entry = apply(raw, prop, today)
    entry["auto"] = True
    walter_vault._write_atomic(wf.BASE, json.dumps(raw, indent=2, ensure_ascii=False) + "\n")
    walter_vault.lock_state(code, wf.BASE, walter_vault.ENC)
    wf.write_js(rebuild(wf))
    say(f"Walter handlade själv: {entry['plain']}")
    # Rad för Actionens commit-meddelande: handlade (affär), koll (autopilotens koll) eller läge (bara läget).
    say("WALTER_COMMIT=" + ("handlade" if prop["trades"] else "koll" if entry.get("check") else "läge"))
    return entry


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import walter_fetch as wf

    if "--auto" in sys.argv[1:]:
        auto(wf, say=print)
        return
    # Walter kan ha handlat i Actionen – hämta det först. Är läget oklart handlas inget manuellt,
    # så att ett JA aldrig skriver över en state.enc med Walters egen affär.
    if walter_vault.sync_from_repo() in ("local", "pullfail"):
        print("\nInget handlat. Reda ut state.json/state.enc först (se ovan), kör sedan paper.bat igen.")
        return
    built = rebuild(wf)
    prop = propose(built)
    print("\nWALTER FÖRESLÅR\n" + prop["plain"])
    if not prop.get("ready") or not prop["needsApproval"]:
        print("\nInget att godkänna.")
        return
    for t in prop["trades"]:
        print(f"  {t['side'].upper():5} {t['asset']:4} {num(t['sek'], 2):>14} kr  avgift {num(t['feeSek'], 2)} kr")
    if input("\nSkriv JA för att godkänna (paper, inga riktiga pengar): ").strip().upper() != "JA":
        print("Inget ändrat.")
        return
    raw = wf.read_json(wf.BASE, None)
    entry = apply(raw, prop, stockholm_today())
    wf.BASE.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    wf.write_js(rebuild(wf))
    if walter_vault.owner_key():
        walter_vault.lock_state()  # state.enc är det som går till main
    else:
        wf.warn("WALTER_OWNER_KEY saknas – state.enc är inte uppdaterad. Kör 'walter_vault.py las' när koden finns.")
    print(f"\nKlart. Journalpost {entry['date']}: {entry['plain']}\nSkrev data/state.json och data/state.js.")


if __name__ == "__main__":
    main()
