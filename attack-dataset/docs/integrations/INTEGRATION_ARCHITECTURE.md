# Integration System Technical Architecture

**Version:** 1.0  
**Date:** 2026-05-15  
**Related:** `../../INTEGRATIONS_BLUEPRINT.md`

---

## System Overview

The Integration System is a microservice that provides a plugin architecture for extending OpsecAI with external tools, APIs, and services. It runs on port 8500 and integrates with the existing service mesh using the established service authentication patterns.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OpsecAI Service Mesh                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Orchestr   │  │   Knowledge  │  │    OpSec     │  │   Analyzer   │    │
│  │   :3001      │  │   Engine     │  │   Monitor    │  │   :8001      │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │            │
│         └─────────────────┴─────────────────┴─────────────────┘            │
│                                   │                                           │
│                                   ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      Integration Hub :8500                             │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │                    FastAPI Application                          │  │   │
│  │  │  - REST API endpoints                                          │  │   │
│  │  │  - WebSocket server                                             │  │   │
│  │  │  - Service authentication middleware                           │  │   │
│  │  │  - Structured logging                                           │  │   │
│  │  │  - Health checks                                                │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │                  Plugin Manager                                 │  │   │
│  │  │  - Plugin discovery & loading                                  │  │   │
│  │  │  - Lifecycle management                                         │  │   │
│  │  │  - Dependency resolution                                        │  │   │
│  │  │  - Health monitoring                                             │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │                 Execution Engine                               │  │   │
│  │  │  - Local Binary Executor (Docker)                               │  │   │
│  │  │  - Remote API Executor (aiohttp)                                │  │   │
│  │  │  - Execution Queue (Redis)                                      │  │   │
│  │  │  - Result aggregation                                           │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │              Configuration Manager                              │  │   │
│  │  │  - YAML/JSON parsing                                             │  │   │
│  │  │  - Environment substitution                                      │  │   │
│  │  │  - Schema validation                                            │  │   │
│  │  │  - Secrets integration (Vault)                                   │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │             OpSec Assessment Layer                              │  │   │
│  │  │  - Risk scoring engine                                           │  │   │
│  │  │  - Detection method mapping                                     │  │   │
│  │  │  - Evasion recommendation generator                              │  │   │
│  │  │  - OpSec Monitor integration                                     │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │               Event & Webhook System                            │  │   │
│  │  │  - Event publisher (Redis Pub/Sub)                              │  │   │
│  │  │  - Webhook delivery with retry                                   │  │   │
│  │  │  - Event filtering                                               │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                   │                                           │
│         ┌─────────────────────────┼─────────────────────────┐              │
│         │                         │                         │              │
│  ┌──────▼──────────┐    ┌────────▼────────┐    ┌─────────▼─────────┐    │
│  │  PostgreSQL      │    │     Redis        │    │   Docker Daemon    │    │
│  │  (plugin configs)│    │  (queue & cache) │    │  (sandbox exec)    │    │
│  └──────────────────┘    └─────────────────┘    └───────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
backend/integrations/
├── main.py                          # FastAPI application entry point
├── config.py                        # Configuration management
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Docker image build
├── plugin_system/
│   ├── __init__.py
│   ├── base.py                      # Base plugin classes
│   ├── manager.py                   # Plugin manager
│   ├── loader.py                    # Plugin loader
│   ├── registry.py                  # Plugin registry
│   ├── lifecycle.py                 # Lifecycle management
│   └── types.py                     # Type definitions
├── execution/
│   ├── __init__.py
│   ├── local.py                     # Local binary executor
│   ├── remote.py                    # Remote API executor
│   ├── queue.py                     # Execution queue
│   └── sandbox.py                   # Sandbox management
├── config/
│   ├── __init__.py
│   ├── manager.py                   # Configuration manager
│   ├── schema.py                    # Configuration schemas
│   └── validator.py                 # Configuration validator
├── opsec/
│   ├── __init__.py
│   ├── assessor.py                  # OpSec assessor
│   ├── scorer.py                    # Risk scoring engine
│   └── mapper.py                    # Detection method mapper
├── events/
│   ├── __init__.py
│   ├── publisher.py                 # Event publisher
│   ├── webhook.py                   # Webhook delivery
│   └── filters.py                   # Event filters
├── api/
│   ├── __init__.py
│   ├── routes.py                    # API route definitions
│   ├── websocket.py                 # WebSocket handlers
│   └── middleware.py                # API middleware
├── integrations/
│   ├── security/
│   │   ├── metasploit/
│   │   │   ├── plugin.yaml          # Plugin configuration
│   │   │   └── plugin.py            # Plugin implementation
│   │   ├── sliver/
│   │   ├── havoc/
│   │   ├── nmap/
│   │   └── ...
│   ├── threat_intel/
│   ├── cloud/
│   └── ...
├── tests/
│   ├── unit/
│   ├── integration/
│   └── sandbox/
└── docs/
    ├── api.md
    ├── plugin_development.md
    └── sdk_reference.md
