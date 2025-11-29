import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("Testing dashboard imports...")

try:
    from modules.dashboard_state_reader import DashboardStateReader
    print("✅ DashboardStateReader imported successfully")
    
    reader = DashboardStateReader()
    print("✅ DashboardStateReader initialized successfully")
    
    metrics = reader.read_account_metrics()
    print(f"✅ Account metrics read: {metrics}")
    
    positions = reader.read_open_positions()
    print(f"✅ Open positions read: {len(positions)} positions")
    
    trades = reader.read_trade_history()
    print(f"✅ Trade history read: {len(trades)} trades")
    
    status = reader.read_bot_status()
    print(f"✅ Bot status read: {status}")
    
    print("\n✅ All dashboard imports and basic functionality working!")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()