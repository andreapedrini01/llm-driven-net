# Action Output Interface

The Action Output Interface handles saving validated network actions to disk before they're executed by the Northbound Script Generator. It provides structured JSON output, logging, and traceability.

## What It Does

After the LLM module generates and validates actions, this service:

1. Packages actions into a structured `NorthboundActionPackage`
2. Saves the package as a JSON file in `output/actions/`
3. Logs the operation to `output/logs/action_output.log`
4. Tracks status in memory for traceability

## How It's Used in main.py

In the main integration flow, `ActionOutputService` (an alias for `ActionOutputInterface`) is called at Step 7:

```python
from llm_integration_module.services.action_output import ActionOutputService

action_output = ActionOutputService()

# After validation passes:
output_result = action_output.save_actions(action_sequence)
```

`save_actions()` is a convenience method that wraps the full workflow — it creates a package, serializes it, saves to file, and logs everything.

## Output Format

Action packages are saved as JSON files named `action_package_{sequence_id}_{timestamp}.json`:

```json
{
  "package_id": "pkg_seq_001_20260210132013",
  "package_version": "1.0",
  "created_at": "2026-02-10T13:20:13.654453",
  "source_intent_id": "intent_001",
  "sequence_id": "seq_001",
  "actions": [
    {
      "action_id": "action_001",
      "action_type": "slice_create",
      "target_resource": "switch-1",
      "parameters": { "slice_name": "slice_intent_001", "resources": ["h1", "h2"], "bandwidth": 10 },
      "execution_priority": 1000,
      "timeout_seconds": 30,
      "description": "Create slice between h1 and h2 at 10 Mbps"
    }
  ],
  "execution_order": ["action_001"],
  "validation": {
    "validation_passed": true,
    "safety_approved": true,
    "risk_level": "low"
  },
  "traceability": {
    "trace_id": "trace_intent_001_20260210132013654453",
    "user_id": null
  }
}
```

## Action Statuses

Actions move through a lifecycle:

- `PENDING` — being prepared
- `READY` — package saved, waiting for execution
- `SENT` — sent to the Northbound module
- `ACKNOWLEDGED` — execution confirmed
- `FAILED` — execution failed

## Querying Records

```python
# Get a specific record
record = action_output.get_output_record(record_id)

# Get all records for an intent
records = action_output.get_records_by_intent(intent_id)

# Update status after execution
action_output.update_record_status(record_id, ActionStatus.ACKNOWLEDGED)
```

## File Locations

| Path | Content |
|------|---------|
| `output/actions/` | JSON action packages |
| `output/logs/action_output.log` | Append-only log of all operations |

Directories are created automatically on first use.
