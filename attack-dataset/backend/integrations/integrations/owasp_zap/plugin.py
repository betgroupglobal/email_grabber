"""
OWASP ZAP Plugin - Web Application Security Scanner Integration for OpsecAI
"""

import logging
import requests
from typing import Dict, Any, List
from datetime import datetime
from urllib.parse import urlparse

from plugin_system.base import BasePlugin, PluginConfig, ExecutionContext, ExecutionResult


logger = logging.getLogger(__name__)


class OWASPZAPPlugin(BasePlugin):
    """OWASP ZAP web application security scanner integration."""
    
    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.base_url = config.execution.get("base_url", "http://localhost:8080")
        self.api_key = config.execution.get("api_key", "")
        self.timeout = config.execution.get("timeout", 600)
        
    async def initialize(self):
        """Initialize the OWASP ZAP plugin."""
        logger.info("Initializing OWASP ZAP plugin...")
        
        # Test ZAP connection
        try:
            response = requests.get(
                f"{self.base_url}/JSON/core/view/version/",
                timeout=5
            )
            if response.status_code == 200:
                logger.info("OWASP ZAP connection successful")
                version_info = response.json()
                logger.info(f"ZAP version: {version_info.get('version', 'Unknown')}")
            else:
                logger.warning(f"OWASP ZAP connection failed: {response.status_code}")
        except Exception as e:
            logger.warning(f"OWASP ZAP connection test failed: {e}")
        
        logger.info("OWASP ZAP plugin initialized successfully")
    
    async def validate_input(self, parameters: Dict[str, Any]) -> bool:
        """Validate input parameters."""
        if "target_url" not in parameters:
            raise ValueError("Missing required parameter: target_url")
        
        target_url = parameters["target_url"]
        if not target_url or not isinstance(target_url, str):
            raise ValueError("Target URL must be a non-empty string")
        
        # Validate URL format
        try:
            parsed = urlparse(target_url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
        except Exception:
            raise ValueError("Invalid URL format")
        
        return True
    
    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Execute OWASP ZAP security scan."""
        target_url = context.parameters["target_url"]
        scan_type = context.parameters.get("scan_type", "passive_scan")
        max_depth = context.parameters.get("max_depth", 5)
        context_name = context.parameters.get("context_name", "Default Context")
        
        logger.info(f"Starting OWASP ZAP scan for: {target_url}")
        
        try:
            # Create ZAP context
            context_result = await self._create_context(context_name, target_url)
            
            # Add target to context
            await self._add_target_to_context(context_name, target_url)
            
            # Perform spider scan if requested
            scan_id = None
            if scan_type in ["spider", "active_scan"]:
                spider_result = await self._start_spider(target_url, max_depth, context_name)
                if spider_result["success"]:
                    scan_id = spider_result["scan_id"]
                    await self._wait_for_scan_completion("spider", scan_id)
            
            # Perform requested scan type
            if scan_type == "active_scan":
                active_result = await self._start_active_scan(target_url, context_name)
                if active_result["success"]:
                    scan_id = active_result["scan_id"]
                    await self._wait_for_scan_completion("ascan", scan_id)
            elif scan_type == "passive_scan":
                # Access the target to trigger passive scan
                await self._access_target(target_url)
            
            # Get results
            alerts = await self._get_alerts(target_url)
            
            result = {
                "scan_id": scan_id or f"manual-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "scan_status": "completed",
                "scan_type": scan_type,
                "target_url": target_url,
                "alerts": alerts,
                "scan_progress": 100,
                "start_time": datetime.utcnow().isoformat(),
                "end_time": datetime.utcnow().isoformat()
            }
            
            return ExecutionResult(
                success=True,
                output=result,
                error=None,
                artifacts=[{
                    "type": "web_security_scan",
                    "source": "owasp_zap",
                    "target_url": target_url,
                    "scan_type": scan_type,
                    "timestamp": datetime.utcnow().isoformat()
                }],
                opsec_context={
                    "service": "owasp_zap",
                    "target_url": target_url,
                    "scan_type": scan_type,
                    "alert_count": len(alerts),
                    "risk_assessment": self._assess_overall_risk(alerts)
                },
                execution_time=0.0
            )
            
        except requests.exceptions.Timeout:
            return ExecutionResult(
                success=False,
                output=None,
                error="Scan timed out",
                artifacts=[],
                opsec_context={"error": "timeout", "service": "owasp_zap"},
                execution_time=0.0
            )
        except Exception as e:
            logger.error(f"OWASP ZAP scan failed: {e}")
            return ExecutionResult(
                success=False,
                output=None,
                error=str(e),
                artifacts=[],
                opsec_context={"error": str(e), "service": "owasp_zap"},
                execution_time=0.0
            )
    
    async def _create_context(self, context_name: str, target_url: str) -> Dict[str, Any]:
        """Create a ZAP context."""
        try:
            params = {
                "contextName": context_name,
                "apiKey": self.api_key
            }
            response = requests.get(
                f"{self.base_url}/JSON/context/action/newContext/",
                params=params,
                timeout=10
            )
            return {"success": response.status_code == 200}
        except Exception as e:
            logger.warning(f"Failed to create context: {e}")
            return {"success": False, "error": str(e)}
    
    async def _add_target_to_context(self, context_name: str, target_url: str) -> Dict[str, Any]:
        """Add target to ZAP context."""
        try:
            params = {
                "contextName": context_name,
                "regex": target_url,
                "apiKey": self.api_key
            }
            response = requests.get(
                f"{self.base_url}/JSON/context/action/includeInContext/",
                params=params,
                timeout=10
            )
            return {"success": response.status_code == 200}
        except Exception as e:
            logger.warning(f"Failed to add target to context: {e}")
            return {"success": False, "error": str(e)}
    
    async def _start_spider(self, target_url: str, max_depth: int, context_name: str) -> Dict[str, Any]:
        """Start ZAP spider scan."""
        try:
            params = {
                "url": target_url,
                "maxDepth": max_depth,
                "contextName": context_name,
                "apiKey": self.api_key
            }
            response = requests.get(
                f"{self.base_url}/JSON/spider/action/scan/",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return {"success": True, "scan_id": result.get("scan", "")}
            else:
                return {"success": False, "error": f"Spider start failed: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _start_active_scan(self, target_url: str, context_name: str) -> Dict[str, Any]:
        """Start ZAP active scan."""
        try:
            params = {
                "url": target_url,
                "contextName": context_name,
                "apiKey": self.api_key
            }
            response = requests.get(
                f"{self.base_url}/JSON/ascan/action/scan/",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return {"success": True, "scan_id": result.get("scan", "")}
            else:
                return {"success": False, "error": f"Active scan start failed: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _access_target(self, target_url: str) -> Dict[str, Any]:
        """Access target to trigger passive scan."""
        try:
            response = requests.get(target_url, timeout=30)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _wait_for_scan_completion(self, scan_type: str, scan_id: str) -> None:
        """Wait for scan to complete."""
        import asyncio
        
        max_attempts = 600  # 10 minutes max
        for attempt in range(max_attempts):
            try:
                if scan_type == "spider":
                    endpoint = f"{self.base_url}/JSON/spider/view/status/"
                    params = {"scanId": scan_id, "apiKey": self.api_key}
                else:  # active scan
                    endpoint = f"{self.base_url}/JSON/ascan/view/status/"
                    params = {"scanId": scan_id, "apiKey": self.api_key}
                
                response = requests.get(endpoint, params=params, timeout=10)
                if response.status_code == 200:
                    status = response.json().get("status", "0")
                    if status == "100":
                        return
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"Error checking scan status: {e}")
                await asyncio.sleep(1)
    
    async def _get_alerts(self, target_url: str) -> List[Dict[str, Any]]:
        """Get security alerts from ZAP."""
        try:
            params = {
                "baseurl": target_url,
                "apiKey": self.api_key
            }
            response = requests.get(
                f"{self.base_url}/JSON/alert/view/alerts/",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                alerts_data = response.json()
                alerts = alerts_data.get("alerts", [])
                
                # Format alerts
                formatted_alerts = []
                for alert in alerts:
                    formatted_alerts.append({
                        "risk": alert.get("risk", "Unknown"),
                        "name": alert.get("name", "Unknown"),
                        "description": alert.get("description", ""),
                        "url": alert.get("url", ""),
                        "param": alert.get("param", ""),
                        "attack": alert.get("attack", ""),
                        "evidence": alert.get("evidence", ""),
                        "confidence": alert.get("confidence", "Unknown")
                    })
                
                return formatted_alerts
            else:
                logger.warning(f"Failed to get alerts: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            return []
    
    def _assess_overall_risk(self, alerts: List[Dict[str, Any]]) -> str:
        """Assess overall risk based on alerts."""
        if not alerts:
            return "low"
        
        high_risk = sum(1 for alert in alerts if alert.get("risk") == "High")
        medium_risk = sum(1 for alert in alerts if alert.get("risk") == "Medium")
        
        if high_risk > 0:
            return "high"
        elif medium_risk > 2:
            return "medium"
        else:
            return "low"
    
    async def health_check(self) -> Dict[str, Any]:
        """Check plugin health."""
        try:
            response = requests.get(
                f"{self.base_url}/JSON/core/view/version/",
                timeout=5
            )
            
            if response.status_code == 200:
                version_info = response.json()
                return {
                    "healthy": True,
                    "status": "operational",
                    "version": version_info.get("version", "Unknown"),
                    "base_url": self.base_url
                }
            else:
                return {
                    "healthy": False,
                    "status": "degraded",
                    "message": f"ZAP returned status {response.status_code}"
                }
        except Exception as e:
            return {
                "healthy": False,
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def cleanup(self):
        """Cleanup plugin resources."""
        logger.info("OWASP ZAP plugin cleaned up")