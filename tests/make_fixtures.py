"""Skriver testfixturer under tests/fixtures/. Kör om när motorn ändras:
  .venv/Scripts/python.exe tests/make_fixtures.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "fetcher"))

import copy  # noqa: E402

import walter_paper  # noqa: E402
import walter_vault  # noqa: E402


def vault_sample():
    """Skrivs bara om den saknas (ny salt varje gång annars, så att filen ändras i onödan)."""
    if (FIX / "vault-sample.enc").exists():
        return
    env = walter_vault.encrypt({"hej": "världen", "n": 1.5}, "TEST-KOD", iter=1000)
    (FIX / "vault-sample.enc").write_text(json.dumps(env), encoding="utf-8")


# Börs med samma avgift som Python (taker + slippage) och SEK som quote, så att fxPct inte läggs på.
PARITY_EXCHANGE = {"id": "test", "quote": "SEK", "takerPct": 0.4, "slippagePct": 0.2, "fxPct": 1,
                   "assets": {"BTC": True, "ETH": True, "GOLD": True}}
MARKET = {"btc": 1050000.37, "ethBtc": 0.0363, "gold": 37000.5}


def _pf(cash, units=None, day="2026-10-01"):
    """Portfölj med kontanter och ev. positioner {tillgång: (enheter, omkostnad)}, värderad till MARKET."""
    px = walter_paper.prices_sek(_market(20, False, False))
    pos, hold = {}, {"BTC": 0, "ETH": 0, "GOLD": 0, "CASH": cash}
    for a, (u, cost) in (units or {}).items():
        pos[a] = {"units": u, "costSek": cost, "since": day}
        hold[a] = round(u * px[a], 2)
    value = round(sum(hold.values()), 2)
    return {"start": 100000, "value": value, "peak": max(value, 100000), "holdings": hold, "positions": pos,
            "firstTrade": day if units else None,
            "history": [{"date": day, "value": 100000, "cash": 100000, "note": "start", "flow": 100000}]}


def _market(vix, spx_below, eth_above):
    return {"usdsek": {"value": 1}, "btc": {"value": MARKET["btc"]}, "ethBtc": {"value": MARKET["ethBtc"]},
            "gold": {"value": MARKET["gold"]}, "vix": {"value": vix}, "spx": {"belowMa": spx_below},
            "ethBtcAbove30dMa": eth_above}


def engine_cases():
    """Python-motorn är facit: samma indata som en loggrad, förväntat utfall från propose/apply."""
    rules = dict(json.loads((ROOT / "data" / "state.json").read_text(encoding="utf-8"))["rules"], strategy="lamps")
    btc_full = (0.033, 30000)   # ≈ 34,6 % av ~100 000 kr
    cases = [  # namn, röda, läge, level, portfölj, vix, S&P under snitt, ETH/BTC över snitt
        ("offensiv_from_cash", 1, "AVVAKTAR", 1, _pf(100000), 15, False, False),
        ("normal_half_caps", 3, "AVVAKTAR", 1, _pf(100000), 15, False, False),
        ("normal_cash_100000_20", 3, "AVVAKTAR", 1, _pf(100000.20), 15, False, False),  # mål 17 500,035
        ("normal_trims_btc", 3, "OFFENSIV", 1, _pf(65350, {"BTC": btc_full}), 15, False, False),
        ("avvaktar_keeps", 5, "NORMAL", 1, _pf(82000, {"BTC": (0.017, 17500)}), 15, False, False),
        ("parkera_sells_all", 7, "NORMAL", 1, _pf(82000, {"BTC": (0.017, 17500)}), 15, False, False),
        ("buffer_6_stays_parked", 6, "PARKERA", 1, _pf(100000), 15, False, False),
        ("buffer_5_wakes", 5, "PARKERA", 1, _pf(100000), 15, False, False),
        ("eth_level2", 2, "OFFENSIV", 2, _pf(65350, {"BTC": btc_full}), 15, False, True),
        ("gold_level3_parked", 8, "PARKERA", 3, _pf(82000, {"BTC": (0.017, 17500)}), 25, False, False),
    ]
    day, out = "2026-10-05", []
    for name, red, mode, level, pf, vix, spx, eth in cases:
        m = _market(vix, spx, eth)
        state = {"rules": rules, "market": m, "portfolio": copy.deepcopy(pf), "mode": mode, "level": level,
                 "lampScore": {"source": "data", "red": red}}
        prop = walter_paper.propose(state)
        raw = {"portfolio": copy.deepcopy(pf), "rules": rules, "mode": mode, "updatedAt": day,
               "journal": [], "k4": []}
        walter_paper.apply(raw, prop, day)
        row = {"date": day, "ready": True, "red": red, "px": walter_paper.prices_sek(m),
               "ethBtcAbove30dMa": eth, "vix": vix, "spxBelowMa": spx}
        out.append({"name": name, "row": row, "user": {"mode": mode, "level": level, "portfolio": pf},
                    "expect": {"mode": prop["mode"], "valueSek": prop["valueSek"], "trades": prop["trades"],
                               "portfolio": raw["portfolio"]}})
    doc = {"rules": rules, "exchange": PARITY_EXCHANGE, "cases": out, "autopilot": autopilot_cases(rules)}
    (FIX / "engine-cases.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")


def autopilot_cases(lamp_rules):
    """Autopiloten (rules.strategy = "autopilot"): samma indata i Python och JS, Python är facit."""
    rules = dict(lamp_rules, strategy="autopilot", decision={"weekday": "söndag", "bandPp": 5})
    sun, fri = "2026-10-25", "2026-10-23"
    px = walter_paper.prices_sek(_market(20, False, False))
    # ≈ 35/20/20/25 av ~100 000 kr till MARKET-priserna
    near = {"BTC": (0.034, 34000), "ETH": (0.52, 19000), "GOLD": (0.55, 20000)}
    near_cash = 100000 - sum(round(u * px[a], 2) for a, (u, _c) in near.items())
    heavy = {"BTC": (0.042, 34000), "ETH": (0.52, 19000), "GOLD": (0.30, 20000)}  # BTC ≈ 42 %, guld ≈ 11 %
    no_gold = {"BTC": True, "ETH": True}
    checked = [{"date": "2026-10-19", "check": True}]  # kollen efter söndag 18 okt är gjord
    cases = [  # namn, dag, röda, läge, portfölj, börsens tillgångar, {journal, ready, gold, prices}
        ("ap_sunday_within_band", sun, 3, "NORMAL", _pf(near_cash, near), None, {}),
        ("ap_sunday_outside_band", sun, 3, "NORMAL", _pf(near_cash, heavy), None, {}),
        ("ap_weekday_waits", fri, 3, "NORMAL", _pf(near_cash, heavy), None, {"journal": checked}),
        ("ap_first_trade_weekday", fri, 8, "AVVAKTAR", _pf(100000), None, {}),
        ("ap_missing_gold_on_exchange", fri, 1, "AVVAKTAR", _pf(100000), no_gold, {}),
        ("ap_missing_price", sun, 3, "NORMAL", _pf(100000), None, {"gold": False}),
        # Lamporna inte klara: autopiloten handlar på priserna, läget står kvar (vädret väntar)
        ("ap_lamps_not_ready", fri, 3, "AVVAKTAR", _pf(100000), None, {"ready": False}),
        # Söndag 18 okt missades (senaste koll 11 okt): fredag 23 okt gör kollen en gång
        ("ap_missed_sunday", fri, 3, "NORMAL", _pf(near_cash, heavy), None,
         {"journal": [{"date": "2026-10-11", "check": True}]}),
        ("ap_checked_today", sun, 3, "NORMAL", _pf(near_cash, heavy), None,
         {"journal": [{"date": sun, "check": True}]}),
        # Missad söndag + guldpris saknas + inget annat att göra: ingen journalpost (görs om i morgon, tyst)
        ("ap_missed_sunday_price_outage", fri, 3, "NORMAL",
         _pf(near_cash, {"BTC": near["BTC"], "ETH": near["ETH"], "GOLD": (0.30, 20000)}), None,
         {"journal": [{"date": "2026-10-11", "check": True}], "gold": False}),
        # Samma på själva söndagen: kollen skrivs (en gång) fast guldet väntar
        ("ap_sunday_price_outage", sun, 3, "NORMAL",
         _pf(near_cash, {"BTC": near["BTC"], "ETH": near["ETH"], "GOLD": (0.30, 20000)}), None, {"gold": False}),
        ("ap_no_prices", sun, 3, "NORMAL", _pf(near_cash, heavy), None, {"prices": False, "ready": False}),
    ]
    out = []
    for name, day, red, mode, pf, assets, o in cases:
        m = _market(15, False, False)
        if not o.get("gold", True):
            m["gold"] = {"value": None}
        if not o.get("prices", True):
            m["btc"], m["gold"] = {"value": None}, {"value": None}
        ready, journal = o.get("ready", True), o.get("journal", [])
        state = {"rules": rules, "market": m, "portfolio": copy.deepcopy(pf), "mode": mode, "level": 1,
                 "journal": copy.deepcopy(journal),
                 "lampScore": {"source": "data" if ready else "journal", "red": red}}
        prop = walter_paper.propose(state, today=day, assets=assets)
        raw = {"portfolio": copy.deepcopy(pf), "rules": rules, "mode": mode, "updatedAt": day,
               "journal": copy.deepcopy(journal), "k4": []}
        entry = walter_paper.apply(raw, prop, day) if prop["ready"] else None
        ex = dict(PARITY_EXCHANGE, assets=assets or PARITY_EXCHANGE["assets"])
        row = {"date": day, "ready": ready, "red": red, "px": walter_paper.prices_sek(m),
               "ethBtcAbove30dMa": False, "vix": 15, "spxBelowMa": False}
        out.append({"name": name, "row": row, "exchange": ex,
                    "user": {"mode": mode, "level": 1, "portfolio": pf, "journal": journal},
                    "expect": {"ready": prop["ready"], "mode": prop["mode"], "red": prop["red"],
                               "valueSek": prop["valueSek"], "trades": prop["trades"],
                               "plain": prop["plain"], "nextCheck": prop.get("nextCheck"),
                               "decisionDay": prop.get("decisionDay"), "check": prop.get("check"),
                               "needsApproval": prop["needsApproval"],
                               "waiting": prop["waiting"], "missing": prop["missing"],
                               "entryCheck": bool(entry and entry.get("check")),
                               "portfolio": raw["portfolio"]}})
    return {"rules": rules, "cases": out}


def main():
    FIX.mkdir(parents=True, exist_ok=True)
    vault_sample()
    engine_cases()
    print("Fixturer skrivna i", FIX)


if __name__ == "__main__":
    main()
