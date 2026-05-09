"""
powerbi.py - Exports data in a star-schema format optimised for Power BI.

Produces CSV files in the powerbi/ directory that Power BI Desktop can
consume directly:

  - dim_ticker.csv        Company dimension
  - dim_date.csv          Fiscal-year calendar
  - fact_financials.csv   All income/balance/cashflow items (long format)
  - fact_ratios.csv       All computed ratios (long format)

Usage (called automatically from main.py):
    python -c "from src.powerbi import export_powerbi; export_powerbi()"
"""

from pathlib import Path

import pandas as pd

from .fetcher import TICKERS
DATA_DIR = Path("data")


POWERBI_DIR = Path("powerbi")
POWERBI_DATA_DIR = POWERBI_DIR / "data"


STATEMENT_LABELS = {
    "Income Statement": "Income Statement",
    "Balance Sheet": "Balance Sheet",
    "Cash Flow Statement": "Cash Flow",
}

# Rough sector / industry metadata for the dimension table
COMPANY_META = {
    "AMD":  {"Sector": "Technology", "Industry": "Semiconductors"},
    "NVDA": {"Sector": "Technology", "Industry": "Semiconductors"},
    "AAPL": {"Sector": "Technology", "Industry": "Consumer Electronics"},
}


def _melt_statement(
    ticker: str, sheet_name: str, label: str
) -> pd.DataFrame | None:
    """Read one statement sheet and melt into long (tidy) format."""
    path = DATA_DIR / f"{ticker}_financial_model.xlsx"
    if not path.exists():
        return None
    try:
        df = pd.read_excel(path, sheet_name=sheet_name, index_col=0)
    except Exception:
        return None
    if df.empty:
        return None

    # Index is fiscal-year dates; columns are line items
    melted = df.reset_index().melt(
        id_vars="index", var_name="Line Item", value_name="Value (Millions USD)"
    )
    melted.rename(columns={"index": "Fiscal Year"}, inplace=True)

    # Parse fiscal year — keep just the year integer
    melted["Fiscal Year"] = pd.to_datetime(melted["Fiscal Year"]).dt.year

    melted.insert(0, "Ticker", ticker)
    melted.insert(2, "Statement", label)
    return melted


def _melt_ratios(
    ticker: str, category: str, df: pd.DataFrame
) -> pd.DataFrame:
    """Melt one ratio-category DataFrame into long format."""
    melted = df.reset_index().melt(
        id_vars="index", var_name="Ratio", value_name="Value"
    )
    melted.rename(columns={"index": "Fiscal Year"}, inplace=True)
    melted["Fiscal Year"] = pd.to_datetime(melted["Fiscal Year"]).dt.year
    melted.insert(0, "Ticker", ticker)
    melted.insert(1, "Category", category)
    return melted


def export_powerbi() -> None:
    """Read every ticker's Excel file and write star-schema CSVs."""
    POWERBI_DATA_DIR.mkdir(parents=True, exist_ok=True)

    all_financials: list[pd.DataFrame] = []
    all_ratios: list[pd.DataFrame] = []

    for ticker in TICKERS:
        xlsx = DATA_DIR / f"{ticker}_financial_model.xlsx"
        if not xlsx.exists():
            print(f"  [PBI] Skipping {ticker} — no Excel file found.")
            continue

        # --- Financial statements (long format) ---
        for sheet, label in STATEMENT_LABELS.items():
            melted = _melt_statement(ticker, sheet, label)
            if melted is not None:
                all_financials.append(melted)

        # --- Ratios (long format) ---
        ratio_sheets = [
            "Profitability Ratios",
            "Liquidity Ratios",
            "Leverage Ratios",
            "Efficiency Ratios",
        ]
        categories = ["Profitability", "Liquidity", "Leverage", "Efficiency"]

        for sheet, cat in zip(ratio_sheets, categories):
            try:
                df = pd.read_excel(xlsx, sheet_name=sheet, index_col=0)
            except Exception:
                continue
            if df.empty:
                continue
            all_ratios.append(_melt_ratios(ticker, cat, df))

    # --- Build dimension tables ---
    # dim_ticker
    dim_ticker_rows = []
    for ticker, name in TICKERS.items():
        meta = COMPANY_META.get(ticker, {})
        dim_ticker_rows.append({
            "Ticker": ticker,
            "Company": name,
            "Sector": meta.get("Sector", ""),
            "Industry": meta.get("Industry", ""),
        })
    dim_ticker = pd.DataFrame(dim_ticker_rows)

    # dim_date  — collect all distinct fiscal years across all data
    all_years: set[int] = set()
    for df in all_financials:
        all_years.update(df["Fiscal Year"].unique())
    for df in all_ratios:
        all_years.update(df["Fiscal Year"].unique())
    dim_date = pd.DataFrame(
        sorted(all_years), columns=["Fiscal Year"]
    )

    # --- Write CSVs ---
    dim_ticker.to_csv(POWERBI_DATA_DIR / "dim_ticker.csv", index=False)
    dim_date.to_csv(POWERBI_DATA_DIR / "dim_date.csv", index=False)

    if all_financials:
        fact_fin = pd.concat(all_financials, ignore_index=True)
        fact_fin.to_csv(POWERBI_DATA_DIR / "fact_financials.csv", index=False)
    if all_ratios:
        fact_rat = pd.concat(all_ratios, ignore_index=True)
        fact_rat.to_csv(POWERBI_DATA_DIR / "fact_ratios.csv", index=False)

    print(f"  [PBI] Star-schema CSV files written to {POWERBI_DATA_DIR.resolve()}/")
    print(f"        Tables: dim_ticker ({len(dim_ticker)} rows), "
          f"dim_date ({len(dim_date)} rows), "
          f"fact_financials ({len(pd.concat(all_financials)) if all_financials else 0} rows), "
          f"fact_ratios ({len(pd.concat(all_ratios)) if all_ratios else 0} rows)")
