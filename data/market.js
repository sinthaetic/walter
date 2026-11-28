// GENERERAD av fetcher/walter_fetch.py – publik marknadsdata, ändra inte här.
window.WALTER_MARKET = {
  "now": {
    "date": "2026-11-28",
    "fetchedAt": "2026-11-28T13:45:50",
    "ready": false,
    "red": 6,
    "mode": null,
    "lamps": [
      {
        "id": "spx",
        "name": "S&P 500",
        "rule": "Under sitt 50-dagarssnitt",
        "status": "red",
        "value": "7 297 (snitt 7 596)",
        "asOf": "2026-11-27"
      },
      {
        "id": "btcTrend",
        "name": "Bitcoin-trend",
        "rule": "Under sitt 200-dagarssnitt",
        "status": "red",
        "value": "$59 176 (snitt $71 713)",
        "asOf": "2026-11-28"
      },
      {
        "id": "btcWeek",
        "name": "Bitcoin, vecka",
        "rule": "Fallit mer än 10 % på 7 dagar",
        "status": "green",
        "value": "−1,6 %",
        "asOf": "2026-11-28"
      },
      {
        "id": "vix",
        "name": "VIX (oro-index)",
        "rule": "Över 20",
        "status": "red",
        "value": "23,81",
        "asOf": "2026-11-27"
      },
      {
        "id": "us10y",
        "name": "10-årig ränta",
        "rule": "Stigit mer än 0,25 %-enheter på en månad",
        "status": "green",
        "value": "4,94 % (−0,11 på en månad)",
        "asOf": "2026-11-27"
      },
      {
        "id": "dxy",
        "name": "Dollarindex",
        "rule": "Över sitt 50-dagarssnitt",
        "status": "red",
        "value": "104,01 (snitt 102,21)",
        "asOf": "2026-11-27"
      },
      {
        "id": "etf",
        "name": "Bitcoin-fonder",
        "rule": "Pengar ut senaste 5 handelsdagarna",
        "status": "red",
        "value": "−$2 313M på 5 dagar",
        "asOf": "2026-11-27"
      },
      {
        "id": "cpi",
        "name": "Inflation (KPI)",
        "rule": "Högre än väntat",
        "status": null,
        "value": "3,7 % mot 3,6 % – gammal (15 okt)",
        "asOf": "2026-10-15"
      },
      {
        "id": "mvrv",
        "name": "MVRV-Z",
        "rule": "Överhettad värdering (över 3)",
        "status": "green",
        "value": "0,22 (27 nov)",
        "asOf": "2026-11-27"
      },
      {
        "id": "sopr",
        "name": "SOPR",
        "rule": "Under 1,0 i snitt över 7 dagar",
        "status": "red",
        "value": "0,980 snitt 7 d (21 nov)",
        "asOf": "2026-11-21"
      }
    ],
    "px": {
      "BTC": 605317.2216,
      "ETH": 16658.329938432,
      "GOLD": 37315.449927
    },
    "usdsek": {
      "value": 10.2291,
      "asOf": "2026-11-27",
      "source": "Riksbanken"
    },
    "eursek": {
      "value": 11.208,
      "asOf": "2026-11-27",
      "source": "Riksbanken"
    },
    "ethBtcAbove30dMa": false,
    "btcLong": false,
    "vix": 23.81,
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
        "BTC": 760653.883,
        "ETH": 22203.486844770003,
        "GOLD": 38282.675222
      },
      "ethBtcAbove30dMa": false,
      "vix": 19.42,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-01",
      "ready": true,
      "red": 5,
      "px": {
        "BTC": 764938.1498,
        "ETH": 22359.142118654,
        "GOLD": 38257.421631
      },
      "ethBtcAbove30dMa": false,
      "vix": 19.42,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-02",
      "ready": true,
      "red": 5,
      "px": {
        "BTC": 749282.2196000001,
        "ETH": 21579.32792448,
        "GOLD": 38500.6867
      },
      "ethBtcAbove30dMa": false,
      "vix": 21.15,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-03",
      "ready": true,
      "red": 5,
      "px": {
        "BTC": 762873.048,
        "ETH": 22825.161596159996,
        "GOLD": 38497.30605
      },
      "ethBtcAbove30dMa": true,
      "vix": 20.83,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-04",
      "ready": true,
      "red": 4,
      "px": {
        "BTC": 780393.5819999999,
        "ETH": 24363.88763004,
        "GOLD": 39487.39524
      },
      "ethBtcAbove30dMa": true,
      "vix": 16.61,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-05",
      "ready": true,
      "red": 5,
      "px": {
        "BTC": 740287.7838,
        "ETH": 20505.97161126,
        "GOLD": 39922.575246
      },
      "ethBtcAbove30dMa": false,
      "vix": 28.18,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-06",
      "ready": true,
      "red": 6,
      "px": {
        "BTC": 747397.591,
        "ETH": 21898.7494163,
        "GOLD": 39999.52769
      },
      "ethBtcAbove30dMa": false,
      "vix": 25.64,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-07",
      "ready": true,
      "red": 6,
      "px": {
        "BTC": 746113.7760000001,
        "ETH": 21883.51705008,
        "GOLD": 40112.997185
      },
      "ethBtcAbove30dMa": false,
      "vix": 25.64,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-08",
      "ready": true,
      "red": 6,
      "px": {
        "BTC": 747032.1975,
        "ETH": 21932.8653186,
        "GOLD": 40000.712750000006
      },
      "ethBtcAbove30dMa": false,
      "vix": 25.64,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-09",
      "ready": true,
      "red": 5,
      "px": {
        "BTC": 734648.544,
        "ETH": 20893.40459136,
        "GOLD": 40456.410879999996
      },
      "ethBtcAbove30dMa": false,
      "vix": 19.92,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-10",
      "ready": true,
      "red": 5,
      "px": {
        "BTC": 723987.6548,
        "ETH": 19801.06235878,
        "GOLD": 39383.564108
      },
      "ethBtcAbove30dMa": false,
      "vix": 19.46,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-11",
      "ready": true,
      "red": 5,
      "px": {
        "BTC": 738739.7093999999,
        "ETH": 20751.198437045998,
        "GOLD": 39543.460818
      },
      "ethBtcAbove30dMa": false,
      "vix": 17.49,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-12",
      "ready": true,
      "red": 6,
      "px": {
        "BTC": 713997.1211999999,
        "ETH": 19470.701495123998,
        "GOLD": 38651.806908
      },
      "ethBtcAbove30dMa": false,
      "vix": 18.7,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-13",
      "ready": true,
      "red": 7,
      "px": {
        "BTC": 684127.1642,
        "ETH": 18423.544531906,
        "GOLD": 38888.444884000004
      },
      "ethBtcAbove30dMa": false,
      "vix": 19.3,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-14",
      "ready": true,
      "red": 7,
      "px": {
        "BTC": 648197.6992,
        "ETH": 16904.995995136,
        "GOLD": 37936.891948
      },
      "ethBtcAbove30dMa": false,
      "vix": 19.3,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-15",
      "ready": true,
      "red": 7,
      "px": {
        "BTC": 652730.3394,
        "ETH": 18485.323211808,
        "GOLD": 38624.627134
      },
      "ethBtcAbove30dMa": false,
      "vix": 19.3,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-16",
      "ready": true,
      "red": 8,
      "px": {
        "BTC": 657557.786,
        "ETH": 18411.618007999998,
        "GOLD": 38733.111175
      },
      "ethBtcAbove30dMa": false,
      "vix": 22.91,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-17",
      "ready": true,
      "red": 8,
      "px": {
        "BTC": 649796.3472,
        "ETH": 18077.334379104,
        "GOLD": 38826.221434
      },
      "ethBtcAbove30dMa": false,
      "vix": 25.46,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-18",
      "ready": true,
      "red": 8,
      "px": {
        "BTC": 633197.07,
        "ETH": 17210.2963626,
        "GOLD": 37761.20128
      },
      "ethBtcAbove30dMa": false,
      "vix": 24.56,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-19",
      "ready": true,
      "red": 8,
      "px": {
        "BTC": 624056.858,
        "ETH": 17192.7664379,
        "GOLD": 36642.77953
      },
      "ethBtcAbove30dMa": false,
      "vix": 28.44,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-20",
      "ready": false,
      "red": 7,
      "px": {
        "BTC": 601916.8925000001,
        "ETH": 15740.126738875,
        "GOLD": 35902.495475
      },
      "ethBtcAbove30dMa": false,
      "vix": 35.89,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-21",
      "ready": false,
      "red": 6,
      "px": {
        "BTC": 615343.3825000001,
        "ETH": 17629.587908625,
        "GOLD": 36219.589175
      },
      "ethBtcAbove30dMa": false,
      "vix": 35.89,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-22",
      "ready": false,
      "red": 6,
      "px": {
        "BTC": 618771.4225,
        "ETH": 17641.173255475,
        "GOLD": 36156.63975
      },
      "ethBtcAbove30dMa": false,
      "vix": 35.89,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-23",
      "ready": false,
      "red": 6,
      "px": {
        "BTC": 631742.2584,
        "ETH": 18017.289209568,
        "GOLD": 37431.571187999994
      },
      "ethBtcAbove30dMa": false,
      "vix": 27.35,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-24",
      "ready": false,
      "red": 6,
      "px": {
        "BTC": 614240.8236,
        "ETH": 16885.480240764,
        "GOLD": 36319.245579
      },
      "ethBtcAbove30dMa": false,
      "vix": 26.3,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-25",
      "ready": false,
      "red": 6,
      "px": {
        "BTC": 611367.365,
        "ETH": 17130.5135673,
        "GOLD": 36055.525499999996
      },
      "ethBtcAbove30dMa": false,
      "vix": 30.35,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-26",
      "ready": false,
      "red": 6,
      "px": {
        "BTC": 617388.5405,
        "ETH": 17317.748561024997,
        "GOLD": 36366.058075
      },
      "ethBtcAbove30dMa": false,
      "vix": 26.8,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-27",
      "ready": false,
      "red": 6,
      "px": {
        "BTC": 610227.1896,
        "ETH": 16701.918179352,
        "GOLD": 37306.55061
      },
      "ethBtcAbove30dMa": false,
      "vix": 23.81,
      "spxBelowMa": true
    },
    {
      "date": "2026-11-28",
      "ready": false,
      "red": 6,
      "px": {
        "BTC": 605317.2216,
        "ETH": 16658.329938432,
        "GOLD": 37315.449927
      },
      "ethBtcAbove30dMa": false,
      "vix": 23.81,
      "spxBelowMa": true
    }
  ]
};
