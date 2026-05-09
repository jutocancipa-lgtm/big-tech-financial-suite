"""charts.py - All Plotly chart functions for the Streamlit dashboard."""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots


# ── Colour palette ──────────────────────────────────────────────────────────
DARK_BG = "#1E1E1E"
CARD_BG = "#2D2D2D"
ACCENT_BLUE = "#1F4E79"
ACCENT_GREEN = "#1B5E20"
UP_GREEN = "#00C853"
DOWN_RED = "#FF5252"
GRID_COLOR = "#333333"
TEXT_COLOR = "#CCCCCC"

_TEMPLATE = "plotly_dark"

# ── Helpers ─────────────────────────────────────────────────────────────────

def _fmt_b(y: float) -> str:
    """Format value in billions to '$X.XB' or '$X.XM'."""
    if pd.isna(y) or y == 0:
        return "$0.0B"
    if abs(y) >= 1000:
        return f"${y/1000:.1f}T"
    if abs(y) >= 1:
        return f"${y:.1f}B"
    return f"${y*1000:.0f}M"


def _fmt_pct(y: float) -> str:
    if pd.isna(y):
        return "N/A"
    return f"{y*100:.1f}%"


def _yoy(present: float, prior: float) -> float | None:
    if pd.isna(present) or pd.isna(prior) or prior == 0:
        return None
    return (present - prior) / abs(prior)


def _year_from_idx(df: pd.DataFrame) -> list[str]:
    """Return fiscal-year labels from a DatetimeIndex."""
    return [str(d.year) for d in df.index]


def _hover_template_base() -> str:
    return "<b>%{x}</b><br>%{y:.2f}<extra></extra>"


# ── Page 1: Stock Price ─────────────────────────────────────────────────────

def candlestick_chart(hist: pd.DataFrame, ticker: str) -> go.Figure:
    """Candlestick with volume and 50/200-day MA."""
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
    )
    fig.add_trace(
        go.Candlestick(
            x=hist.index, open=hist["Open"], high=hist["High"],
            low=hist["Low"], close=hist["Close"],
            name="OHLC",
            increasing_line_color=UP_GREEN, decreasing_line_color=DOWN_RED,
        ), row=1, col=1,
    )
    if len(hist) >= 50:
        ma50 = hist["Close"].rolling(50).mean()
        fig.add_trace(
            go.Scatter(x=hist.index, y=ma50, name="50-day MA",
                       line=dict(color="orange", width=1.2)),
            row=1, col=1,
        )
    if len(hist) >= 200:
        ma200 = hist["Close"].rolling(200).mean()
        fig.add_trace(
            go.Scatter(x=hist.index, y=ma200, name="200-day MA",
                       line=dict(color="purple", width=1.2)),
            row=1, col=1,
        )
    colors = [UP_GREEN if v >= 0 else DOWN_RED for v in hist["Close"].diff()]
    fig.add_trace(
        go.Bar(x=hist.index, y=hist["Volume"], name="Volume",
               marker_color=colors, showlegend=False),
        row=2, col=1,
    )
    fig.update_layout(
        title=f"{ticker} — Candlestick",
        xaxis_rangeslider_visible=False,
        template=_TEMPLATE,
        height=600,
        hovermode="x unified",
        margin=dict(l=10, r=10, t=40, b=10),
        dragmode="zoom",
    )
    fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    return fig


# ── Page 2: Balance Sheet ───────────────────────────────────────────────────

def balance_stacked_bar(balance: pd.DataFrame) -> go.Figure:
    """Stacked bar: Assets, Liabilities, Equity over years."""
    df = balance.sort_index()
    fig = go.Figure()
    for col, colour in [("Total Assets", ACCENT_BLUE),
                        ("Total Liabilities", "#B71C1C"),
                        ("Total Equity", ACCENT_GREEN)]:
        if col in df.columns:
            fig.add_trace(go.Bar(
                x=[str(d.year) for d in df.index],
                y=df[col], name=col.replace("Total ", ""),
                marker_color=colour,
            ))
    fig.update_layout(
        barmode="group", template=_TEMPLATE,
        title="Assets vs Liabilities vs Equity",
        yaxis_title="Millions USD",
        height=450,
        hovermode="x unified",
    )
    return fig


# ── Page 3: Income Statement ────────────────────────────────────────────────

