"""
OpSec Audit Engine - Analyzes attack chains for OpSec risks and provides recommendations.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class RiskLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    
    def __lt__(self, other):
        order = ["info", "low", "medium", "high", "critical"]
        return order.index(self.value) < order.index(other.value)
    
    def __gt__(self, other):
        order = ["info", "low", "medium", "high", "critical"]
        return order.index(self.value) > order.index(other.value)

@dataclass
class ToolRisk:
    tool_name: str
    risk_level: RiskLevel
    risk_factors: List[str]
    detection_methods: List[str]
    opsec_recommendations: List[str]
    substitution_alternative: Optional[str] = None

@dataclass
class StepRisk:
    step_index: int
    step_description: str
    tools_found: List[str]
    tool_risks: List[ToolRisk]
    overall_risk: RiskLevel
    recommendations: List[str]

@dataclass
class ChainAuditResult:
    chain_id: str
    chain_description: str
    overall_risk_score: float  # 0-100, higher = more detectable
    overall_risk_level: RiskLevel
    step_risks: List[StepRisk]
    critical_findings: List[str]
    tool_substitutions: Dict[str, str]
    evasive_techniques: List[str]
    detection_coverage: Dict[str, List[str]]  # detection_method -> affected steps

class OpSecAuditEngine:
    """Engine for auditing attack chains for OpSec risks."""
    
    def __init__(self, tool_reference_path: Optional[str] = None):
        """Initialize the OpSec audit engine."""
        if tool_reference_path is None:
            # Look for tool_reference.json in the parent directory (knowledge_engine root)
            tool_reference_path = Path(__file__).parent.parent / 'tool_reference.json'
        
        with open(tool_reference_path, 'r') as f:
            self.tool_data = json.load(f)
        
        self.tool_lookup = self._build_tool_lookup()
        self.risk_keywords = self._build_risk_keywords()
    
    def _build_tool_lookup(self) -> Dict[str, Dict[str, Any]]:
        """Build a lookup dictionary for tools."""
        lookup = {}
        for tactic, tactic_data in self.tool_data['tactics'].items():
            for tool in tactic_data['tools']:
                lookup[tool['name'].lower()] = tool
                # Add common variations
                if ' ' in tool['name']:
                    lookup[tool['name'].lower().replace(' ', '')] = tool
        return lookup
    
    def _build_risk_keywords(self) -> Dict[str, RiskLevel]:
        """Build keyword-based risk detection."""
        return {
            # Critical risk keywords
            'highly signatured': RiskLevel.CRITICAL,
            'heavily flagged': RiskLevel.CRITICAL,
            'heavily monitored': RiskLevel.CRITICAL,
            'very detectable': RiskLevel.CRITICAL,
            'highly detectable': RiskLevel.CRITICAL,
            'trivially detected': RiskLevel.CRITICAL,
            'commercially signatured': RiskLevel.CRITICAL,
            
            # High risk keywords
            'high detection risk': RiskLevel.HIGH,
            'extremely noisy': RiskLevel.HIGH,
            'very noisy': RiskLevel.HIGH,
            'high visibility': RiskLevel.HIGH,
            'easily enumerated': RiskLevel.HIGH,
            'heavily signatured': RiskLevel.HIGH,
            'signatured': RiskLevel.HIGH,
            'monitored': RiskLevel.HIGH,
            'detectable': RiskLevel.HIGH,
            
            # Medium risk keywords
            'similar concerns': RiskLevel.MEDIUM,
            'customizable': RiskLevel.MEDIUM,
            'use with care': RiskLevel.MEDIUM,
            'use with caution': RiskLevel.MEDIUM,
            
            # Low risk keywords
            'passive mode': RiskLevel.LOW,
            'stealthier': RiskLevel.LOW,
            'better opsec': RiskLevel.LOW,
            'lower detection risk': RiskLevel.LOW,
        }
    
    def _extract_tools_from_text(self, text: str) -> List[str]:
        """Extract tool names from text using the tool lookup."""
        found_tools = []
        text_lower = text.lower()
        
        # Check for exact matches first
        for tool_name in self.tool_lookup.keys():
            if tool_name in text_lower:
                # Get the canonical name
                canonical_name = self.tool_lookup[tool_name]['name']
                if canonical_name not in found_tools:
                    found_tools.append(canonical_name)
        
        return found_tools
    
    def _assess_tool_risk(self, tool_name: str) -> ToolRisk:
        """Assess the risk level of a specific tool."""
        tool_key = tool_name.lower()
        if tool_key not in self.tool_lookup:
            # Unknown tool - medium risk
            return ToolRisk(
                tool_name=tool_name,
                risk_level=RiskLevel.MEDIUM,
                risk_factors=["Tool not in reference database"],
                detection_methods=["Unknown detection profile"],
                opsec_recommendations=["Test in lab environment first", "Use custom configurations"]
            )
        
        tool_info = self.tool_lookup[tool_key]
        # Remove markdown formatting and convert to lowercase
        opsec_text = tool_info['opsec_considerations'].replace('**', '').lower()
        
        # Determine risk level based on keywords
        risk_level = RiskLevel.LOW
        risk_factors = []
        
        for keyword, level in self.risk_keywords.items():
            if keyword in opsec_text:
                if level > risk_level:
                    risk_level = level
                risk_factors.append(f"Contains keyword: '{keyword}'")
        
        # Extract detection methods
        detection_methods = [dm.strip() for dm in tool_info['detection_methods'].split(',')]
        
        # Extract recommendations from opsec considerations
        recommendations = []
        if 'use' in opsec_text and 'custom' in opsec_text:
            recommendations.append("Use custom configurations")
        if 'rate limit' in opsec_text or 'rate-limit' in opsec_text:
            recommendations.append("Implement rate limiting")
        if 'timing' in opsec_text:
            recommendations.append("Adjust timing parameters")
        if 'passive' in opsec_text:
            recommendations.append("Use passive mode when available")
        if 'encode' in opsec_text or 'encrypt' in opsec_text:
            recommendations.append("Encode or encrypt traffic")
        if 'rotate' in opsec_text:
            recommendations.append("Rotate infrastructure regularly")
        
        # Check for substitution alternative
        substitution = None
        if tool_name in self.tool_data['substitution_matrix']:
            substitution = self.tool_data['substitution_matrix'][tool_name]['alternative']
        
        return ToolRisk(
            tool_name=tool_name,
            risk_level=risk_level,
            risk_factors=risk_factors if risk_factors else ["Standard risk profile"],
            detection_methods=detection_methods,
            opsec_recommendations=recommendations if recommendations else ["Test in lab environment"],
            substitution_alternative=substitution
        )
    
    def _calculate_step_risk(self, tool_risks: List[ToolRisk]) -> RiskLevel:
        """Calculate overall risk for a step based on tool risks."""
        if not tool_risks:
            return RiskLevel.LOW
        
        # Use the highest risk level among tools
        highest_risk = max(tr.risk_level.value for tr in tool_risks)
        return RiskLevel(highest_risk)
    
    def _calculate_chain_score(self, step_risks: List[StepRisk]) -> float:
        """Calculate overall detectability score for the chain (0-100)."""
        if not step_risks:
            return 0.0
        
        risk_values = {
            RiskLevel.CRITICAL: 90,
            RiskLevel.HIGH: 70,
            RiskLevel.MEDIUM: 50,
            RiskLevel.LOW: 30,
            RiskLevel.INFO: 10
        }
        
        scores = [risk_values[sr.overall_risk] for sr in step_risks]
        
        # Weighted average - critical steps matter more
        if scores:
            return sum(scores) / len(scores)
        return 0.0
    
    def _get_chain_risk_level(self, score: float) -> RiskLevel:
        """Convert numeric score to risk level."""
        if score >= 80:
            return RiskLevel.CRITICAL
        elif score >= 60:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MEDIUM
        elif score >= 20:
            return RiskLevel.LOW
        else:
            return RiskLevel.INFO
    
    def audit_chain(self, chain_id: str, chain_description: str, steps: List[str]) -> ChainAuditResult:
        """
        Audit an attack chain for OpSec risks.
        
        Args:
            chain_id: Unique identifier for the chain
            chain_description: Description of the attack chain
            steps: List of step descriptions in the chain
            
        Returns:
            ChainAuditResult with detailed risk analysis
        """
        step_risks = []
        all_detection_methods = {}
        tool_substitutions = {}
        critical_findings = []
        evasive_techniques = []
        
        for idx, step in enumerate(steps):
            tools_found = self._extract_tools_from_text(step)
            tool_risks = [self._assess_tool_risk(tool) for tool in tools_found]
            
            # Collect recommendations
            recommendations = []
            for tr in tool_risks:
                recommendations.extend(tr.opsec_recommendations)
                if tr.substitution_alternative:
                    tool_substitutions[tr.tool_name] = tr.substitution_alternative
                
                # Track detection methods
                for dm in tr.detection_methods:
                    if dm not in all_detection_methods:
                        all_detection_methods[dm] = []
                    all_detection_methods[dm].append(f"Step {idx + 1}")
            
            # Identify critical findings
            for tr in tool_risks:
                if tr.risk_level == RiskLevel.CRITICAL:
                    critical_findings.append(
                        f"Step {idx + 1}: {tr.tool_name} - {', '.join(tr.risk_factors)}"
                    )
            
            # Identify evasive techniques
            if 'passive' in step.lower() or 'stealth' in step.lower():
                evasive_techniques.append(f"Step {idx + 1}: Passive/stealth technique detected")
            if 'encode' in step.lower() or 'encrypt' in step.lower():
                evasive_techniques.append(f"Step {idx + 1}: Encoding/encryption detected")
            if 'lolbin' in step.lower() or 'living-off' in step.lower():
                evasive_techniques.append(f"Step {idx + 1}: LOLBin technique detected")
            
            overall_risk = self._calculate_step_risk(tool_risks)
            
            step_risks.append(StepRisk(
                step_index=idx,
                step_description=step,
                tools_found=tools_found,
                tool_risks=tool_risks,
                overall_risk=overall_risk,
                recommendations=list(set(recommendations))  # Deduplicate
            ))
        
        overall_score = self._calculate_chain_score(step_risks)
        overall_risk_level = self._get_chain_risk_level(overall_score)
        
        return ChainAuditResult(
            chain_id=chain_id,
            chain_description=chain_description,
            overall_risk_score=overall_score,
            overall_risk_level=overall_risk_level,
            step_risks=step_risks,
            critical_findings=critical_findings,
            tool_substitutions=tool_substitutions,
            evasive_techniques=evasive_techniques,
            detection_coverage=all_detection_methods
        )
    
    def audit_attack_vector(self, attack_vector: Dict[str, Any]) -> ChainAuditResult:
        """
        Audit an attack vector from the knowledge engine.
        
        Args:
            attack_vector: Attack vector dict with 'steps' array
            
        Returns:
            ChainAuditResult with detailed risk analysis
        """
        chain_id = attack_vector.get('id', 'unknown')
        description = attack_vector.get('description', '')
        steps = [s.get('description', '') for s in attack_vector.get('steps', [])]
        
        return self.audit_chain(chain_id, description, steps)
    
    def get_tool_recommendations(self, tool_name: str) -> Dict[str, Any]:
        """Get recommendations for a specific tool."""
        tool_key = tool_name.lower()
        if tool_key not in self.tool_lookup:
            return {
                "tool": tool_name,
                "found": False,
                "message": "Tool not in reference database"
            }
        
        tool_info = self.tool_lookup[tool_key]
        risk = self._assess_tool_risk(tool_name)
        
        result = {
            "tool": tool_name,
            "found": True,
            "description": tool_info['description'],
            "tactic": tool_info['tactic'],
            "subcategory": tool_info['subcategory'],
            "risk_level": risk.risk_level.value,
            "risk_factors": risk.risk_factors,
            "detection_methods": risk.detection_methods,
            "opsec_recommendations": risk.opsec_recommendations,
            "substitution_alternative": risk.substitution_alternative
        }
        
        # Add tool-specific best practices if available
        if tool_name in self.tool_data['best_practices']['tool_specific']:
            result['best_practices'] = self.tool_data['best_practices']['tool_specific'][tool_name]
        
        return result