// Börslistan: kryptobörser som har MiCA-tillstånd och får erbjuda tjänster i Sverige.
// Tillståndet är kontrollerat mot ESMA:s interimsregister för CASP (CASPS.csv, uppdaterad 2026-10-22).
// Varje börs har lägsta nivåns taker-avgift för spot (inte "instant buy"), en källa och datumet den kontrollerades.
// Kommer en avgift inte att gå att styrka tas börsen bort, inte gissas. Binance finns inte i registret och är därför inte med.
// slippagePct = 0,2 för alla (samma antagande som rules.withdrawalFees). Sorterad på namn.
window.WALTER_EXCHANGES = [
  {
    id: "bitstamp", name: "Bitstamp",
    licence: { country: "LU", authority: "CSSF (Bitstamp Europe S.A.)", register: "ESMA" },
    quote: "EUR", assets: { BTC: true, ETH: true, GOLD: true }, // BTC/EUR, ETH/EUR, PAXG/EUR finns (api/v2/trading-pairs-info)
    takerPct: 0.4, slippagePct: 0.2,
    fxPct: 1, // ingen egen växlingsavgift publicerad: rules.withdrawalFees.fxPct
    source: "https://www.bitstamp.net/fee-schedule/", checked: "2026-10-23" // "Unified Fee Schedule", giltig från 2026-10-21, under 10 000 USD per 30 dagar
  },
  {
    id: "bybit-eu", name: "Bybit EU",
    licence: { country: "AT", authority: "FMA (Bybit EU GmbH)", register: "ESMA" },
    quote: "EUR", assets: { BTC: true, ETH: true, GOLD: false }, // BTCEUR, ETHEUR finns; ingen PAXG/XAUT på bybit.eu (api.bybit.eu)
    takerPct: 0.25, slippagePct: 0.2,
    fxPct: 1, // ingen egen växlingsavgift publicerad: rules.withdrawalFees.fxPct
    source: "https://www.bybit.eu/en-EU/fee/spot", checked: "2026-10-23" // Regular User, under 10 000 USD per 30 dagar
  },
  {
    id: "kraken", name: "Kraken",
    licence: { country: "IE", authority: "Central Bank of Ireland (Payward Europe Solutions Ltd)", register: "ESMA" },
    quote: "EUR", assets: { BTC: true, ETH: true, GOLD: true }, // XBTEUR, ETHEUR, PAXGEUR finns (api.kraken.com AssetPairs)
    takerPct: 0.8, slippagePct: 0.2,
    fxPct: 1, // ingen egen växlingsavgift publicerad: rules.withdrawalFees.fxPct
    source: "https://www.kraken.com/features/fee-schedule", checked: "2026-10-23" // Nivå 1, spot taker 0,80 % (maker 0,40 %)
  },
  {
    id: "okx-europe", name: "OKX Europe",
    licence: { country: "MT", authority: "MFSA (OKX Europe Ltd)", register: "ESMA" },
    quote: "EUR", assets: { BTC: true, ETH: true, GOLD: false }, // BTC-EUR, ETH-EUR finns; PAXG bara mot USDT på eea.okx.com, inte mot EUR
    takerPct: 0.1, slippagePct: 0.2,
    fxPct: 1, // ingen egen växlingsavgift publicerad: rules.withdrawalFees.fxPct
    source: "https://www.okx.com/en-eu/fees", checked: "2026-10-23" // Regular user, spot taker 0,10 %
  },
  {
    id: "safello", name: "Safello",
    licence: { country: "SE", authority: "Finansinspektionen (Safello AB)", register: "ESMA" },
    quote: "SEK", assets: { BTC: true, ETH: true, GOLD: false }, // inget guld/PAXG i Safellos utbud
    takerPct: 0.6, slippagePct: 0.2,
    fxPct: 1, // ingen egen växlingsavgift publicerad: rules.withdrawalFees.fxPct
    source: "https://help.safello.com/en/articles/166728-what-are-safello-s-fees", checked: "2026-10-23" // orderbok, marknadsorder 0,6 % (limit 0,4 %); enkla köp 3,49 % räknas inte
  }
];
