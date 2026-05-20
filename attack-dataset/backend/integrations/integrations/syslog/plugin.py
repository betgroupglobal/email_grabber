"""
Syslog Plugin - Log Analysis Integration for OpsecAI
"""

import logging
import re
from typing import Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path

from plugin_system.base import BasePlugin, PluginConfig, ExecutionContext, ExecutionResult


logger = logging.getLogger(__name__)


class SyslogPlugin(BasePlugin):
    """Syslog log analysis integration."""
    
    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.binary_path = config.execution.get("binary_path", "/usr/bin/logger")
        self.timeout = config.execution.get("timeout", 60)
        
        # Security event patterns
        self.security_patterns = {
            "failed_login": [
                r"failed password",
                r"authentication failure",
                r"invalid user",
                r"login failed"
            ],
            "privilege_escalation": [
                r"sudo.*failed",
                r"su.*failed",
                r"permission denied"
            ],
            "network_attack": [
                r"port scan",
                r"brute force",
                r"dos attack",
                r"intrusion"
            ],
            "malware": [
                r"virus",
                r"malware",
                r"trojan",
                r"ransomware"
            ],
            "data_breach": [
                r"unauthorized access",
                r"data leak",
                r"breach attempt"
            ]
        }
    
    async def initialize(self):
        """Initialize the Syslog plugin."""
        logger.info("Initializing Syslog plugin...")
        logger.info("Syslog plugin initialized successfully")
    
    async def validate_input(self, parameters: Dict[str, Any]) -> bool:
        """Validate input parameters."""
        if "log_source" not in parameters:
            raise ValueError("Missing required parameter: log_source")
        
        log_source = parameters["log_source"]
        if not log_source or not isinstance(log_source, str):
            raise ValueError("Log source must be a non-empty string")
        
        return True
    
    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Execute syslog analysis."""
        log_source = context.parameters["log_source"]
        analysis_type = context.parameters.get("analysis_type", "security_events")
        time_range = context.parameters.get("time_range", "1h")
        custom_patterns = context.parameters.get("patterns", [])
        
        logger.info(f"Analyzing syslog source: {log_source}")
        
        try:
            # Determine if source is a file or remote server
            if log_source.startswith(("/", "./")):
                events = await self._analyze_log_file(log_source, analysis_type, time_range, custom_patterns)
            else:
                events = await self._analyze_remote_syslog(log_source, analysis_type, time_range, custom_patterns)
            
            # Generate summary
            summary = self._generate_summary(events)
            
            result = {
                "log_source": log_source,
                "analysis_type": analysis_type,
                "time_range": time_range,
                "events_found": events,
                "summary": summary,
                "analysis_time": datetime.utcnow().isoformat()
            }
            
            return ExecutionResult(
                success=True,
                output=result,
                error=None,
                artifacts=[{
                    "type": "log_analysis",
                    "source": "syslog",
                    "log_source": log_source,
                    "analysis_type": analysis_type,
                    "timestamp": datetime.utcnow().isoformat()
                }],
                opsec_context={
                    "service": "syslog",
                    "log_source": log_source,
                    "analysis_type": analysis_type,
                    "event_count": len(events),
                    "risk_assessment": self._assess_log_risk(summary)
                },
                execution_time=0.0
            )
            
        except FileNotFoundError:
            return ExecutionResult(
                success=False,
                output=None,
                error=f"Log file not found: {log_source}",
                artifacts=[],
                opsec_context={"error": "file_not_found", "service": "syslog"},
                execution_time=0.0
            )
        except Exception as e:
            logger.error(f"Syslog analysis failed: {e}")
            return ExecutionResult(
                success=False,
                output=None,
                error=str(e),
                artifacts=[],
                opsec_context={"error": str(e), "service": "syslog"},
                execution_time=0.0
            )
    
    async def _analyze_log_file(self, log_file: str, analysis_type: str, time_range: str, custom_patterns: List[str]) -> List[Dict[str, Any]]:
        """Analyze local log file."""
        events = []
        
        try:
            # Parse time range
            time_delta = self._parse_time_range(time_range)
            cutoff_time = datetime.utcnow() - time_delta
            
            # Read log file
            path = Path(log_file)
            if not path.exists():
                raise FileNotFoundError(f"Log file not found: {log_file}")
            
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    event = self._parse_log_line(line, analysis_type, cutoff_time, custom_patterns)
                    if event:
                        events.append(event)
            
            logger.info(f"Found {len(events)} events in log file")
            
        except Exception as e:
            logger.error(f"Error analyzing log file: {e}")
        
        return events
    
    async def _analyze_remote_syslog(self, syslog_server: str, analysis_type: str, time_range: str, custom_patterns: List[str]) -> List[Dict[str, Any]]:
        """Analyze remote syslog server."""
        # This is a simplified implementation
        # Real implementation would use syslog protocol to connect to remote server
        logger.warning("Remote syslog analysis not fully implemented")
        
        return [{
            "timestamp": datetime.utcnow().isoformat(),
            "severity": "warning",
            "message": "Remote syslog analysis requires additional implementation",
            "source": syslog_server
        }]
    
    def _parse_log_line(self, line: str, analysis_type: str, cutoff_time: datetime, custom_patterns: List[str]) -> Dict[str, Any]:
        """Parse a single log line and check for security events."""
        line = line.strip()
        if not line:
            return None
        
        # Extract timestamp (simplified - real implementation would use proper syslog parsing)
        timestamp_match = re.search(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', line)
        if timestamp_match:
            try:
                timestamp_str = timestamp_match.group()
                # Try to parse timestamp
                if 'T' in timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str)
                else:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                
                # Skip if outside time range
                if timestamp < cutoff_time:
                    return None
            except ValueError:
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()
        
        # Determine severity
        severity = self._determine_severity(line)
        
        # Check for security patterns
        event_type = None
        if analysis_type == "security_events":
            event_type = self._check_security_patterns(line)
        elif analysis_type == "error_detection":
            event_type = self._check_error_patterns(line)
        elif custom_patterns:
            event_type = self._check_custom_patterns(line, custom_patterns)
        
        # Only include if event type found or high severity
        if event_type or severity in ["critical", "error"]:
            return {
                "timestamp": timestamp.isoformat(),
                "severity": severity,
                "message": line,
                "source": "syslog",
                "event_type": event_type
            }
        
        return None
    
    def _determine_severity(self, line: str) -> str:
        """Determine log severity based on content."""
        line_lower = line.lower()
        
        if any(word in line_lower for word in ["critical", "emergency", "alert"]):
            return "critical"
        elif any(word in line_lower for word in ["error", "fail", "denied"]):
            return "error"
        elif any(word in line_lower for word in ["warning", "warn"]):
            return "warning"
        else:
            return "info"
    
    def _check_security_patterns(self, line: str) -> str:
        """Check if line matches any security patterns."""
        line_lower = line.lower()
        
        for event_type, patterns in self.security_patterns.items():
            for pattern in patterns:
                if re.search(pattern, line_lower, re.IGNORECASE):
                    return event_type
        
        return None
    
    def _check_error_patterns(self, line: str) -> str:
        """Check if line matches error patterns."""
        error_patterns = [
            r"error",
            r"exception",
            r"failed",
            r"timeout",
            r"connection refused"
        ]
        
        line_lower = line.lower()
        for pattern in error_patterns:
            if re.search(pattern, line_lower):
                return "error"
        
        return None
    
    def _check_custom_patterns(self, line: str, patterns: List[str]) -> str:
        """Check if line matches custom patterns."""
        line_lower = line.lower()
        
        for pattern in patterns:
            if re.search(pattern.lower(), line_lower):
                return "custom_match"
        
        return None
    
    def _parse_time_range(self, time_range: str) -> timedelta:
        """Parse time range string into timedelta."""
        if time_range.endswith("h"):
            hours = int(time_range[:-1])
            return timedelta(hours=hours)
        elif time_range.endswith("d"):
            days = int(time_range[:-1])
            return timedelta(days=days)
        elif time_range.endswith("m"):
            minutes = int(time_range[:-1])
            return timedelta(minutes=minutes)
        else:
            return timedelta(hours=1)  # Default to 1 hour
    
    def _generate_summary(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary of log analysis."""
        summary = {
            "total_events": len(events),
            "critical_events": 0,
            "error_events": 0,
            "warning_events": 0,
            "info_events": 0,
            "event_types": {}
        }
        
        for event in events:
            severity = event.get("severity", "info")
            if severity == "critical":
                summary["critical_events"] += 1
            elif severity == "error":
                summary["error_events"] += 1
            elif severity == "warning":
                summary["warning_events"] += 1
            else:
                summary["info_events"] += 1
            
            event_type = event.get("event_type")
            if event_type:
                summary["event_types"][event_type] = summary["event_types"].get(event_type, 0) + 1
        
        return summary
    
    def _assess_log_risk(self, summary: Dict[str, Any]) -> str:
        """Assess overall risk based on log analysis."""
        if summary["critical_events"] > 0:
            return "high"
        elif summary["error_events"] > 5:
            return "high"
        elif summary["error_events"] > 0 or summary["warning_events"] > 10:
            return "medium"
        else:
            return "low"
    
    async def health_check(self) -> Dict[str, Any]:
        """Check plugin health."""
        try:
            # Check if common log files exist
            log_files = ["/var/log/syslog", "/var/log/auth.log", "/var/log/messages"]
            available_logs = []
            
            for log_file in log_files:
                if Path(log_file).exists():
                    available_logs.append(log_file)
            
            return {
                "healthy": True,
                "status": "operational",
                "available_log_files": available_logs,
                "message": f"Found {len(available_logs)} accessible log files"
            }
        except Exception as e:
            return {
                "healthy": False,
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def cleanup(self):
        """Cleanup plugin resources."""
        logger.info("Syslog plugin cleaned up")