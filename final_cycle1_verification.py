import os
import json
from pathlib import Path

print("=" * 70)
print("FINAL CYCLE 1 VERIFICATION - STREAMLIT DASHBOARD PART 1")
print("=" * 70)

files_to_check = [
    "modules/dashboard.py",
    "modules/dashboard_state_reader.py",
    "validate_dashboard_part1.py",
    "DASHBOARD_README.md",
    "CYCLE_1_SUMMARY.md",
    "config.yaml",
    "data/dashboard_validation_report_part1.json"
]

base_dir = Path("/app/hydra_x_v2_1804")

print("\n📋 File Existence Check:")
all_exist = True
for file_path in files_to_check:
    full_path = base_dir / file_path
    exists = full_path.exists()
    status = "✅" if exists else "❌"
    print(f"  {status} {file_path}")
    if not exists:
        all_exist = False

print("\n📊 File Sizes:")
for file_path in files_to_check:
    full_path = base_dir / file_path
    if full_path.exists():
        size = full_path.stat().st_size
        size_str = f"{size:,} bytes" if size < 1024*1024 else f"{size/(1024*1024):.2f} MB"
        print(f"  • {file_path}: {size_str}")

print("\n🔧 Dashboard Configuration:")
config_file = base_dir / "config.yaml"
if config_file.exists():
    with open(config_file) as f:
        content = f.read()
        if "dashboard:" in content:
            print("  ✅ Dashboard section present in config.yaml")
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'dashboard:' in line:
                    for j in range(i, min(i+10, len(lines))):
                        if lines[j].strip() and not lines[j].strip().startswith('#'):
                            print(f"     {lines[j]}")
                    break
        else:
            print("  ❌ Dashboard section missing from config.yaml")

print("\n✅ Validation Results:")
report_file = base_dir / "data/dashboard_validation_report_part1.json"
if report_file.exists():
    with open(report_file) as f:
        report = json.load(f)
        print(f"  Tests Passed: {report['tests_passed']}")
        print(f"  Tests Failed: {report['tests_failed']}")
        for result in report['test_results']:
            status_emoji = "✅" if result['status'] == "PASS" else "❌"
            print(f"    {status_emoji} {result['test']}")

print("\n🚀 Dashboard Launch Instructions:")
print("  Command: streamlit run /app/hydra_x_v2_1804/modules/dashboard.py")
print("  URL: http://localhost:8501")
print("  Port: 8501 (configurable in config.yaml)")

print("\n" + "=" * 70)
if all_exist:
    print("✅ CYCLE 1 VERIFICATION COMPLETE - ALL ARTIFACTS PRESENT")
else:
    print("⚠️  CYCLE 1 VERIFICATION - SOME FILES MISSING")
print("=" * 70)