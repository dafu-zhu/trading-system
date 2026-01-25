#!/bin/bash
# Trading System Failure Notification with Escalation
# Called by systemd OnFailure directive
#
# Failure Escalation Logic:
#   - Tracks failures in a rolling 10-minute window
#   - < 3 failures: Normal alert, service auto-restarts
#   - >= 3 failures: CRITICAL alert, manual intervention required
#
# State file: /opt/trading-system/data/failure_state.json

set -e

# Configuration
SERVICE_NAME="trading-system"
INSTALL_DIR="/opt/trading-system"
STATE_FILE="$INSTALL_DIR/data/failure_state.json"
CRASH_LOG="$INSTALL_DIR/logs/crashes.log"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Escalation thresholds
FAILURE_WINDOW_SECONDS=600  # 10 minutes
CRITICAL_THRESHOLD=3        # >= 3 failures = critical

# Load environment
ENV_FILE="$INSTALL_DIR/deploy/.env"
if [[ -f "$ENV_FILE" ]]; then
    source "$ENV_FILE"
fi

# Ensure directories exist
mkdir -p "$(dirname "$STATE_FILE")"
mkdir -p "$(dirname "$CRASH_LOG")"

# Get current timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
UNIX_TIME=$(date +%s)

# Get failure reason from journal
FAILURE_REASON=$(journalctl -u "$SERVICE_NAME" -n 50 --no-pager 2>/dev/null | tail -30 || echo "Unable to retrieve journal")

# Log the crash locally
{
    echo "========================================"
    echo "CRASH at $TIMESTAMP"
    echo "========================================"
    echo "$FAILURE_REASON"
    echo ""
} >> "$CRASH_LOG"

# ============================================================================
# Failure State Management
# ============================================================================

# Initialize state file if missing
if [[ ! -f "$STATE_FILE" ]]; then
    echo '{"failures": [], "last_critical": null}' > "$STATE_FILE"
fi

# Read current state (using Python for JSON parsing - available on most systems)
read_state() {
    python3 -c "
import json
import sys
try:
    with open('$STATE_FILE', 'r') as f:
        state = json.load(f)
    print(json.dumps(state))
except:
    print('{\"failures\": [], \"last_critical\": null}')
"
}

# Update state with new failure
update_state() {
    local cutoff=$((UNIX_TIME - FAILURE_WINDOW_SECONDS))

    python3 << EOF
import json
from datetime import datetime

try:
    with open('$STATE_FILE', 'r') as f:
        state = json.load(f)
except:
    state = {"failures": [], "last_critical": None}

# Add new failure
state["failures"].append({
    "timestamp": $UNIX_TIME,
    "datetime": "$TIMESTAMP"
})

# Remove failures outside the window
cutoff = $cutoff
state["failures"] = [f for f in state["failures"] if f["timestamp"] > cutoff]

# Save state
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f, indent=2)

# Output failure count
print(len(state["failures"]))
EOF
}

# Mark as critical
mark_critical() {
    python3 << EOF
import json

with open('$STATE_FILE', 'r') as f:
    state = json.load(f)

state["last_critical"] = "$TIMESTAMP"

with open('$STATE_FILE', 'w') as f:
    json.dump(state, f, indent=2)
EOF
}

# ============================================================================
# Count failures and determine severity
# ============================================================================

FAILURE_COUNT=$(update_state)
echo "[$TIMESTAMP] Failure count in last 10 minutes: $FAILURE_COUNT" >> "$CRASH_LOG"

if [[ $FAILURE_COUNT -ge $CRITICAL_THRESHOLD ]]; then
    SEVERITY="CRITICAL"
    mark_critical
else
    SEVERITY="WARNING"
fi

# ============================================================================
# Build notification message
# ============================================================================

HOSTNAME=$(hostname)

if [[ "$SEVERITY" == "CRITICAL" ]]; then
    SUBJECT="[CRITICAL] Trading System - Manual Intervention Required"
    PRIORITY="high"

    BODY="CRITICAL: Trading System has crashed $FAILURE_COUNT times in 10 minutes.

MANUAL INTERVENTION REQUIRED

The system has hit the crash threshold and requires investigation.
Auto-restart is suspended until the issue is resolved.

Server: $HOSTNAME
Time: $TIMESTAMP
Failures in window: $FAILURE_COUNT
Threshold: $CRITICAL_THRESHOLD

