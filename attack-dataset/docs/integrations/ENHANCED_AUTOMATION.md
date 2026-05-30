# Enhanced Jailbreak AI Automation

## Overview

The enhanced Jailbreak AI integration provides advanced automation capabilities for red team operations, including multi-target automation, continuous monitoring, adaptive replanning, and intelligent evasion.

## API Endpoints

The Integration Hub provides dedicated REST API endpoints for enhanced automation features. These endpoints offer a simplified interface compared to the generic `/integrations/execute` endpoint.

### Base URL
```
http://localhost:8500/api/v1/automation
```

### Multi-Target Operations

**Endpoint:** `POST /api/v1/automation/multi-target`

Start a multi-target red team operation against multiple targets simultaneously.

**Request:**
```json
{
  "engagement_id": "multi_target_001",
  "targets": ["192.168.1.10", "192.168.1.11"],
  "aggression_level": 5,
  "parallel": true,
  "evasion_level": "medium",
  "max_parallel_tasks": 5
}
```

**Response:**
```json
{
  "success": true,
  "output": {
    "multi_target_operation": true,
    "summary": {
      "total_targets": 2,
      "successful": 2,
      "failed": 0,
      "total_findings": 4
    },
    "operations_count": 2,
    "targets": ["192.168.1.10", "192.168.1.11"]
  },
  "error": null,
  "artifacts": [...],
  "opsec_context": {...}
}
```

### Continuous Monitoring

**Endpoint:** `POST /api/v1/automation/monitoring/start`

Start continuous monitoring for persistent surveillance of targets.

**Request:**
```json
{
  "engagement_id": "monitor_001",
  "targets": ["192.168.1.10", "192.168.1.11"],
  "interval": 300
}
```

**Response:**
```json
{
  "success": true,
  "output": {
    "monitoring_session_id": "monitor_123456",
    "targets": ["192.168.1.10", "192.168.1.11"],
    "interval": 300,
    "status": "active"
  },
  "error": null,
  "artifacts": [...],
  "opsec_context": {...}
}
```

### Adaptive Replanning

**Endpoint:** `POST /api/v1/automation/replanning`

Execute AI-driven adaptive replanning for failed attack steps.

**Request:**
```json
{
  "operation_id": "redteam_001",
  "failed_step": {
    "step": "exploit",
    "error": "Connection timeout"
  },
  "context": {
    "engagement_id": "engagement_001",
    "target": "192.168.1.10"
  }
}
```

**Response:**
```json
{
  "success": true,
  "output": {
    "adaptive_replanning": true,
    "alternatives_generated": 3,
    "alternative_approaches": [...]
  },
  "error": null,
  "artifacts": [...],
  "opsec_context": {...}
}
```

### Operation Control

**Endpoint:** `POST /api/v1/automation/operation/control`

Control running operations (pause, resume, abort).

**Request:**
```json
{
  "operation_id": "redteam_001",
  "action": "pause"
}
```

**Monitoring Control**

**Endpoint:** `POST /api/v1/automation/monitoring/control`

Control monitoring sessions (pause, resume, stop).

**Request:**
```json
{
  "session_id": "monitor_123456",
  "action": "pause"
}
```

### Status Endpoints

**List Operations:** `GET /api/v1/automation/operations`
**List Monitoring Sessions:** `GET /api/v1/automation/monitoring/sessions`
**Get Operation Status:** `GET /api/v1/operation/{operation_id}`
**Get Monitoring Status:** `GET /api/v1/monitoring/{session_id}`

## New Features

### 1. Multi-Target Automation

Execute simultaneous red team operations against multiple targets with parallel execution support.

**Endpoint:** `POST /integrations/execute`
**Operation:** `multi_target_automation`

