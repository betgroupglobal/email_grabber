"""
VirusTotal Plugin - Threat Intelligence Integration for OpsecAI
"""

import logging
import os
import requests
from typing import Dict, Any, Optional
from datetime import datetime

from plugin_system.base import BasePlugin, PluginConfig, ExecutionContext, ExecutionResult


logger = logging.getLogger(__name__)


class VirusTotalPlugin(BasePlugin):
    """VirusTotal API integration for threat intelligence."""
    
    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.base_url = config.execution.get("base_url", "https://www.virustotal.com/api/v3")
        self.timeout = config.execution.get("timeout", 30)
        self.api_key = os.getenv("VIRUSTOTAL_API_KEY", "")
        self._rate_limit_remaining = 4
        self._rate_limit_reset = None
        
    async def initialize(self):
        """Initialize the VirusTotal plugin."""
        logger.info("Initializing VirusTotal plugin...")
        
        if not self.api_key:
            logger.warning("VIRUSTOTAL_API_KEY not set. Plugin will have limited functionality.")
        
        # Test API connection
        if self.api_key:
            try:
                response = requests.get(
                    f"{self.base_url}/api_key",
                    headers={"x-apikey": self.api_key},
                    timeout=5
                )
                if response.status_code == 200:
                    logger.info("VirusTotal API connection successful")
                else:
                    logger.warning(f"VirusTotal API key validation failed: {response.status_code}")
            except Exception as e:
                logger.warning(f"VirusTotal API connection test failed: {e}")
        
        logger.info("VirusTotal plugin initialized successfully")
    
    async def validate_input(self, parameters: Dict[str, Any]) -> bool:
        """Validate input parameters."""
        if "resource" not in parameters:
            raise ValueError("Missing required parameter: resource")
        
        resource = parameters["resource"]
        if not resource or not isinstance(resource, str):
            raise ValueError("Resource must be a non-empty string")
        
        return True
    
    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Execute VirusTotal analysis."""
        resource = context.parameters["resource"]
        scan_type = context.parameters.get("scan_type", "auto")
        
        logger.info(f"Analyzing resource with VirusTotal: {resource}")
        
        try:
            # Determine scan type if auto
            if scan_type == "auto":
                scan_type = self._detect_resource_type(resource)
            
            # Get appropriate endpoint
            endpoint = self._get_endpoint(scan_type, resource)
            
            # Make API request
            headers = {"x-apikey": self.api_key} if self.api_key else {}
            response = requests.get(
                endpoint,
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code == 401:
                return ExecutionResult(
                    success=False,
                    output=None,
                    error="Unauthorized: Invalid API key",
                    artifacts=[],
                    opsec_context={
                        "api_error": "authentication_failed",
                        "service": "virustotal"
                    },
                    execution_time=0.0
                )
            
            if response.status_code == 429:
                return ExecutionResult(
                    success=False,
                    output=None,
                    error="Rate limit exceeded. Please try again later.",
                    artifacts=[],
                    opsec_context={
                        "api_error": "rate_limit_exceeded",
                        "service": "virustotal"
                    },
                    execution_time=0.0
                )
            
            response.raise_for_status()
            data = response.json()
            
            # Process results
            result = self._process_response(data, scan_type)
            
            return ExecutionResult(
                success=True,
                output=result,
                error=None,
                artifacts=[{
                    "type": "threat_intelligence",
                    "source": "virustotal",
                    "resource": resource,
                    "scan_type": scan_type,
                    "timestamp": datetime.utcnow().isoformat()
                }],
                opsec_context={
                    "service": "virustotal",
                    "scan_type": scan_type,
                    "risk_assessment": self._assess_risk(result)
                },
                execution_time=0.0
            )
            
        except requests.exceptions.Timeout:
            return ExecutionResult(
                success=False,
                output=None,
                error="Request timed out",
                artifacts=[],
                opsec_context={"api_error": "timeout", "service": "virustotal"},
                execution_time=0.0
            )
        except Exception as e:
            logger.error(f"VirusTotal analysis failed: {e}")
            return ExecutionResult(
                success=False,
                output=None,
                error=str(e),
                artifacts=[],
                opsec_context={"api_error": str(e), "service": "virustotal"},
                execution_time=0.0
            )
    
    def _detect_resource_type(self, resource: str) -> str:
        """Auto-detect resource type."""
        if resource.startswith(("http://", "https://")):
            return "url"
        elif self._is_valid_ip(resource):
            return "ip"
        elif self._is_valid_domain(resource):
            return "domain"
        elif len(resource) in [32, 40, 64]:  # Common hash lengths
            return "file"
        else:
            return "url"  # Default to URL
    
    def _is_valid_ip(self, resource: str) -> bool:
        """Check if resource is a valid IP address."""
        try:
            parts = resource.split(".")
            if len(parts) != 4:
                return False
            return all(0 <= int(part) <= 255 for part in parts)
        except ValueError:
            return False
    
    def _is_valid_domain(self, resource: str) -> bool:
        """Check if resource is a valid domain."""
        if "." not in resource:
            return False
        if resource.startswith(("http://", "https://")):
            return False
        return True
    
    def _get_endpoint(self, scan_type: str, resource: str) -> str:
        """Get the appropriate VirusTotal API endpoint."""
        endpoints = {
            "url": f"{self.base_url}/urls/{self._encode_url(resource)}",
            "ip": f"{self.base_url}/ip_addresses/{resource}",
            "domain": f"{self.base_url}/domains/{resource}",
            "file": f"{self.base_url}/files/{resource}"
        }
        return endpoints.get(scan_type, endpoints["url"])
    
    def _encode_url(self, url: str) -> str:
        """Encode URL for VirusTotal API."""
        import base64
        import hashlib
        # VirusTotal requires base64 encoding of URL
        return base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
    
    def _process_response(self, data: Dict[str, Any], scan_type: str) -> Dict[str, Any]:
        """Process VirusTotal API response."""
        attributes = data.get("data", {}).get("attributes", {})
        
        # Extract analysis statistics
        last_analysis_stats = attributes.get("last_analysis_stats", {})
        malicious = last_analysis_stats.get("malicious", 0)
        suspicious = last_analysis_stats.get("suspicious", 0)
        harmless = last_analysis_stats.get("harmless", 0)
        undetected = last_analysis_stats.get("undetected", 0)
        total = sum(last_analysis_stats.values())
        
        result = {
            "malicious": malicious,
            "suspicious": suspicious,
            "harmless": harmless,
            "undetected": undetected,
            "total": total,
            "detection_ratio": f"{malicious}/{total}" if total > 0 else "0/0",
            "scan_date": attributes.get("last_modification_date", "Unknown"),
            "permalink": f"https://www.virustotal.com/gui/{scan_type}/{data.get('data', {}).get('id', '')}"
        }
        
        # Add type-specific information
        if scan_type == "ip":
            result["country"] = attributes.get("country", "Unknown")
            result["asn"] = attributes.get("asn", "Unknown")
        elif scan_type == "domain":
            result["creation_date"] = attributes.get("creation_date", "Unknown")
        
        return result
    
    def _assess_risk(self, result: Dict[str, Any]) -> str:
        """Assess risk level based on VirusTotal results."""
        malicious = result.get("malicious", 0)
        total = result.get("total", 1)
        
        if malicious == 0:
            return "low"
        elif malicious / total < 0.1:
            return "low"
        elif malicious / total < 0.3:
            return "medium"
        else:
            return "high"
    
    async def health_check(self) -> Dict[str, Any]:
        """Check plugin health."""
        try:
            if not self.api_key:
                return {
                    "healthy": True,
                    "status": "limited",
                    "message": "Plugin running but API key not configured"
                }
            
            response = requests.get(
                f"{self.base_url}/api_key",
                headers={"x-apikey": self.api_key},
                timeout=5
            )
            
            return {
                "healthy": response.status_code == 200,
                "status": "operational" if response.status_code == 200 else "degraded",
                "message": "API connection successful" if response.status_code == 200 else "API connection failed"
            }
        except Exception as e:
            return {
                "healthy": False,
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def cleanup(self):
        """Cleanup plugin resources."""
        logger.info("VirusTotal plugin cleaned up")