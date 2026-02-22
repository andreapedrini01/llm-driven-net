# Northbound Script Generator - Standalone Module

This is a self-contained module that can be integrated into larger projects. All dependencies are included within this folder.

## Structure

```
northbound_script_generator/
├── src/                    # Source code modules
│   ├── api/               # API Gateway and routes
│   ├── backup/            # Backup and recovery system
│   ├── config/            # Configuration management
│   ├── connectors/        # RYU and ComnetsEMU connectors
│   ├── core/              # Core functionality (retry system, etc.)
│   ├── logging/           # Logging and aggregation
│   ├── models/            # Data models
│   ├── monitoring/        # Monitoring and metrics
│   ├── orchestrator/      # System orchestration
│   └── scalability/       # Scalability features
├── config/                # Configuration files
│   ├── backup_config.example.yaml
│   └── system_config.example.yaml
├── logs/                  # Log files (created at runtime)
├── main.py               # Alternative entry point
├── start_system.py       # Primary entry point (recommended)
├── run_api_gateway.py    # API Gateway standalone
├── northbound_script.py  # Legacy script
├── validate_implementation.py  # Validation script
├── requirements.txt      # Python dependencies
├── .env.example         # Environment variables template
└── README.md            # Module documentation
```

## Installation

### 1. Install Dependencies

```bash
cd northbound_script_generator
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
```

### 3. Configure System

```bash
# Copy configuration templates
cp config/system_config.example.yaml config/system_config.yaml
cp config/backup_config.example.yaml config/backup_config.yaml

# Edit configuration files as needed
```

## Usage

### Start the Complete System

```bash
cd northbound_script_generator
python start_system.py
```

This starts:
- Northbound Script Generator
- API Gateway (http://localhost:8000)
- Monitoring Service
- All integrated components

### Start API Gateway Only

```bash
cd northbound_script_generator
python run_api_gateway.py
```

### Use as Python Module

```python
# From parent directory
from northbound_script_generator import NorthboundScript

# Create instance
northbound = NorthboundScript(
    ryu_host="localhost",
    ryu_port=8080
)

# Process LLM output
result = northbound.process_llm_output(llm_json_output)
```

## Integration into Larger Projects

### Option 1: As a Submodule

```bash
# In your main project
git submodule add <repo-url> modules/northbound_script_generator
```

### Option 2: Copy the Folder

```bash
# Copy entire folder into your project
cp -r northbound_script_generator /path/to/your/project/modules/
```

### Option 3: Install as Package

```bash
# From the northbound_script_generator directory
pip install -e .
```

## Importing in Your Project

```python
# If placed in a modules/ folder
from modules.northbound_script_generator import NorthboundScript
from modules.northbound_script_generator.src.api.gateway_app import create_app

# Use the components
northbound = NorthboundScript()
app = create_app(northbound_instance=northbound)
```

## Configuration

All configuration is self-contained within this module:

- **System Config**: `config/system_config.yaml`
- **Backup Config**: `config/backup_config.yaml`
- **Environment**: `.env` file
- **Logs**: `logs/` directory (auto-created)

## Dependencies

All Python dependencies are listed in `requirements.txt`. The module requires:

- Python 3.8+
- FastAPI
- Uvicorn
- SQLAlchemy
- And other dependencies (see requirements.txt)

## Testing

```bash
# Run tests from parent directory
python tests/test_basic.py
```

## API Documentation

Once started, access API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Prometheus Metrics: http://localhost:8000/metrics

## Ports Used

- **8000**: API Gateway
- **8080**: RYU Controller (external)
- **6653**: ComnetsEMU (external)

## Troubleshooting

### Module Import Errors

If you get import errors, ensure you're running from the correct directory:

```bash
# Run from within the module
cd northbound_script_generator
python start_system.py

# Or run from parent with proper Python path
PYTHONPATH=. python northbound_script_generator/start_system.py
```

### Configuration Not Found

Ensure configuration files exist:

```bash
ls config/system_config.yaml
ls config/backup_config.yaml
```

If missing, copy from examples:

```bash
cp config/system_config.example.yaml config/system_config.yaml
cp config/backup_config.example.yaml config/backup_config.yaml
```

### Port Already in Use

If port 8000 is in use, modify the port in `start_system.py`:

```python
config = uvicorn.Config(
    self.app,
    host="0.0.0.0",
    port=8001,  # Change this
    ...
)
```

## License

[Your License Here]

## Support

For issues and questions, please refer to the main project documentation.
