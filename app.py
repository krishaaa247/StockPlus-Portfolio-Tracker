import logging
import html
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import numpy as np
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional

try:
    from google import genai
    from google.genai import errors as genai_errors
except Exception:  # pragma: no cover - AI remains disabled if the SDK is unavailable
    genai = None
    genai_errors = None


logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# ─── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="StockPulse Portfolio Tracker",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Dark theme base */
    .stApp {
        background-color: #0d1117;
        color: #e6edf3;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #21262d;
    }

    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #161b22 0%, #1c2333 100%);
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 16px;
    }
    .metric-label {
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        color: #8b949e;
        margin-bottom: 6px;
    }
    .metric-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 28px;
        font-weight: 600;
        color: #e6edf3;
        line-height: 1;
    }
    .metric-delta-pos {
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
        color: #3fb950;
        margin-top: 4px;
    }
    .metric-delta-neg {
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
        color: #f85149;
        margin-top: 4px;
    }

    /* Table */
    .stock-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
    }
    .stock-table th {
        background-color: #161b22;
        color: #8b949e;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1px;
        text-transform: uppercase;
        padding: 12px 16px;
        border-bottom: 1px solid #21262d;
        text-align: left;
    }
    .stock-table td {
        padding: 14px 16px;
        border-bottom: 1px solid #21262d;
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
        color: #c9d1d9;
    }
    .stock-table tr:hover td {
        background-color: #1c2333;
    }
    .profit { color: #3fb950; font-weight: 600; }
    .loss   { color: #f85149; font-weight: 600; }

    /* Section headers */
    .section-title {
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: #58a6ff;
        border-left: 3px solid #58a6ff;
        padding-left: 10px;
        margin: 24px 0 16px 0;
    }

    /* App header */
    .app-header {
        display: flex;
        align-items: baseline;
        gap: 10px;
        margin-bottom: 4px;
    }
    .app-title {
        font-size: 26px;
        font-weight: 700;
        color: #e6edf3;
        letter-spacing: -0.5px;
    }
    .app-badge {
        background: #1f6feb;
        color: #cae8ff;
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.8px;
        padding: 2px 8px;
        border-radius: 20px;
        text-transform: uppercase;
    }
    .app-subtitle {
        font-size: 13px;
        color: #8b949e;
        margin-bottom: 24px;
    }

    /* Buttons */
    .stButton > button {
        background: #238636;
        color: white;
        border: none;
        border-radius: 6px;
        font-weight: 600;
        font-size: 13px;
        padding: 8px 16px;
        transition: background 0.15s;
    }
    .stButton > button:hover {
        background: #2ea043;
    }

    /* Inputs */
    .stTextInput > div > input,
    .stNumberInput > div > input {
        background-color: #0d1117;
        border: 1px solid #30363d;
        border-radius: 6px;
        color: #e6edf3;
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #0d1117;
        border-bottom: 1px solid #21262d;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        color: #8b949e;
        border: none;
        font-size: 13px;
        font-weight: 500;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        color: #e6edf3;
        border-bottom: 2px solid #58a6ff;
    }

    /* Remove Streamlit branding */
    #MainMenu, footer, header { visibility: hidden; }

    /* Divider */
    hr { border-color: #21262d; }

    /* Select/spinner */
    .stSelectbox > div,
    .stSpinner { color: #8b949e; }

    /* AI chat */
    .chat-row {
        display: flex;
        margin: 10px 0;
        width: 100%;
    }
    .chat-row.user { justify-content: flex-end; }
    .chat-row.assistant { justify-content: flex-start; }
    .chat-bubble {
        max-width: 82%;
        padding: 14px 16px;
        border-radius: 16px;
        border: 1px solid #30363d;
        white-space: pre-wrap;
        word-wrap: break-word;
        line-height: 1.55;
    }
    .chat-bubble.user {
        background: linear-gradient(135deg, #1f6feb 0%, #2ea043 100%);
        color: #f0f6fc;
        border-bottom-right-radius: 6px;
    }
    .chat-bubble.assistant {
        background: #161b22;
        color: #e6edf3;
        border-bottom-left-radius: 6px;
    }
    .chat-role {
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        color: #8b949e;
        margin-bottom: 6px;
    }

    .status-card {
        background: linear-gradient(135deg, #161b22 0%, #0f172a 100%);
        border: 1px solid #30363d;
        border-radius: 16px;
        padding: 18px 20px;
        margin: 12px 0 18px 0;
    }
    .status-card h4 {
        margin: 0 0 6px 0;
        color: #e6edf3;
        font-size: 16px;
    }
    .status-card p {
        margin: 0;
        color: #8b949e;
        font-size: 13px;
        line-height: 1.5;
    }
</style>
""", unsafe_allow_html=True)


# ─── Session State ──────────────────────────────────────────────────────────────
if "portfolio" not in st.session_state:
    st.session_state.portfolio = []   # list of dicts: {symbol, qty, buy_price}

if "prices_cache" not in st.session_state:
    st.session_state.prices_cache = {}

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "current_symbol" not in st.session_state:
    st.session_state.current_symbol = ""

if "stock_context" not in st.session_state:
    st.session_state.stock_context = ""

if "ai_available" not in st.session_state:
    st.session_state.ai_available = False

if "last_updated" not in st.session_state:
    st.session_state.last_updated = None


# ─── Helper Functions ───────────────────────────────────────────────────────────
@st.cache_data(ttl=300)   # cache 5 minutes
def fetch_current_price(symbol: str):
    snapshot = fetch_yfinance_snapshot(symbol)
    price = snapshot.get("current_price")
    return None if price is None or pd.isna(price) else round(float(price), 2)


def _extract_history_close(ticker, period: str):
    data = ticker.history(period=period, auto_adjust=False)
    if data is None or data.empty or "Close" not in data.columns:
        return None
    close_series = pd.to_numeric(data["Close"], errors="coerce").dropna()
    if close_series.empty:
        return None
    return close_series


def _extract_history_frame(ticker, period: str):
    try:
        data = ticker.history(period=period, auto_adjust=False)
        if data is None or data.empty:
            return None
        data = data.reset_index()
        if "Date" in data.columns:
            data["Date"] = pd.to_datetime(data["Date"]).dt.tz_localize(None)
        return data
    except Exception as exc:
        logger.info("yfinance history frame failed: %s", exc)
        return None


def _safe_get_ticker_info(ticker):
    for method_name in ("get_info", "info"):
        try:
            method = getattr(ticker, method_name, None)
            info = method() if callable(method) else method
            if isinstance(info, dict) and info:
                return info
        except Exception as exc:
            logger.info("yfinance %s failed: %s", method_name, exc)
    return {}


def _safe_get_fast_info(ticker):
    try:
        fast_info = getattr(ticker, "fast_info", None)
        if fast_info is None:
            return {}
        if isinstance(fast_info, dict):
            return fast_info
        return dict(fast_info)
    except Exception as exc:
        logger.info("yfinance fast_info failed: %s", exc)
        return None


@st.cache_data(ttl=3600)
def fetch_history(symbol: str, period: str = "6mo"):
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period, auto_adjust=False)
        if data.empty:
            return None
        data = data.reset_index()
        data["Date"] = pd.to_datetime(data["Date"]).dt.tz_localize(None)

        # Coerce the close column so empty strings / invalid values do not leak into charts.
        data["Close"] = pd.to_numeric(data["Close"], errors="coerce")
        data = data.dropna(subset=["Close"])
        if data.empty:
            return None

        return data[["Date", "Close"]]
    except Exception as exc:
        logger.info("fetch_history failed for %s: %s", symbol, exc)
        return None


@st.cache_data(ttl=3600)
def fetch_benchmark(symbol: str, period: str = "6mo"):
    return fetch_history(symbol, period)


@st.cache_data(ttl=600)
def fetch_yfinance_snapshot(symbol: str):
    snapshot = {
        "symbol": symbol,
        "current_price": None,
        "one_week_change": None,
        "one_month_change": None,
        "fifty_two_week_high": None,
        "fifty_two_week_low": None,
        "pe_ratio": None,
        "beta": None,
        "market_cap": None,
        "sector": None,
        "sma_7": None,
        "sma_20": None,
        "rsi_14": None,
        "macd": None,
        "macd_signal": None,
        "macd_histogram": None,
        "latest_volume": None,
        "average_volume": None,
        "volume_trend": None,
        "market_trend": None,
        "closing_prices": [],
        "last_updated": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "data_source": None,
        "available": False,
    }

    def _build_from_history(close_series: pd.Series):
        if close_series is None or close_series.empty:
            return

        snapshot["closing_prices"] = [round(float(value), 2) for value in close_series.tail(30).tolist()]
        snapshot["current_price"] = round(float(close_series.iloc[-1]), 2)

        if len(close_series) >= 6 and close_series.iloc[-6] not in [0, None]:
            snapshot["one_week_change"] = round(((close_series.iloc[-1] - close_series.iloc[-6]) / close_series.iloc[-6]) * 100, 2)
        if len(close_series) >= 22 and close_series.iloc[-22] not in [0, None]:
            snapshot["one_month_change"] = round(((close_series.iloc[-1] - close_series.iloc[-22]) / close_series.iloc[-22]) * 100, 2)

        snapshot["fifty_two_week_high"] = round(float(close_series.max()), 2)
        snapshot["fifty_two_week_low"] = round(float(close_series.min()), 2)
        snapshot["sma_7"] = round(float(close_series.tail(7).mean()), 2) if len(close_series) >= 7 else None
        snapshot["sma_20"] = round(float(close_series.tail(20).mean()), 2) if len(close_series) >= 20 else None
        snapshot["rsi_14"] = compute_rsi(close_series, 14)
        macd_line, signal_line, histogram = compute_macd(close_series)
        snapshot["macd"] = macd_line
        snapshot["macd_signal"] = signal_line
        snapshot["macd_histogram"] = histogram
        snapshot["available"] = True

    def _merge_fundamentals(info: dict, fast_info: dict):
        candidates = {
            "pe_ratio": [info.get("trailingPE"), info.get("forwardPE")],
            "beta": [info.get("beta"), fast_info.get("beta")],
            "market_cap": [info.get("marketCap"), fast_info.get("marketCap")],
            "sector": [info.get("sector")],
        }

        for key, values in candidates.items():
            for value in values:
                if value is None or pd.isna(value):
                    continue
                if key in {"pe_ratio", "beta"}:
                    try:
                        snapshot[key] = round(float(value), 2)
                    except (TypeError, ValueError):
                        continue
                elif key == "market_cap":
                    snapshot[key] = format_market_cap(value)
                else:
                    snapshot[key] = str(value)
                break

    try:
        ticker = yf.Ticker(symbol)
        close_series = None
        for period in ("1y", "6mo", "3mo"):
            try:
                close_series = _extract_history_close(ticker, period)
                if close_series is not None and not close_series.empty:
                    _build_from_history(close_series)
                    break
            except Exception as exc:
                logger.info("history fetch failed for %s (%s): %s", symbol, period, exc)

        if close_series is None or close_series.empty:
            fast_info = _safe_get_fast_info(ticker) or {}
            last_price = fast_info.get("lastPrice") or fast_info.get("last_price") or fast_info.get("regularMarketPrice")
            if last_price is not None and not pd.isna(last_price):
                snapshot["current_price"] = round(float(last_price), 2)
                snapshot["available"] = True
            info = _safe_get_ticker_info(ticker)
            _merge_fundamentals(info, fast_info)
        else:
            info = _safe_get_ticker_info(ticker)
            fast_info = _safe_get_fast_info(ticker) or {}
            _merge_fundamentals(info, fast_info)

        if snapshot["current_price"] is None:
            fallback_price = (fast_info.get("lastPrice") if "fast_info" in locals() else None) or info.get("currentPrice") or info.get("regularMarketPrice")
            if fallback_price is not None and not pd.isna(fallback_price):
                snapshot["current_price"] = round(float(fallback_price), 2)

        if snapshot["rsi_14"] is not None:
            if snapshot["rsi_14"] < 30:
                snapshot["rsi_signal"] = "Oversold (bullish signal)"
            elif snapshot["rsi_14"] > 70:
                snapshot["rsi_signal"] = "Overbought (bearish signal)"
            else:
                snapshot["rsi_signal"] = "Neutral"

        if snapshot["sma_7"] is not None and snapshot["sma_20"] is not None:
            snapshot["sma_signal"] = "Bullish" if snapshot["sma_7"] > snapshot["sma_20"] else "Bearish" if snapshot["sma_7"] < snapshot["sma_20"] else "Neutral"
            snapshot["market_trend"] = snapshot["sma_signal"]

        history_frame = _extract_history_frame(ticker, "3mo")
        if history_frame is not None and "Volume" in history_frame.columns:
            volume_series = pd.to_numeric(history_frame["Volume"], errors="coerce").dropna()
            if not volume_series.empty:
                snapshot["latest_volume"] = int(volume_series.iloc[-1])
                avg_volume = volume_series.tail(20).mean()
                if not pd.isna(avg_volume):
                    snapshot["average_volume"] = int(avg_volume)
                    if avg_volume > 0:
                        ratio = snapshot["latest_volume"] / avg_volume
                        if ratio >= 1.2:
                            snapshot["volume_trend"] = "Above average"
                        elif ratio <= 0.8:
                            snapshot["volume_trend"] = "Below average"
                        else:
                            snapshot["volume_trend"] = "Near average"

        return snapshot
    except Exception as exc:
        logger.exception("fetch_yfinance_snapshot failed for %s", symbol)
        snapshot["error"] = str(exc)
        return snapshot


def build_portfolio_df():
    rows = []
    for stock in st.session_state.portfolio:
        sym = stock["symbol"]
        qty = pd.to_numeric(stock.get("qty", 0), errors="coerce")
        buy_price = pd.to_numeric(stock.get("buy_price", 0), errors="coerce")
        cur_price = fetch_current_price(sym)
        if cur_price is None:
            cur_price = buy_price   # fallback to the purchase price when live data is unavailable

        # Ensure the core calculations are always numeric and never propagate NaN.
        qty = 0 if pd.isna(qty) else float(qty)
        buy_price = 0 if pd.isna(buy_price) else float(buy_price)
        cur_price = buy_price if cur_price is None or pd.isna(cur_price) else float(cur_price)

        invested = round(qty * buy_price, 2)
        cur_value = round(qty * cur_price, 2)
        pnl_amt = round(cur_value - invested, 2)
        pnl_pct = round((pnl_amt / invested) * 100, 2) if invested else 0.0

        rows.append({
            "Symbol": sym,
            "Quantity": qty,
            "Buy Price": buy_price,
            "Current Price": cur_price,
            "Invested Amount": invested,
            "Current Value": cur_value,
            "P&L": pnl_amt,
            "P&L (%)": pnl_pct,
        })

    df = pd.DataFrame(rows)

    # Keep backwards-compatible aliases so the rest of the dashboard still works.
    if not df.empty:
        df["Qty"] = df["Quantity"]
        df["Invested (₹)"] = df["Invested Amount"]
        df["Value (₹)"] = df["Current Value"]
        df["P&L (₹)"] = df["P&L"]

    return df


def fmt_inr(val):
    if pd.isna(val):
        return "N/A"
    return f"₹{val:,.2f}"


def fmt_pct(val):
    if pd.isna(val):
        return "N/A"
    arrow = "▲" if val >= 0 else "▼"
    return f"{arrow} {abs(val):.2f}%"


def fmt_value(val, prefix=""):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "N/A"
    if isinstance(val, (int, float, np.number)):
        return f"{prefix}{val:,.2f}" if isinstance(val, float) else f"{prefix}{val}"
    return f"{prefix}{val}"


def render_metric_card(label: str, value: str, icon: str, tone: str = "default"):
    tone_style = ""
    if tone == "positive":
        tone_style = "border-color:#238636;"
    elif tone == "negative":
        tone_style = "border-color:#f85149;"
    elif tone == "info":
        tone_style = "border-color:#1f6feb;"

    st.markdown(
        f"""
        <div class='metric-card' style='{tone_style}'>
            <div class='metric-label'>{icon} {html.escape(label)}</div>
            <div class='metric-value' style='font-size:22px;'>{html.escape(value)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_extreme_pnl_stock(dataframe: pd.DataFrame, column: str, extreme: str):
    """Return the row with the highest or lowest valid P&L (%) value.

    This helper safely handles empty dataframes, missing columns, and rows with
    non-numeric values by coercing invalid values to NaN before selection.
    """
    if dataframe.empty:
        return None, "Your portfolio is empty. Add stocks to see performance summaries."

    if column not in dataframe.columns:
        return None, f"The expected column '{column}' is missing, so performance summaries cannot be calculated."

    # Coerce the column to numeric so values like "", "N/A", "-", or text become NaN.
    pnl_series = pd.to_numeric(dataframe[column], errors="coerce")
    valid_mask = pnl_series.notna()

    if not valid_mask.any():
        return None, f"No valid numeric values were found in '{column}', so best/worst performer cards cannot be calculated."

    valid_df = dataframe.loc[valid_mask].copy()
    valid_df[column] = pnl_series.loc[valid_mask]

    # Choose the extreme only after confirming there is at least one valid value.
    if extreme == "max":
        idx = valid_df[column].idxmax()
    elif extreme == "min":
        idx = valid_df[column].idxmin()
    else:
        raise ValueError("extreme must be 'max' or 'min'")

    return valid_df.loc[idx], None


def compute_rsi(close_series: pd.Series, period: int = 14):
    if close_series is None:
        return None

    numeric_series = pd.to_numeric(close_series, errors="coerce").dropna()
    if numeric_series.size <= period:
        return None

    deltas = numeric_series.diff().dropna()
    if deltas.empty:
        return None

    gains = deltas.clip(lower=0)
    losses = -deltas.clip(upper=0)

    avg_gain = gains.tail(period).mean()
    avg_loss = losses.tail(period).mean()

    if pd.isna(avg_gain) or pd.isna(avg_loss):
        return None

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi), 2)


def compute_macd(close_series: pd.Series):
    if close_series is None:
        return None, None, None

    numeric_series = pd.to_numeric(close_series, errors="coerce").dropna()
    if numeric_series.size < 35:
        return None, None, None

    ema_12 = numeric_series.ewm(span=12, adjust=False).mean()
    ema_26 = numeric_series.ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line

    return round(float(macd_line.iloc[-1]), 2), round(float(signal_line.iloc[-1]), 2), round(float(histogram.iloc[-1]), 2)


def format_market_cap(value):
    if value is None or pd.isna(value):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    absolute_value = abs(value)
    for divisor, suffix in [(1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if absolute_value >= divisor:
            return f"${value / divisor:.2f}{suffix}"
    return f"${value:,.0f}"


def build_ai_prompt(symbol: str, stock_context: str, chat_history: list[dict], user_message: str):
    chat_summary = "\n".join(f"{item.get('role', 'user')}: {item.get('content', '')}" for item in chat_history[-6:])
    return f"""You are a concise financial assistant helping a retail investor analyze {symbol}.

Use only the provided data. If data is missing, say so briefly instead of inventing it.
Do not promise guaranteed returns or present educational analysis as personalized investment advice.

Data:
{stock_context}

Recent chat:
{chat_summary if chat_summary else 'None'}

The user asked:
{user_message}

Respond with:
📈 Trend
⚠ Risks
✅ Recommendation
❗ Disclaimer

Keep the response concise, practical, and grounded in the data. If the user asks whether to buy, include current price, RSI, moving averages, MACD, volume, portfolio allocation, profit/loss, and market trend when available.
"""


def build_stock_context(snapshot: dict, portfolio_row: Optional[dict] = None, portfolio_totals: Optional[dict] = None):
    context_lines = [f"Symbol: {snapshot['symbol']}"]

    if snapshot.get("current_price") is not None:
        context_lines.append(f"Current price: ₹{snapshot['current_price']:.2f}")
    if snapshot.get("one_week_change") is not None:
        context_lines.append(f"1-week % change: {snapshot['one_week_change']:.2f}%")
    if snapshot.get("one_month_change") is not None:
        context_lines.append(f"1-month % change: {snapshot['one_month_change']:.2f}%")
    if snapshot.get("fifty_two_week_high") is not None:
        context_lines.append(f"52-week high: ₹{snapshot['fifty_two_week_high']:.2f}")
    if snapshot.get("fifty_two_week_low") is not None:
        context_lines.append(f"52-week low: ₹{snapshot['fifty_two_week_low']:.2f}")
    if snapshot.get("pe_ratio") is not None:
        context_lines.append(f"P/E ratio: {snapshot['pe_ratio']:.2f}")
    if snapshot.get("beta") is not None:
        context_lines.append(f"Beta: {snapshot['beta']:.2f}")
    if snapshot.get("market_cap"):
        context_lines.append(f"Market cap: {snapshot['market_cap']}")
    if snapshot.get("sector"):
        context_lines.append(f"Sector: {snapshot['sector']}")
    if snapshot.get("sma_7") is not None:
        context_lines.append(f"7-day SMA: ₹{snapshot['sma_7']:.2f}")
    if snapshot.get("sma_20") is not None:
        context_lines.append(f"20-day SMA: ₹{snapshot['sma_20']:.2f}")
    if snapshot.get("sma_signal"):
        context_lines.append(f"SMA crossover signal: {snapshot['sma_signal']}")
    if snapshot.get("rsi_14") is not None:
        context_lines.append(f"14-day RSI: {snapshot['rsi_14']:.2f}")
    if snapshot.get("rsi_signal"):
        context_lines.append(f"RSI signal: {snapshot['rsi_signal']}")
    if snapshot.get("macd") is not None:
        context_lines.append(f"MACD: {snapshot['macd']:.2f}")
    if snapshot.get("macd_signal") is not None:
        context_lines.append(f"MACD signal: {snapshot['macd_signal']:.2f}")
    if snapshot.get("macd_histogram") is not None:
        context_lines.append(f"MACD histogram: {snapshot['macd_histogram']:.2f}")
    if snapshot.get("latest_volume") is not None:
        context_lines.append(f"Latest volume: {snapshot['latest_volume']:,}")
    if snapshot.get("average_volume") is not None:
        context_lines.append(f"20-day average volume: {snapshot['average_volume']:,}")
    if snapshot.get("volume_trend"):
        context_lines.append(f"Volume trend: {snapshot['volume_trend']}")
    if snapshot.get("market_trend"):
        context_lines.append(f"Market trend from moving averages: {snapshot['market_trend']}")
    if portfolio_row:
        context_lines.append(f"Portfolio quantity: {portfolio_row.get('Quantity', 'N/A')}")
        context_lines.append(f"Portfolio buy price: ₹{portfolio_row.get('Buy Price', 0):,.2f}")
        context_lines.append(f"Portfolio current value: ₹{portfolio_row.get('Current Value', 0):,.2f}")
        context_lines.append(f"Portfolio profit/loss: ₹{portfolio_row.get('P&L', 0):,.2f} ({portfolio_row.get('P&L (%)', 0):.2f}%)")
    if portfolio_totals and portfolio_row:
        total_value = portfolio_totals.get("total_value", 0)
        current_value = portfolio_row.get("Current Value", 0)
        allocation = (current_value / total_value) * 100 if total_value else 0
        context_lines.append(f"Portfolio allocation: {allocation:.2f}%")
    if snapshot.get("closing_prices"):
        context_lines.append(f"Last 30 closing prices: {snapshot['closing_prices']}")

    return "\n".join(context_lines)


def get_gemini_api_key():
    try:
        key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        key = ""

    key = str(key).strip() if key is not None else ""
    if key.lower() in {"", "your-key-here", "changeme", "replace-me"}:
        return ""
    return key


def ai_is_available():
    return bool(get_gemini_api_key()) and genai is not None


@st.cache_resource(ttl=600)
def get_ai_client_cached(api_key: str):
    if not api_key or genai is None:
        return None

    try:
        return genai.Client(api_key=api_key)
    except Exception:
        logger.exception("Failed to initialize Gemini client")
        return None


def get_gemini_client():
    api_key = get_gemini_api_key()
    if not api_key:
        return None

    return get_ai_client_cached(api_key)


def _extract_gemini_text(response):
    text = getattr(response, "text", None)
    if text:
        return str(text).strip()

    parts = []
    candidates = getattr(response, "candidates", []) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                parts.append(str(part_text))
    return "\n".join(parts).strip()


def _gemini_api_error_types():
    if genai_errors is None:
        return ()

    names = ("APIError", "ClientError", "ServerError")
    return tuple(error_type for error_type in (getattr(genai_errors, name, None) for name in names) if isinstance(error_type, type))


def generate_ai_response(prompt: str):
    client = get_gemini_client()
    if client is None:
        return None

    def _request():
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return _extract_gemini_text(response)

    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(_request)
        text = future.result(timeout=25)
        return text or None
    except _gemini_api_error_types():
        logger.warning("Gemini API, quota, or rate-limit error")
        return None
    except (FuturesTimeoutError, TimeoutError, ConnectionError):
        logger.warning("Gemini request timed out or connection failed")
        return None
    except Exception:
        logger.exception("Gemini API request failed")
        return None
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def fetch_ai_stock_snapshot(symbol: str):
    return fetch_yfinance_snapshot(symbol)


def render_chat_message(role: str, content: str):
    bubble_role = "user" if role == "user" else "assistant"
    safe_content = html.escape(content).replace("\n", "<br>")
    role_label = "You" if role == "user" else "AI Analyst"
    st.markdown(
        f"""
        <div class='chat-row {bubble_role}'>
            <div class='chat-bubble {bubble_role}'>
                <div class='chat-role'>{role_label}</div>
                {safe_content}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_card(title: str, body: str):
    st.markdown(
        f"""
        <div class='status-card'>
            <h4>{html.escape(title)}</h4>
            <p>{html.escape(body)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_ai_placeholder():
    st.info("AI Analyst is currently unavailable because the Gemini API key has not been configured.")


def submit_ai_message(symbol: str, message: str):
    if not ai_is_available():
        return

    stock_context = st.session_state.stock_context
    if not stock_context:
        return

    st.session_state.chat_history.append({"role": "user", "content": message})

    prompt = build_ai_prompt(symbol, stock_context, st.session_state.chat_history[:-1], message)
    with st.spinner("Gemini AI is generating a response..."):
        reply = generate_ai_response(prompt)
    if reply is None:
        st.session_state.chat_history.append({"role": "assistant", "content": "AI service is temporarily unavailable. Please try again later."})
    else:
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
    st.rerun()


# ─── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class='app-header'>
        <span class='app-title'>StockPulse</span>
        <span class='app-badge'>LIVE</span>
    </div>
    <div class='app-subtitle'>Personal Portfolio Tracker</div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='section-title'>Add Stock</div>", unsafe_allow_html=True)

    with st.container():
        symbol_input = st.text_input(
            "Ticker Symbol",
            placeholder="e.g. RELIANCE.NS or AAPL",
            help="Use .NS suffix for NSE stocks (e.g. TCS.NS, INFY.NS)"
        ).strip().upper()

        col1, col2 = st.columns(2)
        with col1:
            qty_input = st.number_input("Quantity", min_value=1, value=1, step=1)
        with col2:
            buy_price_input = st.number_input("Buy Price (₹)", min_value=0.01, value=100.0, step=0.5)

        add_btn = st.button("＋ Add to Portfolio", use_container_width=True)

        if add_btn:
            if not symbol_input:
                st.info("Enter a ticker symbol to add a stock.")
            else:
                # Check if valid
                with st.spinner(f"Verifying {symbol_input}…"):
                    price = fetch_current_price(symbol_input)
                if price is None:
                    st.info(f"{symbol_input} could not be validated. Check the symbol and try again.")
                else:
                    # Check duplicate
                    existing = [s for s in st.session_state.portfolio if s["symbol"] == symbol_input]
                    if existing:
                        st.info(f"{symbol_input} is already in your portfolio.")
                    else:
                        st.session_state.portfolio.append({
                            "symbol":    symbol_input,
                            "qty":       qty_input,
                            "buy_price": buy_price_input,
                        })
                        st.success(f"Added **{symbol_input}** @ ₹{buy_price_input}")
                        st.rerun()

    # Current holdings list
    if st.session_state.portfolio:
        st.markdown("<div class='section-title'>Holdings</div>", unsafe_allow_html=True)
        for i, stock in enumerate(st.session_state.portfolio):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"<span style='font-family:JetBrains Mono,monospace;font-size:13px;color:#c9d1d9;'>{stock['symbol']}</span> <span style='font-size:11px;color:#8b949e;'>×{stock['qty']}</span>", unsafe_allow_html=True)
            with col2:
                if st.button("✕", key=f"remove_{i}", help=f"Remove {stock['symbol']}"):
                    st.session_state.portfolio.pop(i)
                    st.rerun()

    st.markdown("---")
    # Quick sample portfolio
    if st.button("📋 Load Sample Portfolio", use_container_width=True):
        st.session_state.portfolio = [
            {"symbol": "RELIANCE.NS", "qty": 10,  "buy_price": 2400.0},
            {"symbol": "TCS.NS",      "qty": 5,   "buy_price": 3500.0},
            {"symbol": "INFY.NS",     "qty": 20,  "buy_price": 1450.0},
            {"symbol": "HDFCBANK.NS", "qty": 15,  "buy_price": 1600.0},
            {"symbol": "ITC.NS",      "qty": 50,  "buy_price": 420.0},
        ]
        st.rerun()

    if st.button("🗑️ Clear Portfolio", use_container_width=True):
        st.session_state.portfolio = []
        st.rerun()


# ─── Main Area ──────────────────────────────────────────────────────────────────
if not st.session_state.portfolio:
    st.markdown("""
    <div style='text-align:center; padding: 80px 20px; color:#8b949e;'>
        <div style='font-size:48px; margin-bottom:16px;'>📊</div>
        <div style='font-size:20px; font-weight:600; color:#c9d1d9; margin-bottom:8px;'>No stocks yet</div>
        <div style='font-size:14px;'>Add stocks from the sidebar, or load the sample portfolio to get started.</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# Build dataframe
with st.spinner("Fetching live prices…"):
    df = build_portfolio_df()

with st.expander("Debug portfolio calculations", expanded=False):
    st.write(df.head())
    st.write(df.dtypes)
    debug_cols = [col for col in ["Current Price", "Current Value", "P&L", "P&L (%)"] if col in df.columns]
    if debug_cols:
        st.write(df[debug_cols])
        st.write(df[debug_cols].isna().sum())
    else:
        st.info("Portfolio data is available, but some debug fields are not present in this session.")

# ─── Summary Metrics ────────────────────────────────────────────────────────────
total_invested = pd.to_numeric(df.get("Invested Amount", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
total_value    = pd.to_numeric(df.get("Current Value", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
total_pnl      = pd.to_numeric(df.get("P&L", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
total_pnl_pct  = round((total_pnl / total_invested) * 100, 2) if total_invested else 0

# Ensure the performance column is numeric before any max/min calculations.
# Invalid values such as "", "N/A", "-", or text are converted to NaN and ignored safely.
if "P&L (%)" in df.columns:
    df["P&L (%)"] = pd.to_numeric(df["P&L (%)"], errors="coerce")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    render_metric_card("Portfolio Value", fmt_inr(total_value), "💼", "info")

with col2:
    render_metric_card("Amount Invested", fmt_inr(total_invested), "📌", "info")

with col3:
    pnl_class = "metric-delta-pos" if total_pnl >= 0 else "metric-delta-neg"
    pnl_sign  = "+" if total_pnl >= 0 else ""
    st.markdown(f"""
    <div class='metric-card' style='border-color:{'#238636' if total_pnl >= 0 else '#f85149'};'>
        <div class='metric-label'>📈 Total P&L</div>
        <div class='metric-value'>{pnl_sign}{fmt_inr(total_pnl)}</div>
        <div class='{pnl_class}'>{fmt_pct(total_pnl_pct)}</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    best_stock, best_error = get_extreme_pnl_stock(df, "P&L (%)", "max")
    if best_stock is not None:
        render_metric_card("Best Performer", f"{best_stock['Symbol']}  ▲ {best_stock['P&L (%)']:.2f}%", "🏆", "positive")
    else:
        render_metric_card("Best Performer", "N/A", "🏆")

with col5:
    worst_stock, worst_error = get_extreme_pnl_stock(df, "P&L (%)", "min")
    if worst_stock is not None:
        render_metric_card("Worst Performer", f"{worst_stock['Symbol']}  ▼ {abs(worst_stock['P&L (%)']):.2f}%", "⚠️", "negative")
    else:
        render_metric_card("Worst Performer", "N/A", "⚠️")


# ─── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Stock Details", "Benchmark", "🤖 AI Analyst"])

CHART_LAYOUT = dict(
    paper_bgcolor="#0d1117",
    plot_bgcolor="#0d1117",
    font=dict(family="Inter, sans-serif", color="#8b949e", size=12),
    margin=dict(l=0, r=0, t=30, b=0),
    legend=dict(bgcolor="#161b22", bordercolor="#30363d", borderwidth=1),
)


# ─── TAB 1: Overview ────────────────────────────────────────────────────────────
with tab1:
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("<div class='section-title'>Allocation</div>", unsafe_allow_html=True)
        pie = px.pie(
            df,
            names="Symbol",
            values="Current Value",
            hole=0.55,
            color_discrete_sequence=["#58a6ff","#3fb950","#d2a8ff","#ffa657","#f85149","#79c0ff","#56d364"],
        )
        pie.update_traces(textinfo="percent+label", textfont_size=12)
        pie.update_layout(
            showlegend=True,
            **CHART_LAYOUT
        )
        st.plotly_chart(pie, use_container_width=True, config={"displayModeBar": False})

    with col_right:
        st.markdown("<div class='section-title'>P&L per Stock</div>", unsafe_allow_html=True)
        bar_colors = ["#3fb950" if v >= 0 else "#f85149" for v in df["P&L"]]
        bar = go.Figure(go.Bar(
            x=df["Symbol"],
            y=df["P&L"],
            marker_color=bar_colors,
            text=[f"{'+'if v>=0 else ''}{v:,.0f}" for v in df["P&L"]],
            textposition="outside",
            textfont=dict(size=11, color="#e6edf3"),
        ))
        bar.update_layout(
            xaxis=dict(showgrid=False, color="#8b949e", tickfont=dict(size=12)),
            yaxis=dict(showgrid=True, gridcolor="#21262d", color="#8b949e", tickprefix="₹"),
            **CHART_LAYOUT
        )
        st.plotly_chart(bar, use_container_width=True, config={"displayModeBar": False})


# ─── TAB 2: Stock Details ────────────────────────────────────────────────────────
with tab2:
    st.markdown("<div class='section-title'>Holdings Table</div>", unsafe_allow_html=True)

    # Build HTML table
    rows_html = ""
    for _, row in df.iterrows():
        pnl_class = "profit" if row["P&L"] >= 0 else "loss"
        pnl_sign  = "+" if row["P&L"] >= 0 else ""
        rows_html += f"""
        <tr>
            <td><b style="color:#e6edf3;">{row['Symbol']}</b></td>
            <td>{int(row['Quantity'])}</td>
            <td>{fmt_inr(row['Buy Price'])}</td>
            <td>{fmt_inr(row['Current Price'])}</td>
            <td>{fmt_inr(row['Invested Amount'])}</td>
            <td>{fmt_inr(row['Current Value'])}</td>
            <td class="{pnl_class}">{pnl_sign}{fmt_inr(row['P&L'])}</td>
            <td class="{pnl_class}">{pnl_sign}{row['P&L (%)']:.2f}%</td>
        </tr>"""

    table_html = f"""
    <div style='overflow-x:auto; border:1px solid #21262d; border-radius:10px; margin-bottom:24px;'>
    <table class='stock-table'>
        <thead><tr>
            <th>Symbol</th><th>Qty</th><th>Buy Price</th><th>Current</th>
            <th>Invested</th><th>Value</th><th>P&L (₹)</th><th>P&L (%)</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
    </div>
    """
    st.markdown(table_html, unsafe_allow_html=True)

    # CSV download
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    st.download_button(
        label="⬇ Download Portfolio CSV",
        data=csv_buffer.getvalue(),
        file_name=f"portfolio_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )

    # Historical line chart
    st.markdown("<div class='section-title'>Price History (6 Months)</div>", unsafe_allow_html=True)

    selected_stocks = st.multiselect(
        "Select stocks to compare",
        options=df["Symbol"].tolist(),
        default=df["Symbol"].tolist()[:3],
    )

    if selected_stocks:
        fig_hist = go.Figure()
        COLORS = ["#58a6ff","#3fb950","#d2a8ff","#ffa657","#f85149","#79c0ff","#56d364"]
        for i, sym in enumerate(selected_stocks):
            hist = fetch_history(sym, "6mo")
            if hist is not None:
                fig_hist.add_trace(go.Scatter(
                    x=hist["Date"],
                    y=hist["Close"],
                    name=sym,
                    line=dict(color=COLORS[i % len(COLORS)], width=2),
                    mode="lines",
                ))
        fig_hist.update_layout(
            xaxis=dict(showgrid=False, color="#8b949e"),
            yaxis=dict(showgrid=True, gridcolor="#21262d", color="#8b949e", tickprefix="₹"),
            hovermode="x unified",
            **CHART_LAYOUT
        )
        st.plotly_chart(fig_hist, use_container_width=True, config={"displayModeBar": False})


# ─── TAB 3: Benchmark ────────────────────────────────────────────────────────────
with tab3:
    st.markdown("<div class='section-title'>Portfolio vs Benchmark</div>", unsafe_allow_html=True)

    benchmark_options = {
        "Nifty 50 (^NSEI)":    "^NSEI",
        "S&P 500 (^GSPC)":     "^GSPC",
        "Sensex (^BSESN)":     "^BSESN",
        "Nasdaq 100 (^NDX)":   "^NDX",
    }
    chosen_label = st.selectbox("Benchmark Index", list(benchmark_options.keys()))
    chosen_sym   = benchmark_options[chosen_label]

    period_map = {"1 Month": "1mo", "3 Months": "3mo", "6 Months": "6mo", "1 Year": "1y"}
    chosen_period = period_map[st.selectbox("Period", list(period_map.keys()), index=2)]

    with st.spinner("Loading benchmark data…"):
        bench_data = fetch_benchmark(chosen_sym, chosen_period)

    def normalise_series(series: pd.Series):
        clean_series = pd.to_numeric(series, errors="coerce").dropna()
        clean_series = clean_series[clean_series > 0]
        if clean_series.empty:
            return None
        base_value = clean_series.iloc[0]
        if base_value == 0 or pd.isna(base_value):
            return None
        return (clean_series / base_value) * 100

    # Build a real portfolio value series from overlapping dates only.
    # This avoids zero/NaN propagation from missing price history.
    portfolio_series_list = []
    for stock in st.session_state.portfolio:
        hist = fetch_history(stock["symbol"], chosen_period)
        if hist is None or hist.empty:
            continue

        hist_series = pd.to_numeric(hist.set_index("Date")["Close"], errors="coerce").dropna()
        if hist_series.empty:
            continue

        portfolio_series_list.append((hist_series * float(stock["qty"])).rename(stock["symbol"]))

    portfolio_history = None
    if portfolio_series_list:
        aligned_history = pd.concat(portfolio_series_list, axis=1, join="inner").dropna(how="any")
        if not aligned_history.empty:
            portfolio_history = aligned_history.sum(axis=1)

    bench_series = None
    if bench_data is not None and not bench_data.empty:
        bench_series = pd.to_numeric(bench_data.set_index("Date")["Close"], errors="coerce").dropna()

    if portfolio_history is not None and bench_series is not None:
        # Normalise both to 100 from the first usable data point.
        port_norm = normalise_series(portfolio_history)
        bench_norm = normalise_series(bench_series)

        if port_norm is None or bench_norm is None:
            st.info("Portfolio or benchmark history does not contain enough valid numeric data to calculate returns.")
            st.stop()

        fig_bench = go.Figure()
        fig_bench.add_trace(go.Scatter(
            x=port_norm.index,
            y=port_norm.values,
            name="My Portfolio",
            line=dict(color="#58a6ff", width=2.5),
        ))
        fig_bench.add_trace(go.Scatter(
            x=bench_norm.index,
            y=bench_norm.values,
            name=chosen_label,
            line=dict(color="#8b949e", width=1.5, dash="dot"),
        ))
        fig_bench.add_hline(y=100, line_dash="dash", line_color="#21262d", line_width=1)
        fig_bench.update_layout(
            yaxis=dict(showgrid=True, gridcolor="#21262d", color="#8b949e", ticksuffix=""),
            xaxis=dict(showgrid=False, color="#8b949e"),
            hovermode="x unified",
            **CHART_LAYOUT
        )
        st.plotly_chart(fig_bench, use_container_width=True, config={"displayModeBar": False})

        # Outperformance
        port_ret  = round(float(port_norm.iloc[-1]) - 100, 2)
        bench_ret = round(float(bench_norm.iloc[-1]) - 100, 2)
        alpha     = round(port_ret - bench_ret, 2)

        c1, c2, c3 = st.columns(3)
        sign = lambda v: ("+" if v >= 0 else "")
        cls  = lambda v: "metric-delta-pos" if v >= 0 else "metric-delta-neg"

        with c1:
            st.markdown(f"""<div class='metric-card'>
                <div class='metric-label'>Portfolio Return</div>
                <div class='metric-value' style='font-size:22px;'>{sign(port_ret)}{port_ret}%</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""<div class='metric-card'>
                <div class='metric-label'>{chosen_label} Return</div>
                <div class='metric-value' style='font-size:22px;'>{sign(bench_ret)}{bench_ret}%</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""<div class='metric-card'>
                <div class='metric-label'>Alpha (Outperformance)</div>
                <div class='metric-value' style='font-size:22px;'><span class='{cls(alpha)}'>{sign(alpha)}{alpha}%</span></div>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("Could not load benchmark or portfolio history with valid numeric prices. Try a different period or verify yfinance data access.")


# ─── TAB 4: AI Analyst ─────────────────────────────────────────────────────────
with tab4:
    render_status_card("AI Analyst", "AI predictions are for educational purposes only. Not financial advice.")

    portfolio_symbols = df["Symbol"].tolist()
    if not portfolio_symbols:
        st.info("Add at least one stock to your portfolio to start an AI conversation.")
    else:
        if "ai_selected_stock" not in st.session_state or st.session_state.ai_selected_stock not in portfolio_symbols:
            st.session_state.ai_selected_stock = portfolio_symbols[0]

        selected_symbol = st.selectbox(
            "Select stock from portfolio",
            options=portfolio_symbols,
            index=portfolio_symbols.index(st.session_state.ai_selected_stock),
            key="ai_selected_stock",
        )

        if st.session_state.current_symbol != selected_symbol:
            st.session_state.current_symbol = selected_symbol
            st.session_state.chat_history = []

        snapshot = fetch_ai_stock_snapshot(selected_symbol)
        selected_rows = df[df["Symbol"] == selected_symbol]
        selected_row = selected_rows.iloc[0].to_dict() if not selected_rows.empty else None
        st.session_state.stock_context = build_stock_context(
            snapshot,
            selected_row,
            {"total_value": total_value},
        )
        st.session_state.ai_available = ai_is_available()

        if not st.session_state.ai_available:
            render_status_card(
                "AI Analyst unavailable",
                "AI Analyst is currently unavailable because the Gemini API key has not been configured.",
            )
            render_ai_placeholder()
        elif not snapshot.get("available") and not snapshot.get("closing_prices"):
            render_status_card("🤖 Gemini AI Ready", "Gemini is connected and ready to analyze your portfolio data.")
            render_status_card(
                "Market data",
                "Live market data is temporarily unavailable. The dashboard will continue with cached or partial values.",
            )
        else:
            render_status_card("🤖 Gemini AI Ready", "Gemini is connected and ready to analyze your portfolio data.")

        clear_col, spacer_col = st.columns([1, 4])
        with clear_col:
            if st.button("Clear Chat", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()

        st.markdown("<div class='section-title'>Quick Questions</div>", unsafe_allow_html=True)
        quick_questions = [
            "Will this stock rise or fall?",
            "Good time to buy?",
            "Analyse RSI",
            "SMA crossover trend?",
            "Key risks?",
            "Hold or sell?",
        ]

        for row_start in (0, 3):
            row_questions = quick_questions[row_start:row_start + 3]
            row_columns = st.columns(3)
            for column_index, question in enumerate(row_questions):
                with row_columns[column_index]:
                    if st.button(
                        question,
                        key=f"ai_quick_{selected_symbol}_{row_start}_{column_index}",
                        use_container_width=True,
                        disabled=not st.session_state.ai_available,
                    ):
                        submit_ai_message(selected_symbol, question)

        st.markdown("<div class='section-title'>Conversation</div>", unsafe_allow_html=True)
        if st.session_state.chat_history:
            for message in st.session_state.chat_history:
                render_chat_message(message["role"], message["content"])
        else:
            st.info("Ask a question or use a quick prompt to get started.")

        user_message = st.chat_input(
            "Ask the AI Analyst about this stock",
            disabled=not st.session_state.ai_available,
        )
        if user_message:
            submit_ai_message(selected_symbol, user_message)
