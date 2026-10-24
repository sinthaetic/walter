"""Walters lampor bakåt i tiden -> data/pulse.js för översiktens graf (rutan WALTERS LAMPOR).

  python -m backtest.pulse        (läser backtest/cache/, hämtar det som saknas)

Skriver window.WALTER_PULSE = [[datum, röda], ...]: en rad per dag (bitcoins kalender), röda av 10 från
backtest/lamps.score med närmaste avrundning (sim.red_count "nearest"), från första dagen med minst 4 lampor.
Dagar med för få lampor hoppas över. Bara datum och heltal – publik marknadsdata, ingen ägardata.
Nya dagar kommer från market.js-loggen i webbläsaren (js/cipher-chart.js mergePulse), så filen behöver
bara byggas om när historiken ska förlängas.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest import lamps as bl  # noqa: E402
from backtest import sim  # noqa: E402

OUT = ROOT / "data" / "pulse.js"


def build(series, rules=None, days=None):
    """[[datum, röda]] för varje dag i days (standard: bitcoins datum) där minst 4 lampor har värde."""
    rules = rules or sim.DEFAULT_RULES
    days = days if days is not None else sorted(series.get("btc") or {})
    out = []
    for d in days:
        s, _ = bl.score(bl.lamps_on(d, series, rules["lampThresholds"], rules.get("lampMaxAgeDays")))
        if s is None:
            continue
        out.append([d, sim.red_count(s, "nearest")])
    return out


def render(rows):
    body = ",\n".join(f'["{d}",{r}]' for d, r in rows)
    return ("// GENERERAD av backtest/pulse.py – publik marknadsdata: röda lampor av 10 per dag. Ändra inte här.\n"
            "window.WALTER_PULSE = [\n" + body + "\n];\n")


def write(rows, path=OUT):
    Path(path).write_text(render(rows), encoding="utf-8", newline="\n")


def main():
    from backtest import data
    rows = build(data.load_all())
    write(rows)
    print(f"Skrev {OUT.relative_to(ROOT)}: {len(rows)} dagar, {rows[0][0] if rows else '-'} till {rows[-1][0] if rows else '-'}.")


if __name__ == "__main__":
    main()
