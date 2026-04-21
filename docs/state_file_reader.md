# StateFileReader

The `StateFileReader` reads network state from JSON files with retry logic, validation, and optional file watching. It's used to load network state from disk when the collector isn't available or for testing.

## Basic Usage

```python
from llm_integration_module.services.state_file_reader import StateFileReader

reader = StateFileReader(
    cache_folder="./cache",
    state_file_name="network_state.json"
)

state = reader.load_network_state()
if state:
    print(f"Loaded {len(state.topology.switches)} switches")
```

## Retry Logic

File reads retry automatically with exponential backoff:

- Attempt 1: immediate
- Attempt 2: wait 1s
- Attempt 3: wait 2s
- Attempt 4: wait 4s
- ...up to `max_backoff` (default 32s)

Configure retries at initialization:

```python
reader = StateFileReader(
    cache_folder="./cache",
    max_retries=5,
    initial_backoff=1.0,
    max_backoff=32.0
)
```

## File Watching

The reader can monitor the state file for changes and call a callback when it's updated:

```python
def on_state_change(state):
    print(f"State updated: {len(state.topology.switches)} switches")

reader = StateFileReader(
    cache_folder="./cache",
    enable_file_watching=True,
    file_change_callback=on_state_change
)

# Watching starts automatically
# Stop when done:
reader.stop_file_watching()
```

File watching uses the `watchdog` library with 1-second debouncing to avoid duplicate triggers.

## JSON Validation

Before parsing, the reader validates that the JSON contains the required structure:

- `timestamp` — ISO format datetime
- `topology` — dict with `switches`, `links`, `hosts` (all lists)
- `flows` — list
- `metrics` — dict with `bandwidth`, `latency`, `utilization`

If validation fails, the read is retried (the file might be mid-write).

## Error Handling

`read_json_file()` returns a `FileReadResult` with details about what happened:

```python
result = reader.read_json_file()

if not result.success:
    print(f"Error: {result.error_type} — {result.error}")
    print(f"Attempts: {result.attempts}")
```

Error types: `FileNotFoundError`, `JSONDecodeError`, `ValueError`, `PermissionError`.

## File Info

Check the state file without reading it:

```python
info = reader.get_file_info()
# {'path': './cache/network_state.json', 'exists': True, 'readable': True,
#  'size_bytes': 4096, 'modified_time': '2026-04-21T10:30:00', 'age_seconds': 120.5}
```

## Thread Safety

The reader is thread-safe. File watching runs in a separate thread, and all internal state is protected by a reentrant lock.
