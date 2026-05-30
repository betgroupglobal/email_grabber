#!/usr/bin/env python3
"""
OpsecAI - Enhanced Comprehensive Menu Startup Interface
Interactive CLI with live module analysis, service management, and advanced features
"""

import os
import sys
import time
import json
import signal
import subprocess
import threading
import pickle
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from functools import wraps, lru_cache
from collections import deque
import asyncio
import aiohttp
from contextlib import asynccontextmanager

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.table import Table
    from rich.live import Live
    from rich.text import Text
    from rich.align import Align
    from rich.syntax import Syntax
    from rich.prompt import Prompt, Confirm
    from rich.rule import Rule
    from rich.box import Box, HEAVY, ROUNDED
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Warning: rich library not found. Install with: pip install rich")
    print("Falling back to basic CLI...")

class ServiceStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    UNKNOWN = "unknown"
    RESTARTING = "restarting"

@dataclass
class ServiceInfo:
    name: str
    port: int
    health_url: str
    status: ServiceStatus
    pid: Optional[int] = None
    uptime: float = 0.0
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    last_check: Optional[str] = None
    error_message: Optional[str] = None
    restart_count: int = 0
    last_restart: Optional[str] = None
    auto_restart: bool = False

@dataclass
class HealthCheckResult:
    service: str
    healthy: bool
    response_time_ms: float
    timestamp: datetime
    error: Optional[str] = None

@dataclass
class ServiceProfile:
    name: str
    description: str
    services: List[str]
    auto_start: bool = True
    auto_restart: bool = False

