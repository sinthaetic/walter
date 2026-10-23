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
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import walter_vault  # noqa: E402

ASSETS = ("BTC", "ETH", "GOLD")
NAMES = {"BTC": "bitcoin", "ETH": "ethereum", "GOLD": "guld"}
K4_NAMES = {"BTC": "Bitcoin (BTC)", "ETH": "Ethereum (ETH)", "GOLD": "Guld (PAXG)"}
WORDS = {"PARKERA": "Vilar", "AVVAKTAR": "Avvaktar", "NORMAL": "Köper lite", "OFFENSIV": "Köper"}
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


def propose(state):
    """Walters förslag från en byggd state (lamporna räknade). Ändrar ingenting."""
    r, m, pf = state["rules"], state["market"], state["portfolio"]
    score = state["lampScore"]
    today = date.today().isoformat()
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
    hist = pf.setdefault("history", [])
    if hist and hist[-1]["date"] == today and not hist[-1].get("flow"):
        hist.pop()
    hist.append({"date": today, "value": pf["value"], "cash": pf["holdings"]["CASH"], "note": note})

    raw["mode"] = prop["mode"]
    raw["updatedAt"] = max(raw["updatedAt"], today)
    facts.append(f"{prop['red']}/10 röda lampor → {WORDS[prop['mode']]}")
    facts.append(f"Kontant {num(pf['holdings']['CASH'])} kr av {num(pf['value'])} kr")
    done = " och ".join(f"{'köpte' if t['side'] == 'köp' else 'sålde'} {NAMES[t['asset']]} för {num(t['sek'])} kr"
                        for t in prop["trades"])
    plain = (f"WALTER {done}. " if done else "") + \
        f"{prop['red']} av 10 lampor var röda, så läget är {WORDS[prop['mode']]}. " \
        f"{num(pf['holdings']['CASH'])} kr ligger som kontanter."
    entry = {"date": today, "mode": prop["mode"], "red": prop["red"], "plain": plain, "facts": facts}
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
    today = today or date.today().isoformat()
    raw = wf.read_json(wf.BASE, None)
    if raw is None:
        say("Hittar inte data/state.json – Walter handlar inte.")
        return None
    last = (raw.get("journal") or [None])[0] or {}
    if last.get("date") == today and last.get("auto"):
        say(f"Walter har redan handlat själv i dag ({today}).")
        return None
    prop = propose(rebuild(wf))
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
    entry = apply(raw, prop, date.today().isoformat())
    wf.BASE.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    wf.write_js(rebuild(wf))
    if walter_vault.owner_key():
        walter_vault.lock_state()  # state.enc är det som går till main
    else:
        wf.warn("WALTER_OWNER_KEY saknas – state.enc är inte uppdaterad. Kör 'walter_vault.py las' när koden finns.")
    print(f"\nKlart. Journalpost {entry['date']}: {entry['plain']}\nSkrev data/state.json och data/state.js.")


if __name__ == "__main__":
    main()
