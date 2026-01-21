# -*- coding: utf-8 -*-
"""
Script to systematically add type hints to UI files.
This script processes files and adds common type hints.
"""
import re
import sys
from pathlib import Path
from typing import List, Tuple

# Type hint patterns to add
PATTERNS = [
    # Add Optional import if not present
    (
        r'^(from PyQt5)',
        r'from typing import Optional, Any\n\n\1'
    ),
    # parent=None -> parent: Optional[QWidget] = None (if not already typed)
    (
        r'(\bdef __init__\([^)]*\bparent)=None\)',
        r'\1: Optional[QWidget] = None)'
    ),
    # Add -> None for __init__ methods
    (
        r'(def __init__\([^)]*\)):\s*\n',
        r'\1 -> None:\n'
    ),
    # Add -> None for _setup_ui methods
    (
        r'(def _setup_ui\([^)]*\)):\s*\n',
        r'\1 -> None:\n'
    ),
]


def has_typing_import(content: str) -> bool:
    """Check if file already has typing import."""
    return 'from typing import' in content or 'import typing' in content


def add_type_hints_to_file(file_path: Path) -> Tuple[bool, str]:
    """
    Add type hints to a single file.

    Returns:
        Tuple of (success, message)
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content

        # Check if we need to add typing import
        needs_typing = 'parent=None' in content or 'parent = None' in content

        if needs_typing and not has_typing_import(content):
            # Add typing import after # -*- coding: utf-8 -*- and docstring
            lines = content.split('\n')
            insert_pos = 0

            # Skip encoding and docstring
            for i, line in enumerate(lines):
                if line.strip().startswith('"""') or line.strip().startswith("'''"):
                    # Find closing docstring
                    if i + 1 < len(lines):
                        for j in range(i + 1, len(lines)):
                            if '"""' in lines[j] or "'''" in lines[j]:
                                insert_pos = j + 1
                                break
                    break
                elif i > 0 and not line.strip().startswith('#'):
                    insert_pos = i
                    break

            if insert_pos > 0:
                lines.insert(insert_pos, 'from typing import Optional, Any\n')
                content = '\n'.join(lines)

        # Apply basic patterns
        content = re.sub(r'\bparent=None\)', r'parent: Optional[QWidget] = None)', content)
        content = re.sub(r'\bparent = None\)', r'parent: Optional[QWidget] = None)', content)

        # Add return type hints to common methods (if not already present)
        content = re.sub(
            r'(def __init__\([^)]*\)):(?!\s*->)\s*\n',
            r'\1 -> None:\n',
            content
        )
        content = re.sub(
            r'(def _setup_ui\([^)]*\)):(?!\s*->)\s*\n',
            r'\1 -> None:\n',
            content
        )

        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            return True, f"Updated: {file_path.name}"
        else:
            return False, f"No changes needed: {file_path.name}"

    except Exception as e:
        return False, f"Error processing {file_path.name}: {e}"


def process_directory(directory: Path, pattern: str = "*.py") -> None:
    """Process all Python files in directory."""
    files = list(directory.rglob(pattern))

    if not files:
        print(f"No files found in {directory}")
        return

    print(f"Found {len(files)} files to process\n")

    updated = 0
    skipped = 0
    errors = 0

    for file_path in files:
        # Skip __init__.py and this script
        if file_path.name == '__init__.py' or 'add_type_hints' in file_path.name:
            continue

        success, message = add_type_hints_to_file(file_path)

        if success:
            print(f"OK: {message}")
            updated += 1
        elif "Error" in message:
            print(f"ERR: {message}")
            errors += 1
        else:
            skipped += 1

    print(f"\n=== Summary ===")
    print(f"Updated: {updated}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")
    print(f"Total: {len(files)}")


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent

    # Process ui/components
    print("Processing ui/components/...\n")
    components_dir = project_root / "ui" / "components"
    if components_dir.exists():
        process_directory(components_dir)
    else:
        print(f"Directory not found: {components_dir}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
