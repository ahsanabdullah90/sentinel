#!/bin/bash

# Sentinel RFP Agent - Environment Pre-Check Script

echo "==============================================="
echo " Sentinel RFP Agent: Environment Pre-Check"
echo "==============================================="
echo ""

FAILS=0

# Helper functions
pass() { echo "  ✅ [PASS] $1"; }
fail() { echo "  ❌ [FAIL] $1"; FAILS=$((FAILS+1)); }
warn() { echo "  ⚠️ [WARN] $1"; }

echo "--- 1. Permissions ---"
if [ -w "$PWD" ]; then
    pass "Write access to workspace directory ($PWD)"
else
    fail "No write access to workspace directory ($PWD). Please run: chmod u+w ."
fi

if sudo -n true 2>/dev/null; then
    pass "Sudo access available without password (or already cached)"
else
    # We can't actually test if they have sudo without prompting, so we'll just warn
    warn "Could not verify passwordless sudo. You will need sudo access to install apt packages."
fi

if [ -w "$HOME" ]; then
    pass "Write access to HOME directory ($HOME)"
else
    fail "No write access to HOME directory. Rustup and Ollama require this."
fi

echo ""
echo "--- 2. Ports ---"
for port in 11434 8000 1420; do
    if ! ss -tuln | grep -q ":$port "; then
        pass "Port $port is free"
    else
        fail "Port $port is in use. Please free this port."
    fi
done

echo ""
echo "--- 3. Disk Space ---"
FREE_SPACE=$(df -m . | awk 'NR==2 {print $4}')
REQUIRED_MB=10240 # 10GB
if [ "$FREE_SPACE" -ge "$REQUIRED_MB" ]; then
    pass "Disk space: $((FREE_SPACE / 1024))GB available (>= 10GB required)"
else
    fail "Disk space: Only $((FREE_SPACE / 1024))GB available. Sentinel requires at least 10GB for models, toolchains, and node_modules."
fi

echo ""
echo "--- 4. Network Reachability ---"
URLS=(
    "https://sh.rustup.rs"
    "https://registry.npmjs.org"
    "https://ollama.com"
    "https://pypi.org"
)

for url in "${URLS[@]}"; do
    if curl -s --head --request GET "$url" | grep "200 OK" > /dev/null; then
        pass "Can reach $url"
    else
        if curl -s --head "$url" > /dev/null; then
            pass "Can reach $url (Non-200 OK, but reachable)"
        else
            fail "Cannot reach $url. Please check your internet connection or firewall."
        fi
    fi
done

echo ""
echo "==============================================="
if [ $FAILS -eq 0 ]; then
    echo "🎉 All pre-checks passed! You are ready to install dependencies."
    exit 0
else
    echo "🚨 $FAILS pre-check(s) failed. Please resolve them before proceeding."
    exit 1
fi
