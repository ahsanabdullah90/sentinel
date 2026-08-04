@echo off
setlocal enabledelayedexpansion

:: Add Rust cargo binary path if present
if exist "%USERPROFILE%\.cargo\bin" set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"

:: Keep the Rust incremental cache on an NTFS drive (the workspace drive may be
:: exFAT, which has no hard-link support and slows every build down)
if "%CARGO_TARGET_DIR%"=="" (
    set "CARGO_TARGET_DIR=%LOCALAPPDATA%\sentinel\target"
    if not exist "%CARGO_TARGET_DIR%" mkdir "%CARGO_TARGET_DIR%"
)

echo ===================================================
echo   Sentinel RFP Agent - Launch and Lifecycle Manager
echo ===================================================

:: 1. Pre-flight checks
echo [i] Running pre-flight checks...

:: Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Node.js is not installed or not in PATH.
    echo [^^!] Please install Node.js ^>= 20 from https://nodejs.org/
    goto :fail
)

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Python is not installed or not in PATH.
    echo [^^!] Please install Python ^>= 3.11 from https://python.org/
    goto :fail
)

:: Use virtual environment if present (created by setup.bat)
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
    set "PIP=.venv\Scripts\pip.exe"
    :: Prepend to PATH so Tauri sidecar spawning finds the venv's python
    set "PATH=%~dp0.venv\Scripts;%PATH%"
    echo [i] Using Python virtual environment at .venv
) else (
    set "PYTHON=python"
    set "PIP=pip"
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

:: Check Ollama (optional - the app can use Google Gemini cloud instead)
netstat -ano | findstr :11434 >nul
if %errorlevel% neq 0 (
    echo [i] Ollama not detected on port 11434.
    echo [i] The app will use Google Gemini cloud unless Ollama is started.
    echo [i] Tip: run "ollama serve" to enable the local provider.
) else (
    echo [OK] Ollama service detected on port 11434.
)

:: Check Python sidecar dependencies
echo [i] Checking Python sidecar dependencies...
!PYTHON! -c "import chromadb; import pypdf; import pydantic" >nul 2>&1
if %errorlevel% neq 0 (
    echo [^^!] Some Python sidecar dependencies are missing. Installing...
    !PIP! install setuptools wheel greenlet --quiet
    !PIP! install chromadb pypdf pydantic beautifulsoup4 --no-build-isolation --quiet
    !PIP! install -e ./sidecars/hunter -e ./sidecars/rag -e ./sidecars/worker -e ./sidecars/gap_engine --no-build-isolation --no-deps --quiet
    if %errorlevel% neq 0 (
        echo [X] Failed to install Python sidecar dependencies.
        echo [^^!] Try running setup.bat first.
        goto :fail
    )
    :: Verify installation succeeded
    !PYTHON! -c "import chromadb; import pypdf; import pydantic" >nul 2>&1
    if %errorlevel% neq 0 (
        echo [X] Python sidecar dependencies still missing after install.
        goto :fail
    )
    echo [OK] Python sidecar dependencies installed.
)

:: Check Playwright
!PYTHON! -c "from playwright.async_api import async_playwright" >nul 2>&1
if %errorlevel% neq 0 (
    echo [^^!] Playwright is not installed. Installing...
    !PIP! install playwright --quiet
    if %errorlevel% neq 0 (
        echo [X] Failed to install Playwright.
        goto :fail
    )
    echo [OK] Playwright installed.
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
    echo [^^!] Check the error messages above for details.
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
pause
goto :eof

:fail
echo.
echo [X] Pre-flight checks failed. Please fix the issues above and try again.
pause
exit /b 1