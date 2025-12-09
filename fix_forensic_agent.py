#!/usr/bin/env python3
"""
Fix script for Forensic_agent.py
This script updates the file to properly handle f-string formatting with imported variables.
"""

import os

# Path to the file that needs fixing
file_path = "realtime/utils/prompts/Forensic_agent.py"

# Read the current content
with open(file_path, 'r') as f:
    content = f.read()

# Check if it's already fixed
if '# Build forensic agent instructions with tool prompts' in content:
    print("✓ File is already fixed!")
    exit(0)

# The fix: Add a blank line and comment before forensic_agent_instructions
old_pattern = """from utils.prompts.contacts import contact_tool_prompt

forensic_agent_instructions = f"""

new_pattern = """from utils.prompts.contacts import contact_tool_prompt


# Build forensic agent instructions with tool prompts
forensic_agent_instructions = f"""

# Apply the fix
if old_pattern in content:
    content = content.replace(old_pattern, new_pattern)

    # Write back
    with open(file_path, 'w') as f:
        f.write(content)

    print("✓ Fixed Forensic_agent.py successfully!")
    print("✓ The forensic agent instructions now properly load tool prompts")
else:
    print("⚠️  Pattern not found. File may already be fixed or has different structure.")
    print("Current imports section:")
    lines = content.split('\n')
    for i, line in enumerate(lines[:15], 1):
        print(f"{i:3d}: {line}")
