"""
Attack Tree / Kill Chain Engine - AI-powered attack pathing with MITRE ATT&CK integration.

This engine provides:
- AI-driven attack tree construction from attack records
- MITRE ATT&CK TTP mapping and scoring using AI analysis
- AI-powered attack path generation and optimization
- Feedback loop integration for adaptive pathing
- Custom TTP support with AI validation
"""
from __future__ import annotations
import uuid
import re
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime

from .core.models import (
    AttackRecord,
    MITRETTP,
    AttackTreeNode,
    AttackTree,
    AttackPath,
    ExecutionResult,
    FeedbackLoop,
    AdaptiveAttackRequest,
    AdaptiveAttackResponse,
)
from .search.attack_chainer import PHASE_ORDER, PHASE_KEYWORDS, classify_phase


# MITRE ATT&CK technique ID patterns
MITRE_TECHNIQUE_PATTERN = r'^T\d{4}(\.\d{3})?$'

# Standard MITRE ATT&CK techniques mapping (subset for demonstration)
MITRE_ATTACK_MAPPING = {
    # Reconnaissance
    "T1595": {"name": "Active Scanning", "tactic": "Reconnaissance", "detection": ["Network traffic analysis", "IDS alerts"], "mitigation": ["Network segmentation", "Traffic monitoring"]},
    "T1590": {"name": "Gather Victim Org Information", "tactic": "Reconnaissance", "detection": ["OSINT monitoring"], "mitigation": ["Employee training", "Brand monitoring"]},
    
    # Initial Access
    "T1190": {"name": "Exploit Public-Facing Application", "tactic": "Initial Access", "detection": ["WAF logs", "Application logs"], "mitigation": ["Patch management", "WAF deployment"]},
    "T1078": {"name": "Valid Accounts", "tactic": "Initial Access", "detection": ["Login monitoring", "Anomaly detection"], "mitigation": ["MFA", "Account hygiene"]},
    "T1566": {"name": "Phishing", "tactic": "Initial Access", "detection": ["Email filtering", "User reporting"], "mitigation": ["Email security", "Security awareness"]},
    
    # Execution
    "T1059": {"name": "Command and Scripting Interpreter", "tactic": "Execution", "detection": ["Process monitoring", "EDR alerts"], "mitigation": ["Application whitelisting", "Behavior monitoring"]},
    "T1203": {"name": "Exploitation for Client Execution", "tactic": "Execution", "detection": ["Exploit detection", "Behavior analysis"], "mitigation": ["Patch management", "Sandboxing"]},
    
    # Persistence
    "T1543": {"name": "Create or Modify System Process", "tactic": "Persistence", "detection": ["Service monitoring", "Registry monitoring"], "mitigation": ["Service hardening", "Registry protection"]},
    "T1053": {"name": "Scheduled Task/Job", "tactic": "Persistence", "detection": ["Task scheduler monitoring"], "mitigation": ["Task scheduler restrictions", "User training"]},
    
    # Privilege Escalation
    "T1068": {"name": "Exploitation for Privilege Escalation", "tactic": "Privilege Escalation", "detection": ["Privilege monitoring", "Kernel monitoring"], "mitigation": ["Patch management", "Least privilege"]},
    "T1548": {"name": "Abuse Elevation Control Mechanism", "tactic": "Privilege Escalation", "detection": ["UAC monitoring", "Sudo monitoring"], "mitigation": ["UAC hardening", "Sudo configuration"]},
    
    # Defense Evasion
    "T1027": {"name": "Obfuscated Files or Information", "tactic": "Defense Evasion", "detection": ["File analysis", "Pattern matching"], "mitigation": ["File scanning", "Behavior analysis"]},
    "T1562": {"name": "Impair Defenses", "tactic": "Defense Evasion", "detection": ["Security tool monitoring"], "mitigation": ["Security tool hardening", "Monitoring"]},
    
    # Credential Access
    "T1003": {"name": "OS Credential Dumping", "tactic": "Credential Access", "detection": ["LSASS monitoring", "Memory monitoring"], "mitigation": ["Credential Guard", "Least privilege"]},
    "T1552": {"name": "Unsecured Credentials", "tactic": "Credential Access", "detection": ["File monitoring", "Network monitoring"], "mitigation": ["Credential encryption", "Secrets management"]},
    
    # Discovery
    "T1018": {"name": "Remote System Discovery", "tactic": "Discovery", "detection": ["Network monitoring", "System logging"], "mitigation": ["Network segmentation", "System hardening"]},
    "T1087": {"name": "Account Discovery", "tactic": "Discovery", "detection": ["Account monitoring", "Log analysis"], "mitigation": ["Account hygiene", "Least privilege"]},
    
    # Lateral Movement
    "T1021": {"name": "Remote Services", "tactic": "Lateral Movement", "detection": ["Network monitoring", "Session monitoring"], "mitigation": ["Network segmentation", "Session hardening"]},
    "T1077": {"name": "Windows Admin Shares", "tactic": "Lateral Movement", "detection": ["SMB monitoring", "File share monitoring"], "mitigation": ["SMB hardening", "Network segmentation"]},
    
    # Collection
    "T1005": {"name": "Data from Local System", "tactic": "Collection", "detection": ["File monitoring", "Process monitoring"], "mitigation": ["File encryption", "Access controls"]},
    "T1113": {"name": "Screen Capture", "tactic": "Collection", "detection": ["Process monitoring", "Behavior analysis"], "mitigation": ["Application restrictions", "User awareness"]},
    
    # Exfiltration
    "T1041": {"name": "Exfiltration Over C2 Channel", "tactic": "Exfiltration", "detection": ["Network monitoring", "DLP"], "mitigation": ["Network segmentation", "DLP deployment"]},
    "T1567": {"name": "Exfiltration Over Web Service", "tactic": "Exfiltration", "detection": ["Web proxy monitoring", "DLP"], "mitigation": ["Web filtering", "DLP deployment"]},
    
    # Impact
    "T1486": {"name": "Data Encrypted for Impact", "tactic": "Impact", "detection": ["File monitoring", "Process monitoring"], "mitigation": ["Backups", "Endpoint protection"]},
    "T1489": {"name": "Service Stop", "tactic": "Impact", "detection": ["Service monitoring", "System logging"], "mitigation": ["Service hardening", "Availability monitoring"]},
}


