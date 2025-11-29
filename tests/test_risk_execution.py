import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, '/app/hydra_x_v2_1804')

from modules.risk import RiskManager, TradeEntry, OpenPosition
from modules.execution import OrderExecutor, FirstRunSafetyTrade, StateManager, GracefulShutdown


class TestRiskManager:
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def config(self):
        return {
            'account_balance': 10000.0,
            'risk_percent': 1.75,
            'max_spread_points': 50,
            'max_daily_loss': 5.0,
            'max_consecutive_losses': 2,
            'exchange_min_lot_size': 0.001
        }
    
    @pytest.fixture
    def risk_manager(self, config, temp_dir):
        return RiskManager(config, data_dir=temp_dir)
    
    def test_position_sizing_formula(self, risk_manager):
        entry_price = 100.0
        stop_loss = 95.0
        
        position_size = risk_manager.position_size(entry_price, stop_loss)
        
        expected_risk = 10000.0 * 0.0175
        expected_sl_distance = 5.0
        expected_size = expected_risk / expected_sl_distance
        
        assert abs(position_size - expected_size) < 0.0001
    
    def test_position_sizing_min_lot(self, risk_manager):
        entry_price = 1.0
        stop_loss = 0.99
        
        position_size = risk_manager.position_size(entry_price, stop_loss)
        
        assert position_size >= risk_manager.exchange_min_lot_size
    
    def test_position_sizing_zero_sl_distance(self, risk_manager):
        entry_price = 100.0
        stop_loss = 100.0
        
        position_size = risk_manager.position_size(entry_price, stop_loss)
        
        assert position_size == 0.0
    
    def test_spread_filter_valid(self, risk_manager):
        bid = 100.0
        ask = 100.005
        
        result = risk_manager.spread_filter(bid, ask)
        
        assert result is True
    
    def test_spread_filter_invalid(self, risk_manager):
        bid = 100.0
        ask = 101.0
        
        result = risk_manager.spread_filter(bid, ask)
        
        assert result is False
    
    def test_daily_pnl_tracking(self, risk_manager, temp_dir):
        risk_manager.track_daily_pnl(100.0, "BTC/USDT")
        
        daily_pnl_file = Path(temp_dir) / "daily_pnl.json"
        assert daily_pnl_file.exists()
        
        with open(daily_pnl_file, 'r') as f:
            data = json.load(f)
            assert data['cumulative_pnl'] == 100.0
            assert data['trades_today'] == 1
            assert data['winning_trades'] == 1
    
    def test_consecutive_losses_increment(self, risk_manager):
        result, reason = risk_manager.increment_consecutive_losses()
        assert result is True
        assert risk_manager.consecutive_loss_counter == 1
        
        result, reason = risk_manager.increment_consecutive_losses()
        assert result is False
        assert "Consecutive loss limit reached" in reason
    
    def test_consecutive_losses_reset(self, risk_manager):
        risk_manager.consecutive_loss_counter = 2
        risk_manager.reset_consecutive_losses()
        assert risk_manager.consecutive_loss_counter == 0
    
    def test_daily_loss_limit_check_passed(self, risk_manager):
        risk_manager.daily_loss_accumulation = -100.0
        result, reason = risk_manager.check_daily_loss_limit()
        assert result is True
    
    def test_daily_loss_limit_check_exceeded(self, risk_manager):
        max_loss = 10000.0 * 0.05
        risk_manager.daily_loss_accumulation = -max_loss - 1.0
        result, reason = risk_manager.check_daily_loss_limit()
        assert result is False
        assert "Daily loss limit exceeded" in reason
    
    def test_slippage_tracker_acceptable(self, risk_manager):
        expected_price = 100.0
        actual_price = 100.02
        
        is_acceptable, slippage_pct = risk_manager.slippage_tracker(expected_price, actual_price)
        
        assert is_acceptable is True
        assert slippage_pct < 0.05
    
    def test_slippage_tracker_excessive(self, risk_manager):
        expected_price = 100.0
        actual_price = 100.1
        
        is_acceptable, slippage_pct = risk_manager.slippage_tracker(expected_price, actual_price)
        
        assert is_acceptable is False
        assert slippage_pct > 0.05


