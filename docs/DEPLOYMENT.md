# Deployment Guide

This guide covers deploying the trading system for production use.

## Prerequisites

- Python 3.13+
- Linux server (Ubuntu 22.04+ recommended)
- Alpaca API credentials (paper or live)
- `uv` package manager

## Quick Start

### Local Development

```bash
# Run in dry-run mode (no API connection)
python run_live.py --symbols AAPL,MSFT --dry-run --replay-days 5

# Run in paper trading mode
python run_live.py --symbols AAPL,MSFT --paper

# Run with custom config
python run_live.py --symbols AAPL --config config/live_trading.yaml --paper
```

### Server Deployment

```bash
# Install as systemd service (run as root)
sudo ./deploy/install.sh

# Configure environment
sudo nano /opt/trading-system/deploy/.env

# Start service
sudo systemctl enable trading-system.service
sudo systemctl start trading-system.service
```

## Configuration

### Environment Variables

Copy `deploy/trading-system.env.example` to `deploy/.env` and configure:

```bash
# Required
ALPACA_API_KEY=your_key
ALPACA_API_SECRET=your_secret
TRADING_SYMBOLS=AAPL,MSFT,GOOGL

# Risk limits
RISK_MAX_POSITION_SIZE=1000
RISK_MAX_POSITION_VALUE=100000
RISK_MAX_TOTAL_EXPOSURE=500000

# Stop loss
STOP_LOSS_POSITION_PCT=2.0
STOP_LOSS_USE_TRAILING=false
STOP_LOSS_CIRCUIT_BREAKER=true
```

### YAML Configuration

Create `config/live_trading.yaml`:

```yaml
trading:
  paper_mode: true
  dry_run: false

risk:
  max_position_size: 1000
  max_position_value: 100000
  max_total_exposure: 500000
  max_orders_per_minute: 100
  min_cash_buffer: 1000

stop_loss:
  position_stop_pct: 2.0
  trailing_stop_pct: 3.0
  portfolio_stop_pct: 5.0
  max_drawdown_pct: 10.0
  use_trailing_stops: false
  enable_circuit_breaker: true

enable_trading: true
enable_stop_loss: true
log_orders: true
data_type: trades  # trades, quotes, or bars
status_log_interval: 100
```

## CLI Reference

```
python run_live.py [OPTIONS]

Required:
  --symbols SYMBOLS     Comma-separated symbols (e.g., AAPL,MSFT,GOOGL)

Optional:
  --config PATH         Path to YAML config file
  --strategy NAME       Strategy class name (default: MACDStrategy)
  --dry-run             Simulate trading with historical data replay
  --paper               Use Alpaca paper trading (default)
  --live                Use Alpaca live trading (REAL MONEY!)
  --data-type TYPE      Data feed type: trades, quotes, bars (default: trades)
  --log-level LEVEL     Logging level: DEBUG, INFO, WARNING, ERROR
  --replay-days N       Days of history to replay in dry-run mode (default: 1)
  --timeframe TF        Bar timeframe for dry-run: 1Min, 5Min, etc.
  --yes, -y             Skip confirmation prompts
```

### Examples

```bash
# Paper trading with default MACD strategy
python run_live.py --symbols AAPL,MSFT --paper

# Dry-run with 5 days of historical replay
python run_live.py --symbols AAPL --dry-run --replay-days 5 --timeframe 1Min

# Live trading (requires confirmation)
python run_live.py --symbols AAPL --live --config config/live_trading.yaml

# Verbose logging for debugging
python run_live.py --symbols AAPL --paper --log-level DEBUG
```

## Systemd Service

### Service Management

```bash
# Start/stop/restart
sudo systemctl start trading-system
sudo systemctl stop trading-system
sudo systemctl restart trading-system

# Enable auto-start on boot
sudo systemctl enable trading-system

# Check status
sudo systemctl status trading-system

# View logs
sudo journalctl -u trading-system -f
sudo journalctl -u trading-system --since "1 hour ago"
```

### Service Configuration

Edit `/etc/systemd/system/trading-system.service`:

```ini
[Service]
# Change symbols
Environment=TRADING_SYMBOLS=AAPL,MSFT,GOOGL

# Restart policy
Restart=on-failure
RestartSec=30
StartLimitBurst=3
```

After changes:
```bash
sudo systemctl daemon-reload
sudo systemctl restart trading-system
```

## Monitoring

### Log Files

| File | Description |
|------|-------------|
| `logs/live_trading.log` | Main application log |
| `logs/orders.csv` | Order audit trail |

### Log Rotation

The application uses rotating file handlers:
- Max size: 10 MB per file
- Keeps 5 backup files
- Format: `live_trading.log`, `live_trading.log.1`, etc.

### Health Checks

Check if the service is running:
```bash
# Service status
systemctl is-active trading-system

# Process check
pgrep -f "run_live.py"

# Recent log entries
tail -20 /opt/trading-system/logs/live_trading.log
```

## Security

### File Permissions

```bash
# Protect credentials
chmod 600 /opt/trading-system/deploy/.env

# Service runs as non-root user
chown -R trading:trading /opt/trading-system
```

### Systemd Hardening

The service file includes security hardening:
- `NoNewPrivileges=yes` - Prevents privilege escalation
- `ProtectSystem=strict` - Read-only filesystem except allowed paths
- `ProtectHome=yes` - No access to home directories
- `ReadWritePaths=` - Only logs and data directories writable

### API Key Security

- Never commit `.env` files to git
- Use environment variables, not hardcoded values
- Consider using secrets managers for production

## Troubleshooting

### Common Issues

**Service won't start:**
```bash
# Check for syntax errors
python -m py_compile /opt/trading-system/run_live.py

# Check environment file
cat /opt/trading-system/deploy/.env

# Check permissions
ls -la /opt/trading-system/
```

**Connection errors:**
```bash
# Verify API credentials
python -c "
from alpaca.trading.client import TradingClient
client = TradingClient('KEY', 'SECRET', paper=True)
print(client.get_account())
"
```

**No trades executing:**
- Check `enable_trading: true` in config
- Verify `dry_run: false`
- Check rate limits in logs
- Verify sufficient buying power

### Debug Mode

Run with verbose logging:
```bash
python run_live.py --symbols AAPL --paper --log-level DEBUG
```

### Recovery

If circuit breaker triggers:
```bash
# Restart service to reset circuit breaker
sudo systemctl restart trading-system
```

If rate limits hit:
- Service will auto-resume after rate limit window (1 minute)
- Consider adjusting `max_orders_per_minute` in config

## Performance

### Resource Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 1 core | 2+ cores |
| RAM | 512 MB | 2+ GB |
| Disk | 1 GB | 10+ GB |
| Network | 1 Mbps | 10+ Mbps |

### Optimization

- Use `data_type: trades` for lowest latency
- Limit number of symbols for faster processing
- Consider running multiple instances for many symbols

## Backup

### What to Backup

- `deploy/.env` - Credentials and configuration
- `config/*.yaml` - Trading configuration
- `logs/orders.csv` - Order audit trail
- `data/` - SQLite database with historical data

### Backup Script

```bash
#!/bin/bash
BACKUP_DIR="/backup/trading-system/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"
cp /opt/trading-system/deploy/.env "$BACKUP_DIR/"
cp -r /opt/trading-system/config "$BACKUP_DIR/"
cp /opt/trading-system/logs/orders.csv "$BACKUP_DIR/"
cp /opt/trading-system/data/*.db "$BACKUP_DIR/"
```
