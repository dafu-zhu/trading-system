# Logger Module

Centralized logging configuration with JSON support.

## Files

| File | Class | Purpose |
|------|-------|---------|
| `logger.py` | `setup_logging()` | Initialize logging from JSON config |
| | `JsonFormatter` | Format logs as JSON for parsing |
| `log_config.json` | - | Logging configuration file |

## Usage

```python
from logger.logger import setup_logging
import logging

# Call once at application startup
setup_logging()

# Get logger for your module
logger = logging.getLogger("src.backtester")

logger.info("Starting backtest")
logger.debug("Processing bar", extra={"symbol": "AAPL", "price": 150.25})
logger.error("Order failed", exc_info=True)
```

## Configuration

The `log_config.json` file defines:

- **Console handler**: Human-readable output to stdout
- **File handler**: Persistent logs to `logs/` directory
- **Queue handler**: Non-blocking async logging (Python 3.12+)

## Log Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Detailed diagnostic info |
| `INFO` | General operational messages |
| `WARNING` | Something unexpected but not critical |
| `ERROR` | Operation failed |
| `CRITICAL` | System-level failure |

## JSON Format

When using `JsonFormatter`, logs are structured as:

```json
{
    "timestamp": "2024-01-24T12:30:45.123Z",
    "level": "INFO",
    "logger": "src.backtester",
    "message": "Order filled",
    "symbol": "AAPL",
    "price": 150.25,
    "quantity": 100
}
```

## Log Files

```
logs/
  trading.log       # All logs
  trading_error.log # ERROR and above only
```