```

---

## Core Components

### 1. Plugin Manager

**File**: `plugin_system/manager.py`

```python
from typing import Dict, Optional, List
import asyncio
import logging
from .loader import PluginLoader
from .registry import PluginRegistry
from .lifecycle import LifecycleManager
from .base import BasePlugin, ExecutionContext, ExecutionResult

logger = logging.getLogger(__name__)

class PluginManager:
    """Manages plugin lifecycle and execution."""
    
    def __init__(self):
        self.loader = PluginLoader()
        self.registry = PluginRegistry()
        self.lifecycle = LifecycleManager()
        self._plugins: Dict[str, BasePlugin] = {}
    
    async def initialize(self):
        """Initialize plugin manager."""
        await self.registry.initialize()
        await self.loader.discover_plugins()
        
        # Load all discovered plugins
        for plugin_name in self.loader.list_plugins():
            await self.load_plugin(plugin_name)
    
    async def load_plugin(self, plugin_name: str) -> BasePlugin:
        """Load and initialize a plugin."""
        if plugin_name in self._plugins:
            return self._plugins[plugin_name]
        
        # Load plugin configuration
        config = await self.loader.load_config(plugin_name)
        
        # Instantiate plugin
        plugin_class = await self.loader.load_plugin_class(plugin_name)
        plugin = plugin_class(config)
        
        # Initialize plugin
        await plugin.initialize()
        
        # Register plugin
        self._plugins[plugin_name] = plugin
        await self.registry.register(plugin_name, config)
        
        logger.info(f"Plugin loaded: {plugin_name}")
        return plugin
    
    async def unload_plugin(self, plugin_name: str):
        """Unload and cleanup a plugin."""
        if plugin_name in self._plugins:
            plugin = self._plugins[plugin_name]
            await plugin.cleanup()
            del self._plugins[plugin_name]
            await self.registry.unregister(plugin_name)
            logger.info(f"Plugin unloaded: {plugin_name}")
    
    async def execute(
        self,
        plugin_name: str,
        context: ExecutionContext
    ) -> ExecutionResult:
        """Execute a plugin with given context."""
        plugin = await self.get_plugin(plugin_name)
        
        # Validate input
        await plugin.validate_input(context.parameters)
        
        # Execute with lifecycle hooks
        result = await self.lifecycle.execute_with_hooks(plugin, context)
        
        return result
    
    async def get_plugin(self, plugin_name: str) -> BasePlugin:
        """Get a loaded plugin, load if necessary."""
        if plugin_name not in self._plugins:
            return await self.load_plugin(plugin_name)
        return self._plugins[plugin_name]
    
    async def list_plugins(self) -> List[Dict]:
        """List all available plugins."""
        return await self.registry.list_plugins()
    
    async def get_plugin_info(self, plugin_name: str) -> Dict:
        """Get plugin information."""
        return await self.registry.get_plugin_info(plugin_name)
    
    async def health_check(self, plugin_name: str) -> Dict:
        """Check plugin health."""
        plugin = await self.get_plugin(plugin_name)
        return await plugin.health_check()
    
    async def shutdown(self):
        """Shutdown plugin manager."""
        for plugin_name in list(self._plugins.keys()):
            await self.unload_plugin(plugin_name)
```

### 2. Execution Engine

**File**: `execution/queue.py`

```python
import asyncio
import logging
from typing import Dict, Optional
from dataclasses import dataclass
import redis.asyncio as redis
from ..plugin_system.base import ExecutionContext, ExecutionResult

logger = logging.getLogger(__name__)

@dataclass
class ExecutionTask:
    """Execution task for the queue."""
    execution_id: str
    plugin_name: str
    context: ExecutionContext
    priority: int = 5  # 1-10, 10 is highest
    
