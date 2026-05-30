# Jailbreak AI Integration

A plugin for the OpsecAI Integration Hub that provides access to the jail-break.chat API for chat completions, penetration testing analysis, and offensive test orchestration.

## Overview

This integration connects to the [jail-break.chat](https://jail-break.chat) API, which provides an OpenAI-compatible interface for uncensored LLM interactions. The plugin supports:
- Standard chat completions (sync and streaming)
- **Model management** - List available models, get model info, count tokens
- **AI-powered scan analysis** - Analyze nmap/port scan results to identify vulnerabilities
- **Attack plan generation** - Create comprehensive, phased penetration test plans
- **Offensive test initiation** - Orchestrate actual penetration tests via the integration hub
- **Enhanced automation** - Multi-target operations, continuous monitoring, adaptive replanning (NEW!)

## API Capabilities (Based on Official Documentation)

### OpenAI-Compatible Endpoints
The Jailbreak AI API implements standard OpenAI-compatible endpoints:

- **GET /v1/models** - List available AI models
- **POST /v1/chat/completions** - Chat completions (sync and streaming)
- **Model Management** - Query available models and their capabilities

### Additional Features
According to the official documentation, Jailbreak AI also provides:
- **28 live-data JailBreakOSINT agents** - Phone lookup, email breach, username search, dark web scan, CVE lookup
- **Uncensored AI image generation** - Text-to-image, image-to-image, 4× upscaling
- **Uncensored AI video generation**
- **Live web search** for real-time information
- **Browser Automation Agent** for pentesting
- **Enterprise AI Builder** - Build web apps, scrapers, or bots
- **AI Memory** - Remembers facts across conversations
- **Custom AI Personas** - DAN, HackerGPT, and more

## Enhanced Automation (NEW!)

The jailbreak_ai integration now includes advanced automation capabilities:

### 🚀 New Features
- **Multi-Target Automation** - Execute simultaneous operations against multiple targets
- **Continuous Monitoring** - Persistent surveillance with automated change detection
- **Adaptive Replanning** - AI-driven alternative approaches when steps fail
- **Intelligent Timing** - Smart delays and evasion based on configurable levels
- **State Persistence** - Save and resume long-running operations
- **Parallel Execution** - Run concurrent tasks with configurable limits

📖 **See [ENHANCED_AUTOMATION.md](./ENHANCED_AUTOMATION.md) for complete documentation on new features.**

### Dedicated API Endpoints

The Integration Hub now provides dedicated REST API endpoints for enhanced automation features:

**Base URL:** `http://localhost:8500/api/v1/automation`

- **POST /multi-target** - Start multi-target operations
- **POST /monitoring/start** - Start continuous monitoring
- **POST /replanning** - Execute adaptive replanning
- **POST /operation/control** - Control operations (pause/resume/abort)
- **POST /monitoring/control** - Control monitoring sessions
- **GET /operations** - List active operations
- **GET /monitoring/sessions** - List monitoring sessions

See the [ENHANCED_AUTOMATION.md](./ENHANCED_AUTOMATION.md) for detailed API documentation and examples.

## Configuration

Add the following to your `.env` file:

```bash
JAILBREAK_API_KEY=your-api-key-here
```

The plugin reads this from the environment variable and uses it for Bearer token authentication.

## API Usage

### 0. Model Management Operations (NEW!)

#### List Available Models
**Endpoint:** `POST /integrations/execute`

**Request:**
```json
{
  "plugin_name": "jailbreak_ai",
  "engagement_id": "eng_123",
  "target": "model_management",
  "parameters": {
    "operation": "list_models"
  },
  "timeout": 30
}
```

**Response:**
```json
{
  "success": true,
  "output": {
    "models": [
      {
        "id": "jailbreak-ai",
        "object": "model",
        "created": 1700000000,
        "owned_by": "jail-break.chat"
      }
    ],
    "count": 1,
    "available_model_ids": ["jailbreak-ai"]
  }
}
```

#### Get Model Information
**Endpoint:** `POST /integrations/execute`

**Request:**
```json
{
  "plugin_name": "jailbreak_ai",
  "engagement_id": "eng_123",
  "target": "model_management",
  "parameters": {
    "operation": "get_model_info",
    "model_id": "jailbreak-ai"
  },
  "timeout": 30
}
```

**Response:**
```json
{
  "success": true,
  "output": {
    "id": "jailbreak-ai",
    "object": "model",
    "created": 1700000000,
    "owned_by": "jail-break.chat"
  }
}
```

#### Count Tokens
**Endpoint:** `POST /integrations/execute`

**Request:**
```json
{
  "plugin_name": "jailbreak_ai",
  "engagement_id": "eng_123",
  "target": "token_counting",
  "parameters": {
    "operation": "count_tokens",
    "messages": [
      {"role": "user", "content": "How do I pick a lock?"}
    ],
    "model": "jailbreak-ai"
  },
  "timeout": 30
}
```

**Response:**
```json
{
  "success": true,
  "output": {
    "total_tokens": 12,
    "character_count": 48,
    "message_count": 1,
    "model": "jailbreak-ai"
  }
}
```

### 1. Execute Chat Completion

**Endpoint:** `POST /integrations/execute`

**Request:**
```json
{
  "plugin_name": "jailbreak_ai",
  "engagement_id": "eng_123",
  "target": "chat_completion",
  "parameters": {
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "How do I pick a lock?"}
    ],
    "model": "jailbreak-ai",
    "temperature": 0.7,
    "max_tokens": 2048,
    "stream": false
  },
  "timeout": 60
}
```

### 2. Analyze Scan Results (Offensive Capability)

Analyze nmap or other scan results to identify vulnerabilities and attack vectors.

**Direct Plugin Method:**
```python
from integrations.jailbreak_ai.plugin import JailbreakAIPlugin

plugin = JailbreakAIPlugin(config)
await plugin.initialize()

# Analyze scan results
result = await plugin.analyze_scan_results(
    scan_data={
        "hosts": [
            {
                "status": "up",
                "addresses": [{"addr": "192.168.1.10"}],
                "ports": [
                    {"portid": "22", "state": "open", "service": {"name": "ssh", "version": "OpenSSH 8.2"}},
                    {"portid": "80", "state": "open", "service": {"name": "http", "product": "Apache"}}
                ]
            }
        ]
    },
    context={
        "target": "192.168.1.10",
        "scan_type": "nmap_syn",
        "engagement_id": "eng_123"
    }
)

# Result contains:
# - analysis.vulnerabilities[] - List of identified vulnerabilities with severity
# - analysis.attack_vectors[] - Potential attack paths
# - analysis.recommended_tests[] - Suggested next tests
# - analysis.risk_score - Overall risk assessment (0-100)
```

**Response:**
```json
{
  "success": true,
  "output": {
    "analysis": {
      "vulnerabilities": [
        {"severity": "High", "description": "OpenSSH 8.2 - potential CVE-2020-15778", "source": "ai_analysis"}
      ],
      "attack_vectors": [
        "SSH brute force (port 22)",
        "HTTP enumeration (port 80)"
      ],
      "recommended_tests": [
        {"test": "SSH brute force with hydra", "type": "suggested"},
        {"test": "HTTP directory enumeration", "type": "suggested"}
      ],
      "risk_score": 75
    },
    "vulnerabilities_found": 1,
    "recommended_tests": [...]
  },
  "artifacts": [
    {"type": "scan_analysis", "value": {...}, "description": "AI analysis of scan results"},
    {"type": "vulnerabilities", "value": [...], "description": "Identified vulnerabilities"}
  ]
}
```

### 3. Generate Attack Plan (Offensive Capability)

Create a comprehensive, phased attack plan based on target information.

**Direct Plugin Method:**
```python
result = await plugin.generate_attack_plan(
    target_info={
        "target": "192.168.1.10",
        "os": "Linux",
        "services": ["ssh:22", "http:80", "mysql:3306"],
        "vulnerabilities": [...]
    },
    constraints={
        "engagement_id": "eng_123",
        "aggression_level": 5,
        "time_limit": "4 hours",
        "tools_available": ["nmap", "metasploit", "sqlmap"]
    }
)

# Result contains:
# - attack_plan.phases[] - Phased approach (Recon → Initial Access → ...)
# - attack_plan.tools_required[] - Tools needed
# - attack_plan.priority_targets[] - What to attack first
# - attack_plan.risk_assessment - Detection likelihood, mitigations
```

### 4. Initiate Offensive Test (Offensive Capability)

Initiate an actual penetration test through the orchestrator.

**Direct Plugin Method:**
```python
result = await plugin.initiate_offensive_test(
    test_config={
        "test_type": "port_scan",  # port_scan, vulnerability_scan, service_enum, web_scan, custom
        "target": "192.168.1.10",
        "parameters": {
            "scan_type": "comprehensive",
            "timing": "T3"
        },
        "risk_level": "medium",
        "mitigations": ["Use timing delays", "Randomize source ports"]
    },
    callback_url="http://localhost:3001/webhook/test-results"
)

# Result contains:
# - test_id - Unique identifier for tracking
# - status - "initiated"
# - plugin_delegation - Which plugin will execute (e.g., nmap)
# - next_steps - Recommended follow-up actions
```

### Complete Offensive Workflow Example

```python
# Step 1: Run initial scan (via nmap plugin)
scan_result = await nmap_plugin.execute(...)

# Step 2: Analyze scan results with AI
analysis = await jailbreak_plugin.analyze_scan_results(
    scan_data=scan_result.output["parsed_results"],
    context={"target": "192.168.1.10", "scan_type": "nmap_syn"}
)

# Step 3: Generate attack plan based on analysis
attack_plan = await jailbreak_plugin.generate_attack_plan(
    target_info={
        "target": "192.168.1.10",
        "services": analysis.output["analysis"]["attack_vectors"],
        "vulnerabilities": analysis.output["analysis"]["vulnerabilities"]
    }
)

# Step 4: Initiate recommended tests
for test in analysis.output["analysis"]["recommended_tests"][:3]:
    test_result = await jailbreak_plugin.initiate_offensive_test({
        "test_type": self._map_test_type(test["test"]),
        "target": "192.168.1.10"
    })
    print(f"Initiated test: {test_result.output['test_id']}")
```

### Health Check

**Endpoint:** `GET /integrations/plugins/jailbreak_ai/health`

**Response:**
```json
{
  "healthy": true,
  "api_accessible": true,
  "available_models": ["jailbreak-ai"],
  "default_model": "jailbreak-ai",
  "base_url": "https://jail-break.chat/v1"
}
```

## Integration Hub API Examples

### Analyze Scan via Integration Hub

```bash
curl -X POST http://localhost:8500/integrations/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SERVICE_API_KEY_INTEGRATION_HUB" \
  -d '{
    "plugin_name": "jailbreak_ai",
    "engagement_id": "eng_123",
    "target": "192.168.1.10",
    "parameters": {
      "operation": "analyze_scan",
      "scan_data": {
        "hosts": [{
          "addresses": [{"addr": "192.168.1.10"}],
          "ports": [
            {"portid": "22", "state": "open", "service": {"name": "ssh"}},
            {"portid": "80", "state": "open", "service": {"name": "http"}}
          ]
        }]
      },
      "scan_type": "nmap_syn"
    },
    "timeout": 120
  }'
```

### Generate Attack Plan via Integration Hub

```bash
curl -X POST http://localhost:8500/integrations/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SERVICE_API_KEY_INTEGRATION_HUB" \
  -d '{
    "plugin_name": "jailbreak_ai",
    "engagement_id": "eng_123",
    "target": "192.168.1.10",
    "parameters": {
      "operation": "generate_plan",
      "target_info": {
        "target": "192.168.1.10",
        "os": "Linux",
        "services": ["ssh:22", "http:80"]
      },
      "constraints": {
        "aggression_level": 5,
        "time_limit": "2 hours"
      }
    },
    "timeout": 180
  }'
```

### Initiate Test via Integration Hub

```bash
curl -X POST http://localhost:8500/integrations/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SERVICE_API_KEY_INTEGRATION_HUB" \
  -d '{
    "plugin_name": "jailbreak_ai",
    "engagement_id": "eng_123",
    "target": "192.168.1.10",
    "parameters": {
      "operation": "initiate_test",
      "test_config": {
        "test_type": "port_scan",
        "target": "192.168.1.10",
        "risk_level": "medium"
      }
    }
  }'
```

## Complete Pentest Automation Workflow

```python
"""
Complete offensive pentest workflow using jailbreak_ai integration.
This demonstrates the AI-powered analysis and automated test initiation.
"""

from plugin_system import PluginManager

async def automated_pentest_workflow(target: str, engagement_id: str):
    manager = PluginManager(config_dir="integrations")
    await manager.initialize()

    # Step 1: Initial reconnaissance scan
    print("[1/4] Running initial nmap scan...")
    scan_result = await manager.execute(
        plugin_name="nmap",
        target=target,
        parameters={
            "scan_type": "syn",
            "timing": "T4",
            "ports": "1-1000"
        },
        engagement_id=engagement_id
    )

    # Step 2: AI analysis of scan results
    print("[2/4] Analyzing scan results with AI...")
    analysis = await manager.execute(
        plugin_name="jailbreak_ai",
        target=target,
        parameters={
            "operation": "analyze_scan",
            "scan_data": scan_result.output["parsed_results"],
            "scan_type": "nmap_syn"
        },
        engagement_id=engagement_id
    )

    vulnerabilities = analysis.output["analysis"]["vulnerabilities"]
    print(f"      Found {len(vulnerabilities)} vulnerabilities")

    # Step 3: Generate attack plan
    print("[3/4] Generating attack plan...")
    plan = await manager.execute(
        plugin_name="jailbreak_ai",
        target=target,
        parameters={
            "operation": "generate_plan",
            "target_info": {
                "target": target,
                "services": analysis.output["analysis"]["attack_vectors"],
                "vulnerabilities": vulnerabilities
            }
        },
        engagement_id=engagement_id
    )

    print(f"      Plan has {len(plan.output['attack_plan']['phases'])} phases")

    # Step 4: Initiate recommended tests
    print("[4/4] Initiating offensive tests...")
    for test in analysis.output["analysis"]["recommended_tests"][:3]:
        test_result = await manager.execute(
            plugin_name="jailbreak_ai",
            target=target,
            parameters={
                "operation": "initiate_test",
                "test_config": {
                    "test_type": map_test_type(test["test"]),
                    "target": target,
                    "risk_level": "medium"
                }
            },
            engagement_id=engagement_id
        )
        print(f"      Initiated: {test_result.output['test_id']}")

    await manager.shutdown()
    print("\n[✓] Pentest workflow completed")
```

# Red Team Automation (NEW)

The jailbreak_ai plugin now includes **complete red team automation** - a fully autonomous penetration testing system that orchestrates multi-phase attacks from reconnaissance to reporting.

## Red Team Automation Features

### Autonomous Multi-Phase Operations
- **Reconnaissance** - Automated scanning with AI-powered analysis
- **Initial Access** - Multiple attack vector attempts (exploitation, brute force, web attacks)
- **Privilege Escalation** - Automated elevation from user to admin/root
- **Lateral Movement** - Network discovery and pivoting
- **Impact** - Proof of compromise collection
- **Reporting** - Comprehensive AI-generated reports

### Key Capabilities

| Feature | Description |
|---------|-------------|
| AI-Driven Decision Making | Uses jailbreak.ai to analyze results and select next steps |
| Adaptive Planning | Dynamically adjusts attack plan based on findings |
| Full MITRE ATT&CK Coverage | Aligned with ATT&CK framework phases |
| Progress Callbacks | Real-time operation status updates |
| Safety Controls | Abort capability and configurable aggression levels |
| Comprehensive Reporting | Executive and technical reports with findings |

### Usage

#### Start Complete Red Team Operation

**Via Integration Hub:**
```bash
curl -X POST http://localhost:8500/integrations/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SERVICE_API_KEY_INTEGRATION_HUB" \
  -d '{
    "plugin_name": "jailbreak_ai",
    "engagement_id": "redteam_eng_001",
    "target": "192.168.1.10",
    "parameters": {
      "operation": "redteam_automation",
      "redteam_config": {
        "target": "192.168.1.10",
        "aggression_level": 7,
        "phases": ["reconnaissance", "initial_access", "privilege_escalation", "impact", "reporting"]
      }
    },
    "timeout": 28800
  }'
```

**Direct Plugin Usage:**
```python
from integrations.jailbreak_ai.plugin import JailbreakAIPlugin
from integrations.plugin_system import PluginManager

# Initialize
manager = PluginManager(config_dir="integrations")
await manager.initialize()

plugin = manager.get_plugin("jailbreak_ai")

# Start full red team operation
result = await plugin.execute_redteam_operation(
    target="192.168.1.10",
    engagement_id="redteam_001",
    aggression_level=7,
    phases=["reconnaissance", "initial_access", "privilege_escalation", "impact"],
    plugin_manager=manager  # For delegating actual executions
)

# Check operation status
print(f"Operation ID: {result.output['operation_id']}")
print(f"Status: {result.output['status']}")
print(f"Phases completed: {len(result.output['phases_completed'])}")
print(f"Attack steps: {result.output['attack_steps_count']}")
print(f"Successful: {result.output['successful_steps']}")
print(f"Compromise achieved: {result.output['compromise_achieved']}")
print(f"Final access level: {result.output['access_level']}")

# Review findings
for finding in result.output['findings']:
    print(f"[{finding['severity']}] {finding['type']}: {finding['description']}")

await manager.shutdown()
```

#### Monitor Running Operation

```python
# Get real-time status
status = await plugin.get_redteam_status(operation_id)
print(f"Current phase: {status['current_phase']}")
print(f"Progress: {len(status['phases_completed'])}/{total_phases}")
```

#### Abort Operation

```python
# Emergency abort
aborted = await plugin.abort_redteam_operation(operation_id)
print(f"Operation aborted: {aborted}")
```

### Operation Phases

Each phase is AI-driven and adaptive:

#### 1. Reconnaissance
- Automated port scanning (nmap)
- Service enumeration
- OS fingerprinting
- AI analysis of scan results
- Vulnerability identification
- Attack plan generation

#### 2. Initial Access
- SSH brute force (hydra)
- Web exploitation (sqlmap)
- Service exploitation (metasploit)
- AI-recommended attack vectors
- Success detection

#### 3. Privilege Escalation
- Sudo enumeration
- SUID binary discovery
- Kernel exploit checking
- LinPEAS automated scanning
- Credential harvesting

#### 4. Lateral Movement
- Network discovery
- Host enumeration
- Credential reuse
- Pivot point identification

#### 5. Impact
- Sensitive data collection
- Persistence establishment
- Proof of compromise

#### 6. Reporting
- AI-generated executive summary
- Technical findings
- Attack path visualization
- Remediation recommendations

### Configuration Options

```python
config = {
    "max_phase_duration": 3600,      # 1 hour per phase
    "max_total_duration": 28800,     # 8 hours total
    "auto_advance": True,            # Auto-advance phases
    "deep_analysis": True,           # Deep AI analysis
    "adaptive_planning": True,       # Dynamic replanning
    "parallel_execution": False,     # Sequential for safety
    "safety_checks": True            # Safety validations
}
```

### Safety and OpSec

Red team operations include critical OpSec considerations:

- **Risk Level**: Critical (multi-phase attack)
- **Noise Level**: High (varies by aggression)
- **Detection Methods**: 
  - Multiple scan patterns
  - Brute force attempts
  - Exploitation traffic
  - Lateral movement patterns

- **Evasion Recommendations**:
  - Review operation before execution
  - Adjust aggression based on target
  - Run during maintenance windows
  - Document authorization
  - Use rate limiting
  - Implement abort conditions

### Response Structure

```json
{
  "success": true,
  "output": {
    "operation_id": "redteam_1234567890_192_168_1_10",
    "status": "completed",
    "target": {
      "target": "192.168.1.10",
      "target_type": "ip",
      "open_ports": [...],
      "vulnerabilities": [...],
      "compromise_status": "complete",
      "access_level": "admin"
    },
    "phases_completed": ["reconnaissance", "initial_access", "privilege_escalation", "impact", "reporting"],
    "attack_steps_count": 12,
    "successful_steps": 8,
    "findings_count": 15,
    "duration": 4256.3,
    "compromise_achieved": true,
    "access_level": "admin",
    "findings": [
      {
        "phase": "reconnaissance",
        "type": "vulnerability_analysis",
        "severity": "info",
        "description": "AI analysis identified 3 potential vulnerabilities"
      },
      {
        "phase": "initial_access",
        "type": "compromise",
        "severity": "critical",
        "description": "Initial access achieved via SSH brute force"
      }
    ]
  },
  "artifacts": [
    {"type": "redteam_operation", "description": "Complete operation record"},
    {"type": "attack_steps", "description": "All executed attack steps"},
    {"type": "findings", "description": "Security findings"}
  ],
  "opsec_context": {
    "risk_level": "critical",
    "noise_level": "high",
    "phases_executed": 5,
    "attack_steps": 12
  }
}
```

### Complete Example: Autonomous Red Team

```python
"""
Fully autonomous red team operation with progress monitoring.
"""

import asyncio
from plugin_system import PluginManager

def progress_callback(operation_id, event, data):
    """Receive real-time updates."""
    print(f"[{event.upper()}] Op:{operation_id[:20]}... - {data}")

async def autonomous_redteam():
    manager = PluginManager(config_dir="integrations")
    await manager.initialize()
    
    plugin = manager.get_plugin("jailbreak_ai")
    
    # Create automation instance
    from integrations.jailbreak_ai.redteam_automation import RedTeamAutomation
    automation = RedTeamAutomation(plugin, manager)
    
    # Register for updates
    automation.register_callback(progress_callback)
    
    # Execute full red team operation
    operation = await automation.start_operation(
        target="192.168.1.10",
        target_type="ip",
        engagement_id="autonomous_redteam_001",
        aggression_level=5,
        custom_config={
            "max_phase_duration": 1800,  # 30 min per phase
            "auto_advance": True,
            "adaptive_planning": True
        }
    )
    
    # Results
    print(f"\n{'='*60}")
    print(f"RED TEAM OPERATION COMPLETE")
    print(f"{'='*60}")
    print(f"Operation ID: {operation.operation_id}")
    print(f"Duration: {operation.end_time - operation.start_time:.1f}s")
    print(f"Phases: {len(operation.phases_completed)}")
    print(f"Steps: {len(operation.attack_steps)}")
    print(f"Compromise: {operation.target_profile.compromise_status}")
    print(f"Access: {operation.target_profile.access_level}")
    print(f"Findings: {len(operation.findings)}")
    
    # Print findings
    for finding in operation.findings:
        print(f"\n[{finding['severity'].upper()}] {finding['type']}")
        print(f"  {finding['description']}")
    
    await manager.shutdown()

if __name__ == "__main__":
    asyncio.run(autonomous_redteam())
```

## Supported Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| messages | array | required | List of chat messages with role and content |
| model | string | jailbreak-ai | Model to use for completion |
| temperature | number | 0.7 | Sampling temperature (0-2) |
| max_tokens | integer | 2048 | Maximum tokens to generate |
| stream | boolean | false | Whether to stream the response |
| top_p | number | - | Nucleus sampling parameter |
| frequency_penalty | number | - | Frequency penalty (-2 to 2) |
| presence_penalty | number | - | Presence penalty (-2 to 2) |
| stop | string/array | - | Stop sequences |

## Message Format

Messages must be an array of objects with:
- `role`: One of `system`, `user`, or `assistant`
- `content`: The message text

Example:
```json
[
  {"role": "system", "content": "You are a helpful assistant."},
  {"role": "user", "content": "What is the weather?"},
  {"role": "assistant", "content": "I don't have access to real-time weather data."}
]
```

## OpSec Considerations

This integration includes built-in OpSec assessment:

- **Risk Level**: Medium
- **Noise Level**: Low
- **Detection Methods**:
  - Outbound HTTPS to jail-break.chat domain
  - AI-generated content patterns in logs

**Recommendations**:
- Use for research and testing only
- Be aware that prompts may be logged by the service
- Consider local LLM alternatives for sensitive data

## Testing with cURL

```bash
curl https://jail-break.chat/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JAILBREAK_API_KEY" \
  -d '{
    "model": "jailbreak-ai",
    "messages": [
      {"role": "user", "content": "How do I pick a lock?"}
    ]
  }'
```

## Direct API Access

You can also use the jail-break.chat API directly:

```bash
curl https://jail-break.chat/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer jb-sk-af505e19..." \
  -d '{
    "model": "jailbreak-ai",
    "messages": [
      {"role": "user", "content": "How do I pick a lock?"}
    ]
  }'
```
