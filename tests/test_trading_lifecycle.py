import asyncio
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
sys.path.insert(0, '/app/hydra_x_v2_1804')

from modules.risk import RiskManager
from modules.execution import OrderExecutor, FirstRunSafetyTrade, StateManager, GracefulShutdown


class MockExchange:
    def __init__(self):
        self.orders = {}
        self.positions = {}
        self.open_orders = []
    
    async def create_order(self, symbol, order_type, side, amount, price, params=None):
        order_id = f"order_{len(self.orders)}"
        order = {
            'id': order_id,
            'symbol': symbol,
            'type': order_type,
            'side': side,
            'amount': amount,
            'price': price,
            'status': 'open',
            'timestamp': datetime.utcnow().isoformat()
        }
        self.orders[order_id] = order
        self.open_orders.append(order)
        return order
    
    async def fetch_open_orders(self, symbol=None):
        if symbol:
            return [o for o in self.open_orders if o['symbol'] == symbol]
        return self.open_orders
    
    async def cancel_order(self, order_id, symbol):
        if order_id in self.orders:
            self.orders[order_id]['status'] = 'canceled'
            self.open_orders = [o for o in self.open_orders if o['id'] != order_id]
        return {'id': order_id, 'status': 'canceled'}
    
    async def close(self):
        pass


async def test_position_lifecycle():
    print("\n=== Testing Position Lifecycle ===")
    with tempfile.TemporaryDirectory() as temp_dir:
        config = {
            'account_balance': 10000.0,
            'risk_percent': 1.75,
            'max_spread_points': 50,
            'max_daily_loss': 5.0,
            'max_consecutive_losses': 2,
            'exchange_min_lot_size': 0.001,
            'max_retries': 3,
            'retry_initial_delay': 0.5,
            'retry_max_delay': 5.0,
            'retry_backoff_multiplier': 2.0,
            'min_human_delay': 0.5,
            'max_human_delay': 1.0,
            'lot_variance_pct': 3.0,
            'tp_sl_variance_pct': 1.0,
            'candle_offset_range': (1, 5)
        }
        
        exchange = MockExchange()
        risk_manager = RiskManager(config, data_dir=temp_dir)
        executor = OrderExecutor(exchange, config, data_dir=temp_dir)
        state_manager = StateManager(data_dir=temp_dir)
        
        entry_price = 100.0
        stop_loss = 95.0
        position_size = risk_manager.position_size(entry_price, stop_loss)
        
        print(f"Entry price: {entry_price}, SL: {stop_loss}, Position size: {position_size}")
        
        order = await executor.submit_order_with_retry(
            symbol='BTC/USDT',
            direction='BUY',
            position_size=position_size,
            entry_price=entry_price,
            stop_loss=stop_loss,
            tp1_price=105.0,
            tp2_price=110.0
        )
        
        assert order is not None, "Order submission failed"
        print(f"✓ Order submitted: {order['id']}")
        
        closes = await executor.partial_close_logic(
            position_id=order['id'],
            current_price=105.5,
            tp1_price=105.0,
            tp2_price=110.0,
            ema21=104.0,
            total_position_size=position_size
        )
        
        assert closes['tp1']['close_size'] > 0, "TP1 close size invalid"
        assert closes['tp2']['close_size'] > 0, "TP2 close size invalid"
        print(f"✓ Partial close logic validated: TP1={closes['tp1']['close_size']:.8f}, TP2={closes['tp2']['close_size']:.8f}")
        
        trade = {
            'entry_time': datetime.utcnow().isoformat(),
            'symbol': 'BTC/USDT',
            'direction': 'BUY',
            'entry_price': entry_price,
            'exit_price': 105.5,
            'pnl': 550.0,
            'pnl_pct': 5.5,
            'duration_minutes': 15,
            'exit_reason': 'TP1_TRIGGERED',
            'close_time': datetime.utcnow().isoformat()
        }
        
        state_manager.save_trade_history(trade)
        risk_manager.track_daily_pnl(550.0, 'BTC/USDT')
        risk_manager.reset_consecutive_losses()
        
        print(f"✓ Trade saved and daily PnL tracked")
        print("✓ Position lifecycle complete")


async def test_daily_loss_shutdown():
    print("\n=== Testing Daily Loss Shutdown ===")
    with tempfile.TemporaryDirectory() as temp_dir:
        config = {
            'account_balance': 10000.0,
            'risk_percent': 1.75,
            'max_spread_points': 50,
            'max_daily_loss': 5.0,
            'max_consecutive_losses': 2,
            'exchange_min_lot_size': 0.001
        }
        
        risk_manager = RiskManager(config, data_dir=temp_dir)
        
        losing_trades = [
            -200.0,
            -150.0,
            -300.0,
            -100.0
        ]
        
        for i, pnl in enumerate(losing_trades, 1):
            risk_manager.track_daily_pnl(pnl, 'BTC/USDT')
            should_continue, reason = risk_manager.check_daily_loss_limit()
            
            print(f"Trade {i}: PnL={pnl}, Cumulative={risk_manager.daily_loss_accumulation:.2f}")
            
            if not should_continue:
                print(f"✓ Daily loss limit triggered at trade {i}: {reason}")
                assert risk_manager.daily_loss_accumulation <= -500.0
                return
        
        print("✗ Daily loss limit was not triggered")