**Example Request:**
```bash
curl -X POST http://localhost:8500/integrations/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SERVICE_API_KEY_INTEGRATION_HUB" \
  -d '{
    "plugin_name": "jailbreak_ai",
    "engagement_id": "multi_target_001",
    "target": "multiple",
    "parameters": {
      "operation": "multi_target_automation",
      "multi_target_config": {
        "targets": ["192.168.1.10", "192.168.1.11", "192.168.1.12"],
        "aggression_level": 5,
        "parallel": true
      }
    },
    "timeout": 28800
  }'
```

**Features:**
- Parallel execution of operations across multiple targets
- Configurable concurrency limits
- Comprehensive multi-target summary reporting
- Individual operation tracking and management

**Configuration:**
```python
{
  "max_parallel_tasks": 5,  # Maximum concurrent operations
  "parallel_execution": true,  # Enable parallel processing
  "auto_advance": true  # Automatically advance phases
}
```

### 2. Continuous Monitoring Mode

Persistent surveillance with automated baseline comparison and alerting.

**Endpoint:** `POST /integrations/execute`
**Operation:** `continuous_monitoring`

**Example Request:**
```bash
curl -X POST http://localhost:8500/integrations/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SERVICE_API_KEY_INTEGRATION_HUB" \
  -d '{
    "plugin_name": "jailbreak_ai",
    "engagement_id": "monitor_001",
    "target": "monitoring",
    "parameters": {
      "operation": "continuous_monitoring",
      "monitor_config": {
        "targets": ["192.168.1.10", "192.168.1.11"],
        "interval": 300
      }
    },
    "timeout": 60
  }'
```

**Features:**
- Configurable monitoring intervals (default: 5 minutes)
- Automatic baseline establishment
- Change detection (ports, services, versions)
- Custom alert callbacks
- Background monitoring loops

**Configuration:**
```python
{
  "continuous_monitoring": true,
  "monitoring_interval": 300,  # 5 minutes
  "intelligent_timing": true
}
```

### 3. Adaptive Replanning

AI-driven generation of alternative attack approaches when steps fail.

**Endpoint:** `POST /integrations/execute`
**Operation:** `adaptive_replanning`

**Example Request:**
```bash
curl -X POST http://localhost:8500/integrations/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SERVICE_API_KEY_INTEGRATION_HUB" \
  -d '{
    "plugin_name": "jailbreak_ai",
    "engagement_id": "replan_001",
    "target": "adaptive",
    "parameters": {
      "operation": "adaptive_replanning",
      "operation_id": "redteam_123456",
      "failed_step": {
        "step_id": "step_001",
        "phase": "initial_access",
        "name": "SSH Brute Force",
        "tool": "hydra",
        "command": "hydra -l user -P pass.txt ssh://target",
        "output": "All passwords failed",
        "executed": true,
        "success": false
      },
      "context": {
        "target": "192.168.1.10",
        "access_level": "none"
      }
    },
    "timeout": 120
  }'
```

**Features:**
- AI analysis of failed steps
- Generation of 2-3 alternative approaches
- Different tools and techniques
- Risk assessment for each alternative
- Automatic integration into operation workflow

**Configuration:**
```python
{
  "adaptive_replanning": true,
  "deep_analysis": true
}
```

### 4. Intelligent Timing and Evasion

Smart delays and pattern randomization to avoid detection.

**Features:**
- Configurable evasion levels (low, medium, high, extreme)
- Randomized timing multipliers
- Pattern avoidance
- Context-aware delays

**Configuration:**
```python
{
  "intelligent_timing": true,
  "evasion_level": "medium"  # low, medium, high, extreme
}
```

**Timing Multipliers:**
- Low: 1.0x (minimal delays)
- Medium: 2.5x (balanced)
- High: 5.0x (significant delays)
- Extreme: 10.0x (maximum evasion)

### 5. Workflow State Persistence

Save and resume operations for long-running engagements.

**Features:**
- Automatic state persistence to disk
- Operation resume capability
- Attack step reconstruction
- Findings and artifacts preservation

**Configuration:**
```python
{
  "persistence_enabled": true
}
```

