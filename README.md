# LLM Integration Module

The LLM integration module is the core component of the intent-based networking system that uses **ChatGPT API (OpenAI)** to interpret network intents in natural language and generate appropriate configuration actions. The exclusive use of ChatGPT API ensures superior response speed and greater accuracy in intent interpretation.

## 📚 Documentation

- **[docs/](docs/)** - Complete documentation index 📖
- **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)** - Getting started guide and server startup ⚡
- **[docs/getting-started/](docs/getting-started/)** - Installation and quick start guides
- **[docs/API_USAGE.md](docs/API_USAGE.md)** - Complete guide to REST API and WebSocket usage 🌐
- **[docs/development/](docs/development/)** - Development, testing and dependencies guides 💻
- **[docs/deployment/](docs/deployment/)** - Deployment and architecture guides 🚀
- **[CHANGELOG.md](CHANGELOG.md)** - Change log and versions 📝

## Project Structure

```
├── src/                    # Source code
│   ├── models/            # Data models (Pydantic)
│   ├── services/          # Business logic services
│   ├── api/               # FastAPI routes and endpoints
│   ├── utils/             # Utilities (logging, monitoring)
│   ├── config.py          # Configuration management
│   └── main.py            # Application entry point
│
├── tests/                  # Test suite
│   ├── unit/              # Unit tests
│   ├── property/          # Property-based tests (Hypothesis)
│   ├── integration/       # End-to-end tests
│   └── mocks/             # Mocks and fixtures
│
├── docs/                   # Documentation
│   ├── getting-started/   # Installation guides
│   ├── api/               # API documentation
│   ├── deployment/        # Deployment guides
│   ├── development/       # Development guides
│   └── architecture/      # Design and requirements
│
├── deployment/             # Deployment and infrastructure
│   ├── kubernetes/        # K8s manifests
│   ├── docker/            # Dockerfile and compose
│   ├── monitoring/        # Prometheus and alerting
│   └── scripts/           # Deployment scripts
│
├── config/                 # Environment configurations
│   ├── .env.example       # Configuration template
│   ├── dev.env            # Development environment
│   ├── staging.env        # Staging environment
│   └── prod.env           # Production environment
│
├── examples/               # Examples and demos
│   ├── data/              # Sample data
│   └── *.py               # Demo scripts
│
├── cache/                  # Runtime cache
├── output/                 # Generated output
└── .kiro/                  # Kiro spec and configuration
```

## Quick Installation

### System Requirements

- Python 3.11 or higher
- pip (Python package manager)
- Internet connection to access ChatGPT API

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd llm-driven-net
   ```

2. **Install dependencies**:
   
   For normal use:
   ```bash
   pip install -r requirements.txt
   ```
   
   For development (includes testing tools, linting, etc.):
   ```bash
   pip install -r requirements-dev.txt
   ```

3. **Configure environment variables**:
   
   Copy the example file and modify it:
   ```bash
   # Windows
   copy config\.env.example .env
   
   # Linux/Mac
   cp config/.env.example .env
   ```
   
   Edit `.env` with your configurations (especially `OPENAI_API_KEY`).

4. **Start the server**:
   ```bash
   python -m src.main
   ```
   
   The server will be available at `http://localhost:8080`

For detailed instructions, see [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)

### Starting the Server

```bash
python -m src.main
```

The server will be available at:
- API: http://localhost:8080
- Metrics: http://localhost:8000
- Docs: http://localhost:8080/docs

### Quick Test

```bash
# Test health check
curl http://localhost:8080/health

# Login
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### Production

For production, use uvicorn directly:
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8080 --workers 4
```

## Testing

### Quick API Test

```bash
python tests/integration/test_api_local.py
```

### Complete Test Suite

Run all tests:
```bash
pytest
```

Run only unit tests:
```bash
pytest tests/unit/ -m unit
```

Run property-based tests:
```bash
pytest tests/property/ -m property
```

Run integration tests:
```bash
pytest tests/integration/
```

**Note**: Property-based tests may take longer to execute.

For complete details, see [tests/README.md](tests/README.md) and [docs/development/TESTING.md](docs/development/TESTING.md)

## Monitoring

The module exposes Prometheus metrics at `http://localhost:8000/metrics` (configurable).

Available metrics:
- `llm_module_intents_total`: Total number of intents processed
- `llm_module_actions_total`: Total number of actions generated
- `llm_module_processing_seconds`: Processing time per component
- `llm_module_anomalies_total`: Total number of anomalies detected

## Configuration

All configurations are managed through environment variables. See `config/.env.example` for the complete list.

### Essential Configurations

