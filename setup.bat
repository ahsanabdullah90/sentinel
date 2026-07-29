@echo off
setlocal enabledelayedexpansion

:: Add Rust cargo binary path if present
if exist "%USERPROFILE%\.cargo\bin" set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"

echo ===================================================
echo   Sentinel RFP Agent - Windows Setup
echo ===================================================

:: 1. Check prerequisites
echo.
echo [1/5] Checking prerequisites...

:: Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Node.js >= 20 is required. Download from https://nodejs.org/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do echo [OK] Node.js %%i

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Python >= 3.11 is required. Download from https://python.org/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo [OK] %%i

:: Check Rust/Cargo
cargo --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Rust toolchain is required. Install from https://rustup.rs/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('cargo --version') do echo [OK] %%i

:: Check Ollama
ollama --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Ollama not found. Install from https://ollama.com/
    echo [i] Continuing without Ollama - AI features will not work.
)

:: 2. Install Node dependencies
echo.
echo [2/5] Installing Node.js dependencies...
call npm ci
if %errorlevel% neq 0 (
    echo [X] npm ci failed.
    pause
    exit /b 1
)
echo [OK] Node dependencies installed.

:: 3. Install Python sidecar dependencies
echo.
echo [3/5] Installing Python sidecar dependencies...

:: Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo [i] Creating Python virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [X] Failed to create Python virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created at .venv
)

:: Install sidecar packages
echo [i] Installing sidecar packages...
call .venv\Scripts\pip install -e ./sidecars/hunter -e ./sidecars/rag -e ./sidecars/worker -e ./sidecars/gap_engine --quiet
if %errorlevel% neq 0 (
    echo [X] Failed to install sidecar packages.
    pause
    exit /b 1
)
echo [OK] Python sidecar dependencies installed.

:: 4. Install Playwright and browser
echo.
echo [4/5] Installing Playwright and Chromium browser...
call .venv\Scripts\pip install playwright --quiet
if %errorlevel% neq 0 (
    echo [X] Failed to install Playwright.
    pause
    exit /b 1
)
call .venv\Scripts\playwright install chromium
if %errorlevel% neq 0 (
    echo [X] Failed to install Chromium browser for Playwright.
    pause
    exit /b 1
)
echo [OK] Playwright and Chromium installed.

:: 5. Create .env
echo.
echo [5/5] Setting up environment...
if not exist .env (
    copy .env.example .env >nul
    echo [OK] Created .env from .env.example
) else (
    echo [OK] .env already exists
)

:: Done
echo.
echo ===================================================
echo   Setup Complete^^!
echo ===================================================
echo.
echo   Next steps:
echo     1. Make sure Ollama is running: ollama serve
echo     2. Run the app: run.bat
echo.
echo ===================================================
pause
