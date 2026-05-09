"""
app.py - Streamlit dashboard for the three-statement financial model.

Usage:
    streamlit run app.py
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go

from src.fetcher import TICKERS, fetch_all
from src.cleaner import (
    clean_income_statement,
    clean_balance_sheet,
    clean_cash_flow_statement,
)
from src.ratios import compute_all
from src.charts import (
    candlestick_chart,
    balance_stacked_bar,
    income_waterfall,
    margins_line_chart,
    cashflow_grouped_bar,
    fcf_line_chart,
    capex_fcf_dual,
    comparison_grouped_bar,
    comparison_margin_line,
    radar_comparison,
    valuation_table,
)


# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FinTech Dashboard — AMD · NVDA · AAPL",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme overrides ─────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #1E1E1E; }
    .st-emotion-cache-1y4p8pa { padding: 1rem 1rem; }
    .main-header { color: #1F4E79; font-size: 1.6rem; font-weight: 700; }
    .metric-card { background: #2D2D2D; border-radius: 8px;
                   padding: 1rem; border-left: 4px solid #1F4E79; }
    .metric-label { color: #999; font-size: 0.8rem; }
    .metric-value { color: #FFF; font-size: 1.5rem; font-weight: 700; }
    .metric-delta-pos { color: #00C853; }
    .metric-delta-neg { color: #FF5252; }
    .footer { text-align: center; color: #666; font-size: 0.8rem;
              padding: 2rem 0 0 0; border-top: 1px solid #333; margin-top: 2rem; }
    .stSidebar .sidebar-content { background-color: #252525; }
    .stTabs [data-baseweb="tab-list"] { gap: 2px; }
    .stTabs [data-baseweb="tab"] { background: #2D2D2D; border-radius: 4px 4px 0 0; }
</style>
""", unsafe_allow_html=True)

SECTOR_AVG = {
    "P/E": 25.0,
    "Gross Margin %": 45.0,
    "Net Margin %": 20.0,
    "ROE %": 30.0,
    "Revenue YoY Growth %": 15.0,
}


# ── Data helpers ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner="Fetching financial statements...")
def load_financials(ticker: str) -> dict[str, Any]:
    """Load and clean all three statements + ratios for a ticker."""
    raw = fetch_all(ticker)
    result: dict[str, Any] = {}
    result["income"] = clean_income_statement(raw.get("income"))
    result["balance"] = clean_balance_sheet(raw.get("balance"))
    result["cashflow"] = clean_cash_flow_statement(raw.get("cashflow"))
    result["ratios"] = compute_all(
        result["income"], result["balance"], result["cashflow"]
    )
    return result


@st.cache_data(ttl=300, show_spinner=False)
def load_price_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Download OHLCV price data from yfinance."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        if hist.empty:
            st.warning(f"No price data for {ticker}")
        return hist
    except Exception:
        st.warning(f"Failed to fetch price data for {ticker}")
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def load_real_time_info(ticker: str) -> dict[str, Any]:
    """Load fast info (real-time) for a ticker."""
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        return {k: info.get(k) for k in dir(info) if not k.startswith("_")}
    except Exception:
        return {}


