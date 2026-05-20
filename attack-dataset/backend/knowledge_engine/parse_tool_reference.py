#!/usr/bin/env python3
"""
Parse OPSEC_OFFENSIVE_TOOL_REFERENCE.md into structured JSON format for OpSec audit engine.
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Any

def parse_tool_reference(markdown_path: str) -> Dict[str, Any]:
    """Parse the tool reference markdown into structured JSON."""
    
    with open(markdown_path, 'r') as f:
        content = f.read()
    
    result = {
        "tactics": {},
        "best_practices": {},
        "detection_indicators": {},
        "countermeasures": {},
        "substitution_matrix": {}
    }
    
    # Parse tactics and tools
    lines = content.split('\n')
    current_tactic = None
    current_subcategory = None
    in_table = False
    
    for i, line in enumerate(lines):
        # Check for tactic headers (##)
        if line.startswith('## ') and not line.startswith('###'):
            current_tactic = line[3:].strip()
            result["tactics"][current_tactic] = {
                "subcategories": {},
                "tools": []
            }
            current_subcategory = None
            in_table = False
        
        # Check for subcategory headers (###)
        elif line.startswith('### ') and current_tactic:
            current_subcategory = line[4:].strip()
            result["tactics"][current_tactic]["subcategories"][current_subcategory] = []
            in_table = False
        
        # Check for table start
        elif line.strip().startswith('|') and 'Tool' in line and 'Description' in line:
            in_table = True
            continue
        
        # Parse table rows
        elif in_table and line.strip().startswith('|') and not line.strip().startswith('|-'):
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) >= 4:
                tool_name = parts[0].replace('**', '').strip()
                if tool_name:  # Skip empty rows
                    tool_data = {
                        "name": tool_name,
                        "description": parts[1],
                        "opsec_considerations": parts[2],
                        "detection_methods": parts[3],
                        "tactic": current_tactic,
                        "subcategory": current_subcategory
                    }
                    result["tactics"][current_tactic]["tools"].append(tool_data)
                    if current_subcategory:
                        result["tactics"][current_tactic]["subcategories"][current_subcategory].append(tool_name)
        
        # Stop table at horizontal rule or new section
        elif in_table and (line.strip() == '---' or line.startswith('## ')):
            in_table = False
    
    # Parse best practices
    best_practices_section = content.split('## OpSec Best Practices by Tool Category')[1].split('## Detection Indicators to Monitor')[0]
    result["best_practices"]["general"] = []
    result["best_practices"]["tool_specific"] = {}
    
    current_tool = None
    for line in best_practices_section.split('\n'):
        if line.strip().startswith('### General Rules'):
            continue
        elif line.strip().startswith('### Tool-Specific OpSec Tips'):
            continue
        elif re.match(r'^\*\*([A-Za-z\s]+)\*\*', line):
            current_tool = line.strip().replace('**', '').strip()
            result["best_practices"]["tool_specific"][current_tool] = []
        elif line.strip().startswith('-') and current_tool:
            tip = line.strip()[1:].strip()
            result["best_practices"]["tool_specific"][current_tool].append(tip)
        elif line.strip().startswith('1.') or line.strip().startswith('2.') or line.strip().startswith('3.'):
            practice = line.strip()
            result["best_practices"]["general"].append(practice)
    
    # Parse detection indicators
    detection_section = content.split('## Detection Indicators to Monitor')[1].split('## Countermeasures for Common Detection Methods')[0]
    for line in detection_section.split('\n'):
        if line.strip().startswith('###'):
            category = line.strip()[4:].strip()
            result["detection_indicators"][category] = []
        elif line.strip().startswith('-'):
            indicator = line.strip()[1:].strip()
            if category in result["detection_indicators"]:
                result["detection_indicators"][category].append(indicator)
    
    # Parse countermeasures
    countermeasures_section = content.split('## Countermeasures for Common Detection Methods')[1].split('## Tool Substitution Matrix')[0]
    for line in countermeasures_section.split('\n'):
        if line.strip().startswith('###'):
            category = line.strip()[4:].strip()
            result["countermeasures"][category] = []
        elif line.strip().startswith('-'):
            countermeasure = line.strip()[1:].strip()
            if category in result["countermeasures"]:
                result["countermeasures"][category].append(countermeasure)
    
    # Parse substitution matrix
    substitution_section = content.split('## Tool Substitution Matrix')[1].split('## References')[0]
    result["substitution_matrix"] = {}
    in_table = False
    for line in substitution_section.split('\n'):
        if line.strip().startswith('|') and 'Tool' in line and 'Quieter' in line:
            in_table = True
            continue
        elif in_table and line.strip().startswith('|') and not line.strip().startswith('|-'):
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) >= 3:
                tool = parts[0].replace('**', '').strip()
                alternative = parts[1].replace('**', '').strip()
                notes = parts[2]
                if tool:
                    result["substitution_matrix"][tool] = {
                        "alternative": alternative,
                        "notes": notes
                    }
        elif in_table and line.strip() == '':
            in_table = False
    
    return result

def main():
    """Main function to parse and save JSON."""
    markdown_path = Path(__file__).parent.parent.parent / 'docs' / 'OPSEC_OFFENSIVE_TOOL_REFERENCE.md'
    output_path = Path(__file__).parent / 'tool_reference.json'
    
    print(f"Parsing {markdown_path}...")
    parsed_data = parse_tool_reference(str(markdown_path))
    
    print(f"Saving to {output_path}...")
    with open(output_path, 'w') as f:
        json.dump(parsed_data, f, indent=2)
    
    print(f"✓ Parsed {len(parsed_data['tactics'])} tactics")
    total_tools = sum(len(tactic['tools']) for tactic in parsed_data['tactics'].values())
    print(f"✓ Parsed {total_tools} tools")
    print(f"✓ Parsed {len(parsed_data['substitution_matrix'])} tool substitutions")
    print(f"✓ Parsed {len(parsed_data['best_practices']['tool_specific'])} tool-specific best practices")

if __name__ == '__main__':
    main()