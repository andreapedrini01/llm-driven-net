# Action Package Guide

## Overview

The Action Package is the standardized input format for the Northbound Script Generator. It represents a validated sequence of network actions that will be executed against the ComnetsEMU/RYU network.

**Validation Status:** ✅ VALIDATED AND PRODUCTION READY

## Quick Reference

### Package Structure

```json
{
  "package_id": "unique-package-id",
  "package_version": "1.0",
  "created_at": "2024-01-15T10:00:00Z",
  "source_intent_id": "intent-id",
  "sequence_id": "sequence-id",
  "actions": [...],
  "execution_order": [...],
  "metadata": {...},
  "validation": {...},
  "rollback": {...},
  "traceability": {...}
}
```

### Action Structure

```json
{
  "action_id": "action-001",
  "action_type": "flow_mod|slice_create|slice_modify|config_change",
  "target_resource": "switch-1",
  "parameters": {...},
  "execution_priority": 1000,
  "timeout_seconds": 30,
  "description": "Human-readable description"
}
```

## Supported Action Types

### 1. flow_mod - Flow Modification

Adds, modifies, or deletes OpenFlow rules.

**Example:**
```json
{
  "action_id": "flow_mod_001",
  "action_type": "flow_mod",
  "target_resource": "switch-1",
  "parameters": {
    "match": {
      "in_port": 1,
      "eth_type": 2048,
      "ip_dst": "10.0.0.5"
    },
    "actions": [{"type": "output", "port": 2}],
    "priority": 100
  },
  "execution_priority": 1000,
  "timeout_seconds": 30,
  "description": "Route traffic to host 10.0.0.5"
}
```

### 2. slice_create - Network Slice Creation

Creates a network slice with QoS guarantees.

**Example:**
```json
{
  "action_id": "slice_create_001",
  "action_type": "slice_create",
  "target_resource": "slice-controller",
  "parameters": {
    "slice_name": "iot_slice",
    "resources": {
      "bandwidth": 500,
      "switches": ["switch-1", "switch-2"],
      "paths": [...]
    },
    "policies": [...],
    "sla": {
      "min_bandwidth": 400,
      "max_latency": 100,
      "availability": 99.9
    }
  },
  "execution_priority": 900,
  "timeout_seconds": 120
}
```

### 3. config_change - Configuration Change

Changes network element configuration.

**Example:**
```json
{
  "action_id": "config_change_001",
  "action_type": "config_change",
  "target_resource": "switch-2",
  "parameters": {
    "config_type": "qos_config",
    "config_data": {...},
    "backup": true,
    "validate_before_apply": true
  },
  "execution_priority": 800,
  "timeout_seconds": 60
}
```

## Field Mapping

| Package Field | System Model | Description |
|--------------|--------------|-------------|
| `action_id` | `NetworkAction.id` | Unique action identifier |
| `action_type` | `NetworkAction.type` | Type of action |
| `target_resource` | `NetworkAction.target` | Target network element |
| `parameters` | `NetworkAction.parameters` | Action-specific parameters |
| `execution_priority` | `NetworkAction.priority` | Execution priority (higher = more urgent) |
| `timeout_seconds` | `NetworkAction.timeout` | Maximum execution time |
| `description` | `NetworkAction.description` | Human-readable description |

## Rollback Plan

**CRITICAL:** Always include complete rollback coverage for all modified targets.

### Good Example (100% Coverage)

```json
{
  "rollback": {
    "rollback_actions": [
      {
        "action_id": "rollback_flow_001",
        "action_type": "flow_mod",
        "target_resource": "switch-1",
        "parameters": {...}
      },
      {
        "action_id": "rollback_slice_001",
        "action_type": "slice_modify",
        "target_resource": "slice-controller",
        "parameters": {"operation": "delete"}
      },
      {
        "action_id": "rollback_config_001",
        "action_type": "config_change",
        "target_resource": "switch-2",
        "parameters": {"operation": "restore"}
      }
    ],
    "has_rollback": true,
    "rollback_coverage": {
      "covered_targets": ["switch-1", "slice-controller", "switch-2"],
      "coverage_percentage": 100
    }
  }
}
```

### Bad Example (Incomplete Coverage)

```json
{
  "rollback": {
    "rollback_actions": [
      {
        "action_id": "rollback_flow_001",
        "target_resource": "switch-1"
      }
      // Missing rollback for slice-controller and switch-2!
    ]
  }
}
```

## Duration Estimation

Calculate realistic duration estimates:

```python
def estimate_duration(actions):
    base_times = {
        "flow_mod": 2,
        "slice_create": 30,
        "slice_modify": 15,
        "config_change": 10
    }
    
    total = sum(base_times.get(a["action_type"], 5) for a in actions)
    overhead = len(actions) * 5 + 20  # Per-action + base overhead
    
    return total + overhead
```

**Example:**
```json
{
  "metadata": {
    "estimated_duration_seconds": 62,
    "duration_calculation": {
      "flow_mod_001": 2,
      "slice_create_001": 30,
      "config_change_001": 10,
      "overhead": 20,
      "total": 62
    }
  }
}
```

## Validation

### Automated Validation

```bash
python scripts/validate_action_package.py
```

**Expected Output:**
```
✓ VALIDATION PASSED - Action package is compatible with the system
(No warnings)
```

### Manual Validation

