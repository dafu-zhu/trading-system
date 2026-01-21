#!/bin/bash
# Trading System Installation Script
# Run as root or with sudo

set -e

# Configuration
INSTALL_DIR="/opt/trading-system"
SERVICE_USER="trading"
SERVICE_GROUP="trading"
SERVICE_FILE="trading-system.service"

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
for cmd in python3 git; do
    if ! command -v $cmd &> /dev/null; then
        log_error "$cmd is required but not installed"
        exit 1
    fi
done

log_info "Starting Trading System installation..."

# Create service user if it doesn't exist
if ! id "$SERVICE_USER" &>/dev/null; then
    log_info "Creating service user: $SERVICE_USER"
    useradd --system --no-create-home --shell /bin/false "$SERVICE_USER"
else
    log_info "Service user $SERVICE_USER already exists"
fi

# Create installation directory
log_info "Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/data"
mkdir -p "$INSTALL_DIR/config"

# Copy application files
log_info "Copying application files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Copy source code
cp -r "$PROJECT_ROOT/src" "$INSTALL_DIR/"
cp -r "$PROJECT_ROOT/run_live.py" "$INSTALL_DIR/"
cp -r "$PROJECT_ROOT/pyproject.toml" "$INSTALL_DIR/"
cp -r "$PROJECT_ROOT/uv.lock" "$INSTALL_DIR/" 2>/dev/null || true

# Copy deploy files
cp -r "$PROJECT_ROOT/deploy" "$INSTALL_DIR/"

# Copy config if exists
if [[ -d "$PROJECT_ROOT/config" ]]; then
    cp -r "$PROJECT_ROOT/config/"* "$INSTALL_DIR/config/" 2>/dev/null || true
fi

# Create environment file from example if .env doesn't exist
if [[ ! -f "$INSTALL_DIR/deploy/.env" ]]; then
    log_info "Creating environment file from example..."
    cp "$INSTALL_DIR/deploy/trading-system.env.example" "$INSTALL_DIR/deploy/.env"
    chmod 600 "$INSTALL_DIR/deploy/.env"
    log_warn "Please edit $INSTALL_DIR/deploy/.env with your credentials"
fi

# Install uv if not present
if ! command -v uv &> /dev/null; then
    log_info "Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Create virtual environment and install dependencies
log_info "Creating virtual environment and installing dependencies..."
cd "$INSTALL_DIR"
uv venv .venv
uv sync

# Set ownership
log_info "Setting file ownership..."
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"

# Ensure logs and data directories are writable
chmod 755 "$INSTALL_DIR/logs"
chmod 755 "$INSTALL_DIR/data"

# Install systemd service
log_info "Installing systemd service..."
cp "$INSTALL_DIR/deploy/$SERVICE_FILE" "/etc/systemd/system/$SERVICE_FILE"
systemctl daemon-reload

log_info "Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Edit the environment file:"
echo "     sudo nano $INSTALL_DIR/deploy/.env"
echo ""
echo "  2. Create a YAML config file (optional):"
echo "     sudo nano $INSTALL_DIR/config/live_trading.yaml"
echo ""
echo "  3. Enable and start the service:"
echo "     sudo systemctl enable $SERVICE_FILE"
echo "     sudo systemctl start $SERVICE_FILE"
echo ""
echo "  4. Check service status:"
echo "     sudo systemctl status $SERVICE_FILE"
echo "     sudo journalctl -u $SERVICE_FILE -f"
echo ""
echo "  5. View logs:"
echo "     tail -f $INSTALL_DIR/logs/live_trading.log"
echo "     tail -f $INSTALL_DIR/logs/orders.csv"
