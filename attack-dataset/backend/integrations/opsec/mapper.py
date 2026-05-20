"""
Detection method mapper for OpSec assessment.

Maps plugin operations to potential detection methods and
provides mapping to MITRE ATT&CK framework techniques.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DetectionMethod(Enum):
    """Common detection methods."""
    NETWORK_MONITORING = "network_monitoring"
    IDS_IPS = "ids_ips"
    FIREWALL = "firewall"
    LOG_ANALYSIS = "log_analysis"
    BEHAVIORAL_ANALYSIS = "behavioral_analysis"
    SIEM = "siem"
    EDR = "edr"
    HIDS = "hids"
    NIDS = "nids"
    APPLICATION_MONITORING = "application_monitoring"
    DATABASE_MONITORING = "database_monitoring"
    AUTHENTICATION_MONITORING = "authentication_monitoring"
    FILE_INTEGRITY = "file_integrity"
    MEMORY_ANALYSIS = "memory_analysis"
    API_MONITORING = "api_monitoring"


@dataclass
class MITRETechnique:
    """MITRE ATT&CK technique mapping."""
    technique_id: str
    technique_name: str
    tactic: str
    sub_techniques: List[str] = None


class DetectionMethodMapper:
    """Maps plugin operations to detection methods and MITRE ATT&CK techniques."""
    
    def __init__(self):
        # Plugin to detection methods mapping
        self.plugin_detection_map = {
            'nmap': [
                DetectionMethod.NETWORK_MONITORING,
                DetectionMethod.NIDS,
                DetectionMethod.FIREWALL,
                DetectionMethod.SIEM
            ],
            'hydra': [
                DetectionMethod.AUTHENTICATION_MONITORING,
                DetectionMethod.LOG_ANALYSIS,
                DetectionMethod.SIEM,
                DetectionMethod.EDR
            ],
            'metasploit': [
                DetectionMethod.EDR,
                DetectionMethod.HIDS,
                DetectionMethod.MEMORY_ANALYSIS,
                DetectionMethod.BEHAVIORAL_ANALYSIS,
                DetectionMethod.SIEM
            ],
            'sqlmap': [
                DetectionMethod.APPLICATION_MONITORING,
                DetectionMethod.DATABASE_MONITORING,
                DetectionMethod.WAF,
                DetectionMethod.SIEM
            ],
            'nikto': [
                DetectionMethod.APPLICATION_MONITORING,
                DetectionMethod.WAF,
                DetectionMethod.NETWORK_MONITORING,
                DetectionMethod.SIEM
            ],
            'jailbreak_ai': [
                DetectionMethod.API_MONITORING,
                DetectionMethod.NETWORK_MONITORING,
                DetectionMethod.SIEM
            ]
        }
        
        # MITRE ATT&CK technique mappings
        self.mitre_mappings = {
            'nmap': [
                MITRETechnique(
                    technique_id="T1046",
                    technique_name="Network Service Scanning",
                    tactic="Discovery"
                ),
                MITRETechnique(
                    technique_id="T1595.002",
                    technique_name="Vulnerability Scanning",
                    tactic="Reconnaissance"
                )
            ],
            'hydra': [
                MITRETechnique(
                    technique_id="T1110",
                    technique_name="Brute Force",
                    tactic="Credential Access"
                ),
                MITRETechnique(
                    technique_id="T1110.001",
                    technique_name="Password Guessing",
                    tactic="Credential Access"
                )
            ],
            'metasploit': [
                MITRETechnique(
                    technique_id="T1190",
                    technique_name="Exploit Public-Facing Application",
                    tactic="Initial Access"
                ),
                MITRETechnique(
                    technique_id="T1068",
                    technique_name="Exploitation for Privilege Escalation",
                    tactic="Privilege Escalation"
                ),
                MITRETechnique(
                    technique_id="T1203",
                    technique_name="Exploitation for Client Execution",
                    tactic="Execution"
                )
            ],
            'sqlmap': [
                MITRETechnique(
                    technique_id="T1190",
                    technique_name="Exploit Public-Facing Application",
                    tactic="Initial Access"
                ),
                MITRETechnique(
                    technique_id="T1190.001",
                    technique_name="SQL Injection",
                    tactic="Initial Access"
                )
            ],
            'nikto': [
                MITRETechnique(
                    technique_id="T1595.002",
                    technique_name="Vulnerability Scanning",
                    tactic="Reconnaissance"
                ),
                MITRETechnique(
                    technique_id="T1190",
                    technique_name="Exploit Public-Facing Application",
                    tactic="Initial Access"
                )
            ],
            'jailbreak_ai': [
                MITRETechnique(
                    technique_id="T1589",
                    technique_name="Gather Victim Identity Information",
                    tactic="Reconnaissance"
                ),
                MITRETechnique(
                    technique_id="T1583",
                    technique_name="Acquire Infrastructure",
                    tactic="Resource Development"
                )
            ]
        }
        
        # Operation-specific detection methods
        self.operation_detection_map = {
            'port_scan': [
                DetectionMethod.NETWORK_MONITORING,
                DetectionMethod.NIDS,
                DetectionMethod.FIREWALL
            ],
            'vulnerability_scan': [
                DetectionMethod.APPLICATION_MONITORING,
                DetectionMethod.NETWORK_MONITORING,
                DetectionMethod.SIEM
            ],
            'brute_force': [
                DetectionMethod.AUTHENTICATION_MONITORING,
                DetectionMethod.LOG_ANALYSIS,
                DetectionMethod.EDR
            ],
            'exploitation': [
                DetectionMethod.EDR,
                DetectionMethod.HIDS,
                DetectionMethod.MEMORY_ANALYSIS,
                DetectionMethod.BEHAVIORAL_ANALYSIS
            ],
            'sql_injection': [
                DetectionMethod.APPLICATION_MONITORING,
                DetectionMethod.DATABASE_MONITORING,
                DetectionMethod.WAF
            ],
            'web_scan': [
                DetectionMethod.APPLICATION_MONITORING,
                DetectionMethod.WAF,
                DetectionMethod.NETWORK_MONITORING
            ]
        }
    
    def map_detection_methods(
        self,
        plugin_name: str,
        operation: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Map plugin operation to detection methods.
        
        Args:
            plugin_name: Name of the plugin
            operation: Specific operation (optional)
            parameters: Operation parameters (optional)
        
        Returns:
            List of detection method mappings with details
        """
        detection_methods = []
        
        # Get base detection methods for plugin
        base_methods = self.plugin_detection_map.get(plugin_name, [
            DetectionMethod.NETWORK_MONITORING,
            DetectionMethod.LOG_ANALYSIS
        ])
        
        # Add operation-specific methods if provided
        if operation:
            operation_methods = self.operation_detection_map.get(operation, [])
            base_methods.extend(operation_methods)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_methods = []
        for method in base_methods:
            if method not in seen:
                seen.add(method)
                unique_methods.append(method)
        
        # Build detailed mappings
        for method in unique_methods:
            detection_methods.append({
                'method': method.value,
                'category': self._get_method_category(method),
                'description': self._get_method_description(method),
                'severity': self._get_method_severity(method),
                'mitigation': self._get_method_mitigation(method)
            })
        
        return detection_methods
    
    def map_mitre_techniques(
        self,
        plugin_name: str,
        operation: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Map plugin operation to MITRE ATT&CK techniques.
        
        Args:
            plugin_name: Name of the plugin
            operation: Specific operation (optional)
        
        Returns:
            List of MITRE technique mappings
        """
        techniques = []
        
        base_techniques = self.mitre_mappings.get(plugin_name, [])
        
        for technique in base_techniques:
            techniques.append({
                'technique_id': technique.technique_id,
                'technique_name': technique.technique_name,
                'tactic': technique.tactic,
                'url': f"https://attack.mitre.org/techniques/{technique.technique_id}",
                'sub_techniques': technique.sub_techniques or []
            })
        
        return techniques
    
    def get_detection_summary(
        self,
        plugin_name: str,
        operation: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive detection summary.
        
        Args:
            plugin_name: Name of the plugin
            operation: Specific operation (optional)
            parameters: Operation parameters (optional)
        
        Returns:
            Comprehensive detection summary
        """
        detection_methods = self.map_detection_methods(plugin_name, operation, parameters)
        mitre_techniques = self.map_mitre_techniques(plugin_name, operation)
        
        # Calculate overall detection risk
        high_severity_count = sum(1 for m in detection_methods if m['severity'] == 'high')
        medium_severity_count = sum(1 for m in detection_methods if m['severity'] == 'medium')
        
        if high_severity_count > 2:
            overall_risk = 'critical'
        elif high_severity_count > 0:
            overall_risk = 'high'
        elif medium_severity_count > 2:
            overall_risk = 'medium'
        else:
            overall_risk = 'low'
        
        return {
            'plugin': plugin_name,
            'operation': operation,
            'overall_detection_risk': overall_risk,
            'detection_methods': detection_methods,
            'mitre_techniques': mitre_techniques,
            'method_count': len(detection_methods),
            'technique_count': len(mitre_techniques),
            'high_severity_methods': high_severity_count,
            'medium_severity_methods': medium_severity_count
        }
    
    def _get_method_category(self, method: DetectionMethod) -> str:
        """Get category for detection method."""
        network_methods = [
            DetectionMethod.NETWORK_MONITORING,
            DetectionMethod.NIDS,
            DetectionMethod.FIREWALL
        ]
        
        host_methods = [
            DetectionMethod.HIDS,
            DetectionMethod.EDR,
            DetectionMethod.FILE_INTEGRITY,
            DetectionMethod.MEMORY_ANALYSIS
        ]
        
        application_methods = [
            DetectionMethod.APPLICATION_MONITORING,
            DetectionMethod.DATABASE_MONITORING,
            DetectionMethod.API_MONITORING
        ]
        
        log_methods = [
            DetectionMethod.LOG_ANALYSIS,
            DetectionMethod.SIEM,
            DetectionMethod.AUTHENTICATION_MONITORING
        ]
        
        if method in network_methods:
            return 'network'
        elif method in host_methods:
            return 'host'
        elif method in application_methods:
            return 'application'
        elif method in log_methods:
            return 'log'
        else:
            return 'other'
    
    def _get_method_description(self, method: DetectionMethod) -> str:
        """Get description for detection method."""
        descriptions = {
            DetectionMethod.NETWORK_MONITORING: "Passive monitoring of network traffic for anomalies",
            DetectionMethod.IDS_IPS: "Intrusion Detection/Prevention Systems with signature-based detection",
            DetectionMethod.FIREWALL: "Network firewalls filtering and logging traffic",
            DetectionMethod.LOG_ANALYSIS: "Analysis of system and application logs for suspicious activity",
            DetectionMethod.BEHAVIORAL_ANALYSIS: "Analysis of system behavior for anomalies",
            DetectionMethod.SIEM: "Security Information and Event Management correlation",
            DetectionMethod.EDR: "Endpoint Detection and Response monitoring",
            DetectionMethod.HIDS: "Host-based Intrusion Detection Systems",
            DetectionMethod.NIDS: "Network-based Intrusion Detection Systems",
            DetectionMethod.APPLICATION_MONITORING: "Application-level monitoring and WAF",
            DetectionMethod.DATABASE_MONITORING: "Database query and access monitoring",
            DetectionMethod.AUTHENTICATION_MONITORING: "Authentication and authorization monitoring",
            DetectionMethod.FILE_INTEGRITY: "File integrity monitoring for changes",
            DetectionMethod.MEMORY_ANALYSIS: "Memory analysis for malicious code",
            DetectionMethod.API_MONITORING: "API request monitoring and rate limiting"
        }
        return descriptions.get(method, "Unknown detection method")
    
    def _get_method_severity(self, method: DetectionMethod) -> str:
        """Get severity level for detection method."""
        high_severity = [
            DetectionMethod.EDR,
            DetectionMethod.BEHAVIORAL_ANALYSIS,
            DetectionMethod.MEMORY_ANALYSIS
        ]
        
        medium_severity = [
            DetectionMethod.IDS_IPS,
            DetectionMethod.NIDS,
            DetectionMethod.HIDS,
            DetectionMethod.SIEM,
            DetectionMethod.APPLICATION_MONITORING
        ]
        
        if method in high_severity:
            return 'high'
        elif method in medium_severity:
            return 'medium'
        else:
            return 'low'
    
    def _get_method_mitigation(self, method: DetectionMethod) -> str:
        """Get mitigation recommendation for detection method."""
        mitigations = {
            DetectionMethod.NETWORK_MONITORING: "Use encrypted channels and obfuscation",
            DetectionMethod.IDS_IPS: "Use polymorphic techniques and evasion methods",
            DetectionMethod.FIREWALL: "Use allowed protocols and ports",
            DetectionMethod.LOG_ANALYSIS: "Minimize log generation and use stealth",
            DetectionMethod.BEHAVIORAL_ANALYSIS: "Mimic legitimate behavior patterns",
            DetectionMethod.SIEM: "Avoid correlation patterns and use timing",
            DetectionMethod.EDR: "Use living-off-the-land techniques",
            DetectionMethod.HIDS: "Avoid file system modifications",
            DetectionMethod.NIDS: "Use encrypted traffic and fragmentation",
            DetectionMethod.APPLICATION_MONITORING: "Use valid API calls and parameters",
            DetectionMethod.DATABASE_MONITORING: "Use parameterized queries",
            DetectionMethod.AUTHENTICATION_MONITORING: "Use slow timing and account rotation",
            DetectionMethod.FILE_INTEGRITY: "Avoid file modifications where possible",
            DetectionMethod.MEMORY_ANALYSIS: "Use file-less techniques",
            DetectionMethod.API_MONITORING: "Mimic legitimate API usage patterns"
        }
        return mitigations.get(method, "Unknown mitigation")