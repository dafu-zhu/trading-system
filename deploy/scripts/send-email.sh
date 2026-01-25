#!/bin/bash
# Gmail SMTP Email Sender
# Uses curl to send email via Gmail's SMTP server
#
# Prerequisites:
#   1. Gmail account with 2FA enabled
#   2. App Password generated at: https://myaccount.google.com/apppasswords
#
# Environment variables (set in .env):
#   SMTP_FROM     - Your Gmail address
#   SMTP_PASSWORD - Gmail App Password (16 chars, no spaces)
#   ALERT_EMAIL   - Recipient email address
#
# Usage:
#   ./send-email.sh --subject "Subject" --body "Message body"
#   ./send-email.sh --subject "Subject" --body-file /path/to/file
#   echo "Message" | ./send-email.sh --subject "Subject" --stdin

set -e

# Load environment if not already set
if [[ -z "$SMTP_FROM" ]]; then
    ENV_FILE="${ENV_FILE:-/opt/trading-system/deploy/.env}"
    if [[ -f "$ENV_FILE" ]]; then
        source "$ENV_FILE"
    fi
fi

# Defaults
SUBJECT=""
BODY=""
BODY_FILE=""
USE_STDIN=false
PRIORITY="normal"  # normal, high, low

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --subject)
            SUBJECT="$2"
            shift 2
            ;;
        --body)
            BODY="$2"
            shift 2
            ;;
        --body-file)
            BODY_FILE="$2"
            shift 2
            ;;
        --stdin)
            USE_STDIN=true
            shift
            ;;
        --priority)
            PRIORITY="$2"
            shift 2
            ;;
        --to)
            ALERT_EMAIL="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 --subject <subject> [--body <text> | --body-file <path> | --stdin]"
            echo ""
            echo "Options:"
            echo "  --subject   Email subject (required)"
            echo "  --body      Email body text"
            echo "  --body-file Read body from file"
            echo "  --stdin     Read body from stdin"
            echo "  --priority  Email priority: normal, high, low"
            echo "  --to        Override recipient email"
            echo ""
            echo "Environment variables:"
            echo "  SMTP_FROM     Gmail sender address"
            echo "  SMTP_PASSWORD Gmail App Password"
            echo "  ALERT_EMAIL   Default recipient"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# Validate required vars
if [[ -z "$SMTP_FROM" ]]; then
    echo "ERROR: SMTP_FROM not set" >&2
    exit 1
fi

if [[ -z "$SMTP_PASSWORD" ]]; then
    echo "ERROR: SMTP_PASSWORD not set" >&2
    exit 1
fi

if [[ -z "$ALERT_EMAIL" ]]; then
    echo "ERROR: ALERT_EMAIL not set" >&2
    exit 1
fi

if [[ -z "$SUBJECT" ]]; then
    echo "ERROR: --subject is required" >&2
    exit 1
fi

# Get body content
if [[ "$USE_STDIN" == true ]]; then
    BODY=$(cat)
elif [[ -n "$BODY_FILE" ]]; then
    if [[ ! -f "$BODY_FILE" ]]; then
        echo "ERROR: Body file not found: $BODY_FILE" >&2
        exit 1
    fi
    BODY=$(cat "$BODY_FILE")
fi

if [[ -z "$BODY" ]]; then
    echo "ERROR: No email body provided" >&2
    exit 1
fi

# Set priority header
case $PRIORITY in
    high)
        PRIORITY_HEADER="X-Priority: 1\r\nImportance: high"
        ;;
    low)
        PRIORITY_HEADER="X-Priority: 5\r\nImportance: low"
        ;;
    *)
        PRIORITY_HEADER=""
        ;;
esac

# Build email message
TIMESTAMP=$(date -R)
MESSAGE_ID="<$(date +%s).$(openssl rand -hex 8)@trading-system>"

EMAIL_CONTENT="From: Trading System <$SMTP_FROM>
To: $ALERT_EMAIL
Subject: $SUBJECT
Date: $TIMESTAMP
Message-ID: $MESSAGE_ID
MIME-Version: 1.0
Content-Type: text/plain; charset=UTF-8
${PRIORITY_HEADER}

$BODY"

# Send via Gmail SMTP using curl
# --ssl-reqd requires SSL from start (port 465)
# Alternative: --starttls for port 587
curl --silent --show-error \
    --ssl-reqd \
    --url "smtps://smtp.gmail.com:465" \
    --user "${SMTP_FROM}:${SMTP_PASSWORD}" \
    --mail-from "$SMTP_FROM" \
    --mail-rcpt "$ALERT_EMAIL" \
    --upload-file - <<< "$EMAIL_CONTENT"

echo "Email sent successfully to $ALERT_EMAIL"
