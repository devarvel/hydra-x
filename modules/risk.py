import asyncio
import json
import logging
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('RiskManager')


@dataclass
class TradeEntry:
    entry_time: str
    symbol: str
    direction: str
    entry_price: float
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    duration_minutes: Optional[int] = None
    exit_reason: Optional[str] = None
    close_time: Optional[str] = None


@dataclass
class OpenPosition:
    symbol: str
    direction: str
    entry_price: float
    current_price: float
    position_size: float
    entry_time: str
    sl_price: float
    tp1_price: float
    tp2_price: float
    pnl_unrealized: float
    status: str = "open"


class RiskManager:
    def __init__(self, config: Dict, data_dir: str = "data"):
        self.config = config
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.account_balance = config.get('account_balance', 10000.0)
        self.risk_percent = config.get('risk_percent', 1.75)
        self.max_spread_points = config.get('max_spread_points', 50)
        self.max_daily_loss_pct = config.get('max_daily_loss', 5.0)
        self.max_consecutive_losses = config.get('max_consecutive_losses', 2)
        self.exchange_min_lot_size = config.get('exchange_min_lot_size', 0.001)
        
        self.daily_pnl_file = self.data_dir / "daily_pnl.json"
        self.consecutive_loss_counter = 0
        self.daily_loss_accumulation = 0.0
        self.shutdown_required = False
        self.shutdown_reason = ""
        
        self._load_daily_pnl()
        logger.info(f"RiskManager initialized with {self.risk_percent}% risk per trade")
    
    def _load_daily_pnl(self) -> None:
        if self.daily_pnl_file.exists():
            try:
                with open(self.daily_pnl_file, 'r') as f:
                    data = json.load(f)
                    today = datetime.utcnow().strftime('%Y-%m-%d')
                    if data.get('date') == today:
                        self.daily_loss_accumulation = float(data.get('cumulative_pnl', 0.0))
                    else:
                        self.daily_loss_accumulation = 0.0
                        self._reset_daily_pnl()
            except Exception as e:
                logger.warning(f"Error loading daily PnL: {e}. Resetting.")
                self.daily_loss_accumulation = 0.0
                self._reset_daily_pnl()
        else:
            self._reset_daily_pnl()
    
    def _reset_daily_pnl(self) -> None:
        daily_pnl_data = {
            'date': datetime.utcnow().strftime('%Y-%m-%d'),
            'cumulative_pnl': 0.0,
            'trades_today': 0,
            'winning_trades': 0,
            'losing_trades': 0
        }
        self._save_daily_pnl(daily_pnl_data)
    
    def _save_daily_pnl(self, data: Dict) -> None:
        try:
            with open(self.daily_pnl_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving daily PnL: {e}")
    
    def position_size(self, entry_price: float, stop_loss: float) -> float:
        if entry_price == stop_loss:
            logger.error("Entry price equals stop loss - cannot calculate position size")
            return 0.0
        
        risk_amount = self.account_balance * (self.risk_percent / 100.0)
        sl_distance = abs(entry_price - stop_loss)
        calculated_size = risk_amount / sl_distance
        
        final_size = max(calculated_size, self.exchange_min_lot_size)
        final_size = round(final_size, 8)
        
        logger.info(f"Position size calculated: {final_size} (Risk: ${risk_amount:.2f}, SL distance: {sl_distance:.2f})")
        return final_size
    
    def spread_filter(self, bid: float, ask: float) -> bool:
        if bid <= 0 or ask <= 0 or bid > ask:
            logger.error(f"Invalid bid/ask: bid={bid}, ask={ask}")
            return False
        
        spread_points = (ask - bid) / bid * 10000
        is_valid = spread_points < self.max_spread_points
        
        if not is_valid:
            logger.warning(f"Spread filter rejected: {spread_points:.1f} points > {self.max_spread_points} max")
        
        return is_valid
    
    def track_daily_pnl(self, pnl: float, symbol: str = "") -> None:
        self.daily_loss_accumulation += pnl
        
        try:
            with open(self.daily_pnl_file, 'r') as f:
                data = json.load(f)
        except:
            data = {
                'date': datetime.utcnow().strftime('%Y-%m-%d'),
                'cumulative_pnl': 0.0,
                'trades_today': 0,
                'winning_trades': 0,
                'losing_trades': 0
            }
        
        data['cumulative_pnl'] = round(float(data['cumulative_pnl']) + pnl, 8)
        data['trades_today'] = int(data.get('trades_today', 0)) + 1
        
        if pnl > 0:
            data['winning_trades'] = int(data.get('winning_trades', 0)) + 1
        else:
            data['losing_trades'] = int(data.get('losing_trades', 0)) + 1
        
        self._save_daily_pnl(data)
        logger.info(f"Daily PnL updated: {data['cumulative_pnl']:.2f} (Total trades: {data['trades_today']})")
    
    def check_daily_loss_limit(self) -> Tuple[bool, str]:
        max_daily_loss = self.account_balance * (self.max_daily_loss_pct / 100.0)
        
        if self.daily_loss_accumulation <= -max_daily_loss:
            reason = f"Daily loss limit exceeded: {self.daily_loss_accumulation:.2f} <= -{max_daily_loss:.2f}"
            logger.error(reason)
            return False, reason
        
        return True, ""
    
    def increment_consecutive_losses(self) -> Tuple[bool, str]:
        self.consecutive_loss_counter += 1
        
        if self.consecutive_loss_counter >= self.max_consecutive_losses:
            reason = f"Consecutive loss limit reached: {self.consecutive_loss_counter} >= {self.max_consecutive_losses}"
            logger.error(reason)
            return False, reason
        
        logger.info(f"Consecutive losses: {self.consecutive_loss_counter}")
        return True, ""
    
    def reset_consecutive_losses(self) -> None:
        self.consecutive_loss_counter = 0
        logger.info("Consecutive loss counter reset on winning trade")
    
    def slippage_tracker(self, expected_price: float, actual_price: float) -> Tuple[bool, float]:
        if expected_price <= 0:
            return False, 0.0
        
        slippage_pct = abs(actual_price - expected_price) / expected_price * 100.0
        is_acceptable = slippage_pct < 0.05
        
        if not is_acceptable:
            logger.warning(f"Slippage exceeded: {slippage_pct:.4f}% > 0.05%")
        
        return is_acceptable, slippage_pct
    
    def get_status(self) -> Dict:
        return {
            'account_balance': self.account_balance,
            'daily_loss_accumulation': self.daily_loss_accumulation,
            'consecutive_losses': self.consecutive_loss_counter,
            'max_daily_loss': self.account_balance * (self.max_daily_loss_pct / 100.0),
            'shutdown_required': self.shutdown_required,
            'shutdown_reason': self.shutdown_reason
        }