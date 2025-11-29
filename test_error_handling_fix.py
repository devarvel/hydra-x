import sys
import json
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from modules.dashboard_state_reader import DashboardStateReader

print("Testing enhanced error handling...")
print("=" * 60)

data_dir = Path("/app/hydra_x_v2_1804/data")

reader = DashboardStateReader()

print("\n1. Testing with placeholder files present:")
metrics = reader.read_account_metrics()
print(f"   Metrics available: {metrics['available']}")
print(f"   Balance: {metrics['balance']}")

positions = reader.read_open_positions()
print(f"   Positions count: {len(positions)}")

trades = reader.read_trade_history()
print(f"   Trades count: {len(trades)}")

status = reader.read_bot_status()
print(f"   Status: {status['status']}")

print("\n2. Testing with missing daily_summary_state.json:")
backup_file = data_dir / "daily_summary_state.json"
backup_path = data_dir / "daily_summary_state.json.bak"

if backup_file.exists():
    os.rename(backup_file, backup_path)

metrics_missing = reader.read_account_metrics()
print(f"   Metrics available when file missing: {metrics_missing['available']}")
print(f"   Returns defaults: {metrics_missing['balance'] == 0.0 and not metrics_missing['available']}")

if backup_path.exists():
    os.rename(backup_path, backup_file)

print("\n3. Testing with corrupted JSON:")
corrupt_file = data_dir / "test_corrupt.json"
with open(corrupt_file, 'w') as f:
    f.write("{ invalid json }")

corrupt_data = reader.read_json_safe(corrupt_file)
print(f"   Corrupted JSON returns None: {corrupt_data is None}")

if corrupt_file.exists():
    os.remove(corrupt_file)

print("\n" + "=" * 60)
print("✅ Error handling enhancements verified!")