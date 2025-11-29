import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("Testing config and dashboard startup...")
print("=" * 60)

try:
    from utils import load_config
    
    config = load_config("/app/hydra_x_v2_1804/config.yaml")
    print("✅ Config loaded successfully")
    
    dashboard_config = config.get("dashboard", {})
    print(f"✅ Dashboard config found: {dashboard_config}")
    
    assert dashboard_config.get("enabled") == True
    assert dashboard_config.get("port") == 8501
    assert dashboard_config.get("refresh_rate") == 1
    print("✅ Dashboard settings verified")
    
    from modules.dashboard_state_reader import DashboardStateReader
    reader = DashboardStateReader()
    print("✅ DashboardStateReader initialized")
    
    metrics = reader.read_account_metrics()
    positions = reader.read_open_positions()
    trades = reader.read_trade_history()
    status = reader.read_bot_status()
    
    print(f"✅ All state readers working")
    print(f"   - Metrics available: {metrics.get('available')}")
    print(f"   - Positions: {len(positions)} found")
    print(f"   - Trades: {len(trades)} found")
    print(f"   - Bot status: {status['status']}")
    
    print("=" * 60)
    print("✅ Dashboard ready to launch!")
    print("\nStart dashboard with:")
    print("  streamlit run /app/hydra_x_v2_1804/modules/dashboard.py")
    print("\nAccess at: http://localhost:8501")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()