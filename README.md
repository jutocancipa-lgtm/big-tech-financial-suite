# Three-Statement Financial Model — AMD, NVIDIA & Apple

A Python tool that downloads real financial data from **Yahoo Finance** (via `yfinance`) for AMD, NVIDIA, and Apple, then builds a three-statement model (Income Statement, Balance Sheet, Cash Flow Statement) plus key financial ratios.

All monetary values are in **millions of USD**.

---

## Project Structure

```
financial-model/
├── app.py               # Streamlit dashboard — run with `streamlit run app.py`
├── main.py              # CLI pipeline — run with `python main.py`
├── requirements.txt     # Pinned dependencies
├── README.md            # This file
├── data/                # Exported Excel files (auto-created)
│   ├── AMD_financial_model.xlsx
│   ├── NVDA_financial_model.xlsx
│   ├── AAPL_financial_model.xlsx
│   └── summary_comparison.xlsx
├── powerbi/             # Power BI integration
│   ├── README.md        # Power BI setup guide
│   └── data/            # Star-schema CSV files (auto-created)
│       ├── dim_ticker.csv
│       ├── dim_date.csv
│       ├── fact_financials.csv
│       └── fact_ratios.csv
└── src/
    ├── __init__.py
    ├── charts.py        # Plotly chart functions for Streamlit
    ├── fetcher.py       # Downloads data from Yahoo Finance
    ├── cleaner.py       # Standardises & cleans raw data
    ├── ratios.py        # Computes financial ratios
    ├── exporter.py      # Writes everything to Excel files
    └── powerbi.py       # Exports Power BI-ready star-schema CSVs
```

## Setup Instructions

### 1. Clone / copy the project

```bash
cd financial-model
```

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate      # Linux / macOS
# venv\Scripts\activate       # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the CLI pipeline

```bash
python main.py
```

The script will:
- Fetch the latest 4 years of annual financial data for **AMD**, **NVDA**, and **AAPL**.
- Clean and standardise all line items.
- Compute **Profitability**, **Liquidity**, **Leverage**, and **Efficiency** ratios.
- Export one Excel file per ticker to the `data/` folder.
- Build a `summary_comparison.xlsx` with side-by-side key metrics.
- Export star-schema CSV files to `powerbi/data/` for **Power BI Desktop**.

### 5. Launch the Streamlit dashboard

```bash
streamlit run app.py
```

Opens an interactive web dashboard with 6 pages:

| Page | Description |
|------|-------------|
| 📈 Stock Price | Candlestick chart + volume + MA50/200 + period selector |
| 📋 Balance Sheet | Cards with expandable breakdowns + stacked bar chart |
| 💰 Income Statement | Expandable sections + waterfall + margins line chart |
| 💵 Cash Flow | CF cards + grouped bar + FCF trend + dual-axis chart |
| ⚖️ Comparison | All 3 companies side-by-side: revenue, margins, radar, valuations |
| 🎯 KPI Dashboard | Real-time metrics with auto-refresh every 5 min |

## Error Handling

- If a ticker's data cannot be fetched (network issue, invalid symbol), the script logs a warning and continues with the remaining tickers.
- Missing line items are filled with `NaN` rather than crashing.

## Output Files

Each ticker's Excel file contains these sheets:

| Sheet | Contents |
|---|---|
| Income Statement | Revenue, COGS, Gross Profit, Operating Expenses, Net Income, EPS, etc. |
| Balance Sheet | Assets, Liabilities, Equity, Cash, Debt, etc. |
| Cash Flow Statement | Operating / Investing / Financing Cash Flows, Free Cash Flow, etc. |
| Profitability Ratios | Net Margin, Gross Margin, ROE, ROA, etc. |
| Liquidity Ratios | Current Ratio, Quick Ratio, Cash Ratio |
| Leverage Ratios | Debt-to-Equity, Debt Ratio, Equity Ratio |
| Efficiency Ratios | Asset Turnover |

The **summary comparison** file collates the latest year's key metrics for all three companies in one table.

---

*Built with `yfinance`, `pandas`, `openpyxl`, `requests`, `streamlit`, and `plotly`.*
