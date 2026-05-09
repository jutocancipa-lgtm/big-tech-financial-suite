"""
cleaner.py - Standardises raw Yahoo Finance data into a consistent format.

- Converts values to millions of USD.
- Transposes DataFrames so rows are fiscal years and columns are line items.
- Extracts a common set of line items for the three-statement model.
"""

import pandas as pd
import numpy as np


def to_millions(df: pd.DataFrame) -> pd.DataFrame:
    """Convert raw values (typically in raw USD) to millions of USD."""
    return df / 1_000_000


def transpose_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    """Transpose so rows = fiscal years, columns = line items.

    Sorts by year descending (most recent first) and converts to millions.
    """
    df = to_millions(df.copy())
    df = df.transpose()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index(ascending=False)
    # Flatten column names to strings
    df.columns = [str(c) for c in df.columns]
    return df


# ---- Line-item labels used by yfinance for each statement ----
# These are the actual label strings returned by yfinance.

INCOME_LABELS = {
    "Total Revenue": "Revenue",
    "Operating Revenue": "Revenue",
    "Gross Profit": "Gross Profit",
    "Operating Expense": "Operating Expenses",
    "Operating Income": "Operating Income",
    "Operating Revenue": "Operating Revenue",
    "Net Income": "Net Income",
    "Net Income From Continuing Operations": "Net Income",
    "EBIT": "EBIT",
    "EBITDA": "EBITDA",
    "Interest Expense": "Interest Expense",
    "Income Before Tax": "Pre-Tax Income",
    "Tax Provision": "Tax Provision",
    "Diluted EPS": "Diluted EPS",
    "Basic EPS": "Basic EPS",
    "Cost Of Revenue": "Cost of Revenue",
    "Research And Development": "R&D Expense",
    "Selling General And Administration": "SG&A",
    "Selling General And Administrative": "SG&A",
}

BALANCE_LABELS = {
    "Total Assets": "Total Assets",
    "Current Assets": "Current Assets",
    "Cash And Cash Equivalents": "Cash & Equivalents",
    "Cash Cash Equivalents And Short Term Investments": "Cash & Equivalents",
    "Current Investments": "Short-Term Investments",
    "Short Term Investments": "Short-Term Investments",
    "Net Receivables": "Accounts Receivable",
    "Inventory": "Inventory",
    "Total Liabilities Net Minority Interest": "Total Liabilities",
    "Current Liabilities": "Current Liabilities",
    "Long Term Debt": "Long-Term Debt",
    "Long Term Debt And Capital Lease Obligation": "Long-Term Debt",
    "Total Equity Gross Minority Interest": "Total Equity",
    "Stockholders Equity": "Total Equity",
    "Retained Earnings": "Retained Earnings",
    "Property Plant Equipment Net": "PP&E (Net)",
    "Goodwill": "Goodwill",
    "Intangible Assets Excluding Goodwill": "Intangibles",
    "Goodwill And Other Intangible Assets": "Goodwill & Intangibles",
    "Accounts Payable": "Accounts Payable",
    "Current Deferred Revenue": "Deferred Revenue",
    "Current Debt": "Short-Term Debt",
    "Current Debt And Capital Lease Obligation": "Short-Term Debt",
    "Common Stock Equity": "Common Equity",
}

CASHFLOW_LABELS = {
    "Operating Cash Flow": "Operating Cash Flow",
    "Free Cash Flow": "Free Cash Flow",
    "Capital Expenditure": "Capital Expenditure",
    "Cash Dividends Paid": "Dividends Paid",
    "Stock Based Compensation": "Stock-Based Compensation",
    "Depreciation Amortization Depletion": "D&A",
    "Depreciation And Amortization": "D&A",
    "Net Income": "Net Income",
    "Change In Working Capital": "Change in Working Capital",
    "Investing Cash Flow": "Investing Cash Flow",
    "Financing Cash Flow": "Financing Cash Flow",
    "Repurchase Of Capital Stock": "Share Repurchases",
    "Common Stock Dividend Paid": "Dividends Paid",
    "Issuance Of Capital Stock": "Stock Issuance",
    "Change In Cash": "Change in Cash",
}


def _rename_columns(df: pd.DataFrame, label_map: dict) -> pd.DataFrame:
    """Rename columns using the label map; drop unmapped columns."""
    renamed = df.rename(columns=label_map, errors="ignore")
    # Keep only columns that matched and have a value
    keep = [c for c in renamed.columns if c in label_map.values()]
    return renamed[[c for c in keep if c in renamed.columns]]


def _common_columns(df: pd.DataFrame, desired: list[str]) -> pd.DataFrame:
    """Ensure all desired columns exist, filling missing ones with NaN."""
    for col in desired:
        if col not in df.columns:
            df[col] = np.nan
    return df[desired]


def clean_income_statement(
    raw: pd.DataFrame,
) -> pd.DataFrame | None:
    """Clean and standardise an income statement.

    Returns a DataFrame with a fixed set of columns, or None if empty.
    """
    if raw is None or raw.empty:
        return None
    df = transpose_and_clean(raw)
    df = _rename_columns(df, INCOME_LABELS)

    desired = [
        "Revenue",
        "Cost of Revenue",
        "Gross Profit",
        "R&D Expense",
        "SG&A",
        "Operating Expenses",
        "Operating Income",
        "Interest Expense",
        "Pre-Tax Income",
        "Tax Provision",
        "Net Income",
        "EBIT",
        "EBITDA",
        "Diluted EPS",
    ]
    return _common_columns(df, desired)


def clean_balance_sheet(raw: pd.DataFrame) -> pd.DataFrame | None:
    """Clean and standardise a balance sheet."""
    if raw is None or raw.empty:
        return None
    df = transpose_and_clean(raw)
    df = _rename_columns(df, BALANCE_LABELS)

    desired = [
        "Cash & Equivalents",
        "Short-Term Investments",
        "Accounts Receivable",
        "Inventory",
        "Current Assets",
        "PP&E (Net)",
        "Goodwill",
        "Intangibles",
        "Total Assets",
        "Accounts Payable",
        "Short-Term Debt",
        "Current Liabilities",
        "Long-Term Debt",
        "Total Liabilities",
        "Total Equity",
        "Retained Earnings",
    ]
    return _common_columns(df, desired)


def clean_cash_flow_statement(raw: pd.DataFrame) -> pd.DataFrame | None:
    """Clean and standardise a cash-flow statement."""
    if raw is None or raw.empty:
        return None
    df = transpose_and_clean(raw)
    df = _rename_columns(df, CASHFLOW_LABELS)

    desired = [
        "Net Income",
        "D&A",
        "Stock-Based Compensation",
        "Change in Working Capital",
        "Operating Cash Flow",
        "Capital Expenditure",
        "Investing Cash Flow",
        "Financing Cash Flow",
        "Free Cash Flow",
        "Dividends Paid",
        "Share Repurchases",
        "Change in Cash",
    ]
    return _common_columns(df, desired)
