@echo off
REM Script di setup automatico per Windows

echo ==========================================
echo   LLM Integration Module - Setup
echo ==========================================
echo.

REM 1. Verifica Python
echo [1/6] Verifica Python
echo ----------------------------------------

python --version >nul 2>&1
if errorlevel 1 (
    echo [X] Python non trovato. Installa Python 3.10 o superiore.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo [OK] Python %PYTHON_VERSION% trovato
echo.

REM 2. Crea ambiente virtuale
echo [2/6] Creazione ambiente virtuale
echo ----------------------------------------

if exist venv (
    echo [!] Ambiente virtuale gia esistente
    set /p RECREATE="Vuoi ricrearlo? (y/n): "
    if /i "%RECREATE%"=="y" (
        rmdir /s /q venv
        python -m venv venv
        echo [OK] Ambiente virtuale ricreato
    )
) else (
    python -m venv venv
    echo [OK] Ambiente virtuale creato
)
echo.

REM 3. Attiva ambiente virtuale
echo [3/6] Attivazione ambiente virtuale
echo ----------------------------------------

call venv\Scripts\activate.bat
echo [OK] Ambiente virtuale attivato
echo.

REM 4. Aggiorna pip
echo [4/6] Aggiornamento pip
echo ----------------------------------------

python -m pip install --upgrade pip --quiet
echo [OK] pip aggiornato
echo.

REM 5. Installa dipendenze
echo [5/6] Installazione dipendenze
echo ----------------------------------------

set /p INSTALL_DEV="Installare dipendenze di sviluppo? (y/n): "
if /i "%INSTALL_DEV%"=="y" (
    pip install -r requirements-dev.txt --quiet
    echo [OK] Dipendenze di sviluppo installate
) else (
    pip install -r requirements.txt --quiet
    echo [OK] Dipendenze di produzione installate
)
echo.

REM 6. Configura .env
echo [6/6] Configurazione file .env
echo ----------------------------------------

if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo [OK] File .env creato da .env.example
        echo [!] IMPORTANTE: Configura OPENAI_API_KEY nel file .env
    ) else (
        echo [X] File .env.example non trovato
    )
) else (
    echo [!] File .env gia esistente
)
echo.

REM Verifica installazione
echo ==========================================
echo   Verifica Installazione
echo ==========================================
echo.

python scripts\verify_installation.py

REM Istruzioni finali
echo.
echo ==========================================
echo   Setup Completato!
echo ==========================================
echo.
echo Prossimi passi:
echo   1. Attiva l'ambiente virtuale:
echo      venv\Scripts\activate
echo.
echo   2. Configura il file .env con la tua OPENAI_API_KEY
echo.
echo   3. Esegui i test:
echo      pytest
echo.
echo   4. Avvia l'applicazione:
echo      python -m src.main
echo.

pause
