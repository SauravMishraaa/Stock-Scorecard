from __future__ import annotations
import pandas as pd

STCG_RATE = 0.15
LTCG_RATE = 0.10
LTCG_EXEMPTION = 100_000.0
FNO_SLAB_RATE = 0.30

def _classify(trades: pd.DataFrame) -> pd.DataFrame:
    """Add 'tax_type' column: STCG or LTCG based on holding period."""
    df = trades.copy()
    df["tax_type"] = df["holding_days"].apply(
        lambda d: "LTCG" if d > 365 else "STCG"
    )
    return df

def compute_equity_tax(trades_df: pd.DataFrame) -> dict:
    if trades_df is None or trades_df.empty:
        return _empty_tax()
    
    df = _classify(trades_df)
    wins = df[df["realized_pnl"] > 0]
    losses = df[df["realized_pnl"] < 0]

    stcg_gains  = float(df[df["tax_type"] == "STCG"]["realized_pnl"].clip(lower=0).sum())
    ltcg_gains  = float(df[df["tax_type"] == "LTCG"]["realized_pnl"].clip(lower=0).sum())
    stcg_losses = float(df[df["tax_type"] == "STCG"]["realized_pnl"].clip(upper=0).sum())
    ltcg_losses = float(df[df["tax_type"] == "LTCG"]["realized_pnl"].clip(upper=0).sum())

    # Net within each bucket
    net_stcg = stcg_gains + stcg_losses
    net_ltcg = ltcg_gains + ltcg_losses

    taxable_ltcg = max(net_ltcg - LTCG_EXEMPTION, 0.0)

    stcg_tax = max(net_stcg, 0.0) * STCG_RATE
    ltcg_tax = taxable_ltcg * LTCG_RATE
    total_tax = stcg_tax + ltcg_tax

    stcg_count = int((df["tax_type"] == "STCG").sum())
    ltcg_count = int((df["tax_type"] == "LTCG").sum())

    return {
        "stcg_gains"    : round(stcg_gains,   2),
        "stcg_losses"   : round(stcg_losses,  2),
        "net_stcg"      : round(net_stcg,      2),
        "ltcg_gains"    : round(ltcg_gains,   2),
        "ltcg_losses"   : round(ltcg_losses,  2),
        "net_ltcg"      : round(net_ltcg,      2),
        "taxable_ltcg"  : round(taxable_ltcg,  2),
        "stcg_tax"      : round(stcg_tax,      2),
        "ltcg_tax"      : round(ltcg_tax,      2),
        "total_tax"     : round(total_tax,     2),
        "stcg_count"    : stcg_count,
        "ltcg_count"    : ltcg_count,
        "stcg_rate"     : STCG_RATE,
        "ltcg_rate"     : LTCG_RATE,
        "ltcg_exemption": LTCG_EXEMPTION,
        "breakdown_df"  : df[["symbol", "buy_date", "sell_date",
                               "holding_days", "tax_type",
                               "investment", "realized_pnl"]].copy(),
    }

def compute_fno_tax(trades_df: pd.DataFrame) -> dict:
    """F&O is speculative/business income"""
    if trades_df is None or trades_df.empty:
        return {"net_profit": 0.0 , "estimated_tax": 0.0, "rate": FNO_SLAB_RATE}
    
    net = float(trades_df["realized_pnl"].sum())
    tax = max(net, 0.0) * FNO_SLAB_RATE
    return {
        "net_profit": round(net, 2),
        "estimated_tax": round(tax, 2),
        "rate": FNO_SLAB_RATE,
    }

def _empty_tax() -> dict:
    return {
        "stcg_gains": 0.0, "stcg_losses": 0.0, "net_stcg": 0.0,
        "ltcg_gains": 0.0, "ltcg_losses": 0.0, "net_ltcg": 0.0,
        "taxable_ltcg": 0.0, "stcg_tax": 0.0, "ltcg_tax": 0.0,
        "total_tax": 0.0, "stcg_count": 0, "ltcg_count": 0,
        "stcg_rate": STCG_RATE, "ltcg_rate": LTCG_RATE,
        "ltcg_exemption": LTCG_EXEMPTION,
        "breakdown_df": pd.DataFrame(),
    }