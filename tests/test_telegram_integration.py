import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import sys
sys.path.insert(0, '/app/hydra_x_v2_1804')

from modules.telegram import TelegramNotifier, DailySummaryTracker


class TestTelegramIntegration:
    """Integration tests for Telegram alerts in trading lifecycle."""

    @pytest.mark.asyncio
    async def test_full_trading_cycle_alerts(self):
        """Test all alert types in a simulated trading cycle."""
        config = {
            'telegram': {
                'enabled': True,
                'token': 'test_token',
                'chat_id': '123456789'
            }
        }
        
        notifier = TelegramNotifier(config)
        notifier.bot = AsyncMock()
        notifier.bot.send_message = AsyncMock(return_value=MagicMock())
        
        await notifier.trade_entry_alert(
            symbol='BTCUSDT',
            direction='LONG',
            entry_price=45000.00,
            stop_loss=44500.00,
            tp1=47500.00,
            tp2=50000.00,
            lot_size=0.5,
            risk_pct=1.75
        )
        
        await notifier.partial_close_alert(
            symbol='BTCUSDT',
            tp_level=1,
            profit_pct=5.5,
            amount_closed=0.15,
            remaining_position=0.35
        )
        
        await notifier.full_close_alert(
            symbol='BTCUSDT',
            exit_reason='TP2 Hit',
            pnl=1500.00,
            pnl_pct=12.5,
            duration='2h 15m'
        )
        
        await notifier.daily_summary_alert()
        
        assert notifier.bot.send_message.call_count == 4

    @pytest.mark.asyncio
    async def test_multiple_signals_with_alerts(self):
        """Test multiple trade signals generating correct alerts."""
        config = {
            'telegram': {
                'enabled': True,
                'token': 'test_token',
                'chat_id': '123456789'
            }
        }
        
        notifier = TelegramNotifier(config)
        notifier.bot = AsyncMock()
        notifier.bot.send_message = AsyncMock(return_value=MagicMock())
        
        symbols = ['BTCUSDT', 'XAUTUSDT']
        for symbol in symbols:
            await notifier.trade_entry_alert(
                symbol=symbol,
                direction='LONG',
                entry_price=45000.00 if symbol == 'BTCUSDT' else 2050.00,
                stop_loss=44500.00 if symbol == 'BTCUSDT' else 2000.00,
                tp1=47500.00 if symbol == 'BTCUSDT' else 2100.00,
                tp2=50000.00 if symbol == 'BTCUSDT' else 2150.00,
                lot_size=0.5,
                risk_pct=1.75
            )
        
        assert notifier.bot.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_error_handling_with_alerts(self):
        """Test error alerts on trading failures."""
        config = {
            'telegram': {
                'enabled': True,
                'token': 'test_token',
                'chat_id': '123456789'
            }
        }
        
        notifier = TelegramNotifier(config)
        notifier.bot = AsyncMock()
        notifier.bot.send_message = AsyncMock(return_value=MagicMock())
        
        error_messages = [
            'Connection lost to exchange',
            'Insufficient balance for trade',
            'Order rejected: invalid parameters'
        ]
        
        for error_msg in error_messages:
            await notifier.error_alert(
                error_message=error_msg,
                severity_level='WARNING'
            )
        
        assert notifier.bot.send_message.call_count == 3

    @pytest.mark.asyncio
    async def test_daily_summary_with_trades(self, tmp_path):
        """Test daily summary tracking with multiple trades."""
        config = {
            'telegram': {
                'enabled': True,
                'token': 'test_token',
                'chat_id': '123456789'
            }
        }
        
        state_file = tmp_path / "state.json"
        notifier = TelegramNotifier(config)
        notifier.summary_tracker = DailySummaryTracker(str(state_file))
        notifier.bot = AsyncMock()
        notifier.bot.send_message = AsyncMock(return_value=MagicMock())
        
        notifier.summary_tracker.record_trade(pnl=100.0, is_win=True)
        notifier.summary_tracker.record_trade(pnl=-50.0, is_win=False)
        notifier.summary_tracker.record_trade(pnl=150.0, is_win=True)
        
        summary = notifier.summary_tracker.get_daily_summary()
        
        assert summary['trades_count'] == 3
        assert summary['win_rate_pct'] == 66.66666666666666
        assert summary['daily_pnl'] == 200.0

    @pytest.mark.asyncio
    async def test_concurrent_alerts(self):
        """Test sending multiple alerts concurrently."""
        config = {
            'telegram': {
                'enabled': True,
                'token': 'test_token',
                'chat_id': '123456789'
            }
        }
        
        notifier = TelegramNotifier(config)
        notifier.bot = AsyncMock()
        notifier.bot.send_message = AsyncMock(return_value=MagicMock())
        
        tasks = []
        for i in range(5):
            task = notifier.trade_entry_alert(
                symbol='BTCUSDT',
                direction='LONG',
                entry_price=45000.00,
                stop_loss=44500.00,
                tp1=47500.00,
                tp2=50000.00,
                lot_size=0.5,
                risk_pct=1.75
            )
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        assert notifier.bot.send_message.call_count == 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])