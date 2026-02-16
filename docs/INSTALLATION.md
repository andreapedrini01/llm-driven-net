# Installation Guide

This comprehensive guide provides detailed instructions for installing and configuring the LLM Integration Module on any platform.

## Overview

This guide covers:
- System requirements and prerequisites
- Step-by-step installation for Windows, Linux, and macOS
- Environment configuration
- Installation verification
- Platform-specific notes
- Common troubleshooting scenarios

For a quick 5-10 minute setup, see the [Quick Start Guide](QUICK_START.md).

## Prerequisites

### Required Software

**Python 3.11 or higher**
- Verify installation: `python --version` or `python3 --version`
- Download from: [python.org](https://www.python.org/downloads/)
- During installation on Windows, select "Add Python to PATH"

**pip (Python package manager)**
- Usually included with Python
- Verify installation: `pip --version`
- Update to latest: `python -m pip install --upgrade pip`

**Git**
- Required to clone the repository
- Verify installation: `git --version`
- Download from: [git-scm.com](https://git-scm.com/downloads)

### Accounts and Credentials

**OpenAI Account**
- Required to obtain API key for ChatGPT integration
- Register at: [platform.openai.com](https://platform.openai.com/signup)
- Get API key from: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- Ensure you have available credits on your account

### System Resources

**Internet Connection**
- Required for downloading Python dependencies
- Required for communicating with ChatGPT API
- Required for cloning the repository

**Disk Space**
- Minimum 500 MB for dependencies and virtual environment
- Additional space for logs and cache

## Installation Steps

### 1. Clone the Repository

```bash
# Clone the repository
git clone <repository-url>

# Enter the project directory
cd llm-driven-net
```

### 2. Create Virtual Environment

A virtual environment isolates project dependencies from your system Python installation, preventing conflicts.

#### Linux/macOS

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# You should see (venv) in your terminal prompt
```

#### Windows (PowerShell)

```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\Activate.ps1

# If you get an execution policy error, run:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# You should see (venv) in your terminal prompt
```

#### Windows (Command Prompt)

```cmd
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate.bat

# You should see (venv) in your terminal prompt
```

**Note**: Always activate the virtual environment before working on the project. You'll need to reactivate it each time you open a new terminal.

### 3. Update pip

```bash
# Update pip to the latest version
python -m pip install --upgrade pip
```

### 4. Install Dependencies

#### For Production Use

```bash
pip install -r requirements.txt
```

This installs all required packages:
- **fastapi** - Web framework for building APIs
- **uvicorn** - ASGI server for running the application
- **pydantic** - Data validation and settings management
- **openai** - ChatGPT API client
- **python-jose** - JWT token authentication
- **bcrypt** - Password hashing (via passlib)
- **python-multipart** - Form data parsing
- **prometheus-client** - Metrics and monitoring
- **structlog** - Structured logging
- **hypothesis** - Property-based testing framework
- **pytest** - Testing framework
- **pytest-asyncio** - Async test support
- **httpx** - HTTP client
- **python-dotenv** - Environment variable management
- **watchdog** - File system monitoring
- **typing-extensions** - Extended type hints

#### For Development (Includes Testing and Linting Tools)

```bash
pip install -r requirements-dev.txt
```

This adds development tools:
- **black** - Code formatter
- **flake8** - Code linter
- **mypy** - Static type checker
- **pytest-cov** - Test coverage reporting
- **ipython** - Enhanced interactive Python shell

**Estimated installation time**: 2-5 minutes (depends on internet connection speed)

### 5. Verify Installed Dependencies

```bash
# List all installed packages
pip list

# Verify specific core dependencies
pip show fastapi openai hypothesis pytest
```

You should see:
- `fastapi` >= 0.104.1
- `openai` >= 1.54.0
- `hypothesis` >= 6.119.4
- `pytest` >= 8.3.4
- And other dependencies listed above

## Configuration

### 1. Create Configuration File

Copy the example environment file to create your configuration:

```bash
# Linux/macOS
cp .env.example .env

# Windows (Command Prompt)
copy .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

### 2. Configure ChatGPT API (REQUIRED)

Open the `.env` file with your preferred text editor and configure the OpenAI API settings:

```env
# === ChatGPT API Configuration (REQUIRED) ===
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4-turbo
OPENAI_MAX_TOKENS=2000
OPENAI_TEMPERATURE=0.1
OPENAI_RATE_LIMIT_RPM=60
OPENAI_TIMEOUT=30
OPENAI_MAX_RETRIES=3
```

**How to get your API key**:
1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Click "Create new secret key"
3. Copy the key (starts with `sk-proj-` or `sk-`)
4. Paste it into the `.env` file, replacing the placeholder

**⚠️ IMPORTANT SECURITY NOTES**:
- Never share your API key publicly
- Never commit the `.env` file to version control
- The `.env` file is already in `.gitignore` to prevent accidental commits
- Ensure there are no spaces before or after the key

### 3. Configure Application Settings (Optional)

```env
# === API Server Configuration ===
API_HOST=0.0.0.0
API_PORT=8080

# === Authentication ===
JWT_SECRET_KEY=your-secure-random-key-here
ADMIN_PASSWORD=admin123
OPERATOR_PASSWORD=operator123
VIEWER_PASSWORD=viewer123

# === RYU Controller ===
RYU_HOST=localhost
RYU_PORT=8080
RYU_API_BASE=/api/v1

# === Northbound Script ===
NORTHBOUND_HOST=localhost
NORTHBOUND_PORT=9090

# === Cache Configuration ===
STATE_CACHE_TTL=300
STATE_CACHE_MAX_SIZE=1000

# === Anomaly Detection ===
ANOMALY_DETECTION_ENABLED=true
ANOMALY_THRESHOLD=0.8

# === Logging ===
LOG_LEVEL=INFO
LOG_FORMAT=json
DEBUG=false
```

**Configuration Notes**:
- Change default passwords for production deployments
- Generate a secure JWT secret key (use a random string generator)
- The default port is 8080 for consistency across the application
- Adjust cache and rate limit settings based on your needs

### 4. Set Up Network State (Optional)

The module can read network state from a JSON file. To set this up:

```bash
# Create the cache directory
mkdir cache
```

Create `cache/network_state.json` with sample data:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "topology": {
    "switches": [
      {
        "id": "s1",
        "name": "Core Switch 1",
        "status": "active",
        "ports": []
      }
    ],
    "links": [],
    "hosts": []
  },
  "flows": [],
  "slices": [],
  "metrics": {
    "bandwidth": {},
    "latency": {},
    "utilization": {}
  },
  "anomalies": []
}
```

## Verification

### 1. Verify ChatGPT Connection

Test that your API key is configured correctly:

```bash
python scripts/test_chatgpt_connection.py
```

**Expected output**:
```
✓ ChatGPT API connection successful
✓ Model: gpt-4-turbo
✓ Response time: ~2-5 seconds
```

If this fails, verify:
- Your API key is correct in `.env`
- You have available credits on your OpenAI account
- Your internet connection is working
- The OpenAI API is operational: [status.openai.com](https://status.openai.com)

### 2. Run Test Suite

```bash
# Run all tests
pytest

# Run tests with detailed output
pytest -v

# Run only unit tests (fast)
pytest tests/test_*.py -k "not properties"

# Run property-based tests (slower)
pytest tests/test_*_properties.py -v
```

**Expected output**:
```
==================== test session starts ====================
collected XX items

tests/test_action_sequencer.py .................. [100%]
tests/test_chatgpt_client.py .................... [100%]
...

==================== XX passed in X.XXs ====================
```

### 3. Start the Application

```bash
# Method 1: Direct Python execution
python -m src.main

# Method 2: Using uvicorn with auto-reload (development)
uvicorn src.main:app --reload --host 0.0.0.0 --port 8080

# Method 3: Using uvicorn (production)
uvicorn src.main:app --host 0.0.0.0 --port 8080
```

**Expected output**:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
```

### 4. Access API Documentation

Open your browser and navigate to:
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

### 5. Test API Endpoints

```bash
# Test health endpoint
curl http://localhost:8080/health

# Expected response:
# {"status": "healthy", "version": "1.0.0", "components": {"api": "healthy"}}

# Test login endpoint
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Expected response:
# {"access_token": "eyJhbGc...", "token_type": "bearer", "expires_in": 3600}
```

## Platform-Specific Notes

### Windows

**PowerShell Execution Policy**:
If you encounter script execution errors, you may need to adjust the execution policy:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**bcrypt Installation Issues**:
If bcrypt fails to install, you may need Visual C++ Build Tools:
1. Download from [Microsoft](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
2. Or use pre-built wheels:
   ```bash
   pip install --only-binary :all: bcrypt cryptography
   ```

**Path Separators**:
Windows uses backslashes (`\`) for paths, but Python accepts forward slashes (`/`) on all platforms. The documentation uses forward slashes for consistency.

### Linux

**System Dependencies**:
Some packages may require system libraries:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install build-essential libssl-dev libffi-dev python3-dev

# Fedora/RHEL
sudo dnf install gcc openssl-devel libffi-devel python3-devel

# Arch Linux
sudo pacman -S base-devel openssl libffi
```

**Permission Issues**:
If you encounter permission errors:
```bash
# Option 1: Install to user directory
pip install --user -r requirements.txt

# Option 2: Use virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### macOS

**Xcode Command Line Tools**:
Some dependencies require compilation tools:
```bash
xcode-select --install
```

**Python Version**:
macOS may have Python 2.7 pre-installed. Ensure you're using Python 3.11+:
```bash
# Check version
python3 --version

# Use python3 explicitly
python3 -m venv venv
```

**Homebrew Python**:
If you installed Python via Homebrew:
```bash
# Homebrew Python location
which python3

# Should show: /usr/local/bin/python3 or /opt/homebrew/bin/python3
```

## Troubleshooting

### Python Not Found

**Symptom**:
```
'python' is not recognized as an internal or external command
```

**Solutions**:
1. Verify Python is installed: `python --version` or `python3 --version`
2. If not installed, download from [python.org](https://www.python.org/downloads/)
3. During installation, select "Add Python to PATH"
4. Restart your terminal after installation
5. Try using `python3` instead of `python` (Linux/macOS)

### pip Not Found

**Symptom**:
```
'pip' is not recognized as an internal or external command
```

**Solutions**:
```bash
# Use python -m pip instead of pip
python -m pip install -r requirements.txt

# Or install pip
python -m ensurepip --upgrade
```

### Virtual Environment Creation Fails

**Symptom**:
```
Error: [Errno 13] Permission denied
```

**Solutions**:
```bash
# Linux/macOS: Check permissions
ls -la
chmod +x .

# Windows: Run terminal as administrator

# Alternative: Install venv module
python -m pip install virtualenv
python -m virtualenv venv
```

### Execution Policy Error (Windows)

**Symptom**:
```
cannot be loaded because running scripts is disabled on this system
```

**Solution**:
```powershell
# Run PowerShell as administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Or use Command Prompt instead of PowerShell
```

### Invalid OpenAI API Key

**Symptom**:
```
Error: Invalid API key provided
```

**Solutions**:
1. Verify the key in `.env` is correct (no spaces, complete key)
2. Check the key is active at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
3. Verify you have available credits on your OpenAI account
4. Ensure the key starts with `sk-proj-` or `sk-`
5. Try regenerating the API key

### Dependency Installation Timeout

**Symptom**:
```
ReadTimeoutError: HTTPSConnectionPool
```

**Solutions**:
```bash
# Increase timeout
pip install -r requirements.txt --timeout=300

# Use a different mirror (example: China mirror)
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# Install packages one at a time
pip install fastapi uvicorn pydantic openai
```

### Version Conflicts

**Symptom**:
```
ERROR: pip's dependency resolver does not currently take into account all the packages
```

**Solutions**:
```bash
# Create a fresh virtual environment
deactivate

# Linux/macOS
rm -rf venv
python3 -m venv venv
source venv/bin/activate

# Windows
rmdir /s venv
python -m venv venv
venv\Scripts\activate

# Reinstall dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Tests Fail with Import Errors

**Symptom**:
```
ImportError: No module named 'src'
```

**Solutions**:
1. Verify you're in the project root directory:
   ```bash
   pwd  # Linux/macOS
   cd   # Windows
   ```
2. Verify virtual environment is activated (you should see `(venv)` in prompt)
3. Reinstall dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Verify Python path:
   ```bash
   python -c "import sys; print(sys.path)"
   ```

### Port Already in Use

**Symptom**:
```
Error: [Errno 48] Address already in use
```

**Solutions**:
```bash
# Find process using port 8080
# Linux/macOS
lsof -i :8080
kill -9 <PID>

# Windows
netstat -ano | findstr :8080
taskkill /PID <PID> /F

# Or use a different port
uvicorn src.main:app --port 8081
```

### bcrypt/cryptography Installation Issues

**Windows**:
```bash
# Install Visual C++ Build Tools, or use pre-built wheels
pip install --only-binary :all: bcrypt cryptography
```

**Linux**:
```bash
# Install system dependencies
sudo apt-get install build-essential libssl-dev libffi-dev python3-dev
pip install -r requirements.txt
```

**macOS**:
```bash
# Install Xcode Command Line Tools
xcode-select --install
pip install -r requirements.txt
```

## Final Installation Checklist

Before considering installation complete, verify:

- [ ] Python 3.11+ installed and accessible
- [ ] Virtual environment created and activated
- [ ] All dependencies installed without errors (`pip list` shows all packages)
- [ ] `.env` file created and configured
- [ ] OpenAI API key set in `.env`
- [ ] ChatGPT connection test passed
- [ ] Test suite executed successfully
- [ ] Application starts without errors
- [ ] API documentation accessible at http://localhost:8080/docs
- [ ] Health endpoint returns successful response

## Next Steps

After successful installation:

1. **Quick Start**: Follow the [Quick Start Guide](QUICK_START.md) for a rapid introduction
2. **API Usage**: Read the [API Usage Guide](API_USAGE.md) for detailed API documentation
3. **Deployment**: See the [Deployment Guide](deployment/DEPLOYMENT_GUIDE.md) for production deployment
4. **Dependencies**: Review [Dependencies](development/DEPENDENCIES.md) for detailed dependency information
5. **Troubleshooting**: Consult [Troubleshooting Guide](TROUBLESHOOTING.md) for common issues

## Additional Support

If you encounter issues not covered in this guide:

1. Check application logs in the console output
2. Review the [Troubleshooting Guide](TROUBLESHOOTING.md)
3. Consult the [Dependencies Guide](development/DEPENDENCIES.md) for dependency-specific issues
4. Verify your configuration in `.env`
5. Check the [Deployment Guide](deployment/DEPLOYMENT_GUIDE.md) for production setup issues

**Congratulations! Your installation is complete.** 🎉
