#!/usr/bin/env bash
# ==============================================================================
# Sentinel RFP Agent - Python Sidecars Standalone Compiler
# ==============================================================================
# Compiles all 4 Python sidecars using PyInstaller inside the local virtual env.
# Outputs compiled standalone binaries named with host target-triple suffix to:
# src-tauri/binaries/
# ==============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

info() { echo -e "  [${BLUE}→${NC}] $1"; }
success() { echo -e "  [${GREEN}✓${NC}] $1"; }
warn() { echo -e "  [${YELLOW}⚠️${NC}] $1"; }
error() { echo -e "  [${RED}❌${NC}] $1"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$WORKSPACE_ROOT"

info "Workspace root: $WORKSPACE_ROOT"

# Ensure virtualenv exists
if [ ! -d ".venv" ]; then
    error "Python virtual environment (.venv) not found. Please run install.sh first."
fi

# Activate virtualenv
info "Activating Python virtual environment..."
source .venv/bin/activate

# Install PyInstaller if not already installed
if ! command -v pyinstaller >/dev/null 2>&1; then
    info "Installing PyInstaller inside virtualenv..."
    pip install pyinstaller --quiet
fi

# Detect host target triple
info "Detecting host target triple..."
if command -v rustc >/dev/null 2>&1; then
    TARGET_TRIPLE=$(rustc -vV | grep host | cut -d' ' -f2)
else
    TARGET_TRIPLE="x86_64-unknown-linux-gnu"
fi
success "Target triple detected: $TARGET_TRIPLE"

# Target directory for sidecar binaries
BINARIES_DIR="src-tauri/binaries"
mkdir -p "$BINARIES_DIR"
info "Prepared binaries output directory: $BINARIES_DIR"

# Ensure we have a clean target temporary dir in the workspace for PyInstaller
PYINSTALLER_TEMP="target/pyinstaller"
mkdir -p "$PYINSTALLER_TEMP"

# List of sidecars to compile: Name | EntryPoint
declare -A SIDECARS=(
    ["hunter"]="sidecars/hunter/src_py/server.py"
    ["rag"]="sidecars/rag/src_py/server.py"
    ["gap-engine"]="sidecars/gap-engine/src_py/server.py"
    ["worker"]="sidecars/worker/src_py/worker.py"
)

# Run PyInstaller for each sidecar
for name in "${!SIDECARS[@]}"; do
    entry="${SIDECARS[$name]}"
    binary_name="${name}-${TARGET_TRIPLE}"
    
    info "Compiling sidecar '${name}' using PyInstaller..."
    
    add_data_args=()
    if [ "$name" = "hunter" ]; then
        PLAYWRIGHT_PATH=$(python -c "import playwright; import os; print(os.path.dirname(playwright.__file__))")
        info "Found Playwright at: $PLAYWRIGHT_PATH. Bundling driver..."
        add_data_args+=("--add-data" "${PLAYWRIGHT_PATH}/driver:playwright/driver")
    fi

    # We set PYTHONPATH to workspace root and pass '--paths .' to PyInstaller
    # so absolute imports like 'from sidecars.hunter...' or 'from sidecars.rag...' work flawlessly.
    PYTHONPATH=. pyinstaller --clean --onefile \
        --paths . \
        --distpath "$BINARIES_DIR" \
        --name "$binary_name" \
        --workpath "$PYINSTALLER_TEMP/${name}-build" \
        --specpath "$PYINSTALLER_TEMP/${name}-spec" \
        "${add_data_args[@]}" \
        "$entry"
        
    if [ -f "$BINARIES_DIR/$binary_name" ]; then
        success "Sidecar '${name}' compiled successfully: $BINARIES_DIR/$binary_name"
    else
        error "Failed to compile sidecar '${name}'! Binary not found in distpath."
    fi
done

# Cleanup PyInstaller temporary folders
info "Cleaning up temporary build directories inside workspace..."
rm -rf "$PYINSTALLER_TEMP"

success "All sidecar binaries successfully compiled!"