**Persistence Location:**
```
.attack-dataset/.redteam_persistence/{operation_id}.json
```

### 6. Enhanced Operation Control

Granular control over running operations.

**New Methods:**
- `pause_operation()` - Pause a running operation
- `resume_operation()` - Resume a paused operation
- `abort_operation()` - Abort a running operation (existing)
- `get_operation_status()` - Get detailed operation status (existing)

**Example:**
```bash
# Pause operation
curl -X POST http://localhost:8500/integrations/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SERVICE_API_KEY_INTEGRATION_HUB" \
  -d '{
    "plugin_name": "jailbreak_ai",
    "parameters": {
      "operation": "control",
      "control_action": "pause",
      "operation_id": "redteam_123456"
    }
  }'
```

## Configuration Options

### Complete Configuration Schema

```python
{
  # Core Settings
  "max_phase_duration": 3600,        # 1 hour per phase
  "max_total_duration": 28800,       # 8 hours total
  "auto_advance": true,              # Auto-advance phases
  "deep_analysis": true,             # Enable deep AI analysis
  "adaptive_planning": true,         # Enable adaptive planning
  "safety_checks": true,             # Enable safety checks
  
  # Enhanced Features
  "parallel_execution": true,        # Enable parallel execution
  "max_parallel_tasks": 5,           # Max concurrent tasks
  "intelligent_timing": true,        # Enable smart delays
  "evasion_level": "medium",         # Evasion aggressiveness
  "persistence_enabled": true,       # Enable state persistence
  "realtime_streaming": true,        # Enable live updates
  "adaptive_replanning": true,       # Enable AI replanning
  "continuous_monitoring": false,    # Enable monitoring mode
  "monitoring_interval": 300         # Monitoring interval (seconds)
}
```

## Operation Modes

### Single Target (Original)
```bash
operation: "redteam_automation"
redteam_config: {
  "target": "192.168.1.10",
  "aggression_level": 5,
  "phases": ["reconnaissance", "initial_access", "privilege_escalation"]
}
```

### Multi-Target (New)
```bash
operation: "multi_target_automation"
multi_target_config: {
  "targets": ["192.168.1.10", "192.168.1.11", "192.168.1.12"],
  "aggression_level": 5,
  "parallel": true
}
```

### Continuous Monitoring (New)
```bash
operation: "continuous_monitoring"
monitor_config: {
  "targets": ["192.168.1.10", "192.168.1.11"],
  "interval": 300
}
```

### Adaptive Replanning (New)
```bash
operation: "adaptive_replanning"
operation_id: "redteam_123456"
failed_step: { ... }
context: { ... }
```

## OpSec Considerations

### Multi-Target Operations
- **Risk Level:** Critical
- **Noise Level:** Very High (parallel) / High (sequential)
- **Detection Methods:** 
  - Simultaneous scan patterns
  - Coordinated attack timing
  - High-volume network traffic
- **Evasion Recommendations:**
  - Stagger target start times
  - Use different source IPs
  - Run during maintenance windows
  - Ensure proper authorization

### Continuous Monitoring
- **Risk Level:** Medium
- **Noise Level:** Medium
- **Detection Methods:**
  - Periodic scan traffic
  - Regular connection attempts
  - Baseline comparison activities
- **Evasion Recommendations:**
  - Use longer intervals
  - Randomize scan timing
  - Monitor during off-peak hours
  - Ensure authorization for persistent monitoring

### Adaptive Replanning
- **Risk Level:** Medium
- **Noise Level:** Low
- **Detection Methods:**
  - AI service usage
- **Evasion Recommendations:**
  - Review alternatives before execution
  - Consider OpSec implications

## Performance Considerations

### Parallel Execution
- **Benefits:** Faster completion, better resource utilization
- **Considerations:** Higher network load, increased detection risk
- **Recommendation:** Use with caution in sensitive environments

### State Persistence
- **Benefits:** Resume capability, crash recovery
- **Considerations:** Disk I/O overhead, storage requirements
- **Recommendation:** Enable for long-running operations

