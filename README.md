# Sprint 4 Market Snapshot Automation

This repository contains a simple Sprint 4 automation increment for the market intelligence project.

The automation fetches recent market data for index and sector ETF proxies, calculates basic trend indicators, and saves the result as structured CSV and JSON files.

## Assets tracked

| Required market item | Proxy ticker |
|---|---|
| S&P 500 | SPY |
| Nasdaq 100 | QQQ |
| Russell 2000 | IWM |
| Technology sector | XLK |
| Financials sector | XLF |
| Energy sector | XLE |

## Indicators calculated

The script calculates:

- Latest close
- 5-day return percentage
- 20-day return percentage
- 20-day simple moving average
- Whether the latest close is above the 20-day average
- Simple signal: Bullish, Bearish, or Mixed / Neutral

## How to run

Install dependencies:

```bash
pip install -r requirements.txt