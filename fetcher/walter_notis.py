"""WALTER notis: morgon 08:13 och kväll 22:05 (svensk tid), på vanlig svenska.

  python fetcher/walter_notis.py              körs av Actionen efter hämtningen
  python fetcher/walter_notis.py morgon       tvinga morgon-notis (manuellt test)
  python fetcher/walter_notis.py kvall --dry  visa texten, skriv inget, skicka inget

GitHub-cron går i UTC, så Actionen startar både sommar- och vintertidens UTC-tid.
Skriptet räknar fram vilken svensk tid schemat gällde och skickar bara när den är
08:13 eller 22:05 – den andra körningen hoppar över. Notisen sparas i cache.json
(visas överst på sidan) och skickas till Telegram om TELEGRAM_TOKEN och
TELEGRAM_CHAT_ID finns.
"""

import json
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from walter_fetch import BASE, CACHE, HTTP, build, num, pct, read_json  # noqa: E402

TZ = ZoneInfo("Europe/Stockholm")
SLOTS = {(8, 13): "morgon", (22, 5): "kvall"}
LABEL = {"morgon": "Morgon", "kvall": "Kväll"}


def slot_from_schedule(cron):
    """'13 6 * * *' -> 'morgon' om 06:13 UTC i dag är 08:13 i Stockholm, annars None."""
    try:
        minute, hour = (int(x) for x in cron.split()[:2])
    except ValueError:
        return None
    utc = datetime.now(timezone.utc).replace(hour=hour, minute=minute, second=0, microsecond=0)
    local = utc.astimezone(TZ)
    return SLOTS.get((local.hour, local.minute))


def text_for(state, slot, when):
    pf, m = state["portfolio"], state["market"]
    value, cash = pf["value"], pf["holdings"]["CASH"]
    money = f"Cash {num(cash)} kr vilar" if cash >= value else f"Cash {num(cash)} kr, {num(value - cash)} kr investerat"
    btc = m.get("btc", {})
    if btc.get("value") is None:
        btc_txt = "BTC väntar på data"
    elif btc.get("changePct24h") is not None:
        btc_txt = f"BTC ${num(btc['value'])} ({pct(btc['changePct24h'], 2)} på ett dygn)"
    else:
        btc_txt = f"BTC ${num(btc['value'])}"
    s = state["lampScore"]
    return (f"{LABEL[slot]} {when}: {money}, {btc_txt}, totalt {num(value)} kr. "
            f"{s['red']}/{s['total']} lampor röda. Walter håller {state['mode']}.")


def telegram(text):
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token:
        print("Ingen TELEGRAM_TOKEN – notisen visas bara på sidan.")
        return
    if not chat:
        print("TELEGRAM_TOKEN finns men TELEGRAM_CHAT_ID saknas – kan inte skicka till Telegram.")
        return
    try:
        r = HTTP.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text}, timeout=20)
        print("Skickat till Telegram." if r.ok else f"Telegram svarade {r.status_code}.")
    except Exception as e:  # token sitter i URL:en – skriv bara feltypen
        print(f"Telegram svarade inte ({type(e).__name__}).")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    forced = (args[0] if args else os.environ.get("WALTER_NOTIS", "")).replace("ä", "a").lower()
    slot = forced if forced in LABEL else slot_from_schedule(os.environ.get("WALTER_SCHEDULE", ""))
    if not slot:
        print("Ingen notis den här körningen.")
        return

    when = datetime.now(TZ).strftime("%H:%M") if forced in LABEL else \
        next(f"{h:02d}:{mi:02d}" for (h, mi), v in SLOTS.items() if v == slot)
    cache = read_json(CACHE, {})
    state = build(read_json(BASE, None), json.loads(json.dumps(cache)), True)
    text = text_for(state, slot, when)
    print(text)
    if dry:
        return

    cache["notis"] = {"slot": slot, "text": text, "at": datetime.now(TZ).isoformat(timespec="seconds")}
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    telegram(text)


if __name__ == "__main__":
    main()
