#!/usr/bin/env python3
"""
Script to combine all core memg_core Python files (excluding __init__.py files).
"""

import os
from pathlib import Path

def combine_core_files(source_dir, output_file):
    """Combine all core Python files excluding __init__.py files."""

    # Get all Python files except __init__.py
    source_path = Path(source_dir)
    python_files = []

    for py_file in source_path.rglob("*.py"):
        if py_file.name != "__init__.py" and "__pycache__" not in str(py_file):
            python_files.append(py_file)

    # Sort for consistent ordering
    python_files.sort()

    print(f"Found {len(python_files)} core Python files")

    with open(output_file, 'w', encoding='utf-8') as out_file:
        # Write header
        out_file.write("#!/usr/bin/env python3\n")
        out_file.write("# Combined memg_core source code - Core files only (no __init__.py)\n\n")

        for py_file in python_files:
            # Get relative path from src/ directory
            relative_path = py_file.relative_to(Path(source_dir).parent)

            # Write path comment
            out_file.write(f"# {relative_path}\n")

            try:
                # Read and write file content
                with open(py_file, 'r', encoding='utf-8') as source_file:
                    content = source_file.read()
                    out_file.write(content)

                # Add separator between files
                out_file.write("\n\n" + "="*80 + "\n\n")

                print(f"Added: {relative_path}")

            except Exception as e:
                print(f"Error reading {py_file}: {e}")
                out_file.write(f"# ERROR: Could not read file - {e}\n\n")

if __name__ == "__main__":
    source_directory = "src/memg_core"
    output_filename = "memg_core_combined_no_init.py"

    print(f"Combining core Python files from {source_directory} into {output_filename}")

    if not os.path.exists(source_directory):
        print(f"Error: Source directory {source_directory} not found!")
        exit(1)

    combine_core_files(source_directory, output_filename)

    print(f"\nDone! Combined file created: {output_filename}")

    # Show stats
    file_count = len([f for f in Path(source_directory).rglob("*.py") if f.name != "__init__.py"])
    output_size = os.path.getsize(output_filename) if os.path.exists(output_filename) else 0

    print(f"Combined {file_count} core Python files")
    print(f"Output file size: {output_size:,} bytes")