def _safe(val: Any, fmt: str = "num") -> str:
    """Return formatted value or 'N/A' if missing."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    if fmt == "pct":
        return f"{val*100:.1f}%"
    if fmt == "pct_raw":
        return f"{val:.1f}%"
    if fmt == "b":
        if abs(val) >= 1000:
            return f"${val/1000:.2f}T"
        return f"${val:.1f}B"
    if fmt == "m":
        return f"${val:.0f}M"
    return str(val)


def _yoy_str(current: float, prior: float) -> str:
    y = _yoy(current, prior)
    if y is None:
        return "N/A"
    cls = "metric-delta-pos" if y >= 0 else "metric-delta-neg"
    return f"<span class='{cls}'>({y*100:+.1f}%)</span>"


def _yoy(current: float, prior: float) -> float | None:
    if pd.isna(current) or pd.isna(prior) or prior == 0:
        return None
    return (current - prior) / abs(prior)


def _year_labels(df: pd.DataFrame) -> list[str]:
    return [str(d.year) for d in df.index]


# ── Sidebar ─────────────────────────────────────────────────────────────────

def build_sidebar():
    with st.sidebar:
        st.markdown("<div class='main-header'>📊 FinTech Dashboard</div>",
                    unsafe_allow_html=True)
        st.markdown("---")
        for t, name in TICKERS.items():
            st.markdown(f"**{t}** — {name}")
        st.markdown("---")
        page = st.radio(
            "Navigate",
            [
                "📈 Stock Price",
                "📋 Balance Sheet",
                "💰 Income Statement",
                "💵 Cash Flow",
                "⚖️ Comparison",
                "🎯 KPI Dashboard",
            ],
            label_visibility="collapsed",
        )
        st.markdown("---")
        st.markdown(
            "<small>Data source: Yahoo Finance<br>"
            "Built by Julian Tocancipá</small>",
            unsafe_allow_html=True,
        )
        return page


# ── Page 1: Stock Price ─────────────────────────────────────────────────────

def page_stock_price():
    st.markdown("<div class='main-header'>📈 Stock Price</div>",
                unsafe_allow_html=True)
    col1, col2 = st.columns([1, 3])
    with col1:
        ticker = st.selectbox("Company", list(TICKERS.keys()), key="sp_ticker")
    with col2:
        period = st.segmented_control(
            "Period", ["1mo", "3mo", "6mo", "1y", "3y", "5y"],
            default="1y", key="sp_period",
        )
    period_map = {"1mo": "1mo", "3mo": "3mo", "6mo": "6mo",
                  "1y": "1y", "3y": "3y", "5y": "5y"}
    hist = load_price_history(ticker, period_map[period])
    if hist.empty:
        st.warning("Price data unavailable. Using sample fallback.")
        return

    latest = hist.iloc[-1]
    prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else latest["Close"]
    change_d = latest["Close"] - prev_close
    change_pct = change_d / prev_close * 100

    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-label'>Current Price</div>
            <div class='metric-value'>${latest['Close']:.2f}</div>
        </div>""", unsafe_allow_html=True)
    with mc2:
        cls = "metric-delta-pos" if change_d >= 0 else "metric-delta-neg"
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-label'>Daily Change $</div>
            <div class='metric-value {cls}'>${change_d:+.2f}</div>
        </div>""", unsafe_allow_html=True)
    with mc3:
        cls = "metric-delta-pos" if change_pct >= 0 else "metric-delta-neg"
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-label'>Daily Change %</div>
            <div class='metric-value {cls}'>{change_pct:+.2f}%</div>
        </div>""", unsafe_allow_html=True)

    fig = candlestick_chart(hist, ticker)
    st.plotly_chart(fig, use_container_width=True)


# ── Page 2: Balance Sheet ───────────────────────────────────────────────────

