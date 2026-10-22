"""WALTER auto: avgör om GitHub Actionen ska hämta just nu.

  python fetcher/walter_auto.py [gh-pages-cache.json]

PARKERA + senaste hämtning < 3 timmar                       -> hoppa över.
NORMAL/OFFENSIV, öppen position, manuell körning eller push  -> kör.
Notis-tiderna (08:13 / 22:05)                               -> kör alltid.
Öppen position = minst ett innehav (utom CASH) över 1 000 kr; mindre är damm.
Skickas en cache.json från gh-pages med och den är nyare än data/cache.json
används den, så att hämtaren bygger vidare på senast publicerade värden.
Skriver run=true/false till $GITHUB_OUTPUT.
"""

import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "state.json"
CACHE = ROOT / "data" / "cache.json"
TZ = ZoneInfo("Europe/Stockholm")  # hämtaren skriver fetchedAt i svensk tid
PARK_INTERVAL = timedelta(hours=3)
DUST_KR = 1000  # innehav upp till detta räknas inte som öppen position
NOTIS_CRONS = {"13 7 * * *", "13 6 * * *", "5 21 * * *", "5 20 * * *"}  # samma som i walter-auto.yml


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def fetched_at(cache):
    raw = (cache or {}).get("fetchedAt")
    if not raw:
        return None
    t = datetime.fromisoformat(raw)
    return t if t.tzinfo else t.replace(tzinfo=TZ)


def newest_cache(pages_path):
    """Lägg den nyaste av main- och gh-pages-cachen i data/cache.json."""
    pages = read_json(pages_path) if pages_path else None
    if fetched_at(pages) and (not fetched_at(read_json(CACHE)) or fetched_at(pages) > fetched_at(read_json(CACHE))):
        shutil.copyfile(pages_path, CACHE)
        print("Använder cache.json från gh-pages (nyast).")


def decide(state, cache, event):
    mode = str(state.get("mode", "")).upper()
    holdings = state.get("portfolio", {}).get("holdings", {})
    open_pos = [k for k, v in holdings.items() if k != "CASH" and (v or 0) > DUST_KR]

    if event in ("workflow_dispatch", "push"):
        return True, f"startad via {event}"
    if os.environ.get("WALTER_SCHEDULE", "").strip() in NOTIS_CRONS:
        return True, "notis-tid – hämtar färskt före morgon/kväll-notisen"
    if mode != "PARKERA":
        return True, f"läge {mode} – vi är i trade, ska vara live"
    if open_pos:
        return True, f"öppen position ({', '.join(open_pos)})"
    last = fetched_at(cache)
    if last is None:
        return True, "ingen tidigare hämtning"
    age = datetime.now(TZ) - last
    if age < PARK_INTERVAL:
        return False, f"PARKERA och senaste hämtning är bara {int(age.total_seconds() // 60)} min gammal"
    return True, f"PARKERA och senaste hämtning är {age.total_seconds() / 3600:.1f} h gammal"


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    newest_cache(sys.argv[1] if len(sys.argv) > 1 else None)
    state = read_json(STATE)
    if state is None:
        # Utan state.json (ingen WALTER_OWNER_KEY / state.enc gick inte att låsa upp) går inget att bygga.
        # Hoppa över i stället för att krascha – senast publicerade sidan ligger kvar.
        print(f"::warning::Hittar inte {STATE.name} (saknas WALTER_OWNER_KEY?) – hoppar över, sidan lämnas orörd.")
        run, why = False, "ingen state.json"
    else:
        run, why = decide(state, read_json(CACHE), os.environ.get("GITHUB_EVENT_NAME", ""))
    print(("KÖR: " if run else "HOPPAR ÖVER: ") + why)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"run={'true' if run else 'false'}\n")


if __name__ == "__main__":
    main()
