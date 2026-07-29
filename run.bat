@echo off
setlocal enabledelayedexpansion

:: Add Rust cargo binary path if present
if exist "%USERPROFILE%\.cargo\bin" set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"

echo ===================================================
echo   Sentinel RFP Agent - Launch and Lifecycle Manager
echo ===================================================

:: 1. Pre-flight checks
echo [i] Running pre-flight checks...

:: Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Node.js is not installed or not in PATH.
    echo [!] Please install Node.js >= 20 from https://nodejs.org/
    goto :fail
)

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Python is not installed or not in PATH.
    echo [!] Please install Python >= 3.11 from https://python.org/
    goto :fail
)

:: Activate virtual environment if present (created by setup.bat)
if exist ".venv\Scripts\python.exe" (
    set "PATH=%~dp0.venv\Scripts;%PATH%"
    echo [i] Using Python virtual environment at .venv
)

:: Check if node_modules exist
if not exist "node_modules" (
    echo [i] node_modules not found. Running npm install...
    call npm ci
    if %errorlevel% neq 0 (
        echo [X] npm install failed.
        goto :fail
    )
)

:: Check Ollama
netstat -ano | findstr :11434 >nul
if %errorlevel% neq 0 (
    echo [!] Ollama is not running on port 11434.
    echo [i] Attempting to start Ollama background service...
    start "" /B ollama serve
    
    set /a count=0
    :poll_ollama
    timeout /t 1 /nobreak >nul
    netstat -ano | findstr :11434 >nul
    if %errorlevel% neq 0 (
        set /a count+=1
        if !count! lss 10 (
            goto :poll_ollama
        ) else (
            echo [WARNING] Ollama did not start within 10 seconds.
            echo [!] Please install and start Ollama manually.
        )
    ) else (
        echo [OK] Ollama service started successfully.
    )
) else (
    echo [OK] Ollama service is online.
)

:: Check Python sidecar dependencies
echo [i] Checking Python sidecar dependencies...
python -c "import chromadb; import pypdf; import pydantic" >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Some Python sidecar dependencies are missing. Installing...
    pip install -e ./sidecars/hunter -e ./sidecars/rag -e ./sidecars/worker -e ./sidecars/gap_engine --quiet
)

:: Check Playwright
python -c "from playwright.async_api import async_playwright" >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Playwright is not installed. Installing...
    pip install playwright --quiet
)

:: Check if .env exists
if not exist .env (
    echo [i] No .env found. Creating from .env.example...
    copy .env.example .env >nul
)

:: 2. Launch Tauri Application
echo.
echo ===================================================
echo   Sentinel - Launching Application
echo ===================================================
echo [i] Close the application window or press Ctrl+C in this terminal to exit.
call npm run tauri dev
if %errorlevel% neq 0 (
    echo.
    echo [X] Tauri dev server exited with an error.
    echo [!] Check the error messages above for details.
    goto :cleanup
)

:cleanup
:: 3. Post-run Cleanup
echo.
echo ===================================================
echo   Sentinel - Initiating Graceful Process Cleanup...
echo ===================================================

echo [i] Terminating any residue Sentinel application processes...
taskkill /F /IM sentinel.exe >nul 2>&1
taskkill /F /IM sentinel-rfp-agent.exe >nul 2>&1

echo [i] Terminating residue Python sidecar processes...
wmic process where "commandline like '%%sidecars%%'" call terminate >nul 2>&1

echo [OK] Cleanup complete. Exiting.
goto :eof

:fail
echo.
echo [X] Pre-flight checks failed. Please fix the issues above and try again.
exit /b 1
