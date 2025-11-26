# Modern Python Logging Guideline

## Table of Contents

1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Architecture Pattern](#architecture-pattern)
4. [Step-by-Step Implementation](#step-by-step-implementation)
5. [Configuration Progression](#configuration-progression)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

## Overview

This tutorial demonstrates a **production-ready logging system** for Python applications using the standard `logging` module. The final implementation showcases modern patterns that provide structured logging, non-blocking I/O, and flexible configuration.

### What You'll Learn

- How to create custom JSON formatters for structured logging
- How to configure logging via external JSON/YAML files
- How to use queue-based handlers for async, non-blocking logging
- How to route logs to multiple destinations with different formats
- How to implement custom filters for advanced log routing
- How to ensure graceful cleanup on application exit

### Requirements

- **Python 3.12+** for full feature support (QueueHandler auto-configuration)
- Python 3.9-3.11 compatible with minor modifications
- Python 3.8 and below require additional changes (see [Python Version Notes](#python-version-notes))

## Key Features

### 1. Custom JSON Formatter

**Purpose**: Output structured, machine-readable logs

**Benefits**:
- Easy parsing by log aggregation tools (ELK, Splunk, CloudWatch)
- Consistent structure across all log entries
- Supports custom fields via `extra` parameter
- Automatic UTC timestamps in ISO format
- Graceful handling of exceptions and stack traces

**Example Output**:
```json
{"level": "ERROR", "message": "Database connection failed", "timestamp": "2024-01-23T15:20:53.151737+00:00", "logger": "my_app", "module": "database", "function": "connect", "line": 42, "thread_name": "MainThread", "db_host": "prod-db-01"}
```

### 2. Queue-Based Async Logging

**Purpose**: Prevent I/O operations from blocking your application

**Benefits**:
- Logging happens in background thread
- Main application thread never waits for file/network I/O
- Critical for high-performance applications
- Automatic queue management in Python 3.12+

**How It Works**:
```
Application Thread          Queue           Background Thread
     |                       |                      |
log.info("msg") -----> [Queue.put()] -----> [Listener picks up]
     |                       |                      |
continues immediately        |              writes to file/console
```

### 3. Multiple Handlers with Different Formats

**Purpose**: Different audiences need different log formats

**Common Pattern**:
- **Console (stderr)**: Human-readable, warnings and above only
- **File (JSON)**: All logs, structured format for analysis
- **Optional stdout**: Info/debug only (filtered)

### 4. Custom Filters

**Purpose**: Route specific log levels to specific handlers

**Example Use Cases**:
- Send DEBUG/INFO to stdout, WARNING+ to stderr
- Filter out sensitive information
- Route logs from specific modules differently
- Implement sampling (log every Nth message)

### 5. Configuration-Based Setup

**Purpose**: Separate logging configuration from code

**Benefits**:
- Change logging behavior without code changes
- Different configs for dev/staging/prod
- Version control your logging setup
- Support both JSON and YAML formats

## Architecture Pattern

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Your Application                       │
│                   logger.info("message")                    │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Queue Handler  │
                    │  (Non-blocking) │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
    ┌──────────────────┐         ┌──────────────────────┐
    │ StreamHandler    │         │ RotatingFileHandler  │
    │ (stderr)         │         │ (JSON file)          │
    │ Level: WARNING   │         │ Level: DEBUG         │
    │ Format: Simple   │         │ Format: JSON         │
    └──────────────────┘         └──────────────────────┘
              │                             │
              ▼                             ▼
        Console Output              logs/my_app.log.jsonl
     WARNING: error msg      {"level":"DEBUG","message":"..."}
```

### Data Flow

1. **Application logs a message**: `logger.info("User logged in", extra={"user_id": 123})`
2. **Root logger receives it**: Checks if level >= DEBUG (passes)
3. **QueueHandler queues it**: Non-blocking put to internal queue
4. **Background thread picks it up**: QueueListener processes queue
5. **Each handler filters**:
   - stderr: WARNING+ only → discards this INFO message
   - file: DEBUG+ → accepts and formats as JSON
6. **Formatters process**: JSON formatter creates structured output
7. **Handlers write**: File rotated if needed, written to disk

## Step-by-Step Implementation

### Step 1: Create the Custom Formatter

Create `mylogger.py`:

```python
import datetime as dt
import json
import logging
from typing import override

# All built-in LogRecord attributes - we'll filter these out
# to avoid cluttering our JSON with internal logging fields
LOG_RECORD_BUILTIN_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


class MyJSONFormatter(logging.Formatter):
    """
    Custom JSON formatter that outputs one JSON object per line (JSONL format).

    Features:
    - Configurable field mapping via fmt_keys
    - Automatic UTC timestamp in ISO format
    - Exception and stack trace handling
    - Custom fields from extra parameter
    """

    def __init__(
        self,
        *,
        fmt_keys: dict[str, str] | None = None,
    ):
        """
        Initialize the formatter.

        Args:
            fmt_keys: Maps output field names to LogRecord attributes.
                     Example: {"level": "levelname", "time": "timestamp"}
        """
        super().__init__()
        self.fmt_keys = fmt_keys if fmt_keys is not None else {}

    @override
    def format(self, record: logging.LogRecord) -> str:
        """Convert LogRecord to JSON string."""
        message = self._prepare_log_dict(record)
        return json.dumps(message, default=str)

    def _prepare_log_dict(self, record: logging.LogRecord):
        """Build the dictionary that will be converted to JSON."""

        # These fields are always included
        always_fields = {
            "message": record.getMessage(),
            "timestamp": dt.datetime.fromtimestamp(
                record.created, tz=dt.timezone.utc
            ).isoformat(),
        }

        # Add exception info if this is an error log
        if record.exc_info is not None:
            always_fields["exc_info"] = self.formatException(record.exc_info)

        # Add stack trace if requested
        if record.stack_info is not None:
            always_fields["stack_info"] = self.formatStack(record.stack_info)

        # Map configured fields (e.g., "level" -> record.levelname)
        # Uses walrus operator for efficiency
        message = {
            key: msg_val
            if (msg_val := always_fields.pop(val, None)) is not None
            else getattr(record, val)
            for key, val in self.fmt_keys.items()
        }

        # Add back any always_fields that weren't mapped
        message.update(always_fields)

        # Add custom fields from extra parameter
        # e.g., logger.info("msg", extra={"user_id": 123})
        for key, val in record.__dict__.items():
            if key not in LOG_RECORD_BUILTIN_ATTRS:
                message[key] = val

        return message
```

**Key Points**:

- **`LOG_RECORD_BUILTIN_ATTRS`**: Set of all standard LogRecord attributes. Any attribute not in this set is considered custom and will be included in output.
- **`fmt_keys`**: Allows renaming fields. For example, `{"level": "levelname"}` outputs `"level"` instead of `"levelname"` in JSON.
- **Walrus operator (`:=`)**: Efficiently checks if a field exists in `always_fields` and uses it, otherwise gets from `record`.
- **`default=str`**: Ensures non-JSON-serializable objects (like datetime) are converted to strings.

### Step 2: Create Custom Filters (Optional)

Add to `mylogger.py`:

```python
class NonErrorFilter(logging.Filter):
    """
    Filter that only allows logs at INFO level or below.
    Useful for splitting INFO/DEBUG to stdout and WARNING+ to stderr.
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool | logging.LogRecord:
        """Return True if record should be logged."""
        return record.levelno <= logging.INFO
```

**Usage Example**:
```python
# In configuration, attach to a handler:
# - stdout handler with NonErrorFilter: gets DEBUG, INFO
# - stderr handler without filter, level=WARNING: gets WARNING, ERROR, CRITICAL
```

### Step 3: Create Directory Structure

```bash
mkdir -p logs
mkdir -p logging_configs
```

### Step 4: Create Configuration Files

#### Basic Configuration (0-stdout.json)

```json
{
  "version": 1,
  "disable_existing_loggers": false,
  "formatters": {
    "simple": {
      "format": "%(levelname)s: %(message)s"
    }
  },
  "handlers": {
    "stdout": {
      "class": "logging.StreamHandler",
      "formatter": "simple",
      "stream": "ext://sys.stdout"
    }
  },
  "loggers": {
    "root": {
      "level": "DEBUG",
      "handlers": ["stdout"]
    }
  }
}
```

**Explanation**:
- `version: 1`: Required, indicates dictConfig format version
- `disable_existing_loggers: false`: Don't disable existing loggers (important!)
- `ext://sys.stdout`: External object reference syntax
- `root`: The root logger (all loggers inherit from this)

#### Advanced Configuration (5-queued-stderr-json-file.json)

```json
{
  "version": 1,
  "disable_existing_loggers": false,
  "formatters": {
    "simple": {
      "format": "[%(levelname)s|%(module)s|L%(lineno)d] %(asctime)s: %(message)s",
      "datefmt": "%Y-%m-%dT%H:%M:%S%z"
    },
    "json": {
      "()": "mylogger.MyJSONFormatter",
      "fmt_keys": {
        "level": "levelname",
        "message": "message",
        "timestamp": "timestamp",
        "logger": "name",
        "module": "module",
        "function": "funcName",
        "line": "lineno",
        "thread_name": "threadName"
      }
    }
  },
  "handlers": {
    "stderr": {
      "class": "logging.StreamHandler",
      "level": "WARNING",
      "formatter": "simple",
      "stream": "ext://sys.stderr"
    },
    "file_json": {
      "class": "logging.handlers.RotatingFileHandler",
      "level": "DEBUG",
      "formatter": "json",
      "filename": "logs/my_app.log.jsonl",
      "maxBytes": 10000,
      "backupCount": 3
    },
    "queue_handler": {
      "class": "logging.handlers.QueueHandler",
      "handlers": [
        "stderr",
        "file_json"
      ],
      "respect_handler_level": true
    }
  },
  "loggers": {
    "root": {
      "level": "DEBUG",
      "handlers": [
        "queue_handler"
      ]
    }
  }
}
```

**Explanation**:
- **Custom formatter**: `"()": "mylogger.MyJSONFormatter"` uses factory syntax to instantiate our class
- **fmt_keys**: Passed as keyword argument to `MyJSONFormatter.__init__()`
- **RotatingFileHandler**: Automatically rotates when file reaches `maxBytes`, keeps `backupCount` old files
- **QueueHandler** (Python 3.12+):
  - `handlers`: List of handlers to wrap
  - `respect_handler_level: true`: Each handler's level is respected
  - Automatically creates queue and listener
- **Root logger**: Points only to queue_handler, which then routes to others

### Step 5: Setup Logging in Application

Create `main.py`:

```python
import atexit
import json
import logging.config
import logging.handlers
import pathlib

# Create logger for this module
logger = logging.getLogger("my_app")  # or use __name__ for automatic naming


def setup_logging():
    """
    Configure logging from external JSON file.
    This should be called once at application startup.
    """
    # Load configuration file
    config_file = pathlib.Path("logging_configs/5-queued-stderr-json-file.json")
    with open(config_file) as f_in:
        config = json.load(f_in)

    # Apply configuration
    logging.config.dictConfig(config)

    # For Python 3.12+: Start the queue listener
    # This creates a background thread that processes queued log records
    queue_handler = logging.getHandlerByName("queue_handler")
    if queue_handler is not None:
        queue_handler.listener.start()
        # Register cleanup function to stop listener on exit
        atexit.register(queue_handler.listener.stop)


def main():
    # Setup logging FIRST, before any logging calls
    setup_logging()

    # Example usage
    logger.debug("debug message", extra={"x": "hello"})
    logger.info("info message")
    logger.warning("warning message")
    logger.error("error message")
    logger.critical("critical message")

    # Exception logging
    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("exception message")  # Automatically includes traceback


if __name__ == "__main__":
    main()
```

**Key Points**:
- **Call `setup_logging()` early**: Before any logging occurs
- **`getHandlerByName()`**: Python 3.12+ feature to retrieve handlers
- **`queue_handler.listener.start()`**: Starts background thread
- **`atexit.register()`**: Ensures listener stops cleanly, no logs lost
- **`logger.exception()`**: Shortcut for `logger.error(..., exc_info=True)`

### Step 6: Run and Verify

```bash
python main.py
```

**Console output (stderr)**:
```
WARNING: warning message
ERROR: error message
CRITICAL: critical message
ERROR: exception message
```

**File output (`logs/my_app.log.jsonl`)**:
```json
{"level": "DEBUG", "message": "debug message", "timestamp": "2024-01-23T15:20:53.151737+00:00", "logger": "my_app", "module": "main", "function": "main", "line": 25, "thread_name": "MainThread", "x": "hello"}
{"level": "INFO", "message": "info message", "timestamp": "2024-01-23T15:20:53.151737+00:00", "logger": "my_app", "module": "main", "function": "main", "line": 26, "thread_name": "MainThread"}
{"level": "WARNING", "message": "warning message", "timestamp": "2024-01-23T15:20:53.151737+00:00", "logger": "my_app", "module": "main", "function": "main", "line": 27, "thread_name": "MainThread"}
{"level": "ERROR", "message": "error message", "timestamp": "2024-01-23T15:20:53.152735+00:00", "logger": "my_app", "module": "main", "function": "main", "line": 28, "thread_name": "MainThread"}
{"level": "CRITICAL", "message": "critical message", "timestamp": "2024-01-23T15:20:53.152735+00:00", "logger": "my_app", "module": "main", "function": "main", "line": 29, "thread_name": "MainThread"}
{"level": "ERROR", "message": "exception message", "timestamp": "2024-01-23T15:20:53.152735+00:00", "logger": "my_app", "module": "main", "function": "main", "line": 33, "thread_name": "MainThread", "exc_info": "Traceback (most recent call last):\n  File \"main.py\", line 31, in main\n    1 / 0\nZeroDivisionError: division by zero"}
```

## Configuration Progression

This section shows the evolution from simple to advanced logging configurations.

### Level 0: Basic stdout Logging

**File**: `logging_configs/0-stdout.json`

```json
{
  "version": 1,
  "disable_existing_loggers": false,
  "formatters": {
    "simple": {
      "format": "%(levelname)s: %(message)s"
    }
  },
  "handlers": {
    "stdout": {
      "class": "logging.StreamHandler",
      "formatter": "simple",
      "stream": "ext://sys.stdout"
    }
  },
  "loggers": {
    "root": {
      "level": "DEBUG",
      "handlers": ["stdout"]
    }
  }
}
```

**Features**:
- Single output to stdout
- Simple format
- All log levels

**When to use**: Development, simple scripts

### Level 1: Split stderr + File

**File**: `logging_configs/1-stderr-file.json`

```json
{
  "version": 1,
  "disable_existing_loggers": false,
  "formatters": {
    "simple": {
      "format": "%(levelname)s: %(message)s"
    },
    "detailed": {
      "format": "[%(levelname)s|%(module)s|L%(lineno)d] %(asctime)s: %(message)s",
      "datefmt": "%Y-%m-%dT%H:%M:%S%z"
    }
  },
  "handlers": {
    "stderr": {
      "class": "logging.StreamHandler",
      "level": "WARNING",
      "formatter": "simple",
      "stream": "ext://sys.stderr"
    },
    "file": {
      "class": "logging.handlers.RotatingFileHandler",
      "level": "DEBUG",
      "formatter": "detailed",
      "filename": "logs/my_app.log",
      "maxBytes": 10000,
      "backupCount": 3
    }
  },
  "loggers": {
    "root": {
      "level": "DEBUG",
      "handlers": ["stderr", "file"]
    }
  }
}
```

**New Features**:
- Two handlers with different levels
- Rotating file handler (automatic size-based rotation)
- Different formatters for different outputs

**When to use**: Small applications, simple logging needs

### Level 2: JSON Formatting

**File**: `logging_configs/2-stderr-json-file.json`

**Changes from Level 1**:
- File handler uses JSON formatter
- Machine-readable structured logs
- Filename ends with `.jsonl` (JSON Lines format)

**When to use**: Applications that need log analysis, integration with log aggregation tools

### Level 3: Filtered Outputs

**File**: `logging_configs/3-homework-filtered-stdout-stderr.json`

```json
{
  "version": 1,
  "disable_existing_loggers": false,
  "formatters": {
    "simple": {
      "format": "%(levelname)s: %(message)s"
    }
  },
  "filters": {
    "no_errors": {
      "()": "mylogger.NonErrorFilter"
    }
  },
  "handlers": {
    "stdout": {
      "class": "logging.StreamHandler",
      "formatter": "simple",
      "stream": "ext://sys.stdout",
      "filters": ["no_errors"]
    },
    "stderr": {
      "class": "logging.StreamHandler",
      "formatter": "simple",
      "stream": "ext://sys.stderr",
      "level": "WARNING"
    }
  },
  "loggers": {
    "root": {
      "level": "DEBUG",
      "handlers": ["stdout", "stderr"]
    }
  }
}
```

**New Features**:
- Custom filter class
- DEBUG/INFO → stdout
- WARNING/ERROR/CRITICAL → stderr
- No duplicate messages

**When to use**: When you need fine-grained control over log routing

### Level 4: Queue-Based (Production Ready)

**File**: `logging_configs/5-queued-stderr-json-file.json`

**New Features**:
- QueueHandler wraps all other handlers
- Non-blocking logging
- Background thread handles I/O
- Production-ready performance

**When to use**: Production applications, high-performance requirements

## Best Practices

### 1. Configuration Management

**Do**:
```python
# Load from external file
with open("logging_config.json") as f:
    config = json.load(f)
logging.config.dictConfig(config)
```

**Don't**:
```python
# Hardcoded configuration
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    handlers=[...] # 50 lines of handler setup
)
```

**Why**: External configs can be changed without code deployment, different configs for different environments.

### 2. Logger Naming

**Do**:
```python
logger = logging.getLogger(__name__)  # Automatic module-based naming
```

**Don't**:
```python
logger = logging.getLogger("my_logger")  # Hardcoded name
```

**Why**: `__name__` automatically uses module name, creating a logger hierarchy that matches your code structure.

### 3. Log Levels

Use appropriate levels:

| Level | When to Use | Example |
|-------|-------------|---------|
| DEBUG | Detailed diagnostic info | `"User query: SELECT * FROM users WHERE id=123"` |
| INFO | Confirmation things are working | `"User authentication successful"` |
| WARNING | Something unexpected, but app continues | `"Disk space low: 10% remaining"` |
| ERROR | Serious problem, function failed | `"Failed to connect to database"` |
| CRITICAL | Application may crash | `"Out of memory, shutting down"` |

### 4. Structured Logging with Extra

**Do**:
```python
logger.info(
    "User logged in",
    extra={
        "user_id": user.id,
        "ip_address": request.ip,
        "session_id": session.id
    }
)
```

**Output**:
```json
{"level": "INFO", "message": "User logged in", "user_id": 12345, "ip_address": "192.168.1.1", "session_id": "abc-123", ...}
```

**Don't**:
```python
logger.info(f"User {user.id} logged in from {request.ip}")
```

**Why**: Structured fields are queryable and indexable in log analysis tools.

### 5. Exception Logging

**Do**:
```python
try:
    risky_operation()
except Exception as e:
    logger.exception("Operation failed")  # Includes traceback
    # or
    logger.error("Operation failed", exc_info=True)
```

**Don't**:
```python
try:
    risky_operation()
except Exception as e:
    logger.error(f"Error: {e}")  # No traceback!
```

**Why**: Tracebacks are essential for debugging.

### 6. Performance Considerations

**Do**:
```python
# Lazy string formatting
logger.debug("Processing item %s", item_id)

# Or use f-strings for complex formatting (they're fast)
logger.debug(f"Processing {len(items)} items: {items}")
```

**Don't**:
```python
# Eager formatting for unused logs
logger.debug("Processing item {}".format(expensive_function()))  # Called even if DEBUG disabled!
```

**Why**: With lazy formatting, the string is only formatted if the log will actually be emitted.

### 7. File Rotation

**Configure appropriate rotation**:
```json
{
  "class": "logging.handlers.RotatingFileHandler",
  "maxBytes": 10485760,  // 10 MB
  "backupCount": 5
}
```

**Or time-based rotation**:
```json
{
  "class": "logging.handlers.TimedRotatingFileHandler",
  "when": "midnight",
  "interval": 1,
  "backupCount": 7
}
```

**Why**: Prevents logs from consuming all disk space.

### 8. Environment-Specific Configs

**Directory structure**:
```
logging_configs/
├── development.json
├── staging.json
└── production.json
```

**Load based on environment**:
```python
import os

env = os.getenv("APP_ENV", "development")
config_file = f"logging_configs/{env}.json"
```

### 9. Sensitive Information

**Do**:
```python
# Create a filter to redact sensitive data
class RedactSensitiveFilter(logging.Filter):
    def filter(self, record):
        record.msg = record.msg.replace(password, "***REDACTED***")
        return True
```

**Don't**:
```python
logger.info(f"User logged in with password: {password}")  # NEVER!
```

### 10. Testing with Logging

**Use `caplog` in pytest**:
```python
def test_something(caplog):
    with caplog.at_level(logging.INFO):
        my_function()

    assert "Expected message" in caplog.text
    assert any(record.levelname == "ERROR" for record in caplog.records)
```

## Troubleshooting

### Problem: No logs appearing

**Check**:
1. Is `setup_logging()` called before any logging?
2. Is logger level too high? (e.g., logger.info but level is WARNING)
3. Is `disable_existing_loggers` set to `true`? Should be `false`
4. Are you using the right logger name?

**Debug**:
```python
# See all loggers and their levels
import logging
print(logging.Logger.manager.loggerDict)
print(logging.getLogger().level)  # Root logger level
```

### Problem: Logs appearing twice

**Cause**: Multiple handlers at different levels of logger hierarchy

**Fix**:
```python
logger.propagate = False  # Don't propagate to parent logger
```

**Or** ensure handlers are only on root logger:
```json
{
  "loggers": {
    "root": {
      "handlers": ["my_handler"]
    },
    "my_app": {
      "level": "DEBUG"
      // No handlers here - inherits from root
    }
  }
}
```

### Problem: JSON formatting errors

**Cause**: Non-serializable objects in extra fields

**Fix**:
```python
# In formatter
json.dumps(message, default=str)  # Converts non-serializable to string
```

**Or** use a custom JSON encoder:
```python
class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)

# In formatter
json.dumps(message, cls=CustomEncoder)
```

### Problem: File not rotating

**Check**:
1. Is `maxBytes` large enough? (maybe file never reaches limit)
2. File permissions correct?
3. Multiple processes writing to same file? (use different files or QueueListener with MultiProcessing)

**Debug**:
```python
handler = logging.getHandlerByName("file_json")
print(f"Current size: {os.path.getsize(handler.baseFilename)}")
print(f"Max bytes: {handler.maxBytes}")
```

### Problem: Queue not working (Python 3.12+)

**Check**:
1. Did you call `queue_handler.listener.start()`?
2. Is `atexit.register()` called for cleanup?
3. Python version is actually 3.12+?

**Verify**:
```python
import sys
print(sys.version_info)  # Should be (3, 12, ...) or higher

queue_handler = logging.getHandlerByName("queue_handler")
print(queue_handler)  # Should not be None
print(hasattr(queue_handler, 'listener'))  # Should be True for 3.12+
```

### Problem: Slow logging performance

**Solutions**:
1. Use QueueHandler to make logging async
2. Reduce log level in production (INFO instead of DEBUG)
3. Use lazy string formatting
4. Consider sampling (log only 1% of requests)

**Measure**:
```python
import time

start = time.perf_counter()
for i in range(10000):
    logger.debug("Test message %d", i)
end = time.perf_counter()
print(f"10,000 logs in {end - start:.3f} seconds")
```

## Python Version Notes

### Python 3.12+

Full support as shown in tutorial. QueueHandler automatically creates and manages QueueListener.

### Python 3.9 - 3.11

**QueueHandler needs manual setup**:

```python
import queue
import logging.handlers

def setup_logging():
    # ... load config ...
    logging.config.dictConfig(config)

    # Manual queue setup
    log_queue = queue.Queue()
    queue_handler = logging.handlers.QueueHandler(log_queue)

    # Get the handlers that should receive logs
    file_handler = logging.getHandlerByName("file_json")
    stderr_handler = logging.getHandlerByName("stderr")

    # Create and start listener
    listener = logging.handlers.QueueListener(
        log_queue,
        file_handler,
        stderr_handler,
        respect_handler_level=True
    )
    listener.start()
    atexit.register(listener.stop)

    # Replace root handler
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(queue_handler)
```

### Python 3.8 and Below

**Change "root" to ""**:

```json
{
  "loggers": {
    "": {  // Empty string instead of "root"
      "level": "DEBUG",
      "handlers": ["stdout"]
    }
  }
}
```

**Or use top-level "root" key**:

```json
{
  "root": {  // Top-level, not under "loggers"
    "level": "DEBUG",
    "handlers": ["stdout"]
  },
  "loggers": {
    "my_app": {
      "level": "DEBUG"
    }
  }
}
```

## Advanced Topics

### Custom Handlers

Create handlers for specific destinations:

```python
class SlackHandler(logging.Handler):
    """Send ERROR+ logs to Slack."""

    def __init__(self, webhook_url):
        super().__init__()
        self.webhook_url = webhook_url

    def emit(self, record):
        msg = self.format(record)
        # Send to Slack
        requests.post(self.webhook_url, json={"text": msg})
```

### Context Managers for Log Context

```python
import contextvars

request_id = contextvars.ContextVar('request_id', default=None)

class ContextFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id.get()
        return True

# Usage
request_id.set("abc-123")
logger.info("Processing request")  # Will include request_id in output
```

### Sampling for High-Volume Logs

```python
import random

class SamplingFilter(logging.Filter):
    def __init__(self, rate=0.1):
        self.rate = rate

    def filter(self, record):
        return random.random() < self.rate

# Log only 10% of DEBUG messages
```

### Multiple Configurations

```python
class LoggerFactory:
    @staticmethod
    def get_logger(name, config_name="default"):
        config_file = f"logging_configs/{config_name}.json"
        with open(config_file) as f:
            config = json.load(f)
        logging.config.dictConfig(config)
        return logging.getLogger(name)

# Different configs for different modules
api_logger = LoggerFactory.get_logger("api", "api_config")
db_logger = LoggerFactory.get_logger("database", "db_config")
```

## Conclusion

You now have a comprehensive understanding of modern Python logging:

1. **Structured logging** with JSON formatters
2. **Async, non-blocking** logging with QueueHandler
3. **Flexible routing** with multiple handlers and filters
4. **Configuration-based** setup for different environments
5. **Production-ready** patterns with rotation and cleanup

### Next Steps

1. Implement in your project
2. Create environment-specific configs
3. Integrate with log aggregation (ELK, Splunk, CloudWatch)
4. Monitor log volume and performance
5. Set up alerts on ERROR/CRITICAL logs

### Resources

- [Python Logging Documentation](https://docs.python.org/3/library/logging.html)
- [Python Logging Cookbook](https://docs.python.org/3/howto/logging-cookbook.html)
- [Logging Best Practices](https://docs.python.org/3/howto/logging.html#logging-basic-tutorial)

Happy logging!
