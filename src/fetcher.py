"""
fetcher.py - Downloads financial data from Yahoo Finance via yfinance.

Handles API errors gracefully: if one ticker fails, others continue.
Includes retry logic for rate limiting.

Falls back to bundled sample data when Yahoo Finance is rate-limited
or returns empty data.
"""

import time
import json
from pathlib import Path
from typing import Any

import yfinance as yf
import pandas as pd
from yfinance.exceptions import YFRateLimitError

from .sampledata import SAMPLE_DATA


# Path for caching fetched data so subsequent runs are faster
CACHE_DIR = Path("data") / "cache"


def _save_cache(ticker: str, data: dict[str, pd.DataFrame | None]) -> None:
    """Save fetched DataFrames as JSON so they can be reused offline."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = {}
    for key, df in data.items():
        if df is not None and not df.empty:
            cache[key] = {
                "columns": [str(c) for c in df.columns],
                "index": [str(i) for i in df.index],
                "data": df.values.tolist(),
            }
    if cache:
        (CACHE_DIR / f"{ticker}.json").write_text(
            json.dumps(cache, indent=2, default=str)
        )


def _load_cache(ticker: str) -> dict[str, pd.DataFrame | None]:
    """Load previously cached data for a ticker."""
    path = CACHE_DIR / f"{ticker}.json"
    if not path.exists():
        return {}
    try:
        cache = json.loads(path.read_text())
        result = {}
        for key, obj in cache.items():
            df = pd.DataFrame(
                obj["data"],
                index=pd.Index(obj["index"]),
                columns=pd.Index(obj["columns"]),
            )
            result[key] = df
        return result
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}


def _fetch_with_retry(
    fetch_fn: Any, ticker: str, label: str, max_retries: int = 3
) -> pd.DataFrame | None:
    """Call *fetch_fn* (a method of Ticker) with retry & backoff.

    Handles YFRateLimitError by sleeping an increasing amount.
    """
    for attempt in range(1, max_retries + 1):
        try:
            result = fetch_fn()
            if isinstance(result, pd.DataFrame) and not result.empty:
                return result
            if attempt == max_retries:
                print(f"  [WARN] No {label} data for {ticker}")
                return None
            time.sleep(2 ** attempt)
        except YFRateLimitError:
            wait = 2 ** attempt * 5
            print(f"  [RATE-LIMIT] {ticker} {label}, retrying in {wait}s "
                  f"(attempt {attempt}/{max_retries})")
            time.sleep(wait)
        except Exception as e:
            print(f"  [ERROR] Failed to fetch {label} for {ticker}: {e}")
            return None
    return None


def fetch_income_statement(ticker: str) -> pd.DataFrame | None:
    """Fetch annual income statement for a ticker.

    Returns a DataFrame with columns as fiscal years and rows as line items,
    or None if the data cannot be retrieved.
    """
    stock = yf.Ticker(ticker)
    return _fetch_with_retry(
        lambda: stock.financials, ticker, "income statement"
    )


def fetch_balance_sheet(ticker: str) -> pd.DataFrame | None:
    """Fetch annual balance sheet for a ticker."""
    stock = yf.Ticker(ticker)
    return _fetch_with_retry(
        lambda: stock.balance_sheet, ticker, "balance sheet"
    )


def fetch_cash_flow(ticker: str) -> pd.DataFrame | None:
    """Fetch annual cash-flow statement for a ticker."""
    stock = yf.Ticker(ticker)
    return _fetch_with_retry(
        lambda: stock.cashflow, ticker, "cash flow"
    )


TICKERS = {
    "AMD": "Advanced Micro Devices",
    "NVDA": "NVIDIA Corporation",
    "AAPL": "Apple Inc.",
}


def fetch_all(ticker: str) -> dict[str, pd.DataFrame | None]:
    """Fetch all three statements for a single ticker.

    Tries (1) live Yahoo Finance, (2) local cache, (3) bundled sample data.
    On success, writes a cache file for offline reuse.

    Returns a dict with keys 'income', 'balance', 'cashflow'.
    """
    print(f"  Fetching {ticker} ...")

    # 1 — Try live Yahoo Finance
    raw = {
        "income": fetch_income_statement(ticker),
        "balance": fetch_balance_sheet(ticker),
        "cashflow": fetch_cash_flow(ticker),
    }
    has_live = any(
        df is not None and not df.empty for df in raw.values()
    )
    if has_live:
        _save_cache(ticker, raw)
        return raw

    # 2 — Try local cache
    cached = _load_cache(ticker)
    if cached:
        print(f"  [CACHE] Using cached data for {ticker}")
        return cached  # type: ignore[return-value]

    # 3 — Fall back to bundled sample data
    if ticker in SAMPLE_DATA:
        print(f"  [SAMPLE] Using bundled sample data for {ticker}")
        sample = SAMPLE_DATA[ticker]
        result: dict[str, pd.DataFrame | None] = {}
        for key, cols_rows in sample.items():
            cols, rows, vals = cols_rows["columns"], cols_rows["rows"], cols_rows["values"]
            df = pd.DataFrame(vals, index=rows, columns=cols)
            result[key] = df
        return result

    print(f"  [SKIP] No data available for {ticker}")
    return raw