def income_waterfall(income: pd.DataFrame) -> go.Figure:
    """Waterfall: Revenue → COGS → Gross Profit → OpEx → Net Income."""
    row = income.iloc[0]
    labels = ["Revenue", "Cost of Revenue", "Gross Profit",
              "Operating Expenses", "Net Income"]
    vals = [
        row.get("Revenue", 0),
        -row.get("Cost of Revenue", 0),
        row.get("Gross Profit", 0),
        -row.get("Operating Expenses", 0),
        row.get("Net Income", 0),
    ]
    meas = ["relative", "relative", "total", "relative", "total"]
    fig = go.Figure(go.Waterfall(
        name="Income Statement", orientation="v",
        measure=meas,
        x=labels, y=vals,
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        decreasing={"marker": {"color": DOWN_RED}},
        increasing={"marker": {"color": UP_GREEN}},
        totals={"marker": {"color": ACCENT_BLUE}},
    ))
    fig.update_layout(
        template=_TEMPLATE,
        title=f"Income Waterfall — {str(income.index[0].year)}",
        height=450,
        hovermode="x unified",
    )
    return fig


def margins_line_chart(income: pd.DataFrame) -> go.Figure:
    """Line chart of Gross, Operating, Net, EBITDA margins over years."""
    df = income.sort_index()
    fig = go.Figure()
    margins_def = {
        "Gross Margin": ("Gross Profit", "Revenue"),
        "Operating Margin": ("Operating Income", "Revenue"),
        "Net Margin": ("Net Income", "Revenue"),
        "EBITDA Margin": ("EBITDA", "Revenue"),
    }
    for label, (num, den) in margins_def.items():
        if num in df.columns and den in df.columns:
            vals = df[num] / df[den] * 100
            fig.add_trace(go.Scatter(
                x=[str(d.year) for d in df.index],
                y=vals, name=label, mode="lines+markers",
            ))
    fig.update_layout(
        template=_TEMPLATE,
        title="Margins Over Time",
        yaxis_title="%",
        height=450,
        hovermode="x unified",
    )
    return fig


# ── Page 4: Cash Flow ───────────────────────────────────────────────────────

def cashflow_grouped_bar(cf: pd.DataFrame) -> go.Figure:
    """Grouped bar: Operating, Investing, Financing CF by year."""
    df = cf.sort_index()
    fig = go.Figure()
    cols_colours = [
        ("Operating Cash Flow", UP_GREEN),
        ("Investing Cash Flow", DOWN_RED),
        ("Financing Cash Flow", "#FFA000"),
    ]
    for col, colour in cols_colours:
        if col in df.columns:
            fig.add_trace(go.Bar(
                x=[str(d.year) for d in df.index],
                y=df[col], name=col,
                marker_color=colour,
            ))
    fig.update_layout(
        barmode="group", template=_TEMPLATE,
        title="Cash Flow by Year",
        yaxis_title="Millions USD",
        height=450,
    )
    return fig


def fcf_line_chart(cf: pd.DataFrame) -> go.Figure:
    """Free Cash Flow trend line."""
    df = cf.sort_index()
    if "Free Cash Flow" not in df.columns:
        return _empty_figure("FCF data not available")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[str(d.year) for d in df.index],
        y=df["Free Cash Flow"], name="Free Cash Flow",
        mode="lines+markers", line=dict(color=UP_GREEN, width=3),
        fill="tozeroy",
    ))
    fig.update_layout(
        template=_TEMPLATE,
        title="Free Cash Flow Trend",
        yaxis_title="Millions USD",
        height=400,
    )
    return fig


def capex_fcf_dual(cf: pd.DataFrame, income: pd.DataFrame | None = None) -> go.Figure:
    """Dual axis: CapEx bars (left) + FCF Margin % line (right)."""
    df = cf.sort_index()
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if "Capital Expenditure" in df.columns:
        fig.add_trace(
            go.Bar(x=[str(d.year) for d in df.index],
                   y=df["Capital Expenditure"],
                   name="CapEx", marker_color="#FF6D00"),
            secondary_y=False,
        )
    fcf_margin = None
    if "Free Cash Flow" in df.columns and income is not None:
        inc_sorted = income.sort_index()
        fcf_margin = df["Free Cash Flow"] / inc_sorted["Revenue"] * 100
        fig.add_trace(
            go.Scatter(x=[str(d.year) for d in df.index],
                       y=fcf_margin, name="FCF Margin %",
                       mode="lines+markers",
                       line=dict(color=ACCENT_GREEN, width=2)),
            secondary_y=True,
        )
    fig.update_layout(
        template=_TEMPLATE,
        title="CapEx & FCF Margin",
        height=400,
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="CapEx (Millions USD)", secondary_y=False)
    fig.update_yaxes(title_text="FCF Margin %", secondary_y=True)
    return fig