class CircuitBreaker:
    """Circuit breaker pattern for health checks."""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def record_success(self):
        self.failures = 0
        self.state = "closed"
    
    def record_failure(self):
        self.failures += 1
        self.last_failure_time = datetime.now()
        if self.failures >= self.failure_threshold:
            self.state = "open"
    
    def can_attempt(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if self.last_failure_time and (datetime.now() - self.last_failure_time).total_seconds() > self.timeout:
                self.state = "half-open"
                return True
            return False
        return True  # half-open allows one attempt

def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator for retry logic with exponential backoff."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
            raise last_error
        return wrapper
    return decorator

class OpsecStartupManagerEnhanced:
    """Enhanced startup and service management system with advanced features."""
    
    def __init__(self):
        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        self.services: Dict[str, ServiceInfo] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        self.running = False
        self.monitoring = False
        self.console = Console() if RICH_AVAILABLE else None
        
        # Performance optimizations
        self.health_cache: Dict[str, Tuple[HealthCheckResult, float]] = {}
        self.cache_ttl = 5.0  # Cache health results for 5 seconds
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Circuit breakers for each service
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Historical metrics (last 100 data points per service)
        self.historical_metrics: Dict[str, deque] = {}
        
        # Log streaming
        self.log_buffers: Dict[str, List[str]] = {}
        
        # Quick actions shortcuts
        self.shortcuts = {
            'q': 'quit',
            'h': 'help',
            's': 'status',
            'a': 'start_all',
            'x': 'stop_all',
            'k': 'kill_all',
            'm': 'monitor',
            'l': 'logs',
            'c': 'config',
            'p': 'profiles',
            'r': 'restart'
        }
        
        # Service definitions (must be defined before services initialization)
        self.service_definitions = {
            "postgres": {
                "name": "PostgreSQL",
                "port": 5432,
                "health_url": "http://localhost:5432",
                "start_cmd": self._start_postgres,
                "stop_cmd": self._stop_postgres,
                "type": "docker",
                "critical": True,
                "startup_timeout": 30
            },
            "qdrant": {
                "name": "Qdrant Vector DB",
                "port": 6333,
                "health_url": "http://localhost:6333/health",
                "start_cmd": self._start_qdrant,
                "stop_cmd": self._stop_qdrant,
                "type": "docker",
                "critical": True,
                "startup_timeout": 20
            },
            "redis": {
                "name": "Redis Cache",
                "port": 6379,
                "health_url": "http://localhost:6379",
                "start_cmd": self._start_redis,
                "stop_cmd": self._stop_redis,
                "type": "docker",
                "critical": True,
                "startup_timeout": 15
            },
            "knowledge_engine": {
                "name": "Knowledge Engine",
                "port": 8010,
                "health_url": "http://localhost:8010/health",
                "start_cmd": self._start_knowledge_engine,
                "stop_cmd": self._stop_service,
                "type": "python",
                "critical": True,
                "startup_timeout": 45
            },
            "opsec_monitor": {
                "name": "OpSec Monitor",
                "port": 8002,
                "health_url": "http://localhost:8002/health",
                "start_cmd": self._start_opsec_monitor,
                "stop_cmd": self._stop_service,
                "type": "python",
                "critical": False,
                "startup_timeout": 30
            },
            "realtime_analyzer": {
                "name": "Real-time Analyzer",
                "port": 8001,
                "health_url": "http://localhost:8001/health",
                "start_cmd": self._start_realtime_analyzer,
                "stop_cmd": self._stop_service,
                "type": "go",
                "critical": False,
                "startup_timeout": 30
            },
            "orchestrator": {
                "name": "Orchestrator",
                "port": 3001,
                "health_url": "http://localhost:3001/health",
                "start_cmd": self._start_orchestrator,
                "stop_cmd": self._stop_service,
                "type": "node",
                "critical": True,
                "startup_timeout": 30
            },
            "integration_hub": {
                "name": "Integration Hub",
                "port": 8500,
                "health_url": "http://localhost:8500/health",
                "start_cmd": self._start_integration_hub,
                "stop_cmd": self._stop_service,
                "type": "python",
                "critical": False,
                "startup_timeout": 30
            },
            "dashboard": {
                "name": "Dashboard",
                "port": 3000,
                "health_url": "http://localhost:3000",
                "start_cmd": self._start_dashboard,
                "stop_cmd": self._stop_service,
                "type": "react",
                "critical": False,
                "startup_timeout": 60
            }
        }
        
        # Initialize service info
        for key, definition in self.service_definitions.items():
            self.services[key] = ServiceInfo(
                name=definition["name"],
                port=definition["port"],
                health_url=definition["health_url"],
                status=ServiceStatus.STOPPED
            )
            self.historical_metrics[key] = deque(maxlen=100)
            self.circuit_breakers[key] = CircuitBreaker()
            self.log_buffers[key] = []
        
        # Service profiles
        self.service_profiles = self._init_service_profiles()
        self.active_profile: Optional[str] = None
        
        # Auto-restart task
        self.auto_restart_task: Optional[asyncio.Task] = None
        
        # Load environment
        self._load_env()
        
        # Load saved state
        self._load_state()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _init_service_profiles(self) -> Dict[str, ServiceProfile]:
        """Initialize service profiles."""
        return {
            "full": ServiceProfile(
                name="Full Stack",
                description="All services for complete functionality",
                services=list(self.service_definitions.keys()),
                auto_start=True,
                auto_restart=False
            ),
            "core": ServiceProfile(
                name="Core Services",
                description="Essential services without dashboard",
                services=["postgres", "qdrant", "redis", "knowledge_engine", "orchestrator"],
                auto_start=True,
                auto_restart=True
            ),
            "minimal": ServiceProfile(
                name="Minimal",
                description="Infrastructure and knowledge engine only",
                services=["postgres", "qdrant", "knowledge_engine"],
                auto_start=True,
                auto_restart=True
            ),
            "development": ServiceProfile(
                name="Development",
                description="All services with auto-restart enabled",
                services=list(self.service_definitions.keys()),
                auto_start=True,
                auto_restart=True
            )
        }

    def _load_env(self):
        """Load environment variables from .env file."""
        env_file = os.path.join(self.root_dir, ".env")
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value

    def _load_state(self):
        """Load saved state from file."""
        state_file = os.path.join(self.root_dir, ".opsec_state.pkl")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'rb') as f:
                    state = pickle.load(f)
                    self.active_profile = state.get('active_profile')
            except Exception as e:
                if self.console:
                    self.console.print(f"Warning: Could not load state: {e}", style="yellow")

    def _save_state(self):
        """Save current state to file."""
        state_file = os.path.join(self.root_dir, ".opsec_state.pkl")
        try:
            with open(state_file, 'wb') as f:
                pickle.dump({'active_profile': self.active_profile}, f)
        except Exception as e:
            if self.console:
                self.console.print(f"Warning: Could not save state: {e}", style="yellow")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print("\n\nShutdown signal received. Stopping all services...")
        self.stop_all_services()
        self._save_state()
        sys.exit(0)

    @asynccontextmanager
    async def get_http_session(self):
        """Get or create HTTP session with connection pooling."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=10, connect=5)
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=20)
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        try:
            yield self.session
        finally:
            pass  # Keep session alive for reuse

    @lru_cache(maxsize=128)
    def _get_cached_env_hash(self) -> str:
        """Get hash of environment variables for cache invalidation."""
        env_str = json.dumps(dict(os.environ), sort_keys=True)
        return hashlib.md5(env_str.encode()).hexdigest()

    async def check_service_health_optimized(self, service_key: str) -> HealthCheckResult:
        """Optimized health check with caching and circuit breaker."""
        service = self.services[service_key]
        circuit_breaker = self.circuit_breakers[service_key]
        
        # Check circuit breaker
        if not circuit_breaker.can_attempt():
            return HealthCheckResult(
                service=service_key,
                healthy=False,
                response_time_ms=0,
                timestamp=datetime.now(),
                error="Circuit breaker open"
            )
        
        # Check cache
        cache_key = f"{service_key}_{self._get_cached_env_hash()}"
        if cache_key in self.health_cache:
            cached_result, cache_time = self.health_cache[cache_key]
            if time.time() - cache_time < self.cache_ttl:
                return cached_result
        
        # Perform actual health check
        start_time = time.time()
        try:
            async with self.get_http_session() as session:
                async with session.get(service.health_url, timeout=aiohttp.ClientTimeout(total=2)) as response:
                    response_time = (time.time() - start_time) * 1000
                    is_healthy = response.status == 200
                    
                    result = HealthCheckResult(
                        service=service_key,
                        healthy=is_healthy,
                        response_time_ms=response_time,
                        timestamp=datetime.now()
                    )
                    
                    if is_healthy:
                        circuit_breaker.record_success()
                    else:
                        circuit_breaker.record_failure()
                    
                    # Cache result
                    self.health_cache[cache_key] = (result, time.time())
                    
                    # Update service info
                    service.last_check = datetime.now().strftime("%H:%M:%S")
                    service.error_message = None if is_healthy else "Health check failed"
                    
                    return result
                    
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            circuit_breaker.record_failure()
            
            result = HealthCheckResult(
                service=service_key,
                healthy=False,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error=str(e)
            )
            
            service.error_message = str(e)
            service.last_check = datetime.now().strftime("%H:%M:%S")
            
            return result

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def start_service_with_retry(self, service_key: str) -> bool:
        """Start service with retry logic."""
        return self.start_service(service_key)

    async def update_service_status(self, service_key: str):
        """Update service status with optimized health checks."""
        service = self.services[service_key]
        
        if service_key in self.processes and self.processes[service_key]:
            process = self.processes[service_key]
            if process.poll() is None:
                service.status = ServiceStatus.RUNNING
                service.pid = process.pid
                service.uptime = time.time() - getattr(process, 'start_time', time.time())
                
                # Optimized health check
                health_result = await self.check_service_health_optimized(service_key)
                
                if health_result.healthy:
                    service.status = ServiceStatus.RUNNING
                    service.error_message = None
                else:
                    service.status = ServiceStatus.ERROR
                    
                # Record historical metrics
                self.historical_metrics[service_key].append({
                    'timestamp': datetime.now(),
                    'cpu': service.cpu_percent,
                    'memory': service.memory_mb,
                    'healthy': health_result.healthy,
                    'response_time': health_result.response_time_ms
                })
            else:
                service.status = ServiceStatus.STOPPED
                service.pid = None
                
                # Auto-restart if enabled
                if service.auto_restart and service.restart_count < 5:
                    await self._auto_restart_service(service_key)
        else:
            service.status = ServiceStatus.STOPPED
            service.pid = None

    async def _auto_restart_service(self, service_key: str):
        """Automatically restart a failed service."""
        service = self.services[service_key]
        
        if self.console:
            self.console.print(f"Auto-restarting {service.name}...", style="yellow")
        
        service.status = ServiceStatus.RESTARTING
        service.restart_count += 1
        service.last_restart = datetime.now().strftime("%H:%M:%S")
        
        # Stop first
        self.stop_service(service_key)
        await asyncio.sleep(2)
        
        # Start again
        success = await self.start_service_with_retry(service_key)
        
        if success:
            if self.console:
                self.console.print(f"✓ {service.name} restarted successfully", style="green")
        else:
            if self.console:
                self.console.print(f"✗ {service.name} restart failed", style="red")

    async def start_auto_restart_monitor(self):
        """Monitor services and auto-restart if needed."""
        while self.running:
            for service_key, service in self.services.items():
                if service.auto_restart and service.status == ServiceStatus.ERROR:
                    await self._auto_restart_service(service_key)
            await asyncio.sleep(10)

    # Service start/stop methods (same as before but with enhanced error handling)
    def _start_postgres(self):
        """Start PostgreSQL via Docker."""
        try:
            subprocess.run(
                ["docker", "compose", "-f", f"{self.root_dir}/docker-compose.yml", "up", "-d", "postgres"],
                check=True,
                cwd=self.root_dir,
                capture_output=True,
                timeout=60
            )
            return True
        except subprocess.TimeoutExpired:
            if self.console:
                self.console.print("PostgreSQL startup timed out", style="red")
            return False
        except subprocess.CalledProcessError as e:
            if self.console:
                self.console.print(f"Failed to start PostgreSQL: {e.stderr.decode() if e.stderr else str(e)}", style="red")
            return False

    def _stop_postgres(self):
        """Stop PostgreSQL."""
        try:
            subprocess.run(
                ["docker", "compose", "-f", f"{self.root_dir}/docker-compose.yml", "stop", "postgres"],
                check=True,
                cwd=self.root_dir,
                capture_output=True,
                timeout=30
            )
            return True
        except Exception as e:
            if self.console:
                self.console.print(f"Failed to stop PostgreSQL: {e}", style="red")
            return False

    def _start_qdrant(self):
        """Start Qdrant via Docker."""
        try:
            subprocess.run(
                ["docker", "compose", "-f", f"{self.root_dir}/docker-compose.yml", "up", "-d", "qdrant"],
                check=True,
                cwd=self.root_dir,
                capture_output=True,
                timeout=60
            )
            return True
        except subprocess.TimeoutExpired:
            if self.console:
                self.console.print("Qdrant startup timed out", style="red")
            return False
        except subprocess.CalledProcessError as e:
            if self.console:
                self.console.print(f"Failed to start Qdrant: {e.stderr.decode() if e.stderr else str(e)}", style="red")
            return False

    def _stop_qdrant(self):
        """Stop Qdrant."""
        try:
            subprocess.run(
                ["docker", "compose", "-f", f"{self.root_dir}/docker-compose.yml", "stop", "qdrant"],
                check=True,
                cwd=self.root_dir,
                capture_output=True,
                timeout=30
            )
            return True
        except Exception as e:
            if self.console:
                self.console.print(f"Failed to stop Qdrant: {e}", style="red")
            return False

    def _start_redis(self):
        """Start Redis via Docker."""
        try:
            subprocess.run(
                ["docker", "compose", "-f", f"{self.root_dir}/docker-compose.yml", "up", "-d", "redis"],
                check=True,
                cwd=self.root_dir,
                capture_output=True,
                timeout=60
            )
            return True
        except subprocess.TimeoutExpired:
            if self.console:
                self.console.print("Redis startup timed out", style="red")
            return False
        except subprocess.CalledProcessError as e:
            if self.console:
                self.console.print(f"Failed to start Redis: {e.stderr.decode() if e.stderr else str(e)}", style="red")
            return False

    def _stop_redis(self):
        """Stop Redis."""
        try:
            subprocess.run(
                ["docker", "compose", "-f", f"{self.root_dir}/docker-compose.yml", "stop", "redis"],
                check=True,
                cwd=self.root_dir,
                capture_output=True,
                timeout=30
            )
            return True
        except Exception as e:
            if self.console:
                self.console.print(f"Failed to stop Redis: {e}", style="red")
            return False

    def _start_knowledge_engine(self):
        """Start Knowledge Engine."""
        try:
            # Install dependencies
            subprocess.run(
                ["pip3", "install", "-q", "-r", "requirements.txt"],
                check=True,
                cwd=os.path.join(self.root_dir, "backend/knowledge_engine"),
                capture_output=True,
                timeout=120
            )
            
            # Run ingestor if needed
            ingestor_path = os.path.join(self.root_dir, "backend/knowledge_engine/ingestor.py")
            if os.path.exists(ingestor_path):
                subprocess.run(
                    ["python3", "ingestor.py"],
                    check=True,
                    cwd=os.path.join(self.root_dir, "backend/knowledge_engine"),
                    capture_output=True,
                    timeout=300
                )
            
            # Start API server
            process = subprocess.Popen(
                ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8010"],
                cwd=os.path.join(self.root_dir, "backend/knowledge_engine"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            process.start_time = time.time()
            self.processes["knowledge_engine"] = process
            
            # Start log streaming
            self._start_log_streaming("knowledge_engine", process)
            
            return True
        except subprocess.TimeoutExpired:
            if self.console:
                self.console.print("Knowledge Engine startup timed out", style="red")
            return False
        except subprocess.CalledProcessError as e:
            if self.console:
                self.console.print(f"Failed to start Knowledge Engine: {e.stderr if e.stderr else str(e)}", style="red")
            return False

    def _start_opsec_monitor(self):
        """Start OpSec Monitor."""
        try:
            subprocess.run(
                ["pip3", "install", "-q", "-r", "requirements.txt"],
                check=True,
                cwd=os.path.join(self.root_dir, "backend/opsec_monitor"),
                capture_output=True,
                timeout=120
            )
            
            process = subprocess.Popen(
                ["uvicorn", "monitor:app", "--host", "0.0.0.0", "--port", "8002"],
                cwd=os.path.join(self.root_dir, "backend/opsec_monitor"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            process.start_time = time.time()
            self.processes["opsec_monitor"] = process
            self._start_log_streaming("opsec_monitor", process)
            return True
        except Exception as e:
            if self.console:
                self.console.print(f"Failed to start OpSec Monitor: {e}", style="red")
            return False

    def _start_realtime_analyzer(self):
        """Start Real-time Analyzer."""
        try:
            subprocess.run(
                ["go", "build", "-o", "/tmp/opsec-analyzer", "."],
                check=True,
                cwd=os.path.join(self.root_dir, "backend/realtime_analyzer"),
                capture_output=True,
                timeout=120
            )
            
            env = os.environ.copy()
            env["ANALYZER_ADDR"] = ":8001"
            env["KNOWLEDGE_ENGINE_URL"] = "http://localhost:8010"
            
            process = subprocess.Popen(
                ["/tmp/opsec-analyzer"],
                cwd=os.path.join(self.root_dir, "backend/realtime_analyzer"),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            process.start_time = time.time()
            self.processes["realtime_analyzer"] = process
            self._start_log_streaming("realtime_analyzer", process)
            return True
        except Exception as e:
            if self.console:
                self.console.print(f"Failed to start Real-time Analyzer: {e}", style="red")
            return False

    def _start_orchestrator(self):
        """Start Orchestrator."""
        try:
            env = os.environ.copy()
            env["PORT"] = "3001"
            env["KNOWLEDGE_ENGINE_URL"] = "http://localhost:8010"
            env["ANALYZER_URL"] = "http://localhost:8001"
            env["OPSEC_URL"] = "http://localhost:8002"
            
            process = subprocess.Popen(
                ["node", "index.js"],
                cwd=os.path.join(self.root_dir, "backend/orchestrator"),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            process.start_time = time.time()
            self.processes["orchestrator"] = process
            self._start_log_streaming("orchestrator", process)
            return True
        except Exception as e:
            if self.console:
                self.console.print(f"Failed to start Orchestrator: {e}", style="red")
            return False

    def _start_integration_hub(self):
        """Start Integration Hub."""
        try:
            subprocess.run(
                ["pip3", "install", "-q", "-r", "requirements.txt"],
                check=True,
                cwd=os.path.join(self.root_dir, "backend/integrations"),
                capture_output=True,
                timeout=120
            )
            
            process = subprocess.Popen(
                ["python3", "-m", "main"],
                cwd=os.path.join(self.root_dir, "backend/integrations"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            process.start_time = time.time()
            self.processes["integration_hub"] = process
            self._start_log_streaming("integration_hub", process)
            return True
        except Exception as e:
            if self.console:
                self.console.print(f"Failed to start Integration Hub: {e}", style="red")
            return False

    def _start_dashboard(self):
        """Start Dashboard."""
        try:
            process = subprocess.Popen(
                ["npm", "start"],
                cwd=os.path.join(self.root_dir, "frontend/dashboard"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            process.start_time = time.time()
            self.processes["dashboard"] = process
            self._start_log_streaming("dashboard", process)
            return True
        except Exception as e:
            if self.console:
                self.console.print(f"Failed to start Dashboard: {e}", style="red")
            return False

    def _start_log_streaming(self, service_key: str, process: subprocess.Popen):
        """Start streaming logs from a process."""
        def stream_logs():
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    log_entry = f"[{timestamp}] {output.strip()}"
                    self.log_buffers[service_key].append(log_entry)
                    if len(self.log_buffers[service_key]) > 100:  # Keep last 100 lines
                        self.log_buffers[service_key].pop(0)
        
        thread = threading.Thread(target=stream_logs, daemon=True)
        thread.start()

    def _stop_service(self, service_key: str):
        """Stop a generic service."""
        if service_key in self.processes and self.processes[service_key]:
            try:
                process = self.processes[service_key]
                process.terminate()
                time.sleep(2)
                if process.poll() is None:
                    process.kill()
                del self.processes[service_key]
                return True
            except Exception as e:
                if self.console:
                    self.console.print(f"Failed to stop {service_key}: {e}", style="red")
                return False
        return True

    def _kill_service(self, service_key: str):
        """Forcefully kill a service using SIGKILL."""
        # Kill tracked process
        if service_key in self.processes and self.processes[service_key]:
            try:
                process = self.processes[service_key]
                process.kill()
                del self.processes[service_key]
                if self.console:
                    self.console.print(f"✓ Killed {service_key} process", style="red")
            except Exception as e:
                if self.console:
                    self.console.print(f"Failed to kill {service_key} process: {e}", style="red")
        
        # Kill any process by port
        service = self.services[service_key]
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{service.port}"],
                capture_output=True,
                text=True
            )
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        subprocess.run(["kill", "-9", pid], capture_output=True)
                        if self.console:
                            self.console.print(f"✓ Killed process {pid} on port {service.port}", style="red")
                    except Exception as e:
                        if self.console:
                            self.console.print(f"Failed to kill PID {pid}: {e}", style="yellow")
        except Exception as e:
            if self.console:
                self.console.print(f"Failed to kill processes on port {service.port}: {e}", style="yellow")
        
        # Update service status
        service.status = ServiceStatus.STOPPED
        service.pid = None
        service.uptime = 0.0

    def start_service(self, service_key: str) -> bool:
        """Start a specific service."""
        if service_key not in self.service_definitions:
            if self.console:
                self.console.print(f"Unknown service: {service_key}", style="red")
            return False
        
        service = self.services[service_key]
        service.status = ServiceStatus.STARTING
        
        if self.console:
            self.console.print(f"Starting {service.name}...", style="yellow")
        
        success = self.service_definitions[service_key]["start_cmd"]()
        
        if success:
            if self.console:
                self.console.print(f"✓ {service.name} started successfully", style="green")
            return True
        else:
            if self.console:
                self.console.print(f"✗ {service.name} failed to start", style="red")
            service.status = ServiceStatus.ERROR
            return False

    def stop_service(self, service_key: str) -> bool:
        """Stop a specific service."""
        if service_key not in self.service_definitions:
            if self.console:
                self.console.print(f"Unknown service: {service_key}", style="red")
            return False
        
        service = self.services[service_key]
        if self.console:
            self.console.print(f"Stopping {service.name}...", style="yellow")
        
        success = self.service_definitions[service_key]["stop_cmd"](service_key)
        
        if success:
            if self.console:
                self.console.print(f"✓ {service.name} stopped successfully", style="green")
            service.status = ServiceStatus.STOPPED
            return True
        else:
            if self.console:
                self.console.print(f"✗ {service.name} failed to stop", style="red")
            return False

    def start_profile(self, profile_name: str) -> bool:
        """Start services from a profile."""
        if profile_name not in self.service_profiles:
            if self.console:
                self.console.print(f"Unknown profile: {profile_name}", style="red")
            return False
        
        profile = self.service_profiles[profile_name]
        self.active_profile = profile_name
        self._save_state()
        
        if self.console:
            self.console.print(f"\nStarting profile: {profile.name}", style="bold cyan")
            self.console.print(f"Description: {profile.description}\n", style="dim")
        
        # Start services in dependency order
        dependency_order = [
            "postgres", "qdrant", "redis",
            "knowledge_engine", "opsec_monitor",
            "realtime_analyzer", "integration_hub",
            "orchestrator", "dashboard"
        ]
        
        for service in dependency_order:
            if service in profile.services:
                self.start_service(service)
                time.sleep(2)
                
                # Enable auto-restart if specified
                if profile.auto_restart:
                    self.services[service].auto_restart = True
        
        return True

    def start_all_services(self):
        """Start all services in dependency order."""
        if self.console:
            self.console.print("\n[bold blue]=== Starting OpsecAI Services ===[/bold blue]\n")
        
        # Use full profile
        self.start_profile("full")

    def stop_all_services(self):
        """Stop all services in reverse order."""
        if self.console:
            self.console.print("\n[bold blue]=== Stopping OpsecAI Services ===[/bold blue]\n")
        
        # Stop in reverse order
        services_reverse = list(self.service_definitions.keys())[::-1]
        for service in services_reverse:
            self.stop_service(service)
            time.sleep(1)
        
        # Close HTTP session
        if self.session and not self.session.closed:
            asyncio.create_task(self.session.close())
        
        if self.console:
            self.console.print("\n[bold green]=== All services stopped ===[/bold green]\n")

    def kill_all_services(self):
        """Forcefully kill all services without graceful shutdown."""
        if self.console:
            self.console.print("\n[bold red]=== Forcefully Killing All Services ===[/bold red]\n")
        
        # Kill all tracked processes first
        if self.console:
            self.console.print("Killing tracked processes...", style="yellow")
        
        for service_key in list(self.processes.keys()):
            self._kill_service(service_key)
        
        # Kill any remaining processes by port
        if self.console:
            self.console.print("\nKilling processes by port...", style="yellow")
        
        for service_key, service in self.services.items():
            try:
                result = subprocess.run(
                    ["lsof", "-ti", f":{service.port}"],
                    capture_output=True,
                    text=True
                )
                if result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        try:
                            subprocess.run(["kill", "-9", pid], capture_output=True)
                            if self.console:
                                self.console.print(f"✓ Killed PID {pid} on port {service.port}", style="red")
                        except Exception as e:
                            if self.console:
                                self.console.print(f"Failed to kill PID {pid}: {e}", style="yellow")
            except Exception as e:
                if self.console:
                    self.console.print(f"Failed to check port {service.port}: {e}", style="yellow")
        
        # Force kill Docker containers
        if self.console:
            self.console.print("\nForce killing Docker containers...", style="yellow")
        
        docker_services = ["postgres", "qdrant", "redis"]
        for service in docker_services:
            try:
                subprocess.run(
                    ["docker", "compose", "-f", f"{self.root_dir}/docker-compose.yml", "kill", service],
                    check=True,
                    cwd=self.root_dir,
                    capture_output=True
                )
                if self.console:
                    self.console.print(f"✓ Killed Docker container: {service}", style="red")
            except Exception as e:
                if self.console:
                    self.console.print(f"Failed to kill Docker container {service}: {e}", style="yellow")
        
        # Clean up process tracking
        self.processes.clear()
        
        # Reset service statuses
        for service in self.services.values():
            service.status = ServiceStatus.STOPPED
            service.pid = None
            service.uptime = 0.0
        
        # Close HTTP session
        if self.session and not self.session.closed:
            asyncio.create_task(self.session.close())
        
        if self.console:
            self.console.print("\n[bold red]=== All services killed forcefully ===[/bold red]\n")
            self.console.print("[yellow]Warning: This was a forceful termination. Data may have been lost.[/yellow]\n")

    async def monitor_services(self):
        """Monitor service health and update status."""
        while self.monitoring:
            tasks = [self.update_service_status(service_key) for service_key in self.services]
            await asyncio.gather(*tasks)
            await asyncio.sleep(3)  # Reduced from 5 seconds for better responsiveness

    def show_enhanced_menu(self):
        """Display the enhanced menu with shortcuts."""
        if not RICH_AVAILABLE:
            self._show_basic_menu()
            return
        
        self.console.clear()
        
        # Create enhanced layout
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=4),
            Layout(name="profile", size=3),
            Layout(name="menu", size=18),
            Layout(name="status", size=22),
            Layout(name="shortcuts", size=4),
            Layout(name="footer", size=3)
        )
        
        # Header with profile info
        profile_info = f"Profile: {self.active_profile or 'None'}" if self.active_profile else "Profile: Default"
        header_text = Text()
        header_text.append("OpsecAI - Enhanced Service Management\n", style="bold cyan")
        header_text.append(profile_info, style="dim")
        
        header = Panel(
            Align.center(header_text),
            style="blue"
        )
        layout["header"].update(header)
        
        # Profile selection
        profile_text = Text()
        profile_text.append("Profiles: ", style="bold")
        for profile_name in self.service_profiles:
            prefix = "• " if profile_name == self.active_profile else "  "
            profile_text.append(f"{prefix}{profile_name}  ", style="yellow" if profile_name == self.active_profile else "dim")
        layout["profile"].update(Panel(profile_text, title="Active Profile", border_style="yellow"))
        
        # Enhanced menu
        menu_text = Text()
        menu_text.append("Main Menu:\n\n", style="bold")
        menu_text.append("1. Start All Services          ", style="green"); menu_text.append("[a]\n", style="dim")
        menu_text.append("2. Stop All Services           ", style="red"); menu_text.append("[x]\n", style="dim")
        menu_text.append("3. Kill All Services           ", style="bold red"); menu_text.append("[k]\n", style="dim")
        menu_text.append("4. Start Specific Service      ", style="yellow"); menu_text.append("[s+name]\n", style="dim")
        menu_text.append("5. Stop Specific Service       ", style="yellow"); menu_text.append("[s-name]\n", style="dim")
        menu_text.append("6. View Service Status         ", style="cyan"); menu_text.append("[s]\n", style="dim")
        menu_text.append("7. Start Live Monitoring       ", style="magenta"); menu_text.append("[m]\n", style="dim")
        menu_text.append("8. View Logs                   ", style="blue"); menu_text.append("[l]\n", style="dim")
        menu_text.append("9. System Health Check         ", style="white")
        menu_text.append("10. Configuration Validation  ", style="white")
        menu_text.append("11. Select Service Profile     ", style="yellow"); menu_text.append("[p]\n", style="dim")
        menu_text.append("12. Toggle Auto-Restart        ", style="yellow"); menu_text.append("[r]\n", style="dim")
        menu_text.append("13. View Historical Metrics    ", style="cyan")
        menu_text.append("14. Edit Configuration         ", style="white"); menu_text.append("[c]\n", style="dim")
        menu_text.append("0. Exit                        ", style="bold red"); menu_text.append("[q]\n", style="dim")
        menu_text.append("\nEnter choice: ", style="dim")
        
        layout["menu"].update(Panel(menu_text, title="Commands", border_style="green"))
        
        # Status table
        status_table = self.create_status_table()
        layout["status"].update(Panel(status_table, title="Service Status", border_style="cyan"))
        
        # Shortcuts
        shortcuts_text = Text()
        shortcuts_text.append("Shortcuts: ", style="bold")
        for key, action in self.shortcuts.items():
            shortcuts_text.append(f"[{key}] {action}  ", style="cyan")
        layout["shortcuts"].update(Panel(shortcuts_text, border_style="dim"))
        
        # Footer
        footer = Panel(
            Align.center(Text("Press Ctrl+C to exit | Type 'h' for help", style="dim")),
            style="dim"
        )
        layout["footer"].update(footer)
        
        self.console.print(layout)

    def create_status_table(self) -> Table:
        """Create enhanced status table with more information."""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Service", style="cyan", width=18)
        table.add_column("Status", style="green", width=12)
        table.add_column("Port", style="yellow", width=6)
        table.add_column("PID", style="blue", width=8)
        table.add_column("Uptime", style="white", width=10)
        table.add_column("Restarts", style="red", width=8)
        table.add_column("Auto-R", style="magenta", width=6)
        
        for service_key, service in self.services.items():
            status_color = {
                ServiceStatus.RUNNING: "green",
                ServiceStatus.STARTING: "yellow",
                ServiceStatus.STOPPED: "red",
                ServiceStatus.ERROR: "bold red",
                ServiceStatus.RESTARTING: "yellow",
                ServiceStatus.UNKNOWN: "dim"
            }.get(service.status, "white")
            
            status_text = {
                ServiceStatus.RUNNING: "● Running",
                ServiceStatus.STARTING: "◐ Starting",
                ServiceStatus.STOPPED: "○ Stopped",
                ServiceStatus.ERROR: "● Error",
                ServiceStatus.RESTARTING: "◐ Restart",
                ServiceStatus.UNKNOWN: "? Unknown"
            }.get(service.status, str(service.status))
            
            uptime_str = f"{service.uptime:.0f}s" if service.uptime > 0 else "-"
            pid_str = str(service.pid) if service.pid else "-"
            auto_restart_str = "✓" if service.auto_restart else "✗"
            
            table.add_row(
                service.name,
                Text(status_text, style=status_color),
                str(service.port),
                pid_str,
                uptime_str,
                str(service.restart_count),
                auto_restart_str
            )
        
        return table

    def show_service_list(self):
        """Display list of available services with indicators."""
        if self.console:
            table = Table(title="Available Services")
            table.add_column("Key", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Port", style="yellow")
            table.add_column("Critical", style="red")
            
            for key, definition in self.service_definitions.items():
                critical = "Yes" if definition.get("critical", False) else "No"
                table.add_row(key, definition["name"], str(definition["port"]), critical)
            
            self.console.print(table)

    def show_logs(self, service_key: str):
        """Show logs for a specific service."""
        if service_key not in self.log_buffers:
            if self.console:
                self.console.print(f"No logs available for {service_key}", style="red")
            return
        
        logs = self.log_buffers[service_key]
        if not logs:
            if self.console:
                self.console.print(f"No logs recorded for {service_key}", style="yellow")
            return
        
        if self.console:
            self.console.print(f"\n[bold blue]=== Logs for {service_key} ===[/bold blue]\n")
            for log in logs[-20:]:  # Show last 20 lines
                self.console.print(log)
            self.console.print()

    def show_historical_metrics(self, service_key: str):
        """Show historical metrics for a service."""
        if service_key not in self.historical_metrics:
            if self.console:
                self.console.print(f"No metrics available for {service_key}", style="red")
            return
        
        metrics = list(self.historical_metrics[service_key])
        if not metrics:
            if self.console:
                self.console.print(f"No historical data for {service_key}", style="yellow")
            return
        
        if self.console:
            table = Table(title=f"Historical Metrics - {service_key}")
            table.add_column("Time", style="cyan")
            table.add_column("CPU %", style="yellow")
            table.add_column("Memory MB", style="green")
            table.add_column("Healthy", style="magenta")
            table.add_column("Response Time", style="white")
            
            for metric in metrics[-10:]:  # Show last 10 entries
                time_str = metric['timestamp'].strftime("%H:%M:%S")
                healthy_str = "✓" if metric['healthy'] else "✗"
                table.add_row(
                    time_str,
                    f"{metric['cpu']:.1f}",
                    f"{metric['memory']:.1f}",
                    healthy_str,
                    f"{metric['response_time']:.1f}ms"
                )
            
            self.console.print(table)

    def toggle_auto_restart(self, service_key: str):
        """Toggle auto-restart for a service."""
        if service_key not in self.services:
            if self.console:
                self.console.print(f"Unknown service: {service_key}", style="red")
            return
        
        service = self.services[service_key]
        service.auto_restart = not service.auto_restart
        
        status = "enabled" if service.auto_restart else "disabled"
        if self.console:
            self.console.print(f"Auto-restart {status} for {service.name}", style="green")

    def select_profile(self):
        """Interactive profile selection."""
        if not RICH_AVAILABLE:
            print("Available profiles:", list(self.service_profiles.keys()))
            profile = input("Select profile: ").strip()
            self.start_profile(profile)
            return
        
        if self.console:
            self.console.print("\n[bold cyan]Available Profiles:[/bold cyan]\n")
            
            table = Table()
            table.add_column("Name", style="cyan")
            table.add_column("Description", style="white")
            table.add_column("Services", style="yellow")
            table.add_column("Auto-Restart", style="magenta")
            
            for name, profile in self.service_profiles.items():
                active = " ← Active" if name == self.active_profile else ""
                table.add_row(
                    f"{name}{active}",
                    profile.description,
                    str(len(profile.services)),
                    "Yes" if profile.auto_restart else "No"
                )
            
            self.console.print(table)
            
            profile_name = Prompt.ask("Select profile", choices=list(self.service_profiles.keys()))
            self.start_profile(profile_name)

    async def live_monitor(self):
        """Start live monitoring with enhanced visuals."""
        if not RICH_AVAILABLE:
            print("Live monitoring requires rich library")
            return
        
        self.monitoring = True
        self.console.clear()
        
        # Status icons for visual appeal
        STATUS_ICONS = {
            ServiceStatus.RUNNING: "🟢",
            ServiceStatus.STARTING: "🟡",
            ServiceStatus.STOPPED: "🔴",
            ServiceStatus.ERROR: "⚠️",
            ServiceStatus.RESTARTING: "🔄",
            ServiceStatus.UNKNOWN: "⚪"
        }
        
        def _create_progress_bar(value: float, total: float = 100, width: int = 10) -> str:
            """Create a visual progress bar."""
            filled = int((value / total) * width)
            bar = "█" * filled + "░" * (width - filled)
            return bar
        
        start_time = datetime.now()
        
        with Live(refresh_per_second=1, screen=True) as live:
            while self.monitoring:
                # Update service statuses
                tasks = [self.update_service_status(service_key) for service_key in self.services]
                await asyncio.gather(*tasks)
                
                # Enhanced display with better layout
                layout = Layout()
                layout.split_column(
                    Layout(name="header", size=3),
                    Layout(name="main", ratio=1),
                    Layout(name="footer", size=3)
                )
                
                layout["main"].split_row(
                    Layout(name="left", ratio=2),
                    Layout(name="right", ratio=1)
                )
                
                # Enhanced header with branding
                uptime = datetime.now() - start_time
                uptime_str = str(uptime).split('.')[0]
                
                header_text = Text()
                header_text.append("🔷 ", style="bold cyan")
                header_text.append("OpsecAI", style="bold cyan")
                header_text.append(" ", style="dim")
                header_text.append("Service Monitor", style="bold white")
                header_text.append(" " * 20, style="dim")
                header_text.append(f"⏱ {uptime_str}", style="dim")
                header_text.append(" " * 5, style="dim")
                header_text.append("🔄 Live", style="green")
                
                header = Panel(
                    Align.center(header_text),
                    box=HEAVY,
                    border_style="cyan"
                )
                layout["header"].update(header)
                
                # Enhanced status table
                status_table = Table(
                    show_header=True,
                    header_style="bold magenta",
                    box=ROUNDED,
                    padding=(0, 1)
                )
                status_table.add_column("Service", style="cyan", width=18)
                status_table.add_column("Status", style="white", width=12)
                status_table.add_column("Port", style="yellow", width=6)
                status_table.add_column("PID", style="blue", width=8)
                status_table.add_column("Uptime", style="white", width=10)
                status_table.add_column("Restarts", style="red", width=8)
                status_table.add_column("Auto-R", style="magenta", width=6)
                
                for service_key, service in self.services.items():
                    status_icon = STATUS_ICONS.get(service.status, '⚪')
                    status_text = f"{status_icon} {service.status.title()}"
                    
                    status_color = {
                        ServiceStatus.RUNNING: "green",
                        ServiceStatus.STARTING: "yellow",
                        ServiceStatus.STOPPED: "red",
                        ServiceStatus.ERROR: "bold red",
                        ServiceStatus.RESTARTING: "yellow",
                        ServiceStatus.UNKNOWN: "dim"
                    }.get(service.status, "white")
                    
                    uptime_str = f"{service.uptime:.0f}s" if service.uptime > 0 else "-"
                    pid_str = str(service.pid) if service.pid else "-"
                    auto_restart_str = "✓" if service.auto_restart else "✗"
                    
                    status_table.add_row(
                        service.name,
                        Text(status_text, style=status_color),
                        str(service.port),
                        pid_str,
                        uptime_str,
                        str(service.restart_count),
                        auto_restart_str
                    )
                
                layout["left"].update(Panel(
                    status_table,
                    title="📊 Service Status",
                    border_style="cyan",
                    box=ROUNDED
                ))
                
                # Enhanced metrics panel
                metrics_panel = Layout()
                metrics_panel.split_column(
                    Layout(name="summary", size=8),
                    Layout(name="profile", size=6),
                    Layout(name="stats", ratio=1)
                )
                
                # Summary metrics
                summary_table = Table.grid(padding=1)
                summary_table.add_column(style="white", width=15)
                summary_table.add_column(style="cyan", justify="right")
                
                running_count = sum(1 for s in self.services.values() if s.status == ServiceStatus.RUNNING)
                error_count = sum(1 for s in self.services.values() if s.status == ServiceStatus.ERROR)
                total_restarts = sum(s.restart_count for s in self.services.values())
                
                summary_table.add_row("🟢 Running", f"{running_count}/{len(self.services)}")
                summary_table.add_row("⚠️ Errors", str(error_count))
                summary_table.add_row("🔄 Restarts", str(total_restarts))
                
                metrics_panel["summary"].update(Panel(
                    summary_table,
                    title="📈 Summary",
                    border_style="green",
                    box=ROUNDED
                ))
                
                # Profile info
                profile_table = Table.grid(padding=1)
                profile_table.add_column(style="white", width=15)
                profile_table.add_column(style="yellow")
                
                profile_table.add_row("Profile", self.active_profile or "Default")
                profile_table.add_row("Services", str(len(self.services)))
                
                metrics_panel["profile"].update(Panel(
                    profile_table,
                    title="⚙️ Configuration",
                    border_style="yellow",
                    box=ROUNDED
                ))
                
                # Quick stats with progress bars
                stats_table = Table.grid(padding=1)
                stats_table.add_column(style="white", width=15)
                stats_table.add_column(style="white")
                
                # Health percentage
                health_percent = (running_count / len(self.services)) * 100
                health_bar = _create_progress_bar(health_percent)
                health_color = "green" if health_percent > 80 else "yellow" if health_percent > 50 else "red"
                stats_table.add_row("💚 Health", f"{health_percent:.0f}%")
                stats_table.add_row("", f"[{health_color}]{health_bar}[/{health_color}]")
                stats_table.add_row("", "")
                
                # Auto-restart enabled
                auto_restart_count = sum(1 for s in self.services.values() if s.auto_restart)
                stats_table.add_row("🔄 Auto-Restart", f"{auto_restart_count} services")
                
                metrics_panel["stats"].update(Panel(
                    stats_table,
                    title="📊 Statistics",
                    border_style="magenta",
                    box=ROUNDED
                ))
                
                layout["right"].update(metrics_panel)
                
                # Enhanced footer
                footer_text = Text()
                footer_text.append("🔄 ", style="green")
                footer_text.append("Live Monitoring Active", style="white")
                footer_text.append(" | ", style="dim")
                footer_text.append("⌨ ", style="cyan")
                footer_text.append("Press Ctrl+C to return to menu", style="dim")
                footer_text.append(" | ", style="dim")
                footer_text.append(f"🕐 {datetime.now().strftime('%H:%M:%S')}", style="dim")
                
                footer = Panel(
                    Align.center(footer_text),
                    box=HEAVY,
                    border_style="dim"
                )
                layout["footer"].update(footer)
                
                live.update(layout)
                await asyncio.sleep(1)

    async def system_health_check(self):
        """Perform enhanced system health check."""
        if self.console:
            self.console.print("\n[bold blue]=== Enhanced System Health Check ===[/bold blue]\n")
        
        health_results = {}
        
        # Check Docker
        try:
            result = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                if self.console:
                    self.console.print(f"✓ Docker installed: {result.stdout.strip()}", style="green")
                health_results["docker"] = True
            else:
                if self.console:
                    self.console.print("✗ Docker not found", style="red")
                health_results["docker"] = False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            if self.console:
                self.console.print("✗ Docker not found", style="red")
            health_results["docker"] = False
        
        # Check Python
        try:
            result = subprocess.run(["python3", "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                if self.console:
                    self.console.print(f"✓ Python3 installed: {result.stdout.strip()}", style="green")
                health_results["python"] = True
            else:
                if self.console:
                    self.console.print("✗ Python3 not found", style="red")
                health_results["python"] = False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            if self.console:
                self.console.print("✗ Python3 not found", style="red")
            health_results["python"] = False
        
        # Check Node.js
        try:
            result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                if self.console:
                    self.console.print(f"✓ Node.js installed: {result.stdout.strip()}", style="green")
                health_results["node"] = True
            else:
                if self.console:
                    self.console.print("✗ Node.js not found", style="red")
                health_results["node"] = False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            if self.console:
                self.console.print("✗ Node.js not found", style="red")
            health_results["node"] = False
        
        # Check Go
        try:
            result = subprocess.run(["go", "version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                if self.console:
                    self.console.print(f"✓ Go installed: {result.stdout.strip()}", style="green")
                health_results["go"] = True
            else:
                if self.console:
                    self.console.print("✗ Go not found", style="red")
                health_results["go"] = False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            if self.console:
                self.console.print("✗ Go not found", style="red")
            health_results["go"] = False
        
        # Check npm
        try:
            result = subprocess.run(["npm", "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                if self.console:
                    self.console.print(f"✓ npm installed: {result.stdout.strip()}", style="green")
                health_results["npm"] = True
            else:
                if self.console:
                    self.console.print("✗ npm not found", style="red")
                health_results["npm"] = False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            if self.console:
                self.console.print("✗ npm not found", style="red")
            health_results["npm"] = False
        
        # Check ports availability
        if self.console:
            self.console.print("\n[bold]Port Availability:[/bold]")
        
        for service_key, service in self.services.items():
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(('localhost', service.port))
                sock.close()
                if result == 0:
                    if self.console:
                        self.console.print(f"✗ Port {service.port} ({service.name}) is in use", style="red")
                    health_results[f"port_{service.port}"] = False
                else:
                    if self.console:
                        self.console.print(f"✓ Port {service.port} ({service.name}) is available", style="green")
                    health_results[f"port_{service.port}"] = True
            except Exception as e:
                if self.console:
                    self.console.print(f"? Port {service.port} ({service.name}) check failed: {e}", style="yellow")
                health_results[f"port_{service.port}"] = None
        
        # Overall health
        all_healthy = all(v is True for v in health_results.values())
        if self.console:
            self.console.print("\n" + "="*50)
            if all_healthy:
                self.console.print("✓ System is healthy", style="green")
            else:
                self.console.print("✗ System has issues that need attention", style="red")
            self.console.print("="*50 + "\n")
        
        return health_results

    def validate_configuration(self):
        """Validate system configuration."""
        if self.console:
            self.console.print("\n[bold blue]=== Configuration Validation ===[/bold blue]\n")
        
        issues = []
        
        # Check .env file
        env_file = os.path.join(self.root_dir, ".env")
        if not os.path.exists(env_file):
            issues.append(".env file not found")
            if self.console:
                self.console.print("✗ .env file not found", style="red")
        else:
            if self.console:
                self.console.print("✓ .env file exists", style="green")
            
            required_vars = [
                "SERVICE_API_KEY_ORCHESTRATOR",
                "SERVICE_API_KEY_ANALYZER",
                "SERVICE_API_KEY_MONITOR",
                "SERVICE_API_KEY_KNOWLEDGE_ENGINE",
                "OPENROUTER_API_KEY"
            ]
            
            with open(env_file) as f:
                env_content = f.read()
                
            for var in required_vars:
                if var in env_content and env_content.split(f"{var}=")[1].strip():
                    if self.console:
                        self.console.print(f"✓ {var} is set", style="green")
                else:
                    issues.append(f"{var} is not set or empty")
                    if self.console:
                        self.console.print(f"✗ {var} is not set or empty", style="red")
        
        # Check dataset file
        dataset_file = os.path.join(self.root_dir, "Attack_Dataset.csv")
        if not os.path.exists(dataset_file):
            issues.append("Attack_Dataset.csv not found")
            if self.console:
                self.console.print("✗ Attack_Dataset.csv not found", style="red")
        else:
            if self.console:
                self.console.print("✓ Attack_Dataset.csv exists", style="green")
        
        if self.console:
            self.console.print("\n" + "="*50)
            if not issues:
                self.console.print("✓ Configuration is valid", style="green")
            else:
                self.console.print(f"✗ Found {len(issues)} configuration issue(s):", style="red")
                for issue in issues:
                    if self.console:
                        self.console.print(f"  - {issue}", style="red")
            self.console.print("="*50 + "\n")
        
        return len(issues) == 0

    def handle_shortcut(self, shortcut: str) -> bool:
        """Handle keyboard shortcuts."""
        if shortcut not in self.shortcuts:
            return False
        
        action = self.shortcuts[shortcut]
        
        if action == 'quit':
            return True  # Signal to exit
        elif action == 'help':
            if self.console:
                self.console.print("\n[bold cyan]Help:[/bold cyan]")
                self.console.print("Use shortcuts or menu numbers for quick access")
                self.console.print("Profile-based starts provide optimized service configurations")
                self.console.print("Auto-restart can be enabled per-service for development\n")
        elif action == 'status':
            asyncio.run(self.monitor_services())
            if self.console:
                self.console.print(self.create_status_table())
        elif action == 'start_all':
            self.start_all_services()
        elif action == 'stop_all':
            self.stop_all_services()
        elif action == 'kill_all':
            if self.console:
                self.console.print("[bold red]WARNING: This will forcefully kill all services without graceful shutdown![/bold red]")
                if Confirm.ask("Are you sure you want to kill all services?"):
                    self.kill_all_services()
                else:
                    if self.console:
                        self.console.print("Kill operation cancelled.", style="yellow")
            else:
                self.kill_all_services()
        elif action == 'monitor':
            try:
                asyncio.run(self.live_monitor())
            except KeyboardInterrupt:
                self.monitoring = False
                if self.console:
                    self.console.print("\nMonitoring stopped")
        elif action == 'logs':
            self.show_service_list()
            service = input("Enter service name: ").strip()
            self.show_logs(service)
        elif action == 'profiles':
            self.select_profile()
        elif action == 'restart':
            self.show_service_list()
            service = input("Enter service name: ").strip()
            self.toggle_auto_restart(service)
        
        return False

    def run(self):
        """Run the enhanced main menu loop."""
        while True:
            self.show_enhanced_menu()
            
            try:
                choice = input("\nEnter choice: ").strip().lower()
                
                # Handle shortcuts
                if len(choice) == 1 and choice in self.shortcuts:
                    should_exit = self.handle_shortcut(choice)
                    if should_exit:
                        break
                    input("\nPress Enter to continue...")
                    continue
                
                # Handle menu choices
                if choice == "1" or choice == "a":
                    self.start_all_services()
                elif choice == "2" or choice == "x":
                    self.stop_all_services()
                elif choice == "3" or choice == "k":
                    if self.console:
                        self.console.print("[bold red]WARNING: This will forcefully kill all services without graceful shutdown![/bold red]")
                        confirm = input("Are you sure you want to kill all services? (y/N): ").strip().lower()
                        if confirm == 'y':
                            self.kill_all_services()
                        else:
                            if self.console:
                                self.console.print("Kill operation cancelled.", style="yellow")
                    else:
                        self.kill_all_services()
                elif choice == "4":
                    self.show_service_list()
                    service = input("Enter service name: ").strip()
                    self.start_service(service)
                elif choice == "5":
                    self.show_service_list()
                    service = input("Enter service name: ").strip()
                    self.stop_service(service)
                elif choice == "6" or choice == "s":
                    asyncio.run(self.monitor_services())
                    self.show_enhanced_menu()
                    if RICH_AVAILABLE:
                        self.console.print(self.create_status_table())
                elif choice == "7" or choice == "m":
                    try:
                        asyncio.run(self.live_monitor())
                    except KeyboardInterrupt:
                        self.monitoring = False
                        if self.console:
                            self.console.print("\nMonitoring stopped")
                elif choice == "8" or choice == "l":
                    self.show_service_list()
                    service = input("Enter service name: ").strip()
                    self.show_logs(service)
                elif choice == "9":
                    asyncio.run(self.system_health_check())
                elif choice == "10":
                    self.validate_configuration()
                elif choice == "11" or choice == "p":
                    self.select_profile()
                elif choice == "12" or choice == "r":
                    self.show_service_list()
                    service = input("Enter service name: ").strip()
                    self.toggle_auto_restart(service)
                elif choice == "13":
                    self.show_service_list()
                    service = input("Enter service name: ").strip()
                    self.show_historical_metrics(service)
                elif choice == "14" or choice == "c":
                    if self.console:
                        self.console.print("Configuration editor - Coming soon!", style="yellow")
                elif choice == "0" or choice == "q":
                    if self.console:
                        self.console.print("\nExiting OpsecAI...")
                    self.stop_all_services()
                    self._save_state()
                    break
                else:
                    if self.console:
                        self.console.print("Invalid choice. Please try again.", style="red")
                
                input("\nPress Enter to continue...")
                
            except KeyboardInterrupt:
                if self.console:
                    self.console.print("\n\nExiting OpsecAI...")
                self.stop_all_services()
                self._save_state()
                break
            except Exception as e:
                if self.console:
                    self.console.print(f"Error: {e}", style="red")
                input("\nPress Enter to continue...")

def main():
    """Main entry point."""
    print("""
╔════════════════════════════════════════════════════════════╗
║                                                              ║
║          OpsecAI - Enhanced Pentesting Automation            ║
║                                                              ║
║          Advanced Startup & Service Management               ║
║                                                              ║
╚════════════════════════════════════════════════════════════╝
""")
    
    manager = OpsecStartupManagerEnhanced()
    manager.run()

if __name__ == "__main__":
    main()