// GENERERAD av fetcher/walter_fetch.py – publik marknadsdata, ändra inte här.
window.WALTER_MARKET = {
  "now": {
    "date": "2026-10-31",
    "fetchedAt": "2026-10-31T18:43:03",
    "ready": true,
    "red": 4,
    "mode": "NORMAL",
    "lamps": [
      {
        "id": "spx",
        "name": "S&P 500",
        "rule": "Under sitt 50-dagarssnitt",
        "status": "red",
        "value": "7 580 (snitt 7 697)",
        "asOf": "2026-10-30"
      },
      {
        "id": "btcTrend",
        "name": "Bitcoin-trend",
        "rule": "Under sitt 200-dagarssnitt",
        "status": "green",
        "value": "$77 512 (snitt $73 136)",
        "asOf": "2026-10-31"
      },
      {
        "id": "btcWeek",
        "name": "Bitcoin, vecka",
        "rule": "Fallit mer än 10 % på 7 dagar",
        "status": "green",
        "value": "−4,1 %",
        "asOf": "2026-10-31"
      },
      {
        "id": "vix",
        "name": "VIX (oro-index)",
        "rule": "Över 20",
        "status": "green",
        "value": "19,42",
        "asOf": "2026-10-30"
      },
      {
        "id": "us10y",
        "name": "10-årig ränta",
        "rule": "Stigit mer än 0,25 %-enheter på en månad",
        "status": "green",
        "value": "4,93 % (−0,36 på en månad)",
        "asOf": "2026-10-30"
      },
      {
        "id": "dxy",
        "name": "Dollarindex",
        "rule": "Över sitt 50-dagarssnitt",
        "status": "red",
        "value": "101,88 (snitt 100,81)",
        "asOf": "2026-10-30"
      },
      {
        "id": "etf",
        "name": "Bitcoin-fonder",
        "rule": "Pengar ut senaste 5 handelsdagarna",
        "status": "green",
        "value": "+$303M på 5 dagar",
        "asOf": "2026-10-29"
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
        "value": "0,75 (30 okt)",
        "asOf": "2026-10-30"
      },
      {
        "id": "sopr",
        "name": "SOPR",
        "rule": "Under 1,0 i snitt över 7 dagar",
        "status": "red",
        "value": "0,999 snitt 7 d (30 okt)",
        "asOf": "2026-10-30"
      }
    ],
    "px": {
      "BTC": 761656.1656,
      "ETH": 22225.126912208,
      "GOLD": 38291.813681
    },
    "usdsek": {
      "value": 9.8263,
      "asOf": "2026-10-30",
      "source": "Riksbanken"
    },
    "eursek": {
      "value": 10.978,
      "asOf": "2026-10-30",
      "source": "Riksbanken"
    },
    "ethBtcAbove30dMa": false,
    "btcLong": true,
    "vix": 19.42,
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
        "BTC": 798869.6072,
        "ETH": 23007.44468736,
        "GOLD": 39756.52188
      },
      "ethBtcAbove30dMa": false,
      "vix": 19.45,
      "spxBelowMa": true
    },
    {
      "date": "2026-10-25",
      "ready": true,
      "red": 3,
      "px": {
        "BTC": 799346.948,
        "ETH": 23165.074553039994,
        "GOLD": 39870.785334
      },
      "ethBtcAbove30dMa": false,
      "vix": 19.45,
      "spxBelowMa": true
    },
    {
      "date": "2026-10-26",
      "ready": true,
      "red": 3,
      "px": {
        "BTC": 795976.1658,
        "ETH": 22932.073336698,
        "GOLD": 40056.464393999995
      },
      "ethBtcAbove30dMa": false,
      "vix": 18.39,
      "spxBelowMa": true
    },
    {
      "date": "2026-10-27",
      "ready": true,
      "red": 3,
      "px": {
        "BTC": 804095.7927999999,
        "ETH": 23608.252476608002,
        "GOLD": 40358.909408
      },
      "ethBtcAbove30dMa": false,
      "vix": 17.52,
      "spxBelowMa": false
    },
    {
      "date": "2026-10-28",
      "ready": true,
      "red": 2,
      "px": {
        "BTC": 805775.1812,
        "ETH": 23496.404283791995,
        "GOLD": 40349.932788
      },
      "ethBtcAbove30dMa": false,
      "vix": 16.91,
      "spxBelowMa": false
    },
    {
      "date": "2026-10-29",
      "ready": true,
      "red": 3,
      "px": {
        "BTC": 786089.7234,
        "ETH": 22136.286610944,
        "GOLD": 39702.264845
      },
      "ethBtcAbove30dMa": false,
      "vix": 17.2,
      "spxBelowMa": false
    },
    {
      "date": "2026-10-30",
      "ready": true,
      "red": 3,
      "px": {
        "BTC": 754433.8351,
        "ETH": 21712.605774178002,
        "GOLD": 38226.960101
      },
      "ethBtcAbove30dMa": false,
      "vix": 19.42,
      "spxBelowMa": true
    },
    {
      "date": "2026-10-31",
      "ready": true,
      "red": 4,
      "px": {
        "BTC": 761656.1656,
        "ETH": 22225.126912208,
        "GOLD": 38291.813681
      },
      "ethBtcAbove30dMa": false,
      "vix": 19.42,
      "spxBelowMa": true
    }
  ]
};
