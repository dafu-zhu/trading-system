#!/bin/bash
# Trading System Health Check
# Run via cron to monitor system health and alert on issues
#
# Checks:
#   1. Service is running (systemctl)
#   2. Health file is fresh (updated within 2 minutes)
#   3. No critical errors in recent logs
#
# Usage:
#   ./health-check.sh           # Run health check
#   ./health-check.sh --install # Install cron job (every 5 minutes)
#   ./health-check.sh --remove  # Remove cron job
#
# Cron example (check every 5 minutes):
#   */5 * * * * /opt/trading-system/deploy/scripts/health-check.sh >> /opt/trading-system/logs/health-check.log 2>&1

set -e

# Configuration
SERVICE_NAME="trading-system"
INSTALL_DIR="/opt/trading-system"
HEALTH_FILE="$INSTALL_DIR/data/health.json"
HEALTH_LOG="$INSTALL_DIR/logs/health-check.log"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Thresholds
MAX_HEALTH_AGE_SECONDS=120  # Health file must be updated within 2 minutes

# Load environment
ENV_FILE="$INSTALL_DIR/deploy/.env"
if [[ -f "$ENV_FILE" ]]; then
    source "$ENV_FILE"
fi

# ============================================================================
# Cron Management
# ============================================================================

install_cron() {
    local cron_entry="*/5 * * * * $SCRIPT_DIR/health-check.sh >> $HEALTH_LOG 2>&1"

    # Check if already installed
    if crontab -l 2>/dev/null | grep -q "health-check.sh"; then
        echo "Health check cron job already installed"
        return 0
    fi

    # Add to crontab
    (crontab -l 2>/dev/null || true; echo "$cron_entry") | crontab -
    echo "Health check cron job installed (runs every 5 minutes)"
    echo "Logs: $HEALTH_LOG"
}

remove_cron() {
    if ! crontab -l 2>/dev/null | grep -q "health-check.sh"; then
        echo "No health check cron job found"
        return 0
    fi

    crontab -l 2>/dev/null | grep -v "health-check.sh" | crontab -
    echo "Health check cron job removed"
}

# Handle cron management args
case "${1:-}" in
    --install)
        install_cron
        exit 0
        ;;
    --remove)
        remove_cron
        exit 0
        ;;
esac

# ============================================================================
# Health Check Functions
# ============================================================================

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
ISSUES=()

log() {
    echo "[$TIMESTAMP] $1"
}

add_issue() {
    ISSUES+=("$1")
}

# Check if service is running
check_service() {
    if ! systemctl is-active --quiet "$SERVICE_NAME"; then
        add_issue "Service $SERVICE_NAME is not running"
        return 1
    fi
    return 0
}

# Check health file freshness
check_health_file() {
    if [[ ! -f "$HEALTH_FILE" ]]; then
        add_issue "Health file missing: $HEALTH_FILE"
        return 1
    fi

    local file_age=$(($(date +%s) - $(stat -c %Y "$HEALTH_FILE" 2>/dev/null || stat -f %m "$HEALTH_FILE")))

    if [[ $file_age -gt $MAX_HEALTH_AGE_SECONDS ]]; then
        add_issue "Health file stale (${file_age}s old, max ${MAX_HEALTH_AGE_SECONDS}s)"
        return 1
    fi

    # Parse health file for status
    local status=$(python3 -c "
import json
try:
    with open('$HEALTH_FILE') as f:
        data = json.load(f)
    print(data.get('status', 'unknown'))
except:
    print('error')
" 2>/dev/null)

    if [[ "$status" != "running" && "$status" != "healthy" ]]; then
        add_issue "Health status is '$status' (expected 'running' or 'healthy')"
        return 1
    fi

    return 0
}

# Check for critical errors in recent logs
check_logs() {
    # Check last 5 minutes of journal for critical errors
    local critical_errors=$(journalctl -u "$SERVICE_NAME" --since "5 minutes ago" --no-pager 2>/dev/null | \
        grep -iE "(CRITICAL|FATAL|circuit.?breaker|out.?of.?memory)" | \
        head -5)

    if [[ -n "$critical_errors" ]]; then
        add_issue "Critical errors in logs: $critical_errors"
        return 1
    fi

    return 0
}

# Check disk space
check_disk() {
    local usage=$(df "$INSTALL_DIR" | awk 'NR==2 {print $5}' | tr -d '%')

    if [[ $usage -gt 90 ]]; then
        add_issue "Disk usage critical: ${usage}%"
        return 1
    fi

    return 0
}

# ============================================================================
# Main Check
# ============================================================================

log "Starting health check..."

# Run all checks (continue even if one fails)
check_service || true
check_health_file || true
check_logs || true
check_disk || true

# ============================================================================
# Report Results
# ============================================================================

if [[ ${#ISSUES[@]} -eq 0 ]]; then
    log "Health check PASSED"
    exit 0
fi

# Build alert message
HOSTNAME=$(hostname)
ISSUE_LIST=""
for issue in "${ISSUES[@]}"; do
    ISSUE_LIST+="  - $issue"$'\n'
done

log "Health check FAILED with ${#ISSUES[@]} issue(s)"

SUBJECT="[HEALTH] Trading System Issues Detected"
BODY="Trading System Health Check Failed

Server: $HOSTNAME
Time: $TIMESTAMP
Issues found: ${#ISSUES[@]}

Issues:
$ISSUE_LIST
Commands:
- Service status: systemctl status $SERVICE_NAME
- View logs: journalctl -u $SERVICE_NAME -f
- Health file: cat $HEALTH_FILE
- Restart: systemctl restart $SERVICE_NAME"

# Send alert if email configured
if [[ -n "$ALERT_EMAIL" ]]; then
    # Prefer Gmail SMTP
    if [[ -n "$SMTP_FROM" && -n "$SMTP_PASSWORD" && -x "$SCRIPT_DIR/send-email.sh" ]]; then
        "$SCRIPT_DIR/send-email.sh" \
            --subject "$SUBJECT" \
            --body "$BODY" \
            --to "$ALERT_EMAIL" 2>/dev/null && \
        log "Alert sent via Gmail"

    # Fallback: system mail
    elif command -v mail &> /dev/null; then
        echo "$BODY" | mail -s "$SUBJECT" "$ALERT_EMAIL" && \
        log "Alert sent via mail"
    else
        log "No email method available"
    fi
else
    log "ALERT_EMAIL not configured, no notification sent"
fi

exit 1
