"""
fetcher.py - Downloads financial data from Alpha Vantage API.

Handles API errors gracefully: if one ticker fails, others continue.
Includes retry logic for rate limiting.

Falls back to bundled sample data when Alpha Vantage is rate-limited
or returns empty data.
"""

import os
import time
import json
from pathlib import Path

import requests
import pandas as pd

from dotenv import load_dotenv

from .sampledata import SAMPLE_DATA


load_dotenv()

# Path for caching fetched data so subsequent runs are faster
CACHE_DIR = Path("data") / "cache"

ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"


# ---- Alpha Vantage API field → yfinance-style row label maps ----
# These convert API field names to the row labels cleaner.py expects
# so the rest of the pipeline works unchanged.

INCOME_FIELD_MAP = {
    "totalRevenue": "Total Revenue",
    "costOfRevenue": "Cost Of Revenue",
    "grossProfit": "Gross Profit",
    "researchAndDevelopment": "Research And Development",
    "sellingGeneralAndAdministrative": "Selling General And Administration",
    "operatingIncome": "Operating Income",
    "interestExpense": "Interest Expense",
    "incomeTaxExpense": "Tax Provision",
    "netIncome": "Net Income",
    "ebit": "EBIT",
    "ebitda": "EBITDA",
    "dilutedEPS": "Diluted EPS",
    "basicEPS": "Basic EPS",
}

BALANCE_FIELD_MAP = {
    "totalAssets": "Total Assets",
    "currentAssets": "Current Assets",
    "cashAndCashEquivalentsAtCarryingValue": "Cash And Cash Equivalents",
    "cashAndShortTermInvestments": "Cash And Cash Equivalents",
    "shortTermInvestments": "Short Term Investments",
    "currentNetReceivables": "Net Receivables",
    "inventory": "Inventory",
    "propertyPlantEquipmentNet": "Property Plant Equipment Net",
    "goodwill": "Goodwill",
    "intangibleAssets": "Intangible Assets Excluding Goodwill",
    "accountsPayable": "Accounts Payable",
    "shortTermDebt": "Short Term Debt",
    "currentLiabilities": "Current Liabilities",
    "longTermDebt": "Long Term Debt",
    "totalLiabilities": "Total Liabilities",
    "totalShareholderEquity": "Total Equity Gross Minority Interest",
    "retainedEarnings": "Retained Earnings",
}

CASHFLOW_FIELD_MAP = {
    "netIncome": "Net Income",
    "depreciationAndAmortization": "Depreciation And Amortization",
    "stockBasedCompensation": "Stock Based Compensation",
    "changeInWorkingCapital": "Change In Working Capital",
    "operatingCashflow": "Operating Cash Flow",
    "capitalExpenditures": "Capital Expenditure",
    "investingCashflow": "Investing Cash Flow",
    "financingCashflow": "Financing Cash Flow",
    "dividendPayout": "Cash Dividends Paid",
    "dividendPayoutCommonStock": "Cash Dividends Paid",
    "repurchaseOfCapitalStock": "Repurchase Of Capital Stock",
    "commonStockRepurchased": "Repurchase Of Capital Stock",
    "changeInCash": "Change in Cash",
    "changeInCashAndCashEquivalents": "Change in Cash",
}


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


def _api_to_dataframe(
    reports: list[dict], field_map: dict
) -> pd.DataFrame:
    """Convert Alpha Vantage annualReports list to a DataFrame.

    Returns a DataFrame with:
      - index  = line-item names (e.g. "Total Revenue")
      - columns = fiscal year dates (e.g. "2024-09-28")
    This matches the orientation yfinance returns so that
    cleaner.py's transpose_and_clean works unchanged.
    """
    data: dict[str, dict[str, float]] = {}
    for report in reports:
        fiscal_end = report.get("fiscalDateEnding")
        if not fiscal_end:
            continue
        for api_field, label in field_map.items():
            value = report.get(api_field)
            if value is not None and value not in ("None", ""):
                try:
                    data.setdefault(label, {})[fiscal_end] = float(value)
                except (ValueError, TypeError):
                    pass

    if not data:
        return pd.DataFrame()

    # rows = line items, columns = fiscal year dates
    return pd.DataFrame(data).T