def page_balance_sheet():
    st.markdown("<div class='main-header'>📋 Balance Sheet</div>",
                unsafe_allow_html=True)
    ticker = st.selectbox("Company", list(TICKERS.keys()), key="bs_ticker")
    data = load_financials(ticker)
    bal = data.get("balance")
    if bal is None or bal.empty:
        st.warning("Balance sheet data unavailable.")
        return
    inc = data.get("income")

    latest = bal.iloc[0]
    prior = bal.iloc[1] if len(bal) > 1 else None

    def _card(label: str, val: float, prev: float | None):
        yoy = _yoy_str(val, prev) if prev is not None and val != 0 else ""
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-label'>{label}</div>
            <div class='metric-value'>{_safe(val, 'b')}</div>
            {yoy}
        </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        _card("Total Assets", latest.get("Total Assets", 0),
              prior.get("Total Assets") if prior is not None else None)
    with c2:
        _card("Total Liabilities", latest.get("Total Liabilities", 0),
              prior.get("Total Liabilities") if prior is not None else None)
    with c3:
        _card("Total Equity", latest.get("Total Equity", 0),
              prior.get("Total Equity") if prior is not None else None)

    with st.expander("📦 Total Assets — Breakdown"):
        ca = latest.get("Current Assets", 0)
        nca = latest.get("Total Assets", 0) - ca if not pd.isna(
            latest.get("Total Assets")) else 0
        sub = {
            "Cash & Equivalents": latest.get("Cash & Equivalents", 0),
            "Accounts Receivable": latest.get("Accounts Receivable", 0),
            "Inventory": latest.get("Inventory", 0),
        }
        for k, v in sub.items():
            st.markdown(f"- **{k}**: {_safe(v, 'b')}")
        st.markdown(f"- **Non-Current Assets**: {_safe(nca, 'b')}")

    with st.expander("📦 Total Liabilities — Breakdown"):
        cl = latest.get("Current Liabilities", 0)
        lt = latest.get("Long-Term Debt", 0)
        other_l = latest.get("Total Liabilities", 0) - cl - lt
        st.markdown(f"- **Current Liabilities**: {_safe(cl, 'b')}")
        st.markdown(f"- **Long-Term Debt**: {_safe(lt, 'b')}")
        st.markdown(f"- **Other Liabilities**: {_safe(other_l, 'b')}")

    with st.expander("📦 Total Equity — Breakdown"):
        re = latest.get("Retained Earnings", 0)
        other_eq = latest.get("Total Equity", 0) - re
        st.markdown(f"- **Retained Earnings**: {_safe(re, 'b')}")
        st.markdown(f"- **Other Equity**: {_safe(other_eq, 'b')}")

    fig = balance_stacked_bar(bal)
    st.plotly_chart(fig, use_container_width=True)


# ── Page 3: Income Statement ────────────────────────────────────────────────

def page_income_statement():
    st.markdown("<div class='main-header'>💰 Income Statement</div>",
                unsafe_allow_html=True)
    ticker = st.selectbox("Company", list(TICKERS.keys()), key="is_ticker")
    data = load_financials(ticker)
    inc = data.get("income")
    if inc is None or inc.empty:
        st.warning("Income statement data unavailable.")
        return

    latest = inc.iloc[0]
    prior = inc.iloc[1] if len(inc) > 1 else None

    def _line(label: str, val: float, prev: float | None = None,
              pct: float | None = None):
        y = _yoy_str(val, prev) if prev is not None else ""
        p = f"({pct*100:.1f}%)" if pct is not None else ""
        st.markdown(f"- **{label}**: {_safe(val, 'b')} {p} {y}")

    with st.expander("📊 Revenue", expanded=True):
        rev = latest.get("Revenue", 0)
        prev_rev = prior.get("Revenue") if prior is not None else None
        yoy_r = _yoy(rev, prev_rev) if prev_rev is not None else None
        _line("Revenue", rev, prev_rev, yoy_r)

    with st.expander("📊 Gross Profit"):
        gp = latest.get("Gross Profit", 0)
        prev_gp = prior.get("Gross Profit") if prior is not None else None
        gm = gp / rev if rev != 0 else 0
        _line("Gross Profit", gp, prev_gp)
        st.markdown(f"  *Gross Margin: {gm*100:.1f}%*")

    with st.expander("📊 Operating Income"):
        oi = latest.get("Operating Income", 0)
        prev_oi = prior.get("Operating Income") if prior is not None else None
        om = oi / rev if rev != 0 else 0
        _line("Operating Income", oi, prev_oi)
        st.markdown(f"  *Operating Margin: {om*100:.1f}%*")
        rd = latest.get("R&D Expense", 0)
        rd_pct = rd / rev if rev != 0 else 0
        _line("R&D Expense", rd)
        st.markdown(f"  *R&D as % of Revenue: {rd_pct*100:.1f}%*")
        sga = latest.get("SG&A", 0)
        _line("SG&A Expense", sga)

    with st.expander("📊 Net Income"):
        ni = latest.get("Net Income", 0)
        prev_ni = prior.get("Net Income") if prior is not None else None
        nm = ni / rev if rev != 0 else 0
        _line("Net Income", ni, prev_ni)
        st.markdown(f"  *Net Margin: {nm*100:.1f}%*")
        tax = latest.get("Tax Provision", 0)
        _line("Tax Expense", tax)
        interest = latest.get("Interest Expense", 0)
        _line("Interest Expense", interest)

    c1, c2 = st.columns(2)
    with c1:
        fig_w = income_waterfall(inc)
        st.plotly_chart(fig_w, use_container_width=True)
    with c2:
        fig_m = margins_line_chart(inc)
        st.plotly_chart(fig_m, use_container_width=True)


