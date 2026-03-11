import pandas as pd
import numpy as np

def detect_segment(df: pd.DataFrame) -> str:
    # Sniff which segment a raw CSV belongs to based on column names
    cols = "".join(c.lower() for c in df.columns)
    if any(k in cols for k in ("strike_price", "option_type","expiry_date", "expiry", "instrument_type")):
        return "FNO"
    if any(k in cols for k in ("scheme_name", "folio_number", "folio", "nav", "scheme")):
        return "MF"
    return "EQ"

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [
        c.strip().lower().replace(" ", "_").replace("-", "_")
        for c in df.columns
    ]
    return df

def _coerce_date(series: pd.Series) -> pd.Series:
    """Try multiple date formats common in Zerodha exports."""
    formats = [
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
    ]
    for fmt in formats:
        try:
            result = pd.to_datetime(series, format=fmt, errors="raise")
            return result
        except Exception:
            pass
    # fallback: let pandas infer
    return pd.to_datetime(series, dayfirst=True, errors="coerce")

def _normalise_trade_type(series: pd.Series) -> pd.Series:
    """Map various broker representations to BUY / SELL."""
    mapping = {
        "b"          : "BUY",
        "buy"        : "BUY",
        "purchase"   : "BUY",
        "p"          : "BUY",
        "subscribe"  : "BUY",
        "sip"        : "BUY",
        "s"          : "SELL",
        "sell"       : "SELL",
        "redemption" : "SELL",
        "red"        : "SELL",
        "redeem"     : "SELL",
        "swp"        : "SELL",
    }
    normalised = series.str.strip().str.lower().map(mapping)
    # For anything not in mapping, preserve the uppercased original
    fallback = series.str.strip().str.upper()
    return normalised.fillna(fallback)

def _map_columns(df: pd.DataFrame, rules: dict) -> pd.DataFrame:
    # Given a mapping of target_column -> list of hints, rename columns in df to match targets based on hints.
    rename_map   = {}
    taken_targets = set()
    for src_col in df.columns:
        for target, hints in rules.items():
            if target in taken_targets:
                continue
            if any(hint in src_col for hint in hints):
                rename_map[src_col] = target
                taken_targets.add(target)
                break
    return df.rename(columns=rename_map)

# Equity Cleaning
_EQ_COL_RULES = {
    "symbol"     : ["symbol", "tradingsymbol", "scrip"],
    "trade_type" : ["trade_type", "transaction_type", "buy_sell", "side", "type"],
    "quantity"   : ["quantity", "qty"],
    "price"      : ["price", "rate", "avg_price", "average_price"],
    "trade_date" : ["trade_date", "order_execution_time", "date"],
    "isin"       : ["isin"],
    "exchange"   : ["exchange"],
    "series"     : ["series"],
    "order_id"   : ["order_id", "order_no"],
}

_EQ_REQUIRED = ["symbol", "trade_type", "quantity", "price", "trade_date"]

def clean_equity(df: pd.DataFrame):
    # Cleans a Zerodha equity tradebook
    df = _normalise_trade_type(df.copy())
    df = _map_columns(df, _EQ_COL_RULES)

    missing = [c for c in _EQ_REQUIRED if c not in df.columns]
    if missing:
        return None, (
            f"Could not find required columns: {missing}. "
            f"Columns detected after normalisation: {list(df.columns)}"
        )
    
    df["trade_date"] = _coerce_date(df["trade_date"])
    df = df.dropna(subset=["trade_date"]).copy()

    df["quantity"]   = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).abs().astype(int)
    df["price"]      = pd.to_numeric(df["price"],    errors="coerce").fillna(0.0)
    df["trade_type"] = _normalise_trade_type(df["trade_type"])
    df["symbol"]     = df["symbol"].astype(str).str.strip().str.upper()
    df["value"]      = df["quantity"] * df["price"]
    df["segment"]    = "EQ"

    df = df[df["quantity"] > 0].reset_index(drop=True)
    df = df.sort_values("trade_date").reset_index(drop=True)
    return df, None

# FNO Cleaning
_FNO_COL_RULES = {
    "symbol"          : ["symbol", "tradingsymbol", "scrip", "instrument"],
    "trade_type"      : ["trade_type", "transaction_type", "buy_sell", "side"],
    "quantity"        : ["quantity", "qty"],
    "price"           : ["price", "rate", "avg_price", "average_price", "trade_price"],
    "trade_date"      : ["trade_date", "order_execution_time", "date"],
    "expiry_date"     : ["expiry_date", "expiry"],
    "strike_price"    : ["strike_price", "strike"],
    "instrument_type" : ["instrument_type", "option_type", "call_put"],
    "exchange"        : ["exchange"],
    "order_id"        : ["order_id", "order_no"],
}

_FNO_REQUIRED = ["symbol", "trade_type", "quantity", "price", "trade_date"]