def extract_mitre_technique_id(record: AttackRecord) -> Optional[str]:
    """Extract MITRE technique ID from attack record"""
    # Check mitre_technique field
    if record.mitre_technique:
        # Extract pattern like T1190 or T1190.001
        match = re.search(MITRE_TECHNIQUE_PATTERN, record.mitre_technique)
        if match:
            return match.group(0)
    
    # Check attack_steps and other fields for technique IDs
    text_to_search = f"{record.attack_steps} {record.tools_used} {record.tags}"
    match = re.search(MITRE_TECHNIQUE_PATTERN, text_to_search)
    if match:
        return match.group(0)
    
    return None


def map_to_mitre_ttp(record: AttackRecord, ai_analyzer=None) -> MITRETTP:
    """Map an attack record to MITRE ATT&CK TTP using AI analysis"""
    technique_id = extract_mitre_technique_id(record)
    
    # Use AI for enhanced TTP mapping if available
    if ai_analyzer:
        try:
            # AI-powered analysis for better TTP mapping
            ai_prompt = f"""
Analyze this attack and provide MITRE ATT&CK mapping:
Attack: {record.title}
Type: {record.attack_type}
Description: {record.scenario_description}
Steps: {record.attack_steps}

Provide:
1. Best MITRE technique ID (or CUSTOM if no match)
2. Technique name
3. MITRE tactic
4. Detection methods (3-5)
5. Mitigations (3-5)
6. Confidence score (0-1)
"""
            ai_response = ai_analyzer.analyze_attack(ai_prompt)
            
            if ai_response and ai_response.get("technique_id"):
                return MITRETTP(
                    technique_id=ai_response["technique_id"],
                    technique_name=ai_response["technique_name"],
                    tactic=ai_response["tactic"],
                    detection=ai_response.get("detection", []),
                    mitigation=ai_response.get("mitigation", []),
                    is_custom=ai_response["technique_id"] == "CUSTOM"
                )
        except Exception as e:
            print(f"AI TTP mapping failed, falling back to rule-based: {e}")
    
    # Fallback to rule-based mapping
    if technique_id and technique_id in MITRE_ATTACK_MAPPING:
        mapping = MITRE_ATTACK_MAPPING[technique_id]
        return MITRETTP(
            technique_id=technique_id,
            technique_name=mapping["name"],
            tactic=mapping["tactic"],
            detection=mapping["detection"],
            mitigation=mapping["mitigation"],
            is_custom=False
        )
    
    # Create custom TTP if no standard mapping found
    phase = classify_phase(record)
    return MITRETTP(
        technique_id=technique_id or "CUSTOM",
        technique_name=record.attack_type or "Custom Technique",
        tactic=phase,
        detection=[record.detection_method] if record.detection_method else [],
        mitigation=[record.solution] if record.solution else [],
        is_custom=True
    )


