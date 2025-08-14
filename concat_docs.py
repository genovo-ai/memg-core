#!/usr/bin/env python3
"""
Concatenate all MEMG Core documentation files into a single comprehensive document.
"""

import os
from pathlib import Path

def main():
    docs_dir = Path("docs/memg_core")
    output_file = Path("docs/MEMG_CORE_COMPLETE_DOCUMENTATION.md")

    # Define the order of files to maintain logical structure
    file_order = [
        "README.md",
        "SYSTEM_OVERVIEW.md",
        "api/public.md",
        "core/config.md",
        "core/exceptions.md",
        "core/models.md",
        "core/logging.md",
        "core/indexing.md",
        "core/yaml_translator.md",
        "core/interfaces/embedder.md",
        "core/interfaces/kuzu.md",
        "core/interfaces/qdrant.md",
        "core/pipeline/indexer.md",
        "core/pipeline/retrieval.md",
        "plugins/yaml_schema.md",
        "showcase/examples/simple_demo.md",
        "showcase/retriever.md",
        "system/info.md",
        "utils/hrid.md"
    ]

    print("🔗 Concatenating MEMG Core documentation...")

    with open(output_file, 'w', encoding='utf-8') as outf:
        # Write header
        outf.write("# MEMG Core - Complete Documentation\n\n")
        outf.write("*This document contains the complete concatenated documentation for MEMG Core.*\n\n")
        outf.write("---\n\n")

        section_num = 1

        for file_path in file_order:
            full_path = docs_dir / file_path
            if not full_path.exists():
                print(f"⚠️  Warning: {file_path} not found, skipping...")
                continue

            print(f"📄 Adding Section {section_num}: {file_path}")

            # Write section header
            outf.write(f"## Section {section_num}: {file_path}\n\n")

            # Write file contents
            try:
                with open(full_path, 'r', encoding='utf-8') as inf:
                    content = inf.read().strip()
                    outf.write(content)
                    outf.write("\n\n")
            except Exception as e:
                print(f"❌ Error reading {file_path}: {e}")
                continue

            # Add separator between sections
            outf.write("---\n\n")
            section_num += 1

    print(f"✅ Documentation concatenated successfully!")
    print(f"📁 Output: {output_file}")

    # Show file stats
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            lines = len(f.readlines())
        file_size = output_file.stat().st_size
        print(f"📊 Total lines: {lines}")
        print(f"📦 File size: {file_size:,} bytes")
    except Exception as e:
        print(f"⚠️  Could not get file stats: {e}")

if __name__ == "__main__":
    main()
