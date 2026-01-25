# Trading System Deployment Guide

Complete guide for deploying the trading system for 24/7 operation with failure notifications and health monitoring.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Free VM Setup](#free-vm-setup)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Gmail App Password Setup](#gmail-app-password-setup)
6. [Monitoring Options](#monitoring-options)
7. [Operations](#operations)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Linux server (Ubuntu 20.04+ recommended)
- Python 3.11+
- Root/sudo access
- Alpaca API credentials (paper or live)
- Gmail account for alerts (optional but recommended)

### Required Packages

```bash
sudo apt update
sudo apt install -y python3 python3-pip git curl
```

---

## Free VM Setup

### Option 1: Oracle Cloud (Recommended)

Oracle offers an **always-free tier** with:
- 2 ARM-based VMs (4 OCPU, 24GB RAM each)
- 200GB storage

1. Sign up at [cloud.oracle.com](https://cloud.oracle.com/)
2. Create a VM instance:
   - Shape: `VM.Standard.A1.Flex` (ARM)
   - Image: Ubuntu 22.04
   - Configure SSH keys
3. Open port 8080 if using health endpoint:
   - Security List → Add Ingress Rule → Port 8080

### Option 2: Google Cloud Platform

GCP offers a **free tier** with:
- 1 e2-micro VM (0.25 vCPU, 1GB RAM)
- 30GB storage

1. Sign up at [cloud.google.com](https://cloud.google.com/)
2. Create VM:
   - Machine type: `e2-micro`
   - Region: `us-east1`, `us-west1`, or `us-central1`
   - Image: Ubuntu 22.04
3. Allow HTTP traffic if using health endpoint

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/trading-system.git
cd trading-system
```

### 2. Run the Installer

```bash
# Standard installation
sudo ./deploy/install.sh

# With optional HTTP health endpoint
sudo ./deploy/install.sh --with-health
```

### 3. Configure Trading Symbols

```bash
sudo nano /opt/trading-system/config/symbols.txt
```

One symbol per line, comments with `#`:
```
# Mega cap tech
AAPL    # Apple
MSFT    # Microsoft
NVDA    # NVIDIA

# Financials
JPM
GS
```

### 4. Configure Environment

```bash
sudo nano /opt/trading-system/deploy/.env
```

Required settings:
```bash
# Alpaca API
ALPACA_API_KEY=your_api_key
ALPACA_API_SECRET=your_api_secret

# Email alerts
ALERT_EMAIL=you@example.com
SMTP_FROM=your-gmail@gmail.com
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx  # Gmail App Password
```

### 5. Start the Service

```bash
sudo systemctl enable trading-system
sudo systemctl start trading-system
```

---

## Configuration

### Environment Variables

All configuration is in `/opt/trading-system/deploy/.env`.

#### Trading Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TRADING_SYMBOLS` | `AAPL,MSFT,GOOGL` | Comma-separated symbols |
| `TRADING_DRY_RUN` | `true` | `true` = simulate orders |
| `TRADING_ENABLE` | `true` | `false` = monitoring only |
| `TRADING_PAPER_MODE` | `true` | `false` = REAL MONEY |

#### Risk Management

| Variable | Default | Description |
|----------|---------|-------------|
| `RISK_MAX_POSITION_SIZE` | `1000` | Max shares per position |
| `RISK_MAX_POSITION_VALUE` | `100000` | Max $ per position |
| `STOP_LOSS_POSITION_PCT` | `2.0` | Position stop-loss % |
| `STOP_LOSS_CIRCUIT_BREAKER` | `true` | Halt on major drawdown |

#### Email Alerts

| Variable | Description |
|----------|-------------|
| `ALERT_EMAIL` | Recipient email address |
| `SMTP_FROM` | Gmail sender address |
| `SMTP_PASSWORD` | Gmail App Password (16 chars) |

### Trading Config YAML (Optional)

For advanced configuration, create `/opt/trading-system/config/live_trading.yaml`:

```yaml
trading:
  dry_run: false
  paper_mode: true

risk:
  max_position_size: 500
  max_position_value: 50000

stop_loss:
  position_pct: 2.0
  trailing_pct: 3.0
  use_trailing: true
```

---

## Gmail App Password Setup

Gmail App Passwords allow sending email without your main password.

### Step 1: Enable 2-Factor Authentication

1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Under "How you sign in", click **2-Step Verification**
3. Follow the setup wizard

### Step 2: Create App Password

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Select **Mail** as the app
3. Select **Other (Custom name)** as the device
4. Enter "Trading System" as the name
5. Click **Generate**
6. Copy the 16-character password (e.g., `abcd efgh ijkl mnop`)
7. Remove spaces and add to `.env`:
   ```
   SMTP_PASSWORD=abcdefghijklmnop
   ```

### Testing Email

```bash
# Test the email sender directly
cd /opt/trading-system
sudo -u trading ./deploy/scripts/send-email.sh \
    --subject "Test Email" \
    --body "Hello from Trading System"
```

---

## Monitoring Options

### File-Based Health (Default)

The live engine writes health status to `/opt/trading-system/data/health.json` every 30 seconds:

```json
{
  "status": "running",
  "timestamp": "2024-01-15T10:30:00Z",
  "uptime_seconds": 3600,
  "metrics": {
    "tick_count": 1200,
    "orders_filled": 5
  },
  "portfolio": {
    "portfolio_value": 100500.00,
    "pnl": 500.00,
    "pnl_percent": 0.5
  }
}
```

### Cron-Based Health Check

Install the health check cron job:

```bash
# As the trading user
sudo -u trading /opt/trading-system/deploy/scripts/health-check.sh --install
```

This checks every 5 minutes and sends alerts if:
- Service is not running
- Health file is stale (>2 minutes old)
- Critical errors in logs
- Disk usage > 90%

### HTTP Health Endpoint (Optional)

For external monitoring (UptimeRobot, Pingdom, etc.):

```bash
# Install and start health service
sudo systemctl enable trading-system-health
sudo systemctl start trading-system-health

# Test
curl http://localhost:8080/health
```

Endpoints:
- `GET /health` - Returns 200 if healthy, 503 if unhealthy
- `GET /metrics` - Full health data (JSON)
- `GET /` - Simple status page

---

## Operations

### Starting/Stopping

```bash
# Start
sudo systemctl start trading-system

# Stop
sudo systemctl stop trading-system

# Restart
sudo systemctl restart trading-system

# Check status
sudo systemctl status trading-system
```

### Viewing Logs

```bash
# Systemd journal
sudo journalctl -u trading-system -f

# Application logs
tail -f /opt/trading-system/logs/live_trading.log

# Order log
tail -f /opt/trading-system/logs/orders.csv

# Crash log
cat /opt/trading-system/logs/crashes.log
```

### Checking Health

```bash
# Health file
cat /opt/trading-system/data/health.json | python3 -m json.tool

# HTTP endpoint (if enabled)
curl http://localhost:8080/health

# Failure state
cat /opt/trading-system/data/failure_state.json
```

### Clearing Failure State

After investigating repeated crashes:

```bash
# Clear the failure counter
sudo rm /opt/trading-system/data/failure_state.json

# Restart service
sudo systemctl restart trading-system
```

---

## Failure Escalation

The system tracks crashes in a 10-minute rolling window:

| Failures | Action |
|----------|--------|
| 1-2 | Normal alert, auto-restart in 30s |
| 3+ | **CRITICAL** alert, requires manual intervention |

Critical alerts include:
- Instructions to investigate
- Recent log output
- Commands to check and restart

### Investigating Critical Alerts

```bash
# 1. Check recent logs
sudo journalctl -u trading-system -n 200

# 2. Check application logs
tail -200 /opt/trading-system/logs/live_trading.log

# 3. Check crash log
cat /opt/trading-system/logs/crashes.log

# 4. After fixing, clear state and restart
sudo rm /opt/trading-system/data/failure_state.json
sudo systemctl restart trading-system
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check for errors
sudo journalctl -u trading-system -n 50

# Verify environment
sudo -u trading cat /opt/trading-system/deploy/.env

# Test manually
cd /opt/trading-system
sudo -u trading .venv/bin/python run_live.py --symbols AAPL --dry-run
```

### Email Not Sending

```bash
# Test email script
sudo -u trading /opt/trading-system/deploy/scripts/send-email.sh \
    --subject "Test" --body "Testing"

# Check Gmail App Password
# - Must be 16 characters (no spaces)
# - 2FA must be enabled on Gmail account
# - Less secure apps must NOT be enabled
```

### Health Check Failing

```bash
# Check health file age
ls -la /opt/trading-system/data/health.json

# Check if engine is writing health
sudo journalctl -u trading-system -n 20 | grep -i health

# Manually run health check
sudo -u trading /opt/trading-system/deploy/scripts/health-check.sh
```

### Permission Issues

```bash
# Fix ownership
sudo chown -R trading:trading /opt/trading-system

# Fix permissions
sudo chmod 755 /opt/trading-system/logs /opt/trading-system/data
sudo chmod 600 /opt/trading-system/deploy/.env
```

### Uninstalling

```bash
# Clean uninstall (keeps data)
sudo ./deploy/uninstall.sh --keep-data

# Full uninstall
sudo ./deploy/uninstall.sh --force
```

---

## File Structure

```
/opt/trading-system/
├── src/                    # Application source
├── run_live.py             # Entry point
├── config/
│   └── live_trading.yaml   # Trading configuration
├── data/
│   ├── trading.db          # Market data cache
│   ├── health.json         # Health status
│   └── failure_state.json  # Crash tracking
├── logs/
│   ├── live_trading.log    # Application log
│   ├── orders.csv          # Order audit trail
│   └── crashes.log         # Crash history
└── deploy/
    ├── .env                # Environment secrets
    ├── systemd/            # Service files
    ├── scripts/            # Helper scripts
    └── monitoring/         # Health server
```

---

## Security Notes

1. **Never commit `.env`** to version control
2. **Use paper trading** until you're confident
3. **Set appropriate risk limits** before going live
4. **Monitor regularly** - don't just set and forget
5. **Keep backups** of logs and configuration
