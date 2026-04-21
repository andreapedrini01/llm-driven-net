# LLM Integration Module

The LLM integration module is the core component of the intent-based networking system that uses **ChatGPT API (OpenAI)** to interpret network intents in natural language and generate appropriate configuration actions.

## 📚 Documentation

- **[Quick Start Guide](docs/QUICK_START.md)** - Get started in 5-10 minutes ⚡
- **[Installation Guide](docs/INSTALLATION.md)** - Complete installation instructions 📦
- **[API Usage Guide](docs/API_USAGE.md)** - REST API and WebSocket documentation 🌐
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions 🔧
- **[Deployment Guide](docs/deployment/DEPLOYMENT_GUIDE.md)** - Production deployment �
- **[Architecture](docs/deployment/ARCHITECTURE.md)** - System design and architecture 🏗️
- **[Development Guide](docs/development/)** - Testing, dependencies, and development �

## Quick Start

### Prerequisites
- Python 3.11 or higher
- OpenAI API key

### Installation

```bash
# Clone and navigate to the repository
git clone <repository-url>
cd llm-driven-net

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp config/.env.example .env
# Edit .env and add your OPENAI_API_KEY

# Start the server
python -m src.main
```

The server will be available at:
- **API**: http://localhost:8080
- **Docs**: http://localhost:8080/docs
- **Metrics**: http://localhost:8000

For detailed instructions, see the [Quick Start Guide](docs/QUICK_START.md) or [Installation Guide](docs/INSTALLATION.md).

## Key Features

- **Natural Language Processing**: Interpret network intents using ChatGPT API
- **REST API & WebSocket**: Complete API for intent management and real-time updates
- **Authentication & Authorization**: JWT-based security with role-based access control
- **Monitoring**: Prometheus metrics and health checks
- **Production Ready**: Docker support, Kubernetes manifests, and deployment guides

## Project Structure

```
├── llm_integration_module/                    # Source code
├── tests_llm_module/       # Test suite (unit, property-based, integration)
├── docs/                   # Complete documentation
├── deployment/             # Kubernetes, Docker, monitoring
├── config/                 # Environment configurations
└── examples/               # Usage examples
```

## API Overview

Main endpoints:
- `POST /api/v1/auth/login` - Authentication
- `POST /api/v1/intents` - Submit network intent
- `GET /api/v1/intents/{id}/status` - Check intent status
- `WS /api/v1/ws` - WebSocket for real-time updates
- `GET /health` - Health check

Interactive documentation available at http://localhost:8080/docs

For complete API documentation, see [API Usage Guide](docs/API_USAGE.md).

## Configuration

Essential environment variables:
- `OPENAI_API_KEY` - Your OpenAI API key (required)
- `OPENAI_MODEL` - Model to use (default: gpt-4o-mini)
- `API_PORT` - Server port (default: 8080)
- `JWT_SECRET_KEY` - Secret for JWT tokens

See `config/.env.example` for all available options and [Installation Guide](docs/INSTALLATION.md) for configuration details.

## Testing

```bash
# Run all tests
pytest

# Run specific test types
pytest tests_llm_module/unit/           # Unit tests
pytest tests_llm_module/property/       # Property-based tests
pytest tests_llm_module/integration/    # Integration tests
```

For complete testing documentation, see [Testing Guide](docs/development/TESTING.md).

## Support

For issues or questions:
- Check the [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
- Review the [documentation](docs/)
- Check server logs for detailed errors

## Version

Current version: **0.1.0**

See [CHANGELOG.md](CHANGELOG.md) for the complete change history.

## License

This project is developed for educational and research purposes.

## Authors

@andreapedrini01
