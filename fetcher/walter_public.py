"""Publik marknadsfil: lampor, läge, priser och regler + daglig logg. Aldrig ägarens data."""
import json
import os
from datetime import date as _date
from pathlib import Path

import walter_paper as wp

LOG_KEYS = ("date", "ready", "red", "px", "ethBtcAbove30dMa", "vix", "spxBelowMa")


def _value(m, key):
    return (m.get(key) or {}).get("value")


def _age_days(as_of, day):
    try:
        return (_date.fromisoformat(day) - _date.fromisoformat(as_of[:10])).days
    except (TypeError, ValueError):
        return None


def _fresh_px(m, px, day, rules):
    """Gammal data får aldrig loggas som dagens pris: pris utan datum från idag blir null."""
    max_age = (rules.get("lampMaxAgeDays") or {}).get("default", 4)
    fx_age = _age_days((m.get("usdsek") or {}).get("asOf"), day)
    if fx_age is None or fx_age > max_age:
        return {k: None for k in px}
    src = {"BTC": "btc", "ETH": "btc", "GOLD": "gold"}
    return {k: v if (m.get(src[k]) or {}).get("asOf") == day else None for k, v in px.items()}


LEVEL_KEYS = ("asset", "name", "gainPct", "maxDd")


def _public_levels(levels):
    """Bara nivåernas regler (vad som låses upp och kraven), aldrig ägarens datum eller texter."""
    if not levels:
        return None
    return {k: {f: v[f] for f in LEVEL_KEYS if f in v} for k, v in levels.items()}


def snapshot(state):
    m = state.get("market", {})
    lamps = [{k: l.get(k) for k in ("id", "name", "rule", "status", "value", "asOf")} for l in state["lamps"]]
    ready = bool(lamps) and all(l["status"] is not None for l in lamps)
    red = sum(l["status"] == "red" for l in lamps)
    below = (m.get("btc") or {}).get("belowMa200")
    fetched = state.get("fetchedAt")
    day = (fetched or m.get("asOf") or state.get("updatedAt") or "")[:10]
    px = _fresh_px(m, wp.prices_sek(m), day, state["rules"])
    return {
        "date": day,
        "fetchedAt": fetched,
        "ready": ready,
        "red": red,
        "mode": wp.suggest_mode(red, "AVVAKTAR", state["rules"]) if ready else None,
        "lamps": lamps,
        "px": {k: px.get(k) for k in ("BTC", "ETH", "GOLD")},
        "usdsek": m.get("usdsek"),
        "eursek": m.get("eursek"),
        "ethBtcAbove30dMa": m.get("ethBtcAbove30dMa"),
        "btcLong": None if below is None else not below,
        "vix": _value(m, "vix"),
        "spxBelowMa": (m.get("spx") or {}).get("belowMa"),
        "rules": state["rules"],
        "levels": _public_levels(state.get("levels")),
        "version": state.get("version"),
    }


def append_log(log, snap):
    row = {k: snap.get(k) for k in LOG_KEYS}
    rows = {r["date"]: r for r in log}
    old = rows.get(row["date"])
    if old and old.get("ready") and not row["ready"]:
        return [rows[d] for d in sorted(rows)]  # en klar dag skrivs aldrig över av en halvfärdig
    rows[row["date"]] = row
    return [rows[d] for d in sorted(rows)]


def write_market_js(snap, log, path):
    path = Path(path)
    body = json.dumps({"now": snap, "log": log}, indent=2, ensure_ascii=False)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("// GENERERAD av fetcher/walter_fetch.py – publik marknadsdata, ändra inte här.\n"
                   f"window.WALTER_MARKET = {body};\n", encoding="utf-8")
    os.replace(tmp, path)
