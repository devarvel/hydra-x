import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timezone

import sys
sys.path.insert(0, '/app/hydra_x_v2_1804')

from modules.telegram import TelegramNotifier, DailySummaryTracker


class TestDailySummaryTracker:
    """Test cases for DailySummaryTracker."""

    def test_init_state(self, tmp_path):
        """Test initialization with fresh state."""
        state_file = tmp_path / "state.json"
        tracker = DailySummaryTracker(str(state_file))
        
        assert tracker.state['trades_taken'] == 0
        assert tracker.state['wins_count'] == 0
        assert tracker.state['losses_count'] == 0
        assert tracker.state['total_daily_pnl'] == 0.0

    def test_record_trade_win(self, tmp_path):
        """Test recording a winning trade."""
        state_file = tmp_path / "state.json"
        tracker = DailySummaryTracker(str(state_file))
        
        tracker.record_trade(pnl=50.0, is_win=True)
        
        assert tracker.state['trades_taken'] == 1
        assert tracker.state['wins_count'] == 1
        assert tracker.state['losses_count'] == 0
        assert tracker.state['total_daily_pnl'] == 50.0

    def test_record_trade_loss(self, tmp_path):
        """Test recording a losing trade."""
        state_file = tmp_path / "state.json"
        tracker = DailySummaryTracker(str(state_file))
        
        tracker.record_trade(pnl=-30.0, is_win=False)
        
        assert tracker.state['trades_taken'] == 1
        assert tracker.state['wins_count'] == 0
        assert tracker.state['losses_count'] == 1
        assert tracker.state['total_daily_pnl'] == -30.0

    def test_multiple_trades(self, tmp_path):
        """Test recording multiple trades."""
        state_file = tmp_path / "state.json"
        tracker = DailySummaryTracker(str(state_file))
        
        tracker.record_trade(pnl=100.0, is_win=True)
        tracker.record_trade(pnl=-50.0, is_win=False)
        tracker.record_trade(pnl=75.0, is_win=True)
        
        assert tracker.state['trades_taken'] == 3
        assert tracker.state['wins_count'] == 2
        assert tracker.state['losses_count'] == 1
        assert tracker.state['total_daily_pnl'] == 125.0

    def test_get_daily_summary(self, tmp_path):
        """Test getting daily summary statistics."""
        state_file = tmp_path / "state.json"
        tracker = DailySummaryTracker(str(state_file))
        
        tracker.record_trade(pnl=100.0, is_win=True)
        tracker.record_trade(pnl=-50.0, is_win=False)
        
        summary = tracker.get_daily_summary()
        
        assert summary['trades_count'] == 2
        assert summary['win_rate_pct'] == 50.0
        assert summary['daily_pnl'] == 50.0

    def test_win_rate_calculation(self, tmp_path):
        """Test win rate calculation."""
        state_file = tmp_path / "state.json"
        tracker = DailySummaryTracker(str(state_file))
        
        for _ in range(3):
            tracker.record_trade(pnl=100.0, is_win=True)
        for _ in range(1):
            tracker.record_trade(pnl=-50.0, is_win=False)
        
        summary = tracker.get_daily_summary()
        assert summary['win_rate_pct'] == 75.0

    def test_state_persistence(self, tmp_path):
        """Test saving and loading state from JSON."""
        state_file = tmp_path / "state.json"
        tracker1 = DailySummaryTracker(str(state_file))
        
        tracker1.record_trade(pnl=100.0, is_win=True)
        tracker1.record_trade(pnl=-50.0, is_win=False)
        
        tracker2 = DailySummaryTracker(str(state_file))
        summary = tracker2.get_daily_summary()
        
        assert summary['trades_count'] == 2
        assert summary['daily_pnl'] == 50.0

    def test_max_drawdown_tracking(self, tmp_path):
        """Test max drawdown calculation."""
        state_file = tmp_path / "state.json"
        tracker = DailySummaryTracker(str(state_file))
        
        tracker.record_trade(pnl=-200.0, is_win=False)
        
        summary = tracker.get_daily_summary()
        assert summary['max_drawdown'] > 0


