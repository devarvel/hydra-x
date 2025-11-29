"""
Helper module for reading and parsing bot state JSON files.
Provides safe access to account metrics, positions, trades, and status.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class DashboardStateReader:
    """Reads and parses bot state JSON files with error handling."""
    
    def __init__(self, data_dir: str = "/app/hydra_x_v2_1804/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def read_json_safe(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Safely read JSON file with error handling."""
        try:
            if not file_path.exists():
                logger.debug(f"File not found: {file_path.name}")
                return None
            with open(file_path, 'r') as f:
                data = json.load(f)
                if data is None:
                    return None
                return data
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted JSON in {file_path.name}: {str(e)}")
            return None
        except FileNotFoundError as e:
            logger.debug(f"File not found: {file_path.name}")
            return None
        except Exception as e:
            logger.error(f"Error reading {file_path.name}: {str(e)}")
            return None
    
    def read_account_metrics(self) -> Dict[str, Any]:
        """Read account metrics from daily_summary_state.json."""
        state_file = self.data_dir / "daily_summary_state.json"
        
        if not state_file.exists():
            logger.debug(f"Account metrics file not found: {state_file}")
            return {
                "balance": 0.0,
                "equity": 0.0,
                "free_margin": 0.0,
                "margin_ratio_pct": 0.0,
                "drawdown_pct": 0.0,
                "daily_pnl": 0.0,
                "daily_pnl_pct": 0.0,
                "available": False
            }
        
        data = self.read_json_safe(state_file)
        
        if not data:
            logger.debug("Account metrics data is None or empty")
            return {
                "balance": 0.0,
                "equity": 0.0,
                "free_margin": 0.0,
                "margin_ratio_pct": 0.0,
                "drawdown_pct": 0.0,
                "daily_pnl": 0.0,
                "daily_pnl_pct": 0.0,
                "available": False
            }
        
        balance = float(data.get("balance", 0.0))
        equity = float(data.get("equity", 0.0))
        drawdown_pct = float(data.get("drawdown_pct", 0.0))
        daily_pnl = float(data.get("daily_pnl", 0.0))
        
        free_margin = equity - (equity * float(data.get("margin_used_pct", 0.0)) / 100)
        margin_ratio = float(data.get("margin_ratio_pct", 0.0))
        
        return {
            "balance": balance,
            "equity": equity,
            "free_margin": max(0, free_margin),
            "margin_ratio_pct": margin_ratio,
            "drawdown_pct": drawdown_pct,
            "daily_pnl": daily_pnl,
            "daily_pnl_pct": (daily_pnl / balance * 100) if balance > 0 else 0.0,
            "available": True
        }
    
    def read_open_positions(self) -> List[Dict[str, Any]]:
        """Read open positions from open_positions.json."""
        state_file = self.data_dir / "open_positions.json"
        data = self.read_json_safe(state_file)
        
        if not data or not isinstance(data, list):
            return []
        
        positions = []
        for pos in data:
            try:
                entry_price = float(pos.get("entry_price", 0))
                current_price = float(pos.get("current_price", 0))
                position_size = float(pos.get("position_size", 0))
                
                unrealized_pnl = 0.0
                if "direction" in pos and current_price > 0:
                    direction = pos.get("direction").upper()
                    if direction == "LONG":
                        unrealized_pnl = position_size * (current_price - entry_price)
                    else:
                        unrealized_pnl = position_size * (entry_price - current_price)
                
                sl_price = float(pos.get("sl", 0))
                pct_to_sl = 0.0
                if sl_price > 0 and entry_price > 0:
                    pct_to_sl = abs((current_price - sl_price) / (entry_price - sl_price) * 100) if entry_price != sl_price else 0
                
                positions.append({
                    "symbol": pos.get("symbol", "N/A"),
                    "direction": pos.get("direction", "N/A").upper(),
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "unrealized_pnl": unrealized_pnl,
                    "unrealized_pnl_pct": (unrealized_pnl / (position_size * entry_price) * 100) if (position_size * entry_price) > 0 else 0,
                    "position_size": position_size,
                    "sl": sl_price,
                    "tp": float(pos.get("tp", 0)),
                    "tp1": float(pos.get("tp1", 0)),
                    "tp2": float(pos.get("tp2", 0)),
                    "entry_time": pos.get("entry_time", "N/A"),
                    "pct_to_sl": pct_to_sl,
                    "risk_pct": float(pos.get("risk_pct", 0.0))
                })
            except (ValueError, KeyError) as e:
                logger.debug(f"Error parsing position: {str(e)}")
                continue
        
        return positions
    
    def read_trade_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Read closed trade history from trade_history.json."""
        state_file = self.data_dir / "trade_history.json"
        data = self.read_json_safe(state_file)
        
        if not data or not isinstance(data, list):
            return []
        
        trades = []
        for trade in data[-limit:]:
            try:
                entry_price = float(trade.get("entry_price", 0))
                exit_price = float(trade.get("exit_price", 0))
                position_size = float(trade.get("position_size", 0))
                
                pnl = 0.0
                if "direction" in trade and entry_price > 0:
                    direction = trade.get("direction").upper()
                    if direction == "LONG":
                        pnl = position_size * (exit_price - entry_price)
                    else:
                        pnl = position_size * (entry_price - exit_price)
                
                pnl_pct = (pnl / (position_size * entry_price) * 100) if (position_size * entry_price) > 0 else 0
                
                entry_time = trade.get("entry_time", "N/A")
                exit_time = trade.get("exit_time", "N/A")
                
                duration = "N/A"
                if entry_time != "N/A" and exit_time != "N/A":
                    try:
                        entry_dt = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
                        exit_dt = datetime.fromisoformat(exit_time.replace("Z", "+00:00"))
                        delta = exit_dt - entry_dt
                        hours = delta.total_seconds() // 3600
                        minutes = (delta.total_seconds() % 3600) // 60
                        duration = f"{int(hours):02d}:{int(minutes):02d}"
                    except:
                        pass
                
                trades.append({
                    "entry_time": entry_time,
                    "symbol": trade.get("symbol", "N/A"),
                    "direction": trade.get("direction", "N/A").upper(),
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "duration": duration,
                    "exit_reason": trade.get("exit_reason", "N/A"),
                    "exit_time": exit_time
                })
            except (ValueError, KeyError) as e:
                logger.debug(f"Error parsing trade: {str(e)}")
                continue
        
        return sorted(trades, key=lambda x: x["entry_time"], reverse=True)
    
    def read_bot_status(self) -> Dict[str, Any]:
        """Read bot status from daily_summary_state.json."""
        state_file = self.data_dir / "daily_summary_state.json"
        data = self.read_json_safe(state_file)
        
        if not data:
            return {
                "status": "UNKNOWN",
                "consecutive_losses": 0,
                "daily_trade_count": 0,
                "shutdown_reason": "",
                "last_update": "N/A",
                "available": False
            }
        
        return {
            "status": data.get("status", "UNKNOWN"),
            "consecutive_losses": int(data.get("consecutive_losses", 0)),
            "daily_trade_count": int(data.get("daily_trade_count", 0)),
            "shutdown_reason": data.get("shutdown_reason", ""),
            "last_update": data.get("last_update", "N/A"),
            "available": True
        }
    
    def read_trend_data(self) -> Dict[str, Any]:
        """Read trend data from signal_generator cache if available."""
        trend_file = self.data_dir / "trend_cache.json"
        data = self.read_json_safe(trend_file)
        
        if not data:
            return {}
        
        return data
    
    def read_pa_confirmation(self) -> Dict[str, Any]:
        """Read price action confirmation data from cache."""
        pa_file = self.data_dir / "pa_confirmation_cache.json"
        data = self.read_json_safe(pa_file)
        
        if not data:
            return {
                "confirmation_count": 0,
                "confirmation_score": 0.0,
                "patterns": []
            }
        
        return data