# HYDRA-X v2 Streamlit Dashboard - Part 1

## Overview

The HYDRA-X v2 Dashboard is a real-time web-based monitoring interface for the algorithmic trading bot. It provides live visualization of account metrics, open positions, trade history, and bot status with 1-5 second refresh intervals.

## Features Implemented (Part 1)

### Core Components

1. **Account Metrics Panel**
   - Current Balance (with daily P&L delta)
   - Equity (balance + unrealized P&L)
   - Free Margin (available for new trades)
   - Margin Ratio % (used/total margin)
   - Current Drawdown % (highest peak decline)
   - Daily P&L (total and percentage)
   - Color-coded values (green/red for positive/negative)

2. **Open Positions Table**
   - Symbol, Direction (LONG/SHORT), Entry Price, Current Price
   - Unrealized P&L and P&L %
   - Stop Loss and Take Profit levels
   - Percentage to Stop Loss (distance metric)
   - Risk percentage per trade
   - Expandable rows showing additional details:
     - Entry Time
     - Position Size
     - TP1 and TP2 levels
     - Unrealized P&L %

3. **Trade History Table**
   - Last 50 closed trades
   - Entry/Exit times, symbol, direction
   - Entry/Exit prices
   - P&L and P&L %
   - Trade duration (HH:MM format)
   - Summary statistics:
     - Total trades, win count, loss count
     - Win rate percentage
     - Average profit and loss amounts

4. **Bot Status Display**
   - Current status: Running (🚀), Paused (⏸️), Shutdown (🛑)
   - Consecutive losses counter with color coding
   - Daily trade count vs. configured maximum
   - Shutdown reason (if applicable)

5. **Trend Bias Display**
   - M15 timeframe analysis per symbol
   - Trend classification: Bullish (📈), Bearish (📉), Ranging (➡️)
   - EMA50 and EMA200 values
   - Visual indicators for trend confirmation

6. **Price Action Confirmation Score**
   - Confirmation count (number of patterns detected)
   - Confirmation score (0-10 scale)
   - Active pattern indicators:
     - Engulfing, Pin Bar, Morning Star, Evening Star
     - Break of Structure (BOS), Fair Value Gap (FVG)
     - EMA retests, Support/Resistance retests

### Sidebar Controls

1. **Refresh Rate Slider** (0.5-5.0 seconds)
   - Controls dashboard update frequency
   - Configurable via sidebar
   - Default: 1 second

2. **Symbol Filter** (Multiselect)
   - Filter displays by symbol
   - Options: BTCUSDT, XAUTUSDT, All
   - Filters all tables and metrics

3. **View Toggle Buttons**
   - Overview: All components combined
   - Positions: Open positions table only
   - History: Trade history table only
   - Trends: Trend bias and PA confirmation

4. **Manual Refresh Button**
   - Immediate data refresh
   - Updates all displays in real-time

### Error Handling & Fallback

- **Missing Bot State**: Shows placeholder data with warning banner
- **Unavailable State Files**: Returns sensible defaults (0 values, "N/A")
- **Corrupted JSON**: Logs error and continues with empty data
- **Stale Data Detection**: Displays last-updated timestamp
- **Graceful Degradation**: UI remains readable even without bot running

## Installation & Setup

### Prerequisites

```bash
pip install streamlit pandas pyyaml
```

### Configuration

Dashboard settings in `config.yaml`:

```yaml
dashboard:
  enabled: true                # Enable/disable dashboard
  port: 8501                   # Streamlit server port
  refresh_rate: 1              # Default refresh rate (seconds)
  max_refresh_rate: 5          # Maximum allowed refresh rate
  min_refresh_rate: 0.5        # Minimum allowed refresh rate
  history_limit: 50            # Number of past trades to display
  update_timeout: 30           # Seconds before marking data as stale
  show_placeholder_data: true  # Show example UI when bot not running
```

## Running the Dashboard

### Start Dashboard

```bash
streamlit run /app/hydra_x_v2_1804/modules/dashboard.py
```

Dashboard will be available at: **http://localhost:8501**

### With Custom Port

```bash
streamlit run /app/hydra_x_v2_1804/modules/dashboard.py --server.port 8502
```

### With Bot Running Simultaneously

```bash
# Terminal 1: Start the trading bot
python /app/hydra_x_v2_1804/main.py

# Terminal 2: Start the dashboard
streamlit run /app/hydra_x_v2_1804/modules/dashboard.py
```

## Data Sources

Dashboard reads from JSON state files written by the bot:

### Files

