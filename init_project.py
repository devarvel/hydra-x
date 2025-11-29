import os
import sys
from pathlib import Path

project_root = "/app/hydra_x_v2_1804"

dirs_to_create = [
    f"{project_root}/modules",
    f"{project_root}/data",
    f"{project_root}/logs"
]

files_to_create = [
    f"{project_root}/modules/__init__.py",
    f"{project_root}/main.py",
    f"{project_root}/indicators.py",
]

module_stubs = [
    "trend.py", "breakout.py", "sweep.py", "price_action.py",
    "support_resistance.py", "risk.py", "execution.py", 
    "telegram.py", "dashboard.py"
]

for dir_path in dirs_to_create:
    Path(dir_path).mkdir(parents=True, exist_ok=True)
    print(f"✓ Created directory: {dir_path}")

for file_path in files_to_create:
    Path(file_path).touch()
    print(f"✓ Created file: {file_path}")

for module in module_stubs:
    module_path = f"{project_root}/modules/{module}"
    with open(module_path, 'w') as f:
        f.write(f'"""{module.replace(".py", "").replace("_", " ").title()} Module"""\n\n')
        f.write(f'def placeholder():\n    pass\n')
    print(f"✓ Created module: {module_path}")

print("\n✓ Project structure initialization complete!")