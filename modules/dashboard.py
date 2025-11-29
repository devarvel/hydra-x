"""
Streamlit dashboard for HYDRA-X v2 trading bot.
Displays real-time account metrics, positions, trade history, and bot status.
"""

import streamlit as st
import pandas as pd
import time
import logging
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.dashboard_state_reader import DashboardStateReader
from utils import load_config

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="HYDRA-X v2 Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .metric-card {
        padding: 15px;
        border-radius: 8px;
        margin: 5px;
    }
    .positive {
        background-color: #00aa00;
        color: white;
    }
    .negative {
        background-color: #ff4444;
        color: white;
    }
    .neutral {
        background-color: #4444aa;
        color: white;
    }
    .warning {
        background-color: #ffaa00;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_state_reader():
    return DashboardStateReader("/app/hydra_x_v2_1804/data")

@st.cache_resource
def get_config():
    try:
        return load_config("/app/hydra_x_v2_1804/config.yaml")
    except:
        return {"symbols": ["BTCUSDT", "XAUTUSDT"], "max_daily_trades": 4}

def get_emoji_trend(trend: str) -> str:
    if "bullish" in trend.lower():
        return "📈"
    elif "bearish" in trend.lower():
        return "📉"
    else:
        return "➡️"

def get_emoji_status(status: str) -> str:
    if "running" in status.lower():
        return "🚀"
    elif "paused" in status.lower():
        return "⏸️"
    else:
        return "🛑"

def format_currency(value: float) -> str:
    return f"${value:,.2f}"

def format_percent(value: float) -> str:
    sign = "+" if value >= 0 else ""
    color = "green" if value >= 0 else "red"
    return f"{sign}{value:.2f}%"

def render_account_metrics(metrics: dict):
    """Render account metrics in 4-column layout."""
    st.subheader("📊 Account Metrics")
    
    if not metrics.get("available"):
        st.warning("⚠️ Bot not running or state unavailable. Showing placeholder data.")
        metrics = {
            "balance": 1000.0,
            "equity": 1050.0,
            "free_margin": 900.0,
            "margin_ratio_pct": 14.3,
            "drawdown_pct": 0.0,
            "daily_pnl": 50.0,
            "daily_pnl_pct": 5.0,
            "available": False
        }
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Balance",
            value=format_currency(metrics["balance"]),
            delta=format_percent(metrics["daily_pnl_pct"]),
            delta_color="off"
        )
    
    with col2:
        st.metric(
            label="Equity",
            value=format_currency(metrics["equity"]),
            delta=None
        )
    
    with col3:
        st.metric(
            label="Free Margin",
            value=format_currency(metrics["free_margin"]),
            delta=None
        )
    
    with col4:
        st.metric(
            label="Margin Ratio %",
            value=f"{metrics['margin_ratio_pct']:.2f}%",
            delta=None
        )
    
    col5, col6 = st.columns(2)
    
    with col5:
        drawdown_color = "inverse" if metrics["drawdown_pct"] > 3 else "off"
        st.metric(
            label="Current Drawdown %",
            value=f"{metrics['drawdown_pct']:.2f}%",
            delta=None,
            delta_color=drawdown_color
        )
    
    with col6:
        st.metric(
            label="Daily P&L",
            value=format_currency(metrics["daily_pnl"]),
            delta=format_percent(metrics["daily_pnl_pct"]),
            delta_color="off"
        )

def render_open_positions(positions: list):
    """Render open positions table."""
    st.subheader("📍 Open Positions")
    
    if not positions:
        st.info("No open positions")
        return
    
    df_data = []
    for pos in positions:
        df_data.append({
            "Symbol": pos["symbol"],
            "Direction": pos["direction"],
            "Entry Price": f"${pos['entry_price']:.2f}",
            "Current Price": f"${pos['current_price']:.2f}",
            "Unrealized PnL": f"${pos['unrealized_pnl']:.2f}",
            "SL": f"${pos['sl']:.2f}",
            "TP": f"${pos['tp']:.2f}",
            "% to SL": f"{pos['pct_to_sl']:.1f}%",
            "Risk %": f"{pos['risk_pct']:.2f}%"
        })
    
    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    for idx, pos in enumerate(positions):
        with st.expander(f"Details: {pos['symbol']} {pos['direction']}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Entry Time:** {pos['entry_time']}")
                st.write(f"**TP1:** ${pos['tp1']:.2f}")
            with col2:
                st.write(f"**Position Size:** {pos['position_size']:.4f}")
                st.write(f"**TP2:** ${pos['tp2']:.2f}")
            with col3:
                st.write(f"**Unrealized %:** {pos['unrealized_pnl_pct']:.2f}%")