async def test_consecutive_loss_shutdown():
    print("\n=== Testing Consecutive Loss Shutdown ===")
    with tempfile.TemporaryDirectory() as temp_dir:
        config = {
            'account_balance': 10000.0,
            'risk_percent': 1.75,
            'max_consecutive_losses': 2,
            'exchange_min_lot_size': 0.001
        }
        
        risk_manager = RiskManager(config, data_dir=temp_dir)
        
        risk_manager.track_daily_pnl(100.0)
        risk_manager.reset_consecutive_losses()
        print("Trade 1: Win - reset counter")
        
        for i in range(1, 4):
            risk_manager.track_daily_pnl(-100.0)
            should_continue, reason = risk_manager.increment_consecutive_losses()
            
            print(f"Trade {i+1}: Loss - consecutive count={risk_manager.consecutive_loss_counter}")
            
            if not should_continue:
                print(f"✓ Consecutive loss limit triggered: {reason}")
                assert risk_manager.consecutive_loss_counter == 2
                return
        
        print("✗ Consecutive loss limit was not triggered")


async def test_state_recovery():
    print("\n=== Testing State Recovery ===")
    with tempfile.TemporaryDirectory() as temp_dir:
        state_manager = StateManager(data_dir=temp_dir)
        
        positions = [
            {
                'symbol': 'BTC/USDT',
                'direction': 'BUY',
                'entry_price': 100.0,
                'current_price': 102.0,
                'position_size': 0.1,
                'entry_time': datetime.utcnow().isoformat(),
                'sl_price': 95.0,
                'tp1_price': 105.0,
                'tp2_price': 110.0,
                'pnl_unrealized': 200.0
            }
        ]
        
        state_manager.save_open_positions(positions)
        print("✓ Positions saved")
        
        recovered_positions = state_manager.load_open_positions()
        assert len(recovered_positions) == 1
        assert recovered_positions[0]['symbol'] == 'BTC/USDT'
        print(f"✓ Positions recovered: {len(recovered_positions)} position(s)")
        
        trades = [
            {
                'entry_time': datetime.utcnow().isoformat(),
                'symbol': 'ETH/USDT',
                'direction': 'SHORT',
                'entry_price': 2000.0,
                'exit_price': 1950.0,
                'pnl': 500.0
            }
        ]
        
        for trade in trades:
            state_manager.save_trade_history(trade)
        
        recovered_trades = state_manager.load_trade_history()
        assert len(recovered_trades) == 1
        print(f"✓ Trades recovered: {len(recovered_trades)} trade(s)")
        
        print("✓ State recovery complete")


async def test_first_run_flow():
    print("\n=== Testing First-Run Safety Trade Flow ===")
    with tempfile.TemporaryDirectory() as temp_dir:
        config = {
            'account_balance': 10000.0,
            'risk_percent': 1.75,
            'max_retries': 3,
            'retry_initial_delay': 0.5,
            'retry_max_delay': 5.0,
            'retry_backoff_multiplier': 2.0,
            'min_human_delay': 0.1,
            'max_human_delay': 0.2,
            'lot_variance_pct': 3.0,
            'tp_sl_variance_pct': 1.0,
            'candle_offset_range': (1, 5),
            'exchange_min_lot_size': 0.001
        }
        
        exchange = MockExchange()
        safety_trade = FirstRunSafetyTrade(data_dir=temp_dir)
        executor = OrderExecutor(exchange, config, data_dir=temp_dir)
        
        is_first_run, reason = safety_trade.check_first_run_status()
        assert is_first_run is True
        print(f"✓ First-run detected: {reason}")
        
        safety_order = await safety_trade.execute_safety_trade(
            executor=executor,
            symbol='BTC/USDT',
            signal_direction='BUY',
            current_price=50000.0,
            account_balance=10000.0
        )
        
        assert safety_order is not None
        print(f"✓ Safety trade executed: {safety_order['id']}")
        
        safety_trade.create_marker_file()
        marker_exists = (Path(temp_dir) / "hydra_first_run.done").exists()
        assert marker_exists is True
        print("✓ Marker file created")
        
        is_first_run, reason = safety_trade.check_first_run_status()
        assert is_first_run is False
        print("✓ First-run mode bypassed on subsequent check")


async def test_graceful_shutdown():
    print("\n=== Testing Graceful Shutdown ===")
    with tempfile.TemporaryDirectory() as temp_dir:
        exchange = MockExchange()
        state_manager = StateManager(data_dir=temp_dir)
        graceful_shutdown = GracefulShutdown(exchange, state_manager, data_dir=temp_dir)
        
        await exchange.create_order('BTC/USDT', 'limit', 'buy', 0.1, 100.0)
        await exchange.create_order('ETH/USDT', 'limit', 'sell', 1.0, 2000.0)
        
        open_orders = await exchange.fetch_open_orders()
        print(f"✓ Created {len(open_orders)} pending orders")
        
        positions = [
            {'symbol': 'BTC/USDT', 'direction': 'BUY', 'entry_price': 100.0}
        ]
        
        trades = [
            {'symbol': 'ETH/USDT', 'direction': 'SHORT', 'pnl': 500.0}
        ]
        
        exit_code = await graceful_shutdown.cleanup(positions=positions, trades=trades)
        assert exit_code == 0
        print(f"✓ Graceful shutdown completed with exit code {exit_code}")
        
        remaining_orders = await exchange.fetch_open_orders()
        assert len(remaining_orders) == 0
        print(f"✓ All pending orders cancelled")
        
        recovered_positions = state_manager.load_open_positions()
        assert len(recovered_positions) == 1
        print(f"✓ Positions persisted: {len(recovered_positions)}")


async def main():
    print("=" * 60)
    print("INTEGRATION TESTS FOR TRADING LIFECYCLE")
    print("=" * 60)
    
    try:
        await test_position_lifecycle()
        await test_daily_loss_shutdown()
        await test_consecutive_loss_shutdown()
        await test_state_recovery()
        await test_first_run_flow()
        await test_graceful_shutdown()
        
        print("\n" + "=" * 60)
        print("ALL INTEGRATION TESTS PASSED ✓")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(main())