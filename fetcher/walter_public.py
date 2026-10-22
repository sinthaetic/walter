"""Publik marknadsfil: lampor, läge, priser och regler + daglig logg. Aldrig ägarens data."""
import json
import os
from pathlib import Path

import walter_paper as wp

LOG_KEYS = ("date", "ready", "red", "px", "ethBtcAbove30dMa", "vix", "spxBelowMa")


def _value(m, key):
    return (m.get(key) or {}).get("value")


def snapshot(state):
    m = state.get("market", {})
    lamps = [{k: l.get(k) for k in ("id", "name", "rule", "status", "value", "asOf")} for l in state["lamps"]]
    ready = bool(lamps) and all(l["status"] is not None for l in lamps)
    red = sum(l["status"] == "red" for l in lamps)
    below = (m.get("btc") or {}).get("belowMa200")
    px = wp.prices_sek(m)
    fetched = state.get("fetchedAt")
    return {
        "date": (fetched or m.get("asOf") or state.get("updatedAt") or "")[:10],
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
    }


def append_log(log, snap):
    row = {k: snap.get(k) for k in LOG_KEYS}
    rows = {r["date"]: r for r in log}
    rows[row["date"]] = row
    return [rows[d] for d in sorted(rows)]


def write_market_js(snap, log, path):
    path = Path(path)
    body = json.dumps({"now": snap, "log": log}, indent=2, ensure_ascii=False)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("// GENERERAD av fetcher/walter_fetch.py – publik marknadsdata, ändra inte här.\n"
                   f"window.WALTER_MARKET = {body};\n", encoding="utf-8")
    os.replace(tmp, path)
