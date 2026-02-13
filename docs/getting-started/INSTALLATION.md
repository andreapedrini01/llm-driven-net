# Complete Installation Guide

This guide provides detailed instructions for installing and configuring the LLM Integration module on a new device.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Step-by-Step Installation](#step-by-step-installation)
3. [Configuration](#configuration)
4. [Installation Verification](#installation-verification)
5. [Troubleshooting](#troubleshooting)

## System Requirements

### Required Software

- **Python**: Version 3.11 or higher
  - Verify: `python --version` or `python3 --version`
  - Download: [python.org](https://www.python.org/downloads/)

- **pip**: Python package manager (usually included with Python)
  - Verify: `pip --version`

- **Git**: To clone the repository
  - Verify: `git --version`
  - Download: [git-scm.com](https://git-scm.com/downloads)

### Accounts and Credentials

- **OpenAI Account**: Required to obtain the API key
  - Register at: [platform.openai.com](https://platform.openai.com/signup)
  - Get API key from: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

### Internet Connection

- Required for:
  - Downloading Python dependencies
  - Communicating with ChatGPT API
  - Cloning the repository

## Step-by-Step Installation

### 1. Clone the Repository

```bash
# Clone the repository
git clone <repository-url>

# Enter the project directory
cd llm-driven-net
```

### 2. Create Virtual Environment

A virtual environment isolates project dependencies from the system.

#### Linux/macOS

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# You should see (venv) in the prompt
```

#### Windows (PowerShell)

```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\Activate.ps1

# If you get execution policy error:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# You should see (venv) in the prompt
```

#### Windows (CMD)

```cmd
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate.bat

# You should see (venv) in the prompt
```

### 3. Update pip

```bash
# Update pip to latest version
python -m pip install --upgrade pip
```

### 4. Install Dependencies

#### For Production Use

```bash
pip install -r requirements.txt
```

#### For Development (Includes Testing Tools)

```bash
pip install -r requirements-dev.txt
```

**Estimated time**: 2-5 minutes (depends on internet connection)

### 5. Verify Installed Dependencies

```bash
# List all installed dependencies
pip list

# Verify specific dependencies
pip show fastapi openai hypothesis pytest
```

You should see:
- `fastapi` >= 0.104.1
- `openai` >= 1.54.0
- `hypothesis` >= 6.119.4
- `pytest` >= 8.3.4
- And other dependencies...

## Configuration

### 1. Create Configuration File

```bash
# Linux/macOS
cp .env.example .env

# Windows
copy .env.example .env
```

### 2. Configure ChatGPT API (REQUIRED)

Open the `.env` file with a text editor and configure:

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

**How to get the API key**:
1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Click "Create new secret key"
3. Copy the key (starts with `sk-proj-` or `sk-`)
4. Paste it in the `.env` file

**⚠️ IMPORTANT**: Never share your API key!

### 3. Configure Other Parameters (Optional)

```env
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
```

## Installation Verification

### 1. Verify ChatGPT Connection

```bash
python scripts/test_chatgpt_connection.py
```

**Expected output**:
```
✓ ChatGPT API connection successful
✓ Model: gpt-4-turbo
✓ Response time: ~2-5 seconds
```

### 2. Run Tests

```bash
# Run all tests
pytest

# Run tests with detailed output
pytest -v

# Run only unit tests (fast)
pytest tests/test_*.py -v

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

### 3. Start Application (Manual Test)

```bash
# Start server
python -m src.main

# Or with uvicorn
uvicorn src.main:app --reload
```

**Expected output**:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Open browser at `http://localhost:8000/docs` to see interactive API documentation.

## Troubleshooting

### Problem: Python not found

**Symptom**:
```
'python' is not recognized as an internal or external command
```

**Solution**:
1. Verify Python is installed: download from [python.org](https://www.python.org/downloads/)
2. During installation, select "Add Python to PATH"
3. Restart terminal
4. Try with `python3` instead of `python`

### Problem: pip not found

**Symptom**:
```
'pip' is not recognized as an internal or external command
```

**Solution**:
```bash
# Use python -m pip instead of pip
python -m pip install -r requirements.txt
```

### Problem: Error creating venv

**Symptom**:
```
Error: [Errno 13] Permission denied
```

**Solution**:
```bash
# Linux/macOS: use sudo
sudo python3 -m venv venv

# Windows: run PowerShell as administrator
```

### Problem: Execution Policy Error (Windows)

**Symptom**:
```
cannot be loaded because running scripts is disabled on this system
```

**Solution**:
```powershell
# Run in PowerShell as administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Problem: Invalid OpenAI API key

**Symptom**:
```
Error: Invalid API key provided
```

**Solution**:
1. Verify the key in `.env` file is correct
2. Check the key is active at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
3. Verify you have available credit on your OpenAI account
4. Make sure there are no spaces before/after the key in `.env` file

### Problem: Tests fail

**Symptom**:
```
ImportError: No module named 'src'
```

**Solution**:
1. Verify you're in the project root directory: `pwd` (Linux/Mac) or `cd` (Windows)
2. Verify virtual environment is activated (you should see `(venv)` in prompt)
3. Reinstall dependencies: `pip install -r requirements.txt`

### Problem: Timeout during dependency installation

**Symptom**:
```
ReadTimeoutError: HTTPSConnectionPool
```

**Solution**:
```bash
# Increase timeout
pip install -r requirements.txt --timeout=300

# Or use a faster mirror
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Problem: Version conflicts

**Symptom**:
```
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed
```

**Solution**:
```bash
# Create a new clean virtual environment
deactivate
rm -rf venv  # Linux/Mac
# or
rmdir /s venv  # Windows

# Recreate environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate  # Windows

# Reinstall
pip install -r requirements.txt
```

## Additional Support

If you encounter other problems:

1. Check logs in `logs/` (if they exist)
2. Verify complete documentation in `docs/`
3. Consult `README.md` file for general information
4. Check issues on GitHub (if available)

## Final Checklist

Before considering installation complete, verify:

- [ ] Python 3.10+ installed and working
- [ ] Virtual environment created and activated
- [ ] All dependencies installed without errors
- [ ] `.env` file created and configured
- [ ] OpenAI API key configured and valid
- [ ] ChatGPT connection test passed
- [ ] Test suite executed successfully
- [ ] Application started without errors

**Congratulations! Installation is complete.** 🎉
