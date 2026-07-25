@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   Sentinel RFP Agent – Launch & Lifecycle Manager
echo ===================================================

:: 1. Ensure .env exists
if not exist .env (
    echo [i] Copying .env.example to create default .env...
    copy .env.example .env >nul
)

:: 2. Pre-launch checks: Check if Ollama is running
echo [i] Checking local dependencies...
netstat -ano | findstr :11434 >nul
if %errorlevel% neq 0 (
    echo [!] Ollama is not running on port 11434.
    echo [i] Attempting to start Ollama background service...
    start "" /B ollama serve
    
    :: Wait and poll up to 10 seconds
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
        )
    ) else (
        echo [✓] Ollama service started successfully.
    )
) else (
    echo [✓] Ollama service is online.
)

:: 3. Run Tauri Application in development mode
echo [i] Launching Sentinel RFP Agent...
echo [i] Close the application window or press Ctrl+C in this terminal to exit.
call npm run tauri dev

:: 4. Post-run Cleanup: Terminate orphaned child processes
echo ===================================================
echo   Sentinel – Initiating Graceful Process Cleanup...
echo ===================================================

:: Kill orphaned Tauri / Rust binaries
echo [i] Terminating any residue Sentinel application processes...
taskkill /F /IM sentinel.exe >nul 2>&1
taskkill /F /IM sentinel-rfp-agent.exe >nul 2>&1

:: Kill orphaned Python sidecar processes
echo [i] Terminating residue Python sidecar processes...
wmic process where "commandline like '%%sidecars%%'" call terminate >nul 2>&1

echo [✓] Cleanup complete. Exiting.
