# StateFileReader Documentation

## Overview

The `StateFileReader` is a comprehensive JSON file reader service for network state data with robust error handling, validation, retry logic with exponential backoff, and file watching capabilities.

## Features

- **Robust File Reading**: Read and parse JSON files with comprehensive error handling
- **Retry Logic**: Automatic retry with exponential backoff for transient failures
- **JSON Validation**: Validate JSON structure before parsing to NetworkState
- **File Watching**: Automatic detection of file changes with callback support
- **Thread-Safe**: Safe for concurrent access from multiple threads
- **Detailed Error Reporting**: Clear error messages with error types and attempt counts

## Installation

The StateFileReader requires the `watchdog` library for file watching functionality:

```bash
pip install watchdog>=3.0.0
```

## Basic Usage

### Simple File Reading

```python
from src.services.state_file_reader import StateFileReader

# Create reader
reader = StateFileReader(
    cache_folder="./cache",
    state_file_name="network_state.json"
)

# Load network state
state = reader.load_network_state()

if state:
    print(f"Loaded state with {len(state.topology.switches)} switches")
else:
    print("Failed to load state")
```

### With Custom Retry Configuration

```python
reader = StateFileReader(
    cache_folder="./cache",
    state_file_name="network_state.json",
    max_retries=5,
    initial_backoff=1.0,
    max_backoff=32.0
)

state = reader.load_network_state()
```

### File Watching

```python
def on_state_change(state):
    """Callback when state file changes."""
    print(f"State updated: {len(state.topology.switches)} switches")

reader = StateFileReader(
    cache_folder="./cache",
    state_file_name="network_state.json",
    enable_file_watching=True,
    file_change_callback=on_state_change
)

# File watching starts automatically
# Or start manually:
reader.start_file_watching()

# Stop watching when done
reader.stop_file_watching()
```

## API Reference

### StateFileReader

#### Constructor Parameters

- `cache_folder` (str): Path to cache folder containing state files (default: "./cache")
- `state_file_name` (str): Name of the state JSON file (default: "network_state.json")
- `max_retries` (int): Maximum number of retry attempts (default: 5)
- `initial_backoff` (float): Initial backoff delay in seconds (default: 1.0)
- `max_backoff` (float): Maximum backoff delay in seconds (default: 32.0)
- `enable_file_watching` (bool): Whether to enable automatic file watching (default: False)
- `file_change_callback` (Callable): Callback function when file changes (receives NetworkState)

#### Methods

##### `load_network_state(file_path: Optional[str] = None) -> Optional[NetworkState]`

Load network state from JSON file with full error handling and retry logic.

**Returns**: NetworkState object or None if loading failed

##### `read_json_file(file_path: Optional[str] = None) -> FileReadResult`

Read and parse JSON file with retry logic and exponential backoff.

**Returns**: FileReadResult with success status, data, or error information

##### `parse_to_network_state(data: Dict[str, Any]) -> NetworkState`

Parse validated JSON data to NetworkState object.

**Raises**: ValueError if data cannot be parsed

##### `start_file_watching() -> bool`

Start watching the state file for changes.

**Returns**: True if watching started successfully

##### `stop_file_watching() -> bool`

Stop watching the state file.

**Returns**: True if watching stopped successfully

##### `is_watching() -> bool`

Check if file watching is active.

**Returns**: True if watching is active

##### `get_file_info(file_path: Optional[str] = None) -> Dict[str, Any]`

Get information about the state file.

**Returns**: Dictionary with file information (exists, readable, size, modified time, age)

##### `get_file_path(file_name: Optional[str] = None) -> str`

Get full path to state file.

**Returns**: Full path to state file

### FileReadResult

Data class containing the result of a file read operation.

#### Attributes

- `success` (bool): Whether the read was successful
- `data` (Optional[Dict]): Parsed JSON data if successful
- `error` (Optional[str]): Error message if failed
- `error_type` (Optional[str]): Type of error (FileNotFoundError, JSONDecodeError, etc.)
- `attempts` (int): Number of attempts made
- `read_time` (Optional[datetime]): Time when file was successfully read

## Error Handling

