"""
Threat Emulation Service - Combines ML classification with jailbreak.ai for automated threat actor emulation.

This service uses ML model predictions to inform jailbreak.ai's attack planning,
enabling emulation of specific threat actor behaviors during authorized security testing.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from .ml_service import MLModelService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ThreatActorType(Enum):
    """Known threat actor categories for emulation."""
    APT = "Advanced Persistent Threat"
    SCRIPT_KIDDIE = "Script Kiddie"
    RANSOMWARE = "Ransomware Operator"
    HACKTIVIST = "Hacktivist"
    INSIDER_THREAT = "Insider Threat"
    STATE_SPONSORED = "State-Sponsored Actor"
    CYBERCRIME_SYNDICATE = "Cybercrime Syndicate"


@dataclass
class ThreatActorProfile:
    """Profile defining threat actor characteristics."""
    name: str
    actor_type: ThreatActorType
    typical_categories: List[str]
    aggression_level: int
    stealth_level: int
    persistence_level: int
    common_tools: List[str]
    mitre_tactics: List[str]
    description: str


@dataclass
class EmulationPlan:
    """Generated threat emulation plan."""
    target: str
    threat_actor: ThreatActorProfile
    ml_category: str
    ml_confidence: float
    attack_phases: List[Dict[str, Any]]
    recommended_tools: List[str]
    jailbreak_plan: Optional[Dict[str, Any]] = None


class ThreatEmulationService:
    """Service for ML-informed threat emulation using jailbreak.ai."""
    
    # Predefined threat actor profiles
    THREAT_ACTOR_PROFILES = {
        "apt28": ThreatActorProfile(
            name="APT28 (Fancy Bear)",
            actor_type=ThreatActorType.STATE_SPONSORED,
            typical_categories=[
                "Network Security",
                "Web Application Security", 
                "Malware & Threat"
            ],
            aggression_level=7,
            stealth_level=8,
            persistence_level=9,
            common_tools=["XAgent", "Sedreco", "Mimikatz", "Cobalt Strike"],
            mitre_tactics=["Initial Access", "Execution", "Persistence", "Defense Evasion"],
            description="Russian state-sponsored actor known for targeted attacks against government and military"
        ),
        "conti": ThreatActorProfile(
            name="Conti Ransomware Group",
            actor_type=ThreatActorType.RANSOMWARE,
            typical_categories=[
                "Malware & Threat",
                "Network Security",
                "Cloud Security"
            ],
            aggression_level=9,
            stealth_level=6,
            persistence_level=8,
            common_tools=["Ryuk", "TrickBot", "Cobalt Strike", "PowerShell"],
            mitre_tactics=["Initial Access", "Execution", "Impact", "Exfiltration"],
            description="Russian-speaking ransomware operator known for double-extortion attacks"
        ),
        "lazarus": ThreatActorProfile(
            name="Lazarus Group",
            actor_type=ThreatActorType.STATE_SPONSORED,
            typical_categories=[
                "Cryptocurrency",
                "Financial Security",
                "Malware & Threat"
            ],
            aggression_level=8,
            stealth_level=7,
            persistence_level=8,
            common_tools=["AppleJeus", "BeagleBoyz", "Manuscrypt", "PowerShell"],
            mitre_tactics=["Initial Access", "Execution", "Persistence", "Defense Evasion"],
            description="North Korean state-sponsored actor targeting financial institutions and cryptocurrency"
        ),
        "anonymous": ThreatActorProfile(
            name="Anonymous (Hacktivist)",
            actor_type=ThreatActorType.HACKTIVIST,
            typical_categories=[
                "Web Application Security",
                "Network Security",
                "Social Engineering"
            ],
            aggression_level=6,
            stealth_level=4,
            persistence_level=3,
            common_tools=["LOIC", "SQLMap", "Nmap", "Metasploit"],
            mitre_tactics=["Initial Access", "Execution", "Impact"],
            description="Decentralized hacktivist collective known for DDoS attacks and data leaks"
        )
    }
    
    def __init__(self, ml_service: MLModelService):
        """Initialize threat emulation service."""
        self.ml_service = ml_service
        logger.info("Threat Emulation Service initialized")
    
    def classify_target_context(self, target_description: str) -> Dict[str, Any]:
        """
        Use ML to classify target context and predict likely attack categories.
        
        Args:
            target_description: Description of the target environment
            
        Returns:
            ML classification results with category predictions
        """
        try:
            available_models = list(self.ml_service.models.keys())
            if not available_models:
                logger.warning("No ML models available for classification")
                return {"category": "Unknown", "confidence": 0.0}
            
            target_name = available_models[0]
            predictions = self.ml_service.predict(target_name, target_description, top_k=3)
            
            if predictions and len(predictions) > 0:
                top_prediction = predictions[0]
                return {
                    "category": top_prediction.get("label", "Unknown"),
                    "confidence": top_prediction.get("confidence", 0.0),
                    "all_predictions": predictions
                }
            
            return {"category": "Unknown", "confidence": 0.0}
            
        except Exception as e:
            logger.error(f"ML classification failed: {e}")
            return {"category": "Unknown", "confidence": 0.0}
    
    def match_threat_actor(self, ml_category: str) -> List[ThreatActorProfile]:
        """
        Match ML-predicted category to appropriate threat actor profiles.
        
        Args:
            ml_category: ML-predicted attack category
            
        Returns:
            List of matching threat actor profiles ranked by relevance
        """
        matched_profiles = []
        
        for profile_id, profile in self.THREAT_ACTOR_PROFILES.items():
            # Check if ML category matches typical categories for this threat actor
            category_match = any(
                ml_category.lower() in cat.lower() or cat.lower() in ml_category.lower()
                for cat in profile.typical_categories
            )
            
            if category_match:
                matched_profiles.append((profile_id, profile))
        
        # If no direct match, return all profiles sorted by aggression level
        if not matched_profiles:
            matched_profiles = [(pid, p) for pid, p in self.THREAT_ACTOR_PROFILES.items()]
        
        # Sort by relevance (exact matches first) then by aggression level
        matched_profiles.sort(
            key=lambda x: (
                0 if any(ml_category.lower() in cat.lower() for cat in x[1].typical_categories) else 1,
                x[1].aggression_level
            )
        )
        
        return [profile for _, profile in matched_profiles]
    
    def recommend_tools(self, threat_actor: ThreatActorProfile, ml_category: str) -> List[str]:
        """
        Recommend tools based on threat actor profile and ML classification.
        
        Args:
            threat_actor: Threat actor profile
            ml_category: ML-predicted attack category
            
        Returns:
            List of recommended tools for the emulation
        """
        tools = set(threat_actor.common_tools)
        
        # Add category-specific tool recommendations
        category_tool_map = {
            "web": ["Burp Suite", "OWASP ZAP", "SQLMap", "Nmap"],
            "network": ["Nmap", "Wireshark", "Metasploit", "Cobalt Strike"],
            "malware": ["Cuckoo Sandbox", "Ghidra", "IDA Pro", "YARA"],
            "cloud": ["AWS CLI", "Azure CLI", "Terraform", "Pacu"],
            "mobile": ["MobSF", "Frida", "ADB", "Burp Suite"],
            "iot": ["Shodan", "Firmware Mod Kit", "Wireshark", "Nmap"]
        }
        
        for category_key, category_tools in category_tool_map.items():
            if category_key in ml_category.lower():
                tools.update(category_tools)
        
        return list(tools)
    
    def generate_emulation_plan(
        self,
        target: str,
        target_description: str,
        threat_actor_id: Optional[str] = None
    ) -> EmulationPlan:
        """
        Generate a comprehensive threat emulation plan.
        
        Args:
            target: Target system/network
            target_description: Description of the target environment
            threat_actor_id: Optional specific threat actor to emulate
            
        Returns:
            Complete emulation plan with ML insights and tool recommendations
        """
        # Step 1: Classify target context using ML
        ml_classification = self.classify_target_context(target_description)
        ml_category = ml_classification["category"]
        ml_confidence = ml_classification["confidence"]
        
        logger.info(f"ML Classification: {ml_category} (confidence: {ml_confidence:.2f})")
        
        # Step 2: Match threat actor profiles
        if threat_actor_id and threat_actor_id in self.THREAT_ACTOR_PROFILES:
            threat_actor = self.THREAT_ACTOR_PROFILES[threat_actor_id]
        else:
            matched_profiles = self.match_threat_actor(ml_category)
            threat_actor = matched_profiles[0] if matched_profiles else list(self.THREAT_ACTOR_PROFILES.values())[0]
        
        logger.info(f"Selected Threat Actor: {threat_actor.name}")
        
        # Step 3: Recommend tools
        recommended_tools = self.recommend_tools(threat_actor, ml_category)
        
        # Step 4: Generate attack phases based on threat actor profile
        attack_phases = self._generate_attack_phases(threat_actor, ml_category)
        
        # Step 5: Create emulation plan
        plan = EmulationPlan(
            target=target,
            threat_actor=threat_actor,
            ml_category=ml_category,
            ml_confidence=ml_confidence,
            attack_phases=attack_phases,
            recommended_tools=recommended_tools
        )
        
        return plan
    
    def _generate_attack_phases(self, threat_actor: ThreatActorProfile, ml_category: str) -> List[Dict[str, Any]]:
        """Generate attack phases based on threat actor profile and ML classification."""
        phases = []
        
        # Map MITRE tactics to phases
        tactic_phase_map = {
            "Reconnaissance": {
                "duration": "1-3 days",
                "stealth": "high",
                "techniques": ["Passive OSINT", "Active scanning", "Social engineering"]
            },
            "Initial Access": {
                "duration": "1-7 days",
                "stealth": "medium",
                "techniques": ["Phishing", "Exploit public-facing application", "Valid accounts"]
            },
            "Execution": {
                "duration": "hours",
                "stealth": "low",
                "techniques": ["Command-line interface", "PowerShell", "Scripting"]
            },
            "Persistence": {
                "duration": "ongoing",
                "stealth": "high",
                "techniques": ["Scheduled tasks", "Registry run keys", "Web shells"]
            },
            "Defense Evasion": {
                "duration": "ongoing",
                "stealth": "high",
                "techniques": ["Obfuscated files", "Process injection", "Rootkit"]
            },
            "Exfiltration": {
                "duration": "hours-days",
                "stealth": "medium",
                "techniques": ["Exfiltration over C2 channel", "Web service", "DNS"]
            }
        }
        
        for tactic in threat_actor.mitre_tactics:
            if tactic in tactic_phase_map:
                phase_info = tactic_phase_map[tactic].copy()
                phase_info["tactic"] = tactic
                phase_info["ml_informed"] = True
                phases.append(phase_info)
        
        return phases
    
    def generate_jailbreak_payload(self, plan: EmulationPlan) -> Dict[str, Any]:
        """
        Generate jailbreak.ai automation payload based on emulation plan.
        
        Args:
            plan: Threat emulation plan
            
        Returns:
            Jailbreak.ai compatible automation payload
        """
        # Construct phases for jailbreak.ai red team automation
        phases = []
        for phase in plan.attack_phases:
            phases.append({
                "phase": phase["tactic"],
                "techniques": phase["techniques"],
                "estimated_duration": phase["duration"],
                "stealth_level": phase["stealth"]
            })
        
        payload = {
            "operation": "redteam_automation",
            "redteam_config": {
                "target": plan.target,
                "aggression_level": plan.threat_actor.aggression_level,
                "phases": [p["tactic"] for p in plan.attack_phases],
                "threat_actor_profile": plan.threat_actor.name,
                "ml_category": plan.ml_category,
                "ml_confidence": plan.ml_confidence
            },
            "context": {
                "recommended_tools": plan.recommended_tools,
                "attack_phases": phases,
                "stealth_preference": plan.threat_actor.stealth_level > 6
            }
        }
        
        return payload


def get_threat_emulation_service(ml_service: MLModelService) -> ThreatEmulationService:
    """Get or create threat emulation service instance."""
    return ThreatEmulationService(ml_service)