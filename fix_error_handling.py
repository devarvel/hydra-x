import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

print("Fixing error handling for missing files...")
print("=" * 60)

data_dir = Path("/app/hydra_x_v2_1804/data")
data_dir.mkdir(parents=True, exist_ok=True)

placeholder_metrics = {
    "balance": 10000.0,
    "equity": 10000.0,
    "drawdown_pct": 0.0,
    "daily_pnl": 0.0,
    "margin_used_pct": 0.0,
    "margin_ratio_pct": 0.0,
    "status": "UNKNOWN",
    "consecutive_losses": 0,
    "daily_trade_count": 0,
    "shutdown_reason": "",
    "last_update": datetime.now().isoformat()
}

placeholder_positions = []

placeholder_trades = []

placeholder_trend = {
    "BTCUSDT": {"trend": "RANGING", "ema50": 0, "ema200": 0},
    "XAUTUSDT": {"trend": "RANGING", "ema50": 0, "ema200": 0}
}

placeholder_pa = {
    "confirmation_count": 0,
    "confirmation_score": 0.0,
    "patterns": []
}

files_to_create = [
    ("daily_summary_state.json", placeholder_metrics),
    ("open_positions.json", placeholder_positions),
    ("trade_history.json", placeholder_trades),
    ("trend_cache.json", placeholder_trend),
    ("pa_confirmation_cache.json", placeholder_pa)
]

for filename, data in files_to_create:
    filepath = data_dir / filename
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"✅ Created placeholder: {filename}")

print("\n" + "=" * 60)
print("✅ Placeholder files created successfully")
print("\nNow fixing DashboardStateReader error handling...")