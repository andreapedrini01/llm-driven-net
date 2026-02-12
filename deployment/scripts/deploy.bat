@echo off
REM Deployment script for LLM Integration Module (Windows)

setlocal enabledelayedexpansion

REM Parse arguments
set ENVIRONMENT=%1
set ACTION=%2

if "%ENVIRONMENT%"=="" set ENVIRONMENT=dev
if "%ACTION%"=="" set ACTION=deploy

REM Validate environment
if not "%ENVIRONMENT%"=="dev" if not "%ENVIRONMENT%"=="staging" if not "%ENVIRONMENT%"=="prod" (
    echo [ERROR] Invalid environment: %ENVIRONMENT%
    echo Usage: %0 ^<dev^|staging^|prod^> [deploy^|rollback^|status]
    exit /b 1
)

REM Validate action
if not "%ACTION%"=="deploy" if not "%ACTION%"=="rollback" if not "%ACTION%"=="status" (
    echo [ERROR] Invalid action: %ACTION%
    echo Usage: %0 ^<dev^|staging^|prod^> [deploy^|rollback^|status]
    exit /b 1
)

echo ==========================================
echo   LLM Integration Module - Deployment
echo ==========================================
echo.
echo Environment: %ENVIRONMENT%
echo Action: %ACTION%
echo.

REM Load environment configuration
set ENV_FILE=config\%ENVIRONMENT%.env
if not exist "%ENV_FILE%" (
    echo [ERROR] Environment file not found: %ENV_FILE%
    exit /b 1
)

echo [OK] Environment file loaded: %ENV_FILE%

REM Execute action
if "%ACTION%"=="deploy" goto :deploy
if "%ACTION%"=="rollback" goto :rollback
if "%ACTION%"=="status" goto :status

:deploy
echo.
echo ==========================================
echo   Deploying to %ENVIRONMENT%
echo ==========================================
echo.

REM Pre-deployment checks
echo [INFO] Running pre-deployment checks...

if not exist "Dockerfile" (
    echo [ERROR] Dockerfile not found
    exit /b 1
)

if not exist "docker-compose.yml" (
    echo [ERROR] docker-compose.yml not found
    exit /b 1
)

echo [OK] Pre-deployment checks passed

REM Build Docker image
echo [INFO] Building Docker image...

for /f "tokens=1-3 delims=:." %%a in ("%time%") do set TIMESTAMP=%%a%%b%%c
set IMAGE_TAG=llm-integration-module:%ENVIRONMENT%-%date:~-4%%date:~-7,2%%date:~-10,2%-%TIMESTAMP%

docker build -t "%IMAGE_TAG%" .
docker tag "%IMAGE_TAG%" "llm-integration-module:%ENVIRONMENT%-latest"

echo [OK] Docker image built: %IMAGE_TAG%

REM Stop existing containers
echo [INFO] Stopping existing containers...

docker-compose --env-file "%ENV_FILE%" down 2>nul

echo [OK] Existing containers stopped

REM Start new containers
echo [INFO] Starting new containers...

docker-compose --env-file "%ENV_FILE%" up -d

echo [OK] New containers started

REM Wait for health check
echo [INFO] Waiting for service to become healthy...

python scripts\health_check.py --wait --max-wait 60

if %errorlevel% equ 0 (
    echo [OK] Deployment successful!
) else (
    echo [ERROR] Health check failed
    echo [WARNING] Rolling back...
    goto :rollback
    exit /b 1
)

echo.
echo ==========================================
echo   Deployment Complete
echo ==========================================
echo.
echo [OK] Service is running at http://localhost:8080
echo [INFO] View logs: docker-compose logs -f
echo [INFO] Check status: %0 %ENVIRONMENT% status

goto :end

:rollback
echo.
echo ==========================================
echo   Rolling back %ENVIRONMENT%
echo ==========================================
echo.

echo [INFO] Stopping current containers...
docker-compose --env-file "%ENV_FILE%" down

echo [INFO] Starting previous version...
set PREVIOUS_TAG=llm-integration-module:%ENVIRONMENT%-previous

docker images | findstr /C:"%PREVIOUS_TAG%" >nul
if %errorlevel% equ 0 (
    docker tag "%PREVIOUS_TAG%" "llm-integration-module:%ENVIRONMENT%-latest"
    docker-compose --env-file "%ENV_FILE%" up -d
    echo [OK] Rollback complete
) else (
    echo [ERROR] No previous version found
    exit /b 1
)

goto :end

:status
echo.
echo ==========================================
echo   Status Check - %ENVIRONMENT%
echo ==========================================
echo.

echo [INFO] Container status:
docker-compose --env-file "%ENV_FILE%" ps

echo.
echo [INFO] Running health checks:
python scripts\health_check.py

echo.
echo [INFO] Recent logs:
docker-compose --env-file "%ENV_FILE%" logs --tail=20

goto :end

:end
endlocal