```python
from src.models.action_models import NetworkAction, ActionType

# Validate action
action = NetworkAction(
    id="action_001",
    type=ActionType("flow_mod"),
    target="switch-1",
    parameters={"match": {"in_port": 1}},
    priority=1000,
    timeout=30
)

result = action.validate_action_parameters()
print(f"Valid: {result['is_valid']}")
```

## Submitting to API

### Individual Submission

```python
import requests

# Load package
with open('action_package.json') as f:
    package = json.load(f)

# Authenticate
response = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"username": "admin", "password": "admin"}
)
token = response.json()["access_token"]

# Submit each action
for action in package['actions']:
    response = requests.post(
        "http://localhost:8000/api/v1/actions",
        json={
            "type": action["action_type"],
            "target": action["target_resource"],
            "parameters": action["parameters"],
            "priority": action["execution_priority"],
            "timeout": action["timeout_seconds"],
            "description": action.get("description")
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    print(f"✓ {action['action_id']}: {response.status_code}")
```

### Batch Submission

```python
# Convert all actions
batch_actions = [
    {
        "type": a["action_type"],
        "target": a["target_resource"],
        "parameters": a["parameters"],
        "priority": a["execution_priority"],
        "timeout": a["timeout_seconds"],
        "description": a.get("description")
    }
    for a in package['actions']
]

# Submit as batch
response = requests.post(
    "http://localhost:8000/api/v1/actions/batch",
    json={
        "actions": batch_actions,
        "execution_mode": "parallel"
    },
    headers={"Authorization": f"Bearer {token}"}
)
```

## Best Practices

### 1. Action IDs
- Use descriptive, unique identifiers
- Include action type: `flow_mod_001`, `slice_create_001`
- Use consistent naming conventions

### 2. Priorities
- Critical actions: 1000+
- Normal actions: 500-999
- Background actions: 1-499

### 3. Timeouts
- Flow modifications: 30-60 seconds
- Slice creation: 60-120 seconds
- Configuration changes: 30-90 seconds

### 4. Descriptions
- Always include human-readable descriptions
- Explain purpose and expected outcome
- Include relevant context

### 5. Rollback Plans
- **ALWAYS** provide rollback for critical operations
- Ensure 100% target coverage
- Test rollback procedures
- Use specific match criteria

### 6. Duration Estimates
- Calculate based on action types
- Include overhead (20-30 seconds)
- Stay within 50% variance
- Document calculation

## Common Issues

### Issue: Validation Failed

**Symptoms:** Package fails validation

**Solutions:**
- Check all required fields present
- Verify action_type values are valid
- Ensure parameters match action type
- Validate JSON syntax

### Issue: Incomplete Rollback

**Symptoms:** Warning about missing rollback coverage

**Solution:**
```json
{
  "rollback": {
    "rollback_actions": [
      // Add one rollback action per forward action
      // Ensure all targets are covered
    ],
    "rollback_coverage": {
      "covered_targets": [...],  // List all targets
      "coverage_percentage": 100  // Must be 100
    }
  }
}
```

### Issue: Duration Variance

**Symptoms:** Warning about duration estimate

**Solution:**
```json
{
  "metadata": {
    "estimated_duration_seconds": 62,  // Realistic estimate
    "duration_calculation": {
      "action_1": 2,
      "action_2": 30,
      "overhead": 20,
      "total": 62
    }
  }
}
```

## Example Packages

### Simple Flow Rule

```json
{
  "package_id": "pkg_simple_001",
  "package_version": "1.0",
  "created_at": "2024-01-15T10:00:00Z",
  "source_intent_id": "intent_001",
  "sequence_id": "seq_001",
  "actions": [
    {
      "action_id": "flow_001",
      "action_type": "flow_mod",
      "target_resource": "switch-1",
      "parameters": {
        "match": {"in_port": 1},
        "actions": [{"type": "output", "port": 2}],
        "priority": 100
      },
      "execution_priority": 1000,
      "timeout_seconds": 30,
      "description": "Forward traffic from port 1 to port 2"
    }
  ],
  "metadata": {
    "estimated_duration_seconds": 22
  },
  "rollback": {
    "rollback_actions": [
      {
        "action_id": "rollback_001",
        "action_type": "flow_mod",
        "target_resource": "switch-1",
        "parameters": {
          "match": {"in_port": 1},
          "actions": [{"type": "drop"}]
        },
        "execution_priority": 1000,
        "timeout_seconds": 30
      }
    ],
    "has_rollback": true
  }
}
```

### Complete Example

See `.vscode/action_package_seq_demo_001_corrected.json` for a production-ready example with:
- Multiple action types
- Complete rollback coverage
- Accurate duration estimates
- Full metadata and traceability

## Quality Checklist

Before submitting an action package, verify:

- [ ] All required fields present
- [ ] Action types are valid
- [ ] Parameters match action type requirements
- [ ] Rollback coverage is 100%
- [ ] Duration estimate is realistic (within 50% variance)
- [ ] All action IDs are unique
- [ ] Descriptions are clear and informative
- [ ] Validation passes with no warnings
- [ ] JSON syntax is valid

## References

- **System Models:** `src/models/action_models.py`
- **API Models:** `src/api/models.py`
- **Validation Script:** `scripts/validate_action_package.py`
- **API Documentation:** http://localhost:8000/docs
- **Example Package:** `.vscode/action_package_seq_demo_001_corrected.json`

---

**Version:** 1.0 | **Status:** Production Ready ✅ | **Last Updated:** January 2025
