"""
Multi-Agent Orchestration System for OpsecAI - AI-Powered Decision Making

This system provides specialized agents for different phases of penetration testing:
- Recon Agent: Information gathering and target reconnaissance
- Exploit Agent: Vulnerability exploitation and initial access
- Post-Exploitation Agent: Privilege escalation, persistence, and lateral movement
- Cleanup Agent: Evidence removal and system restoration

The orchestrator uses AI to coordinate agents and make intelligent decisions about
task assignment, agent selection, and execution strategy.
"""
from __future__ import annotations
import uuid
import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import json
from pydantic import BaseModel, Field

from .core.models import (
    AttackRecord,
    AttackPath,
    AttackTree,
    ExecutionResult,
    FeedbackLoop,
)
from .attack_tree_engine import AttackTreeEngine


class AgentStatus(Enum):
    """Agent execution status"""
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentType(Enum):
    """Types of specialized agents"""
    RECON = "recon"
    EXPLOIT = "exploit"
    POST_EXPLOITATION = "post_exploitation"
    CLEANUP = "cleanup"


class AgentTask(BaseModel):
    """Task to be executed by an agent"""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_type: AgentType
    target: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=5, ge=1, le=10)
    dependencies: List[str] = Field(default_factory=list)
    status: AgentStatus = Field(default=AgentStatus.IDLE)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: str(datetime.now()))
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class AgentCapability(BaseModel):
    """Describes an agent's capabilities"""
    capability_id: str
    name: str
    description: str
    required_tools: List[str]
    estimated_time_range: tuple[int, int]  # (min_seconds, max_seconds)
    success_probability: float
    detection_risk: float


class BaseAgent:
    """Base class for all specialized agents"""
    
    def __init__(self, agent_type: AgentType, agent_id: str):
        self.agent_type = agent_type
        self.agent_id = agent_id
        self.status = AgentStatus.IDLE
        self.capabilities: List[AgentCapability] = []
        self.current_task: Optional[AgentTask] = None
        self.execution_history: List[ExecutionResult] = []
    
    def get_capabilities(self) -> List[AgentCapability]:
        """Return the agent's capabilities"""
        return self.capabilities
    
    def can_execute(self, task: AgentTask) -> bool:
        """Check if the agent can execute the given task"""
        return task.agent_type == self.agent_type and self.status == AgentStatus.IDLE
    
    async def execute(self, task: AgentTask, context: Dict[str, Any]) -> ExecutionResult:
        """Execute a task (to be implemented by subclasses)"""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def update_status(self, status: AgentStatus):
        """Update the agent's status"""
        self.status = status