# ── Page 4: Cash Flow ───────────────────────────────────────────────────────

def page_cash_flow():
    st.markdown("<div class='main-header'>💵 Cash Flow Statement</div>",
                unsafe_allow_html=True)
    ticker = st.selectbox("Company", list(TICKERS.keys()), key="cf_ticker")
    data = load_financials(ticker)
    cf = data.get("cashflow")
    inc = data.get("income")
    if cf is None or cf.empty:
        st.warning("Cash flow data unavailable.")
        return

    latest = cf.iloc[0]

    def _cf_card(label: str, val: float):
        cls = "metric-delta-pos" if val >= 0 else "metric-delta-neg"
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-label'>{label}</div>
            <div class='metric-value {cls}'>{_safe(val, 'b')}</div>
        </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        _cf_card("Operating CF", latest.get("Operating Cash Flow", 0))
    with c2:
        _cf_card("Investing CF", latest.get("Investing Cash Flow", 0))
    with c3:
        _cf_card("Financing CF", latest.get("Financing Cash Flow", 0))

    with st.expander("📦 Operating Cash Flow — Details"):
        for k in ["Net Income", "D&A", "Stock-Based Compensation",
                  "Change in Working Capital"]:
            v = latest.get(k, 0)
            st.markdown(f"- **{k}**: {_safe(v, 'b')}")

    with st.expander("📦 Investing Cash Flow — Details"):
        capex = latest.get("Capital Expenditure", 0)
        st.markdown(f"- **Capital Expenditure**: {_safe(capex, 'b')}")

    with st.expander("📦 Financing Cash Flow — Details"):
        for k in ["Dividends Paid", "Share Repurchases"]:
            v = latest.get(k, 0)
            st.markdown(f"- **{k}**: {_safe(v, 'b')}")

    c1, c2 = st.columns(2)
    with c1:
        fig1 = cashflow_grouped_bar(cf)
        st.plotly_chart(fig1, use_container_width=True)
    with c2:
        fig2 = fcf_line_chart(cf)
        st.plotly_chart(fig2, use_container_width=True)
    fig3 = capex_fcf_dual(cf, inc)
    st.plotly_chart(fig3, use_container_width=True)


# ── Page 5: Comparison ──────────────────────────────────────────────────────

