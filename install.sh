#!/usr/bin/env bash
# ==============================================================================
# Sentinel RFP Agent - Enterprise Unified Installer
# ==============================================================================
# A professional, single-command setup tool for local dev and desktop deployments.
# Performs dependency checks, installs system libraries, configures environments,
# and downloads required LLM weights natively.
# ==============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

info() { echo -e "  [${BLUE}→${NC}] $1"; }
success() { echo -e "  [${GREEN}✓${NC}] $1"; }
warn() { echo -e "  [${YELLOW}⚠️${NC}] $1"; }
error() { echo -e "  [${RED}❌${NC}] $1"; exit 1; }
title() {
    echo -e ""
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
    echo -e "${BOLD}${CYAN}  $1 ${NC}"
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

title "Sentinel RFP Agent: Enterprise Setup & Provisioning"

title "[1/5] Detecting Host Environment"
OS_TYPE=$(uname -s)
info "OS Type detected: $OS_TYPE"

IS_DEBIAN=false
if [ -f /etc/debian_version ] || [ -f /etc/lsb-release ]; then
    IS_DEBIAN=true
    success "OS Distribution: Debian/Ubuntu-compatible Linux system."
fi

title "[2/5] Provisioning System Libraries"
if [ "$IS_DEBIAN" = "true" ]; then
    info "Installing native system libraries (requires sudo privileges)..."
    if sudo -n true 2>/dev/null; then
        sudo apt-get update -y
        sudo apt-get install -y libsqlite3-dev protobuf-compiler \
          libwebkit2gtk-4.1-dev build-essential curl wget file libxdo-dev \
          libssl-dev libayatana-appindicator3-dev librsvg2-dev
        success "System libraries installed successfully."
    else
        warn "Sudo access is required to install target system libraries."
        info "Please execute the following command manually:"
        echo -e "${BOLD}${YELLOW}sudo apt-get update && sudo apt-get install -y libsqlite3-dev libwebkit2gtk-4.1-dev build-essential curl wget file libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev${NC}"
        echo -e ""
        read -p "Press [Enter] after installing system libraries manually, or to skip..." || true
    fi
fi

info "Verifying required local development binaries..."
command -v node >/dev/null 2>&1 || error "Node.js (>=20) is required but not installed."
command -v npm >/dev/null 2>&1 || error "NPM is required but not installed."
command -v git >/dev/null 2>&1 || error "Git is required but not installed."
success "Local binaries (Node, NPM, Git) are provisioned."

title "[3/5] Provisioning Environment Configuration"
if [ ! -f .env ]; then
    cp .env.example .env
    success "Created .env from .env.example"
else
    info "Existing .env file found. Retaining current environment keys."
fi

title "[4/5] Installing Application Dependencies"

info "Provisioning Python Virtual Environment (.venv)..."
if [ ! -d ".venv" ]; then
    virtualenv .venv || python3 -m venv .venv
    success "Python virtual environment created."
else
    info "Python virtual environment already exists."
fi

info "Installing Python sidecar dependencies..."
.venv/bin/pip install --upgrade pip
if [ -f "sidecars/hunter/requirements.txt" ]; then
    .venv/bin/pip install -r sidecars/hunter/requirements.txt --quiet
fi
if [ -f "sidecars/rag/requirements.txt" ]; then
    .venv/bin/pip install -r sidecars/rag/requirements.txt --quiet
fi
if [ -f "sidecars/worker/requirements.txt" ]; then
    .venv/bin/pip install -r sidecars/worker/requirements.txt --quiet
fi
# Playwright python driver needs its own install step for chromium
info "Installing Python Playwright browsers..."
.venv/bin/playwright install chromium

info "Installing primary application node dependencies..."
npm ci --silent

info "Installing Playwright scraper and Chromium browser dependencies..."
npm run hunter:install --silent

info "Installing RAG sidecar dependencies..."
cd sidecars/rag
npm install --silent
cd ../..

success "All JavaScript and Playwright sidecar dependencies are successfully provisioned."

title "[5/5] Compiling Standalone Production Desktop Bundle"
info "Building frontend production assets..."
npm run build

info "Compiling standalone desktop binary and installer via Tauri..."
npx tauri build

success "Standalone production desktop application successfully compiled!"

echo -e ""
echo -e "${BOLD}${GREEN}======================================================================${NC}"
echo -e "${BOLD}${GREEN}   DEPLOYMENT & COMPILATION COMPLETED SUCCESSFULLY - SYSTEMS GREEN     ${NC}"
echo -e "${BOLD}${GREEN}======================================================================${NC}"
echo -e ""
echo -e "${BOLD}Standalone Desktop Installer Location:${NC}"
echo -e "  • Binaries/Installers reside in: ${BOLD}${CYAN}src-tauri/target/release/bundle/${NC}"
echo -e ""
echo -e "${BOLD}Alternative Development Commands:${NC}"
echo -e "  1. Run Tauri development server:"
echo -e "     ${BOLD}${CYAN}npm run tauri dev${NC}"
echo -e ""
echo -e "======================================================================"