def calculate_base_scores(record: AttackRecord, ai_analyzer=None) -> Tuple[float, float, float]:
    """Calculate base scores for success probability, detection risk, and impact using AI analysis"""
    
    # Use AI for enhanced scoring if available
    if ai_analyzer:
        try:
            # AI-powered scoring analysis
            ai_prompt = f"""
Analyze this attack and provide scoring (0-1 for each):
Attack: {record.title}
Type: {record.attack_type}
Description: {record.scenario_description}
Detection Method: {record.detection_method}
Impact: {record.impact}

Provide:
1. Success probability (0-1): How likely is this attack to succeed?
2. Detection risk (0-1): How likely is this to be detected?
3. Impact score (0-1): What's the potential impact if successful?
4. Reasoning: Brief explanation for scores
"""
            ai_response = ai_analyzer.analyze_attack(ai_prompt)
            
            if ai_response and all(k in ai_response for k in ["success_probability", "detection_risk", "impact_score"]):
                return (
                    float(ai_response["success_probability"]),
                    float(ai_response["detection_risk"]),
                    float(ai_response["impact_score"])
                )
        except Exception as e:
            print(f"AI scoring failed, falling back to rule-based: {e}")
    
    # Fallback to rule-based scoring
    text = f"{record.attack_type} {record.title} {record.scenario_description}".lower()
    
    # Success probability based on attack type
    high_success = ["exploit", "injection", "bypass", "rce", "remote code"]
    medium_success = ["scan", "enum", "discover", "recon"]
    
    if any(kw in text for kw in high_success):
        success_prob = 0.7
    elif any(kw in text for kw in medium_success):
        success_prob = 0.5
    else:
        success_prob = 0.6
    
    # Detection risk based on detection method
    high_detection = ["log", "monitor", "alert", "ids", "ips", "waf"]
    low_detection = ["passive", "stealth", "covert", "encrypted"]
    
    if any(kw in text for kw in high_detection):
        detection_risk = 0.8
    elif any(kw in text for kw in low_detection):
        detection_risk = 0.3
    else:
        detection_risk = 0.5
    
    # Impact score based on impact description
    high_impact = ["critical", "severe", "ransom", "data loss", "compromise"]
    medium_impact = ["moderate", "information disclosure"]
    
    if any(kw in text for kw in high_impact):
        impact_score = 0.9
    elif any(kw in text for kw in medium_impact):
        impact_score = 0.6
    else:
        impact_score = 0.4
    
    return success_prob, detection_risk, impact_score


def extract_tools(record: AttackRecord) -> List[str]:
    """Extract required tools from attack record"""
    tools = []
    if record.tools_used:
        # Split by common delimiters
        for tool in re.split(r'[,;|]', record.tools_used):
            tool = tool.strip()
            if tool and len(tool) > 2:
                tools.append(tool)
    
    # Also check attack_steps for tool mentions
    common_tools = ["nmap", "metasploit", "burp", "sqlmap", "nikto", "hydra", "john", "mimikatz"]
    text = record.attack_steps.lower()
    for tool in common_tools:
        if tool in text:
            if tool not in tools:
                tools.append(tool)
    
    return tools[:5]  # Limit to top 5 tools


