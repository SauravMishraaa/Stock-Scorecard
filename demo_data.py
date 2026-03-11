import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

NIFTY50_SYMBOLS = [
    "RELIANCE", "TCS", "INFY", "HDFC", "ICICIBANK",
    "SBIN", "AXISBANK", "BHARTIARTL", "ITC", "WIPRO",
    "HCLTECH", "MARUTI", "BAJFINANCE", "TITAN", "NESTLEIND",
    "SUNPHARMA", "ASIANPAINT", "KOTAKBANK", "LT", "ULTRACEMCO",
    "POWERGRID", "NTPC", "ONGC", "COALINDIA", "JSWSTEEL",
    "TATAMOTORS", "TATASTEEL", "HINDALCO", "CIPLA", "DRREDDY",
]

# Approximate real-world price range for each symbol (just for realism)
_BASE_PRICES = {
    "RELIANCE": 2900, "TCS": 3800, "INFY": 1600, "HDFC": 1700,
    "ICICIBANK": 950,  "SBIN": 620,  "AXISBANK": 1100, "BHARTIARTL": 1200,
    "ITC": 470,        "WIPRO": 480,  "HCLTECH": 1350, "MARUTI": 10500,
    "BAJFINANCE": 6800,"TITAN": 3400, "NESTLEIND": 24000,"SUNPHARMA": 1600,
    "ASIANPAINT": 2900,"KOTAKBANK": 1800,"LT": 3400,"ULTRACEMCO": 10200,
    "POWERGRID": 320,  "NTPC": 380,   "ONGC": 270,     "COALINDIA": 490,
    "JSWSTEEL": 850,   "TATAMOTORS": 920,"TATASTEEL": 165,"HINDALCO": 640,
    "CIPLA": 1450,     "DRREDDY": 6200,
}

FNO_INSTRUMENTS = [
    ("NIFTY",     18000, "CE", "NFO-OPT"),
    ("NIFTY",     17500, "PE", "NFO-OPT"),
    ("BANKNIFTY", 44000, "CE", "NFO-OPT"),
    ("BANKNIFTY", 43000, "PE", "NFO-OPT"),
    ("RELIANCE",  2900,  "CE", "NFO-OPT"),
    ("TCS",       3800,  "CE", "NFO-OPT"),
    ("NIFTY",     None,  None, "NFO-FUT"),  # futures
    ("BANKNIFTY", None,  None, "NFO-FUT"),
]

MF_SCHEMES = [
    "MIRAE ASSET LARGE CAP FUND - DIRECT GROWTH",
    "PARAG PARIKH FLEXI CAP FUND - DIRECT GROWTH",
    "AXIS MIDCAP FUND - DIRECT GROWTH",
    "HDFC INDEX FUND NIFTY 50 PLAN - DIRECT GROWTH",
    "QUANT SMALL CAP FUND - DIRECT GROWTH",
    "KOTAK EQUITY OPPORTUNITIES FUND - DIRECT GROWTH",
]

def make_equity(
        seed      : int = 42,
        start     : str = "2023-02-11",
        end       : str = "2025-12-31",
        n_symbols : int = 14,
) -> pd.DataFrame:
    # Generate a realistic equity tradebook in Zerodha's CSV format.
    rng       = np.random.default_rng(seed)
    symbols   = NIFTY50_SYMBOLS[:n_symbols]
    start_dt  = datetime.strptime(start, "%Y-%m-%d")
    end_dt    = datetime.strptime(end,   "%Y-%m-%d")
    total_days = (end_dt - start_dt).days

    rows = []
    order_id_counter = 1_000_000_000

    for sym in symbols:
        base = _BASE_PRICES.get(sym, rng.uniform(200, 5000))
        n_rounds = rng.integers(1, 4)  # 1, 2, or 3 buy rounds

        for _ in range(n_rounds):
            buy_offset = int(rng.uniform(0, total_days * 0.8))
            buy_date   = start_dt + timedelta(days=buy_offset)
            buy_qty    = int(rng.integers(5, 50)) * 5          # multiples of 5
            buy_price  = round(float(base * rng.uniform(0.82, 1.18)), 2)

            rows.append({
                "symbol"               : sym,
                "isin"                 : f"INE{sym[:3]:3s}{'0' * (9 - len(sym[:3]))}01",
                "trade_date"           : buy_date.strftime("%d-%m-%Y"),
                "exchange"             : "NSE",
                "segment"              : "EQ",
                "series"               : "EQ",
                "trade_type"           : "buy",
                "auction"              : "N",
                "quantity"             : buy_qty,
                "price"                : buy_price,
                "order_id"             : order_id_counter,
                "order_execution_time" : buy_date.strftime("%d-%m-%Y %H:%M:%S"),
            })

            order_id_counter += 1

            # ~60 % chance of selling this lot
            if rng.random() > 0.40:
                hold_days  = int(rng.integers(10, min(400, total_days - buy_offset)))
                sell_date  = buy_date + timedelta(days=hold_days)
                if sell_date > end_dt:
                    sell_date = end_dt
                    # Introduce a mix: 65% chance of profit
                direction  = 1 if rng.random() < 0.65 else -1
                sell_price = round(float(buy_price * (1 + direction * rng.uniform(0.03, 0.55))), 2)

                rows.append({
                    "symbol"               : sym,
                    "isin"                 : f"INE{sym[:3]:3s}{'0' * (9 - len(sym[:3]))}01",
                    "trade_date"           : sell_date.strftime("%d-%m-%Y"),
                    "exchange"             : "NSE",
                    "segment"              : "EQ",
                    "series"               : "EQ",
                    "trade_type"           : "sell",
                    "auction"              : "N",
                    "quantity"             : buy_qty,
                    "price"                : sell_price,
                    "order_id"             : order_id_counter,
                    "order_execution_time" : sell_date.strftime("%d-%m-%Y %H:%M:%S"),
                })
                order_id_counter += 1

    df = pd.DataFrame(rows).sort_values("trade_date").reset_index(drop=True)
    return df

