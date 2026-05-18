"""
ratios.py - Computes financial ratios from cleaned three-statement data.

All ratios use values already expressed in millions of USD.
"""

import pandas as pd
import numpy as np


def _safe_div(num: pd.Series | float, den: pd.Series | float) -> pd.Series:
    """Divide two series/values, returning NaN where denominator is zero."""
    with np.errstate(divide="ignore", invalid="ignore"):
        result = num / den
    with pd.option_context("future.no_silent_downcasting", True):
        return result.replace([np.inf, -np.inf], np.nan).infer_objects(copy=False)


def profitability_ratios(
    income: pd.DataFrame, balance: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Compute profitability ratios from the income statement."""
    income = income.loc[~income.index.duplicated(keep='first')]
    if balance is not None:
        balance = balance.loc[~balance.index.duplicated(keep='first')]
    ratios = pd.DataFrame(index=income.index)

    # Net Profit Margin = Net Income / Revenue
    ratios["Net Profit Margin"] = _safe_div(
        income["Net Income"], income["Revenue"]
    )

    # Gross Margin = Gross Profit / Revenue
    ratios["Gross Margin"] = _safe_div(
        income["Gross Profit"], income["Revenue"]
    )

    # Operating Margin = Operating Income / Revenue
    if "Operating Income" in income.columns:
        ratios["Operating Margin"] = _safe_div(
            income["Operating Income"], income["Revenue"]
        )

    # EBITDA Margin = EBITDA / Revenue
    if "EBITDA" in income.columns:
        ratios["EBITDA Margin"] = _safe_div(
            income["EBITDA"], income["Revenue"]
        )

    # R&D as % of Revenue
    if "R&D Expense" in income.columns:
        ratios["R&D % of Revenue"] = _safe_div(
            income["R&D Expense"], income["Revenue"]
        )

    # Effective Tax Rate = Tax Provision / Pre-Tax Income
    if "Tax Provision" in income.columns and "Pre-Tax Income" in income.columns:
        ratios["Effective Tax Rate"] = _safe_div(
            income["Tax Provision"], income["Pre-Tax Income"]
        )

    # Basic EPS (maybe not from Diluted)
    if "Diluted EPS" in income.columns:
        ratios["Diluted EPS"] = income["Diluted EPS"]

    # ROA & ROE if balance sheet is available
    if balance is not None:
        avg_assets = balance["Total Assets"].mean()
        avg_equity = balance["Total Equity"].mean()
        ratios["ROA"] = _safe_div(income["Net Income"], avg_assets)
        ratios["ROE"] = _safe_div(income["Net Income"], avg_equity)

    return ratios


def liquidity_ratios(balance: pd.DataFrame) -> pd.DataFrame:
    """Compute liquidity ratios from the balance sheet."""
    balance = balance.loc[~balance.index.duplicated(keep='first')]
    ratios = pd.DataFrame(index=balance.index)

    # Current Ratio = Current Assets / Current Liabilities
    ratios["Current Ratio"] = _safe_div(
        balance["Current Assets"], balance["Current Liabilities"]
    )

    # Quick Ratio = (Current Assets - Inventory) / Current Liabilities
    inventory = balance.get("Inventory", pd.Series(0, index=balance.index))
    ratios["Quick Ratio"] = _safe_div(
        balance["Current Assets"] - inventory, balance["Current Liabilities"]
    )

    # Cash Ratio = Cash & Equivalents / Current Liabilities
    ratios["Cash Ratio"] = _safe_div(
        balance["Cash & Equivalents"], balance["Current Liabilities"]
    )

    return ratios


def leverage_ratios(balance: pd.DataFrame) -> pd.DataFrame:
    """Compute leverage / solvency ratios from the balance sheet."""
    balance = balance.loc[~balance.index.duplicated(keep='first')]
    ratios = pd.DataFrame(index=balance.index)

    # Debt-to-Equity = Total Liabilities / Total Equity
    ratios["Debt-to-Equity"] = _safe_div(
        balance["Total Liabilities"], balance["Total Equity"]
    )

    # Debt Ratio = Total Liabilities / Total Assets
    ratios["Debt Ratio"] = _safe_div(
        balance["Total Liabilities"], balance["Total Assets"]
    )

    # Long-Term Debt to Equity
    if "Long-Term Debt" in balance.columns:
        ratios["LT Debt-to-Equity"] = _safe_div(
            balance["Long-Term Debt"], balance["Total Equity"]
        )

    # Equity Ratio = Total Equity / Total Assets
    ratios["Equity Ratio"] = _safe_div(
        balance["Total Equity"], balance["Total Assets"]
    )

    return ratios


def efficiency_ratios(
    income: pd.DataFrame, balance: pd.DataFrame
) -> pd.DataFrame:
    """Compute efficiency / turnover ratios."""
    income = income.loc[~income.index.duplicated(keep='first')]
    balance = balance.loc[~balance.index.duplicated(keep='first')]
    ratios = pd.DataFrame(index=income.index)

    # Asset Turnover = Revenue / Avg Total Assets
    avg_assets = balance["Total Assets"]
    ratios["Asset Turnover"] = _safe_div(income["Revenue"], avg_assets)

    return ratios


def compute_all(
    income: pd.DataFrame | None,
    balance: pd.DataFrame | None,
    cashflow: pd.DataFrame | None,
) -> dict[str, pd.DataFrame | None]:
    """Compute all ratio categories and return a dict of DataFrames."""
    result: dict[str, pd.DataFrame | None] = {}

    if income is not None:
        result["Profitability"] = profitability_ratios(income, balance)
    else:
        result["Profitability"] = None

    if balance is not None:
        result["Liquidity"] = liquidity_ratios(balance)
        result["Leverage"] = leverage_ratios(balance)
    else:
        result["Liquidity"] = None
        result["Leverage"] = None

    if income is not None and balance is not None:
        result["Efficiency"] = efficiency_ratios(income, balance)
    else:
        result["Efficiency"] = None

    return result