class TestOrderExecutor:
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def config(self):
        return {
            'max_retries': 3,
            'retry_initial_delay': 0.5,
            'retry_max_delay': 5.0,
            'retry_backoff_multiplier': 2.0,
            'min_human_delay': 0.5,
            'max_human_delay': 3.5,
            'lot_variance_pct': 3.0,
            'tp_sl_variance_pct': 1.0,
            'candle_offset_range': (1, 5)
        }
    
    @pytest.fixture
    def mock_exchange(self):
        exchange = AsyncMock()
        return exchange
    
    @pytest.fixture
    def executor(self, mock_exchange, config, temp_dir):
        return OrderExecutor(mock_exchange, config, data_dir=temp_dir)
    
    def test_randomize_lot_size_within_variance(self, executor):
        base_size = 1.0
        
        sizes = [executor.randomize_lot_size(base_size) for _ in range(100)]
        
        for size in sizes:
            variance = abs(size - base_size) / base_size * 100
            assert variance <= 3.0
    
    def test_randomize_tp_sl_within_variance(self, executor):
        price = 100.0
        
        prices = [executor.randomize_tp_sl(price, is_tp=True) for _ in range(100)]
        
        for p in prices:
            variance = abs(p - price) / price * 100
            assert variance <= 1.0
    
    def test_partial_close_percentages(self, executor):
        tp1_pct, tp2_pct, runner_pct = executor.randomize_partial_close_percentages()
        
        assert 0.28 <= tp1_pct <= 0.35
        assert 0.38 <= tp2_pct <= 0.42
        assert abs(tp1_pct + tp2_pct + runner_pct - 1.0) < 0.001
    
    def test_order_validation_spread_check(self, executor):
        bid = 100.0
        ask = 100.1
        
        valid, reason = executor.order_validation(
            bid=bid,
            ask=ask,
            spread_threshold=0.05,
            expected_price=100.05,
            actual_price=100.05
        )
        
        assert valid is False
        assert "Spread" in reason
    
    def test_order_validation_slippage_check(self, executor):
        bid = 100.0
        ask = 100.005
        
        valid, reason = executor.order_validation(
            bid=bid,
            ask=ask,
            spread_threshold=0.1,
            expected_price=100.0,
            actual_price=100.1
        )
        
        assert valid is False
        assert "Slippage" in reason
    
    @pytest.mark.asyncio
    async def test_submit_order_with_retry_success(self, executor, mock_exchange):
        mock_exchange.create_order.return_value = {
            'id': '12345',
            'symbol': 'BTC/USDT',
            'side': 'buy',
            'amount': 0.1
        }
        
        result = await executor.submit_order_with_retry(
            symbol='BTC/USDT',
            direction='BUY',
            position_size=0.1,
            entry_price=100.0,
            stop_loss=95.0,
            tp1_price=105.0,
            tp2_price=110.0
        )
        
        assert result is not None
        assert result['id'] == '12345'
        assert mock_exchange.create_order.called
    
    @pytest.mark.asyncio
    async def test_submit_order_with_retry_failure(self, executor, mock_exchange):
        mock_exchange.create_order.side_effect = Exception("Connection failed")
        
        result = await executor.submit_order_with_retry(
            symbol='BTC/USDT',
            direction='BUY',
            position_size=0.1,
            entry_price=100.0,
            stop_loss=95.0,
            tp1_price=105.0,
            tp2_price=110.0
        )
        
        assert result is None
        assert mock_exchange.create_order.call_count >= 3