def page_comparison():
    st.markdown("<div class='main-header'>⚖️ Comparison — AMD vs NVDA vs AAPL</div>",
                unsafe_allow_html=True)

    all_data = {}
    for t in TICKERS:
        all_data[t] = load_financials(t)

    incs = {t: all_data[t]["income"] for t in TICKERS}
    bals = {t: all_data[t]["balance"] for t in TICKERS}
    cfs = {t: all_data[t]["cashflow"] for t in TICKERS}
    rat_all = {t: all_data[t]["ratios"] for t in TICKERS}

    st.subheader("📊 Revenue Comparison")
    fig = comparison_grouped_bar(incs, "Revenue", "Revenue by Company")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📊 Margins Comparison")
    c1, c2 = st.columns(2)
    with c1:
        fig = comparison_margin_line(incs, "Net Income", "Revenue",
                                     "Net Margin % Over Time")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = comparison_margin_line(incs, "Gross Profit", "Revenue",
                                     "Gross Margin % Over Time")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("📊 Profitability Radar")
    radar_data = {}
    for t in TICKERS:
        inc = incs[t]
        bal = bals[t]
        cf = cfs[t]
        if inc is None or inc.empty:
            continue
        latest_inc = inc.iloc[0]
        ni = latest_inc.get("Net Income", 0)
        rev = latest_inc.get("Revenue", 0)
        gp = latest_inc.get("Gross Profit", 0)
        nm = ni / rev if rev != 0 else 0
        gm = gp / rev if rev != 0 else 0
        fcf_m = 0
        if cf is not None and not cf.empty:
            fcf = cf.iloc[0].get("Free Cash Flow", 0)
            fcf_m = fcf / rev if rev != 0 else 0
        ta = bal.iloc[0].get("Total Assets") if bal is not None else 0
        te = bal.iloc[0].get("Total Equity") if bal is not None else 0
        roa = ni / ta if ta != 0 else 0
        roe = ni / te if te != 0 else 0
        radar_data[t] = {
            "Net Margin": nm, "Gross Margin": gm,
            "FCF Margin": fcf_m, "ROA": roa, "ROE": roe,
        }
    if radar_data:
        fig = radar_comparison(radar_data)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("📊 Valuation Multiples")
    val_data = {}
    for t in TICKERS:
        info = load_real_time_info(t)
        inc = incs[t]
        cf = cfs[t]
        bal = bals[t]
        val = {}
        price = info.get("regular_market_previous_close") or info.get("last_price")
        shares = info.get("shares")

        pe = None
        if inc is not None and not inc.empty:
            ni = inc.iloc[0].get("Net Income", 0)
            if price and shares and ni:
                mcap = price * shares * 1e-6  # millions
                pe = mcap / ni if ni != 0 else None
        val["P/E"] = round(pe, 2) if pe else "N/A"

        ev_ebitda = None
        if inc is not None and not inc.empty and bal is not None and not bal.empty:
            ebitda = inc.iloc[0].get("EBITDA", 0)
            mcap_ev = (price * shares * 1e-6) if (price and shares) else 0
            debt = bal.iloc[0].get("Total Liabilities", 0)
            cash = bal.iloc[0].get("Cash & Equivalents", 0)
            ev = mcap_ev + debt - cash
            ev_ebitda = ev / ebitda if ebitda != 0 else None
        val["EV/EBITDA"] = round(ev_ebitda, 2) if ev_ebitda else "N/A"

        pfcf = None
        if cf is not None and not cf.empty:
            fcf = cf.iloc[0].get("Free Cash Flow", 0)
            mcap_pfcf = (price * shares * 1e-6) if (price and shares) else 0
            pfcf = mcap_pfcf / fcf if fcf != 0 else None
        val["P/FCF"] = round(pfcf, 2) if pfcf else "N/A"
        val_data[t] = val

    fig = valuation_table(val_data, None)
    st.plotly_chart(fig, use_container_width=True)


# ── Page 6: KPI Dashboard ───────────────────────────────────────────────────