IMMEDIATE ACTIONS REQUIRED:
1. Check system logs: journalctl -u $SERVICE_NAME -n 200
2. Check application logs: tail -100 $INSTALL_DIR/logs/live_trading.log
3. Investigate and fix the root cause
4. Clear failure state: rm $STATE_FILE
5. Restart service: systemctl restart $SERVICE_NAME

Last 30 lines of log:
----------------------------------------
$FAILURE_REASON
----------------------------------------

Do NOT restart without investigating. The system may be in a crash loop."

else
    SUBJECT="[ALERT] Trading System Crashed - Auto-Restarting"
    PRIORITY="normal"

    BODY="Trading system crashed at $TIMESTAMP

The service will auto-restart in 30 seconds.

Server: $HOSTNAME
Failures in last 10 min: $FAILURE_COUNT/$CRITICAL_THRESHOLD
Status: Normal (auto-recovering)

Last 30 lines of log:
----------------------------------------
$FAILURE_REASON
----------------------------------------

Commands:
- Status: systemctl status $SERVICE_NAME
- Logs: journalctl -u $SERVICE_NAME -f
- App logs: tail -f $INSTALL_DIR/logs/live_trading.log"

fi

# ============================================================================
# Send notification
# ============================================================================

if [[ -z "$ALERT_EMAIL" ]]; then
    echo "[$TIMESTAMP] No ALERT_EMAIL configured, skipping notification" >> "$CRASH_LOG"
    exit 0
fi

# Prefer Gmail SMTP if configured
if [[ -n "$SMTP_FROM" && -n "$SMTP_PASSWORD" ]]; then
    if [[ -x "$SCRIPT_DIR/send-email.sh" ]]; then
        "$SCRIPT_DIR/send-email.sh" \
            --subject "$SUBJECT" \
            --body "$BODY" \
            --priority "$PRIORITY" \
            --to "$ALERT_EMAIL" 2>> "$CRASH_LOG" && \
        echo "[$TIMESTAMP] Email sent via Gmail SMTP ($SEVERITY)" >> "$CRASH_LOG"
    else
        echo "[$TIMESTAMP] send-email.sh not found or not executable" >> "$CRASH_LOG"
    fi

# Fallback: system mail command
elif command -v mail &> /dev/null; then
    echo "$BODY" | mail -s "$SUBJECT" "$ALERT_EMAIL" && \
    echo "[$TIMESTAMP] Email sent via mail command ($SEVERITY)" >> "$CRASH_LOG"

# Fallback: Mailgun API
elif [[ -n "$MAILGUN_API_KEY" && -n "$MAILGUN_DOMAIN" ]]; then
    curl -s --user "api:$MAILGUN_API_KEY" \
        "https://api.mailgun.net/v3/$MAILGUN_DOMAIN/messages" \
        -F from="Trading System <alerts@$MAILGUN_DOMAIN>" \
        -F to="$ALERT_EMAIL" \
        -F subject="$SUBJECT" \
        -F text="$BODY" && \
    echo "[$TIMESTAMP] Email sent via Mailgun ($SEVERITY)" >> "$CRASH_LOG"

# Fallback: SendGrid API
elif [[ -n "$SENDGRID_API_KEY" ]]; then
    # Escape body for JSON
    BODY_ESCAPED=$(echo "$BODY" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')

    curl -s --request POST \
        --url https://api.sendgrid.com/v3/mail/send \
        --header "Authorization: Bearer $SENDGRID_API_KEY" \
        --header "Content-Type: application/json" \
        --data "{
            \"personalizations\": [{\"to\": [{\"email\": \"$ALERT_EMAIL\"}]}],
            \"from\": {\"email\": \"alerts@trading-system.local\"},
            \"subject\": \"$SUBJECT\",
            \"content\": [{\"type\": \"text/plain\", \"value\": $BODY_ESCAPED}]
        }" && \
    echo "[$TIMESTAMP] Email sent via SendGrid ($SEVERITY)" >> "$CRASH_LOG"

else
    echo "[$TIMESTAMP] No email method configured (Gmail/mail/Mailgun/SendGrid)" >> "$CRASH_LOG"
fi

# Log final status
echo "[$TIMESTAMP] Notification complete: severity=$SEVERITY, failures=$FAILURE_COUNT" >> "$CRASH_LOG"
