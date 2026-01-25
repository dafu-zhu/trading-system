#!/bin/bash
# Trading System Installation Script
# Run as root or with sudo
#
# This script installs the trading system to /opt/trading-system
# and configures systemd services for 24/7 operation.
#
# Usage:
#   sudo ./install.sh              # Standard install
#   sudo ./install.sh --with-health  # Also install health endpoint service

set -e

# Configuration
INSTALL_DIR="/opt/trading-system"
SERVICE_USER="trading"
SERVICE_GROUP="trading"
INSTALL_HEALTH=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --with-health)
            INSTALL_HEALTH=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --with-health  Also install the HTTP health endpoint service"
            echo "  --help         Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    log_error "This script must be run as root or with sudo"
    exit 1
fi

# Check for required commands
for cmd in python3 git curl; do
    if ! command -v $cmd &> /dev/null; then
        log_error "$cmd is required but not installed"
        exit 1
    fi
done

log_info "Starting Trading System installation..."

# ============================================================================
# Create service user
# ============================================================================

if ! id "$SERVICE_USER" &>/dev/null; then
    log_info "Creating service user: $SERVICE_USER"
    useradd --system --no-create-home --shell /bin/false "$SERVICE_USER"
else
    log_info "Service user $SERVICE_USER already exists"
fi

# ============================================================================
# Create directory structure
# ============================================================================

log_info "Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/data"
mkdir -p "$INSTALL_DIR/config"
mkdir -p "$INSTALL_DIR/deploy/systemd"
mkdir -p "$INSTALL_DIR/deploy/scripts"
mkdir -p "$INSTALL_DIR/deploy/monitoring"

# ============================================================================
# Copy application files
# ============================================================================

log_info "Copying application files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Core application
cp -r "$PROJECT_ROOT/src" "$INSTALL_DIR/"
cp "$PROJECT_ROOT/run_live.py" "$INSTALL_DIR/"
cp "$PROJECT_ROOT/pyproject.toml" "$INSTALL_DIR/"
cp "$PROJECT_ROOT/uv.lock" "$INSTALL_DIR/" 2>/dev/null || true

# Deploy structure
cp "$PROJECT_ROOT/deploy/trading-system.env.example" "$INSTALL_DIR/deploy/"
cp "$PROJECT_ROOT/deploy/DEPLOYMENT.md" "$INSTALL_DIR/deploy/" 2>/dev/null || true

# Systemd services
cp "$PROJECT_ROOT/deploy/systemd/"*.service "$INSTALL_DIR/deploy/systemd/"

# Scripts
cp "$PROJECT_ROOT/deploy/scripts/"*.sh "$INSTALL_DIR/deploy/scripts/"
chmod +x "$INSTALL_DIR/deploy/scripts/"*.sh

# Monitoring
cp "$PROJECT_ROOT/deploy/monitoring/"*.py "$INSTALL_DIR/deploy/monitoring/" 2>/dev/null || true

# Config files
if [[ -d "$PROJECT_ROOT/config" ]]; then
    # Copy all config files
    cp -r "$PROJECT_ROOT/config/"* "$INSTALL_DIR/config/" 2>/dev/null || true
fi

# Ensure symbols.txt exists
if [[ ! -f "$INSTALL_DIR/config/symbols.txt" ]]; then
    if [[ -f "$PROJECT_ROOT/config/symbols.txt" ]]; then
        cp "$PROJECT_ROOT/config/symbols.txt" "$INSTALL_DIR/config/"
    else
        # Create minimal default
        cat > "$INSTALL_DIR/config/symbols.txt" << 'EOF'
# Trading symbols - one per line
# Edit this file to configure your trading universe
AAPL
MSFT
GOOGL
EOF
    fi
    log_warn "Edit $INSTALL_DIR/config/symbols.txt to configure trading symbols"
fi

# ============================================================================
# Environment file
# ============================================================================

if [[ ! -f "$INSTALL_DIR/deploy/.env" ]]; then
    log_info "Creating environment file from example..."
    cp "$INSTALL_DIR/deploy/trading-system.env.example" "$INSTALL_DIR/deploy/.env"
    chmod 600 "$INSTALL_DIR/deploy/.env"
    log_warn "Please edit $INSTALL_DIR/deploy/.env with your credentials"
else
    log_info "Environment file already exists, preserving..."
fi

# ============================================================================
# Install uv and dependencies
# ============================================================================

if ! command -v uv &> /dev/null; then
    log_info "Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

log_info "Creating virtual environment and installing dependencies..."
cd "$INSTALL_DIR"
uv venv .venv
uv sync

# ============================================================================
# Set ownership and permissions
# ============================================================================

log_info "Setting file ownership..."
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"

# Ensure logs and data directories are writable
chmod 755 "$INSTALL_DIR/logs"
chmod 755 "$INSTALL_DIR/data"

# Protect .env file
chmod 600 "$INSTALL_DIR/deploy/.env"

# ============================================================================
# Install systemd services
# ============================================================================

log_info "Installing systemd services..."

# Main trading service
cp "$INSTALL_DIR/deploy/systemd/trading-system.service" "/etc/systemd/system/"

# Notification service
cp "$INSTALL_DIR/deploy/systemd/trading-system-notify.service" "/etc/systemd/system/"

# Health service (optional)
if [[ "$INSTALL_HEALTH" == true ]]; then
    cp "$INSTALL_DIR/deploy/systemd/trading-system-health.service" "/etc/systemd/system/"
    log_info "Health service installed"
fi

systemctl daemon-reload

# ============================================================================
# Installation complete
# ============================================================================

log_info "Installation complete!"
echo ""
echo "=========================================="
echo "  Trading System Installed Successfully  "
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "  1. Configure trading symbols:"
echo "     sudo nano $INSTALL_DIR/config/symbols.txt"
echo ""
echo "  2. Configure credentials:"
echo "     sudo nano $INSTALL_DIR/deploy/.env"
echo ""
echo "     Required:"
echo "       - ALPACA_API_KEY / ALPACA_API_SECRET"
echo ""
echo "     For email alerts (recommended):"
echo "       - ALERT_EMAIL (recipient)"
echo "       - SMTP_FROM / SMTP_PASSWORD (Gmail App Password)"
echo ""
echo "  3. Create trading config (optional):"
echo "     sudo nano $INSTALL_DIR/config/live_trading.yaml"
echo ""
echo "  3. Start the service:"
echo "     sudo systemctl enable trading-system"
echo "     sudo systemctl start trading-system"
echo ""
echo "  4. Monitor:"
echo "     sudo systemctl status trading-system"
echo "     sudo journalctl -u trading-system -f"
echo "     tail -f $INSTALL_DIR/logs/live_trading.log"
echo ""
if [[ "$INSTALL_HEALTH" == true ]]; then
echo "  5. Health endpoint (optional):"
echo "     sudo systemctl enable trading-system-health"
echo "     sudo systemctl start trading-system-health"
echo "     curl http://localhost:8080/health"
echo ""
fi
echo "For Gmail App Password setup, see:"
echo "  https://myaccount.google.com/apppasswords"
echo ""
echo "Full documentation: $INSTALL_DIR/deploy/DEPLOYMENT.md"
echo ""