class TestFirstRunSafetyTrade:
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def safety_trade(self, temp_dir):
        return FirstRunSafetyTrade(data_dir=temp_dir)
    
    def test_first_run_detection_missing_marker(self, safety_trade):
        is_first_run, reason = safety_trade.check_first_run_status()
        assert is_first_run is True
        assert "Marker file missing" in reason
    
    def test_first_run_detection_empty_history(self, safety_trade, temp_dir):
        marker_file = Path(temp_dir) / "hydra_first_run.done"
        marker_file.write_text("test")
        
        trade_history_file = Path(temp_dir) / "trade_history.json"
        trade_history_file.write_text("[]")
        
        is_first_run, reason = safety_trade.check_first_run_status()
        assert is_first_run is True
    
    def test_marker_file_creation(self, safety_trade, temp_dir):
        safety_trade.create_marker_file()
        
        marker_file = Path(temp_dir) / "hydra_first_run.done"
        assert marker_file.exists()
    
    @pytest.mark.asyncio
    async def test_execute_safety_trade(self, safety_trade):
        mock_executor = AsyncMock()
        mock_executor.submit_order_with_retry.return_value = {
            'id': 'safety_123',
            'amount': 0.02
        }
        
        result = await safety_trade.execute_safety_trade(
            executor=mock_executor,
            symbol='BTC/USDT',
            signal_direction='BUY',
            current_price=50000.0,
            account_balance=10000.0
        )
        
        assert result is not None
        assert result['id'] == 'safety_123'


class TestStateManager:
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def state_manager(self, temp_dir):
        return StateManager(data_dir=temp_dir)
    
    def test_save_and_load_trade_history(self, state_manager, temp_dir):
        trade = {
            'entry_time': datetime.utcnow().isoformat(),
            'symbol': 'BTC/USDT',
            'direction': 'BUY',
            'entry_price': 100.0,
            'exit_price': 105.0,
            'pnl': 500.0
        }
        
        state_manager.save_trade_history(trade)
        trades = state_manager.load_trade_history()
        
        assert len(trades) == 1
        assert trades[0]['symbol'] == 'BTC/USDT'
    
    def test_save_and_load_open_positions(self, state_manager, temp_dir):
        positions = [
            {
                'symbol': 'BTC/USDT',
                'direction': 'BUY',
                'entry_price': 100.0,
                'current_price': 102.0,
                'position_size': 0.1
            }
        ]
        
        state_manager.save_open_positions(positions)
        loaded_positions = state_manager.load_open_positions()
        
        assert len(loaded_positions) == 1
        assert loaded_positions[0]['symbol'] == 'BTC/USDT'
    
    def test_atomic_write_operations(self, state_manager, temp_dir):
        positions = [{'symbol': 'BTC/USDT', 'direction': 'BUY'}]
        
        state_manager.save_open_positions(positions)
        
        temp_file = state_manager.open_positions_file.with_suffix('.tmp')
        assert not temp_file.exists()


class TestGracefulShutdown:
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def mock_exchange(self):
        return AsyncMock()
    
    @pytest.fixture
    def state_manager(self, temp_dir):
        return StateManager(data_dir=temp_dir)
    
    @pytest.fixture
    def graceful_shutdown(self, mock_exchange, state_manager):
        return GracefulShutdown(mock_exchange, state_manager)
    
    @pytest.mark.asyncio
    async def test_cancel_pending_orders(self, graceful_shutdown, mock_exchange):
        mock_exchange.fetch_open_orders.return_value = [
            {'id': 'order1', 'symbol': 'BTC/USDT'},
            {'id': 'order2', 'symbol': 'ETH/USDT'}
        ]
        
        await graceful_shutdown.cancel_pending_orders()
        
        assert mock_exchange.cancel_order.call_count == 2
    
    @pytest.mark.asyncio
    async def test_cleanup_timeout(self, graceful_shutdown, mock_exchange):
        mock_exchange.fetch_open_orders.return_value = []
        mock_exchange.close.side_effect = asyncio.sleep(35)
        
        exit_code = await graceful_shutdown.cleanup()
        
        assert exit_code == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])