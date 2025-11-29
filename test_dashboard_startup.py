import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("Testing dashboard startup capability...")
print("=" * 60)

try:
    from modules.dashboard_state_reader import DashboardStateReader
    from utils import load_config
    
    print("✅ Imports successful")
    
    reader = DashboardStateReader()
    print("✅ DashboardStateReader initialized")
    
    config = load_config("/app/hydra_x_v2_1804/config.yaml")
    print(f"✅ Config loaded with dashboard section: {config.get('dashboard', {})}")
    
    metrics = reader.read_account_metrics()
    positions = reader.read_open_positions()
    trades = reader.read_trade_history()
    status = reader.read_bot_status()
    
    print(f"✅ Account metrics available: {metrics.get('available')}")
    print(f"✅ Open positions: {len(positions)} found")
    print(f"✅ Trade history: {len(trades)} trades")
    print(f"✅ Bot status: {status['status']}")
    
    print("=" * 60)
    print("✅ Dashboard ready to launch!")
    print("\nTo start dashboard, run:")
    print("  streamlit run /app/hydra_x_v2_1804/modules/dashboard.py")
    print("\nDashboard will be available at: http://localhost:8501")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()