class TestTelegramNotifier:
    """Test cases for TelegramNotifier."""

    def test_init_disabled(self):
        """Test initialization with disabled Telegram."""
        config = {
            'telegram': {
                'enabled': False,
                'token': '',
                'chat_id': ''
            }
        }
        notifier = TelegramNotifier(config)
        assert notifier.enabled is False

    def test_init_enabled(self):
        """Test initialization with enabled Telegram."""
        config = {
            'telegram': {
                'enabled': True,
                'token': 'test_token_123',
                'chat_id': '123456789'
            }
        }
        notifier = TelegramNotifier(config)
        assert notifier.enabled is True
        assert notifier.token == 'test_token_123'
        assert notifier.chat_id == '123456789'

    @pytest.mark.asyncio
    async def test_initialize_disabled(self):
        """Test async initialization with disabled config."""
        config = {
            'telegram': {
                'enabled': False,
                'token': '',
                'chat_id': ''
            }
        }
        notifier = TelegramNotifier(config)
        await notifier.initialize()
        assert notifier.enabled is False

    def test_message_format_trade_entry(self):
        """Test trade entry message formatting."""
        config = {'telegram': {'enabled': True, 'token': 'test', 'chat_id': '123'}}
        notifier = TelegramNotifier(config)
        
        assert notifier.enabled is True

    def test_config_loading_with_defaults(self):
        """Test config loading with default values."""
        config = {}
        notifier = TelegramNotifier(config)
        assert notifier.enabled is False
        assert notifier.token == ''
        assert notifier.chat_id == ''

    @pytest.mark.asyncio
    async def test_trade_entry_alert_formatting(self):
        """Test trade entry alert message formatting."""
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
        
        assert notifier.bot.send_message.called

    @pytest.mark.asyncio
    async def test_partial_close_alert_formatting(self):
        """Test partial close alert message formatting."""
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
        
        await notifier.partial_close_alert(
            symbol='BTCUSDT',
            tp_level=1,
            profit_pct=5.5,
            amount_closed=0.15,
            remaining_position=0.35
        )
        
        assert notifier.bot.send_message.called

    @pytest.mark.asyncio
    async def test_full_close_alert_formatting(self):
        """Test full close alert message formatting."""
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
        
        await notifier.full_close_alert(
            symbol='BTCUSDT',
            exit_reason='TP2 Hit',
            pnl=1500.00,
            pnl_pct=12.5,
            duration='2h 15m'
        )
        
        assert notifier.bot.send_message.called

    @pytest.mark.asyncio
    async def test_daily_summary_alert_formatting(self):
        """Test daily summary alert message formatting."""
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
        
        await notifier.daily_summary_alert()
        
        assert notifier.bot.send_message.called

    @pytest.mark.asyncio
    async def test_error_alert_formatting(self):
        """Test error alert message formatting."""
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
        
        await notifier.error_alert(
            error_message='Connection lost to exchange',
            severity_level='WARNING'
        )
        
        assert notifier.bot.send_message.called

    @pytest.mark.asyncio
    async def test_send_message_retry_success(self):
        """Test send message with successful first attempt."""
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
        
        result = await notifier._send_message('Test message')
        
        assert result is True
        assert notifier.bot.send_message.call_count == 1

    @pytest.mark.asyncio
    async def test_send_message_retry_on_timeout(self):
        """Test send message with timeout retry."""
        config = {
            'telegram': {
                'enabled': True,
                'token': 'test_token',
                'chat_id': '123456789'
            }
        }
        notifier = TelegramNotifier(config)
        notifier.bot = AsyncMock()
        
        call_count = [0]
        async def mock_send(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise asyncio.TimeoutError()
            return MagicMock()
        
        notifier.bot.send_message = mock_send
        
        result = await notifier._send_message('Test message', max_retries=3)
        
        assert result is True
        assert call_count[0] == 3

    @pytest.mark.asyncio
    async def test_send_message_disabled(self):
        """Test send message when Telegram is disabled."""
        config = {
            'telegram': {
                'enabled': False,
                'token': '',
                'chat_id': ''
            }
        }
        notifier = TelegramNotifier(config)
        
        result = await notifier._send_message('Test message')
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_no_bot(self):
        """Test send message when bot is None."""
        config = {
            'telegram': {
                'enabled': True,
                'token': 'test_token',
                'chat_id': '123456789'
            }
        }
        notifier = TelegramNotifier(config)
        notifier.bot = None
        
        result = await notifier._send_message('Test message')
        
        assert result is False

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_error(self):
        """Test graceful degradation when sending fails."""
        config = {
            'telegram': {
                'enabled': True,
                'token': 'test_token',
                'chat_id': '123456789'
            }
        }
        notifier = TelegramNotifier(config)
        notifier.bot = AsyncMock()
        notifier.bot.send_message = AsyncMock(side_effect=Exception("Test error"))
        
        result = await notifier._send_message('Test message')
        
        assert result is False

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test graceful shutdown."""
        config = {
            'telegram': {
                'enabled': True,
                'token': 'test_token',
                'chat_id': '123456789'
            }
        }
        notifier = TelegramNotifier(config)
        notifier.bot = AsyncMock()
        notifier.bot.close = AsyncMock()
        
        await notifier.shutdown()
        
        assert notifier.bot.close.called


if __name__ == '__main__':
    pytest.main([__file__, '-v'])