# F&O generator 
def make_fno(
    seed  : int = 7,
    start : str = "2023-02-11",
    end   : str = "2025-12-31",
) -> pd.DataFrame:
    # Generate a realistic F&O tradebook (options + futures) in Zerodha's format.
    rng       = np.random.default_rng(seed)
    start_dt  = datetime.strptime(start, "%Y-%m-%d")
    end_dt    = datetime.strptime(end,   "%Y-%m-%d")
    total_days = (end_dt - start_dt).days

    rows = []
    order_id_counter = 2_000_000_000

    for sym, strike, opt_type, exchange in FNO_INSTRUMENTS:
        # Each instrument traded 1–3 times
        for _ in range(int(rng.integers(1, 4))):
            buy_offset  = int(rng.uniform(0, total_days * 0.85))
            buy_date    = start_dt + timedelta(days=buy_offset)
            expiry_date = buy_date + timedelta(days=int(rng.integers(7, 30)))

            is_future  = (opt_type is None)
            lot_size       = 50 if "NIFTY" in sym and not "BANK" in sym else (15 if "BANK" in sym else 250)
            num_contracts  = int(rng.integers(1, 5))
            buy_qty        = num_contracts

            if is_future:
                buy_price  = round(float(_BASE_PRICES.get(sym, 18000) * rng.uniform(0.98, 1.02)) * lot_size, 2)
                tradingsym = f"{sym}{expiry_date.strftime('%y%b').upper()}FUT"
            else:
                buy_price  = round(float(rng.uniform(30, 500)) * lot_size, 2)
                tradingsym = f"{sym}{expiry_date.strftime('%y%b').upper()}{strike}{opt_type}"

            # Futures: ~55 % profitable; Options: ~40 % profitable
            win_prob   = 0.55 if is_future else 0.40
            direction  = 1 if rng.random() < win_prob else -1
            sell_price = round(float(buy_price * (1 + direction * rng.uniform(0.05, 1.5))), 2)
            sell_price = max(0.05, sell_price)

            hold_days  = int(rng.integers(1, 20))
            sell_date  = buy_date + timedelta(days=hold_days)
            if sell_date > end_dt:
                sell_date = end_dt

            
            common = {
                "symbol"               : tradingsym,
                "exchange"             : exchange,
                "expiry_date"          : expiry_date.strftime("%d-%m-%Y"),
                "strike_price"         : strike if not is_future else "",
                "instrument_type"      : opt_type if not is_future else "FUT",
                "quantity"             : buy_qty,
                "order_id"             : order_id_counter,
            }
            rows.append({**common,
                "trade_date"           : buy_date.strftime("%d-%m-%Y"),
                "trade_type"           : "buy",
                "price"                : buy_price,
                "order_execution_time" : buy_date.strftime("%d-%m-%Y %H:%M:%S"),
            })
            order_id_counter += 1
            rows.append({**common,
                "trade_date"           : sell_date.strftime("%d-%m-%Y"),
                "trade_type"           : "sell",
                "price"                : sell_price,
                "order_execution_time" : sell_date.strftime("%d-%m-%Y %H:%M:%S"),
            })
            order_id_counter += 1

    df = pd.DataFrame(rows).sort_values("trade_date").reset_index(drop=True)
    return df