def _fetch_with_retry(
    ticker: str, label: str, max_retries: int = 3
) -> pd.DataFrame | None:
    """Fetch *label* statement for *ticker* from Alpha Vantage.

    Retries up to *max_retries* times with a 5-second delay.
    Returns None when all attempts fail.
    """
    api_key = os.getenv("ALPHA_VANTAGE_KEY")
    if not api_key:
        print("  [ERROR] ALPHA_VANTAGE_KEY environment variable not set")
        return None

    function = {
        "income statement": "INCOME_STATEMENT",
        "balance sheet": "BALANCE_SHEET",
        "cash flow": "CASH_FLOW",
    }[label]

    field_map = {
        "income statement": INCOME_FIELD_MAP,
        "balance sheet": BALANCE_FIELD_MAP,
        "cash flow": CASHFLOW_FIELD_MAP,
    }[label]

    url = (
        f"{ALPHA_VANTAGE_BASE}"
        f"?function={function}"
        f"&symbol={ticker}"
        f"&apikey={api_key}"
    )

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            body = resp.json()

            # Alpha Vantage returns {"Error Message": ...} on bad requests
            if "Error Message" in body:
                print(f"  [ERROR] {ticker} {label}: {body['Error Message']}")
                return None

            # Rate-limit detection
            info = body.get("Information", "")
            if "rate" in info.lower():
                if attempt < max_retries:
                    print(
                        f"  [RATE-LIMIT] {ticker} {label}, "
                        f"retrying in 5s (attempt {attempt}/{max_retries})"
                    )
                    time.sleep(5)
                    continue
                print(f"  [ERROR] {ticker} {label}: rate limited")
                return None

            data_key = "annualReports"
            reports = body.get(data_key)
            if not reports:
                if attempt == max_retries:
                    print(f"  [WARN] No {label} data for {ticker}")
                    return None
                time.sleep(5)
                continue

            df = _api_to_dataframe(reports, field_map)
            df = df.loc[~df.index.duplicated(keep='first')]

            # Compute Free Cash Flow for cash flow statements
            if label == "cash flow":
                ocf = df.loc["Operating Cash Flow"] if "Operating Cash Flow" in df.index else None
                capex = df.loc["Capital Expenditure"] if "Capital Expenditure" in df.index else None
                if ocf is not None and capex is not None:
                    fcf = ocf + capex  # capex is negative
                    df.loc["Free Cash Flow"] = fcf

            return df

        except requests.RequestException as e:
            if attempt == max_retries:
                print(f"  [ERROR] Failed to fetch {label} for {ticker}: {e}")
                return None
            print(
                f"  [RETRY] {ticker} {label} failed ({e}), "
                f"retrying in 5s (attempt {attempt}/{max_retries})"
            )
            time.sleep(5)
        except Exception as e:
            if attempt == max_retries:
                print(f"  [ERROR] Failed to fetch {label} for {ticker}: {e}")
                return None
            print(
                f"  [RETRY] {ticker} {label} failed ({e}), "
                f"retrying in 5s (attempt {attempt}/{max_retries})"
            )
            time.sleep(5)

    return None


def fetch_income_statement(ticker: str) -> pd.DataFrame | None:
    """Fetch annual income statement for a ticker.

    Returns a DataFrame with columns as fiscal years and rows as line items,
    or None if the data cannot be retrieved.
    """
    return _fetch_with_retry(ticker, "income statement")


def fetch_balance_sheet(ticker: str) -> pd.DataFrame | None:
    """Fetch annual balance sheet for a ticker."""
    return _fetch_with_retry(ticker, "balance sheet")


def fetch_cash_flow(ticker: str) -> pd.DataFrame | None:
    """Fetch annual cash-flow statement for a ticker."""
    return _fetch_with_retry(ticker, "cash flow")


TICKERS = {
    "AMD": "Advanced Micro Devices",
    "NVDA": "NVIDIA Corporation",
    "AAPL": "Apple Inc.",
}


def fetch_all(ticker: str) -> dict[str, pd.DataFrame | None]:
    """Fetch all three statements for a single ticker.

    Tries (1) live Alpha Vantage, (2) local cache, (3) bundled sample data.
    On success, writes a cache file for offline reuse.

    Returns a dict with keys 'income', 'balance', 'cashflow'.
    """
    print(f"  Fetching {ticker} ...")

    # 1 — Try live Alpha Vantage
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
            df = df.loc[~df.index.duplicated(keep='first')]
            result[key] = df
        return result

    print(f"  [SKIP] No data available for {ticker}")
    return raw
