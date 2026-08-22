#!/usr/bin/env python3
from pathlib import Path

project_root = Path("/Users/prajwalnavadagp/Engineering/Projects/degrade-watch")
generated_data_dir = project_root / "data" / "generated"
baseline_dir = generated_data_dir / "baselines"
baseline_path = baseline_dir / "merch_upi_smb.json"

print(f"project_root: {project_root}")
print(f"generated_data_dir: {generated_data_dir}")
print(f"baseline_dir: {baseline_dir}")
print(f"baseline_path: {baseline_path}")
print(f"baseline_path.exists(): {baseline_path.exists()}")
print(f"baseline_path.is_absolute(): {baseline_path.is_absolute()}")

# Also check the actual directory listing
print(f"\nContents of {baseline_dir}:")
if baseline_dir.exists():
    for item in baseline_dir.iterdir():
        print(f"  {item.name}")
else:
    print("  Directory does not exist")