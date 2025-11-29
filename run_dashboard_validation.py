import json
import sys
from pathlib import Path
import subprocess

sys.path.insert(0, str(Path(__file__).parent))

result = subprocess.run(
    ["python", "/app/hydra_x_v2_1804/validate_dashboard_part1.py"],
    capture_output=True,
    text=True
)

print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)
print("Exit code:", result.returncode)