The StateFileReader handles various error scenarios:

### File Not Found

```python
result = reader.read_json_file()
if not result.success and result.error_type == "FileNotFoundError":
    print(f"File not found after {result.attempts} attempts")
```

### Malformed JSON

```python
result = reader.read_json_file()
if not result.success and result.error_type == "JSONDecodeError":
    print(f"Invalid JSON: {result.error}")
```

### Invalid Structure

```python
result = reader.read_json_file()
if not result.success and result.error_type == "ValueError":
    print(f"Invalid structure: {result.error}")
```

## JSON Structure Validation

The reader validates that JSON files contain required fields:

### Required Top-Level Fields

- `timestamp`: ISO format timestamp
- `topology`: Dictionary with switches, links, hosts
- `flows`: List of flow entries
- `metrics`: Dictionary with bandwidth, latency, utilization

### Example Valid JSON

```json
{
  "timestamp": "2024-01-15T10:30:00",
  "topology": {
    "switches": [...],
    "links": [...],
    "hosts": [...]
  },
  "flows": [...],
  "slices": [...],
  "metrics": {
    "bandwidth": {...},
    "latency": {...},
    "utilization": {...}
  },
  "anomalies": [...]
}
```

## Retry Logic

The reader implements exponential backoff for retries:

1. **Initial attempt**: Immediate
2. **Retry 1**: Wait `initial_backoff` seconds (default: 1.0s)
3. **Retry 2**: Wait `initial_backoff * 2` seconds (default: 2.0s)
4. **Retry 3**: Wait `initial_backoff * 4` seconds (default: 4.0s)
5. **Continue**: Up to `max_backoff` seconds (default: 32.0s)

The backoff delay doubles with each retry until reaching `max_backoff`.

## File Watching

File watching uses the `watchdog` library to monitor file changes:

- **Debouncing**: Prevents multiple triggers for rapid changes (1 second debounce)
- **Automatic Reload**: Loads and parses updated state automatically
- **Callback Notification**: Calls user-provided callback with new NetworkState
- **Error Handling**: Gracefully handles errors during file change processing

### File Watching Limitations

- May not work reliably in all environments (containers, network drives)
- Requires file system support for change notifications
- Callback is called asynchronously in a separate thread

## Thread Safety

The StateFileReader is thread-safe for concurrent access:

- Uses `threading.RLock` for internal synchronization
- Safe to call methods from multiple threads
- File watching runs in a separate thread

## Best Practices

1. **Use file watching for real-time updates**: Enable file watching when you need automatic state updates
2. **Configure appropriate retry settings**: Adjust retry parameters based on your environment
3. **Handle None returns**: Always check if `load_network_state()` returns None
4. **Stop file watching when done**: Call `stop_file_watching()` to clean up resources
5. **Use context managers**: Consider wrapping in a context manager for automatic cleanup

## Example: Complete Integration

```python
from src.services.state_file_reader import StateFileReader
from src.services.context_analyzer import NetworkStateCache

# Create cache
cache = NetworkStateCache(
    cache_folder="./cache",
    state_file_name="network_state.json"
)

# Create reader with file watching
def on_state_update(state):
    """Update cache when file changes."""
    cache.update_state(state)
    print(f"Cache updated with state from {state.timestamp}")

reader = StateFileReader(
    cache_folder="./cache",
    state_file_name="network_state.json",
    enable_file_watching=True,
    file_change_callback=on_state_update
)

# Initial load
initial_state = reader.load_network_state()
if initial_state:
    cache.update_state(initial_state)

# File watching will automatically update cache on changes
# ... your application logic ...

# Cleanup
reader.stop_file_watching()
```

## Testing

Run the test suite:

```bash
pytest tests/test_state_file_reader.py -v
```

Run the demo:

```bash
python examples/state_file_reader_demo.py
```

## Requirements

- Python 3.8+
- watchdog >= 3.0.0
- pydantic >= 2.5.0

## Related Components

- `NetworkStateCache`: Cache for network state with TTL support
- `ContextAnalyzer`: Analyzes network state and correlates with intents
- `NetworkState`: Pydantic model for network state data
