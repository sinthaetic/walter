"""Avgifter och svensk skatt för historiktestet.

Exchange: börsens kostnader. Per affär = taker + prisglidning på affärsbeloppet. Växling (fx_pct) bara när pengar
går in (SEK -> börsens valuta vid start) och ut (börsens valuta -> SEK), aldrig per affär. SEPA-avgift vid uttag.

TaxBook: Skatteverkets regler för krypto (PAXG räknas likadant, som "annan tillgång"):
- Genomsnittsmetoden per tillgång. Köpavgiften ingår i omkostnaden, säljavgiften minskar försäljningspriset.
- Vinst/förlust räknas vid varje försäljning, i SEK (dagens kurs).
- Per kalenderår: skattepliktigt = vinster − 0,7 × förluster, skatt = 30 % × max(0, skattepliktigt).
- Är skattepliktigt NEGATIVT (nettoförlust) blir det underskott av kapital: skattereduktion 30 % av underskottet
  upp till 100 000 kr och 21 % av resten (credit). Den minskar ägarens skatt på annat (lön/annan kapitalinkomst),
  så pengarna hamnar på bankkontot, inte på börsen. Antagande: ägaren har så mycket annan skatt att dra av mot.
  Inget förs vidare till nästa år (så funkar det för privatpersoner).
"""
from dataclasses import dataclass

TAX_RATE = 0.30
LOSS_DEDUCTIBLE = 0.70
DEFICIT_CAP = 100000     # underskott av kapital: 30 % upp till hit, 21 % över
DEFICIT_RATE_ABOVE = 0.21


@dataclass(frozen=True)
class Exchange:
    name: str = "börs"
    taker_pct: float = 0.8
    slippage_pct: float = 0.2
    quote: str = "EUR"        # "EUR" | "SEK"
    fx_pct: float = 1.0       # SEK<->EUR, bara vid insättning och uttag
    sepa_sek: float = 10.0    # per uttag till svensk bank

    @property
    def trade_fee(self):
        """Andel av affärsbeloppet som går till avgift (taker + glidning)."""
        return (self.taker_pct + self.slippage_pct) / 100

    @property
    def fx(self):
        return 0.0 if self.quote == "SEK" else self.fx_pct / 100

    def deposit(self, sek, rate):
        """SEK in -> belopp i börsens valuta. rate = SEK per enhet av börsens valuta."""
        return sek * (1 - self.fx) / rate

    def withdraw(self, amount, rate):
        """Belopp i börsens valuta ut -> (SEK på banken, avgifter i SEK)."""
        gross = amount * rate
        sek = gross * (1 - self.fx) - self.sepa_sek
        return sek, gross - sek

    def quote_for_sek(self, sek, rate):
        """Hur mycket av börsens valuta som måste tas ut för att `sek` ska landa på banken."""
        return (sek + self.sepa_sek) / (1 - self.fx) / rate


KRAKEN = Exchange("Kraken", 0.8, 0.2, "EUR", 1.0, 10.0)
BITSTAMP = Exchange("Bitstamp", 0.4, 0.2, "EUR", 1.0, 10.0)
SAFELLO = Exchange("Safello", 0.6, 0.2, "SEK", 0.0, 0.0)


class TaxBook:
    """Omkostnad (genomsnittsmetoden) och realiserat resultat per kalenderår, allt i SEK."""

    def __init__(self):
        self.units = {}      # tillgång -> antal
        self.cost = {}       # tillgång -> total omkostnad SEK (inkl. köpavgifter)
        self.gains = {}      # år -> summa vinster
        self.losses = {}     # år -> summa förluster (positivt tal)
        self.sales = []      # (datum, tillgång, antal, försäljningspris, omkostnad, resultat)

    def buy(self, asset, units, cost_sek):
        """cost_sek = hela beloppet som betalades, inklusive avgift."""
        self.units[asset] = self.units.get(asset, 0) + units
        self.cost[asset] = self.cost.get(asset, 0) + cost_sek

    def avg_cost(self, asset):
        u = self.units.get(asset, 0)
        return self.cost.get(asset, 0) / u if u else 0.0

    def sell(self, day, asset, units, proceeds_sek):
        """proceeds_sek = försäljningspris efter avgift. Returnerar resultatet (vinst > 0)."""
        held = self.units.get(asset, 0)
        if units <= 0 or held <= 0:
            return 0.0
        part = min(1.0, units / held)
        basis = self.cost[asset] * part
        result = proceeds_sek - basis
        if part >= 1 - 1e-12:
            self.units[asset], self.cost[asset] = 0, 0
        else:
            self.units[asset] = held - units
            self.cost[asset] -= basis
        y = int(day[:4])
        if result >= 0:
            self.gains[y] = self.gains.get(y, 0) + result
        else:
            self.losses[y] = self.losses.get(y, 0) - result
        self.sales.append((day, asset, units, proceeds_sek, basis, result))
        return result

    def taxable(self, year):
        return self.gains.get(year, 0) - LOSS_DEDUCTIBLE * self.losses.get(year, 0)

    def tax(self, year):
        return TAX_RATE * max(0.0, self.taxable(year))

    def credit(self, year):
        """Skattereduktion för underskott av kapital (förlustår), SEK. 0 om året gick plus."""
        deficit = max(0.0, -self.taxable(year))
        return TAX_RATE * min(deficit, DEFICIT_CAP) + DEFICIT_RATE_ABOVE * max(0.0, deficit - DEFICIT_CAP)
