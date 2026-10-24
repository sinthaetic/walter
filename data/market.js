// GENERERAD av fetcher/walter_fetch.py – publik marknadsdata, ändra inte här.
window.WALTER_MARKET = {
  "now": {
    "date": "2026-10-24",
    "fetchedAt": "2026-10-24T21:51:29",
    "ready": true,
    "red": 3,
    "mode": "NORMAL",
    "lamps": [
      {
        "id": "spx",
        "name": "S&P 500",
        "rule": "Under sitt 50-dagarssnitt",
        "status": "red",
        "value": "7 624 (snitt 7 700)",
        "asOf": "2026-10-23"
      },
      {
        "id": "btcTrend",
        "name": "Bitcoin-trend",
        "rule": "Under sitt 200-dagarssnitt",
        "status": "green",
        "value": "$80 444 (snitt $72 898)",
        "asOf": "2026-10-24"
      },
      {
        "id": "btcWeek",
        "name": "Bitcoin, vecka",
        "rule": "Fallit mer än 10 % på 7 dagar",
        "status": "green",
        "value": "−1,2 %",
        "asOf": "2026-10-24"
      },
      {
        "id": "vix",
        "name": "VIX (oro-index)",
        "rule": "Över 20",
        "status": "green",
        "value": "19,45",
        "asOf": "2026-10-23"
      },
      {
        "id": "us10y",
        "name": "10-årig ränta",
        "rule": "Stigit mer än 0,25 %-enheter på en månad",
        "status": "green",
        "value": "4,99 % (−0,13 på en månad)",
        "asOf": "2026-10-23"
      },
      {
        "id": "dxy",
        "name": "Dollarindex",
        "rule": "Över sitt 50-dagarssnitt",
        "status": "red",
        "value": "101,81 (snitt 100,54)",
        "asOf": "2026-10-23"
      },
      {
        "id": "etf",
        "name": "Bitcoin-fonder",
        "rule": "Pengar ut senaste 5 handelsdagarna",
        "status": "green",
        "value": "+$360M på 5 dagar",
        "asOf": "2026-10-22"
      },
      {
        "id": "cpi",
        "name": "Inflation (KPI)",
        "rule": "Högre än väntat",
        "status": "red",
        "value": "3,7 % mot 3,6 %",
        "asOf": "2026-10-15"
      },
      {
        "id": "mvrv",
        "name": "MVRV-Z",
        "rule": "Överhettad värdering (över 3)",
        "status": "green",
        "value": "0,87 (23 okt)",
        "asOf": "2026-10-23"
      },
      {
        "id": "sopr",
        "name": "SOPR",
        "rule": "Under 1,0 i snitt över 7 dagar",
        "status": "green",
        "value": "1,002 snitt 7 d (17 okt)",
        "asOf": "2026-10-17"
      }
    ],
    "px": {
      "BTC": 799983.4023999999,
      "ETH": 23071.521325216,
      "GOLD": 39777.107202
    },
    "usdsek": {
      "value": 9.9446,
      "asOf": "2026-10-23",
      "source": "Riksbanken"
    },
    "eursek": {
      "value": 11.131,
      "asOf": "2026-10-23",
      "source": "Riksbanken"
    },
    "ethBtcAbove30dMa": false,
    "btcLong": true,
    "vix": 19.45,
    "spxBelowMa": true,
    "rules": {
      "strategy": "autopilot",
      "decision": {
        "weekday": "söndag",
        "bandPp": 5
      },
      "parkeraAtRed": 7,
      "wakeAtRed": 5,
      "modes": {
        "buyAtRed": 2,
        "buyLittleAtRed": 4,
        "littleShare": 0.5
      },
      "paper": {
        "minTradePct": 2
      },
      "maxInvested": 0.75,
      "minCash": 0.25,
      "caps": {
        "BTC": 0.35,
        "ETH": 0.2,
        "GOLD": 0.2
      },
      "unlock": {
        "early": {
          "days": 15,
          "gainPct": 20,
          "maxDd": 8,
          "minGreen": 7
        },
        "normal": {
          "days": 30,
          "gainPct": 10,
          "maxDd": 12
        }
      },
      "ethMaxRed": 4,
      "gold": {
        "vixAbove": 20,
        "spxBelowMa": true,
        "allowedWhenParked": true
      },
      "withdrawalFees": {
        "takerPct": 0.4,
        "slippagePct": 0.2,
        "sepaEur": 1,
        "fxPct": 1
      },
      "lampThresholds": {
        "spxMaDays": 50,
        "btcMaDays": 200,
        "btcWeekDropPct": -10,
        "vixAbove": 20,
        "us10yRisePp": 0.25,
        "dxyMaDays": 50,
        "etfDays": 5,
        "mvrvZ": 3,
        "soprAvgDays": 7,
        "sopr": 1
      },
      "lampMaxAgeDays": {
        "default": 4,
        "etf": 6,
        "mvrv": 10,
        "sopr": 10,
        "cpi": 35
      }
    },
    "levels": {
      "1": {
        "asset": "BTC",
        "name": "Bitcoin"
      },
      "2": {
        "asset": "ETH",
        "name": "Ethereum"
      },
      "3": {
        "asset": "GULD",
        "name": "Guld",
        "gainPct": 50,
        "maxDd": 12
      }
    },
    "version": "1.13"
  },
  "log": [
    {
      "date": "2026-10-23",
      "ready": true,
      "red": 3,
      "px": {
        "BTC": 809052.8776,
        "ETH": 23883.240946752,
        "GOLD": 39825.736296
      },
      "ethBtcAbove30dMa": false,
      "vix": 19.45,
      "spxBelowMa": true
    },
    {
      "date": "2026-10-24",
      "ready": true,
      "red": 3,
      "px": {
        "BTC": 799983.4023999999,
        "ETH": 23071.521325216,
        "GOLD": 39777.107202
      },
      "ethBtcAbove30dMa": false,
      "vix": 19.45,
      "spxBelowMa": true
    }
  ]
};
