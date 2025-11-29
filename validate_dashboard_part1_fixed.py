import json
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from modules.dashboard_state_reader import DashboardStateReader

class DashboardValidatorFixed:
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
    
    def test_error_handling_missing_file(self):
        """Test error handling for missing files - FIXED VERSION."""
        try:
            reader = DashboardStateReader()
            
            backup_files = {}
            test_files = ["daily_summary_state.json", "open_positions.json", "trade_history.json"]
            
            for filename in test_files:
                filepath = self.data_dir / filename
                if filepath.exists():
                    backup_files[filename] = filepath.read_text()
                    os.remove(filepath)
            
            metrics = reader.read_account_metrics()
            assert metrics["available"] == False, f"Metrics should mark unavailable when file missing, got: {metrics['available']}"
            assert metrics["balance"] == 0.0, "Should return default balance 0.0"
            
            positions = reader.read_open_positions()
            assert isinstance(positions, list), "Should return empty list for missing file"
            assert len(positions) == 0, "Should return empty positions list"
            
            trades = reader.read_trade_history()
            assert isinstance(trades, list), "Should return list for missing trades"
            
            for filename, content in backup_files.items():
                filepath = self.data_dir / filename
                with open(filepath, 'w') as f:
                    f.write(content)
            
            self.results["tests_passed"] += 1
            self.results["test_results"].append({
                "test": "Error Handling - Missing Files",
                "status": "PASS",
                "message": "Gracefully handles missing state files with proper unavailable flag"
            })
            return True
        except Exception as e:
            self.results["tests_failed"] += 1
            self.results["test_results"].append({
                "test": "Error Handling - Missing Files",
                "status": "FAIL",
                "message": str(e)
            })
            
            for filename, content in backup_files.items():
                filepath = self.data_dir / filename
                try:
                    with open(filepath, 'w') as f:
                        f.write(content)
                except:
                    pass
            
            return False
    
    def run_validation(self):
        """Run key validation tests."""
        print("Running Fixed Validation Tests")
        print("=" * 60)
        
        self.test_state_reader_initialization()
        self.test_error_handling_missing_file()
        
        print("=" * 60)
        print(f"Tests Passed: {self.results['tests_passed']}")
        print(f"Tests Failed: {self.results['tests_failed']}")
        
        for result in self.results["test_results"]:
            status_emoji = "✅" if result["status"] == "PASS" else "❌"
            print(f"{status_emoji} {result['test']}: {result['message']}")
        
        return self.results

validator = DashboardValidatorFixed()
results = validator.run_validation()

report_file = Path("/app/hydra_x_v2_1804/data/dashboard_validation_report_part1_fixed.json")
with open(report_file, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n✅ Report saved to {report_file}")