# Troubleshooting Guide

Complete guide to solve common problems with the LLM Integration Module.

## 📋 Table of Contents

- [Installation Problems](#installation-problems)
- [Startup Problems](#startup-problems)
- [API Problems](#api-problems)
- [ChatGPT Problems](#chatgpt-problems)
- [Database/Cache Problems](#databasecache-problems)
- [Testing Problems](#testing-problems)
- [Deployment Problems](#deployment-problems)
- [Performance Problems](#performance-problems)

## 🔧 Installation Problems

### Error: "ModuleNotFoundError"

**Symptom**:
```
ModuleNotFoundError: No module named 'fastapi'
```

**Cause**: Dependencies not installed

**Solution**:
```bash
# Reinstall dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep fastapi

# If still having problems, use virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### Error: "bcrypt installation failed"

**Symptom**:
```
error: Microsoft Visual C++ 14.0 or greater is required
```

**Cause**: Missing build tools for bcrypt

**Windows Solution**:
```bash
# Option 1: Install Visual C++ Build Tools
# Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/

# Option 2: Use precompiled wheel
pip install --only-binary :all: bcrypt
```

**Linux Solution**:
```bash
# Ubuntu/Debian
sudo apt-get install build-essential libssl-dev libffi-dev python3-dev

# CentOS/RHEL
sudo yum install gcc openssl-devel libffi-devel python3-devel

# Then reinstall
pip install -r requirements.txt
```

### Error: "cryptography installation failed"

**Symptom**:
```
error: can not find Rust compiler
```

**Cause**: Old pip version or missing build tools

**Solution**:
```bash
# Update pip
python -m pip install --upgrade pip

# Reinstall
pip install cryptography

# If still having problems, install Rust
# Windows: https://rustup.rs/
# Linux: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

## 🚀 Startup Problems

### Server won't start

**Symptom**:
```
Error: [Errno 10048] Only one usage of each socket address
```

**Cause**: Port 8080 already in use

**Solution**:
```bash
# Windows: Find process on port
netstat -ano | findstr :8080
taskkill /PID <PID> /F

# Linux/Mac
lsof -i :8080
kill -9 <PID>

# Or use different port
uvicorn src.main:app --port 8081
```

### Error: "OPENAI_API_KEY not found"

**Symptom**:
```
ValueError: OPENAI_API_KEY not configured
```

**Cause**: Environment variable not configured

**Solution**:
```bash
# Verify .env exists
ls .env  # Windows: dir .env

# If doesn't exist, copy template
copy config\.env.example .env  # Windows
cp config/.env.example .env    # Linux/Mac

# Edit .env and add:
OPENAI_API_KEY=sk-your-actual-key-here

# Restart server
python -m src.main
```

### Error: "Cannot import name 'app'"

**Symptom**:
```
ImportError: cannot import name 'app' from 'src.main'
```

**Cause**: Syntax error in src/main.py or circular dependencies

**Solution**:
```bash
# Verify syntax
python -m py_compile src/main.py

# Check circular imports
python -c "import src.main"

# Verify PYTHONPATH
echo %PYTHONPATH%  # Windows
echo $PYTHONPATH   # Linux/Mac

# If necessary, add root to path
set PYTHONPATH=%CD%  # Windows
export PYTHONPATH=$(pwd)  # Linux/Mac
```

## 🌐 API Problems

### 401 Unauthorized

**Symptom**:
```json
{"detail": "Not authenticated"}
```

**Cause**: Missing or expired JWT token

**Solution**:
```bash
# 1. Get new token
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 2. Use token in requests
curl -X GET http://localhost:8080/api/v1/intents \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"

# 3. Verify token not expired (default: 60 minutes)
# If expired, request new token
```

### 403 Forbidden

**Symptom**:
```json
{"detail": "Insufficient permissions"}
```

**Cause**: User doesn't have necessary permissions

**Solution**:
```bash
# Verify user role
curl -X GET http://localhost:8080/api/v1/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN"

# Use user with correct permissions:
# - admin: all permissions
# - operator: read + write
# - viewer: read only

# Login as admin
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### 422 Unprocessable Entity

**Symptom**:
```json
{"detail": [{"loc": ["body", "text"], "msg": "field required"}]}
```

**Cause**: Invalid request data

**Solution**:
```bash
# Verify request format
# Correct example for submit intent:
curl -X POST http://localhost:8080/api/v1/intents \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Create network slice for IoT",
    "user_id": "admin",
    "priority": 5
  }'

# Check API documentation
# http://localhost:8080/docs
```

### 500 Internal Server Error

**Symptom**:
```json
{"detail": "Internal server error"}
```

**Cause**: Server error

**Solution**:
```bash
# 1. Check server logs
# Look for traceback and error message

# 2. Verify configuration
cat .env  # Linux/Mac
type .env  # Windows

# 3. Verify dependencies
pip list

# 4. Test with simple data
curl -X GET http://localhost:8080/health

# 5. If persists, enable debug
# In .env:
DEBUG=true
LOG_LEVEL=DEBUG
```

## 🤖 ChatGPT Problems

### Error: "Rate limit exceeded"

**Symptom**:
```
openai.RateLimitError: Rate limit exceeded
```

**Cause**: Too many requests to ChatGPT API

**Solution**:
```bash
# 1. Check limits in .env
OPENAI_RATE_LIMIT_RPM=60  # Requests per minute

# 2. Reduce rate if necessary
OPENAI_RATE_LIMIT_RPM=20

# 3. Implement exponential backoff (already implemented)

# 4. Check OpenAI quota
# https://platform.openai.com/account/usage

# 5. Consider upgrading OpenAI plan
```

### Error: "Invalid API key"

**Symptom**:
```
openai.AuthenticationError: Invalid API key
```

**Cause**: Invalid or expired API key

**Solution**:
```bash
# 1. Verify API key format
# Must start with "sk-"
echo $OPENAI_API_KEY

# 2. Generate new key
# https://platform.openai.com/api-keys

# 3. Update .env
OPENAI_API_KEY=sk-your-new-key-here

# 4. Restart server
python -m src.main

# 5. Test connection
python deployment/scripts/test_chatgpt_connection.py
```

### Error: "Timeout"

**Symptom**:
```
openai.APITimeoutError: Request timed out
```

**Cause**: Request too slow or timeout too short

**Solution**:
```bash
# 1. Increase timeout in .env
OPENAI_TIMEOUT=60  # Seconds (default: 30)

# 2. Verify internet connection
ping api.openai.com

# 3. Reduce prompt complexity
# Shorter prompts = faster responses

# 4. Use faster model
OPENAI_MODEL=gpt-3.5-turbo  # Faster than gpt-4
```

### Error: "Model not found"

**Symptom**:
```
openai.NotFoundError: Model 'gpt-5' not found
```

**Cause**: Specified model doesn't exist

**Solution**:
```bash
# Use supported models in .env:
OPENAI_MODEL=gpt-4-turbo      # Recommended
# or
OPENAI_MODEL=gpt-4            # High quality
# or
OPENAI_MODEL=gpt-3.5-turbo    # Fast and economical

# Verify available models
# https://platform.openai.com/docs/models
```

## 💾 Database/Cache Problems

### Error: "network_state.json not found"

**Symptom**:
```
FileNotFoundError: cache/network_state.json
```

**Cause**: Missing network state file

**Solution**:
```bash
# 1. Create cache folder
mkdir cache

# 2. Create sample state file
# Copy from examples/data/
copy examples\data\network_context_latest.json cache\network_state.json

# Or create manually:
echo '{"timestamp":"2024-01-01T00:00:00Z","topology":{"switches":[],"links":[],"hosts":[]},"flows":[],"slices":[],"metrics":{},"anomalies":[]}' > cache/network_state.json
```

### Error: "Invalid JSON"

**Symptom**:
```
json.JSONDecodeError: Expecting value: line 1 column 1
```

**Cause**: Corrupted or malformed JSON file

**Solution**:
```bash
# 1. Validate JSON
python -m json.tool cache/network_state.json

# 2. If corrupted, restore from backup
copy cache\network_state.json.bak cache\network_state.json

# 3. Or recreate from template
copy examples\data\network_context_latest.json cache\network_state.json

# 4. Verify format
cat cache/network_state.json | python -m json.tool
```

### Hypothesis cache too large

**Symptom**:
```
.hypothesis/ folder is 500MB+
```

**Cause**: Too many examples saved from property-based tests

**Solution**:
```bash
# 1. Clean cache
rm -rf .hypothesis/  # Linux/Mac
rmdir /s /q .hypothesis  # Windows

# 2. Limit saved examples in pytest.ini
[pytest]
hypothesis_profile = default

[hypothesis]
max_examples = 100
database = none  # Disable database

# 3. Add to .gitignore (already present)
echo ".hypothesis/" >> .gitignore
```

## 🧪 Testing Problems

### Tests fail: "No module named 'src'"

**Symptom**:
```
ModuleNotFoundError: No module named 'src'
```

**Cause**: PYTHONPATH not configured

**Solution**:
```bash
# Run tests from project root
cd /path/to/llm-driven-net

# Use python -m pytest
python -m pytest tests/

# Or configure PYTHONPATH
set PYTHONPATH=%CD%  # Windows
export PYTHONPATH=$(pwd)  # Linux/Mac

pytest tests/
```

### Property tests too slow

**Symptom**:
Property-based tests take >5 minutes

**Cause**: Too many examples or inefficient generators

**Solution**:
```bash
# 1. Reduce examples in pytest.ini
[hypothesis]
max_examples = 50  # Default: 100

# 2. Run only fast tests
pytest -m "not slow"

# 3. Use profiling
pytest --durations=10

# 4. Optimize generators
# Use st.integers(min_value=0, max_value=100)
# instead of st.integers()
```

### ChatGPT tests fail

**Symptom**:
```
tests/unit/test_chatgpt_client.py::test_api_call FAILED
```

**Cause**: API key not configured or mock not working

**Solution**:
```bash
# 1. Use mocks for unit tests
# Tests should use mocks, not real API

# 2. For integration tests, configure API key
export OPENAI_API_KEY=sk-your-key  # Linux/Mac
set OPENAI_API_KEY=sk-your-key     # Windows

# 3. Skip tests requiring API
pytest -m "not integration"

# 4. Verify mocks in tests/mocks/
```

## 🚢 Deployment Problems

### Docker build fails

**Symptom**:
```
ERROR: failed to solve: process "/bin/sh -c pip install -r requirements.txt" did not complete successfully
```

**Cause**: Dependencies not installable or incorrect Dockerfile

**Solution**:
```bash
# 1. Verify requirements.txt
cat requirements.txt

# 2. Test local installation
pip install -r requirements.txt

# 3. Use Docker cache
docker build --no-cache -t llm-module .

# 4. Verify Dockerfile
# Make sure COPY requirements.txt is before RUN pip install

# 5. Use multi-stage build for debugging
docker build --target builder -t llm-module-debug .
```

### Kubernetes pod in CrashLoopBackOff

**Symptom**:
```
NAME                    READY   STATUS             RESTARTS
llm-module-xxx          0/1     CrashLoopBackOff   5
```

**Cause**: Container crashes on startup

**Solution**:
```bash
# 1. Check logs
kubectl logs llm-module-xxx

# 2. Describe pod
kubectl describe pod llm-module-xxx

# 3. Verify secrets
kubectl get secrets
kubectl describe secret llm-module-secrets

# 4. Verify health check
kubectl exec -it llm-module-xxx -- curl localhost:8080/health

# 5. Interactive debug
kubectl run -it --rm debug --image=llm-module --restart=Never -- /bin/bash
```

### Ingress not working

**Symptom**:
```
curl: (7) Failed to connect to api.example.com
```

**Cause**: Ingress not configured or DNS not resolving

**Solution**:
```bash
# 1. Verify ingress
kubectl get ingress
kubectl describe ingress llm-module-ingress

# 2. Verify service
kubectl get svc
kubectl describe svc llm-module-service

# 3. Test service directly
kubectl port-forward svc/llm-module-service 8080:8080
curl localhost:8080/health

# 4. Verify DNS
nslookup api.example.com

# 5. Check ingress controller
kubectl get pods -n ingress-nginx
```

## ⚡ Performance Problems

### Slow server

**Symptom**:
API responses take >5 seconds

**Cause**: Various possible causes

**Solution**:
```bash
# 1. Enable profiling
pip install py-spy
py-spy top -- python -m src.main

# 2. Check metrics
curl localhost:8000/metrics

# 3. Increase workers
uvicorn src.main:app --workers 4

# 4. Optimize ChatGPT
# Reduce max_tokens in .env
OPENAI_MAX_TOKENS=1000

# 5. Enable caching
# Implement cache for similar responses
```

### Memory leak

**Symptom**:
Memory continuously increases

**Cause**: Objects not released

**Solution**:
```bash
# 1. Monitor memory
pip install memory_profiler
python -m memory_profiler src/main.py

# 2. Use garbage collector
import gc
gc.collect()

# 3. Limit cache size
# Configure LRU cache with maxsize

# 4. Periodic restart
# In Kubernetes, configure liveness probe
```

### Database connection pool exhausted

**Symptom**:
```
OperationalError: connection pool exhausted
```

**Cause**: Too many open connections

**Solution**:
```bash
# 1. Increase pool size
# In database config
pool_size=20
max_overflow=10

# 2. Use connection pooling
# Make sure to close connections

# 3. Implement retry logic

# 4. Monitor active connections
```

## 🆘 Additional Support

If the problem persists:

1. **Check detailed logs**:
   ```bash
   # Enable debug logging
   LOG_LEVEL=DEBUG python -m src.main
   ```

2. **Collect information**:
   ```bash
   # Python version
   python --version
   
   # Installed dependencies
   pip list
   
   # Environment variables (mask secrets!)
   env | grep -v "KEY\|SECRET\|PASSWORD"
   ```

3. **Consult documentation**:
   - [Getting Started](GETTING_STARTED.md)
   - [API Usage](API_USAGE.md)
   - [Deployment Guide](deployment/DEPLOYMENT.md)

4. **Search existing issues**:
   - Check `.kiro/specs/llm-integration-module/tasks.md`

5. **Open new issue**:
   - Include complete logs
   - Describe steps to reproduce
   - Specify environment (OS, Python version, etc.)

---

**Last updated**: February 12, 2026  
**Version**: 1.0