### Intelligent Timing
- **Benefits:** Reduced detection risk, better evasion
- **Considerations:** Longer operation duration
- **Recommendation:** Balance evasion vs. time constraints

## Error Handling

### Automatic Recovery
- Failed steps trigger adaptive replanning
- Parallel failures don't stop other operations
- Monitoring loops auto-retry on transient errors

### Manual Intervention
- Pause/resume operations for manual review
- Abort operations for emergency stops
- Load saved states for crash recovery

## API Reference

### New Operations

#### `multi_target_automation`
Execute operations against multiple targets.

**Parameters:**
- `targets` (list): List of target IPs/domains
- `aggression_level` (int): 1-10 scale
- `parallel` (bool): Enable parallel execution

**Response:**
- `summary`: Multi-target operation summary
- `operations_count`: Number of operations
- `targets`: List of targeted hosts

#### `continuous_monitoring`
Start persistent monitoring.

**Parameters:**
- `targets` (list): List of targets to monitor
- `interval` (int): Monitoring interval in seconds

**Response:**
- `monitoring_session_id`: Session identifier
- `status`: Monitoring status
- `interval`: Configured interval

#### `adaptive_replanning`
Generate alternative attack approaches.

**Parameters:**
- `operation_id`: Operation identifier
- `failed_step`: Failed step details
- `context`: Additional context

**Response:**
- `alternatives_generated`: Number of alternatives
- `alternative_approaches`: List of alternative steps

## Troubleshooting

### Common Issues

**Issue:** Multi-target operation fails
- **Solution:** Check network connectivity, reduce parallel tasks, verify API keys

**Issue:** Monitoring not detecting changes
- **Solution:** Verify interval settings, check baseline establishment, review target accessibility

**Issue:** Adaptive replanning returns no alternatives
- **Solution:** Check AI service availability, review failed step context, verify operation ID

## Best Practices

1. **Start Small:** Test with single targets before scaling to multi-target
2. **Monitor Closely:** Use pause/resume for critical operations
3. **Configure Evasion:** Adjust evasion levels based on environment sensitivity
4. **Enable Persistence:** Save states for long-running operations
5. **Review Alternatives:** Manually review AI-generated alternatives before execution
6. **Schedule Wisely:** Run intensive operations during maintenance windows
7. **Document Authorization:** Ensure proper authorization for all targets

## Migration Guide

### From Original Automation

No breaking changes. Original `redteam_automation` operation remains unchanged.

To use new features:
1. Update operation type to `multi_target_automation` for multiple targets
2. Add `continuous_monitoring` for persistent surveillance
3. Call `adaptive_replanning` when steps fail
4. Enable new configuration options in config

### Configuration Migration

Add new options to existing configuration:
```python
# Old config
config = {
  "aggression_level": 5,
  "phases": ["reconnaissance", "initial_access"]
}

# New config with enhancements
config = {
  "aggression_level": 5,
  "phases": ["reconnaissance", "initial_access"],
  "parallel_execution": true,
  "intelligent_timing": true,
  "adaptive_replanning": true,
  "persistence_enabled": true
}
```

## Support

For issues or questions:
1. Check logs: `backend/integrations/logs/`
2. Review operation states: `.redteam_persistence/`
3. Verify configuration in `.env`
4. Consult main documentation: [INTEGRATIONS_BLUEPRINT.md](../architecture/INTEGRATIONS_BLUEPRINT.md)

## Changelog

### Version 2.0 (Enhanced Automation)
- Added multi-target automation
- Added continuous monitoring mode
- Added adaptive replanning
- Added intelligent timing and evasion
- Added workflow state persistence
- Added enhanced operation control
- Added parallel execution engine
- Improved OpSec assessments
- Enhanced error handling and recovery

### Version 1.0 (Original)
- Basic red team automation
- Single target operations
- Sequential phase execution
- Basic AI analysis
- Standard reporting