def render_trade_history(trades: list):
    """Render trade history table."""
    st.subheader("📜 Trade History (Last 50)")
    
    if not trades:
        st.info("No closed trades yet")
        return
    
    win_count = len([t for t in trades if t["pnl"] > 0])
    loss_count = len([t for t in trades if t["pnl"] < 0])
    total_trades = len(trades)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
    avg_profit = sum([t["pnl"] for t in trades if t["pnl"] > 0]) / max(1, win_count)
    avg_loss = sum([t["pnl"] for t in trades if t["pnl"] < 0]) / max(1, loss_count)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Trades", total_trades)
    col2.metric("Wins", win_count)
    col3.metric("Losses", loss_count)
    col4.metric("Win Rate %", f"{win_rate:.1f}%")
    col5.metric("Avg Profit/Loss", f"${avg_profit:.2f} / ${avg_loss:.2f}")
    
    df_data = []
    for trade in trades:
        df_data.append({
            "Entry Time": trade["entry_time"],
            "Symbol": trade["symbol"],
            "Direction": trade["direction"],
            "Entry Price": f"${trade['entry_price']:.2f}",
            "Exit Price": f"${trade['exit_price']:.2f}",
            "PnL": f"${trade['pnl']:.2f}",
            "PnL %": f"{trade['pnl_pct']:.2f}%",
            "Duration": trade["duration"]
        })
    
    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

def render_bot_status(status: dict):
    """Render bot status display."""
    st.subheader("🤖 Bot Status")
    
    if not status.get("available"):
        st.warning("⚠️ Bot state unavailable")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        emoji = get_emoji_status(status["status"])
        status_color = "🟢" if "RUNNING" in status["status"].upper() else ("🟡" if "PAUSED" in status["status"].upper() else "🔴")
        st.markdown(f"### {emoji} {status_color} Status: {status['status']}")
    
    with col2:
        loss_color = "🔴" if status["consecutive_losses"] >= 2 else ("🟡" if status["consecutive_losses"] == 1 else "🟢")
        st.markdown(f"### {loss_color} Consecutive Losses: {status['consecutive_losses']}")
    
    with col3:
        st.markdown(f"### 📈 Daily Trades: {status['daily_trade_count']}")
    
    if status.get("shutdown_reason"):
        st.error(f"**Shutdown Reason:** {status['shutdown_reason']}")

def render_trend_bias(config: dict, reader: DashboardStateReader):
    """Render trend bias display."""
    st.subheader("📊 Trend Bias (M15)")
    
    symbols = config.get("symbols", ["BTCUSDT", "XAUTUSDT"])
    trend_data = reader.read_trend_data()
    
    cols = st.columns(len(symbols))
    for idx, symbol in enumerate(symbols):
        with cols[idx]:
            if symbol in trend_data:
                trend = trend_data[symbol].get("trend", "RANGING")
                ema50 = trend_data[symbol].get("ema50", 0)
                ema200 = trend_data[symbol].get("ema200", 0)
            else:
                trend = "RANGING"
                ema50 = 0
                ema200 = 0
            
            emoji = get_emoji_trend(trend)
            st.markdown(f"### {emoji} {symbol}")
            st.write(f"**Trend:** {trend}")
            st.write(f"**EMA50:** {ema50:.2f}")
            st.write(f"**EMA200:** {ema200:.2f}")

def render_pa_confirmation(reader: DashboardStateReader):
    """Render price action confirmation display."""
    st.subheader("📍 Price Action Confirmation")
    
    pa_data = reader.read_pa_confirmation()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Confirmation Count", pa_data.get("confirmation_count", 0))
    
    with col2:
        score = pa_data.get("confirmation_score", 0)
        st.metric("Confirmation Score", f"{score:.1f}/10")
    
    patterns = pa_data.get("patterns", [])
    if patterns:
        st.write("**Active Patterns:**")
        for pattern in patterns:
            st.write(f"- ✓ {pattern}")

def render_sidebar(config: dict):
    """Render sidebar controls."""
    st.sidebar.title("⚙️ Configuration")
    
    refresh_rate = st.sidebar.slider(
        "Refresh Rate (seconds)",
        min_value=0.5,
        max_value=5.0,
        value=1.0,
        step=0.5
    )
    
    symbols = config.get("symbols", ["BTCUSDT", "XAUTUSDT"])
    selected_symbols = st.sidebar.multiselect(
        "Symbol Filter",
        options=symbols + ["All"],
        default=["All"]
    )
    
    view_mode = st.sidebar.radio(
        "View Mode",
        options=["Overview", "Positions", "History", "Trends"],
        horizontal=False
    )
    
    manual_refresh = st.sidebar.button("🔄 Manual Refresh")
    
    return refresh_rate, selected_symbols, view_mode, manual_refresh

def main():
    """Main dashboard app."""
    st.title("🚀 HYDRA-X v2 Dashboard")
    
    reader = get_state_reader()
    config = get_config()
    
    refresh_rate, selected_symbols, view_mode, manual_refresh = render_sidebar(config)
    
    container = st.container()
    
    if view_mode == "Overview":
        with container:
            metrics = reader.read_account_metrics()
            render_account_metrics(metrics)
            
            st.divider()
            render_bot_status(reader.read_bot_status())
            
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                render_trend_bias(config, reader)
            with col2:
                render_pa_confirmation(reader)
            
            st.divider()
            positions = reader.read_open_positions()
            render_open_positions(positions)
    
    elif view_mode == "Positions":
        with container:
            positions = reader.read_open_positions()
            render_open_positions(positions)
    
    elif view_mode == "History":
        with container:
            trades = reader.read_trade_history(limit=50)
            render_trade_history(trades)
    
    elif view_mode == "Trends":
        with container:
            render_trend_bias(config, reader)
            st.divider()
            render_pa_confirmation(reader)
    
    st.divider()
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    if manual_refresh or refresh_rate > 0:
        time.sleep(refresh_rate)
        st.rerun()

if __name__ == "__main__":
    main()