def clean_fno(df: pd.DataFrame):
    # Cleans a Zerodha FNO tradebook
    df = _normalise_trade_type(df.copy())
    df = _map_columns(df, _FNO_COL_RULES)

    missing = [c for c in _FNO_REQUIRED if c not in df.columns]
    if missing:
        return None, (
            f"Could not find required F&O columns: {missing}."
            f"Columns present: {list(df.columns)}"
        )
    
    df["trade_date"] = _coerce_date(df["trade_date"])
    df = df.dropna(subset=["trade_date"]).copy()

    df["quantity"]   = pd.to_numeric(df["quantity"],    errors="coerce").fillna(0).abs().astype(int)
    df["price"]      = pd.to_numeric(df["price"],       errors="coerce").fillna(0.0)
    df["trade_type"] = _normalise_trade_type(df["trade_type"])
    df["symbol"]     = df["symbol"].astype(str).str.strip().str.upper()
    df["value"]      = df["quantity"] * df["price"]
    df["segment"]    = "FNO"

    if "expiry_date" in df.columns:
        df["expiry_date"] = _coerce_date(df["expiry_date"])
    if "strike_price" in df.columns:
        df["strike_price"] = pd.to_numeric(df["strike_price"], errors="coerce")

    df = df[df["quantity"] > 0].reset_index(drop=True)
    df = df.sort_values("trade_date").reset_index(drop=True)
    return df, None

# Mutual Fund Cleaning
_MF_COL_RULES = {
    "symbol"     : ["scheme_name", "fund_name", "scheme", "fund", "name"],
    "trade_type" : ["transaction_type", "trade_type", "type", "nature"],
    "quantity"   : ["units", "quantity", "qty", "unit"],
    "price"      : ["nav", "price", "rate"],
    "trade_date" : ["trade_date", "transaction_date", "date"],
    "amount"     : ["amount", "value", "net_amount"],
    "folio"      : ["folio_number", "folio_no", "folio"],
}

_MF_REQUIRED = ["symbol", "trade_type", "trade_date"]

def clean_mf(df: pd.DataFrame):
    # Cleans a Zerodha/CAMS/KFinTech mutual fund tradebook
    df = _normalise_trade_type(df.copy())
    df = _map_columns(df, _MF_COL_RULES)

    missing = [c for c in _MF_REQUIRED if c not in df.columns]

    if missing:
        return None, (
            f"Could not find required MF columns: {missing}. "
            f"Columns present: {list(df.columns)}"
        )
    
    df["trade_date"] = _coerce_date(df["trade_date"])
    df = df.dropna(subset=["trade_date"]).copy()

    df["quantity"] = pd.to_numeric(df.get("quantity", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    df["price"]    = pd.to_numeric(df.get("price",    pd.Series(dtype=float)), errors="coerce").fillna(0.0)

    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    else:
        df["amount"] = df["quantity"] * df["price"]

    df["value"]      = df["amount"]
    df["trade_type"] = _normalise_trade_type(df["trade_type"])
    df["symbol"]     = df["symbol"].astype(str).str.strip().str.upper()
    df["segment"]    = "MF"

    df = df.sort_values("trade_date").reset_index(drop=True)
    return df, None

def clean_tradebook(df: pd.DataFrame):
    # Auto clean any tradebook
    segment = detect_segment(df)
    if segment == "EQ":
        return clean_equity(df)
    elif segment == "FNO":
        return clean_fno(df)
    elif segment == "MF":
        return clean_mf(df)
    else:
        cleaned, err = clean_equity(df)
    return cleaned, err, segment

# Validation report
def validation_report(df: pd.DataFrame) -> dict:
    # Generate a report of data-quality 
    report = {
        "total_rows"      : len(df),
        "date_range"      : (df["trade_date"].min(), df["trade_date"].max()),
        "unique_symbols"  : df["symbol"].nunique(),
        "buy_count"       : int((df["trade_type"] == "BUY").sum()),
        "sell_count"      : int((df["trade_type"] == "SELL").sum()),
        "zero_price_rows" : int((df["price"] == 0).sum()),
        "zero_qty_rows"   : int((df["quantity"] == 0).sum()),
        "duplicate_rows"  : int(
            df.duplicated(
                subset=["symbol", "trade_date", "trade_type", "quantity", "price"]
            ).sum()
        ),
        "warnings": [],
    }

    if report["zero_price_rows"] > 0:
        report["warnings"].append(
            f"{report['zero_price_rows']} rows have ₹0 price — check raw CSV."
        )
    if report["duplicate_rows"] > 0:
        report["warnings"].append(
            f"{report['duplicate_rows']} possible duplicate rows detected."
        )
    if report["sell_count"] > report["buy_count"]:
        report["warnings"].append(
            "More SELL rows than BUY rows — did you upload the full tradebook from inception?"
        )

    return report