# Mutual Fund generation
def make_mf(
    seed  : int = 13,
    start : str = "2021-01-01",
    end   : str = "2025-12-31",
) -> pd.DataFrame:
    # Generate a realistic Mutual Fund transaction statement.
    rng       = np.random.default_rng(seed)
    start_dt  = datetime.strptime(start, "%Y-%m-%d")
    end_dt    = datetime.strptime(end,   "%Y-%m-%d")
    total_days = (end_dt - start_dt).days

    rows = []
    folio_counter = 10000000

    for scheme in MF_SCHEMES:
        folio     = str(folio_counter)
        folio_counter += 1
        base_nav  = round(float(rng.uniform(20, 500)), 2)
        nav_drift = 0.0

        # SIPs (12–24 monthly instalments)
        n_sip = int(rng.integers(12, 25))
        sip_amount = round(float(rng.choice([1000, 2000, 3000, 5000, 10000])), 2)

        for i in range(n_sip):
            sip_date = start_dt + timedelta(days=i * 30 + int(rng.integers(0, 5)))
            if sip_date > end_dt:
                break
            nav_drift += rng.uniform(-0.02, 0.04)
            nav        = round(base_nav * (1 + nav_drift), 2)
            units      = round(sip_amount / nav, 4)
            rows.append({
                "scheme_name"      : scheme,
                "folio_number"     : folio,
                "transaction_date" : sip_date.strftime("%d-%m-%Y"),
                "transaction_type" : "Purchase",
                "units"            : units,
                "nav"              : nav,
                "amount"           : sip_amount,
            })
        
        # Occasional lump-sum redemption (~40 % of schemes)
        if rng.random() < 0.40:
            redeem_offset = int(rng.uniform(total_days * 0.5, total_days * 0.9))
            redeem_date   = start_dt + timedelta(days=redeem_offset)
            nav_drift    += rng.uniform(0.1, 0.5)
            nav            = round(base_nav * (1 + nav_drift), 2)
            redeem_units   = round(rng.uniform(50, 200), 4)
            rows.append({
                "scheme_name"      : scheme,
                "folio_number"     : folio,
                "transaction_date" : redeem_date.strftime("%d-%m-%Y"),
                "transaction_type" : "Redemption",
                "units"            : redeem_units,
                "nav"              : nav,
                "amount"           : round(redeem_units * nav, 2),
            })

    df = pd.DataFrame(rows).sort_values("transaction_date").reset_index(drop=True)
    return df

def save_all_csvs(output_dir: str = ".") -> None:
    # Save all three demo DataFrames as CSVs into output_dir.
    os.makedirs(output_dir, exist_ok=True)

    make_equity().to_csv(
        os.path.join(output_dir, "zerodha_equity_tradebook.csv"), index=False
    )
    make_fno().to_csv(
        os.path.join(output_dir, "zerodha_fno_tradebook.csv"), index=False
    )
    make_mf().to_csv(
        os.path.join(output_dir, "zerodha_mf_statement.csv"), index=False
    )
    print(f"✓ Saved 3 demo CSVs to {os.path.abspath(output_dir)}/")

def _lazy(fn):
    """Return a cached property-like function for module-level DataFrames."""
    _cache = {}
    def wrapper():
        if "v" not in _cache:
            _cache["v"] = fn()
        return _cache["v"]
    return wrapper

equity_df = _lazy(make_equity)
fno_df    = _lazy(make_fno)
mf_df     = _lazy(make_mf)

def generate_equity_trades(*args, **kwargs):
    return make_equity(*args, **kwargs)

def generate_fo_trades(*args, **kwargs):
    return make_fno(*args, **kwargs)

def generate_mf_trades(*args, **kwargs):
    return make_mf(*args, **kwargs)

if __name__ == "__main__":
    eq = make_equity()
    fn = make_fno()
    mf = make_mf()

    print(f"Equity   : {len(eq):>5} rows  |  {eq['symbol'].nunique()} symbols")
    print(f"F&O      : {len(fn):>5} rows  |  {fn['symbol'].nunique()} instruments")
    print(f"MF       : {len(mf):>5} rows  |  {mf['scheme_name'].nunique()} schemes")

    print("\n── Equity sample ──")
    print(eq.head(4).to_string(index=False))

    print("\n── F&O sample ──")
    print(fn.head(4).to_string(index=False))

    print("\n── MF sample ──")
    print(mf.head(4).to_string(index=False))