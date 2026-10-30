# Stock Scorecard

Portfolio analysis and performance tracking for Indian stock market traders.

## Overview

Stock Scorecard processes your trading data across Equity, F&O, and Mutual Funds to compute detailed performance metrics, risk analysis, tax estimates, and visual comparisons against market benchmarks. It uses FIFO matching for P&L calculations and applies Indian tax rules (STCG/LTCG for equity, business income for F&O).

## Features

**Performance Analysis**
- Cumulative P&L tracking over time
- Monthly and symbol-wise P&L breakdown
- Win rate, profit factor, and return statistics
- Worst trade identification

**Risk Metrics**
- Return volatility and Sharpe ratio
- Maximum consecutive losses and wins
- Drawdown analysis
- Trade holding period distribution

**Portfolio Conviction**
- Capital deployment and concentration metrics
- Median investment per trade tracking
- Sector and instrument breakdown

**Tax Estimation**
- STCG computation (15% on gains within 365 days)
- LTCG computation (10% on gains above 365 days, 1 lakh exemption)
- F&O treated as business income (30% slab estimate)
- Trade-level STCG/LTCG breakdown

**Multi-Broker Support**
- Zerodha (single combined upload)
- Groww (separate equity/F&O/MF uploads)
- Angel One (separate equity/F&O/MF uploads)

**Additional Features**
- Live price enrichment for open positions via yfinance
- Nifty 50 benchmark overlay on cumulative P&L
- PDF report generation for archival and sharing
- CSV export of cleaned tradebook

## PDF Report

The PDF report provides a complete snapshot of your portfolio performance in printable format. Available in the Raw Data tab under "Download PDF Report".

Contents:

- Header with portfolio name and generation timestamp
- Summary metrics: Total P&L, capital deployed, closed trades, overall ROI
- Equity section: Performance metrics, risk indicators, conviction metrics, top 5 worst trades
- F&O section: Profit/loss, win rate, average holding period, worst trades
- Mutual Funds section: Total invested, redeemed, P&L, fund count
- Tax estimates: STCG/LTCG breakdown (equity), business income estimate (F&O)
- Trade-level summary: Consolidated worst trades across all segments with dates, values, and percentages

PDF requires reportlab. Install with:

```bash
pip install reportlab
```

Without reportlab, the download button will show an informational message.

## How It Works
Data Pipeline: Raw CSV is cleaned, columns are mapped to standard names, and data is split by segment (EQ/FNO/MF)

FIFO Matching: Sells are matched against earliest buys to compute per-trade P&L, holding days, and status (closed/open)

Tax Calculation: Holding days determine STCG vs LTCG classification. Net gains per category are computed with loss offset. LTCG exemption applied as per rules.

Enrichment: Open positions are enriched with live prices from yfinance. Benchmark data fetched for portfolio comparison.

Visualization: Charts and metrics are rendered per trading segment with comparison against Nifty 50.

## Caching
Open position enrichment and benchmark data are cached per session (5 minute and 1 hour TTL respectively) to minimize API calls.

## Limitations
Tax computation is an estimate. Consult a CA for precise liability.
F&O tax assumes 30% slab as a proxy for business income. Actual treatment depends on audit and set-off rules.
Holding days calculated as calendar days, not trading days.
No corporate action adjustments (splits, bonus) in FIFO matching.


## Installation

Requires Python 3.10+. Install uv if you haven't:

```bash
pip install uv
```

Clone the repository and install dependencies:
```bash
git clone https://github.com/yourusername/stock-project.git
cd Stock-Scorecard
uv sync
```

Activate the venv:
```bash
# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

Run the app:
```bash
streamlit run app.py
```

## License
See LICENSE file