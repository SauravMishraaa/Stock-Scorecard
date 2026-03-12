from __future__ import annotations
import pandas as pd
import numpy as np
from datetime import datetime
from tax import compute_equity_tax

def _fifo_closed_trades(df: pd.DataFrame):
    # Match BUY lots against SELLs with FIFO.
    closed = []
    lots   = {} 

    for _, row in df.sort_values("trade_date").iterrows():
        sym   = str(row["symbol"])
        qty   = int(row["quantity"])
        price = float(row["price"])
        date  = pd.to_datetime(row["trade_date"])  # ← ENSURE datetime conversion
        ttype = str(row["trade_type"]).upper()

        if "BUY" in ttype:
            lots.setdefault(sym, []).append({"qty": qty, "price": price, "date": date})

        elif "SELL" in ttype:
            remaining = qty
            cost      = 0.0
            buy_date  = date

            bucket = lots.get(sym, [])
            while remaining > 0 and bucket:
                lot  = bucket[0]
                take = min(lot["qty"], remaining)
                cost      += take * lot["price"]
                buy_date   = lot["date"]
                remaining -= take
                lot["qty"] -= take
                if lot["qty"] == 0:
                    bucket.pop(0)
            if not bucket:
                lots.pop(sym, None)

            matched = qty - remaining
            if matched > 0:
                avg_buy   = cost / matched
                proceeds  = matched * price
                pnl       = proceeds - cost
                ret_pct   = pnl / cost * 100 if cost else 0.0
                buy_date_dt = pd.to_datetime(buy_date)
                hold_days = max((pd.to_datetime(date) - buy_date_dt).days, 0)
                closed.append({
                    "symbol"        : sym,
                    "buy_date"      : buy_date,
                    "sell_date"     : date,
                    "quantity"      : matched,
                    "avg_buy_price" : round(avg_buy,  2),
                    "sell_price"    : round(price,    2),
                    "investment"    : round(cost,     2),
                    "proceeds"      : round(proceeds, 2),
                    "realized_pnl"  : round(pnl,      2),
                    "return_pct"    : round(ret_pct,  2),
                    "holding_days"  : hold_days,
                })

    return closed, lots