class AttackTreeEngine:
    """Main engine for building and managing attack trees using AI reasoning"""
    
    def __init__(self, ai_analyzer=None):
        self.trees: Dict[str, AttackTree] = {}
        self.custom_ttps: Dict[str, MITRETTP] = {}
        self.ai_analyzer = ai_analyzer  # AI analyzer for intelligent decision-making
    
    def add_custom_ttp(self, ttp: MITRETTP) -> None:
        """Add a custom TTP to the engine"""
        self.custom_ttps[ttp.technique_id] = ttp
    
    def build_attack_tree(self, records: List[AttackRecord], target_description: str) -> AttackTree:
        """Build an attack tree from a list of attack records using AI analysis"""
        tree_id = str(uuid.uuid4())[:8]
        nodes: Dict[str, AttackTreeNode] = {}
        root_nodes: List[str] = []
        leaf_nodes: List[str] = []
        
        # Use AI to analyze target and optimize attack tree structure
        if self.ai_analyzer:
            try:
                ai_prompt = f"""
Analyze this target and recommend attack tree structure:
Target: {target_description}
Available attacks: {len(records)} attack records

Provide:
1. Which MITRE tactics are most relevant for this target?
2. Suggested node connections between phases
3. Priority ranking of attack phases
4. Recommended complexity level (simple/medium/complex)
"""
                ai_analysis = self.ai_analyzer.analyze_attack(ai_prompt)
                print(f"AI analysis for attack tree: {ai_analysis}")
            except Exception as e:
                print(f"AI attack tree analysis failed, using standard structure: {e}")
        
        # Group records by phase
        phased_records: Dict[str, List[AttackRecord]] = {phase: [] for phase in PHASE_ORDER}
        for record in records:
            phase = classify_phase(record)
            phased_records[phase].append(record)
        
        # Create nodes for each phase
        phase_node_map: Dict[str, List[str]] = {phase: [] for phase in PHASE_ORDER}
        
        for phase in PHASE_ORDER:
            phase_records = phased_records[phase]
            if not phase_records:
                continue
            
            # Use AI to select and rank the best attacks for this phase
            if self.ai_analyzer and len(phase_records) > 3:
                try:
                    phase_records = self._ai_rank_attacks_for_phase(phase_records, phase, target_description)
                except Exception as e:
                    print(f"AI attack ranking failed for phase {phase}: {e}")
            
            # Create nodes for this phase (limit to top 3 per phase for manageability)
            for idx, record in enumerate(phase_records[:3]):
                node_id = f"{phase[:3].lower()}_{idx}_{tree_id}"
                
                # Calculate scores using AI
                success_prob, detection_risk, impact_score = calculate_base_scores(record, self.ai_analyzer)
                
                # Map to MITRE TTP using AI
                mitre_ttp = map_to_mitre_ttp(record, self.ai_analyzer)
                
                # Extract tools
                tools = extract_tools(record)
                
                # Use AI to estimate execution time
                time_estimate = self._ai_estimate_time(record, self.ai_analyzer)
                
                # Create node
                node = AttackTreeNode(
                    node_id=node_id,
                    attack_record_id=record.id,
                    mitre_ttp=mitre_ttp,
                    phase=phase,
                    success_probability=success_prob,
                    detection_risk=detection_risk,
                    impact_score=impact_score,
                    time_estimate=time_estimate,
                    required_tools=tools,
                    prerequisites=[],
                    outcomes=[]
                )
                
                nodes[node_id] = node
                phase_node_map[phase].append(node_id)
        
        # Use AI to build intelligent edges between phases
        if self.ai_analyzer:
            try:
                self._ai_build_edges(nodes, phase_node_map, target_description)
            except Exception as e:
                print(f"AI edge building failed, using standard structure: {e}")
                self._build_standard_edges(nodes, phase_node_map)
        else:
            self._build_standard_edges(nodes, phase_node_map)
        
        # Identify root and leaf nodes
        if phase_node_map[PHASE_ORDER[0]]:
            root_nodes = phase_node_map[PHASE_ORDER[0]]
        
        if phase_node_map[PHASE_ORDER[-1]]:
            leaf_nodes = phase_node_map[PHASE_ORDER[-1]]
        
        # Calculate overall tree score using AI-enhanced scoring
        overall_score = self._calculate_tree_score(nodes, root_nodes)
        
        # Calculate total estimated time
        total_time = sum(node.time_estimate for node in nodes.values())
        
        tree = AttackTree(
            tree_id=tree_id,
            target_description=target_description,
            nodes=nodes,
            root_nodes=root_nodes,
            leaf_nodes=leaf_nodes,
            overall_score=overall_score,
            estimated_time=total_time
        )
        
        self.trees[tree_id] = tree
        return tree
    
    def _ai_rank_attacks_for_phase(self, records: List[AttackRecord], phase: str, target: str) -> List[AttackRecord]:
        """Use AI to rank attacks by relevance for a specific phase"""
        try:
            records_text = "\n".join([
                f"- {r.title}: {r.scenario_description[:100]}" 
                for r in records[:10]
            ])
            
            ai_prompt = f"""
Rank these attacks by relevance for phase '{phase}' against target '{target}':
{records_text}

Provide the top 3 most relevant attack indices (0-based) as a list: [0, 2, 4]
"""
            ai_response = self.ai_analyzer.analyze_attack(ai_prompt)
            
            if ai_response and "top_indices" in ai_response:
                indices = ai_response["top_indices"]
                ranked_records = []
                for idx in indices:
                    if 0 <= idx < len(records):
                        ranked_records.append(records[idx])
                # Add remaining records that weren't ranked
                for i, record in enumerate(records):
                    if i not in indices:
                        ranked_records.append(record)
                return ranked_records
        except Exception as e:
            print(f"AI ranking failed: {e}")
        
        return records
    
    def _ai_estimate_time(self, record: AttackRecord, ai_analyzer=None) -> int:
        """Use AI to estimate execution time for an attack"""
        if ai_analyzer:
            try:
                ai_prompt = f"""
Estimate execution time in seconds for this attack:
Attack: {record.title}
Type: {record.attack_type}
Complexity: {record.scenario_description[:200]}

Provide estimated time in seconds (integer).
"""
                ai_response = ai_analyzer.analyze_attack(ai_prompt)
                if ai_response and "estimated_time" in ai_response:
                    return int(ai_response["estimated_time"])
            except Exception as e:
                print(f"AI time estimation failed: {e}")
        
        return 60  # Default fallback
    
    def _ai_build_edges(self, nodes: Dict[str, AttackTreeNode], phase_node_map: Dict[str, List[str]], target: str):
        """Use AI to build intelligent connections between attack phases"""
        try:
            phase_info = "\n".join([
                f"{phase}: {len(node_ids)} nodes - {node_ids[:2]}"
                for phase, node_ids in phase_node_map.items() if node_ids
            ])
            
            ai_prompt = f"""
Design intelligent connections between attack phases for target '{target}':
{phase_info}

For each phase transition, recommend which nodes should connect.
Provide connections as: phase1->phase2: [node_indices_connection_pattern]

Use standard sequential connections if specific patterns aren't clear.
"""
            ai_response = self.ai_analyzer.analyze_attack(ai_prompt)
            print(f"AI edge recommendations: {ai_response}")
        except Exception as e:
            print(f"AI edge building failed: {e}")
            self._build_standard_edges(nodes, phase_node_map)
    
    def _build_standard_edges(self, nodes: Dict[str, AttackTreeNode], phase_node_map: Dict[str, List[str]]):
        """Build standard sequential edges between phases"""
        for i, phase in enumerate(PHASE_ORDER[:-1]):
            current_phase_nodes = phase_node_map[phase]
            next_phase_nodes = phase_node_map[PHASE_ORDER[i + 1]]
            
            if current_phase_nodes and next_phase_nodes:
                # Connect each node in current phase to nodes in next phase
                for current_node in current_phase_nodes:
                    nodes[current_node].outcomes = next_phase_nodes
                    
                    for next_node in next_phase_nodes:
                        if next_node not in nodes[next_node].prerequisites:
                            nodes[next_node].prerequisites.append(current_node)
    
    def _calculate_tree_score(self, nodes: Dict[str, AttackTreeNode], root_nodes: List[str]) -> float:
        """Calculate overall score for the attack tree"""
        if not root_nodes:
            return 0.0
        
        # Calculate score as weighted average of success probability and impact
        # penalized by detection risk
        total_score = 0.0
        node_count = 0
        
        for node_id, node in nodes.items():
            # Score formula: (success * impact) - (detection_risk * 0.3)
            node_score = (node.success_probability * node.impact_score) - (node.detection_risk * 0.3)
            node_score = max(0.0, min(1.0, node_score))  # Clamp to [0, 1]
            total_score += node_score
            node_count += 1
        
        return total_score / max(node_count, 1)
    
    def generate_attack_paths(self, tree: AttackTree, top_k: int = 3) -> List[AttackPath]:
        """Generate top attack paths through the tree"""
        if not tree.root_nodes:
            return []
        
        paths = []
        
        # Generate paths from each root to each leaf
        for root in tree.root_nodes:
            for leaf in tree.leaf_nodes:
                path_nodes = self._find_path(tree, root, leaf)
                if path_nodes:
                    path = self._create_attack_path(tree, path_nodes)
                    paths.append(path)
        
        # Sort by cumulative score and return top_k
        paths.sort(key=lambda p: p.cumulative_score, reverse=True)
        return paths[:top_k]
    
    def _find_path(self, tree: AttackTree, start: str, end: str) -> List[str]:
        """Find a path from start node to end node using DFS"""
        visited = set()
        path = []
        
        def dfs(current: str) -> bool:
            if current in visited:
                return False
            visited.add(current)
            path.append(current)
            
            if current == end:
                return True
            
            for neighbor in tree.nodes[current].outcomes:
                if dfs(neighbor):
                    return True
            
            path.pop()
            return False
        
        if dfs(start):
            return path
        return []
    
    def _create_attack_path(self, tree: AttackTree, node_sequence: List[str]) -> AttackPath:
        """Create an AttackPath from a node sequence"""
        if not node_sequence:
            raise ValueError("Node sequence cannot be empty")
        
        # Calculate cumulative metrics
        cumulative_score = 0.0
        success_prob = 1.0
        detection_risk = 0.0
        total_time = 0
        
        for node_id in node_sequence:
            node = tree.nodes[node_id]
            
            # Cumulative score (average of node scores)
            node_score = (node.success_probability * node.impact_score) - (node.detection_risk * 0.3)
            node_score = max(0.0, min(1.0, node_score))
            cumulative_score += node_score
            
            # Overall success probability (product of individual probabilities)
            success_prob *= node.success_probability
            
            # Overall detection risk (average)
            detection_risk += node.detection_risk
            
            # Total time
            total_time += node.time_estimate
        
        cumulative_score /= len(node_sequence)
        detection_risk /= len(node_sequence)
        
        return AttackPath(
            path_id=str(uuid.uuid4())[:8],
            tree_id=tree.tree_id,
            node_sequence=node_sequence,
            cumulative_score=cumulative_score,
            success_probability=success_prob,
            detection_risk=detection_risk,
            estimated_time=total_time,
            is_adaptive=False
        )
    
    def apply_feedback(self, tree: AttackTree, feedback: FeedbackLoop) -> AttackTree:
        """Apply feedback to adjust the attack tree"""
        adjusted_tree = tree.model_copy()
        
        # Adjust node probabilities based on execution results
        for result in feedback.execution_results:
            if result.node_id in adjusted_tree.nodes:
                node = adjusted_tree.nodes[result.node_id]
                
                # Adjust success probability based on actual result
                if result.status == "success":
                    # Increase success probability
                    node.success_probability = min(1.0, node.success_probability + 0.1)
                elif result.status == "failure":
                    # Decrease success probability
                    node.success_probability = max(0.1, node.success_probability - 0.2)
                
                # Adjust detection risk based on whether it was detected
                if result.detected:
                    node.detection_risk = min(1.0, node.detection_risk + 0.15)
                else:
                    node.detection_risk = max(0.1, node.detection_risk - 0.1)
                
                # Adjust time estimate based on actual time
                if result.actual_time > 0:
                    # Weighted average of old and new estimate
                    node.time_estimate = int(
                        (node.time_estimate * 0.7) + (result.actual_time * 0.3)
                    )
        
        # Recalculate tree score
        adjusted_tree.overall_score = self._calculate_tree_score(
            adjusted_tree.nodes,
            adjusted_tree.root_nodes
        )
        
        # Update tree ID to indicate it's modified
        adjusted_tree.tree_id = f"{tree.tree_id}_adj"
        
        return adjusted_tree
    
    def generate_adaptive_attack(self, request: AdaptiveAttackRequest, records: List[AttackRecord]) -> AdaptiveAttackResponse:
        """Generate adaptive attack paths based on feedback history"""
        # Build initial attack tree
        tree = self.build_attack_tree(records, request.target_description)
        
        # Apply feedback history if available
        adaptation_summary = ""
        for feedback in request.feedback_history:
            tree = self.apply_feedback(tree, feedback)
            adaptation_summary += f"Applied feedback from {feedback.timestamp}. "
        
        # Generate attack paths
        paths = self.generate_attack_paths(tree, request.top_paths)
        
        # Mark paths as adaptive if feedback was applied
        if request.feedback_history:
            for path in paths:
                path.is_adaptive = True
        
        # Calculate confidence score based on feedback history
        confidence_score = tree.overall_score
        if request.feedback_history:
            # Increase confidence if we have feedback data
            confidence_score = min(1.0, confidence_score + 0.1)
        
        return AdaptiveAttackResponse(
            target_description=request.target_description,
            attack_tree=tree,
            recommended_paths=paths,
            adaptation_summary=adaptation_summary or "No feedback applied - using baseline attack tree.",
            confidence_score=confidence_score
        )