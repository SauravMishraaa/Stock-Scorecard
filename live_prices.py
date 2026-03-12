import pandas as pd
import numpy as np

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False

def _to_yf_ticker(symbol: str) -> str:
    """Convert NSE symbol to Yahoo Finance ticker (append .NS)"""
    return f"{symbol.strip().upper()}.NS"

def fetch_live_price(symbols: list[str]) -> dict[str, float]:
    """Fetch latest closing prices for a list of NSE symbols."""
    if not _YF_AVAILABLE or not symbols:
        return {}
    
    tickers = [_to_yf_ticker(s) for s in symbols]
    try:
        data = yf.download(tickers, period="2d", auto_adjust=True,
                           progress=False, threads=True)
        closes = data["Close"] if "Close" in data else data
        result = {}

        # yf returns DataFrame with ticker columns when multiple symbols
        if isinstance(closes, pd.DataFrame):
            last = closes.ffill().iloc[-1]
            for sym, tkr in zip(symbols, tickers):
                val = last.get(tkr)
                result[sym] = float(val) if val is not None and not np.isnan(val) else None
        else:
            # Single symbol case returns Series
            val = float(closes.ffill().iloc[-1])
            result[symbols[0]] = val if not np.isnan(val) else None
        return result
    except Exception:
        return {}
    
def enrich_open_positions(open_pos: pd.DataFrame) -> pd.DataFrame:
    """Add live_price, current_value, unrealized_pnl, unrealized_pct columns"""
    if open_pos is None or open_pos.empty:
        return open_pos
    
    pos = open_pos.copy()
    if not _YF_AVAILABLE:
        pos["live_price"]      = None
        pos["current_value"]   = None
        pos["unrealised_pnl"]  = None
        pos["unrealised_pct"]  = None
        return pos
    
    symbols = pos["symbol"].tolist()
    prices = fetch_live_price(symbols)

    pos["live_price"] = pos["symbol"].map(prices)
    pos["current_value"] = pos.apply(
        lambda r: round(r["quantity"] * r["live_price"], 2)
        if r["live_price"] is not None else None, axis=1,
    )
    pos["unrealised_pnl"] = pos.apply(
        lambda r: round(r["current_value"] - r["invested_value"], 2)
                  if r["current_value"] is not None else None,
        axis=1,
    )
    pos["unrealised_pct"] = pos.apply(
        lambda r: round(r["unrealised_pnl"] / r["invested_value"] * 100, 2)
                  if (r["unrealised_pnl"] is not None and r["invested_value"] > 0) else None,
        axis=1,
    )
    return pos

def fetch_benchmark(start: str, end: str, ticker: str = "^NSE1") -> pd.DataFrame:
    """Fetch Nifty 50 (or any ticker)"""
    if not _YF_AVAILABLE:
        return pd.DataFrame(columns=["date", "benchmark_value"])
    try:
        raw = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
        if raw.empty:
            return pd.DataFrame(columns=["date", "benchmark_value"])
        closes = raw["Close"].ffill().dropna()
        normed = (closes / closes.iloc[0] * 100).reset_index()
        normed.columns = ["date", "benchmark_value"]
        normed["date"] = pd.to_datetime(normed["date"])
        return normed
    except Exception:
        return pd.DataFrame(columns=["date", "benchmark_value"])