def page_kpi_dashboard():
    st.markdown("<div class='main-header'>🎯 KPI Dashboard — Real Time</div>",
                unsafe_allow_html=True)
    st.caption("Auto-refresh every 5 minutes")

    all_kpis: dict[str, dict[str, Any]] = {}

    for ticker in TICKERS:
        data = load_financials(ticker)
        info = load_real_time_info(ticker)
        inc = data.get("income")
        bal = data.get("balance")
        cf = data.get("cashflow")

        kpi: dict[str, Any] = {}

        # Current price
        price = info.get("regular_market_previous_close") or info.get("last_price")
        kpi["Current Price"] = price if price else "N/A"

        # Market cap
        shares = info.get("shares")
        mcap = (price * shares * 1e-6) if (price and shares) else None
        kpi["Market Cap ($M)"] = round(mcap, 0) if mcap else "N/A"

        # P/E
        if inc is not None and not inc.empty and mcap:
            ni = inc.iloc[0].get("Net Income", 0)
            kpi["P/E"] = round(mcap / ni, 2) if ni else "N/A"
        else:
            kpi["P/E"] = "N/A"

        # Margins
        if inc is not None and not inc.empty:
            li = inc.iloc[0]
            rev = li.get("Revenue", 0)
            kpi["Gross Margin %"] = round(li.get("Gross Profit", 0) / rev * 100, 1) if rev else "N/A"
            kpi["Net Margin %"] = round(li.get("Net Income", 0) / rev * 100, 1) if rev else "N/A"
            # Revenue YoY
            if len(inc) > 1:
                prev_rev = inc.iloc[1].get("Revenue", 0)
                yoy_r = _yoy(rev, prev_rev)
                kpi["Revenue YoY Growth %"] = round(yoy_r * 100, 1) if yoy_r else "N/A"
            else:
                kpi["Revenue YoY Growth %"] = "N/A"
        else:
            kpi["Gross Margin %"] = "N/A"
            kpi["Net Margin %"] = "N/A"
            kpi["Revenue YoY Growth %"] = "N/A"

        # FCF
        if cf is not None and not cf.empty:
            kpi["Free Cash Flow ($M)"] = round(cf.iloc[0].get("Free Cash Flow", 0), 0)
        else:
            kpi["Free Cash Flow ($M)"] = "N/A"

        # ROE
        if inc is not None and not inc.empty and bal is not None and not bal.empty:
            ni = inc.iloc[0].get("Net Income", 0)
            te = bal.iloc[0].get("Total Equity", 0)
            kpi["ROE %"] = round(ni / te * 100, 1) if te else "N/A"
        else:
            kpi["ROE %"] = "N/A"

        all_kpis[ticker] = kpi

    # Metric cards per company
    for ticker in TICKERS:
        st.subheader(f"{ticker} — {TICKERS[ticker]}")
        kpi = all_kpis[ticker]
        cols = st.columns(4)
        keys_shown = ["Current Price", "Market Cap ($M)", "P/E", "Gross Margin %",
                      "Net Margin %", "Free Cash Flow ($M)", "Revenue YoY Growth %",
                      "ROE %"]
        for i, key in enumerate(keys_shown):
            val = kpi.get(key, "N/A")
            v_str = val if isinstance(val, str) else str(val)
            sq = SECTOR_AVG.get(key)
            cls = ""
            if isinstance(val, (int, float)) and sq:
                cls = "metric-delta-pos" if val >= sq else "metric-delta-neg"
            with cols[i % 4]:
                st.markdown(f"""
                <div class='metric-card'>
                    <div class='metric-label'>{key}</div>
                    <div class='metric-value {cls}'>{v_str}</div>
                </div>""", unsafe_allow_html=True)

    # Summary table
    st.subheader("📋 KPI Summary — All Companies")
    rows = []
    metrics = ["Current Price", "Market Cap ($M)", "P/E", "Gross Margin %",
               "Net Margin %", "Free Cash Flow ($M)", "Revenue YoY Growth %",
               "ROE %"]
    for m in metrics:
        row = {"KPI": m}
        for t in TICKERS:
            row[t] = all_kpis.get(t, {}).get(m, "N/A")
        rows.append(row)
    df_t = pd.DataFrame(rows)
    st.dataframe(df_t, use_container_width=True, hide_index=True)

    # Auto-refresh
    st.caption("Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if st.button("🔄 Refresh Now"):
        st.cache_data.clear()
        st.rerun()


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    page = build_sidebar()
    st.markdown(f"<small>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small>",
                unsafe_allow_html=True)

    if "Stock Price" in page:
        page_stock_price()
    elif "Balance Sheet" in page:
        page_balance_sheet()
    elif "Income Statement" in page:
        page_income_statement()
    elif "Cash Flow" in page:
        page_cash_flow()
    elif "Comparison" in page:
        page_comparison()
    elif "KPI" in page:
        page_kpi_dashboard()

    st.markdown("""
    <div class='footer'>
        Data source: Yahoo Finance | Built by Julian Tocancipá |
        Last updated: {ts}
    </div>
    """.format(ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        unsafe_allow_html=True)


if __name__ == "__main__":
    main()