class ExecutionQueue:
    """Async execution queue with priority support."""
    
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        self._queues: Dict[int, asyncio.Queue] = {
            i: asyncio.Queue() for i in range(1, 11)
        }
        self._running = False
        self._workers = []
    
    async def initialize(self, num_workers: int = 4):
        """Initialize execution queue with workers."""
        self._running = True
        
        # Start workers for each priority level
        for i in range(num_workers):
            worker = asyncio.create_task(self._worker())
            self._workers.append(worker)
        
        logger.info(f"Execution queue initialized with {num_workers} workers")
    
    async def submit(self, task: ExecutionTask) -> str:
        """Submit task to execution queue."""
        queue = self._queues[task.priority]
        await queue.put(task)
        
        # Store task metadata in Redis
        await self.redis.hset(
            f"execution:{task.execution_id}",
            mapping={
                "plugin_name": task.plugin_name,
                "status": "queued",
                "priority": task.priority
            }
        )
        
        logger.info(f"Task submitted: {task.execution_id}")
        return task.execution_id
    
    async def _worker(self):
        """Worker process for executing tasks."""
        while self._running:
            # Check all priority queues (highest first)
            task = None
            for priority in range(10, 0, -1):
                queue = self._queues[priority]
                if not queue.empty():
                    task = await queue.get()
                    break
            
            if task is None:
                await asyncio.sleep(0.1)
                continue
            
            try:
                # Update status
                await self.redis.hset(
                    f"execution:{task.execution_id}",
                    "status",
                    "running"
                )
                
                # Execute task (delegated to PluginManager)
                result = await self._execute_task(task)
                
                # Store result
                await self.redis.hset(
                    f"execution:{task.execution_id}",
                    mapping={
                        "status": "completed" if result.success else "failed",
                        "result": result.to_json()
                    }
                )
                
            except Exception as e:
                logger.error(f"Task execution failed: {e}")
                await self.redis.hset(
                    f"execution:{task.execution_id}",
                    mapping={
                        "status": "error",
                        "error": str(e)
                    }
                )
    
    async def _execute_task(self, task: ExecutionTask) -> ExecutionResult:
        """Execute task (delegated to PluginManager)."""
        # This would be injected from PluginManager
        from ..plugin_system.manager import plugin_manager
        
        return await plugin_manager.execute(
            task.plugin_name,
            task.context
        )
    
    async def get_status(self, execution_id: str) -> Dict:
        """Get execution status."""
        data = await self.redis.hgetall(f"execution:{execution_id}")
        return {
            "execution_id": execution_id,
            "status": data.get("status", "unknown"),
            "plugin_name": data.get("plugin_name"),
            "result": data.get("result"),
            "error": data.get("error")
        }
    
    async def shutdown(self):
        """Shutdown execution queue."""
        self._running = False
        
        for worker in self._workers:
            worker.cancel()
        
        await asyncio.gather(*self._workers, return_exceptions=True)
        await self.redis.close()
        
        logger.info("Execution queue shutdown complete")
```

### 3. Configuration Manager

**File**: `config/manager.py`

```python
import yaml
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from .schema import PluginConfigSchema
import hvac  # HashiCorp Vault client

logger = logging.getLogger(__name__)