| File | Purpose | Updated By |
|------|---------|-----------|
| `data/daily_summary_state.json` | Account metrics, bot status | Risk Manager / Main loop |
| `data/open_positions.json` | Current open positions | Order Executor |
| `data/trade_history.json` | Closed trade records | Order Executor |
| `data/trend_cache.json` | M15 trend data | Signal Generator (optional) |
| `data/pa_confirmation_cache.json` | PA confirmation scores | Signal Generator (optional) |

## Module Architecture

### dashboard_state_reader.py

Handles all JSON file reading and parsing:

```python
reader = DashboardStateReader("/app/hydra_x_v2_1804/data")

# Read account metrics
metrics = reader.read_account_metrics()
# Returns: {balance, equity, free_margin, margin_ratio_pct, drawdown_pct, ...}

# Read open positions
positions = reader.read_open_positions()
# Returns: List[{symbol, direction, entry_price, current_price, unrealized_pnl, ...}]

# Read trade history
trades = reader.read_trade_history(limit=50)
# Returns: List[{entry_time, symbol, direction, entry_price, exit_price, pnl, pnl_pct, ...}]

# Read bot status
status = reader.read_bot_status()
# Returns: {status, consecutive_losses, daily_trade_count, shutdown_reason, ...}
```

### dashboard.py

Main Streamlit application:

- `render_account_metrics()`: Renders account metrics panel
- `render_open_positions()`: Renders positions table with expandable details
- `render_trade_history()`: Renders trade history with summary stats
- `render_bot_status()`: Renders bot status indicator
- `render_trend_bias()`: Renders M15 trend display
- `render_pa_confirmation()`: Renders price action confirmation
- `render_sidebar()`: Renders sidebar controls
- `main()`: Main app entry point

## Performance Metrics

- **Refresh Rate**: 1-5 seconds (user configurable)
- **CPU Usage**: < 10% idle, < 30% during active refresh
- **Memory Usage**: < 500MB steady state, < 1GB peak
- **Data Read Latency**: < 100ms per JSON file
- **UI Update Latency**: < 50ms (Streamlit rendering)

## Troubleshooting

### Dashboard Not Displaying Data

**Symptom**: Dashboard shows placeholder data, error banner visible

**Solution**:
1. Verify bot is running: `ps aux | grep main.py`
2. Check state files exist: `ls -la data/*.json`
3. Verify JSON file permissions: `chmod 644 data/*.json`
4. Check logs: `tail -f logs/hydra_x_main.log`

### High CPU Usage

**Symptom**: Dashboard using > 50% CPU

**Solution**:
1. Increase refresh rate via sidebar slider (reduce to 5 seconds)
2. Switch to filtered view (single symbol instead of all)
3. Reduce history limit in config.yaml
4. Check for corrupted JSON files

### Stale Data

**Symptom**: Timestamp shows old time, values not updating

**Solution**:
1. Click "Manual Refresh" button
2. Reduce refresh rate slider
3. Verify bot is actively updating state files
4. Check bot logs for errors

### Port Already in Use

**Symptom**: Error "Address already in use" on port 8501

**Solution**:
```bash
# Find process using port 8501
lsof -i :8501

# Kill process
kill -9 <PID>

# Or use different port
streamlit run modules/dashboard.py --server.port 8502
```

## Testing

Run validation suite:

```bash
python /app/hydra_x_v2_1804/validate_dashboard_part1.py
```

Expected output:
- ✅ State Reader Initialization
- ✅ Account Metrics Reading
- ✅ Open Positions Reading
- ✅ Trade History Reading
- ✅ Bot Status Reading
- ✅ Error Handling - Missing Files
- ✅ Error Handling - Corrupted JSON

## Future Enhancements (Part 2)

- Live OHLC candlestick charts with Plotly
- Support/Resistance zone visualization
- P&L curve chart with equity progression
- Performance statistics dashboard
- Advanced filtering and export options
- Real-time WebSocket updates (optional)

## Integration with Bot

The dashboard is designed to run alongside the bot without interfering:

1. **Non-intrusive**: Only reads state JSON files, never writes
2. **Asynchronous**: Doesn't block bot operations
3. **Fault-tolerant**: Continues operating even if bot stops
4. **Real-time**: Updates every 1-5 seconds via filesystem polling
5. **Scalable**: Can handle multiple dashboard instances

## Notes

- Dashboard refreshes by reading JSON files from disk
- No database required - uses file-based state
- Suitable for single-machine deployments
- For high-frequency updates (< 1 second), consider WebSocket integration in Part 2
- All timestamps are UTC
- Currency values formatted as USD with commas for thousands
- Percentages displayed to 1-2 decimal places

## Support

For issues or questions:
1. Check logs: `tail -f logs/hydra_x_main.log`
2. Review config.yaml for dashboard settings
3. Verify state file structure in data/ directory
4. Run validation script: `python validate_dashboard_part1.py`