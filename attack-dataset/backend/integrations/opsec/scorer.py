"""
Risk scoring engine for OpSec assessment.

Calculates risk scores based on various factors:
- Network traffic patterns
- Tool signatures
- Timing characteristics
- Service interactions
- Target environment
- Tool-specific risk from database
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


@dataclass
class RiskFactors:
    """Risk factors for scoring."""
    network_noise: int = 0  # 0-100
    tool_signature: int = 0  # 0-100
    timing_pattern: int = 0  # 0-100
    service_exposure: int = 0  # 0-100
    target_sensitivity: int = 0  # 0-100
    detection_likelihood: int = 0  # 0-100


@dataclass
class RiskScore:
    """Comprehensive risk score."""
    overall_score: int  # 0-100
    risk_level: RiskLevel
    factors: RiskFactors
    recommendations: List[str]
    detection_methods: List[str]
    evasion_opportunities: List[str]


class RiskScorer:
    """Engine for calculating operational security risk scores."""
    
    def __init__(self, db_config: Optional[Dict[str, Any]] = None):
        # Weightings for different risk factors
        self.weights = {
            'network_noise': 0.20,
            'tool_signature': 0.15,
            'timing_pattern': 0.10,
            'service_exposure': 0.10,
            'target_sensitivity': 0.15,
            'detection_likelihood': 0.10,
            'tool_specific_risk': 0.20  # New weight for tool-specific risk
        }
        
        # Database configuration for tool risk data
        self.db_config = db_config or {
            'host': 'localhost',
            'port': 5432,
            'database': 'attack_db',
            'user': 'opsec',
            'password': 'opsec'
        }
        
        # Known tool signatures and their detection risk (fallback if DB unavailable)
        self.tool_signatures = {
            'nmap': 85,
            'metasploit': 90,
            'hydra': 80,
            'sqlmap': 85,
            'nikto': 75,
            'burpsuite': 80,
            'wireshark': 70,
            'tcpdump': 60,
            'curl': 30,
            'wget': 30,
            'python': 40
        }
        
        # Service exposure risks
        self.service_risks = {
            'ssh': 60,
            'http': 50,
            'https': 45,
            'ftp': 70,
            'telnet': 90,
            'rdp': 75,
            'smb': 80,
            'dns': 40,
            'mysql': 65,
            'postgresql': 65,
            'mongodb': 70,
            'redis': 85,
            'elasticsearch': 60
        }
        
        # Cache for tool-specific risk data
        self._tool_risk_cache = {}
    
    def _get_db_connection(self):
        """Get database connection for tool risk data."""
        try:
            return psycopg2.connect(**self.db_config, cursor_factory=RealDictCursor)
        except Exception as e:
            logger.warning(f"Failed to connect to database for tool risk data: {e}")
            return None
    
    def _load_tool_risk_from_db(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Load tool-specific risk data from database."""
        if tool_name in self._tool_risk_cache:
            return self._tool_risk_cache[tool_name]
        
        conn = self._get_db_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT risk_level, noise_level, stealth_level, detection_methods, opsec_considerations FROM offensive_tools WHERE name = %s",
                (tool_name,)
            )
            row = cursor.fetchone()
            
            if row:
                tool_risk = {
                    'risk_level': row['risk_level'],
                    'noise_level': row['noise_level'],
                    'stealth_level': row['stealth_level'],
                    'detection_methods': row['detection_methods'],
                    'opsec_considerations': row['opsec_considerations']
                }
                self._tool_risk_cache[tool_name] = tool_risk
                return tool_risk
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to load tool risk for {tool_name}: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def _get_tool_specific_risk_score(self, tool_name: str) -> int:
        """Get tool-specific risk score from database or fallback."""
        tool_risk = self._load_tool_risk_from_db(tool_name)
        
        if tool_risk:
            # Convert risk level to score
            risk_scores = {'critical': 95, 'high': 75, 'medium': 50, 'low': 25}
            base_score = risk_scores.get(tool_risk['risk_level'], 50)
            
            # Adjust based on noise level
            base_score += (tool_risk['noise_level'] - 50) // 2
            
            # Adjust based on stealth level (higher stealth = lower risk)
            base_score -= (tool_risk['stealth_level'] - 50) // 2
            
            return max(0, min(100, base_score))
        else:
            # Fallback to static signatures
            return self.tool_signatures.get(tool_name.lower(), 50)
    
    def calculate_risk(
        self,
        plugin_name: str,
        parameters: Dict[str, Any],
        target: str,
        context: Optional[Dict[str, Any]] = None
    ) -> RiskScore:
        """
        Calculate comprehensive risk score for an operation.
        
        Args:
            plugin_name: Name of the plugin being executed
            parameters: Operation parameters
            target: Target of the operation
            context: Additional context (optional)
        
        Returns:
            RiskScore with comprehensive assessment
        """
        factors = RiskFactors()
        
        # Calculate individual risk factors
        factors.network_noise = self._assess_network_noise(plugin_name, parameters)
        factors.tool_signature = self._get_tool_specific_risk_score(plugin_name)  # Use DB data
        factors.timing_pattern = self._assess_timing_pattern(parameters)
        factors.service_exposure = self._assess_service_exposure(parameters)
        factors.target_sensitivity = self._assess_target_sensitivity(target, context)
        factors.detection_likelihood = self._assess_detection_likelihood(factors)
        
        # Calculate weighted overall score
        overall_score = self._calculate_weighted_score(factors)
        
        # Determine risk level
        risk_level = self._determine_risk_level(overall_score)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(factors, plugin_name)
        
        # Identify detection methods
        detection_methods = self._identify_detection_methods_enhanced(plugin_name, parameters)
        
        # Identify evasion opportunities
        evasion_opportunities = self._identify_evasion_opportunities_enhanced(factors, plugin_name)
        
        return RiskScore(
            overall_score=overall_score,
            risk_level=risk_level,
            factors=factors,
            recommendations=recommendations,
            detection_methods=detection_methods,
            evasion_opportunities=evasion_opportunities
        )
    
    def _assess_network_noise(self, plugin_name: str, parameters: Dict[str, Any]) -> int:
        """Assess network noise level (0-100)."""
        noise_score = 0
        
        # Check for port scanning (high noise)
        if plugin_name == 'nmap':
            scan_type = parameters.get('scan_type', '')
            if scan_type in ['syn', 'connect']:
                noise_score += 70
            elif scan_type in ['udp', 'sctp']:
                noise_score += 60
            else:
                noise_score += 50
            
            # Timing affects noise
            timing = parameters.get('timing', 'T3')
            timing_scores = {'T0': 20, 'T1': 35, 'T2': 50, 'T3': 65, 'T4': 80, 'T5': 90}
            noise_score += timing_scores.get(timing, 65)
        
        # Check for brute force (very high noise)
        elif plugin_name == 'hydra':
            noise_score += 90
        
        # Check for web scanning (medium-high noise)
        elif plugin_name in ['nikto', 'sqlmap']:
            noise_score += 75
        
        # Check for exploitation (very high noise)
        elif plugin_name == 'metasploit':
            noise_score += 95
        
        return min(noise_score, 100)
    
    def _identify_detection_methods_enhanced(self, plugin_name: str, parameters: Dict[str, Any]) -> List[str]:
        """Identify potential detection methods using database data."""
        tool_risk = self._load_tool_risk_from_db(plugin_name)
        
        if tool_risk and tool_risk.get('detection_methods'):
            return tool_risk['detection_methods']
        else:
            # Fallback to default detection methods
            detection_methods = []
            
            if plugin_name == 'nmap':
                detection_methods.extend([
                    "IDS/IPS signature detection",
                    "Firewall connection tracking",
                    "Port scan detection algorithms",
                    "Network traffic analysis"
                ])
                if parameters.get('scan_type') == 'syn':
                    detection_methods.append("SYN flood detection")
            
            elif plugin_name == 'hydra':
                detection_methods.extend([
                    "Authentication log monitoring",
                    "Account lockout mechanisms",
                    "Brute force detection systems",
                    "Rate limiting on authentication"
                ])
            
            elif plugin_name == 'metasploit':
                detection_methods.extend([
                    "Exploit attempt signatures",
                    "Shellcode detection",
                    "Memory integrity monitoring",
                    "Behavioral analysis"
                ])
            
            elif plugin_name == 'sqlmap':
                detection_methods.extend([
                    "WAF SQL injection detection",
                    "Database query monitoring",
                    "Application log analysis",
                    "Input validation systems"
                ])
            
            else:
                detection_methods.extend([
                    "Network traffic monitoring",
                    "System log analysis",
                    "Behavioral anomaly detection"
                ])
            
            return detection_methods
    
    def _identify_evasion_opportunities_enhanced(self, factors: RiskFactors, plugin_name: str) -> List[str]:
        """Identify potential evasion opportunities using database data."""
        tool_risk = self._load_tool_risk_from_db(plugin_name)
        
        opportunities = []
        
        # Add general evasion opportunities
        if factors.network_noise > 50:
            opportunities.append("Timing delays can reduce detection likelihood")
            opportunities.append("Decoy scans can confuse correlation")
        
        if factors.tool_signature > 50:
            opportunities.append("Tool obfuscation techniques available")
            opportunities.append("Alternative tools may provide better stealth")
        
        if factors.timing_pattern > 50:
            opportunities.append("Randomized timing can break patterns")
            opportunities.append("Scheduling during maintenance windows")
        
        # Add tool-specific opportunities from database
        if tool_risk and tool_risk.get('opsec_considerations'):
            opsec_text = tool_risk['opsec_considerations']
            
            if 'stealthier' in opsec_text.lower():
                opportunities.append(f"{plugin_name}: Consider stealthier alternatives")
            if 'passive' in opsec_text.lower():
                opportunities.append(f"{plugin_name}: Use passive mode if available")
            if 'timing' in opsec_text.lower():
                opportunities.append(f"{plugin_name}: Adjust timing parameters")
            if 'decoy' in opsec_text.lower():
                opportunities.append(f"{plugin_name}: Use decoy techniques")
        
        # Add plugin-specific opportunities
        if plugin_name == 'nmap':
            opportunities.append("Stealth scan modes available (-sS, -sF, -sX)")
            opportunities.append("Fragmentation can evade some IDS")
            opportunities.append("Decoy scans can obscure source")
        
        elif plugin_name == 'hydra':
            opportunities.append("Very slow timing can avoid lockouts")
            opportunities.append("Distributed attacks can bypass rate limits")
        
        return opportunities
    
    def _assess_timing_pattern(self, parameters: Dict[str, Any]) -> int:
        """Assess timing pattern detection risk (0-100)."""
        timing_score = 50  # Default medium risk
        
        # Check for explicit timing controls
        if 'delay' in parameters:
            delay = parameters['delay']
            if delay < 1:
                timing_score += 20  # Very fast is suspicious
            elif delay > 10:
                timing_score -= 20  # Slower is less suspicious
        
        if 'timing' in parameters:
            timing = parameters['timing']
            if timing in ['T4', 'T5']:
                timing_score += 15
            elif timing in ['T0', 'T1']:
                timing_score -= 15
        
        return max(0, min(timing_score, 100))
    
    def _assess_service_exposure(self, parameters: Dict[str, Any]) -> int:
        """Assess service exposure risk (0-100)."""
        exposure_score = 0
        
        # Check for service-specific operations
        if 'ports' in parameters:
            ports = parameters['ports']
            if isinstance(ports, str):
                # Count port numbers
                port_count = len(ports.split(','))
                exposure_score += min(port_count * 5, 50)
            elif isinstance(ports, int):
                exposure_score += 10
        
        if 'services' in parameters:
            services = parameters['services']
            if isinstance(services, list):
                for service in services:
                    service_name = service.split(':')[0].lower()
                    exposure_score += self.service_risks.get(service_name, 50)
        
        return min(exposure_score, 100)
    
    def _assess_target_sensitivity(self, target: str, context: Optional[Dict[str, Any]]) -> int:
        """Assess target sensitivity (0-100)."""
        sensitivity_score = 50  # Default medium
        
        if not context:
            return sensitivity_score
        
        # Check for target type
        target_type = context.get('target_type', 'unknown')
        if target_type == 'production':
            sensitivity_score += 30
        elif target_type == 'staging':
            sensitivity_score += 15
        elif target_type == 'development':
            sensitivity_score -= 10
        
        # Check for network zone
        network_zone = context.get('network_zone', 'unknown')
        if network_zone == 'dmz':
            sensitivity_score += 10
        elif network_zone == 'internal':
            sensitivity_score += 25
        elif network_zone == 'internet':
            sensitivity_score += 35
        
        # Check for compliance requirements
        compliance = context.get('compliance', [])
        if 'pci_dss' in compliance:
            sensitivity_score += 20
        if 'hipaa' in compliance:
            sensitivity_score += 25
        if 'gdpr' in compliance:
            sensitivity_score += 20
        
        return max(0, min(sensitivity_score, 100))
    
    def _assess_detection_likelihood(self, factors: RiskFactors) -> int:
        """Assess overall detection likelihood (0-100)."""
        # Detection likelihood is based on the highest risk factor
        return max(
            factors.network_noise,
            factors.tool_signature,
            factors.timing_pattern,
            factors.service_exposure
        )
    
    def _calculate_weighted_score(self, factors: RiskFactors) -> int:
        """Calculate weighted overall risk score."""
        weighted = (
            factors.network_noise * self.weights['network_noise'] +
            factors.tool_signature * self.weights['tool_signature'] +
            factors.timing_pattern * self.weights['timing_pattern'] +
            factors.service_exposure * self.weights['service_exposure'] +
            factors.target_sensitivity * self.weights['target_sensitivity'] +
            factors.detection_likelihood * self.weights['detection_likelihood']
        )
        return int(weighted)
    
    def _determine_risk_level(self, score: int) -> RiskLevel:
        """Determine risk level from score."""
        if score >= 80:
            return RiskLevel.CRITICAL
        elif score >= 60:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MEDIUM
        elif score >= 20:
            return RiskLevel.LOW
        else:
            return RiskLevel.MINIMAL
    
    def _generate_recommendations(self, factors: RiskFactors, plugin_name: str) -> List[str]:
        """Generate risk mitigation recommendations."""
        recommendations = []
        
        if factors.network_noise > 70:
            recommendations.append("Reduce network noise by using slower timing profiles")
            recommendations.append("Consider using stealth scan techniques")
            recommendations.append("Stagger operations to reduce burst traffic")
        
        if factors.tool_signature > 70:
            recommendations.append("Obfuscate tool signatures where possible")
            recommendations.append("Use alternative tools with lower detection profiles")
            recommendations.append("Consider custom or modified tools")
        
        if factors.timing_pattern > 70:
            recommendations.append("Add random delays between operations")
            recommendations.append("Vary operation timing to avoid patterns")
            recommendations.append("Schedule operations during low-traffic periods")
        
        if factors.service_exposure > 70:
            recommendations.append("Limit scope to specific services only")
            recommendations.append("Avoid unnecessary port/service enumeration")
            recommendations.append("Focus on high-value targets only")
        
        if factors.target_sensitivity > 70:
            recommendations.append("Ensure proper authorization is documented")
            recommendations.append("Consider running in a test environment first")
            recommendations.append("Implement additional monitoring and alerting")
        
        # Plugin-specific recommendations
        if plugin_name == 'nmap':
            recommendations.append("Use decoy scans if available")
            recommendations.append("Consider source IP spoofing (if legal)")
            recommendations.append("Use fragmented packets to evade IDS")
        
        elif plugin_name == 'hydra':
            recommendations.append("Use very slow timing to avoid lockouts")
            recommendations.append("Implement delay between attempts")
            recommendations.append("Use targeted wordlists, not brute force")
        
        if not recommendations:
            recommendations.append("Operation appears to have acceptable risk profile")
        
        return recommendations
    
    def _identify_detection_methods(self, plugin_name: str, parameters: Dict[str, Any]) -> List[str]:
        """Identify potential detection methods."""
        detection_methods = []
        
        if plugin_name == 'nmap':
            detection_methods.extend([
                "IDS/IPS signature detection",
                "Firewall connection tracking",
                "Port scan detection algorithms",
                "Network traffic analysis"
            ])
            if parameters.get('scan_type') == 'syn':
                detection_methods.append("SYN flood detection")
        
        elif plugin_name == 'hydra':
            detection_methods.extend([
                "Authentication log monitoring",
                "Account lockout mechanisms",
                "Brute force detection systems",
                "Rate limiting on authentication"
            ])
        
        elif plugin_name == 'metasploit':
            detection_methods.extend([
                "Exploit attempt signatures",
                "Shellcode detection",
                "Memory integrity monitoring",
                "Behavioral analysis"
            ])
        
        elif plugin_name == 'sqlmap':
            detection_methods.extend([
                "WAF SQL injection detection",
                "Database query monitoring",
                "Application log analysis",
                "Input validation systems"
            ])
        
        else:
            detection_methods.extend([
                "Network traffic monitoring",
                "System log analysis",
                "Behavioral anomaly detection"
            ])
        
        return detection_methods
    
    def _identify_evasion_opportunities(self, factors: RiskFactors, plugin_name: str) -> List[str]:
        """Identify potential evasion opportunities."""
        opportunities = []
        
        if factors.network_noise > 50:
            opportunities.append("Timing delays can reduce detection likelihood")
            opportunities.append("Decoy scans can confuse correlation")
        
        if factors.tool_signature > 50:
            opportunities.append("Tool obfuscation techniques available")
            opportunities.append("Alternative tools may provide better stealth")
        
        if factors.timing_pattern > 50:
            opportunities.append("Randomized timing can break patterns")
            opportunities.append("Scheduling during maintenance windows")
        
        # Plugin-specific opportunities
        if plugin_name == 'nmap':
            opportunities.append("Stealth scan modes available (-sS, -sF, -sX)")
            opportunities.append("Fragmentation can evade some IDS")
            opportunities.append("Decoy scans can obscure source")
        
        elif plugin_name == 'hydra':
            opportunities.append("Very slow timing can avoid lockouts")
            opportunities.append("Distributed attacks can bypass rate limits")
        
        return opportunities