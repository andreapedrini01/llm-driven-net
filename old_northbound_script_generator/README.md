# Northbound Script Generator - Root Scripts

This folder contains the main entry point scripts for the Northbound Script Generator system.

## Files

### start_system.py
**Primary entry point** for starting the complete integrated system.

**Usage:**
```bash
python northbound_script_generator/start_system.py
```

**What it does:**
- Starts the System Orchestrator
- Initializes all services (API Gateway, Monitoring, Backup, etc.)
- Manages service lifecycle and dependencies
- Provides graceful shutdown

**Use this for:** Production deployments and normal operation

---

### main.py
Alternative entry point for the Northbound Module.

**Usage:**
```bash
python northbound_script_generator/main.py
```

**What it does:**
- Starts the Northbound Module directly
- Simpler startup without full orchestration

**Use this for:** Development and testing

---

### run_api_gateway.py
Standalone API Gateway entry point.

**Usage:**
```bash
python northbound_script_generator/run_api_gateway.py
```

**What it does:**
- Starts only the API Gateway service
- Useful for microservices deployment

**Use this for:** Running API Gateway independently

---

### northbound_script.py
Legacy/standalone northbound script.

**Usage:**
```bash
python northbound_script_generator/northbound_script.py
```

**What it does:**
- Original northbound script implementation
- May be deprecated in favor of start_system.py

**Use this for:** Legacy compatibility or specific use cases

---

### validate_implementation.py
Implementation validation script.

**Usage:**
```bash
python northbound_script_generator/validate_implementation.py
```

**What it does:**
- Validates that all modules are properly implemented
- Checks imports and dependencies
- Verifies system integrity

**Use this for:** Testing and validation after changes

---

## Recommended Usage

For most use cases, use **start_system.py**:

```bash
# From project root
python northbound_script_generator/start_system.py

# Or create a convenience script at root
```

## Note

These files were moved from the project root to improve organization. If you need to run them from the root directory, you can:

1. **Create wrapper scripts** at the root
2. **Update your PATH** to include this directory
3. **Use absolute paths** when running

Example wrapper script at root (`start.py`):
```python
#!/usr/bin/env python3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import and run
from northbound_script_generator.start_system import main
main()
```
