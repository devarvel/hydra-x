import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from telegram import Bot
from telegram.error import TelegramError, BadRequest, TimedOut, RetryAfter

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)


class DailySummaryTracker:
    """Tracks daily trading statistics for summary alerts."""

    def __init__(self, state_file: str = "/app/hydra_x_v2_1804/data/daily_summary_state.json"):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load state from JSON file if it exists and is from today."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    saved_state = json.load(f)
                    saved_date = saved_state.get('date')
                    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                    if saved_date == today:
                        return saved_state
            except Exception as e:
                logger.warning(f"Failed to load daily summary state: {e}")
        return self._init_state()

    def _init_state(self) -> Dict[str, Any]:
        """Initialize fresh state for a new day."""
        return {
            'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            'trades_taken': 0,
            'wins_count': 0,
            'losses_count': 0,
            'total_daily_pnl': 0.0,
            'max_drawdown': 0.0,
            'peak_balance': 10000.0,
            'current_balance': 10000.0
        }

    def _save_state(self):
        """Persist state to JSON file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save daily summary state: {e}")

    def record_trade(self, pnl: float, is_win: bool):
        """Record a completed trade."""
        self.state['trades_taken'] += 1
        if is_win:
            self.state['wins_count'] += 1
        else:
            self.state['losses_count'] += 1
        self.state['total_daily_pnl'] += pnl
        
        new_balance = 10000.0 + self.state['total_daily_pnl']
        self.state['current_balance'] = new_balance
        
        if new_balance > self.state['peak_balance']:
            self.state['peak_balance'] = new_balance
        
        drawdown = self.state['peak_balance'] - new_balance
        if drawdown > self.state['max_drawdown']:
            self.state['max_drawdown'] = drawdown
        
        self._save_state()

    def get_daily_summary(self) -> Dict[str, Any]:
        """Get current daily summary statistics."""
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        if self.state['date'] != today:
            self.state = self._init_state()
            self._save_state()
        
        trades = self.state['trades_taken']
        win_rate = (self.state['wins_count'] / trades * 100) if trades > 0 else 0
        
        return {
            'trades_count': trades,
            'win_rate_pct': win_rate,
            'daily_pnl': self.state['total_daily_pnl'],
            'max_drawdown': self.state['max_drawdown']
        }

    def reset_daily_stats(self):
        """Reset stats at 00:00 UTC."""
        self.state = self._init_state()
        self._save_state()


class TelegramNotifier:
    """Handles Telegram notifications for trading alerts."""

    def __init__(self, config_dict: Dict[str, Any]):
        """Initialize TelegramNotifier with config."""
        self.config = config_dict
        self.enabled = config_dict.get('telegram', {}).get('enabled', False)
        self.token = config_dict.get('telegram', {}).get('token', '')
        self.chat_id = config_dict.get('telegram', {}).get('chat_id', '')
        self.bot = None
        self.summary_tracker = DailySummaryTracker()
        
        if not self.enabled:
            logger.info("Telegram notifications disabled in config")

    async def initialize(self):
        """Initialize Telegram bot asynchronously."""
        if not self.enabled or not self.token or not self.chat_id:
            logger.warning("Telegram not properly configured - notifications disabled")
            self.enabled = False
            return
        
        try:
            self.bot = Bot(token=self.token)
            test_msg = await self.bot.get_me()
            logger.info(f"Telegram bot initialized: {test_msg.username}")
        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            self.enabled = False

    async def _send_message(self, text: str, max_retries: int = 3) -> bool:
        """Send message with retry logic and exponential backoff."""
        if not self.enabled or not self.bot:
            return False
        
        delays = [0.5, 2.0, 5.0]
        
        for attempt in range(max_retries):
            try:
                await asyncio.wait_for(
                    self.bot.send_message(
                        chat_id=self.chat_id,
                        text=text,
                        parse_mode='Markdown'
                    ),
                    timeout=10.0
                )
                logger.info(f"Telegram message sent successfully (attempt {attempt + 1})")
                return True
            except asyncio.TimeoutError:
                logger.warning(f"Telegram send timeout on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(delays[attempt])
            except RetryAfter as e:
                logger.warning(f"Telegram rate limit: waiting {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
            except BadRequest as e:
                logger.error(f"Permanent Telegram error (bad request): {e}")
                return False
            except TelegramError as e:
                logger.warning(f"Telegram error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(delays[attempt])
            except Exception as e:
                logger.error(f"Unexpected error sending Telegram message: {e}")
                return False
        
        logger.error(f"Failed to send Telegram message after {max_retries} attempts")
        return False

    async def trade_entry_alert(
        self, symbol: str, direction: str, entry_price: float, stop_loss: float,
        tp1: float, tp2: float, lot_size: float, risk_pct: float
    ):
        """Send trade entry alert."""
        try:
            direction_emoji = "🟢" if direction == "LONG" else "🔴"
            timestamp = datetime.now(timezone.utc).strftime('%H:%M:%S UTC')
            
            message = (
                f"🚀 *TRADE ENTRY ALERT*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"*Symbol:* `{symbol}`\n"
                f"*Direction:* {direction_emoji} *{direction}*\n"
                f"*Entry Price:* `${entry_price:.2f}`\n"
                f"*Stop Loss:* ❌ `${stop_loss:.2f}`\n"
                f"*Take Profit 1:* 🎯 `${tp1:.2f}` (30% close)\n"
                f"*Take Profit 2:* 🎯 `${tp2:.2f}` (40% close)\n"
                f"*Position Size:* `{lot_size:.4f}`\n"
                f"*Risk:* `{risk_pct:.2f}%`\n"
                f"*Time:* `{timestamp}`"
            )
            
            await self._send_message(message)
        except Exception as e:
            logger.error(f"Error sending trade entry alert: {e}")

    async def partial_close_alert(
        self, symbol: str, tp_level: int, profit_pct: float,
        amount_closed: float, remaining_position: float
    ):
        """Send partial close alert."""
        try:
            timestamp = datetime.now(timezone.utc).strftime('%H:%M:%S UTC')
            profit_emoji = "📈" if profit_pct >= 0 else "📉"
            
            message = (
                f"🎯 *PARTIAL CLOSE ALERT*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"*Symbol:* `{symbol}`\n"
                f"*TP Level:* `TP{tp_level}`\n"
                f"*Profit:* {profit_emoji} `{profit_pct:+.2f}%`\n"
                f"*Amount Closed:* `{amount_closed:.4f}`\n"
                f"*Remaining Position:* `{remaining_position:.4f}`\n"
                f"*Time:* `{timestamp}`"
            )
            
            await self._send_message(message)
        except Exception as e:
            logger.error(f"Error sending partial close alert: {e}")

    async def full_close_alert(
        self, symbol: str, exit_reason: str, pnl: float,
        pnl_pct: float, duration: str
    ):
        """Send full close alert."""
        try:
            timestamp = datetime.now(timezone.utc).strftime('%H:%M:%S UTC')
            pnl_emoji = "✅" if pnl >= 0 else "❌"
            
            message = (
                f"✅ *TRADE CLOSED*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"*Symbol:* `{symbol}`\n"
                f"*Exit Reason:* `{exit_reason}`\n"
                f"*Final PnL:* {pnl_emoji} `${pnl:+.2f}`\n"
                f"*PnL %:* `{pnl_pct:+.2f}%`\n"
                f"*Duration:* `{duration}`\n"
                f"*Time:* `{timestamp}`"
            )
            
            await self._send_message(message)
            
            is_win = pnl > 0
            self.summary_tracker.record_trade(pnl, is_win)
        except Exception as e:
            logger.error(f"Error sending full close alert: {e}")

    async def daily_summary_alert(self):
        """Send daily summary alert at 00:00 UTC."""
        try:
            summary = self.summary_tracker.get_daily_summary()
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
            
            win_rate_emoji = "📈" if summary['win_rate_pct'] >= 50 else "📉"
            pnl_emoji = "💰" if summary['daily_pnl'] >= 0 else "📉"
            
            message = (
                f"📊 *DAILY SUMMARY*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"*Trades Taken:* `{summary['trades_count']}`\n"
                f"*Win Rate:* {win_rate_emoji} `{summary['win_rate_pct']:.1f}%`\n"
                f"*Daily PnL:* {pnl_emoji} `${summary['daily_pnl']:+.2f}`\n"
                f"*Max Drawdown:* `${summary['max_drawdown']:.2f}`\n"
                f"*Report Time:* `{timestamp}`"
            )
            
            await self._send_message(message)
        except Exception as e:
            logger.error(f"Error sending daily summary alert: {e}")

    async def error_alert(self, error_message: str, severity_level: str = "WARNING"):
        """Send error/alert notification."""
        try:
            timestamp = datetime.now(timezone.utc).strftime('%H:%M:%S UTC')
            
            severity_emoji = "⚠️" if severity_level == "WARNING" else "🚨"
            
            message = (
                f"{severity_emoji} *{severity_level} ALERT*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"*Error:* `{error_message}`\n"
                f"*Time:* `{timestamp}`"
            )
            
            await self._send_message(message)
        except Exception as e:
            logger.error(f"Error sending error alert: {e}")

    async def shutdown(self):
        """Gracefully shutdown Telegram bot."""
        if self.bot:
            try:
                await self.bot.close()
                logger.info("Telegram bot closed")
            except Exception as e:
                logger.error(f"Error closing Telegram bot: {e}")