#### ChatGPT API (Required)
- `OPENAI_API_KEY`: Your OpenAI API key
- `OPENAI_MODEL`: Model to use (default: `gpt-4o-mini`)

#### Authentication (Recommended to change in production)
- `JWT_SECRET_KEY`: Secret key for JWT
- `ADMIN_PASSWORD`: Admin user password
- `OPERATOR_PASSWORD`: Operator user password
- `VIEWER_PASSWORD`: Viewer user password

#### Server
- `API_HOST`: Server host (default: `0.0.0.0`)
- `API_PORT`: Server port (default: `8080`)

### Advanced Configurations

#### ChatGPT API
- `OPENAI_MAX_TOKENS`: Maximum tokens per response (default: 2000)
- `OPENAI_TEMPERATURE`: Response creativity (0.0-1.0, default: 0.1)
- `OPENAI_RATE_LIMIT_RPM`: Maximum requests per minute (default: 60)
- `OPENAI_TIMEOUT`: Request timeout in seconds (default: 30)
- `OPENAI_MAX_RETRIES`: Maximum retries on error (default: 3)

#### Network State
- `STATE_CACHE_TTL`: Network state cache TTL (default: 300 seconds)
- `STATE_REFRESH_INTERVAL`: Automatic refresh interval (default: 60 seconds)

#### Monitoring
- `METRICS_PORT`: Port for Prometheus metrics (default: 8000)
- `ENABLE_METRICS`: Enable metrics server (default: true)

See `config/.env.example` for all available options.

## Architecture

The module follows a modular architecture with the following main components:

### Core Components

1. **Intent Parser**: Analyzes intents in natural language
2. **Context Analyzer**: Correlates intents with network state
3. **Action Generator**: Generates concrete actions via ChatGPT API
4. **Validator**: Validates and verifies action security
5. **ChatGPT Client**: Manages communication with OpenAI API with retry logic and rate limiting

### API Layer

6. **REST API**: Endpoints for intent submission and management
7. **WebSocket**: Real-time updates for connected clients
8. **Authentication**: JWT system with roles and permissions

### Infrastructure

9. **State Cache**: Thread-safe cache for network state
10. **Monitoring**: Prometheus metrics and health checks
11. **Logging**: Structured logging with correlation IDs

See [.kiro/specs/llm-integration-module/design.md](.kiro/specs/llm-integration-module/design.md) for complete details.

## REST API

The module exposes a complete REST API for network intent management.

### Main Endpoints

- `POST /api/v1/auth/login` - Authentication and JWT token retrieval
- `GET /api/v1/auth/me` - Current user information
- `POST /api/v1/intents` - Submit intent in natural language
- `GET /api/v1/intents/{id}/status` - Intent status
- `WS /api/v1/ws` - WebSocket for real-time updates
- `GET /health` - Health check
- `GET /health/ready` - Readiness check
- `GET /health/live` - Liveness check

### Interactive Documentation

Once the server is started, interactive documentation is available at:
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

### Authentication

The API uses JWT (JSON Web Tokens) for authentication. Default users:
- `admin` / `admin123` - Full access
- `operator` / `operator123` - Read and write
- `viewer` / `viewer123` - Read only

**Important**: Change default passwords in production via environment variables!

For complete details, see [docs/API_USAGE.md](docs/API_USAGE.md)

## Logging

The system uses structured logging with support for:
- JSON output for production
- Correlation ID for tracking
- Audit logging for critical events
- Configurable log levels

## Development

To contribute to the project:

1. Follow the task structure defined in `.kiro/specs/llm-integration-module/tasks.md`
2. Use Pydantic models defined in `src/models/`
3. Implement both unit and property-based tests in `tests/`
4. Maintain high test coverage
5. Follow logging and monitoring conventions

### Development Dependencies

To install development dependencies (linting, formatting, etc.):

```bash
pip install -r requirements-dev.txt
```

This includes:
- black (code formatter)
- flake8 (linter)
- mypy (type checker)
- pytest-cov (test coverage)
- And more (see requirements-dev.txt)

For complete details, see [docs/development/](docs/development/)

## Version

Current version: **0.1.0**

See [CHANGELOG.md](CHANGELOG.md) for the complete change history.

## License

This project is developed for educational and research purposes.

## Authors

@andreapedrini01

## Support

For issues or questions:
- Consult the documentation in `docs/`
- Read the [Troubleshooting Guide](docs/TROUBLESHOOTING.md) for common issues
- Check server logs for detailed errors
- Verify configuration in `.env`
- Review requirements in `requirements.txt`
- Read guides in [docs/README.md](docs/README.md)