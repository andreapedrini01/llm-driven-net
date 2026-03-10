# Necessary Scripts - Simplified Northbound Script Generator

Minimal implementation for local file-based network action processing without enterprise dependencies.

## Overview

This directory contains the essential scripts needed to run a simplified version of the northbound script generator that:
- Processes network actions from local files
- Connects to ComnetsEMU for network operations
- Saves results to local JSON files
- Uses simple YAML configuration
- Has NO dependencies on PostgreSQL, Redis, InfluxDB, API Gateway, or other enterprise components

## Files

### Core Components
- `main.py` - Main entry point for processing actions
- `action_processor.py` - Core action processing logic
- `comnetsemu_connector.py` - ComnetsEMU network connectivity
- `retry_system.py` - Retry logic with exponential backoff
- `models.py` - Data models for network actions
- `history_manager.py` - Local file-based result storage
- `config_loader.py` - YAML configuration loader

### Configuration
- `config.example.yaml` - Example configuration file
- `requirements.txt` - Minimal Python dependencies (only 2!)

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy example configuration:
```bash
cp config.example.yaml config.yaml
```

3. Edit `config.yaml` with your settings:
```yaml
comnetsemu_host: localhost
comnetsemu_port: 6653
max_retries: 3
retry_delay: 2.0
timeout_seconds: 30
log_level: INFO
history_dir: data/history
actions_file: logs/actions.jsonl
```

## Usage

### Prepare Actions File

Create a file `logs/actions.jsonl` with network actions (one JSON object per line):

```json
{"id": "action-1", "type": "flow_mod", "target": "switch-1", "parameters": {"operation": "add", "match": {"in_port": 1}, "actions": [{"type": "output", "port": 2}]}, "priority": 1000, "timeout": 30}
{"id": "action-2", "type": "config_change", "target": "switch-2", "parameters": {"config_type": "qos", "bandwidth": 100}, "priority": 1000, "timeout": 30}
```

Or use JSON format `logs/actions.json`:

```json
[
  {
    "id": "action-1",
    "type": "flow_mod",
    "target": "switch-1",
    "parameters": {
      "operation": "add",
      "match": {"in_port": 1},
      "actions": [{"type": "output", "port": 2}]
    },
    "priority": 1000,
    "timeout": 30
  }
]
```

### Run the Script

```bash
python main.py
```

The script will:
1. Load configuration from `config.yaml`
2. Read actions from `logs/actions.jsonl`
3. Process each action sequentially
4. Save results to `data/history/result_<action_id>_<timestamp>.json`
5. Display summary statistics

## Output

Results are saved as JSON files in `data/history/`:

```json
{
  "action_id": "action-1",
  "status": "success",
  "timestamp": "2024-01-27T10:30:45.123456",
  "duration": 2.34,
  "message": "Action executed successfully",
  "target": "switch-1",
  "action_type": "flow_mod",
  "error": null,
  "network_state_before": {...},
  "network_state_after": {...}
}
```

## Architecture

```
┌─────────────┐
│   main.py   │  Entry point
└──────┬──────┘
       │
       ├──> config_loader.py    (Load YAML config)
       │
       ├──> action_processor.py (Process actions)
       │         │
       │         ├──> models.py (Data structures)
       │         │
       │         └──> comnetsemu_connector.py (Network ops)
       │                   │
       │                   └──> retry_system.py (Retry logic)
       │
       └──> history_manager.py  (Save results)
```

## Key Features

✅ **Minimal Dependencies**: Only 2 external packages (pyyaml, requests)
✅ **No Database**: Results stored as local JSON files
✅ **No API Gateway**: Direct file-based operation
✅ **Simple Configuration**: Single YAML file
✅ **Retry Logic**: Exponential backoff for network errors
✅ **Action Validation**: Parameter validation before execution
✅ **Error Handling**: Comprehensive error logging with stack traces

## Differences from Enterprise Version

| Feature | Enterprise Version | Simplified Version |
|---------|-------------------|-------------------|
| Storage | PostgreSQL | Local JSON files |
| Configuration | Distributed (Redis/etcd) | Single YAML file |
| API | FastAPI REST API | Direct file processing |
| Monitoring | InfluxDB + Grafana | Python logging |
| Authentication | JWT tokens | None |
| Backup | Automated backup system | Manual file backup |
| Scalability | Kubernetes deployment | Single process |
| Dependencies | 20+ packages | 2 packages |

## Troubleshooting

### ComnetsEMU Connection Failed
- Check that ComnetsEMU is running
- Verify `comnetsemu_host` and `comnetsemu_port` in config.yaml
- Check network connectivity

### Actions File Not Found
- Ensure `logs/actions.jsonl` exists
- Check `actions_file` path in config.yaml
- Verify file permissions

### History Directory Error
- Ensure write permissions for `data/history/`
- Check `history_dir` path in config.yaml
- Directory will be created automatically if it doesn't exist

## Development

To extend functionality:

1. **Add new action types**: Update `ActionType` enum in `models.py`
2. **Modify retry behavior**: Edit `RetryConfig` in `retry_system.py`
3. **Change storage format**: Modify `HistoryManager` in `history_manager.py`
4. **Add validation rules**: Update `validate_action_parameters()` in `models.py`

## Testing

Run with example actions:
```bash
# Create test actions file
echo '{"id": "test-1", "type": "flow_mod", "target": "switch-1", "parameters": {"operation": "add", "match": {}, "actions": []}, "priority": 1000, "timeout": 30}' > logs/actions.jsonl

# Run script
python main.py
```

Check results:
```bash
ls -la data/history/
cat data/history/result_test-1_*.json
```

## License

Same as parent project.