def _build_open_positions(lots: dict) -> pd.DataFrame:
    rows = []
    for sym, bucket in lots.items():
        total_qty = sum(l["qty"] for l in bucket)
        if total_qty == 0:
            continue
        avg_price  = sum(l["qty"] * l["price"] for l in bucket) / total_qty
        first_date = min(l["date"] for l in bucket)
        rows.append({
            "symbol"         : sym,
            "quantity"       : total_qty,
            "avg_buy_price"  : round(avg_price, 2),
            "invested_value" : round(total_qty * avg_price, 2),
            "first_buy"      : first_date,
            "holding_days"   : (datetime.now() - first_date).days,
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["symbol", "quantity", "avg_buy_price",
                 "invested_value", "first_buy", "holding_days"]
    )


def _cum_pnl_df(trades_df: pd.DataFrame) -> pd.DataFrame:
    daily = (
        trades_df.groupby("sell_date")["realized_pnl"]
        .sum().sort_index().cumsum().reset_index()
    )
    daily.columns = ["sell_date", "cum_pnl"]
    return daily


def _monthly_pnl_df(trades_df: pd.DataFrame) -> pd.DataFrame:
    df = trades_df.copy()
    df["month"] = df["sell_date"].dt.to_period("M").astype(str)
    return df.groupby("month")["realized_pnl"].sum().reset_index()


def _max_consecutive(series: pd.Series, condition: bool) -> int:
    max_run = run = 0
    for val in series:
        if val == condition:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    return max_run


def _profit_factor(wins_total: float, losses_total: float) -> float:
    if losses_total == 0:
        return 99.0 if wins_total > 0 else 0.0
    return round(abs(wins_total / losses_total), 2)


def _sharpe(returns: pd.Series) -> float:
    if len(returns) < 2 or returns.std() == 0:
        return 0.0
    return round(returns.mean() / returns.std() * np.sqrt(252), 2)


def compute_equity_scorecard(df: pd.DataFrame) -> dict:
    """Full equity scorecard """
    empty = _empty_equity_scorecard()
    if df is None or df.empty:
        return empty

    closed, open_lots = _fifo_closed_trades(df)
    open_pos          = _build_open_positions(open_lots)


    if not closed:
        sc = empty.copy()
        sc["open_positions"]  = open_pos
        sc["total_buy_value"] = float(df[df["trade_type"] == "BUY"]["value"].sum())
        return sc

    trades = pd.DataFrame(closed)
    wins   = trades[trades["realized_pnl"] > 0]
    losses = trades[trades["realized_pnl"] < 0]

    win_count  = len(wins)
    loss_count = len(losses)
    total_tr   = len(trades)
    win_rate   = win_count / total_tr * 100 if total_tr else 0.0
    avg_win    = float(wins["realized_pnl"].mean())   if win_count  else 0.0
    avg_loss   = float(losses["realized_pnl"].mean()) if loss_count else 0.0
    total_pnl  = float(trades["realized_pnl"].sum())
    pf         = _profit_factor(wins["realized_pnl"].sum(), losses["realized_pnl"].sum())
    avg_hold   = float(trades["holding_days"].mean()) if total_tr else 0.0
    return_std = float(trades["return_pct"].std())    if total_tr > 1 else 0.0
    sharpe     = _sharpe(trades["return_pct"])
    median_inv = float(trades["investment"].median())
    total_buy  = float(df[df["trade_type"] == "BUY"]["value"].sum())

    is_win  = trades["realized_pnl"] > 0
    is_loss = trades["realized_pnl"] < 0

    sym_inv   = trades.groupby("symbol")["investment"].sum().sort_values(ascending=False)
    top5_conc = sym_inv.head(5).sum() / sym_inv.sum() * 100 if sym_inv.sum() > 0 else 0.0

    top_sym = (
        trades.groupby("symbol")
        .agg(trade_value=("investment", "sum"))
        .reset_index()
        .sort_values("trade_value", ascending=False)
    )

    worst_trade = trades.loc[trades["realized_pnl"].idxmin()].to_dict() if total_tr else None

    return {
        "total_realized_pnl"  : round(total_pnl, 2),
        "win_rate"            : round(win_rate, 1),
        "profit_factor"       : pf,
        "win_count"           : win_count,
        "loss_count"          : loss_count,
        "avg_holding_days"    : round(avg_hold, 1),
        "total_trades"        : total_tr,
        "avg_win"             : round(avg_win,  2),
        "avg_loss"            : round(avg_loss, 2),
        "unique_symbols"      : int(trades["symbol"].nunique()),
        "return_std"          : round(return_std, 2),
        "sharpe"              : sharpe,
        "max_consec_losses"   : _max_consecutive(is_loss, True),
        "worst_trade"         : worst_trade,
        "median_investment"   : round(median_inv, 2),
        "total_buy_value"     : round(total_buy, 2),
        "max_consec_wins"     : _max_consecutive(is_win, True),
        "concentration_top5"  : round(top5_conc, 1),
        "has_trades"          : True,
        "trades_df"           : trades,
        "cum_pnl"             : _cum_pnl_df(trades),
        "monthly_pnl"         : _monthly_pnl_df(trades),
        "top_symbols"         : top_sym,
        "open_positions"      : open_pos,
        "tax_summary"         : compute_equity_tax(trades),
    }


def _empty_equity_scorecard() -> dict:
    return {
        "total_realized_pnl": 0.0, "win_rate": 0.0, "profit_factor": 0.0,
        "win_count": 0, "loss_count": 0, "avg_holding_days": 0.0,
        "total_trades": 0, "avg_win": 0.0, "avg_loss": 0.0, "unique_symbols": 0,
        "return_std": 0.0, "sharpe": 0.0, "max_consec_losses": 0,
        "worst_trade": None, "median_investment": 0.0, "total_buy_value": 0.0,
        "max_consec_wins": 0, "concentration_top5": 0.0,
        "has_trades": False, "trades_df": pd.DataFrame(),
        "cum_pnl": pd.DataFrame(columns=["sell_date", "cum_pnl"]),
        "monthly_pnl": pd.DataFrame(columns=["month", "realized_pnl"]),
        "top_symbols": pd.DataFrame(columns=["symbol", "trade_value"]),
        "open_positions": pd.DataFrame(),
        "tax_summary": {},
    }


def compute_fo_scorecard(df: pd.DataFrame) -> dict:
    """F&O scorecard """
    empty = _empty_fo_scorecard()
    if df is None or df.empty:
        return empty

    closed, _ = _fifo_closed_trades(df)
    if not closed:
        return empty

    trades = pd.DataFrame(closed)
    wins   = trades[trades["realized_pnl"] > 0]
    losses = trades[trades["realized_pnl"] < 0]

    win_count  = len(wins)
    loss_count = len(losses)
    total_tr   = len(trades)
    win_rate   = win_count / total_tr * 100 if total_tr else 0.0
    avg_win    = float(wins["realized_pnl"].mean())   if win_count  else 0.0
    avg_loss   = float(losses["realized_pnl"].mean()) if loss_count else 0.0
    total_pnl  = float(trades["realized_pnl"].sum())
    pf         = _profit_factor(wins["realized_pnl"].sum(), losses["realized_pnl"].sum())
    avg_hold   = float(trades["holding_days"].mean()) if total_tr else 0.0
    total_buy  = float(df[df["trade_type"] == "BUY"]["value"].sum())

    def _infer_type(sym):
        s = str(sym).upper()
        if s.endswith("CE"):  return "CE"
        if s.endswith("PE"):  return "PE"
        if s.endswith("FUT"): return "FUT"
        return "OTHER"

    trades["inferred_type"] = trades["symbol"].apply(_infer_type)
    inst_breakdown = (
        trades.groupby("inferred_type")
        .agg(trade_value=("investment", "sum"))
        .reset_index()
        .rename(columns={"inferred_type": "instrument_type"})
    )

    return {
        "total_realized_pnl"   : round(total_pnl, 2),
        "win_rate"             : round(win_rate, 1),
        "profit_factor"        : pf,
        "win_count"            : win_count,
        "loss_count"           : loss_count,
        "unique_instruments"   : int(trades["symbol"].nunique()),
        "total_trades"         : total_tr,
        "avg_win"              : round(avg_win,  2),
        "avg_loss"             : round(avg_loss, 2),
        "avg_holding_days"     : round(avg_hold, 1),
        "total_buy_value"      : round(total_buy, 2),
        "has_trades"           : True,
        "trades_df"            : trades,
        "cum_pnl"              : _cum_pnl_df(trades),
        "monthly_pnl"          : _monthly_pnl_df(trades),
        "instrument_breakdown" : inst_breakdown,
    }


def _empty_fo_scorecard() -> dict:
    return {
        "total_realized_pnl": 0.0, "win_rate": 0.0, "profit_factor": 0.0,
        "win_count": 0, "loss_count": 0, "unique_instruments": 0,
        "total_trades": 0, "avg_win": 0.0, "avg_loss": 0.0,
        "avg_holding_days": 0.0, "total_buy_value": 0.0,
        "has_trades": False, "trades_df": pd.DataFrame(),
        "cum_pnl": pd.DataFrame(columns=["sell_date", "cum_pnl"]),
        "monthly_pnl": pd.DataFrame(columns=["month", "realized_pnl"]),
        "instrument_breakdown": pd.DataFrame(),
    }

def compute_mf_scorecard(df: pd.DataFrame) -> dict:
    """MF scorecard """
    empty = _empty_mf_scorecard()
    if df is None or df.empty:
        return empty

    df = df.copy()
    ttype = df["trade_type"].str.upper()

    closed, _ = _fifo_closed_trades(df)

    df["buy_val"]  = df["value"].where(ttype == "BUY",  0.0)
    df["sell_val"] = df["value"].where(ttype == "SELL", 0.0)

    total_invested = float(df["buy_val"].sum())
    total_redeemed = float(df["sell_val"].sum())
    total_pnl      = 0.0
    has_trades     = False
    trades_df      = pd.DataFrame()
    cum_df         = pd.DataFrame(columns=["sell_date", "cum_pnl"])
    monthly_df     = pd.DataFrame(columns=["month", "realized_pnl"])
    total_trades   = 0

    if closed:
        trades_df    = pd.DataFrame(closed)
        total_pnl    = float(trades_df["realized_pnl"].sum())
        has_trades   = True
        cum_df       = _cum_pnl_df(trades_df)
        monthly_df   = _monthly_pnl_df(trades_df)
        total_trades = len(trades_df)

    fund_breakdown = (
        df.groupby("symbol")
        .agg(trade_value=("buy_val", "sum"))
        .reset_index()
        .sort_values("trade_value", ascending=False)
    )

    return {
        "total_invested"     : round(total_invested, 2),
        "total_redeemed"     : round(total_redeemed, 2),
        "total_realized_pnl" : round(total_pnl, 2),
        "unique_funds"       : int(df["symbol"].nunique()),
        "total_trades"       : total_trades,
        "has_trades"         : has_trades,
        "trades_df"          : trades_df,
        "cum_pnl"            : cum_df,
        "monthly_pnl"        : monthly_df,
        "fund_breakdown"     : fund_breakdown,
    }


def _empty_mf_scorecard() -> dict:
    return {
        "total_invested": 0.0, "total_redeemed": 0.0,
        "total_realized_pnl": 0.0, "unique_funds": 0, "total_trades": 0,
        "has_trades": False, "trades_df": pd.DataFrame(),
        "cum_pnl": pd.DataFrame(columns=["sell_date", "cum_pnl"]),
        "monthly_pnl": pd.DataFrame(columns=["month", "realized_pnl"]),
        "fund_breakdown": pd.DataFrame(),
    }