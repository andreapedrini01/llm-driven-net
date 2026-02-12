# Quick Start Guide

Quick guide to get started with the LLM Integration module in 5 minutes.

## Prerequisites

- Python 3.10 or higher
- OpenAI account with API key

## Quick Installation

### Linux/macOS

```bash
# 1. Clone and enter directory
git clone <repository-url>
cd llm-driven-net

# 2. Run automatic setup script
chmod +x setup.sh
./setup.sh

# 3. Configure your API key in .env file
nano .env  # or use your preferred editor
```

### Windows

```cmd
REM 1. Clone and enter directory
git clone <repository-url>
cd llm-driven-net

REM 2. Run automatic setup script
setup.bat

REM 3. Configure your API key in .env file
notepad .env
```

### Manual Installation

If you prefer to install manually:

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure .env
cp .env.example .env  # Linux/Mac
copy .env.example .env  # Windows

# 5. Edit .env with your API key
```

## API Key Configuration

1. Get an API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. Open the `.env` file
3. Replace `your-api-key-here` with your key:

```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4-turbo
```

## Installation Verification

```bash
# Verify everything is configured correctly
python scripts/verify_installation.py
```

Expected output:
```
✓ Python 3.12.4 (>= 3.10 required)
✓ fastapi installed
✓ openai installed
...
✓ Installation complete and correct!
```

## Run Tests

```bash
# Run all tests
pytest

# Run tests with detailed output
pytest -v

# Run only unit tests (fast)
pytest tests/test_*.py -k "not properties"
```

## Start Application

```bash
# Method 1: Directly with Python
python -m src.main

# Method 2: With uvicorn (recommended for development)
uvicorn src.main:app --reload

# Method 3: With uvicorn (production)
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

The application will be available at:
- API: http://localhost:8000
- Interactive documentation: http://localhost:8000/docs
- Alternative documentation: http://localhost:8000/redoc

## Quick Test

### Test ChatGPT Connection

```bash
python scripts/test_chatgpt_connection.py
```

### Test API (with curl)

```bash
# Health check
curl http://localhost:8000/health

# Example request (to be implemented)
curl -X POST http://localhost:8000/api/v1/intents \
  -H "Content-Type: application/json" \
  -d '{"text": "Create a flow from switch-1 to switch-2"}'
```

## Project Structure

```
llm-driven-net/
├── src/                    # Source code
│   ├── models/            # Data models
│   ├── services/          # Business logic
│   ├── api/              # API endpoints
│   └── main.py           # Entry point
├── tests/                 # Test suite
├── scripts/              # Utility scripts
├── .env                  # Configuration (to create)
├── requirements.txt      # Production dependencies
└── README.md            # Complete documentation
```

## Useful Commands

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Deactivate virtual environment
deactivate

# Update dependencies
pip install --upgrade -r requirements.txt

# Check outdated dependencies
pip list --outdated

# Run linting (if you installed requirements-dev.txt)
flake8 src/
black src/ --check

# Format code
black src/

# Type checking
mypy src/

# Test coverage
pytest --cov=src tests/
```

## Next Steps

1. **Read complete documentation**: `README.md`
2. **Consult detailed installation guide**: `INSTALL.md`
3. **Explore project specifications**: `.kiro/specs/llm-integration-module/`
4. **Contribute**: Follow tasks in `tasks.md`

## Quick Troubleshooting

### Python not found
```bash
# Verify installation
python --version
python3 --version

# If not installed, download from python.org
```

### pip not found
```bash
# Use python -m pip instead of pip
python -m pip install -r requirements.txt
```

### API key error
```bash
# Verify .env exists and contains the key
cat .env | grep OPENAI_API_KEY  # Linux/Mac
type .env | findstr OPENAI_API_KEY  # Windows

# Verify key is valid at platform.openai.com
```

### Tests fail
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Verify installation
python scripts/verify_installation.py
```

## Support

For problems or questions:

1. Consult `INSTALL.md` for detailed instructions
2. Consult `DEPENDENCIES.md` for dependency issues
3. Run `python scripts/verify_installation.py` for diagnostics
4. Check logs in `logs/` (if they exist)

## Resources

- **OpenAI Documentation**: [platform.openai.com/docs](https://platform.openai.com/docs)
- **FastAPI Docs**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **Hypothesis Docs**: [hypothesis.readthedocs.io](https://hypothesis.readthedocs.io)

---

**Happy coding! 🚀**
