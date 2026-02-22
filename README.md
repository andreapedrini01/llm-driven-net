# LLM-Driven Network - Northbound Script Generator

Intent-based SDN network management using Large Language Models (LLMs) with RYU and ComnetsEMU controllers.

## Overview

The Northbound Script Generator is a production-ready system that translates high-level network intents (expressed in natural language or structured JSON) into low-level SDN controller commands. It provides a bridge between LLM-generated network policies and actual network infrastructure.

## Key Features

- **LLM-to-SDN Translation**: Converts natural language or JSON intents into OpenFlow rules
- **Multi-Controller Support**: Works with both RYU and ComnetsEMU controllers
- **Advanced Retry System**: Persistent action queues with exponential backoff
- **Safety Validation**: Prevents dangerous network configurations
- **Rollback Capabilities**: Automatic rollback on failures
- **REST API**: Full-featured API Gateway with authentication
- **Monitoring**: Prometheus metrics, InfluxDB storage, Grafana dashboards
- **Backup System**: Automated configuration backups with retention policies
- **Scalability**: Connection pooling, rate limiting, load balancing
- **Web Dashboard**: React-based frontend for visualization and control

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Start the entire stack
docker-compose up -d

# With monitoring
docker-compose --profile monitoring up -d

# Access services
# API Gateway: http://localhost:8000
# Frontend: http://localhost:3000
# Grafana: http://localhost:3001
```

### Option 2: Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start the system
python start.py

# Or use the integrated system
python northbound_script_generator/start_system.py
```

### Option 3: Standalone Module

```bash
# The northbound_script_generator folder is self-contained
cd northbound_script_generator
pip install -r requirements.txt
python start_system.py
```

## Project Structure

```
llm-driven-net/
├── northbound_script_generator/    # Self-contained module
│   ├── src/                        # All source code
│   ├── config/                     # Configuration files
│   └── *.py                        # Entry points
├── src/                            # Shared source code
│   ├── api/                        # API Gateway
│   ├── connectors/                 # RYU & ComnetsEMU
│   ├── monitoring/                 # Metrics & alerts
│   └── ...
├── frontend/                       # React dashboard
├── tests/                          # Test suite
├── docs/                           # Documentation
├── deployment/                     # Kubernetes, Docker configs
├── demos/                          # Example scripts
└── scripts/                        # Utility scripts
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - System architecture and design
- [API Reference](docs/API_REFERENCE.md) - REST API documentation
- [Action Package Guide](docs/ACTION_PACKAGE_GUIDE.md) - Input format specification
- [Deployment](docs/DEPLOYMENT.md) - Deployment instructions
- [Operations](docs/OPERATIONS.md) - Operations and troubleshooting
- [Standalone Module](docs/STANDALONE_MODULE.md) - Using as standalone module

## Usage Examples

### Python API

```python
from northbound_script_generator import NorthboundScript

# Initialize
northbound = NorthboundScript(
    ryu_host="localhost",
    ryu_port=8080
)

# Process LLM output
action_package = {
    "id": "seq_001",
    "intent_id": "block_attacker",
    "actions": [{
        "type": "flow_mod",
        "target": "switch-1",
        "parameters": {
            "operation": "add",
            "match": {"ip_src": "192.168.1.100"},
            "actions": ["drop"]
        }
    }]
}

result = northbound.process_llm_output(json.dumps(action_package))
```

### REST API

```bash
# Health check
curl http://localhost:8000/health

# Execute action sequence
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d @action_package.json

# Get system status
curl http://localhost:8000/api/v1/status
```

### CLI

```bash
# Validate action package
python scripts/validate_action_package.py action_package.json

# Run tests
python scripts/run_tests.py

# Benchmark performance
python scripts/benchmark.py
```

## Testing

```bash
# Run basic tests
python tests/test_basic.py

# Run full test suite
python scripts/run_tests.py

# Verify standalone module
python scripts/verify_standalone_module.py
```

## Development

### Prerequisites

- Python 3.8+
- Docker & Docker Compose (for containerized deployment)
- RYU Controller (for SDN operations)
- ComnetsEMU (optional, for network emulation)

### Setup Development Environment

```bash
# Clone repository
git clone <repository-url>
cd llm-driven-net

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Configure system
cp config/system_config.example.yaml config/system_config.yaml
```

### Running Tests

```bash
# Unit tests
pytest tests/

# Integration tests
pytest tests/integration/

# With coverage
pytest --cov=src --cov-report=html
```

## Deployment

### Docker Deployment

See [docker-compose.yml](docker-compose.yml) for full stack configuration.

### Kubernetes Deployment

```bash
# Apply configurations
kubectl apply -f deployment/kubernetes/

# Check status
kubectl get pods -n northbound
```

See [deployment/README.md](deployment/README.md) for detailed instructions.

## Monitoring

The system includes comprehensive monitoring:

- **Prometheus**: Metrics collection (port 9090)
- **Grafana**: Visualization dashboards (port 3001)
- **InfluxDB**: Time-series storage (port 8086)
- **Built-in Metrics**: `/metrics` endpoint on API Gateway

## Configuration

### Environment Variables

See [.env.example](.env.example) for all available environment variables.

### Configuration Files

- `config/system_config.yaml` - Main system configuration
- `config/backup_config.yaml` - Backup system configuration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

[Your License Here]

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check the [documentation](docs/)
- Review [operations guide](docs/OPERATIONS.md)

## Acknowledgments

Built with:
- [RYU SDN Controller](https://ryu-sdn.org/)
- [ComnetsEMU](https://git.comnets.net/public-repo/comnetsemu)
- [FastAPI](https://fastapi.tiangolo.com/)
- [React](https://reactjs.org/)
- [Prometheus](https://prometheus.io/)
- [Grafana](https://grafana.com/)

---

**Status**: Production Ready  
**Version**: 1.0.0  
**Last Updated**: February 2026
