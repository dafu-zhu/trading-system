#!/bin/bash
# Trading System Uninstall Script
# Cleanly removes all trading system components
#
# Usage:
#   sudo ./uninstall.sh           # Interactive uninstall
#   sudo ./uninstall.sh --force   # Non-interactive, remove everything
#   sudo ./uninstall.sh --keep-data  # Keep logs and data

set -e

# Configuration
INSTALL_DIR="/opt/trading-system"
SERVICE_USER="trading"
SERVICES=(
    "trading-system.service"
    "trading-system-notify.service"
    "trading-system-health.service"
)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse arguments
FORCE=false
KEEP_DATA=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE=true
            shift
            ;;
        --keep-data)
            KEEP_DATA=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --force      Non-interactive, remove everything"
            echo "  --keep-data  Keep logs, data, and .env file"
            echo "  --help       Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    log_error "This script must be run as root or with sudo"
    exit 1
fi

# Confirmation
if [[ "$FORCE" != true ]]; then
    echo "This will uninstall the trading system from $INSTALL_DIR"
    echo ""
    echo "The following will be removed:"
    echo "  - Systemd services: ${SERVICES[*]}"
    echo "  - Installation directory: $INSTALL_DIR"
    if [[ "$KEEP_DATA" != true ]]; then
        echo "  - All logs and data"
    else
        echo "  - (Keeping logs and data)"
    fi
    echo ""
    read -p "Are you sure you want to continue? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Uninstall cancelled"
        exit 0
    fi
fi

log_info "Starting uninstall..."

# Stop and disable services
for service in "${SERVICES[@]}"; do
    if systemctl is-active --quiet "$service" 2>/dev/null; then
        log_info "Stopping $service..."
        systemctl stop "$service" || true
    fi

    if systemctl is-enabled --quiet "$service" 2>/dev/null; then
        log_info "Disabling $service..."
        systemctl disable "$service" || true
    fi

    if [[ -f "/etc/systemd/system/$service" ]]; then
        log_info "Removing $service..."
        rm -f "/etc/systemd/system/$service"
    fi
done

# Reload systemd
systemctl daemon-reload

# Remove health check cron job
if crontab -l -u "$SERVICE_USER" 2>/dev/null | grep -q "health-check.sh"; then
    log_info "Removing health check cron job..."
    crontab -l -u "$SERVICE_USER" 2>/dev/null | grep -v "health-check.sh" | crontab -u "$SERVICE_USER" - || true
fi

# Remove installation directory
if [[ -d "$INSTALL_DIR" ]]; then
    if [[ "$KEEP_DATA" == true ]]; then
        log_info "Keeping data directories..."

        # Backup important files
        DATA_BACKUP="$INSTALL_DIR-backup-$(date +%Y%m%d%H%M%S)"
        mkdir -p "$DATA_BACKUP"

        [[ -d "$INSTALL_DIR/logs" ]] && mv "$INSTALL_DIR/logs" "$DATA_BACKUP/"
        [[ -d "$INSTALL_DIR/data" ]] && mv "$INSTALL_DIR/data" "$DATA_BACKUP/"
        [[ -f "$INSTALL_DIR/deploy/.env" ]] && cp "$INSTALL_DIR/deploy/.env" "$DATA_BACKUP/"

        log_info "Data backed up to: $DATA_BACKUP"

        # Remove the rest
        rm -rf "$INSTALL_DIR"

        # Restore backup to expected location
        mkdir -p "$INSTALL_DIR"
        mv "$DATA_BACKUP"/* "$INSTALL_DIR/" 2>/dev/null || true
        rmdir "$DATA_BACKUP" 2>/dev/null || true

        log_info "Kept: $INSTALL_DIR/logs, $INSTALL_DIR/data, and .env"
    else
        log_info "Removing $INSTALL_DIR..."
        rm -rf "$INSTALL_DIR"
    fi
fi

# Remove service user (optional - commented out for safety)
# if id "$SERVICE_USER" &>/dev/null; then
#     log_info "Removing service user: $SERVICE_USER"
#     userdel "$SERVICE_USER" 2>/dev/null || true
# fi

log_info "Uninstall complete!"
echo ""
echo "Notes:"
echo "  - Service user '$SERVICE_USER' was NOT removed (may be used by other services)"
if [[ "$KEEP_DATA" == true ]]; then
    echo "  - Data and logs preserved at: $INSTALL_DIR"
fi
echo ""
echo "To completely remove the user (if not needed):"
echo "  sudo userdel $SERVICE_USER"