class ConfigurationManager:
    """Manages plugin configuration with secret resolution."""
    
    def __init__(
        self,
        config_dir: str = "integrations",
        vault_url: Optional[str] = None,
        vault_token: Optional[str] = None
    ):
        self.config_dir = Path(config_dir)
        self.vault_url = vault_url
        self.vault_client = None
        
        if vault_url and vault_token:
            self.vault_client = hvac.Client(
                url=vault_url,
                token=vault_token
            )
    
    async def load_plugin_config(self, plugin_name: str) -> PluginConfigSchema:
        """Load and validate plugin configuration with secret resolution."""
        config_path = self.config_dir / plugin_name / "plugin.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Plugin config not found: {config_path}")
        
        with open(config_path, 'r') as f:
            raw_config = yaml.safe_load(f)
        
        # Substitute environment variables
        raw_config = self._substitute_env_vars(raw_config)
        
        # Resolve secrets from Vault
        if self.vault_client:
            raw_config = await self._resolve_secrets(raw_config)
        
        # Validate against schema
        config = PluginConfigSchema(**raw_config)
        
        logger.info(f"Loaded plugin config: {plugin_name}")
        return config
    
    def _substitute_env_vars(self, config: Any) -> Any:
        """Substitute environment variables in configuration."""
        if isinstance(config, dict):
            return {k: self._substitute_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._substitute_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith('${') and config.endswith('}'):
            env_var = config[2:-1]
            return os.getenv(env_var, config)
        else:
            return config
    
    async def _resolve_secrets(self, config: Any) -> Any:
        """Resolve secrets from Vault."""
        if isinstance(config, dict):
            result = {}
            for k, v in config.items():
                if k == 'vault_secret':
                    result.update(await self._get_vault_secret(v))
                else:
                    result[k] = await self._resolve_secrets(v)
            return result
        elif isinstance(config, list):
            return [await self._resolve_secrets(item) for item in config]
        else:
            return config
    
    async def _get_vault_secret(self, secret_path: str) -> Dict[str, Any]:
        """Get secret from Vault."""
        try:
            response = self.vault_client.secrets.kv.v2.read_secret_version(
                path=secret_path
            )
            return response['data']['data']
        except Exception as e:
            logger.error(f"Failed to get secret from Vault: {e}")
            return {}
```

### 4. OpSec Assessment Layer

**File**: `opsec/assessor.py`

```python
from typing import Dict, Any, Optional
import logging
from ..plugin_system.base import BasePlugin, ExecutionResult

logger = logging.getLogger(__name__)

class OpSecAssessor:
    """Assesses OpSec implications of plugin executions."""
    
    def __init__(self):
        self.risk_scorer = RiskScorer()
        self.detection_mapper = DetectionMethodMapper()
        self.evasion_generator = EvasionRecommendationGenerator()
    
    async def assess_execution(
        self,
        plugin: BasePlugin,
        result: ExecutionResult,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess OpSec implications of an execution."""
        if not plugin.config.opsec or not plugin.config.opsec.enabled:
            return None
        
        # Get plugin OpSec configuration
        opsec_config = plugin.config.opsec
        
        # Calculate risk score
        risk_score = await self.risk_scorer.calculate_score(
            plugin.config.name,
            result,
            context
        )
        
        # Map detection methods
        detection_methods = await self.detection_mapper.map_methods(
            plugin.config.name,
            result
        )
        
        # Generate evasion recommendations
        evasion_recommendations = await self.evasion_generator.generate(
            plugin.config.name,
            risk_score,
            detection_methods
        )
        
        return {
            'integration': plugin.config.name,
            'risk_level': opsec_config.risk_level,
            'calculated_risk_score': risk_score,
            'noise_level': opsec_config.noise_level,
            'detection_methods': detection_methods,
            'evasion_recommendations': evasion_recommendations,
            'execution_success': result.success,
            'target': context.get('target'),
            'timestamp': context.get('timestamp')
        }
    
    async def integrate_with_opsec_monitor(
        self,
        opsec_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send OpSec context to OpSec Monitor for assessment."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'http://opsec-monitor:8002/assess/integration',
                    json=opsec_context,
                    headers={'X-Service-Auth': 'true'}
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"OpSec Monitor returned {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Failed to integrate with OpSec Monitor: {e}")
            return None

class RiskScorer:
    """Calculates risk scores for plugin executions."""
    
    async def calculate_score(
        self,
        plugin_name: str,
        result: ExecutionResult,
        context: Dict[str, Any]
    ) -> float:
        """Calculate risk score (0-100)."""
        base_risk = self._get_base_risk(plugin_name)
        
        # Adjust based on execution context
        risk_adjustment = 0.0
        
        if result.success:
            risk_adjustment += 20.0  # Successful execution increases risk
        
        if context.get('target_type') == 'production':
            risk_adjustment += 30.0  # Production targets increase risk
        
        if context.get('aggression_level', 5) > 7:
            risk_adjustment += 15.0  # High aggression increases risk
        
        final_risk = min(100.0, base_risk + risk_adjustment)
        return final_risk
    
    def _get_base_risk(self, plugin_name: str) -> float:
        """Get base risk score for plugin."""
        risk_map = {
            'metasploit': 80.0,
            'sliver': 75.0,
            'havoc': 70.0,
            'nmap': 40.0,
            'masscan': 60.0,
            'sqlmap': 65.0,
            'burpsuite': 50.0
        }
        return risk_map.get(plugin_name, 50.0)

class DetectionMethodMapper:
    """Maps detection methods for plugin executions."""
    
    async def map_methods(
        self,
        plugin_name: str,
        result: ExecutionResult
    ) -> list:
        """Map detection methods based on plugin and execution."""
        method_map = {
            'metasploit': [
                'AV/EDR signature detection',
                'C2 beacon patterns',
                'Network anomalies',
                'Process injection'
            ],
            'nmap': [
                'IDS/IPS signature detection',
                'Firewall logs',
                'Netflow anomalies',
                'Port scan detection'
            ],
            'masscan': [
                'Massive connection attempts',
                'SYN flood detection',
                'ISP abuse reports'
            ]
        }
        
        return method_map.get(plugin_name, ['Generic detection'])

class EvasionRecommendationGenerator:
    """Generates evasion recommendations."""
    
    async def generate(
        self,
        plugin_name: str,
        risk_score: float,
        detection_methods: list
    ) -> list:
        """Generate context-aware evasion recommendations."""
        recommendations = []
        
        # Base recommendations for high risk
        if risk_score > 70:
            recommendations.append("Consider using stealth variants")
            recommendations.append("Implement timing randomization")
            recommendations.append("Use decoy infrastructure")
        
        # Method-specific recommendations
        for method in detection_methods:
            if 'C2 beacon' in method:
                recommendations.append("Customize C2 profiles and beacons")
            elif 'signature' in method:
                recommendations.append("Use custom payloads and encoding")
            elif 'network' in method:
                recommendations.append("Implement traffic obfuscation")
        
        return recommendations
```

---

## API Implementation Details

### FastAPI Application Structure

**File**: `main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys
import os

# Add shared directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

from .config import settings
from .api.routes import router as api_router
from .api.websocket import router as ws_router
from .api.middleware import setup_middleware
from shared.logging_config import setup_logging
from shared.health import setup_health_endpoints
from shared.config_validation import validate_config

# Setup logging
setup_logging(
    service_name="integration-hub",
    environment=settings.ENVIRONMENT,
    log_level=settings.LOG_LEVEL
)

logger = logging.getLogger(__name__)

# Validate configuration
validate_config()

# Create FastAPI app
app = FastAPI(
    title="OpsecAI Integration Hub",
    description="Plugin architecture for external tool and API integrations",
    version="1.0.0"
)

# Setup middleware
setup_middleware(app)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include routers
app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/ws")

# Setup health endpoints
setup_health_endpoints(
    app,
    service_name="integration-hub",
    version="1.0.0"
)

@app.on_event("startup")
async def startup():
    """Initialize integration hub."""
    logger.info("Starting Integration Hub...")
    
    # Initialize plugin manager
    from .plugin_system.manager import PluginManager
    app.state.plugin_manager = PluginManager()
    await app.state.plugin_manager.initialize()
    
    # Initialize execution queue
    from .execution.queue import ExecutionQueue
    app.state.execution_queue = ExecutionQueue(settings.REDIS_URL)
    await app.state.execution_queue.initialize()
    
    logger.info("Integration Hub started successfully")

@app.on_event("shutdown")
async def shutdown():
    """Shutdown integration hub."""
    logger.info("Shutting down Integration Hub...")
    
    await app.state.plugin_manager.shutdown()
    await app.state.execution_queue.shutdown()
    
    logger.info("Integration Hub shutdown complete")
```

### API Routes Implementation

**File**: `api/routes.py`

```python
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional
from ..plugin_system.base import ExecutionContext
from ..plugin_system.manager import PluginManager
from ..execution.queue import ExecutionTask, ExecutionQueue

router = APIRouter()

@router.get("/plugins")
async def list_plugins(
    plugin_manager: PluginManager = Depends(lambda: router.app.state.plugin_manager)
):
    """List all available plugins."""
    return await plugin_manager.list_plugins()

@router.get("/plugins/{plugin_name}")
async def get_plugin_info(
    plugin_name: str,
    plugin_manager: PluginManager = Depends(lambda: router.app.state.plugin_manager)
):
    """Get plugin information."""
    try:
        return await plugin_manager.get_plugin_info(plugin_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/execute")
async def execute_plugin(
    plugin_name: str,
    target: str,
    parameters: dict,
    engagement_id: Optional[str] = None,
    timeout: int = 300,
    enable_opsec: bool = True,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    plugin_manager: PluginManager = Depends(lambda: router.app.state.plugin_manager),
    execution_queue: ExecutionQueue = Depends(lambda: router.app.state.execution_queue)
):
    """Execute a plugin."""
    import uuid
    
    # Create execution context
    execution_id = f"exec_{uuid.uuid4().hex[:8]}"
    context = ExecutionContext(
        integration_id=execution_id,
        engagement_id=engagement_id or f"eng_{uuid.uuid4().hex[:8]}",
        target=target,
        parameters=parameters,
        timeout=timeout,
        metadata={
            "enable_opsec": enable_opsec,
            "timestamp": datetime.utcnow().isoformat()
        }
    )
    
    # Submit to execution queue
    task = ExecutionTask(
        execution_id=execution_id,
        plugin_name=plugin_name,
        context=context,
        priority=5
    )
    
    await execution_queue.submit(task)
    
    return {
        "execution_id": execution_id,
        "status": "queued",
        "message": "Execution queued successfully"
    }

@router.get("/executions/{execution_id}")
async def get_execution_status(
    execution_id: str,
    execution_queue: ExecutionQueue = Depends(lambda: router.app.state.execution_queue)
):
    """Get execution status."""
    return await execution_queue.get_status(execution_id)
```

---

## Docker Integration

### Dockerfile

**File**: `Dockerfile`

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create integrations directory
RUN mkdir -p integrations

# Expose port
EXPOSE 8500

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8500"]
```

### Docker Compose Integration

**Add to existing docker-compose.yml**:

```yaml
# Integration Hub
integration-hub:
  build:
    context: ./backend/integrations
    dockerfile: Dockerfile
  ports:
    - "8500:8500"
  environment:
    - POSTGRES_DSN=postgresql://opsec:opsec@postgres:5432/attack_db
    - REDIS_URL=redis://redis:6379
    - VAULT_URL=http://vault:8200
    - SERVICE_API_KEY_INTEGRATION_HUB=${SERVICE_API_KEY_INTEGRATION_HUB}
  volumes:
    - ./integrations:/app/integrations
    - /var/run/docker.sock:/var/run/docker.sock  # For Docker-in-Docker
  depends_on:
    - postgres
    - redis
  cap_add:
    - NET_ADMIN
    - SYS_ADMIN
```

---

## Environment Variables

Add to `.env.example`:

```bash
# Integration Hub
INTEGRATION_HUB_PORT=8500
INTEGRATION_HUB_HOST=0.0.0.0

# Service Authentication
SERVICE_API_KEY_INTEGRATION_HUB=your-integration-hub-api-key

# Configuration
INTEGRATION_CONFIG_DIR=integrations
INTEGRATION_PLUGIN_DIR=integrations

# Redis (for execution queue)
REDIS_URL=redis://localhost:6379

# Vault (for secrets)
VAULT_URL=http://localhost:8200
VAULT_TOKEN=your-vault-token

# Docker (for sandboxed execution)
DOCKER_HOST=unix:///var/run/docker.sock

# OpSec Integration
OPSEC_MONITOR_URL=http://localhost:8002
OPSEC_ASSESSMENT_ENABLED=true
```

---

## Testing Strategy

### Unit Tests

```python
# tests/plugin_system/test_manager.py
import pytest
from integrations.plugin_system.manager import PluginManager

@pytest.fixture
async def plugin_manager():
    manager = PluginManager()
    await manager.initialize()
    yield manager
    await manager.shutdown()

@pytest.mark.asyncio
async def test_load_plugin(plugin_manager):
    plugin = await plugin_manager.load_plugin('nmap')
    assert plugin is not None
    assert plugin.config.name == 'nmap'

@pytest.mark.asyncio
async def test_execute_plugin(plugin_manager):
    context = ExecutionContext(
        integration_id='test',
        engagement_id='test-engagement',
        target='127.0.0.1',
        parameters={'ports': '80,443'},
        timeout=30,
        metadata={}
    )
    
    result = await plugin_manager.execute('nmap', context)
    assert result.success is True
```

### Integration Tests

```python
# tests/integration/test_api.py
import pytest
from httpx import AsyncClient
from main import app

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_list_plugins(client):
    response = await client.get("/api/v1/plugins")
    assert response.status_code == 200
    data = response.json()
    assert 'plugins' in data
    assert len(data['plugins']) > 0

@pytest.mark.asyncio
async def test_execute_plugin(client):
    response = await client.post(
        "/api/v1/execute",
        json={
            "plugin_name": "nmap",
            "target": "127.0.0.1",
            "parameters": {"ports": "80"},
            "timeout": 30
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert 'execution_id' in data
```

---

## Performance Optimization

### Caching Strategy

```python
# config/manager.py
import asyncio
from functools import lru_cache

class ConfigurationManager:
    def __init__(self):
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
    
    async def load_plugin_config(self, plugin_name: str) -> PluginConfigSchema:
        cache_key = f"config:{plugin_name}"
        
        # Check cache
        if cache_key in self._cache:
            cached, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return cached
        
        # Load configuration
        config = await self._load_from_file(plugin_name)
        
        # Cache result
        self._cache[cache_key] = (config, time.time())
        
        return config
```

### Connection Pooling

```python
# execution/remote.py
import aiohttp

class RemoteAPIExecutor:
    def __init__(self):
        self.connector = aiohttp.TCPConnector(
            limit=100,  # Max connections
            limit_per_host=20,  # Max per host
            ttl_dns_cache=300
        )
        self.session = None
    
    async def initialize(self):
        self.session = aiohttp.ClientSession(
            connector=self.connector
        )
```

---

## Security Implementation

### Service Authentication

```python
# api/middleware.py
from fastapi import Request, HTTPException
from shared.auth import verify_service_api_key

async def service_auth_middleware(request: Request, call_next):
    """Verify service-to-service authentication."""
    if request.url.path.startswith("/api/v1"):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(status_code=401, detail="Missing Authorization header")
        
        api_key = auth_header.replace("Bearer ", "")
        service_name = verify_service_api_key(api_key)
        
        if not service_name:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        request.state.service_name = service_name
    
    response = await call_next(request)
    return response
```

### Input Validation

```python
# api/routes.py
from pydantic import BaseModel, Field, validator

class ExecuteRequest(BaseModel):
    plugin_name: str = Field(..., regex="^[a-z0-9_]+$")
    target: str = Field(..., regex="^[a-zA-Z0-9.-]+$")
    parameters: dict = Field(default_factory=dict)
    engagement_id: Optional[str] = None
    timeout: int = Field(default=300, ge=1, le=3600)
    enable_opsec: bool = True
    
    @validator('target')
    def validate_target(cls, v):
        # Additional target validation
        if not is_valid_target(v):
            raise ValueError("Invalid target format")
        return v
```

---

## Monitoring & Observability

### Metrics Collection

```python
# plugin_system/manager.py
from prometheus_client import Counter, Histogram, Gauge

# Metrics
plugin_executions_total = Counter(
    'plugin_executions_total',
    'Total plugin executions',
    ['plugin_name', 'status']
)

plugin_execution_duration = Histogram(
    'plugin_execution_duration_seconds',
    'Plugin execution duration',
    ['plugin_name']
)

plugin_health_status = Gauge(
    'plugin_health_status',
    'Plugin health status (1=healthy, 0=unhealthy)',
    ['plugin_name']
)

class PluginManager:
    async def execute(self, plugin_name: str, context: ExecutionContext) -> ExecutionResult:
        start_time = time.time()
        
        try:
            result = await self._execute_internal(plugin_name, context)
            
            # Record metrics
            plugin_executions_total.labels(
                plugin_name=plugin_name,
                status='success' if result.success else 'failure'
            ).inc()
            
            plugin_execution_duration.labels(
                plugin_name=plugin_name
            ).observe(time.time() - start_time)
            
            return result
        except Exception as e:
            plugin_executions_total.labels(
                plugin_name=plugin_name,
                status='error'
            ).inc()
            raise
```

---

## Conclusion

This technical architecture provides the implementation details for the Integration Hub service. The design follows the established patterns in the OpsecAI codebase while introducing new capabilities for plugin management, execution, and OpSec integration.

The architecture prioritizes:
- **Security**: Sandboxed execution, service authentication, input validation
- **Performance**: Async execution, connection pooling, caching
- **Extensibility**: Plugin system, configuration management, event hooks
- **Reliability**: Error handling, health checks, graceful degradation
- **Observability**: Metrics, logging, tracing

Implementation should follow the phased approach outlined in the main blueprint, starting with core infrastructure and progressively adding integrations and advanced features.