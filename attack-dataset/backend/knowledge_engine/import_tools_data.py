"""
Import offensive tools reference data from documentation into database.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import re
import json
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ToolDataImporter:
    """Import tool reference data from markdown documentation."""
    
    def __init__(self, db_config: Dict[str, Any] = None):
        self.db_config = db_config or {
            'host': 'localhost',
            'port': 5432,
            'database': 'attack_db',
            'user': 'opsec',
            'password': 'opsec'
        }
        self.conn = None
        
    def connect(self):
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            logger.info("Database connection established")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def parse_markdown_table(self, markdown_content: str, category: str, mitre_tactic: str) -> List[Dict[str, Any]]:
        """Parse tool tables from markdown content."""
        tools = []
        seen_tools = set()
        
        # Find the specific section for this category
        category_pattern = rf'### {re.escape(category)}'
        category_match = re.search(category_pattern, markdown_content)
        
        if not category_match:
            logger.warning(f"Category section not found: {category}")
            return tools
        
        # Get content from this section to next major heading
        section_start = category_match.end()
        next_section = re.search(r'\n###\s', markdown_content[section_start:])
        section_end = next_section.start() if next_section else len(markdown_content)
        section_content = markdown_content[section_start:section_start + section_end]
        
        # Split content by table headers
        table_pattern = r'\|\s*Tool\s*\|\s*Description\s*\|\s*OpSec Considerations\s*\|\s*Detection Methods\s*\|'
        table_match = re.search(table_pattern, section_content)
        
        if not table_match:
            logger.warning(f"Table not found in category: {category}")
            return tools
        
        table_content = section_content[table_match.end():]
        
        # Extract table rows
        rows = re.findall(r'\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|', table_content, re.DOTALL)
        
        for row in rows:
            tool_name = row[0].strip()
            
            # Skip if already seen (avoid duplicates)
            if tool_name in seen_tools:
                continue
            
            seen_tools.add(tool_name)
            
            description = row[1].strip()
            opsec_considerations = row[2].strip()
            detection_methods = row[3].strip()
            
            # Parse detection methods into array
            detection_methods_list = [dm.strip() for dm in detection_methods.split(',')]
            
            # Determine risk level based on OpSec considerations
            risk_level = self._assess_risk_level(opsec_considerations)
            
            # Determine noise level
            noise_level = self._assess_noise_level(opsec_considerations)
            
            # Determine stealth level
            stealth_level = 100 - noise_level
            
            tool_data = {
                'name': tool_name,
                'category': category,
                'description': description,
                'opsec_considerations': opsec_considerations,
                'detection_methods': detection_methods_list,
                'mitre_tactic': mitre_tactic,
                'risk_level': risk_level,
                'noise_level': noise_level,
                'stealth_level': stealth_level,
                'platform': self._detect_platform(description),
                'alternatives': []
            }
            
            tools.append(tool_data)
        
        logger.info(f"Parsed {len(tools)} unique tools from {category}")
        return tools
    
    def _assess_risk_level(self, opsec_considerations: str) -> str:
        """Assess risk level based on OpSec considerations."""
        opsec_lower = opsec_considerations.lower()
        
        high_risk_indicators = ['highly signatured', 'very detectable', 'extremely noisy', 'commercially signatured']
        critical_risk_indicators = ['attribution risk', 'public tunnels', 'audit trails']
        
        for indicator in critical_risk_indicators:
            if indicator in opsec_lower:
                return 'critical'
        
        for indicator in high_risk_indicators:
            if indicator in opsec_lower:
                return 'high'
        
        if 'stealthier' in opsec_lower or 'lower detection' in opsec_lower:
            return 'low'
        
        return 'medium'
    
    def _assess_noise_level(self, opsec_considerations: str) -> str:
        """Assess noise level (0-100) based on OpSec considerations."""
        opsec_lower = opsec_considerations.lower()
        
        if 'extremely noisy' in opsec_lower or 'massive spike' in opsec_lower:
            return 90
        elif 'very noisy' in opsec_lower or 'high request volume' in opsec_lower:
            return 75
        elif 'noisy' in opsec_lower or 'generates high' in opsec_lower:
            return 60
        elif 'stealthier' in opsec_lower or 'lower detection' in opsec_lower:
            return 30
        elif 'passive' in opsec_lower or 'safer' in opsec_lower:
            return 20
        else:
            return 50
    
    def _detect_platform(self, description: str) -> List[str]:
        """Detect platform from description."""
        platforms = []
        desc_lower = description.lower()
        
        if 'windows' in desc_lower or 'powershell' in desc_lower or '.net' in desc_lower:
            platforms.append('Windows')
        if 'linux' in desc_lower or 'unix' in desc_lower or 'bash' in desc_lower:
            platforms.append('Linux')
        if 'macos' in desc_lower or 'os x' in desc_lower:
            platforms.append('macOS')
        if 'web' in desc_lower or 'http' in desc_lower or 'api' in desc_lower:
            platforms.append('Web')
        if 'wireless' in desc_lower or 'wifi' in desc_lower:
            platforms.append('Wireless')
        if 'network' in desc_lower:
            platforms.append('Network')
        if 'dns' in desc_lower:
            platforms.append('DNS')
            
        return platforms if platforms else ['Cross-platform']
    
    def import_tools(self, tools: List[Dict[str, Any]]):
        """Import tools into database."""
        if not self.connect():
            return False
        
        try:
            cursor = self.conn.cursor()
            
            for tool in tools:
                insert_query = """
                INSERT INTO offensive_tools (
                    name, category, description, opsec_considerations,
                    detection_methods, mitre_tactic, risk_level, noise_level,
                    stealth_level, platform
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (name) DO UPDATE SET
                    description = EXCLUDED.description,
                    opsec_considerations = EXCLUDED.opsec_considerations,
                    detection_methods = EXCLUDED.detection_methods,
                    risk_level = EXCLUDED.risk_level,
                    noise_level = EXCLUDED.noise_level,
                    stealth_level = EXCLUDED.stealth_level,
                    updated_at = CURRENT_TIMESTAMP
                """
                
                cursor.execute(insert_query, (
                    tool['name'],
                    tool['category'],
                    tool['description'],
                    tool['opsec_considerations'],
                    tool['detection_methods'],
                    tool['mitre_tactic'],
                    tool['risk_level'],
                    tool['noise_level'],
                    tool['stealth_level'],
                    tool['platform']
                ))
            
            self.conn.commit()
            logger.info(f"Imported {len(tools)} tools successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to import tools: {e}")
            if self.conn:
                self.conn.rollback()
            return False
        finally:
            if self.conn:
                self.conn.close()
    
    def load_and_import_from_file(self, file_path: str):
        """Load tools from markdown file and import to database."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Define category mappings
            category_mappings = {
                'Reconnaissance': [
                    ('Network Scanning', 'Reconnaissance'),
                    ('DNS & Subdomain Enumeration', 'Reconnaissance'),
                    ('Web Reconnaissance', 'Reconnaissance'),
                    ('Wireless Reconnaissance', 'Reconnaissance')
                ],
                'Resource Development': [
                    ('Infrastructure Setup', 'Resource Development'),
                    ('Domain & Infrastructure', 'Resource Development')
                ],
                'Initial Access': [
                    ('Exploitation Frameworks', 'Initial Access'),
                    ('Phishing & Social Engineering', 'Initial Access'),
                    ('Web Exploits', 'Initial Access'),
                    ('Password Attacks', 'Initial Access')
                ],
                'Execution': [
                    ('Command & Control', 'Execution'),
                    ('Process Injection', 'Execution'),
                    ('File Execution', 'Execution')
                ],
                'Persistence': [
                    ('Windows Persistence', 'Persistence'),
                    ('C2 Persistence', 'Persistence')
                ],
                'Privilege Escalation': [
                    ('Windows Privilege Escalation', 'Privilege Escalation'),
                    ('Linux Privilege Escalation', 'Privilege Escalation')
                ],
                'Defense Evasion': [
                    ('Anti-Virus/EDR Evasion', 'Defense Evasion')
                ]
            }
            
            all_tools = []
            
            for main_category, subcategories in category_mappings.items():
                for subcategory, mitre_tactic in subcategories:
                    tools = self.parse_markdown_table(content, subcategory, mitre_tactic)
                    all_tools.extend(tools)
                    logger.info(f"Parsed {len(tools)} tools from {subcategory}")
            
            # Import all tools
            self.import_tools(all_tools)
            
            return all_tools
            
        except Exception as e:
            logger.error(f"Failed to load and import from file: {e}")
            return []


def main():
    """Main execution function."""
    importer = ToolDataImporter()
    
    # Import from documentation file
    tool_file = '/Users/adminuser/attack-dataset/docs/security/OPSEC_OFFENSIVE_TOOL_REFERENCE.md'
    tools = importer.load_and_import_from_file(tool_file)
    
    if tools:
        logger.info(f"Successfully imported {len(tools)} tools")
        print(f"\nImport Summary:")
        print(f"Total tools imported: {len(tools)}")
        print(f"Categories: {set(tool['category'] for tool in tools)}")
        print(f"Risk levels: {set(tool['risk_level'] for tool in tools)}")
    else:
        logger.error("No tools imported")


if __name__ == "__main__":
    main()