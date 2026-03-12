import pandas as pd
import numpy as np

def detect_segment(df: pd.DataFrame) -> str:
    # Sniff which segment a raw CSV belongs to based on column names
    cols = " ".join(c.lower() for c in df.columns)
    if any(k in cols for k in ("strike_price", "option_type","expiry_date", "expiry", "instrument_type")):
        return "FNO"
    if any(k in cols for k in ("scheme_name", "folio_number", "folio", "nav", "scheme")):
        return "MF"
    return "EQ"

def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [
        c.strip().lower().replace(" ", "_").replace("-", "_")
        for c in df.columns
    ]
    return df

def _coerce_date(series) -> pd.Series:
    """
    Try multiple date formats common in Zerodha exports.
    """
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.Series(series)
    # Coerce to plain strings before any parsing attempt
    series = series.astype(str).str.strip()
    for fmt in (
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ):
        try:
            return pd.to_datetime(series, format=fmt, errors="raise")
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
    cleaned    = series.astype(str).str.strip().str.lower()
    normalised = cleaned.map(mapping)
    # For anything not in mapping, preserve the uppercased original
    fallback   = series.astype(str).str.strip().str.upper()
    return normalised.fillna(fallback)

def _map_columns(df: pd.DataFrame, rules: dict) -> pd.DataFrame:
    """
    Rename columns per rules dict.
    """
    rename_map    = {}
    taken_targets = set()
    for src_col in df.columns:
        for target, hints in rules.items():
            if target in taken_targets:
                continue
            if any(hint == src_col for hint in hints):
                rename_map[src_col] = target
                taken_targets.add(target)
                break
    df = df.rename(columns=rename_map)
    # Drop duplicate columns — keep first occurrence
    df = df.loc[:, ~df.columns.duplicated(keep="first")]
    return df

# Equity Cleaning
_EQ_COL_RULES = {
    "symbol"     : ["symbol", "tradingsymbol", "scrip", "stock_symbol", "scrip_name", "trading_symbol"],
    "trade_type" : ["trade_type", "transaction_type", "buy_sell", "side", "type"],
    "quantity"   : ["quantity", "qty"],
    "price"      : ["price", "rate", "avg_price", "average_price"],
    "trade_date" : ["trade_date", "order_execution_time", "date"],
    "isin"       : ["isin"],
    "exchange"   : ["exchange"],
    "series"     : ["series"],
    "order_id"   : ["order_id", "order_no", "trade_id"],
}

_EQ_REQUIRED = ["symbol", "trade_type", "quantity", "price", "trade_date"]

def clean_equity(df: pd.DataFrame):
    # Cleans a Zerodha equity tradebook
    df = _normalise_columns(df.copy())
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
    "symbol"          : ["symbol", "tradingsymbol", "scrip", "instrument", "stock_symbol", "scrip_name"],
    "trade_type"      : ["trade_type", "transaction_type", "buy_sell", "side"],
    "quantity"        : ["quantity", "qty"],
    "price"           : ["price", "rate", "avg_price", "average_price", "trade_price"],
    "trade_date"      : ["trade_date", "order_execution_time", "date"],
    "expiry_date"     : ["expiry_date", "expiry"],
    "strike_price"    : ["strike_price", "strike"],
    "instrument_type" : ["instrument_type", "option_type", "call_put"],
    "exchange"        : ["exchange"],
    "order_id"        : ["order_id", "order_no", "trade_id"],
}

_FNO_REQUIRED = ["symbol", "trade_type", "quantity", "price", "trade_date"]

def clean_fno(df: pd.DataFrame):
    # Cleans a Zerodha FNO tradebook
    df = _normalise_columns(df.copy())
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
    df = _normalise_columns(df.copy())
    df = _map_columns(df, _MF_COL_RULES)

    missing = [c for c in _MF_REQUIRED if c not in df.columns]
    if missing:
        return None, (
            f"Could not find required MF columns: {missing}. "
            f"Columns present: {list(df.columns)}"
        )

    df["trade_date"] = _coerce_date(df["trade_date"])
    df = df.dropna(subset=["trade_date"]).copy()

    if "quantity" in df.columns:
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0.0)
    else:
        df["quantity"] = 0.0

    if "price" in df.columns:
        df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0.0)
    else:
        df["price"] = 0.0

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

def auto_clean(df: pd.DataFrame):
    # Auto clean any tradebook
    segment = detect_segment(df)
    if segment == "EQ":
        cleaned, err = clean_equity(df)
    elif segment == "FNO":
        cleaned, err = clean_fno(df)
    else:
        cleaned, err = clean_mf(df)
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
            f"{report['zero_price_rows']} rows have price=0 — check raw CSV."
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

def clean_tradebook(df: pd.DataFrame):
    # Cleans a raw tradebook DataFrame
    return auto_clean(df)

def split_segments(df: pd.DataFrame) -> dict:
    result = {"EQ": None, "FNO": None, "MF": None}

    if "segment" in df.columns:
        for seg in ("EQ", "FNO", "MF"):
            part = df[df["segment"] == seg]
            if len(part) > 0:
                if seg == "EQ":
                    cleaned, _ = clean_equity(part.copy())
                elif seg == "FNO":
                    cleaned, _ = clean_fno(part.copy())
                else:
                    cleaned, _ = clean_mf(part.copy())
                if cleaned is not None:
                    result[seg] = cleaned
        return result

    # No segment column — detect and clean
    cleaned, err, seg = auto_clean(df)
    if err is None and cleaned is not None:
        result[seg] = cleaned
    return result