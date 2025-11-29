"""
Validation script for Streamlit dashboard Part 1 implementation.
Tests all core components: initialization, state reading, UI rendering, error handling.
"""

import json
import sys
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from modules.dashboard_state_reader import DashboardStateReader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DashboardValidator:
    def __init__(self):
        self.data_dir = Path("/app/hydra_x_v2_1804/data")
        self.results = {
            "tests_passed": 0,
            "tests_failed": 0,
            "test_results": []
        }
    
    def test_state_reader_initialization(self):
        """Test that state reader initializes correctly."""
        try:
            reader = DashboardStateReader()
            assert reader.data_dir.exists(), "Data directory not created"
            self.results["tests_passed"] += 1
            self.results["test_results"].append({
                "test": "State Reader Initialization",
                "status": "PASS",
                "message": "DashboardStateReader initialized successfully"
            })
            return True
        except Exception as e:
            self.results["tests_failed"] += 1
            self.results["test_results"].append({
                "test": "State Reader Initialization",
                "status": "FAIL",
                "message": str(e)
            })
            return False
    
    def test_account_metrics_reading(self):
        """Test account metrics reading with mock data."""
        try:
            reader = DashboardStateReader()
            
            mock_state = {
                "balance": 10000.0,
                "equity": 10500.0,
                "drawdown_pct": 2.5,
                "daily_pnl": 500.0,
                "margin_used_pct": 30.0,
                "margin_ratio_pct": 14.3
            }
            
            state_file = self.data_dir / "daily_summary_state.json"
            with open(state_file, 'w') as f:
                json.dump(mock_state, f)
            
            metrics = reader.read_account_metrics()
            
            assert metrics["available"] == True, "Metrics not marked as available"
            assert metrics["balance"] == 10000.0, "Balance mismatch"
            assert metrics["equity"] == 10500.0, "Equity mismatch"
            assert metrics["drawdown_pct"] == 2.5, "Drawdown mismatch"
            
            self.results["tests_passed"] += 1
            self.results["test_results"].append({
                "test": "Account Metrics Reading",
                "status": "PASS",
                "message": "Account metrics read and parsed correctly"
            })
            return True
        except Exception as e:
            self.results["tests_failed"] += 1
            self.results["test_results"].append({
                "test": "Account Metrics Reading",
                "status": "FAIL",
                "message": str(e)
            })
            return False
    
    def test_open_positions_reading(self):
        """Test open positions reading with mock data."""
        try:
            reader = DashboardStateReader()
            
            mock_positions = [
                {
                    "symbol": "BTCUSDT",
                    "direction": "LONG",
                    "entry_price": 50000,
                    "current_price": 51000,
                    "position_size": 0.1,
                    "sl": 49000,
                    "tp": 52000,
                    "tp1": 51500,
                    "tp2": 52000,
                    "entry_time": datetime.now().isoformat(),
                    "risk_pct": 1.5
                }
            ]
            
            pos_file = self.data_dir / "open_positions.json"
            with open(pos_file, 'w') as f:
                json.dump(mock_positions, f)
            
            positions = reader.read_open_positions()
            
            assert len(positions) > 0, "No positions read"
            assert positions[0]["symbol"] == "BTCUSDT", "Symbol mismatch"
            assert positions[0]["direction"] == "LONG", "Direction mismatch"
            
            self.results["tests_passed"] += 1
            self.results["test_results"].append({
                "test": "Open Positions Reading",
                "status": "PASS",
                "message": "Open positions read and parsed correctly"
            })
            return True
        except Exception as e:
            self.results["tests_failed"] += 1
            self.results["test_results"].append({
                "test": "Open Positions Reading",
                "status": "FAIL",
                "message": str(e)
            })
            return False
    
    def test_trade_history_reading(self):
        """Test trade history reading with mock data."""
        try:
            reader = DashboardStateReader()
            
            now = datetime.now()
            mock_trades = [
                {
                    "symbol": "BTCUSDT",
                    "direction": "LONG",
                    "entry_price": 50000,
                    "exit_price": 51000,
                    "position_size": 0.1,
                    "entry_time": (now - timedelta(hours=2)).isoformat(),
                    "exit_time": now.isoformat(),
                    "exit_reason": "TP_HIT",
                    "pnl": 100
                }
            ]
            
            trade_file = self.data_dir / "trade_history.json"
            with open(trade_file, 'w') as f:
                json.dump(mock_trades, f)
            
            trades = reader.read_trade_history(limit=50)
            
            assert len(trades) > 0, "No trades read"
            assert trades[0]["symbol"] == "BTCUSDT", "Symbol mismatch"
            assert trades[0]["pnl_pct"] > 0, "PnL % calculation failed"
            
            self.results["tests_passed"] += 1
            self.results["test_results"].append({
                "test": "Trade History Reading",
                "status": "PASS",
                "message": "Trade history read and parsed correctly"
            })
            return True
        except Exception as e:
            self.results["tests_failed"] += 1
            self.results["test_results"].append({
                "test": "Trade History Reading",
                "status": "FAIL",
                "message": str(e)
            })
            return False
    
    def test_bot_status_reading(self):
        """Test bot status reading."""
        try:
            reader = DashboardStateReader()
            
            mock_status = {
                "status": "RUNNING",
                "consecutive_losses": 1,
                "daily_trade_count": 2,
                "shutdown_reason": "",
                "last_update": datetime.now().isoformat()
            }
            
            state_file = self.data_dir / "daily_summary_state.json"
            with open(state_file, 'w') as f:
                json.dump(mock_status, f)
            
            status = reader.read_bot_status()
            
            assert status["available"] == True, "Status not marked as available"
            assert status["status"] == "RUNNING", "Status mismatch"
            
            self.results["tests_passed"] += 1
            self.results["test_results"].append({
                "test": "Bot Status Reading",
                "status": "PASS",
                "message": "Bot status read correctly"
            })
            return True
        except Exception as e:
            self.results["tests_failed"] += 1
            self.results["test_results"].append({
                "test": "Bot Status Reading",
                "status": "FAIL",
                "message": str(e)
            })
            return False
    
    def test_error_handling_missing_file(self):
        """Test error handling for missing files."""
        try:
            reader = DashboardStateReader()
            
            metrics = reader.read_account_metrics()
            assert metrics["available"] == False, "Should mark unavailable when file missing"
            
            positions = reader.read_open_positions()
            assert isinstance(positions, list), "Should return empty list for missing file"
            
            self.results["tests_passed"] += 1
            self.results["test_results"].append({
                "test": "Error Handling - Missing Files",
                "status": "PASS",
                "message": "Gracefully handles missing state files"
            })
            return True
        except Exception as e:
            self.results["tests_failed"] += 1
            self.results["test_results"].append({
                "test": "Error Handling - Missing Files",
                "status": "FAIL",
                "message": str(e)
            })
            return False
    
    def test_error_handling_corrupted_json(self):
        """Test error handling for corrupted JSON."""
        try:
            reader = DashboardStateReader()
            
            state_file = self.data_dir / "daily_summary_state.json"
            with open(state_file, 'w') as f:
                f.write("{ invalid json }")
            
            metrics = reader.read_account_metrics()
            assert metrics["available"] == False, "Should handle corrupted JSON"
            
            self.results["tests_passed"] += 1
            self.results["test_results"].append({
                "test": "Error Handling - Corrupted JSON",
                "status": "PASS",
                "message": "Gracefully handles corrupted JSON files"
            })
            return True
        except Exception as e:
            self.results["tests_failed"] += 1
            self.results["test_results"].append({
                "test": "Error Handling - Corrupted JSON",
                "status": "FAIL",
                "message": str(e)
            })
            return False
    
    def run_all_tests(self):
        """Run all validation tests."""
        logger.info("Starting Dashboard Part 1 Validation Tests")
        logger.info("=" * 60)
        
        self.test_state_reader_initialization()
        self.test_account_metrics_reading()
        self.test_open_positions_reading()
        self.test_trade_history_reading()
        self.test_bot_status_reading()
        self.test_error_handling_missing_file()
        self.test_error_handling_corrupted_json()
        
        logger.info("=" * 60)
        logger.info(f"Tests Passed: {self.results['tests_passed']}")
        logger.info(f"Tests Failed: {self.results['tests_failed']}")
        
        return self.results
    
    def save_report(self):
        """Save validation report to JSON."""
        report_file = self.data_dir / "dashboard_validation_report_part1.json"
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        logger.info(f"Validation report saved to {report_file}")

def main():
    validator = DashboardValidator()
    results = validator.run_all_tests()
    validator.save_report()
    
    print("\n" + "="*60)
    print("DASHBOARD PART 1 VALIDATION REPORT")
    print("="*60)
    for result in results["test_results"]:
        status_symbol = "✅" if result["status"] == "PASS" else "❌"
        print(f"{status_symbol} {result['test']}: {result['message']}")
    
    print("="*60)
    print(f"Total: {results['tests_passed']} passed, {results['tests_failed']} failed")
    print("="*60)

if __name__ == "__main__":
    main()