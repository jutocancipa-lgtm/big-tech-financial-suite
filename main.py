"""
main.py - Entry point for the three-statement financial model.

Downloads financial data for AMD, NVDA, and AAPL from Yahoo Finance,
cleans it, computes ratios, and exports everything to Excel files.

Usage:
    python main.py
"""

from pathlib import Path

from src.fetcher import TICKERS, fetch_all
from src.cleaner import (
    clean_income_statement,
    clean_balance_sheet,
    clean_cash_flow_statement,
)
from src.ratios import compute_all
from src.exporter import export
from src.powerbi import export_powerbi


DATA_DIR = Path("data")
SUMMARY_FILE = DATA_DIR / "summary_comparison.xlsx"


def process_ticker(ticker: str) -> bool:
    """Fetch, clean, ratio, and export for one ticker.

    Returns True on success, False if any critical step failed.
    """
    raw = fetch_all(ticker)
    if all(v is None for v in raw.values()):
        print(f"  [SKIP] No data at all for {ticker}, moving on.\n")
        return False

    income = clean_income_statement(raw["income"])
    balance = clean_balance_sheet(raw["balance"])
    cashflow = clean_cash_flow_statement(raw["cashflow"])

    ratios = compute_all(income, balance, cashflow)

    export(ticker, income, balance, cashflow, ratios, DATA_DIR)
    return True


def build_summary() -> None:
    """Build a combined summary sheet with key metrics across tickers."""
    print("\nBuilding summary comparison ...")
    import pandas as pd
    import numpy as np

    summary_data = {}

    for ticker in TICKERS:
        xlsx = DATA_DIR / f"{ticker}_financial_model.xlsx"
        if not xlsx.exists():
            continue
        try:
            inc = pd.read_excel(xlsx, sheet_name="Income Statement", index_col=0)
            inc = inc.loc[~inc.index.duplicated(keep='first')]
            bal = pd.read_excel(xlsx, sheet_name="Balance Sheet", index_col=0)
            bal = bal.loc[~bal.index.duplicated(keep='first')]
            cf  = pd.read_excel(xlsx, sheet_name="Cash Flow Statement", index_col=0)
            cf = cf.loc[~cf.index.duplicated(keep='first')]
        except Exception:
            continue

        # Grab latest year (first row)
        if inc is not None and not inc.empty:
            latest_inc = inc.iloc[0]
        else:
            continue

        summary_data[ticker] = {
            "Revenue ($M)": latest_inc.get("Revenue", np.nan),
            "Gross Profit ($M)": latest_inc.get("Gross Profit", np.nan),
            "Operating Income ($M)": latest_inc.get("Operating Income", np.nan),
            "Net Income ($M)": latest_inc.get("Net Income", np.nan),
        }

        if bal is not None and not bal.empty:
            latest_bal = bal.iloc[0]
            summary_data[ticker].update({
                "Total Assets ($M)": latest_bal.get("Total Assets", np.nan),
                "Total Liabilities ($M)": latest_bal.get("Total Liabilities", np.nan),
                "Total Equity ($M)": latest_bal.get("Total Equity", np.nan),
            })

        if cf is not None and not cf.empty:
            latest_cf = cf.iloc[0]
            summary_data[ticker].update({
                "Operating Cash Flow ($M)": latest_cf.get("Operating Cash Flow", np.nan),
                "Free Cash Flow ($M)": latest_cf.get("Free Cash Flow", np.nan),
            })

    if not summary_data:
        print("  No summary data available.")
        return

    df = pd.DataFrame.from_dict(summary_data, orient="index")
    df.index.name = "Ticker"

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_excel(SUMMARY_FILE, sheet_name="Summary")
    print(f"  Saved summary: {SUMMARY_FILE}")


def main() -> None:
    """Orchestrate the full pipeline for all tickers."""
    print("=" * 55)
    print("  Three-Statement Financial Model")
    print("  Tickers: " + ", ".join(TICKERS.keys()))
    print("=" * 55)

    success_count = 0
    for ticker in TICKERS:
        print(f"\n{'─' * 40}")
        print(f"  Processing {ticker} ({TICKERS[ticker]})")
        print(f"{'─' * 40}")
        ok = process_ticker(ticker)
        if ok:
            success_count += 1

    print(f"\n{'=' * 55}")
    print(f"  Done. {success_count}/{len(TICKERS)} tickers exported successfully.")
    print(f"  Files saved in: {DATA_DIR.resolve()}")

    if success_count > 0:
        build_summary()
        export_powerbi()
        print(f"\n  All done! Check the {DATA_DIR}/ folder for Excel files "
              f"and {Path('powerbi/data')}/ for Power BI-ready CSVs.")
    else:
        print("\n  No data was exported. Check your internet / ticker symbols.")


if __name__ == "__main__":
    main()
