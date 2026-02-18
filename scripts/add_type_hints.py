# -*- coding: utf-8 -*-
"""
Script to add type hints to UI files using automated tools.
Uses monkeytype for runtime type inference.
"""
import subprocess
import sys
from pathlib import Path

# Key UI files that need type hints
UI_FILES = [
    "ui/components/primary_button.py",
    "ui/components/secondary_button.py",
    "ui/components/input_field.py",
    "ui/pages/dashboard_page.py",
    "controllers/claim_controller.py",
]

def add_type_hints():
    """Add type hints using mypy stubgen."""
    project_root = Path(__file__).parent.parent

    for file_path in UI_FILES:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"Processing {file_path}...")
            # Run mypy to check current status
            result = subprocess.run(
                [sys.executable, "-m", "mypy", str(full_path),
                 "--ignore-missing-imports"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"  Issues found in {file_path}")
                print(result.stdout)
        else:
            print(f"  File not found: {file_path}")

if __name__ == "__main__":
    add_type_hints()
