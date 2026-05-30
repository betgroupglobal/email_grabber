"""
Nmap plugin implementation.
"""

import asyncio
import logging
import subprocess
import xml.etree.ElementTree as ET
from typing import Dict, Any, List
import re

import sys
import os
# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from plugin_system.base import (
    BasePlugin,
    PluginConfig,
    ExecutionContext,
    ExecutionResult
)


logger = logging.getLogger(__name__)


class NmapPlugin(BasePlugin):
    """Nmap network scanner plugin."""
    
    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.nmap_binary = "nmap"
    
    async def initialize(self) -> None:
        """Initialize Nmap plugin."""
        # Get nmap binary path from config
        if 'local' in self.config.execution:
            self.nmap_binary = self.config.execution['local'].get('binary', 'nmap')
        
        # Verify nmap is available
        try:
            result = await self._run_nmap(["--version"])
            if "Nmap" not in result:
                raise RuntimeError("Nmap binary not found or not working")
            
            self._initialized = True
            self.status = self.status.READY
            logger.info("Nmap plugin initialized successfully")
            
        except Exception as e:
            logger.error(f"Nmap plugin initialization failed: {e}")
            self.status = self.status.ERROR
            raise
    
    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Execute Nmap scan."""
        import time
        start_time = time.time()
        
        try:
            # Build nmap command
            args = await self._build_nmap_args(context.parameters)
            
            # Run nmap
            xml_output = await self._run_nmap(args)
            
            # Parse results
            parsed_results = await self._parse_xml_output(xml_output)
            
            execution_time = time.time() - start_time
            
            # Build artifacts
            artifacts = [
                {
                    "type": "scan_output",
                    "value": xml_output,
                    "description": "Raw Nmap XML output"
                },
                {
                    "type": "parsed_results",
                    "value": parsed_results,
                    "description": "Parsed scan results"
                }
            ]
            
            # OpSec context (if enabled)
            opsec_context = None
            if self.config.opsec and self.config.opsec.get('enabled'):
                opsec_context = {
                    "integration": "nmap",
                    "risk_level": self.config.opsec.get('risk_level', 'medium'),
                    "noise_level": self.config.opsec.get('noise_level', 'medium'),
                    "detection_methods": self.config.opsec.get('detection_methods', []),
                    "evasion_recommendations": self.config.opsec.get('evasion_recommendations', []),
                    "target": context.target,
                    "scan_type": context.parameters.get('scan_type', 'tcp'),
                    "timing": context.parameters.get('timing', 'T4')
                }
            
            return ExecutionResult(
                success=True,
                output={
                    "xml_output": xml_output,
                    "parsed_results": parsed_results,
                    "scan_time": execution_time
                },
                error=None,
                artifacts=artifacts,
                opsec_context=opsec_context,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Nmap execution failed: {e}")
            
            return ExecutionResult(
                success=False,
                output=None,
                error=str(e),
                artifacts=[],
                opsec_context=None,
                execution_time=execution_time
            )
    
    async def validate_input(self, parameters: Dict[str, Any]) -> bool:
        """Validate input parameters."""
        if 'target' not in parameters:
            raise ValueError("Missing required parameter: target")
        
        target = parameters['target']
        
        # Basic target validation
        if not self._is_valid_target(target):
            raise ValueError(f"Invalid target format: {target}")
        
        # Validate port specification if provided
        if parameters.get('ports'):
            ports = parameters['ports']
            if not self._is_valid_port_spec(ports):
                raise ValueError(f"Invalid port specification: {ports}")
        
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Nmap health."""
        try:
            result = await self._run_nmap(["--version"])
            if "Nmap" in result:
                return {
                    "healthy": True,
                    "version": self._extract_version(result),
                    "binary": self.nmap_binary
                }
            else:
                return {
                    "healthy": False,
                    "error": "Nmap not functioning properly"
                }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("Nmap plugin cleanup complete")
    
    async def _build_nmap_args(self, parameters: Dict[str, Any]) -> List[str]:
        """Build Nmap command arguments."""
        args = []
        
        # Default args from config
        if 'local' in self.config.execution:
            default_args = self.config.execution['local'].get('default_args', [])
            args.extend(default_args)
        
        # Scan type
        scan_type = parameters.get('scan_type', 'tcp')
        if scan_type == 'tcp':
            args.append('-sS')  # SYN scan
        elif scan_type == 'connect':
            args.append('-sT')  # TCP connect
        elif scan_type == 'udp':
            args.append('-sU')  # UDP scan
        elif scan_type == 'syn':
            args.append('-sS')  # SYN scan
        elif scan_type == 'quick':
            args.extend(['-sS', '-F'])  # Fast top ports

        # Timing
        timing = parameters.get('timing', 'T4')
        args.append(f'-{timing}')
        
        # Ports
        if 'ports' in parameters:
            args.extend(['-p', parameters['ports']])
        
        # Target
        args.append(parameters['target'])
        
        return args
    
    async def _run_nmap(self, args: List[str]) -> str:
        """Run Nmap command and return output."""
        try:
            # Run subprocess
            process = await asyncio.create_subprocess_exec(
                self.nmap_binary,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore')
                raise RuntimeError(f"Nmap failed: {error_msg}")
            
            return stdout.decode('utf-8', errors='ignore')
            
        except FileNotFoundError:
            raise RuntimeError(f"Nmap binary not found: {self.nmap_binary}")
        except Exception as e:
            raise RuntimeError(f"Nmap execution failed: {e}")
    
    async def _parse_xml_output(self, xml_output: str) -> Dict[str, Any]:
        """Parse Nmap XML output."""
        try:
            root = ET.fromstring(xml_output)
            
            results = {
                "hosts": [],
                "scan_stats": {}
            }
            
            # Parse hosts
            for host in root.findall('.//host'):
                host_info = {
                    "status": host.find('.//status').get('state'),
                    "addresses": [],
                    "ports": []
                }
                
                # Addresses
                for addr in host.findall('.//address'):
                    host_info["addresses"].append({
                        "addr": addr.get('addr'),
                        "type": addr.get('addrtype')
                    })
                
                # Ports
                for port in host.findall('.//port'):
                    port_info = {
                        "protocol": port.get('protocol'),
                        "portid": port.get('portid'),
                        "state": port.find('.//state').get('state'),
                        "service": {}
                    }
                    
                    service = port.find('.//service')
                    if service is not None:
                        port_info["service"] = {
                            "name": service.get('name'),
                            "product": service.get('product'),
                            "version": service.get('version')
                        }
                    
                    host_info["ports"].append(port_info)
                
                results["hosts"].append(host_info)
            
            return results
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML output: {e}")
            return {"error": str(e)}
    
    def _is_valid_target(self, target: str) -> bool:
        """Validate target format."""
        # Basic validation for IP, hostname, or CIDR
        patterns = [
            r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$',  # IPv4
            r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$',  # CIDR
            r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]+[a-zA-Z0-9]$',  # Hostname
            r'^localhost$',  # localhost
        ]
        
        for pattern in patterns:
            if re.match(pattern, target):
                return True
        
        return False
    
    def _is_valid_port_spec(self, ports: str) -> bool:
        """Validate port specification."""
        # Allow single port, comma-separated, or ranges
        pattern = r'^\d+(,\d+)*(-\d+)?(,\d+(-\d+)?)*$'
        return bool(re.match(pattern, ports))
    
    def _extract_version(self, version_output: str) -> str:
        """Extract version string from nmap --version output."""
        match = re.search(r'Nmap version (\d+\.\d+)', version_output)
        return match.group(1) if match else "unknown"