# ── Page 5: Comparison ──────────────────────────────────────────────────────

def comparison_grouped_bar(
    data: dict[str, pd.DataFrame], metric_col: str,
    title: str = "", suffix: str = "M"
) -> go.Figure:
    """Grouped bar comparing a metric across companies over years."""
    fig = go.Figure()
    colours = {"AMD": "#FF0000", "NVDA": "#76B900", "AAPL": "#555555"}
    for ticker, df in data.items():
        if df is None or metric_col not in df.columns:
            continue
        sdf = df.sort_index()
        fig.add_trace(go.Bar(
            x=[str(d.year) for d in sdf.index],
            y=sdf[metric_col],
            name=ticker, marker_color=colours.get(ticker, ACCENT_BLUE),
        ))
    fig.update_layout(
        barmode="group", template=_TEMPLATE,
        title=title,
        yaxis_title=f"Millions USD",
        height=450,
    )
    return fig


def comparison_margin_line(
    data: dict[str, pd.DataFrame], num_col: str, den_col: str,
    title: str = ""
) -> go.Figure:
    """Line chart comparing a margin across companies."""
    fig = go.Figure()
    colours = {"AMD": "#FF0000", "NVDA": "#76B900", "AAPL": "#555555"}
    for ticker, df in data.items():
        if df is None or num_col not in df.columns or den_col not in df.columns:
            continue
        sdf = df.sort_index()
        vals = sdf[num_col] / sdf[den_col] * 100
        fig.add_trace(go.Scatter(
            x=[str(d.year) for d in sdf.index],
            y=vals, name=ticker, mode="lines+markers",
            line=dict(color=colours.get(ticker), width=3),
        ))
    fig.update_layout(
        template=_TEMPLATE,
        title=title,
        yaxis_title="%", height=400,
    )
    return fig


def radar_comparison(
    data: dict[str, dict[str, float]],
    title: str = "Profitability Radar"
) -> go.Figure:
    """Radar chart comparing key metrics across companies.

    *data* is {ticker: {metric_name: value}}
    """
    fig = go.Figure()
    colours = {"AMD": "#FF0000", "NVDA": "#76B900", "AAPL": "#555555"}
    metrics = list(next(iter(data.values())).keys()) if data else []
    for ticker, vals in data.items():
        fig.add_trace(go.Scatterpolar(
            r=[vals.get(m, 0) for m in metrics],
            theta=metrics, fill="toself",
            name=ticker, line=dict(color=colours.get(ticker)),
        ))
    fig.update_layout(
        template=_TEMPLATE,
        title=title,
        polar=dict(
            radialaxis=dict(visible=True, tickformat=".0%"),
        ),
        height=500,
    )
    return fig


def valuation_table(
    data: dict[str, dict[str, float | str]],
    avg_data: dict[str, dict[str, float]] | None = None,
) -> go.Figure:
    """Table of valuation multiples with conditional colouring."""
    headers = ["Metric"] + list(data.keys())
    rows = []
    metrics = list(next(iter(data.values())).keys()) if data else []
    for m in metrics:
        row = [m]
        for t in data:
            row.append(data[t].get(m, "N/A"))
        rows.append(row)

    # cell colours
    cell_colours: list[list] = [["" for _ in data] for _ in metrics]
    for i, m in enumerate(metrics):
        for j, t in enumerate(data.keys()):
            v = data[t].get(m)
            if isinstance(v, (int, float)) and avg_data and t in avg_data:
                avg_v = avg_data[t].get(m)
                if avg_v and not pd.isna(avg_v):
                    cell_colours[i][j] = UP_GREEN if v < avg_v else DOWN_RED

    fig = go.Figure(data=[go.Table(
        header=dict(values=headers, fill_color=ACCENT_BLUE,
                    font=dict(color="white"), align="center"),
        cells=dict(
            values=list(zip(*rows)) if rows else [],
            fill_color=[["#2D2D2D"] * len(data) for _ in metrics],
            font=dict(color="white", size=13),
            align="center",
            format=[None] + [",.2f" if isinstance(rows[0][j+1], (int, float))
                             else None for j in range(len(data))],
        ),
    )])
    fig.update_layout(
        template=_TEMPLATE, title="Valuation Multiples",
        height=250 + 30 * len(metrics),
    )
    return fig


# ── Page 6: KPI helpers ────────────────────────────────────────────────────

def _empty_figure(msg: str = "No data") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False,
                       font=dict(size=20, color="#666"))
    fig.update_layout(template=_TEMPLATE, height=300)
    return fig
