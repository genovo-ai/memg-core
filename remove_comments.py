#!/usr/bin/env python3
"""
Script to remove all comments and docstrings from the final memg_core file.
"""

import re

def remove_comments_and_docstrings(input_file, output_file):
    """Remove all # comments and docstrings from Python file."""

    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    print(f"Original size: {len(content)} characters")

    # Step 1: Remove triple-quoted docstrings (both """ and ''')
    # Handle multi-line docstrings
    content = re.sub(r'"""[\s\S]*?"""', '', content)
    content = re.sub(r"'''[\s\S]*?'''", '', content)

    # Step 2: Remove single-line comments starting with #
    # But preserve shebang
    lines = content.split('\n')
    cleaned_lines = []

    for line in lines:
        # Keep shebang
        if line.strip().startswith('#!'):
            cleaned_lines.append(line)
            continue

        # Remove comments, but be careful with strings
        in_string = False
        quote_char = None
        escaped = False
        result = ""

        i = 0
        while i < len(line):
            char = line[i]

            if escaped:
                result += char
                escaped = False
                i += 1
                continue

            if char == '\\' and in_string:
                result += char
                escaped = True
                i += 1
                continue

            if not in_string:
                if char in ['"', "'"]:
                    # Starting a string
                    in_string = True
                    quote_char = char
                    result += char
                elif char == '#':
                    # Found comment outside string, stop here
                    break
                else:
                    result += char
            else:
                # We're inside a string
                if char == quote_char:
                    # Ending the string
                    in_string = False
                    quote_char = None
                result += char

            i += 1

        # Only keep non-empty lines
        if result.strip():
            cleaned_lines.append(result.rstrip())

    # Step 3: Join lines and clean up excessive whitespace
    final_content = '\n'.join(cleaned_lines)

    # Remove multiple consecutive empty lines
    final_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', final_content)

    # Remove leading/trailing whitespace
    final_content = final_content.strip()

    # Write the result
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(final_content)

    print(f"Final size: {len(final_content)} characters")
    reduction = len(content) - len(final_content)
    percentage = (reduction / len(content) * 100) if len(content) > 0 else 0
    print(f"Removed: {reduction} characters ({percentage:.1f}%)")

if __name__ == "__main__":
    input_file = "memg_core_final.py"
    output_file = "memg_core_no_comments.py"

    print(f"Removing comments and docstrings from {input_file} -> {output_file}")

    try:
        remove_comments_and_docstrings(input_file, output_file)
        print(f"\n✅ Success! Created: {output_file}")

        # Test syntax
        print("Testing syntax...")
        import subprocess
        import sys
        result = subprocess.run([sys.executable, "-m", "py_compile", output_file],
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Syntax check passed!")
        else:
            print(f"❌ Syntax error: {result.stderr}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