class ReconAgent(BaseAgent):
    """Specialized agent for reconnaissance and information gathering"""
    
    def __init__(self, agent_id: str = "recon_agent_1"):
        super().__init__(AgentType.RECON, agent_id)
        self.capabilities = [
            AgentCapability(
                capability_id="port_scan",
                name="Port Scanning",
                description="Comprehensive port scanning using Nmap",
                required_tools=["nmap"],
                estimated_time_range=(30, 300),
                success_probability=0.95,
                detection_risk=0.4
            ),
            AgentCapability(
                capability_id="service_enum",
                name="Service Enumeration",
                description="Detailed service enumeration and version detection",
                required_tools=["nmap", "netcat"],
                estimated_time_range=(60, 600),
                success_probability=0.85,
                detection_risk=0.5
            ),
            AgentCapability(
                capability_id="os_fingerprint",
                name="OS Fingerprinting",
                description="Operating system detection and fingerprinting",
                required_tools=["nmap", "xprobe2"],
                estimated_time_range=(30, 180),
                success_probability=0.75,
                detection_risk=0.3
            ),
            AgentCapability(
                capability_id="vuln_scan",
                name="Vulnerability Scanning",
                description="Automated vulnerability scanning",
                required_tools=["nmap", "nessus", "openvas"],
                estimated_time_range=(300, 1800),
                success_probability=0.80,
                detection_risk=0.6
            ),
        ]
    
    async def execute(self, task: AgentTask, context: Dict[str, Any]) -> ExecutionResult:
        """Execute reconnaissance task"""
        self.update_status(AgentStatus.RUNNING)
        self.current_task = task
        task.started_at = str(datetime.now())
        
        try:
            # Simulate reconnaissance execution
            # In production, this would interface with real tools
            
            capability = task.parameters.get("capability", "port_scan")
            
            # Simulate execution based on capability
            if capability == "port_scan":
                result_data = await self._execute_port_scan(task.target, context)
            elif capability == "service_enum":
                result_data = await self._execute_service_enum(task.target, context)
            elif capability == "os_fingerprint":
                result_data = await self._execute_os_fingerprint(task.target, context)
            elif capability == "vuln_scan":
                result_data = await self._execute_vuln_scan(task.target, context)
            else:
                raise ValueError(f"Unknown capability: {capability}")
            
            task.result = result_data
            task.status = AgentStatus.COMPLETED
            task.completed_at = str(datetime.now())
            
            # Create execution result
            execution_result = ExecutionResult(
                result_id=str(uuid.uuid4())[:8],
                path_id=task.task_id,
                node_id=self.agent_id,
                status="success",
                actual_time=result_data.get("execution_time", 60),
                detected=result_data.get("detected", False),
                artifacts=result_data.get("artifacts", []),
                lessons_learned=result_data.get("lessons_learned", "")
            )
            
            self.execution_history.append(execution_result)
            self.update_status(AgentStatus.IDLE)
            self.current_task = None
            
            return execution_result
            
        except Exception as e:
            task.status = AgentStatus.FAILED
            task.error = str(e)
            task.completed_at = str(datetime.now())
            
            execution_result = ExecutionResult(
                result_id=str(uuid.uuid4())[:8],
                path_id=task.task_id,
                node_id=self.agent_id,
                status="failure",
                actual_time=0,
                detected=False,
                artifacts=[],
                lessons_learned=f"Execution failed: {str(e)}"
            )
            
            self.execution_history.append(execution_result)
            self.update_status(AgentStatus.IDLE)
            self.current_task = None
            
            return execution_result
    
    async def _execute_port_scan(self, target: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate port scanning"""
        # In production, this would call nmap or similar tools
        await asyncio.sleep(2)  # Simulate execution time
        
        return {
            "execution_time": 120,
            "detected": False,
            "artifacts": ["network_traffic_logs"],
            "lessons_learned": "Port scan completed successfully, 22 open ports found",
            "open_ports": [22, 80, 443, 3306, 8080],
            "scan_results": {"target": target, "ports_scanned": 1000, "open_ports": 5}
        }
    
    async def _execute_service_enum(self, target: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate service enumeration"""
        await asyncio.sleep(3)
        
        return {
            "execution_time": 180,
            "detected": True,
            "artifacts": ["connection_logs", "banner_grabs"],
            "lessons_learned": "Service enumeration detected by IDS, consider stealthier approach",
            "services": [
                {"port": 22, "service": "ssh", "version": "OpenSSH 8.2"},
                {"port": 80, "service": "http", "version": "nginx 1.18"},
                {"port": 443, "service": "https", "version": "nginx 1.18"},
            ]
        }
    
    async def _execute_os_fingerprint(self, target: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate OS fingerprinting"""
        await asyncio.sleep(2)
        
        return {
            "execution_time": 90,
            "detected": False,
            "artifacts": ["packet_captures"],
            "lessons_learned": "OS identified as Ubuntu 20.04 LTS with 85% confidence",
            "os_guess": "Ubuntu 20.04 LTS",
            "confidence": 0.85
        }
    
    async def _execute_vuln_scan(self, target: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate vulnerability scanning"""
        await asyncio.sleep(5)
        
        return {
            "execution_time": 600,
            "detected": True,
            "artifacts": ["scan_logs", "vulnerability_reports"],
            "lessons_learned": "Vulnerability scan detected by WAF, 3 potential vulnerabilities found",
            "vulnerabilities": [
                {"cve": "CVE-2021-44228", "severity": "critical", "service": "apache"},
                {"cve": "CVE-2022-22965", "severity": "high", "service": "spring"},
                {"cve": "CVE-2021-34527", "severity": "medium", "service": "windows"},
            ]
        }


class ExploitAgent(BaseAgent):
    """Specialized agent for exploitation and initial access"""
    
    def __init__(self, agent_id: str = "exploit_agent_1"):
        super().__init__(AgentType.EXPLOIT, agent_id)
        self.capabilities = [
            AgentCapability(
                capability_id="remote_exploit",
                name="Remote Exploitation",
                description="Exploit remote vulnerabilities for initial access",
                required_tools=["metasploit", "exploitdb"],
                estimated_time_range=(60, 600),
                success_probability=0.60,
                detection_risk=0.8
            ),
            AgentCapability(
                capability_id="web_exploit",
                name="Web Application Exploitation",
                description="Exploit web application vulnerabilities",
                required_tools=["burpsuite", "sqlmap", "nikto"],
                estimated_time_range=(120, 1200),
                success_probability=0.55,
                detection_risk=0.7
            ),
            AgentCapability(
                capability_id="auth_bypass",
                name="Authentication Bypass",
                description="Bypass authentication mechanisms",
                required_tools=["hydra", "john", "hashcat"],
                estimated_time_range=(300, 3600),
                success_probability=0.45,
                detection_risk=0.6
            ),
            AgentCapability(
                capability_id="social_engineering",
                name="Social Engineering",
                description="Phishing and social engineering attacks",
                required_tools=["gophish", "setoolkit"],
                estimated_time_range=(600, 7200),
                success_probability=0.35,
                detection_risk=0.4
            ),
        ]
    
    async def execute(self, task: AgentTask, context: Dict[str, Any]) -> ExecutionResult:
        """Execute exploitation task"""
        self.update_status(AgentStatus.RUNNING)
        self.current_task = task
        task.started_at = str(datetime.now())
        
        try:
            capability = task.parameters.get("capability", "remote_exploit")
            
            if capability == "remote_exploit":
                result_data = await self._execute_remote_exploit(task.target, context)
            elif capability == "web_exploit":
                result_data = await self._execute_web_exploit(task.target, context)
            elif capability == "auth_bypass":
                result_data = await self._execute_auth_bypass(task.target, context)
            elif capability == "social_engineering":
                result_data = await self._execute_social_engineering(task.target, context)
            else:
                raise ValueError(f"Unknown capability: {capability}")
            
            task.result = result_data
            task.status = AgentStatus.COMPLETED
            task.completed_at = str(datetime.now())
            
            execution_result = ExecutionResult(
                result_id=str(uuid.uuid4())[:8],
                path_id=task.task_id,
                node_id=self.agent_id,
                status=result_data.get("status", "success"),
                actual_time=result_data.get("execution_time", 120),
                detected=result_data.get("detected", False),
                artifacts=result_data.get("artifacts", []),
                lessons_learned=result_data.get("lessons_learned", "")
            )
            
            self.execution_history.append(execution_result)
            self.update_status(AgentStatus.IDLE)
            self.current_task = None
            
            return execution_result
            
        except Exception as e:
            task.status = AgentStatus.FAILED
            task.error = str(e)
            task.completed_at = str(datetime.now())
            
            execution_result = ExecutionResult(
                result_id=str(uuid.uuid4())[:8],
                path_id=task.task_id,
                node_id=self.agent_id,
                status="failure",
                actual_time=0,
                detected=False,
                artifacts=[],
                lessons_learned=f"Execution failed: {str(e)}"
            )
            
            self.execution_history.append(execution_result)
            self.update_status(AgentStatus.IDLE)
            self.current_task = None
            
            return execution_result
    
    async def _execute_remote_exploit(self, target: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate remote exploitation"""
        await asyncio.sleep(4)
        
        # Simulate success/failure based on context
        success_rate = context.get("exploit_success_rate", 0.6)
        import random
        success = random.random() < success_rate
        
        return {
            "execution_time": 300,
            "detected": True,
            "artifacts": ["exploit_logs", "shell_history"],
            "lessons_learned": "Exploit successful but triggered IDS alerts" if success else "Exploit failed due to patch",
            "status": "success" if success else "failure",
            "shell_access": success,
            "privilege_level": "user" if success else None
        }
    
    async def _execute_web_exploit(self, target: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate web exploitation"""
        await asyncio.sleep(5)
        
        return {
            "execution_time": 480,
            "detected": True,
            "artifacts": ["web_logs", "payload_files"],
            "lessons_learned": "SQL injection successful, WAF bypassed using encoding",
            "status": "success",
            "vulnerability": "SQL injection",
            "data_accessed": ["user_table", "credentials"]
        }
    
    async def _execute_auth_bypass(self, target: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate authentication bypass"""
        await asyncio.sleep(6)
        
        return {
            "execution_time": 900,
            "detected": False,
            "artifacts": ["auth_logs", "password_files"],
            "lessons_learned": "Brute force successful, weak password policy detected",
            "status": "success",
            "credentials_obtained": ["admin", "password123"]
        }
    
    async def _execute_social_engineering(self, target: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate social engineering"""
        await asyncio.sleep(3)
        
        return {
            "execution_time": 1800,
            "detected": False,
            "artifacts": ["email_logs", "phishing_templates"],
            "lessons_learned": "Phishing campaign had 15% click rate, 2 credentials harvested",
            "status": "success",
            "click_rate": 0.15,
            "credentials_harvested": 2
        }


class PostExploitationAgent(BaseAgent):
    """Specialized agent for post-exploitation activities"""
    
    def __init__(self, agent_id: str = "post_exploit_agent_1"):
        super().__init__(AgentType.POST_EXPLOITATION, agent_id)
        self.capabilities = [
            AgentCapability(
                capability_id="privilege_escalation",
                name="Privilege Escalation",
                description="Escalate privileges to higher access levels",
                required_tools=["linpeas", "winpeas", "metasploit"],
                estimated_time_range=(120, 600),
                success_probability=0.50,
                detection_risk=0.7
            ),
            AgentCapability(
                capability_id="persistence",
                name="Persistence Mechanisms",
                description="Establish persistent access",
                required_tools=["metasploit", "custom_scripts"],
                estimated_time_range=(60, 300),
                success_probability=0.75,
                detection_risk=0.6
            ),
            AgentCapability(
                capability_id="lateral_movement",
                name="Lateral Movement",
                description="Move laterally through the network",
                required_tools=["psexec", "wmi", "ssh"],
                estimated_time_range=(180, 900),
                success_probability=0.55,
                detection_risk=0.8
            ),
            AgentCapability(
                capability_id="data_exfiltration",
                name="Data Exfiltration",
                description="Extract sensitive data from target",
                required_tools=["rsync", "scp", "custom_exfil"],
                estimated_time_range=(300, 1800),
                success_probability=0.70,
                detection_risk=0.9
            ),
        ]
    
    async def execute(self, task: AgentTask, context: Dict[str, Any]) -> ExecutionResult:
        """Execute post-exploitation task"""
        self.update_status(AgentStatus.RUNNING)
        self.current_task = task
        task.started_at = str(datetime.now())
        
        try:
            capability = task.parameters.get("capability", "privilege_escalation")
            
            if capability == "privilege_escalation":
                result_data = await self._execute_privilege_escalation(task.target, context)
            elif capability == "persistence":
                result_data = await self._execute_persistence(task.target, context)
            elif capability == "lateral_movement":
                result_data = await self._execute_lateral_movement(task.target, context)
            elif capability == "data_exfiltration":
                result_data = await self._execute_data_exfiltration(task.target, context)
            else:
                raise ValueError(f"Unknown capability: {capability}")
            
            task.result = result_data
            task.status = AgentStatus.COMPLETED
            task.completed_at = str(datetime.now())
            
            execution_result = ExecutionResult(
                result_id=str(uuid.uuid4())[:8],
                path_id=task.task_id,
                node_id=self.agent_id,
                status=result_data.get("status", "success"),
                actual_time=result_data.get("execution_time", 180),
                detected=result_data.get("detected", False),
                artifacts=result_data.get("artifacts", []),
                lessons_learned=result_data.get("lessons_learned", "")
            )
            
            self.execution_history.append(execution_result)
            self.update_status(AgentStatus.IDLE)
            self.current_task = None
            
            return execution_result
            
        except Exception as e:
            task.status = AgentStatus.FAILED
            task.error = str(e)
            task.completed_at = str(datetime.now())
            
            execution_result = ExecutionResult(
                result_id=str(uuid.uuid4())[:8],
                path_id=task.task_id,
                node_id=self.agent_id,
                status="failure",
                actual_time=0,
                detected=False,
                artifacts=[],
                lessons_learned=f"Execution failed: {str(e)}"
            )
            
            self.execution_history.append(execution_result)
            self.update_status(AgentStatus.IDLE)
            self.current_task = None
            
            return execution_result
    
    async def _execute_privilege_escalation(self, target: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate privilege escalation"""
        await asyncio.sleep(3)
        
        return {
            "execution_time": 240,
            "detected": True,
            "artifacts": ["system_logs", "privilege_logs"],
            "lessons_learned": "Privilege escalation successful via kernel exploit, but triggered EDR",
            "status": "success",
            "new_privilege_level": "root"
        }
    
    async def _execute_persistence(self, target: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate persistence establishment"""
        await asyncio.sleep(2)
        
        return {
            "execution_time": 120,
            "detected": False,
            "artifacts": ["cron_jobs", "startup_scripts"],
            "lessons_learned": "Backdoor installed via cron job, should remain undetected",
            "status": "success",
            "persistence_method": "cron_job",
            "callback_interval": 3600
        }
    
    async def _execute_lateral_movement(self, target: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate lateral movement"""
        await asyncio.sleep(4)
        
        return {
            "execution_time": 420,
            "detected": True,
            "artifacts": ["network_logs", "authentication_logs"],
            "lessons_learned": "Lateral movement to 3 hosts successful, but raised alerts",
            "status": "success",
            "hosts_accessed": 3,
            "method": "ssh_key_authentication"
        }
    
    async def _execute_data_exfiltration(self, target: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate data exfiltration"""
        await asyncio.sleep(5)
        
        return {
            "execution_time": 600,
            "detected": True,
            "artifacts": ["transfer_logs", "compressed_archives"],
            "lessons_learned": "Data exfiltration detected by DLP, partial data obtained",
            "status": "partial",
            "data_size_mb": 250,
            "exfil_method": "dns_tunneling"
        }


class CleanupAgent(BaseAgent):
    """Specialized agent for cleanup and evidence removal"""
    
    def __init__(self, agent_id: str = "cleanup_agent_1"):
        super().__init__(AgentType.CLEANUP, agent_id)
        self.capabilities = [
            AgentCapability(
                capability_id="log_cleanup",
                name="Log Cleanup",
                description="Remove or modify logs to hide activity",
                required_tools=["custom_scripts", "log_tools"],
                estimated_time_range=(60, 300),
                success_probability=0.80,
                detection_risk=0.5
            ),
            AgentCapability(
                capability_id="artifact_removal",
                name="Artifact Removal",
                description="Remove tools and files left behind",
                required_tools=["secure_delete", "file_shredders"],
                estimated_time_range=(30, 180),
                success_probability=0.85,
                detection_risk=0.3
            ),
            AgentCapability(
                capability_id="process_cleanup",
                name="Process Cleanup",
                description="Terminate and remove malicious processes",
                required_tools=["process_tools", "rootkits"],
                estimated_time_range=(30, 120),
                success_probability=0.75,
                detection_risk=0.4
            ),
            AgentCapability(
                capability_id="system_restoration",
                name="System Restoration",
                description="Restore system to original state",
                required_tools=["backup_tools", "config_managers"],
                estimated_time_range=(180, 600),
                success_probability=0.70,
                detection_risk=0.2
            ),
        ]
    
    async def execute(self, task: AgentTask, context: Dict[str, Any]) -> ExecutionResult:
        """Execute cleanup task"""
        self.update_status(AgentStatus.RUNNING)
        self.current_task = task
        task.started_at = str(datetime.now())
        
        try:
            capability = task.parameters.get("capability", "log_cleanup")
            
            if capability == "log_cleanup":
                result_data = await self._execute_log_cleanup(task.target, context)
            elif capability == "artifact_removal":
                result_data = await self._execute_artifact_removal(task.target, context)
            elif capability == "process_cleanup":
                result_data = await self._execute_process_cleanup(task.target, context)
            elif capability == "system_restoration":
                result_data = await self._execute_system_restoration(task.target, context)
            else:
                raise ValueError(f"Unknown capability: {capability}")
            
            task.result = result_data
            task.status = AgentStatus.COMPLETED
            task.completed_at = str(datetime.now())
            
            execution_result = ExecutionResult(
                result_id=str(uuid.uuid4())[:8],
                path_id=task.task_id,
                node_id=self.agent_id,
                status=result_data.get("status", "success"),
                actual_time=result_data.get("execution_time", 90),
                detected=result_data.get("detected", False),
                artifacts=result_data.get("artifacts", []),
                lessons_learned=result_data.get("lessons_learned", "")
            )
            
            self.execution_history.append(execution_result)
            self.update_status(AgentStatus.IDLE)
            self.current_task = None
            
            return execution_result
            
        except Exception as e:
            task.status = AgentStatus.FAILED
            task.error = str(e)
            task.completed_at = str(datetime.now())
            
            execution_result = ExecutionResult(
                result_id=str(uuid.uuid4())[:8],
                path_id=task.task_id,
                node_id=self.agent_id,
                status="failure",
                actual_time=0,
                detected=False,
                artifacts=[],
                lessons_learned=f"Execution failed: {str(e)}"
            )
            
            self.execution_history.append(execution_result)
            self.update_status(AgentStatus.IDLE)
            self.current_task = None
            
            return execution_result
    
    async def _execute_log_cleanup(self, target: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate log cleanup"""
        await asyncio.sleep(2)
        
        return {
            "execution_time": 150,
            "detected": False,
            "artifacts": ["modified_log_files"],
            "lessons_learned": "Auth logs cleared, system logs sanitized",
            "status": "success",
            "logs_cleaned": ["auth.log", "secure", "messages"]
        }
    
    async def _execute_artifact_removal(self, target: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate artifact removal"""
        await asyncio.sleep(2)
        
        return {
            "execution_time": 90,
            "detected": False,
            "artifacts": [],
            "lessons_learned": "All tools and temporary files securely deleted",
            "status": "success",
            "files_removed": 15
        }
    
    async def _execute_process_cleanup(self, target: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate process cleanup"""
        await asyncio.sleep(1)
        
        return {
            "execution_time": 60,
            "detected": False,
            "artifacts": [],
            "lessons_learned": "All malicious processes terminated",
            "status": "success",
            "processes_terminated": 3
        }
    
    async def _execute_system_restoration(self, target: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate system restoration"""
        await asyncio.sleep(3)
        
        return {
            "execution_time": 300,
            "detected": False,
            "artifacts": ["backup_logs"],
            "lessons_learned": "System configurations restored to baseline",
            "status": "success",
            "configs_restored": ["ssh_config", "nginx_config", "firewall_rules"]
        }


class MultiAgentOrchestrator:
    """Orchestrates multiple specialized agents using AI for intelligent coordination"""
    
    def __init__(self, ai_analyzer=None):
        self.agents: Dict[AgentType, BaseAgent] = {}
        self.task_queue: List[AgentTask] = []
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.attack_tree_engine = AttackTreeEngine(ai_analyzer)
        self.ai_analyzer = ai_analyzer  # AI analyzer for intelligent decision-making
        
        # Initialize default agents
        self._initialize_default_agents()
    
    def _initialize_default_agents(self):
        """Initialize the default set of agents"""
        self.agents[AgentType.RECON] = ReconAgent()
        self.agents[AgentType.EXPLOIT] = ExploitAgent()
        self.agents[AgentType.POST_EXPLOITATION] = PostExploitationAgent()
        self.agents[AgentType.CLEANUP] = CleanupAgent()
    
    def register_agent(self, agent: BaseAgent):
        """Register a new agent"""
        self.agents[agent.agent_type] = agent
    
    def get_agent(self, agent_type: AgentType) -> Optional[BaseAgent]:
        """Get an agent by type"""
        return self.agents.get(agent_type)
    
    def create_attack_plan(self, attack_tree: AttackTree) -> List[AgentTask]:
        """Create an attack plan from an attack tree using AI-powered task assignment"""
        tasks = []
        
        # Use AI to analyze the attack tree and optimize task assignment
        if self.ai_analyzer:
            try:
                ai_plan = self._ai_create_optimized_plan(attack_tree)
                if ai_plan:
                    return ai_plan
            except Exception as e:
                print(f"AI attack planning failed, using standard approach: {e}")
        
        # Fallback to standard task creation
        for node_id, node in attack_tree.nodes.items():
            agent_type = self._map_phase_to_agent_type(node.phase, attack_tree.target_description)
            if agent_type:
                task = AgentTask(
                    agent_type=agent_type,
                    target=attack_tree.target_description,
                    parameters={
                        "node_id": node_id,
                        "mitre_ttp": node.mitre_ttp.model_dump(),
                        "capability": self._select_capability(node, agent_type, attack_tree.target_description)
                    },
                    priority=self._calculate_priority(node, attack_tree.target_description)
                )
                tasks.append(task)
        
        # Set up task dependencies based on tree structure
        for task in tasks:
            node_id = task.parameters["node_id"]
            node = attack_tree.nodes[node_id]
            task.dependencies = node.prerequisites
        
        # Sort tasks by priority and dependencies
        tasks.sort(key=lambda t: (-t.priority, len(t.dependencies)))
        
        return tasks
    
    def _ai_create_optimized_plan(self, attack_tree: AttackTree) -> Optional[List[AgentTask]]:
        """Use AI to create an optimized attack plan"""
        try:
            # Prepare attack tree summary for AI
            tree_summary = self._summarize_attack_tree(attack_tree)
            
            ai_prompt = f"""
Analyze this attack tree and create an optimized execution plan:
Target: {attack_tree.target_description}
Tree Summary:
{tree_summary}

Provide:
1. Optimal task ordering considering dependencies
2. Which tasks can be executed in parallel
3. Priority levels for each task (1-10)
4. Special considerations for execution
5. Recommended parallelization strategy

Format as JSON with task assignments.
"""
            ai_response = self.ai_analyzer.analyze_attack(ai_prompt)
            
            if ai_response and "optimized_plan" in ai_response:
                return self._parse_ai_plan(ai_response["optimized_plan"], attack_tree)
        except Exception as e:
            print(f"AI plan creation failed: {e}")
        
        return None
    
    def _summarize_attack_tree(self, attack_tree: AttackTree) -> str:
        """Create a summary of the attack tree for AI analysis"""
        summary = f"Nodes: {len(attack_tree.nodes)}\n"
        summary += f"Root nodes: {attack_tree.root_nodes}\n"
        summary += f"Leaf nodes: {attack_tree.leaf_nodes}\n"
        summary += "Node details:\n"
        
        for node_id, node in attack_tree.nodes.items():
            summary += f"- {node_id}: {node.phase} (success: {node.success_probability:.2f}, detection: {node.detection_risk:.2f})\n"
        
        return summary
    
    def _parse_ai_plan(self, ai_plan: Dict, attack_tree: AttackTree) -> List[AgentTask]:
        """Parse AI-generated plan into agent tasks"""
        tasks = []
        # This would parse the AI response into actual tasks
        # For now, return None to use standard approach
        return None
    
    def _map_phase_to_agent_type(self, phase: str, target: str = "") -> Optional[AgentType]:
        """Map attack phase to agent type using AI analysis"""
        # Use AI for intelligent agent selection
        if self.ai_analyzer:
            try:
                ai_prompt = f"""
Analyze this attack phase and recommend the best agent type:
Phase: {phase}
Target: {target}

Available agent types:
- RECON: Information gathering, scanning, enumeration
- EXPLOIT: Vulnerability exploitation, initial access
- POST_EXPLOITATION: Privilege escalation, persistence, lateral movement, data exfiltration
- CLEANUP: Evidence removal, system restoration

Recommend the most appropriate agent type for this phase.
"""
                ai_response = self.ai_analyzer.analyze_attack(ai_prompt)
                
                if ai_response and "recommended_agent" in ai_response:
                    agent_type_str = ai_response["recommended_agent"].upper()
                    try:
                        return AgentType(agent_type_str)
                    except ValueError:
                        pass
            except Exception as e:
                print(f"AI agent mapping failed, using rule-based: {e}")
        
        # Fallback to rule-based mapping
        phase_lower = phase.lower()
        
        if "recon" in phase_lower or "discovery" in phase_lower:
            return AgentType.RECON
        elif "initial" in phase_lower or "execution" in phase_lower:
            return AgentType.EXPLOIT
        elif "persistence" in phase_lower or "privilege" in phase_lower or "lateral" in phase_lower or "collection" in phase_lower or "exfil" in phase_lower:
            return AgentType.POST_EXPLOITATION
        elif "impact" in phase_lower or "cleanup" in phase_lower:
            return AgentType.CLEANUP
        
        return None
    
    def _select_capability(self, node: 'AttackTreeNode', agent_type: AgentType, target: str = "") -> str:
        """Select appropriate capability for a node using AI analysis"""
        agent = self.agents.get(agent_type)
        if not agent or not agent.capabilities:
            return "default"
        
        # Use AI for intelligent capability selection
        if self.ai_analyzer:
            try:
                capabilities_list = [cap.capability_id for cap in agent.capabilities]
                capabilities_desc = "\n".join([
                    f"- {cap.capability_id}: {cap.name} - {cap.description}"
                    for cap in agent.capabilities
                ])
                
                ai_prompt = f"""
Select the best capability for this attack node:
Agent Type: {agent_type.value}
MITRE Technique: {node.mitre_ttp.technique_name} ({node.mitre_ttp.technique_id})
Phase: {node.phase}
Success Probability: {node.success_probability}
Detection Risk: {node.detection_risk}
Target: {target}

Available capabilities:
{capabilities_desc}

Recommend the most suitable capability ID.
"""
                ai_response = self.ai_analyzer.analyze_attack(ai_prompt)
                
                if ai_response and "recommended_capability" in ai_response:
                    recommended = ai_response["recommended_capability"]
                    if recommended in capabilities_list:
                        return recommended
            except Exception as e:
                print(f"AI capability selection failed, using rule-based: {e}")
        
        # Fallback to rule-based selection
        if agent_type == AgentType.RECON:
            if "vuln" in node.mitre_ttp.technique_name.lower():
                return "vuln_scan"
            elif "os" in node.mitre_ttp.technique_name.lower():
                return "os_fingerprint"
            elif "service" in node.mitre_ttp.technique_name.lower():
                return "service_enum"
            else:
                return "port_scan"
        
        elif agent_type == AgentType.EXPLOIT:
            if "web" in node.mitre_ttp.technique_name.lower():
                return "web_exploit"
            elif "auth" in node.mitre_ttp.technique_name.lower():
                return "auth_bypass"
            elif "social" in node.mitre_ttp.technique_name.lower():
                return "social_engineering"
            else:
                return "remote_exploit"
        
        elif agent_type == AgentType.POST_EXPLOITATION:
            if "privilege" in node.mitre_ttp.technique_name.lower():
                return "privilege_escalation"
            elif "persistence" in node.mitre_ttp.technique_name.lower():
                return "persistence"
            elif "lateral" in node.mitre_ttp.technique_name.lower():
                return "lateral_movement"
            elif "exfil" in node.mitre_ttp.technique_name.lower():
                return "data_exfiltration"
            else:
                return "privilege_escalation"
        
        elif agent_type == AgentType.CLEANUP:
            if "log" in node.mitre_ttp.technique_name.lower():
                return "log_cleanup"
            elif "artifact" in node.mitre_ttp.technique_name.lower():
                return "artifact_removal"
            elif "process" in node.mitre_ttp.technique_name.lower():
                return "process_cleanup"
            else:
                return "system_restoration"
        
        return "default"
    
    def _calculate_priority(self, node: 'AttackTreeNode', target: str = "") -> int:
        """Calculate task priority based on node characteristics using AI analysis"""
        # Use AI for intelligent priority calculation
        if self.ai_analyzer:
            try:
                ai_prompt = f"""
Calculate priority (1-10) for this attack task:
MITRE Technique: {node.mitre_ttp.technique_name} ({node.mitre_ttp.technique_id})
Phase: {node.phase}
Success Probability: {node.success_probability}
Detection Risk: {node.detection_risk}
Impact Score: {node.impact_score}
Target: {target}

Consider:
- Higher impact = higher priority
- Lower detection risk = higher priority
- Higher success probability = higher priority
- Critical phases (initial access, privilege escalation) = higher priority

Provide priority as integer (1-10).
"""
                ai_response = self.ai_analyzer.analyze_attack(ai_prompt)
                
                if ai_response and "priority" in ai_response:
                    priority = int(ai_response["priority"])
                    return max(1, min(10, priority))
            except Exception as e:
                print(f"AI priority calculation failed, using rule-based: {e}")
        
        # Fallback to rule-based calculation
        base_priority = 5
        impact_bonus = int(node.impact_score * 2)
        detection_penalty = int(node.detection_risk * 2)
        
        return max(1, min(10, base_priority + impact_bonus - detection_penalty))
    
    async def execute_attack_plan(self, tasks: List[AgentTask], context: Dict[str, Any]) -> List[ExecutionResult]:
        """Execute an attack plan using the agents"""
        execution_results = []
        completed_tasks = set()
        
        while len(completed_tasks) < len(tasks):
            # Find tasks that can be executed (dependencies satisfied)
            ready_tasks = [
                task for task in tasks 
                if task.status == AgentStatus.IDLE 
                and all(dep in completed_tasks for dep in task.dependencies)
            ]
            
            if not ready_tasks:
                # No ready tasks - check for circular dependencies or failed tasks
                break
            
            # Execute ready tasks (in parallel for independence)
            execution_coroutines = []
            for task in ready_tasks:
                agent = self.agents.get(task.agent_type)
                if agent and agent.can_execute(task):
                    execution_coroutines.append(agent.execute(task, context))
            
            # Execute tasks concurrently
            if execution_coroutines:
                results = await asyncio.gather(*execution_coroutines, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, ExecutionResult):
                        execution_results.append(result)
                        completed_tasks.add(result.path_id)
                    elif isinstance(result, Exception):
                        # Handle execution errors
                        print(f"Task execution failed: {result}")
            
            # Small delay between batches
            await asyncio.sleep(0.5)
        
        return execution_results
    
    def create_feedback_loop(self, session_id: str, execution_results: List[ExecutionResult]) -> FeedbackLoop:
        """Create a feedback loop from execution results"""
        # Calculate adjusted probabilities based on results
        adjusted_probabilities = {}
        
        for result in execution_results:
            if result.status == "success":
                # Increase probability for similar successful nodes
                adjusted_probabilities[result.node_id] = 0.1
            elif result.status == "failure":
                # Decrease probability for failed nodes
                adjusted_probabilities[result.node_id] = -0.2
            
            if result.detected:
                # Increase detection risk
                adjusted_probabilities[f"{result.node_id}_detection"] = 0.15
        
        # Generate new recommendations based on lessons learned
        new_recommendations = []
        for result in execution_results:
            if result.lessons_learned:
                new_recommendations.append(result.lessons_learned)
        
        feedback = FeedbackLoop(
            feedback_id=str(uuid.uuid4())[:8],
            session_id=session_id,
            execution_results=execution_results,
            adjusted_probabilities=adjusted_probabilities,
            new_recommendations=new_recommendations,
            confidence_delta=sum(adjusted_probabilities.values()) / max(len(adjusted_probabilities), 1)
        )
        
        return feedback
    
    async def execute_adaptive_attack(self, attack_tree: AttackTree, context: Dict[str, Any], max_iterations: int = 3) -> Dict[str, Any]:
        """Execute an adaptive attack with feedback loops"""
        session_id = str(uuid.uuid4())[:8]
        feedback_history = []
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Create attack plan from current tree
            tasks = self.create_attack_plan(attack_tree)
            
            # Execute the plan
            execution_results = await self.execute_attack_plan(tasks, context)
            
            # Create feedback loop
            feedback = self.create_feedback_loop(session_id, execution_results)
            feedback_history.append(feedback)
            
            # Apply feedback to attack tree
            attack_tree = self.attack_tree_engine.apply_feedback(attack_tree, feedback)
            
            # Check if we should continue (e.g., if significant improvements possible)
            if abs(feedback.confidence_delta) < 0.05:
                break
        
        return {
            "session_id": session_id,
            "iterations": iteration,
            "final_attack_tree": attack_tree,
            "feedback_history": feedback_history,
            "total_execution_results": [result for feedback in feedback_history for result in feedback.execution_results]
        }