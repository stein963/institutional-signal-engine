# Institutional Signal Engine

A Python-based trading system that tracks institutional positioning in Gold futures using CFTC Commitments of Traders (COT) data.

## Components

- **gold_ctfc_scraper.py** — Scrapes live COT data from the CFTC Socrata API, filtering for COMEX Gold contracts
- **gold_cot_analysis.py** — Analyses institutional positioning, generates z-score sentiment signals and dark-themed charts
- **gold_cot_sd_FINAL.py** — Backtests the COT-based strategy against historical price data
- **server.py** — Serves live institutional signals and market analysis

## Data
- `gold_cftc_output/` — Raw and processed COT CSV datasets
- `gold_cot_charts/` — Generated signal charts

## Results
Backtest results (2020–2026) show consistent edge tracking institutional money manager positioning in COMEX Gold futures.

## Built With
Python, pandas, matplotlib, requests, Yahoo Finance