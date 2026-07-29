@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   Sentinel RFP Agent - Sidecar Compiler (Windows)
echo ===================================================
echo.

:: 1. Ensure virtualenv exists
if not exist ".venv" (
    echo [X] Python virtual environment (.venv) not found.
    echo [i] Please run setup.bat first.
    exit /b 1
)

:: 2. Activate virtualenv
echo [i] Activating Python virtual environment...
call .venv\Scripts\activate.bat

:: 3. Install PyInstaller if not already installed
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo [i] Installing PyInstaller inside virtualenv...
    pip install pyinstaller --quiet
)

:: 4. Detect host target triple
echo [i] Detecting host target triple...
for /f "tokens=2 delims= " %%i in ('rustc -vV ^| findstr "host:"') do set TARGET_TRIPLE=%%i
if "%TARGET_TRIPLE%"=="" set TARGET_TRIPLE=x86_64-pc-windows-msvc
echo [OK] Target triple detected: %TARGET_TRIPLE%

:: 5. Prepare output directory
set BINARIES_DIR=src-tauri\binaries
if not exist "%BINARIES_DIR%" mkdir "%BINARIES_DIR%"

:: 6. Create temp directory for PyInstaller artifacts
if not exist "target\pyinstaller" mkdir "target\pyinstaller"

:: 7. Compile each sidecar
for %%s in (hunter rag gap_engine worker) do (
    set BINARY_NAME=%%s-%TARGET_TRIPLE%

    if "%%s"=="hunter" set ENTRY_FILE=sidecars/hunter/src_py/server.py
    if "%%s"=="rag" set ENTRY_FILE=sidecars/rag/src_py/server.py
    if "%%s"=="gap_engine" set ENTRY_FILE=sidecars/gap_engine/src_py/server.py
    if "%%s"=="worker" set ENTRY_FILE=sidecars/worker/src_py/server.py

    echo [i] Compiling sidecar '%%s' using PyInstaller...

    set ADD_DATA_ARGS=
    if "%%s"=="hunter" (
        for /f "tokens=*" %%d in ('python -c "import playwright; import os; print(os.path.dirname(playwright.__file__))"') do set PLAYWRIGHT_PATH=%%d
        if not "!PLAYWRIGHT_PATH!"=="" (
            echo [i] Found Playwright at !PLAYWRIGHT_PATH!. Bundling driver...
            set ADD_DATA_ARGS=--add-data "!PLAYWRIGHT_PATH!\driver;playwright\driver"
        )
    )

    set PYTHONPATH=.
    pyinstaller --clean --onefile ^
        --paths . ^
        --distpath "%BINARIES_DIR%" ^
        --name "!BINARY_NAME!" ^
        --workpath "target\pyinstaller\!BINARY_NAME!-build" ^
        --specpath "target\pyinstaller\!BINARY_NAME!-spec" ^
        !ADD_DATA_ARGS! ^
        "!ENTRY_FILE!"

    if exist "%BINARIES_DIR%\!BINARY_NAME!.exe" (
        echo [OK] Sidecar '%%s' compiled successfully
    ) else if exist "%BINARIES_DIR%\!BINARY_NAME!" (
        echo [OK] Sidecar '%%s' compiled successfully
    ) else (
        echo [X] Failed to compile sidecar '%%s'!
    )
)

:: 8. Cleanup PyInstaller temporary folders
if exist "target\pyinstaller" (
    echo [i] Cleaning up temporary build directories...
    rmdir /s /q "target\pyinstaller"
)

echo.
echo ===================================================
echo   All sidecar binaries successfully compiled
echo ===================================================

endlocal