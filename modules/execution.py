import asyncio
import logging
import sys
import json
import random
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, List, Any
import os
import signal
import functools
from unittest.mock import AsyncMock

sys.stdout.flush()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)


class StateManager:
    def __init__(self, data_dir: str = 'data'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.trade_history_file = self.data_dir / "trade_history.json"
        self.open_positions_file = self.data_dir / "open_positions.json"
        self.logger = logging.getLogger('OrderExecutor')
        self.logger.info("StateManager initialized")
    
    def save_trade_history(self, trade: Dict[str, Any]) -> None:
        trades = self.load_trade_history()
        trades.append(trade)
        
        temp_file = self.trade_history_file.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(trades, f, indent=2, default=str)
        os.rename(temp_file, self.trade_history_file)
        
        self.logger.info(f"Trade history saved: {len(trades)} trades total")
    
    def load_trade_history(self) -> List[Dict]:
        if not self.trade_history_file.exists():
            return []
        
        try:
            with open(self.trade_history_file, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def save_open_positions(self, positions: List[Dict]) -> None:
        temp_file = self.open_positions_file.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(positions, f, indent=2, default=str)
        os.rename(temp_file, self.open_positions_file)
        
        self.logger.info(f"Open positions saved: {len(positions)} positions")
    
    def load_open_positions(self) -> List[Dict]:
        if not self.open_positions_file.exists():
            return []
        
        try:
            with open(self.open_positions_file, 'r') as f:
                return json.load(f)
        except:
            return []


class FirstRunSafetyTrade:
    def __init__(self, data_dir: str = 'data'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.marker_file = self.data_dir / "hydra_first_run.done"
        self.trade_history_file = self.data_dir / "trade_history.json"
        self.logger = logging.getLogger('OrderExecutor')
        self.logger.info("FirstRunSafetyTrade initialized")
    
    def check_first_run_status(self) -> Tuple[bool, str]:
        if not self.marker_file.exists():
            return True, "Marker file missing - first run detected"
        
        if not self.trade_history_file.exists():
            return True, "No trade history found - first run detected"
        
        try:
            with open(self.trade_history_file, 'r') as f:
                trades = json.load(f)
            
            if not trades:
                return True, "Empty trade history - first run detected"
            
            last_trade = trades[-1]
            last_trade_time = datetime.fromisoformat(last_trade.get('close_time', last_trade.get('entry_time', datetime.utcnow().isoformat())))
            days_since = (datetime.utcnow() - last_trade_time).days
            
            if days_since >= 30:
                return True, f"No trades in last 30 days ({days_since} days) - first run mode"
            
            return False, "Trading history exists and recent"
        except:
            return True, "Error reading trade history - first run mode"
    
    def create_marker_file(self) -> None:
        self.marker_file.write_text(f"First run completed at {datetime.utcnow().isoformat()}")
        self.logger.info(f"Marker file created: {self.marker_file}")
    
    async def execute_safety_trade(
        self,
        executor: 'OrderExecutor',
        symbol: str,
        signal_direction: str,
        current_price: float,
        account_balance: float
    ) -> Optional[Dict]:
        safety_risk_pct = 0.02
        safety_risk_amount = account_balance * (safety_risk_pct / 100)
        
        sl_distance = current_price * 0.01
        safety_position_size = safety_risk_amount / sl_distance if sl_distance > 0 else 0.001
        safety_position_size = max(safety_position_size, 0.001)
        
        sl_price = current_price - sl_distance if signal_direction == 'BUY' else current_price + sl_distance
        tp1_price = current_price + (sl_distance * 1.5) if signal_direction == 'BUY' else current_price - (sl_distance * 1.5)
        tp2_price = current_price + (sl_distance * 2.5) if signal_direction == 'BUY' else current_price - (sl_distance * 2.5)
        
        self.logger.info(f"Executing safety trade: {symbol} {signal_direction} size={safety_position_size:.8f}")
        
        order = await executor.submit_order_with_retry(
            symbol=symbol,
            direction=signal_direction,
            position_size=safety_position_size,
            entry_price=current_price,
            stop_loss=sl_price,
            tp1_price=tp1_price,
            tp2_price=tp2_price
        )
        
        return order


class OrderExecutor:
    def __init__(self, exchange, config: Dict, data_dir: str = 'data'):
        self.exchange = exchange
        self.config = config
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_manager = StateManager(data_dir=str(self.data_dir))
        self.logger = logging.getLogger('OrderExecutor')
        self.logger.info("OrderExecutor initialized")
    
    def randomize_lot_size(self, base_size: float) -> float:
        variance_pct = self.config.get('lot_variance_pct', 3.0)
        variance_factor = random.gauss(1.0, variance_pct / 100 / 3)
        randomized_size = base_size * variance_factor
        variance = (randomized_size - base_size) / base_size * 100
        self.logger.info(f"Lot size randomized: {base_size:.8f} -> {randomized_size:.8f} (variance: {variance:.2f}%)")
        return randomized_size
    
    def randomize_tp_sl(self, price: float, is_tp: bool = True) -> float:
        variance_pct = self.config.get('tp_sl_variance_pct', 1.0)
        variance_factor = random.uniform(1.0 - variance_pct / 100, 1.0 + variance_pct / 100)
        randomized_price = price * variance_factor
        variance = (randomized_price - price) / price * 100
        label = "TP" if is_tp else "SL"
        self.logger.info(f"{label} randomized: {price:.2f} -> {randomized_price:.2f} (variance: {variance:.2f}%)")
        return randomized_price
    
    def randomize_partial_close_percentages(self) -> Tuple[float, float, float]:
        tp1_pct = random.uniform(0.28, 0.35)
        tp2_pct = random.uniform(0.38, 0.42)
        runner_pct = 1.0 - tp1_pct - tp2_pct
        
        self.logger.info(f"Partial close percentages: TP1={tp1_pct*100:.1f}%, TP2={tp2_pct*100:.1f}%, Runner={runner_pct*100:.1f}%")
        return tp1_pct, tp2_pct, runner_pct
    
    def order_validation(
        self,
        bid: float,
        ask: float,
        spread_threshold: float,
        expected_price: float,
        actual_price: float,
        max_slippage_pct: float = 0.05
    ) -> Tuple[bool, str]:
        spread_points = (ask - bid) / bid * 10000
        if spread_points > spread_threshold:
            return False, f"Spread {spread_points:.2f} > {spread_threshold} threshold"
        
        slippage_pct = abs(actual_price - expected_price) / expected_price * 100
        if slippage_pct > max_slippage_pct:
            return False, f"Slippage {slippage_pct:.4f}% > {max_slippage_pct}% threshold"
        
        return True, "Validation passed"
    
    async def add_human_like_delay(self) -> None:
        min_delay = self.config.get('min_human_delay', 0.5)
        max_delay = self.config.get('max_human_delay', 3.5)
        delay = random.uniform(min_delay, max_delay)
        self.logger.info(f"Adding human-like delay: {delay:.2f}s")
        await asyncio.sleep(delay)
    
    async def submit_order_with_retry(
        self,
        symbol: str,
        direction: str,
        position_size: float,
        entry_price: float,
        stop_loss: float,
        tp1_price: float,
        tp2_price: float
    ) -> Optional[Dict]:
        max_retries = self.config.get('max_retries', 3)
        initial_delay = self.config.get('retry_initial_delay', 0.5)
        max_delay = self.config.get('retry_max_delay', 5.0)
        backoff_multiplier = self.config.get('retry_backoff_multiplier', 2.0)
        
        randomized_size = self.randomize_lot_size(position_size)
        randomized_tp1 = self.randomize_tp_sl(tp1_price, is_tp=True)
        randomized_tp2 = self.randomize_tp_sl(tp2_price, is_tp=True)
        randomized_sl = self.randomize_tp_sl(stop_loss, is_tp=False)
        
        await self.add_human_like_delay()
        
        for attempt in range(1, max_retries + 1):
            try:
                order_params = {
                    'symbol': symbol,
                    'direction': direction,
                    'size': randomized_size,
                    'entry_price': entry_price,
                    'stop_loss': randomized_sl,
                    'tp1': randomized_tp1,
                    'tp2': randomized_tp2,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                self.logger.info(f"Attempt {attempt}/{max_retries}: Submitting order - {order_params}")
                
                order = await self.exchange.create_order(
                    symbol=symbol,
                    order_type='limit',
                    side=direction.lower(),
                    amount=randomized_size,
                    price=entry_price
                )
                
                self.logger.info(f"Order submitted successfully: {order}")
                return order
            
            except Exception as e:
                self.logger.warning(f"Attempt {attempt} failed: {e}")
                
                if attempt < max_retries:
                    delay = min(initial_delay * (backoff_multiplier ** (attempt - 1)), max_delay)
                    delay += random.uniform(-0.1, 0.1)
                    self.logger.info(f"Retrying in {delay:.2f}s...")
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(f"Order submission failed after {max_retries} attempts")
                    return None
        
        return None
    
    async def partial_close_logic(
        self,
        position_id: str,
        current_price: float,
        tp1_price: float,
        tp2_price: float,
        ema21: float,
        total_position_size: float
    ) -> Dict:
        tp1_pct, tp2_pct, runner_pct = self.randomize_partial_close_percentages()
        
        self.logger.info(f"Partial close plan: TP1={tp1_pct*100:.1f}%, TP2={tp2_pct*100:.1f}%, Runner={runner_pct*100:.1f}%")
        
        return {
            'tp1': {
                'close_size': total_position_size * tp1_pct,
                'close_price': tp1_price,
                'percentage': tp1_pct * 100
            },
            'tp2': {
                'close_size': total_position_size * tp2_pct,
                'close_price': tp2_price,
                'percentage': tp2_pct * 100
            },
            'runner': {
                'close_size': total_position_size * runner_pct,
                'trail_target': ema21,
                'percentage': runner_pct * 100
            }
        }


class GracefulShutdown:
    def __init__(self, exchange, state_manager: StateManager, data_dir: str = 'data'):
        self.exchange = exchange
        self.state_manager = state_manager
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger('OrderExecutor')
        self.shutdown_flag = False
    
    async def cancel_pending_orders(self) -> None:
        try:
            open_orders = await self.exchange.fetch_open_orders()
            self.logger.info(f"Cancelling {len(open_orders)} pending orders...")
            
            for order in open_orders:
                try:
                    await self.exchange.cancel_order(order['id'], order['symbol'])
                    self.logger.info(f"Cancelled order: {order['id']}")
                except Exception as e:
                    self.logger.warning(f"Failed to cancel order {order['id']}: {e}")
        except Exception as e:
            self.logger.error(f"Error fetching open orders: {e}")
    
    async def cleanup(
        self,
        positions: Optional[List[Dict]] = None,
        trades: Optional[List[Dict]] = None
    ) -> int:
        self.logger.info("Initiating graceful shutdown...")
        
        try:
            await asyncio.wait_for(self.cancel_pending_orders(), timeout=30)
        except asyncio.TimeoutError:
            self.logger.error("Timeout cancelling pending orders")
            return 1
        
        if positions:
            self.state_manager.save_open_positions(positions)
        
        if trades:
            for trade in trades:
                self.state_manager.save_trade_history(trade)
        
        try:
            await self.exchange.close()
            self.logger.info("Exchange connection closed")
        except Exception as e:
            self.logger.warning(f"Error closing exchange: {e}")
        
        self.logger.info("Graceful shutdown complete")
        return 0